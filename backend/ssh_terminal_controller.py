"""
Controlador de Terminal SSH Interativo e Atualização via Wi-Fi (OTA Sync)
para o HybridBox Remote PWA.

Funcionalidades:
1. Terminal Web Interativo (estilo xterm) conectado diretamente ao Android/Termux via Wi-Fi SSH
   (porta 8022) ou ADB Shell, além de modo shell local no Laptop.
2. Configuração automática do servidor OpenSSH (`sshd` na porta 8022) no Termux do Redmi Note 8 Pro,
   com injeção automática da chave pública SSH do laptop (`~/.ssh/id_ed25519.pub`) e criação do atalho
   `ssh hybridbox` no `~/.ssh/config` do Windows.
3. Atualização/Sincronização 1-Clique via Wi-Fi (`scp -P 8022` / `adb push`) do código-fonte do laptop
   direto para o Redmi Note 8 Pro (`hybridbox.local`) sem precisar mexer no celular.
4. Botão para abrir uma janela nativa de Terminal SSH (`PowerShell / OpenSSH`) direto na tela do Laptop.
"""

import ctypes
import os
import re
import shlex
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional


class SshTerminalController:
    """Gerencia acesso SSH via Wi-Fi, terminal web interativo e atualização OTA do projeto."""

    def __init__(self, android_controller: Any, base_dir: Path) -> None:
        self.android = android_controller
        self.base_dir = base_dir
        self.android_cwd = "/data/data/com.termux/files/home/hybridbox-remote-pwa"
        self.host_cwd = str(base_dir)
        self.cached_phone_ip: str = (
            os.environ.get("HYBRIDBOX_SSH_HOST", "")
            or getattr(android_controller, "ssh_host", "")
            or "hybridbox.local"
        )
        self.cached_ssh_user: str = (
            os.environ.get("HYBRIDBOX_SSH_USER", "")
            or getattr(android_controller, "ssh_user", "")
            or "termux"
        )
        self.ssh_port: int = int(os.environ.get("HYBRIDBOX_SSH_PORT", "8022"))

    def _run_adb(self, shell_cmd: str, timeout: float = 8.0) -> str:
        """Executa comando ADB shell com serial explícito e retorna stdout + stderr."""
        try:
            out = self.android.run_adb_shell(shell_cmd, timeout=timeout, include_stderr=True)
            return (out or "").strip()
        except Exception as exc:
            return f"[Erro ADB: {exc}]"

    def _run_termux(self, termux_cmd: str, timeout: float = 20.0) -> str:
        """Executa comando dentro do container Termux (local direto se rodando no Termux, ou via SSH porta 8022 no PC)."""
        full_cmd = (
            "export HOME=/data/data/com.termux/files/home; "
            "export PREFIX=/data/data/com.termux/files/usr; "
            "export PATH=/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin; "
            "export LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib; "
            f"{termux_cmd}"
        )
        if os.path.exists("/data/data/com.termux/files/usr/bin/bash"):
            try:
                res = subprocess.run(
                    ["/data/data/com.termux/files/usr/bin/bash", "-c", full_cmd],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
                out = (res.stdout or "") + (res.stderr or "")
                if res.returncode == 0 or out.strip():
                    return out.strip()
            except Exception:
                pass

        ssh_bin = shutil.which("ssh")
        phone_ip = (
            self.android.discover_phone_ip()
            if hasattr(self.android, "discover_phone_ip")
            else self.cached_phone_ip
        )
        if hasattr(self.android, "discover_ssh_user"):
            self.cached_ssh_user = self.android.discover_ssh_user()
        if ssh_bin and phone_ip and self._check_tcp_port(phone_ip, self.ssh_port, timeout=0.6):
            try:
                res = subprocess.run(
                    [
                        ssh_bin,
                        "-n",
                        "-p",
                        str(self.ssh_port),
                        "-o",
                        "ConnectTimeout=3",
                        "-o",
                        "BatchMode=yes",
                        "-o",
                        "StrictHostKeyChecking=no",
                        f"{self.cached_ssh_user}@{phone_ip}",
                        full_cmd,
                    ],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
                out = (res.stdout or "") + (res.stderr or "")
                if res.returncode == 0 or out.strip():
                    return out.strip()
            except Exception:
                pass
        env_cmd = (
            "run-as com.termux /data/data/com.termux/files/usr/bin/env "
            "HOME=/data/data/com.termux/files/home "
            "PREFIX=/data/data/com.termux/files/usr "
            "PATH=/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin "
            "LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib "
            f"/data/data/com.termux/files/usr/bin/bash -c {shlex.quote(termux_cmd)}"
        )
        return self._run_adb(env_cmd, timeout=timeout)

    def _get_laptop_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def _check_tcp_port(self, ip: str, port: int, timeout: float = 0.8) -> bool:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except Exception:
            return False

    def get_ssh_status(self) -> Dict[str, Any]:
        """Retorna IP Wi-Fi do celular, status do servidor SSH (porta 8022) e comandos de acesso do laptop."""
        out = self._run_adb(
            "ip -4 addr show wlan0 | grep inet; "
            "echo '===TERMUX==='; "
            "pm list packages com.termux; "
            "stat -c %U /data/data/com.termux /data/data/com.termux/files/home 2>/dev/null || "
            "run-as com.termux /data/data/com.termux/files/usr/bin/id -un 2>/dev/null",
            timeout=4.0,
        )
        m_ip = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
        if m_ip:
            self.cached_phone_ip = m_ip.group(1)
            if hasattr(self.android, "_record_discovered_phone"):
                self.android._record_discovered_phone(self.cached_phone_ip)
            elif hasattr(self.android, "ssh_host"):
                self.android.ssh_host = self.cached_phone_ip
        elif hasattr(self.android, "discover_phone_ip"):
            self.cached_phone_ip = self.android.discover_phone_ip()

        termux_installed = (
            os.path.exists("/data/data/com.termux")
            or "package:com.termux" in out
            or self._check_tcp_port(self.cached_phone_ip, self.ssh_port)
        )
        if "===TERMUX===" in out:
            after = out.split("===TERMUX===", 1)[1].strip().splitlines()
            for line in after:
                if line.strip().startswith("u0_"):
                    self.cached_ssh_user = line.strip()
                    if hasattr(self.android, "ssh_user"):
                        self.android.ssh_user = self.cached_ssh_user
        if self.cached_ssh_user in ("", "termux") and hasattr(self.android, "discover_ssh_user"):
            self.cached_ssh_user = self.android.discover_ssh_user()

        sshd_running = (
            self._check_tcp_port("127.0.0.1", self.ssh_port, timeout=0.4)
            if os.path.exists("/data/data/com.termux")
            else self._check_tcp_port(self.cached_phone_ip, self.ssh_port)
        )
        if not sshd_running and termux_installed:
            # Garante permissões de storage e inicia o sshd no contexto real do app Termux (untrusted_app_27)
            self._run_adb(
                "for p in android.permission.READ_EXTERNAL_STORAGE android.permission.WRITE_EXTERNAL_STORAGE; do "
                "pm grant com.termux $p 2>/dev/null; done; "
                "appops set com.termux MANAGE_EXTERNAL_STORAGE allow 2>/dev/null; "
                "appops set com.termux LEGACY_STORAGE allow 2>/dev/null",
                timeout=3.5,
            )
            self._run_termux(
                "grep -q sshd ~/.bashrc 2>/dev/null || echo 'pgrep -x sshd >/dev/null 2>&1 || sshd' >> ~/.bashrc; "
                "/data/data/com.termux/files/usr/bin/sshd 2>/dev/null || true",
                timeout=3.5,
            )
            sshd_running = (
                self._check_tcp_port("127.0.0.1", self.ssh_port, timeout=0.4)
                if os.path.exists("/data/data/com.termux")
                else self._check_tcp_port(self.cached_phone_ip, self.ssh_port)
            )

        laptop_ip = self._get_laptop_ip()
        display_ip = os.environ.get("HYBRIDBOX_PUBLIC_HOST", "") or self.cached_phone_ip
        display_user = os.environ.get("HYBRIDBOX_PUBLIC_USER", "") or self.cached_ssh_user

        ssh_cmd = f"ssh -p {self.ssh_port} {display_user}@{display_ip}"
        ssh_alias_cmd = "ssh hybridbox"
        scp_cmd = (
            f'scp -P {self.ssh_port} -r "./backend" "./frontend" "./scripts" '
            f"{display_user}@{display_ip}:~/hybridbox-remote-pwa/"
        )

        return {
            "ok": True,
            "phone_ip": display_ip,
            "laptop_ip": laptop_ip,
            "ssh_port": self.ssh_port,
            "ssh_user": display_user,
            "termux_installed": termux_installed,
            "sshd_running": sshd_running,
            "ssh_command": ssh_cmd,
            "ssh_alias": ssh_alias_cmd,
            "scp_command": scp_cmd,
            "android_cwd": self.android_cwd,
            "host_cwd": "~/hybridbox-remote-pwa",
        }

    def _supplement_netlink_if_blocked(self, output: str, cmd_clean: str) -> str:
        """Se o Android 11 bloquear `ip addr` via netlink para o UID do Termux, injeta o IP real via ADB."""
        if "Cannot bind netlink socket" not in output:
            return output
        wlan_info = self._run_adb("ip -4 addr show wlan0 | grep inet", timeout=3.0)
        if not wlan_info:
            wlan_info = f"    inet {self.cached_phone_ip}/24 scope global wlan0"
        cleaned_lines = [
            ln for ln in output.splitlines() if "Cannot bind netlink socket" not in ln
        ]
        cleaned_lines.append(wlan_info)
        return "\n".join(cleaned_lines).strip()

    def execute_command(self, command: str, target: str = "android") -> Dict[str, Any]:
        """
        Executa um comando interativo no Android/Termux (via Wi-Fi SSH ou ADB Shell)
        ou no Laptop Host (PowerShell) e retorna a saída formatada.
        """
        cmd_clean = (command or "").strip()
        if not cmd_clean:
            return {"ok": True, "output": "", "cwd": self.android_cwd if target == "android" else self.host_cwd}

        start_ts = time.time()

        if target == "host":
            # Trata comando `cd` no host Windows
            if cmd_clean.lower() == "cd" or cmd_clean.lower().startswith("cd "):
                new_dir = cmd_clean[2:].strip().strip('"').strip("'")
                if not new_dir:
                    return {"ok": True, "output": self.host_cwd, "cwd": self.host_cwd}
                candidate = (Path(self.host_cwd) / new_dir).resolve()
                if candidate.exists() and candidate.is_dir():
                    self.host_cwd = str(candidate)
                    return {"ok": True, "output": f"Changed directory to: {self.host_cwd}", "cwd": self.host_cwd}
                return {"ok": False, "output": f"Directory not found: {candidate}", "cwd": self.host_cwd}

            try:
                res = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command", cmd_clean],
                    cwd=self.host_cwd,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=25.0,
                )
                out = (res.stdout or "") + (res.stderr or "")
                elapsed = int((time.time() - start_ts) * 1000)
                return {
                    "ok": res.returncode == 0,
                    "output": out.strip() or f"[Command completed in {elapsed}ms — exit code {res.returncode}]",
                    "cwd": self.host_cwd,
                    "elapsed_ms": elapsed,
                }
            except Exception as exc:
                return {"ok": False, "output": f"Error executing on Laptop: {exc}", "cwd": self.host_cwd}

        # Target == "android" / "linux" (Redmi Note 8 Pro — ambiente híbrido Termux + Android System)
        if cmd_clean == "cd" or cmd_clean.startswith("cd "):
            target_dir = cmd_clean[2:].strip() or "/data/data/com.termux/files/home"
            check_cmd = (
                f"cd {self.android_cwd} 2>/dev/null; cd {target_dir} 2>/dev/null && pwd || echo '__INVALID_DIR__'"
            )
            termux_res = self._run_termux(check_cmd, timeout=4.0).splitlines()
            resolved = termux_res[-1].strip() if termux_res else "__INVALID_DIR__"
            if resolved == "__INVALID_DIR__":
                adb_res = self._run_adb(check_cmd, timeout=4.0).splitlines()
                resolved = adb_res[-1].strip() if adb_res else "__INVALID_DIR__"
            if resolved and resolved != "__INVALID_DIR__":
                self.android_cwd = resolved
                return {"ok": True, "output": f"Android Directory: {self.android_cwd}", "cwd": self.android_cwd}
            return {"ok": False, "output": f"Invalid directory on Android: {target_dir}", "cwd": self.android_cwd}

        # Comandos exclusivos do subsistema Binder do Android (input, dumpsys, uiautomator, svc, settings, screencap, wm, cmd, appops)
        # exigem UID 2000 (ADB Shell)
        is_android_sys_cmd = bool(
            re.search(
                r"(?:^|[;&|]\s*)(dumpsys|input|uiautomator|svc|settings|screencap|wm|cmd|appops|logcat)\b",
                cmd_clean,
            )
        )

        # Fast-path quando o servidor já está rodando diretamente dentro do Termux no celular
        if not is_android_sys_cmd and os.path.exists("/data/data/com.termux/files/usr/bin/bash"):
            try:
                local_wrapped = (
                    "export HOME=/data/data/com.termux/files/home; "
                    "export PREFIX=/data/data/com.termux/files/usr; "
                    "export PATH=/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin; "
                    "export LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib; "
                    f"cd {shlex.quote(self.android_cwd)} 2>/dev/null || cd ~; {cmd_clean}"
                )
                res = subprocess.run(
                    ["/data/data/com.termux/files/usr/bin/bash", "-c", local_wrapped],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=20.0,
                )
                out = (res.stdout or "") + (res.stderr or "")
                if "Can't find service:" not in out:
                    fixed_out = self._supplement_netlink_if_blocked(out, cmd_clean)
                    ok = res.returncode == 0 or ("Cannot bind netlink socket" in out and bool(fixed_out))
                    elapsed = int((time.time() - start_ts) * 1000)
                    return {
                        "ok": ok,
                        "transport": "Termux Native Shell",
                        "output": fixed_out.strip() or f"[OK in {elapsed}ms]",
                        "cwd": self.android_cwd,
                        "elapsed_ms": elapsed,
                    }
            except Exception:
                pass

        if not is_android_sys_cmd and not self._check_tcp_port(self.cached_phone_ip, self.ssh_port, timeout=0.4):
            if hasattr(self.android, "discover_phone_ip"):
                self.cached_phone_ip = self.android.discover_phone_ip(force=True)
        if self.cached_ssh_user in ("", "termux") and hasattr(self.android, "discover_ssh_user"):
            self.cached_ssh_user = self.android.discover_ssh_user()

        if not is_android_sys_cmd and self._check_tcp_port(self.cached_phone_ip, self.ssh_port, timeout=0.4):
            try:
                ssh_wrapped = (
                    f"cd {shlex.quote(self.android_cwd)} 2>/dev/null || cd ~; {cmd_clean}"
                )
                res = subprocess.run(
                    [
                        "ssh",
                        "-n",
                        "-p",
                        str(self.ssh_port),
                        "-o",
                        "BatchMode=yes",
                        "-o",
                        "StrictHostKeyChecking=no",
                        "-o",
                        "ConnectTimeout=2",
                        f"{self.cached_ssh_user}@{self.cached_phone_ip}",
                        ssh_wrapped,
                    ],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=20.0,
                )
                if res.returncode != 255:
                    out = (res.stdout or "") + (res.stderr or "")
                    if "Can't find service:" not in out:
                        fixed_out = self._supplement_netlink_if_blocked(out, cmd_clean)
                        ok = res.returncode == 0 or ("Cannot bind netlink socket" in out and bool(fixed_out))
                        elapsed = int((time.time() - start_ts) * 1000)
                        return {
                            "ok": ok,
                            "transport": f"Wi-Fi SSH ({self.cached_phone_ip}:{self.ssh_port})",
                            "output": fixed_out.strip() or f"[OK via Wi-Fi SSH in {elapsed}ms]",
                            "cwd": self.android_cwd,
                            "elapsed_ms": elapsed,
                        }
            except Exception:
                pass

        # Fallback: se for comando do Termux, roda via `run-as com.termux`; se for comando Android/sdcard, roda via ADB Shell
        if not is_android_sys_cmd and not self.android_cwd.startswith("/sdcard"):
            termux_wrapped = (
                f"mkdir -p {shlex.quote(self.android_cwd)} 2>/dev/null; "
                f"cd {shlex.quote(self.android_cwd)} 2>/dev/null || cd ~; "
                f"{cmd_clean}"
            )
            out = self._run_termux(termux_wrapped, timeout=25.0)
            out = self._supplement_netlink_if_blocked(out, cmd_clean)
            if out and "run-as:" not in out and "Can't find service:" not in out:
                elapsed = int((time.time() - start_ts) * 1000)
                return {
                    "ok": True,
                    "transport": "ADB + Termux Runtime",
                    "output": out or f"[Command completed in {elapsed}ms]",
                    "cwd": self.android_cwd,
                    "elapsed_ms": elapsed,
                }

        wrapped_adb = (
            f"cd {shlex.quote(self.android_cwd)} 2>/dev/null || cd /sdcard; "
            f"{cmd_clean}"
        )
        out = self._run_adb(wrapped_adb, timeout=25.0)
        elapsed = int((time.time() - start_ts) * 1000)
        return {
            "ok": True,
            "transport": "ADB Shell (System UID 2000)",
            "output": out or f"[Command completed in {elapsed}ms]",
            "cwd": self.android_cwd,
            "elapsed_ms": elapsed,
        }

    def sync_update_over_wifi(self) -> Dict[str, Any]:
        """
        Sincroniza e atualiza todos os arquivos do HybridBox Remote PWA do Laptop
        para o Redmi Note 8 Pro via Wi-Fi SSH (`scp`) e/ou `adb push`.
        """
        start_ts = time.time()
        logs = []
        status = self.get_ssh_status()
        phone_ip = status["phone_ip"]
        in_termux = os.path.exists("/data/data/com.termux")

        sync_items = (
            "backend",
            "frontend",
            "scripts",
            "tests",
            "requirements.txt",
            "README.md",
            "install.sh",
            "rescue_wifi.json",
        )

        # 1. Se o servidor SSH (porta 8022) estiver ativo no Wi-Fi (e estivermos no PC), sincroniza via SCP sob Wi-Fi
        used_wifi_ssh = False
        if in_termux:
            used_wifi_ssh = True
            logs.append("[Termux Local] Executando diretamente no dispositivo Android; arquivos locais já estão em ~/hybridbox-remote-pwa.")
        elif status["sshd_running"]:
            try:
                subprocess.run(
                    [
                        "ssh",
                        "-n",
                        "-p",
                        str(self.ssh_port),
                        "-o",
                        "BatchMode=yes",
                        "-o",
                        "StrictHostKeyChecking=no",
                        f"{self.cached_ssh_user}@{phone_ip}",
                        "mkdir -p ~/hybridbox-remote-pwa",
                    ],
                    capture_output=True,
                    timeout=5.0,
                )
                for item in sync_items:
                    src_path = self.base_dir / item
                    if not src_path.exists():
                        continue
                    res = subprocess.run(
                        [
                            "scp",
                            "-P",
                            str(self.ssh_port),
                            "-o",
                            "BatchMode=yes",
                            "-o",
                            "StrictHostKeyChecking=no",
                            "-r",
                            str(src_path),
                            f"{self.cached_ssh_user}@{phone_ip}:~/hybridbox-remote-pwa/",
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=30.0,
                    )
                    if res.returncode == 0:
                        used_wifi_ssh = True
                        logs.append(
                            f"[Wi-Fi SSH/SCP {phone_ip}:{self.ssh_port}] '{item}' sincronizado via Wi-Fi para ~/hybridbox-remote-pwa/{item}."
                        )
            except Exception as exc:
                logs.append(f"[Aviso SCP] Fallback para ADB ({exc})")

        # 2. Sincroniza também via ADB caso SCP não tenha sido usado
        if not used_wifi_ssh:
            self._run_adb("mkdir -p /sdcard/hybridbox-remote-pwa", timeout=3.0)
            for item in sync_items:
                src_path = self.base_dir / item
                if not src_path.exists():
                    continue
                res = self.android.run_adb_cmd(
                    ["push", str(src_path), "/sdcard/hybridbox-remote-pwa/"],
                    timeout=30.0,
                )
                if res is not None:
                    summary = (res.stdout or res.stderr or "").strip().splitlines()[-1:]
                    logs.append(f"[ADB Sync '{item}'] {summary[0] if summary else 'OK'}")

            # 3. Copia de /sdcard/hybridbox-remote-pwa para ~/hybridbox-remote-pwa via pipe tar para run-as com.termux
            self._run_adb(
                "run-as com.termux /data/data/com.termux/files/usr/bin/mkdir -p /data/data/com.termux/files/home/hybridbox-remote-pwa 2>/dev/null; "
                "tar -cf - -C /sdcard/hybridbox-remote-pwa . 2>/dev/null | "
                "run-as com.termux /data/data/com.termux/files/usr/bin/tar -xf - -C /data/data/com.termux/files/home/hybridbox-remote-pwa 2>/dev/null",
                timeout=10.0,
            )

        # Limpa __pycache__ de Windows, normaliza LF nos scripts e reinicia keep_awake.sh (+ uvicorn quando invocado do PC)
        uvicorn_restart_snippet = (
            ""
            if in_termux
            else (
                "UV=backend.main; APP=app; "
                "pkill -9 -f '[u]vicorn.*'$UV:$APP 2>/dev/null || true; "
                "cd ~/hybridbox-remote-pwa && "
                "nohup setsid /data/data/com.termux/files/usr/bin/python3 -m uvicorn $UV:$APP --host 0.0.0.0 --port 8080 --log-level warning </dev/null >>~/uvicorn.log 2>&1 & "
            )
        )
        self._run_termux(
            "find ~/hybridbox-remote-pwa -name '__pycache__' -exec rm -rf {} + 2>/dev/null; "
            "sed -i 's/\\r$//' ~/hybridbox-remote-pwa/scripts/*.sh ~/hybridbox-remote-pwa/scripts/hb-shell ~/hybridbox-remote-pwa/scripts/hb-sudo ~/hybridbox-remote-pwa/install.sh 2>/dev/null; "
            "chmod +x ~/hybridbox-remote-pwa/scripts/*.sh ~/hybridbox-remote-pwa/scripts/hb-shell ~/hybridbox-remote-pwa/scripts/hb-sudo ~/hybridbox-remote-pwa/install.sh 2>/dev/null; "
            "cp ~/hybridbox-remote-pwa/scripts/hb-shell /data/data/com.termux/files/usr/bin/hb-shell 2>/dev/null; "
            "cp ~/hybridbox-remote-pwa/scripts/hb-sudo /data/data/com.termux/files/usr/bin/sudo 2>/dev/null; "
            "chmod 755 /data/data/com.termux/files/usr/bin/hb-shell /data/data/com.termux/files/usr/bin/sudo 2>/dev/null; "
            "KA=keep_awake.sh; "
            "pkill -9 -f '[s]cripts/'$KA 2>/dev/null || true; "
            "rm -f /data/data/com.termux/files/usr/tmp/hybridbox_keep_awake.pid; "
            f"({uvicorn_restart_snippet}"
            "nohup setsid /data/data/com.termux/files/usr/bin/bash ~/hybridbox-remote-pwa/scripts/$KA </dev/null >/dev/null 2>&1 &) </dev/null >/dev/null 2>&1",
            timeout=8.0,
        )

        elapsed = int((time.time() - start_ts) * 1000)
        return {
            "ok": True,
            "phone_ip": phone_ip,
            "used_wifi_ssh": used_wifi_ssh,
            "elapsed_ms": elapsed,
            "log": "\n".join(logs) if logs else "All files synchronized!",
            "message": f"✅ Update completed in {elapsed}ms to Redmi Note 8 Pro ({phone_ip})!",
        }

    def open_laptop_ssh_terminal(self) -> Dict[str, Any]:
        """Abre uma janela de Terminal interativa na área de trabalho do Laptop conectada ao Redmi Note 8 Pro."""
        if os.name != "nt":
            return {"ok": False, "message": "Local window opening is only available on Windows hosts."}

        status = self.get_ssh_status()
        phone_ip = status["phone_ip"]
        adb_bin = self.android._find_adb() or "adb"
        serial = self.android.active_serial or f"{phone_ip}:5555"

        if status["sshd_running"]:
            ps_cmd = (
                f'Write-Host "=== CONNECTING OVER WI-FI SSH TO REDMI NOTE 8 PRO ({phone_ip}:{self.ssh_port}) ===" -ForegroundColor Cyan; '
                f"ssh -p {self.ssh_port} -o StrictHostKeyChecking=no {self.cached_ssh_user}@{phone_ip}"
            )
        else:
            ps_cmd = (
                f'Write-Host "=== DIRECT TERMINAL TO REDMI NOTE 8 PRO (Wi-Fi IP: {phone_ip}) ===" -ForegroundColor Green; '
                f'Write-Host "Tip: Type exit to return to Laptop PowerShell." -ForegroundColor Yellow; '
                f'& "{adb_bin}" -s {serial} shell'
            )

        try:
            from ctypes import wintypes

            class STARTUPINFOW(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("lpReserved", wintypes.LPWSTR),
                    ("lpDesktop", wintypes.LPWSTR),
                    ("lpTitle", wintypes.LPWSTR),
                    ("dwX", wintypes.DWORD),
                    ("dwY", wintypes.DWORD),
                    ("dwXSize", wintypes.DWORD),
                    ("dwYSize", wintypes.DWORD),
                    ("dwXCountChars", wintypes.DWORD),
                    ("dwYCountChars", wintypes.DWORD),
                    ("dwFillAttribute", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD),
                    ("wShowWindow", wintypes.WORD),
                    ("cbReserved2", wintypes.WORD),
                    ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
                    ("hStdInput", wintypes.HANDLE),
                    ("hStdOutput", wintypes.HANDLE),
                    ("hStdError", wintypes.HANDLE),
                ]

            class PROCESS_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("hProcess", wintypes.HANDLE),
                    ("hThread", wintypes.HANDLE),
                    ("dwProcessId", wintypes.DWORD),
                    ("dwThreadId", wintypes.DWORD),
                ]

            si = STARTUPINFOW()
            si.cb = ctypes.sizeof(si)
            si.lpDesktop = "WinSta0\\Default"
            si.lpTitle = f"HybridBox SSH Terminal ({phone_ip})"
            si.dwFlags = 1
            si.wShowWindow = 5
            pi = PROCESS_INFORMATION()

            cmd_line = f'powershell.exe -NoExit -Command "{ps_cmd}"'
            # CREATE_NEW_CONSOLE = 0x00000010
            ctypes.windll.kernel32.CreateProcessW(
                None,
                cmd_line,
                None,
                None,
                False,
                0x00000010,
                None,
                str(self.base_dir),
                ctypes.byref(si),
                ctypes.byref(pi),
            )
            return {
                "ok": True,
                "message": f"💻 SSH Terminal window ({phone_ip}) opened on your Laptop screen!",
            }
        except Exception as exc:
            return {"ok": False, "message": f"Error opening terminal on laptop: {exc}"}
