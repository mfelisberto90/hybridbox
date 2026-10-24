"""
Controlador de Input X11 de Latência Zero para Termux:X11 (DISPLAY=:0).
Utiliza python-xlib (XTest extension) em memória com fallback automático
para processo persistente `xdotool -` via pipe stdin.
"""

import os
import shlex
import shutil
import subprocess
import threading
import time
from typing import Any, Optional

try:
    import Xlib.support.unix_connect as _uc

    _orig_get_unix = _uc._get_unix_socket

    def _termux_unix_socket(address: str):
        clean = address.lstrip("\0")
        if clean.startswith("/tmp/.X11-unix/"):
            termux_addr = "/data/data/com.termux/files/usr" + clean
            if os.path.exists(termux_addr):
                address = termux_addr
        return _orig_get_unix(address)

    _uc._get_unix_socket = _termux_unix_socket
    from Xlib import X, XK, Xatom, display
    from Xlib.ext import xinput, xtest

    HAS_XLIB = True
except Exception:
    HAS_XLIB = False


SPECIAL_KEYSYMS = {
    "Enter": "Return",
    "Return": "Return",
    "Backspace": "BackSpace",
    "BackSpace": "BackSpace",
    "Tab": "Tab",
    "Escape": "Escape",
    "Esc": "Escape",
    "Space": "space",
    " ": "space",
    "ArrowUp": "Up",
    "Up": "Up",
    "ArrowDown": "Down",
    "Down": "Down",
    "ArrowLeft": "Left",
    "Left": "Left",
    "ArrowRight": "Right",
    "Right": "Right",
    "Home": "Home",
    "End": "End",
    "PageUp": "Prior",
    "PageDown": "Next",
    "Delete": "Delete",
    "Super": "Super_L",
    "Meta": "Super_L",
}


class X11Controller:
    """Injeta movimentos de mouse, cliques, scroll e teclado diretamente no DISPLAY=:0."""

    def __init__(
        self, display_name: str = ":0", android_controller: Optional[Any] = None
    ) -> None:
        self.display_name = os.environ.get("DISPLAY", display_name) or ":0"
        self.android = android_controller
        self._lock = threading.Lock()
        self._dpy: Optional["display.Display"] = None
        self._root = None
        self._xdotool_proc: Optional[subprocess.Popen] = None
        self._backend_type = "none"
        self._rem_x: float = 0.0
        self._rem_y: float = 0.0
        self._last_move_ts: float = 0.0
        self._last_shield_ts: float = 0.0
        self._connect()

    def _is_pipe_backend(self) -> bool:
        return self._backend_type in (
            "xdotool-pipe",
            f"adb-termux-xdotool ({self.display_name})",
            f"ssh-termux-xdotool ({self.display_name})",
        )

    def _is_remote_android_backend(self) -> bool:
        return self.android is not None and (
            os.name == "nt"
            or self._backend_type.startswith("adb-termux-xdotool")
            or self._backend_type.startswith("ssh-termux-xdotool")
            or (self._backend_type != "python-xlib" and not shutil.which("xdotool"))
        )

    def disable_physical_touch_devices(self, force: bool = False) -> None:
        """
        Desativa 'Lorie mouse' e 'Lorie touch' no X11 para impedir que o touch físico quebrado
        do Redmi Note 8 Pro faça o cursor tremer ou clicar sozinho no Linux Desktop.
        """
        now = time.time()
        if not force and (now - self._last_shield_ts < 8.0):
            return
        self._last_shield_ts = now

        if HAS_XLIB and self._dpy is not None:
            try:
                prop_atom = self._dpy.get_atom("Device Enabled")
                info = self._dpy.xinput_query_device(xinput.AllDevices)
                for dev in info.devices:
                    if dev.name in ("Lorie mouse", "Lorie touch") and getattr(dev, "enabled", 1) != 0:
                        self._dpy.xinput_change_device_property(
                            dev.deviceid,
                            prop_atom,
                            Xatom.INTEGER,
                            X.PropModeReplace,
                            (8, [0]),
                        )
                self._dpy.sync()
                return
            except Exception:
                pass

        if self.android is not None:
            flag = "--full" if force else ""
            self.android.send_raw_command(
                "run-as com.termux /data/data/com.termux/files/usr/bin/env "
                f"DISPLAY={self.display_name} "
                "HOME=/data/data/com.termux/files/home "
                "PREFIX=/data/data/com.termux/files/usr "
                "PATH=/data/data/com.termux/files/usr/bin:/system/bin "
                "LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib "
                "/data/data/com.termux/files/usr/bin/python3 "
                f"/data/data/com.termux/files/home/hybridbox-remote-pwa/scripts/shield_x11_touch.py {flag} >/dev/null 2>&1 &"
            )

    def _connect(self) -> None:
        """Inicializa conexão persistente com X11 via python-xlib, xdotool local ou ADB Termux xdotool."""
        os.environ["DISPLAY"] = self.display_name
        if HAS_XLIB and os.name != "nt":
            try:
                self._dpy = display.Display(self.display_name)
                self._root = self._dpy.screen().root
                self._backend_type = "python-xlib"
                self.disable_physical_touch_devices(force=True)
                return
            except Exception:
                self._dpy = None
                self._root = None

        if shutil.which("xdotool") and os.name != "nt":
            try:
                env = os.environ.copy()
                env["DISPLAY"] = self.display_name
                self._xdotool_proc = subprocess.Popen(
                    ["xdotool", "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    env=env,
                )
                self._backend_type = "xdotool-pipe"
                self.disable_physical_touch_devices(force=True)
                return
            except Exception:
                self._xdotool_proc = None

        # 3. Se estiver rodando no Host Windows/PC com celular conectado via ADB ou Wi-Fi SSH,
        # abre pipe persistente para o `xdotool -` dentro do Termux (DISPLAY=:0)
        if self.android is not None:
            adb_bin = self.android._find_adb()
            serial = ""
            if adb_bin:
                serial = self.android.active_serial or self.android._resolve_target_serial(
                    adb_bin
                )
            try:
                check = self.android.run_adb_shell(
                    "run-as com.termux /data/data/com.termux/files/usr/bin/env "
                    f"DISPLAY={self.display_name} "
                    "HOME=/data/data/com.termux/files/home "
                    "PREFIX=/data/data/com.termux/files/usr "
                    "PATH=/data/data/com.termux/files/usr/bin:/system/bin "
                    "LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib "
                    "/data/data/com.termux/files/usr/bin/bash -c "
                    "'if [ -x /data/data/com.termux/files/usr/bin/xdotool ]; then "
                    "pgrep -f \"[t]ermux.x11\" >/dev/null 2>&1 || (nohup termux-x11 :0 -ac </dev/null >/dev/null 2>&1 & sleep 1); "
                    "echo XDOTOOL_READY; fi'",
                    timeout=4.0,
                )
                if "XDOTOOL_READY" in (check or ""):
                    if adb_bin and serial:
                        remote_cmd = (
                            "run-as com.termux /data/data/com.termux/files/usr/bin/env "
                            f"DISPLAY={self.display_name} "
                            "HOME=/data/data/com.termux/files/home "
                            "PREFIX=/data/data/com.termux/files/usr "
                            "PATH=/data/data/com.termux/files/usr/bin:/system/bin "
                            "LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib "
                            "/data/data/com.termux/files/usr/bin/xdotool -"
                        )
                        self._xdotool_proc = subprocess.Popen(
                            [adb_bin, "-s", serial, "shell", remote_cmd],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            text=True,
                            bufsize=1,
                        )
                        self._backend_type = f"adb-termux-xdotool ({self.display_name})"
                        self.disable_physical_touch_devices(force=True)
                        return

                    ssh_bin = shutil.which("ssh")
                    if ssh_bin:
                        ssh_cmd = (
                            f"export DISPLAY={self.display_name}; "
                            "export HOME=/data/data/com.termux/files/home; "
                            "export PREFIX=/data/data/com.termux/files/usr; "
                            "export PATH=/data/data/com.termux/files/usr/bin:/system/bin; "
                            "export LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib; "
                            "exec /data/data/com.termux/files/usr/bin/xdotool -"
                        )
                        self._xdotool_proc = subprocess.Popen(
                            [
                                ssh_bin,
                                "-p",
                                str(self.android.ssh_port),
                                "-o",
                                "ConnectTimeout=3",
                                "-o",
                                "BatchMode=yes",
                                "-o",
                                "StrictHostKeyChecking=no",
                                f"{self.android.ssh_user}@{self.android.ssh_host}",
                                ssh_cmd,
                            ],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            text=True,
                            bufsize=1,
                        )
                        self._backend_type = f"ssh-termux-xdotool ({self.display_name})"
                        self.disable_physical_touch_devices(force=True)
                        return
            except Exception:
                self._xdotool_proc = None

        self._backend_type = "simulated"

    @property
    def backend_name(self) -> str:
        return self._backend_type

    def is_connected(self) -> bool:
        if self._backend_type == "python-xlib" and self._dpy is not None:
            return True
        if (
            self._is_pipe_backend()
            and self._xdotool_proc is not None
            and self._xdotool_proc.poll() is None
        ):
            return True
        return False

    def _ensure_connection(self) -> None:
        if not self.is_connected():
            self._connect()

    def _send_xdotool(self, cmd: str) -> None:
        if self._xdotool_proc and self._xdotool_proc.stdin:
            try:
                self._xdotool_proc.stdin.write(cmd + "\n")
                self._xdotool_proc.stdin.flush()
            except Exception:
                self._connect()

    def move_relative(self, dx: float, dy: float) -> None:
        """Move o cursor relativamente por (dx, dy) pixels com acumulação sub-pixel e filtro anti-tremor."""
        if abs(dx) < 0.25 and abs(dy) < 0.25:
            return

        now = time.time()
        with self._lock:
            if now - self._last_move_ts > 0.18:
                self._rem_x = 0.0
                self._rem_y = 0.0
            self._last_move_ts = now

            total_x = self._rem_x + dx
            total_y = self._rem_y + dy
            ix = int(total_x)
            iy = int(total_y)
            self._rem_x = total_x - ix
            self._rem_y = total_y - iy

            if ix == 0 and iy == 0:
                return

            self.disable_physical_touch_devices(force=False)
            self._ensure_connection()
            if self._backend_type == "python-xlib" and self._dpy:
                try:
                    xtest.fake_input(self._dpy, X.MotionNotify, detail=1, x=ix, y=iy)
                    self._dpy.flush()
                    return
                except Exception:
                    try:
                        self._dpy.warp_pointer(ix, iy)
                        self._dpy.flush()
                        return
                    except Exception:
                        self._connect()

            if self._is_pipe_backend():
                self._send_xdotool(f"mousemove_relative -- {ix} {iy}")

    def mouse_button(self, button: int = 1, down: bool = True) -> None:
        """Pressiona ou solta um botão do mouse (1=Esq, 2=Meio, 3=Dir)."""
        with self._lock:
            self._ensure_connection()
            if self._backend_type == "python-xlib" and self._dpy:
                try:
                    event_type = X.ButtonPress if down else X.ButtonRelease
                    xtest.fake_input(self._dpy, event_type, button)
                    self._dpy.flush()
                    return
                except Exception:
                    self._connect()

            if self._is_pipe_backend():
                action = "mousedown" if down else "mouseup"
                self._send_xdotool(f"{action} {button}")

    def click(self, button: int = 1, count: int = 1) -> None:
        """Executa clique simples ou duplo no botão especificado."""
        with self._lock:
            self.disable_physical_touch_devices(force=False)
            self._ensure_connection()
            if self._backend_type == "python-xlib" and self._dpy:
                try:
                    for _ in range(max(1, count)):
                        xtest.fake_input(self._dpy, X.ButtonPress, button)
                        xtest.fake_input(self._dpy, X.ButtonRelease, button)
                    self._dpy.flush()
                    return
                except Exception:
                    self._connect()

            if self._is_pipe_backend():
                self._send_xdotool(f"click --repeat {max(1, count)} {button}")

    def scroll(self, dx: float = 0.0, dy: float = 0.0) -> None:
        """
        Injeta eventos de rolagem no X11:
        Button 4 = Scroll Up, Button 5 = Scroll Down,
        Button 6 = Scroll Left, Button 7 = Scroll Right.
        """
        with self._lock:
            self._ensure_connection()
            buttons = []
            if abs(dy) >= 1.0:
                btn_y = 4 if dy < 0 else 5
                steps_y = min(5, max(1, int(abs(dy) // 12) or 1))
                buttons.extend([btn_y] * steps_y)
            if abs(dx) >= 1.0:
                btn_x = 6 if dx < 0 else 7
                steps_x = min(5, max(1, int(abs(dx) // 12) or 1))
                buttons.extend([btn_x] * steps_x)

            if not buttons:
                return

            if self._backend_type == "python-xlib" and self._dpy:
                try:
                    for btn in buttons:
                        xtest.fake_input(self._dpy, X.ButtonPress, btn)
                        xtest.fake_input(self._dpy, X.ButtonRelease, btn)
                    self._dpy.flush()
                    return
                except Exception:
                    self._connect()

            if self._is_pipe_backend():
                for btn in buttons:
                    self._send_xdotool(f"click {btn}")

    def send_key(self, key_name: str) -> None:
        """Envia uma tecla ou combinação de atalho (ex: 'Return', 'Alt+Tab', 'ctrl+c')."""
        with self._lock:
            self._ensure_connection()
            mapped = SPECIAL_KEYSYMS.get(key_name, key_name)

            if "+" in mapped and self._is_pipe_backend():
                self._send_xdotool(f"key --clearmodifiers {mapped}")
                return

            if self._backend_type == "python-xlib" and self._dpy:
                try:
                    if "+" in mapped:
                        parts = [SPECIAL_KEYSYMS.get(p, p) for p in mapped.split("+")]
                        mod_map = {
                            "ctrl": "Control_L",
                            "control": "Control_L",
                            "alt": "Alt_L",
                            "shift": "Shift_L",
                            "super": "Super_L",
                        }
                        keycodes = []
                        for p in parts:
                            sym_name = mod_map.get(p.lower(), p)
                            ks = XK.string_to_keysym(sym_name)
                            if ks == 0 and len(sym_name) == 1:
                                ks = XK.string_to_keysym(sym_name.lower())
                            kc = self._dpy.keysym_to_keycode(ks) if ks else 0
                            if kc:
                                keycodes.append(kc)
                        for kc in keycodes:
                            xtest.fake_input(self._dpy, X.KeyPress, kc)
                        for kc in reversed(keycodes):
                            xtest.fake_input(self._dpy, X.KeyRelease, kc)
                        self._dpy.flush()
                        return

                    ks = XK.string_to_keysym(mapped)
                    if ks == 0 and len(mapped) == 1:
                        ks = ord(mapped)
                    kc = self._dpy.keysym_to_keycode(ks) if ks else 0
                    if kc:
                        xtest.fake_input(self._dpy, X.KeyPress, kc)
                        xtest.fake_input(self._dpy, X.KeyRelease, kc)
                        self._dpy.flush()
                        return
                except Exception:
                    self._connect()

            if self._is_pipe_backend():
                self._send_xdotool(f"key {mapped}")

    def send_text(self, text: str) -> None:
        """Digita uma string completa no X11."""
        if not text:
            return
        if shutil.which("xdotool") and os.name != "nt":
            env = os.environ.copy()
            env["DISPLAY"] = self.display_name
            subprocess.Popen(
                ["xdotool", "type", "--clearmodifiers", "--delay", "5", "--", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            return

        if self._is_remote_android_backend():
            safe_txt = shlex.quote(text)
            self.android.send_raw_command(
                "run-as com.termux /data/data/com.termux/files/usr/bin/env "
                f"DISPLAY={self.display_name} "
                "PATH=/data/data/com.termux/files/usr/bin:/system/bin "
                "LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib "
                f"/data/data/com.termux/files/usr/bin/xdotool type --clearmodifiers --delay 5 -- {safe_txt} >/dev/null 2>&1 &"
            )
            return

        for ch in text:
            if ch == "\n":
                self.send_key("Return")
            elif ch == " ":
                self.send_key("space")
            else:
                self.send_key(ch)

    def launch_linux_command(self, cmd: str) -> None:
        """Executa um comando gráfico na sessão DISPLAY=:0 do Termux:X11."""
        self.disable_physical_touch_devices(force=True)
        if self._is_remote_android_backend():
            safe_cmd = shlex.quote(cmd)
            self.android.send_raw_command(
                "run-as com.termux /data/data/com.termux/files/usr/bin/env "
                f"DISPLAY={self.display_name} "
                "HOME=/data/data/com.termux/files/home "
                "PREFIX=/data/data/com.termux/files/usr "
                "PATH=/data/data/com.termux/files/usr/bin:/system/bin "
                "LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib "
                f"/data/data/com.termux/files/usr/bin/bash -c {safe_cmd} >/dev/null 2>&1 &"
            )
            return

        env = os.environ.copy()
        env["DISPLAY"] = self.display_name
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

