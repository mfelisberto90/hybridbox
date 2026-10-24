"""
Guardião 'Plug & Revive' Automático no PC Windows (scripts/pc_usb_autorevive.py).

Quando o Xiaomi Redmi Note 8 Pro desliga por bateria zerada (0%) e o usuário o conecta
no cabo USB (ou religa no botão Power na rede Wi-Fi), este guardião:
1. Detecta automaticamente o Xiaomi via USB ADB ou Wi-Fi (`hybridbox.local` / LAN);
2. Reativa o ADB Sem Fio (`adb tcpip 5555`) e o daemon `HybridBoxBridge` (`5558`);
3. Instala o APK `Termux:Boot` (`com.termux.boot`) e libera o Autostart da MIUI (`OP_AUTO_START = 10008`);
4. Sincroniza os arquivos mais recentes (`v19`) e sobe `keep_awake.sh` + `uvicorn` (`8080`) em segundos!
"""

import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from backend.android_controller import AndroidController


def tcp_open(host: str, port: int, timeout: float = 0.5) -> bool:
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def normalize_shell_scripts() -> None:
    scripts_dir = BASE_DIR / "scripts"
    lf_targets = list(scripts_dir.glob("*.sh")) + [
        scripts_dir / "hb-shell",
        scripts_dir / "hb-sudo",
        BASE_DIR / "install.sh",
    ]
    for p in lf_targets:
        if not p.exists():
            continue
        try:
            data = p.read_bytes()
            if b"\r\n" in data:
                p.write_bytes(data.replace(b"\r\n", b"\n"))
        except Exception:
            pass

    for bat_p in BASE_DIR.glob("*.bat"):
        try:
            data = bat_p.read_bytes()
            normalized = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            if normalized != data:
                bat_p.write_bytes(normalized)
        except Exception:
            pass


def _ensure_pc_ssh_key_on_phone(adb_bin: str, serial: str) -> None:
    """Garante chave SSH pública do PC injetada no Termux (/data/data/com.termux/files/home/.ssh/authorized_keys) quando ADB está conectado."""
    if not adb_bin or not serial:
        return
    try:
        ssh_dir = pathlib.Path.home() / ".ssh"
        ssh_dir.mkdir(parents=True, exist_ok=True)
        pub_key_path = ssh_dir / "id_ed25519.pub"
        if not pub_key_path.exists():
            rsa_pub = ssh_dir / "id_rsa.pub"
            if rsa_pub.exists():
                pub_key_path = rsa_pub
            elif shutil.which("ssh-keygen"):
                subprocess.run(
                    ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(ssh_dir / "id_ed25519")],
                    capture_output=True,
                    timeout=5.0,
                )
        if pub_key_path.exists():
            pub_key = pub_key_path.read_text(encoding="utf-8", errors="ignore").strip()
            if pub_key:
                termux_ssh_dir = "/data/data/com.termux/files/home/.ssh"
                auth_keys = f"{termux_ssh_dir}/authorized_keys"
                subprocess.run(
                    [
                        adb_bin,
                        "-s",
                        serial,
                        "shell",
                        "run-as com.termux /data/data/com.termux/files/usr/bin/env "
                        "HOME=/data/data/com.termux/files/home "
                        "PREFIX=/data/data/com.termux/files/usr "
                        "PATH=/data/data/com.termux/files/usr/bin:/system/bin "
                        "LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib "
                        "/data/data/com.termux/files/usr/bin/bash -c "
                        f"\"mkdir -p {termux_ssh_dir} && chmod 700 {termux_ssh_dir} && touch {auth_keys} && "
                        f"(grep -qF '{pub_key}' {auth_keys} 2>/dev/null || echo '{pub_key}' >> {auth_keys}) && "
                        f"chmod 600 {auth_keys} && "
                        f"/data/data/com.termux/files/usr/bin/ssh-keygen -A >/dev/null 2>&1 || true; "
                        f"/data/data/com.termux/files/usr/bin/sshd 2>/dev/null || true\"",
                    ],
                    capture_output=True,
                    timeout=6.0,
                )
    except Exception:
        pass


def sync_files_and_restart_phone(
    phone_ip: str, adb_bin: str = "", serial: str = "", ssh_user: str = ""
) -> bool:
    """Sincroniza código atualizado para o Xiaomi via SCP (ou ADB) e reinicia os guardiões sem matar o próprio subshell."""
    normalize_shell_scripts()
    _ensure_pc_ssh_key_on_phone(adb_bin, serial)
    ssh_bin = shutil.which("ssh")
    scp_bin = shutil.which("scp")
    ssh_user = (ssh_user or os.environ.get("HYBRIDBOX_SSH_USER", "") or "termux").strip()

    sync_item_names = (
        "backend",
        "frontend",
        "scripts",
        "tests",
        "requirements.txt",
        "README.md",
        "install.sh",
        "rescue_wifi.json",
    )
    items_to_copy = [
        str(BASE_DIR / item)
        for item in sync_item_names
        if (BASE_DIR / item).exists()
    ]

    restart_cmd = (
        "find ~/hybridbox-remote-pwa -name '__pycache__' -exec rm -rf {} + 2>/dev/null; "
        "sed -i 's/\\r$//' ~/hybridbox-remote-pwa/scripts/*.sh ~/hybridbox-remote-pwa/scripts/hb-shell ~/hybridbox-remote-pwa/scripts/hb-sudo ~/hybridbox-remote-pwa/install.sh 2>/dev/null; "
        "chmod 755 ~/hybridbox-remote-pwa/scripts/*.sh ~/hybridbox-remote-pwa/scripts/hb-shell ~/hybridbox-remote-pwa/scripts/hb-sudo ~/hybridbox-remote-pwa/install.sh 2>/dev/null; "
        "cp ~/hybridbox-remote-pwa/scripts/hb-shell /data/data/com.termux/files/usr/bin/hb-shell 2>/dev/null; "
        "cp ~/hybridbox-remote-pwa/scripts/hb-sudo /data/data/com.termux/files/usr/bin/sudo 2>/dev/null; "
        "chmod 755 /data/data/com.termux/files/usr/bin/hb-shell /data/data/com.termux/files/usr/bin/sudo 2>/dev/null; "
        "KA=keep_awake.sh; UV=backend.main; APP=app; "
        "pkill -9 -f '[s]cripts/'$KA 2>/dev/null || true; "
        "pkill -9 -f '[u]vicorn.*'$UV:$APP 2>/dev/null || true; "
        "rm -f /data/data/com.termux/files/usr/tmp/hybridbox_keep_awake.pid; "
        "(cd ~/hybridbox-remote-pwa && "
        "nohup setsid /data/data/com.termux/files/usr/bin/python3 -m uvicorn $UV:$APP --host 0.0.0.0 --port 8080 --log-level warning </dev/null >>~/uvicorn.log 2>&1 & "
        "nohup setsid /data/data/com.termux/files/usr/bin/bash ~/hybridbox-remote-pwa/scripts/$KA </dev/null >/dev/null 2>&1 &) </dev/null >/dev/null 2>&1"
    )

    synced = False
    if scp_bin and ssh_bin and phone_ip and tcp_open(phone_ip, 8022, 0.8):
        try:
            subprocess.run(
                [
                    ssh_bin,
                    "-n",
                    "-p",
                    "8022",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=4",
                    "-o",
                    "StrictHostKeyChecking=no",
                    f"{ssh_user}@{phone_ip}",
                    "mkdir -p ~/hybridbox-remote-pwa",
                ],
                capture_output=True,
                timeout=5.0,
            )
            if items_to_copy:
                r = subprocess.run(
                    [
                        scp_bin,
                        "-P",
                        "8022",
                        "-o",
                        "BatchMode=yes",
                        "-o",
                        "ConnectTimeout=5",
                        "-o",
                        "StrictHostKeyChecking=no",
                        "-r",
                        *items_to_copy,
                        f"{ssh_user}@{phone_ip}:~/hybridbox-remote-pwa/",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=45.0,
                )
                if r.returncode == 0:
                    synced = True

            subprocess.run(
                [
                    ssh_bin,
                    "-n",
                    "-p",
                    "8022",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=4",
                    "-o",
                    "StrictHostKeyChecking=no",
                    f"{ssh_user}@{phone_ip}",
                    restart_cmd,
                ],
                capture_output=True,
                text=True,
                timeout=12.0,
            )
        except Exception:
            pass

    if not synced and adb_bin and serial:
        subprocess.run(
            [adb_bin, "-s", serial, "shell", "mkdir -p /sdcard/hybridbox-remote-pwa"],
            capture_output=True,
            timeout=5.0,
        )
        for item_p in items_to_copy:
            subprocess.run(
                [adb_bin, "-s", serial, "push", item_p, "/sdcard/hybridbox-remote-pwa/"],
                capture_output=True,
                timeout=30.0,
            )
        subprocess.run(
            [
                adb_bin,
                "-s",
                serial,
                "shell",
                "run-as com.termux /data/data/com.termux/files/usr/bin/mkdir -p /data/data/com.termux/files/home/hybridbox-remote-pwa 2>/dev/null; "
                "tar -cf - -C /sdcard/hybridbox-remote-pwa . 2>/dev/null | "
                "run-as com.termux /data/data/com.termux/files/usr/bin/tar -xf - -C /data/data/com.termux/files/home/hybridbox-remote-pwa 2>/dev/null; "
                "run-as com.termux /data/data/com.termux/files/usr/bin/env "
                "HOME=/data/data/com.termux/files/home "
                "PREFIX=/data/data/com.termux/files/usr "
                "PATH=/data/data/com.termux/files/usr/bin:/system/bin "
                "LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib "
                f"/data/data/com.termux/files/usr/bin/bash -c {subprocess.list2cmdline([restart_cmd])}",
            ],
            capture_output=True,
            timeout=15.0,
        )
        synced = True

    if adb_bin and serial:
        bridge_jar = BASE_DIR / "scripts" / "hybridbox_bridge.jar"
        if bridge_jar.exists():
            subprocess.run(
                [adb_bin, "-s", serial, "push", str(bridge_jar), "/data/local/tmp/hybridbox_bridge.jar"],
                capture_output=True,
                timeout=8.0,
            )
        wd_local = BASE_DIR / "scripts" / "hb_system_watchdog.sh"
        if wd_local.exists():
            subprocess.run(
                [adb_bin, "-s", serial, "push", str(wd_local), "/data/local/tmp/hb_system_watchdog.sh"],
                capture_output=True,
                timeout=8.0,
            )
        subprocess.run(
            [
                adb_bin,
                "-s",
                serial,
                "shell",
                "chmod 755 /data/local/tmp/hb_system_watchdog.sh 2>/dev/null; "
                "nohup /system/bin/sh /data/local/tmp/hb_system_watchdog.sh </dev/null >/dev/null 2>&1 &",
            ],
            capture_output=True,
            timeout=6.0,
        )
    return synced


def run_once(ctrl: AndroidController, force_sync: bool = False) -> bool:
    adb_bin = ctrl._find_adb() or ""
    usb_serials = []
    if adb_bin:
        serials = ctrl._get_active_adb_serials(adb_bin)
        usb_serials = [s for s in serials if ":" not in s and not s.startswith("emulator-")]

    phone_ip = ctrl.discover_phone_ip(force=True)
    ssh_user = ctrl.discover_ssh_user(phone_ip)
    phone_has_8080 = bool(phone_ip and tcp_open(phone_ip, 8080, 0.6))
    phone_has_8022 = bool(phone_ip and tcp_open(phone_ip, 8022, 0.6))
    phone_has_5555 = bool(phone_ip and tcp_open(phone_ip, 5555, 0.6))

    if not usb_serials and not phone_has_8080 and not phone_has_8022 and not phone_has_5555:
        return False

    if usb_serials or not phone_has_8080 or not phone_has_5555 or force_sync:
        print(f"[Plug&Revive] Xiaomi detectado (USB={usb_serials}, IP={phone_ip}, SSH={ssh_user})! Revivendo serviços...")
        res = ctrl.revive_phone_connection()
        active_serial = usb_serials[0] if usb_serials else (f"{phone_ip}:5555" if phone_ip else "")
        sync_files_and_restart_phone(phone_ip, adb_bin=adb_bin, serial=active_serial, ssh_user=ssh_user)
        print(f"[Plug&Revive] Resultado: {res.get('message')}")
        return True

    return True


def install_missing_apks(ctrl: AndroidController) -> None:
    """Instala APKs da pasta apks/ via ADB apenas se ainda não estiverem instalados no aparelho (evitando matar o Termux em execução)."""
    apks_dir = BASE_DIR / "apks"
    if not apks_dir.exists():
        return
    apk_files = sorted(apks_dir.glob("*.apk"))
    if not apk_files:
        print("    - No APK files found in apks/ directory.")
        return

    adb_bin = ctrl._find_adb() or ""
    if not adb_bin:
        print("    - ADB not found; skipping optional APK checks.")
        return

    serials = ctrl._get_active_adb_serials(adb_bin)
    usb_serials = [s for s in serials if ":" not in s and not s.startswith("emulator-")]
    phone_ip = ctrl.discover_phone_ip(force=False)
    active_serial = usb_serials[0] if usb_serials else (f"{phone_ip}:5555" if phone_ip else (serials[0] if serials else ""))
    if not active_serial:
        print("    - No active ADB device detected; skipping optional APK checks.")
        return

    installed_pkgs: set[str] = set()
    try:
        r = subprocess.run(
            [adb_bin, "-s", active_serial, "shell", "pm", "list", "packages"],
            capture_output=True,
            text=True,
            timeout=6.0,
        )
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("package:"):
                installed_pkgs.add(line.split("package:", 1)[1].strip())
    except Exception:
        pass

    known_pkg_map: dict[str, tuple[str, ...]] = {
        "lemuroid": ("com.swordfish.lemuroid",),
        "projectivylauncher": ("com.spocky.projengmenu",),
        "smarttube": ("org.smarttube.stable", "com.liskovsoft.smarttubetv.beta", "com.liskovsoft.smarttubetv"),
        "termux-arm64": ("com.termux",),
        "termux-boot": ("com.termux.boot",),
        "termux-x11": ("com.termux.x11",),
    }

    for apk_path in apk_files:
        name_lower = apk_path.stem.lower()
        matched_candidates: tuple[str, ...] = ()
        for prefix, pkgs in known_pkg_map.items():
            if name_lower.startswith(prefix):
                matched_candidates = pkgs
                break
        already_pkg = next((p for p in matched_candidates if p in installed_pkgs), "")
        if already_pkg:
            print(f"    - [OK] {apk_path.name} ({already_pkg}) already installed.")
            continue
        print(f"    - Installing APK: {apk_path.name} ...")
        try:
            res = subprocess.run(
                [adb_bin, "-s", active_serial, "install", "-r", str(apk_path)],
                capture_output=True,
                text=True,
                timeout=60.0,
            )
            if res.returncode == 0 and matched_candidates:
                installed_pkgs.update(matched_candidates)
        except Exception:
            pass


def main() -> None:
    if "--print-target" in sys.argv:
        ctrl = AndroidController(adb_serial="127.0.0.1:5555")
        ip = ctrl.discover_phone_ip(force=True) or "hybridbox.local"
        user = ctrl.discover_ssh_user(ip) or "termux"
        print(f"{ip}|{user}")
        return
    normalize_shell_scripts()
    ctrl = AndroidController(adb_serial="127.0.0.1:5555")
    if "--install-apks" in sys.argv:
        install_missing_apks(ctrl)
        return
    if "--once" in sys.argv:
        ok = run_once(ctrl, force_sync=True)
        print("ONLINE" if ok else "OFFLINE")
        return

    print("[Plug&Revive] Guardião USB & Wi-Fi iniciado em segundo plano...")
    was_online = False
    while True:
        try:
            adb_bin = ctrl._find_adb() or ""
            usb_serials = []
            if adb_bin:
                serials = ctrl._get_active_adb_serials(adb_bin)
                usb_serials = [s for s in serials if ":" not in s and not s.startswith("emulator-")]

            phone_ip = ctrl.discover_phone_ip()
            is_online_now = bool(
                usb_serials
                or (phone_ip and (tcp_open(phone_ip, 8080, 0.5) or tcp_open(phone_ip, 8022, 0.5) or tcp_open(phone_ip, 5555, 0.5)))
            )

            if is_online_now and not was_online:
                run_once(ctrl, force_sync=True)
                was_online = True
            elif is_online_now:
                run_once(ctrl, force_sync=False)
            else:
                was_online = False
        except Exception:
            pass
        time.sleep(5.0)


if __name__ == "__main__":
    main()
