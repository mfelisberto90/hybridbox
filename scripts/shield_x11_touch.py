#!/data/data/com.termux/files/usr/bin/python3
"""
Bloqueador Duplo de Toques Fantasmas (X11 XInput + Kernel evdev EVIOCGRAB)
para o Redmi Note 8 Pro e Configurador do Navegador Padrão XFCE4 (Firefox).

1. Nível X11 (Termux:X11 DISPLAY=:0):
   Desativa os dispositivos escravos XInput 'Lorie mouse' e 'Lorie touch',
   mantendo apenas o 'Virtual core XTEST pointer' ativo.
2. Nível Kernel Android (/dev/input/event2 — NVTCapacitiveTouchScreen):
   Compila (se necessário) e inicia o daemon `/data/local/tmp/grab_ghost_touch --daemon`
   como uid=2000(shell) [gid=1004(input)], aplicando `ioctl(fd, EVIOCGRAB, 1)` para
   bloquear os eventos fantasmas de 120Hz no InputReader/InputDispatcher do Android
   e limpando quaisquer ponteiros presos (`TouchStates: <no displays touched>`).
3. Nível XFCE4 Desktop:
   Configura `~/.config/xfce4/helpers.rc`, `~/.local/share/xfce4/helpers/firefox.desktop`
   e `~/.local/share/applications/firefox.desktop` com `MOZ_DISABLE_CONTENT_SANDBOX=1`
   para que o navegador funcione tanto pelo botão do PWA quanto pelos ícones do painel XFCE4.
"""

import os
import shutil
import subprocess
import sys


def patch_termux_xlib_socket() -> None:
    try:
        import Xlib.support.unix_connect as uc

        orig_get_unix = uc._get_unix_socket

        def termux_unix_socket(address: str):
            clean = address.lstrip("\0")
            if clean.startswith("/tmp/.X11-unix/"):
                termux_addr = "/data/data/com.termux/files/usr" + clean
                if os.path.exists(termux_addr):
                    address = termux_addr
            return orig_get_unix(address)

        uc._get_unix_socket = termux_unix_socket
    except Exception:
        pass


def disable_lorie_physical_touch(display_name: str = ":0") -> int:
    """Desativa 'Lorie mouse' e 'Lorie touch' via XInput no servidor Termux:X11."""
    patch_termux_xlib_socket()
    disabled_count = 0
    try:
        from Xlib import X, Xatom, display
        from Xlib.ext import xinput

        d = display.Display(display_name)
        prop_atom = d.get_atom("Device Enabled")
        info = d.xinput_query_device(xinput.AllDevices)
        for dev in info.devices:
            if dev.name in ("Lorie mouse", "Lorie touch") and getattr(dev, "enabled", 1) != 0:
                d.xinput_change_device_property(
                    dev.deviceid,
                    prop_atom,
                    Xatom.INTEGER,
                    X.PropModeReplace,
                    (8, [0]),
                )
                disabled_count += 1
        d.sync()
        d.close()
    except Exception:
        pass
    return disabled_count


def ensure_kernel_evdev_grab() -> str:
    """
    Garante que o daemon `/data/local/tmp/grab_ghost_touch --daemon` esteja ativo
    segurando `EVIOCGRAB` no `/dev/input/event2` (NVTCapacitiveTouchScreen).
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    c_src = os.path.join(script_dir, "grab_ghost_touch.c")
    tmp_bin = "/data/data/com.termux/files/usr/tmp/grab_ghost_touch"
    clang_bin = shutil.which("clang") or "/data/data/com.termux/files/usr/bin/clang"

    if (
        not os.path.exists("/data/local/tmp/grab_ghost_touch")
        and not os.path.exists(tmp_bin)
        and os.path.exists(c_src)
        and os.path.exists(clang_bin)
    ):
        try:
            subprocess.run(
                [clang_bin, "-O2", c_src, "-o", tmp_bin],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8.0,
            )
        except Exception:
            pass

    shell_cmd = (
        "if ps -ef | grep -q '[g]rab_ghost_touch'; then echo ALREADY_RUNNING; exit 0; fi; "
        "if [ ! -x /data/local/tmp/grab_ghost_touch ]; then "
        "if [ -f /sdcard/grab_ghost_touch ]; then "
        "cp /sdcard/grab_ghost_touch /data/local/tmp/grab_ghost_touch && chmod 755 /data/local/tmp/grab_ghost_touch; "
        f"else run-as com.termux /data/data/com.termux/files/usr/bin/cat {tmp_bin} > /data/local/tmp/grab_ghost_touch.tmp 2>/dev/null && "
        "[ -s /data/local/tmp/grab_ghost_touch.tmp ] && mv /data/local/tmp/grab_ghost_touch.tmp /data/local/tmp/grab_ghost_touch && "
        "chmod 755 /data/local/tmp/grab_ghost_touch; fi; fi; "
        "if [ -x /data/local/tmp/grab_ghost_touch ]; then "
        "OUT=$(/data/local/tmp/grab_ghost_touch --daemon 2>&1); "
        'echo "$OUT"; '
        'case "$OUT" in *GRAB_OK*) input tap 1 1 >/dev/null 2>&1 || true ;; esac; '
        "fi"
    )

    hb_shell = "/data/data/com.termux/files/usr/bin/hb-shell"
    if os.path.exists(hb_shell):
        try:
            res = subprocess.run(
                [hb_shell, shell_cmd],
                capture_output=True,
                text=True,
                timeout=4.0,
            )
            if res.stdout:
                return res.stdout.strip()
        except Exception:
            pass

    if os.geteuid() == 2000:
        try:
            res = subprocess.run(
                ["/system/bin/sh", "-c", shell_cmd],
                capture_output=True,
                text=True,
                timeout=4.0,
            )
            if res.stdout:
                return res.stdout.strip()
        except Exception:
            pass

    return "SKIPPED"


def _write_if_changed(path: str, content: str) -> None:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                if f.read() == content:
                    return
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass


def ensure_xfce_browser_helper() -> None:
    """
    Garante que o XFCE4 (`exo-open --launch WebBrowser` e atalhos do painel/menu)
    use o Firefox com `MOZ_DISABLE_CONTENT_SANDBOX=1`.
    """
    home = os.environ.get("HOME") or "/data/data/com.termux/files/home"
    xfce_dir = os.path.join(home, ".config", "xfce4")
    local_helpers_dir = os.path.join(home, ".local", "share", "xfce4", "helpers")
    local_apps_dir = os.path.join(home, ".local", "share", "applications")
    os.makedirs(xfce_dir, exist_ok=True)
    os.makedirs(local_helpers_dir, exist_ok=True)
    os.makedirs(local_apps_dir, exist_ok=True)

    helpers_rc = os.path.join(xfce_dir, "helpers.rc")
    desired_rc = "WebBrowser=firefox\nTerminalEmulator=xfce4-terminal\nFileManager=thunar\n"
    _write_if_changed(helpers_rc, desired_rc)

    helper_desktop = os.path.join(local_helpers_dir, "firefox.desktop")
    helper_content = (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Icon=firefox\n"
        "Type=X-XFCE-Helper\n"
        "Name=Mozilla Firefox\n"
        "StartupNotify=false\n"
        "X-XFCE-Binaries=firefox;\n"
        "X-XFCE-Category=WebBrowser\n"
        "X-XFCE-Commands=env MOZ_DISABLE_CONTENT_SANDBOX=1 %B;\n"
        'X-XFCE-CommandsWithParameter=env MOZ_DISABLE_CONTENT_SANDBOX=1 %B "%s";\n'
    )
    _write_if_changed(helper_desktop, helper_content)

    app_desktop = os.path.join(local_apps_dir, "firefox.desktop")
    app_content = (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Name=Firefox Web Browser\n"
        "GenericName=Web Browser\n"
        "Exec=env MOZ_DISABLE_CONTENT_SANDBOX=1 firefox %u\n"
        "Terminal=false\n"
        "Type=Application\n"
        "Icon=firefox\n"
        "Categories=Network;WebBrowser;\n"
        "StartupWMClass=firefox\n"
    )
    _write_if_changed(app_desktop, app_content)


def apply_termux_x11_preferences() -> None:
    """Oculta a barra de teclas extras do Termux:X11 e desativa tapToMove para blindar contra toques fantasmas."""
    pref_bin = "/data/data/com.termux/files/usr/bin/termux-x11-preference"
    if not os.path.exists(pref_bin):
        return
    try:
        subprocess.run(
            [
                pref_bin,
                "showAdditionalKbd:false",
                "additionalKbdVisible:false",
                "tapToMove:false",
                "swipeDownAction:no action",
                "swipeUpAction:no action",
                "volumeUpAction:no action",
                "volumeDownAction:no action",
                "mediaKeysAction:no action",
                "showMouseHelper:false",
                "fullscreen:true",
                "hideCutout:true",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3.5,
        )
    except Exception:
        pass


if __name__ == "__main__":
    dpy = os.environ.get("DISPLAY") or ":0"
    ensure_xfce_browser_helper()
    n = disable_lorie_physical_touch(dpy)
    grab_status = ensure_kernel_evdev_grab()
    if "--full" in sys.argv:
        apply_termux_x11_preferences()
    print(f"SHIELD_OK disabled={n} evdev={grab_status}")
