"""
Controlador Persistente de Input Android TV via ADB Loopback (127.0.0.1:5555) ou Root (su).
Mantém um subprocesso shell aberto com stdin persistente para disparar `input keyevent`,
`input tap`, `input swipe`, `input text` e `am start` sem criar um processo por pacote.
"""

import concurrent.futures
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RUNTIME_CACHE_FILE = Path(__file__).resolve().parent.parent / ".hybridbox_runtime.json"
PHONE_WIFI_MAC = os.environ.get("HYBRIDBOX_PHONE_MAC", "").strip().lower().replace(":", "-")
PHONE_MAC_SUFFIX = "-".join(PHONE_WIFI_MAC.split("-")[-3:]) if PHONE_WIFI_MAC.count("-") >= 2 else ""


KEY_MAP: Dict[str, str] = {
    # D-Pad & Navegação
    "UP": "KEYCODE_DPAD_UP",
    "DOWN": "KEYCODE_DPAD_DOWN",
    "LEFT": "KEYCODE_DPAD_LEFT",
    "RIGHT": "KEYCODE_DPAD_RIGHT",
    "OK": "KEYCODE_DPAD_CENTER",
    "CENTER": "KEYCODE_DPAD_CENTER",
    "ENTER": "KEYCODE_ENTER",
    "BACK": "KEYCODE_BACK",
    "HOME": "KEYCODE_HOME",
    "MENU": "KEYCODE_MENU",
    "RECENTS": "KEYCODE_APP_SWITCH",
    # Mídia & Volume
    "VOL_UP": "KEYCODE_VOLUME_UP",
    "VOL_DOWN": "KEYCODE_VOLUME_DOWN",
    "MUTE": "KEYCODE_VOLUME_MUTE",
    "PLAY_PAUSE": "KEYCODE_MEDIA_PLAY_PAUSE",
    "PREV": "KEYCODE_MEDIA_PREVIOUS",
    "NEXT": "KEYCODE_MEDIA_NEXT",
    "STOP": "KEYCODE_MEDIA_STOP",
    "REWIND": "KEYCODE_MEDIA_REWIND",
    "FAST_FORWARD": "KEYCODE_MEDIA_FAST_FORWARD",
    # Teclas de Teclado Comuns & Macros
    "Backspace": "KEYCODE_DEL",
    "BackSpace": "KEYCODE_DEL",
    "Delete": "KEYCODE_FORWARD_DEL",
    "Return": "KEYCODE_ENTER",
    "Escape": "KEYCODE_ESCAPE",
    "Tab": "KEYCODE_TAB",
    "Space": "KEYCODE_SPACE",
    " ": "KEYCODE_SPACE",
    "ArrowUp": "KEYCODE_DPAD_UP",
    "ArrowDown": "KEYCODE_DPAD_DOWN",
    "ArrowLeft": "KEYCODE_DPAD_LEFT",
    "ArrowRight": "KEYCODE_DPAD_RIGHT",
    "POWER": "KEYCODE_POWER",
    "Super_L": "KEYCODE_HOME",
    "SUPER_L": "KEYCODE_HOME",
    "Alt+Tab": "KEYCODE_APP_SWITCH",
    "ALT+TAB": "KEYCODE_APP_SWITCH",
    "Alt+F4": "KEYCODE_BACK",
    "ALT+F4": "KEYCODE_BACK",
    "ctrl+c": "KEYCODE_COPY",
    "CTRL+C": "KEYCODE_COPY",
    "ctrl+v": "KEYCODE_PASTE",
    "CTRL+V": "KEYCODE_PASTE",
    # Botões de Gamepad (SNES / MAME / Lemuroid / RetroArch / Mega Drive 6-Btn)
    "BTN_A": "KEYCODE_BUTTON_A",
    "BTN_B": "KEYCODE_BUTTON_B",
    "BTN_C": "KEYCODE_BUTTON_C",
    "BTN_X": "KEYCODE_BUTTON_X",
    "BTN_Y": "KEYCODE_BUTTON_Y",
    "BTN_Z": "KEYCODE_BUTTON_Z",
    "BTN_L": "KEYCODE_BUTTON_L1",
    "BTN_R": "KEYCODE_BUTTON_R1",
    "BTN_L1": "KEYCODE_BUTTON_L1",
    "BTN_R1": "KEYCODE_BUTTON_R1",
    "BTN_L2": "KEYCODE_BUTTON_L2",
    "BTN_R2": "KEYCODE_BUTTON_R2",
    "BTN_START": "KEYCODE_BUTTON_START",
    "BTN_SELECT": "KEYCODE_BUTTON_SELECT",
    "BTN_COIN": "KEYCODE_BUTTON_SELECT",
    "BTN_MODE": "KEYCODE_BUTTON_MODE",
    "BTN_THUMBL": "KEYCODE_BUTTON_THUMBL",
    "BTN_THUMBR": "KEYCODE_BUTTON_THUMBR",
}

# Coordenadas calibradas dos controles virtuais on-screen (2340x1080 landscape no Redmi Note 8 Pro)
# para Snes9x EX+, NEO.emu e MD.emu (garantem resposta de 60fps com hold de ~80ms por toque).
GAMEPAD_TOUCH_COORDS: Dict[str, Dict[str, Tuple[int, int]]] = {
    "snes": {
        "UP": (330, 560),
        "DOWN": (330, 830),
        "LEFT": (195, 695),
        "RIGHT": (465, 695),
        "OK": (1992, 845),
        "BTN_START": (2175, 132),
        "BTN_SELECT": (162, 162),
        "BTN_COIN": (162, 162),
        "BTN_B": (1992, 845),
        "BTN_A": (2175, 678),
        "BTN_C": (2175, 678),
        "BTN_Y": (1808, 678),
        "BTN_X": (1992, 510),
        "BTN_Z": (1992, 510),
        "BTN_L": (162, 336),
        "BTN_R": (2175, 305),
        "BTN_L1": (162, 336),
        "BTN_R1": (2175, 305),
        "BTN_L2": (162, 336),
        "BTN_R2": (2175, 305),
    },
    "mame": {
        "UP": (330, 560),
        "DOWN": (330, 830),
        "LEFT": (195, 695),
        "RIGHT": (465, 695),
        "OK": (1992, 845),
        "BTN_START": (2175, 336),
        "BTN_SELECT": (162, 368),
        "BTN_COIN": (162, 368),
        "BTN_A": (1992, 845),   # NeoGeo A (Bottom)
        "BTN_B": (2175, 678),   # NeoGeo B (Right)
        "BTN_C": (1808, 678),   # NeoGeo C (Left)
        "BTN_X": (1808, 678),   # NeoGeo C (Left)
        "BTN_Y": (1992, 510),   # NeoGeo D (Top)
        "BTN_Z": (1992, 510),   # NeoGeo D (Top)
        "BTN_L": (162, 368),    # Coin / Select
        "BTN_R": (2175, 336),   # Start
        "BTN_L1": (162, 368),
        "BTN_R1": (2175, 336),
        "BTN_L2": (162, 368),
        "BTN_R2": (2175, 336),
    },
    "megadrive": {
        "UP": (330, 560),
        "DOWN": (330, 830),
        "LEFT": (195, 695),
        "RIGHT": (465, 695),
        "OK": (1992, 695),
        "BTN_START": (2175, 368),
        "BTN_SELECT": (2175, 162),
        "BTN_COIN": (2175, 162),
        "BTN_A": (1808, 695),   # Mega Drive A (Left)
        "BTN_B": (1992, 695),   # Mega Drive B (Middle)
        "BTN_C": (2175, 695),   # Mega Drive C (Right)
        "BTN_X": (1808, 695),   # Mega Drive X / A (Left)
        "BTN_Y": (1992, 695),   # Mega Drive Y / B (Middle)
        "BTN_Z": (2175, 695),   # Mega Drive Z / C (Right)
        "BTN_L": (1808, 695),
        "BTN_R": (2175, 695),
        "BTN_L1": (1808, 695),
        "BTN_R1": (2175, 695),
        "BTN_L2": (1808, 695),
        "BTN_R2": (2175, 695),
    },
}


class AndroidController:
    """Gerencia um pipe shell Android persistente (ADB local 127.0.0.1:5555 ou su)."""

    def __init__(self, adb_serial: str = "127.0.0.1:5555") -> None:
        self.adb_serial = os.environ.get("HYBRIDBOX_ADB_SERIAL", adb_serial)
        self.active_serial: str = self.adb_serial
        cache = self._load_runtime_cache()
        self.ssh_host: str = (
            os.environ.get("HYBRIDBOX_PHONE_IP", "").strip()
            or os.environ.get("HYBRIDBOX_SSH_HOST", "").strip()
            or str(cache.get("phone_ip", "")).strip()
            or self._read_ssh_config_host()
            or "hybridbox.local"
        )
        self.ssh_port: int = int(os.environ.get("HYBRIDBOX_SSH_PORT", "8022"))
        self.ssh_user: str = (
            os.environ.get("HYBRIDBOX_SSH_USER", "").strip()
            or str(cache.get("ssh_user", "")).strip()
            or self._read_ssh_config_user()
            or "termux"
        )
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self._backend_type = "none"
        self.active_emulator: str = "snes"
        self.in_emulator_menu: bool = False
        # Resolução nativa do Redmi Note 8 Pro (1080x2340 em retrato ou 2340x1080 em paisagem)
        self.screen_w: int = 1080
        self.screen_h: int = 2340
        self.cursor_x: int = 540
        self.cursor_y: int = 1170
        self._last_bounds_ts: float = 0.0
        self._last_adb_check_ts: float = 0.0
        self._last_ip_check_ts: float = 0.0
        self._last_battery_ts: float = 0.0
        self._cached_battery: Dict[str, Any] = {}
        self._bounds_syncing: bool = False
        if self.ssh_host == "hybridbox.local" or not (
            self._tcp_open(self.ssh_host, self.ssh_port, 0.25)
            or self._tcp_open(self.ssh_host, 5555, 0.25)
        ):
            self.discover_phone_ip(force=True)
        elif self.ssh_user in ("", "termux"):
            self.discover_ssh_user()
        self._connect()
        self.sync_screen_bounds(force=True)
        if os.name == "nt":
            threading.Thread(
                target=self._keepalive_watchdog_loop, daemon=True
            ).start()

    @staticmethod
    def _load_runtime_cache() -> Dict[str, Any]:
        try:
            if RUNTIME_CACHE_FILE.exists():
                data = json.loads(RUNTIME_CACHE_FILE.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    @classmethod
    def _save_runtime_cache(cls, **updates: Any) -> None:
        try:
            data = cls._load_runtime_cache()
            changed = False
            for k, v in updates.items():
                if v and data.get(k) != v:
                    data[k] = v
                    changed = True
            if changed:
                data["updated_at"] = round(time.time(), 1)
                RUNTIME_CACHE_FILE.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                )
        except Exception:
            pass

    @staticmethod
    def _read_ssh_config_host() -> str:
        try:
            ssh_cfg = Path.home() / ".ssh" / "config"
            if ssh_cfg.exists():
                content = ssh_cfg.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"Host\s+hybridbox\b[\s\S]*?HostName\s+(\S+)", content, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _read_ssh_config_user() -> str:
        try:
            ssh_cfg = Path.home() / ".ssh" / "config"
            if ssh_cfg.exists():
                content = ssh_cfg.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"Host\s+hybridbox\b[\s\S]*?User\s+(\S+)", content, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _is_ipv4(val: str) -> bool:
        parts = (val or "").strip().split(".")
        return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

    @staticmethod
    def _tcp_open(ip: str, port: int, timeout: float = 0.35) -> bool:
        if not ip:
            return False
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except Exception:
            return False

    def _update_ssh_config_host(self, new_ip: str, ssh_user: str = "") -> None:
        """Atualiza ou cria o atalho `Host hybridbox` no ~/.ssh/config quando o IP ou usuário Termux é descoberto."""
        if not new_ip or not self._is_ipv4(new_ip) or os.path.exists("/data/data/com.termux"):
            return
        user_val = (ssh_user or self.ssh_user or "termux").strip()
        try:
            ssh_dir = Path.home() / ".ssh"
            ssh_dir.mkdir(parents=True, exist_ok=True)
            ssh_cfg = ssh_dir / "config"
            content = ssh_cfg.read_text(encoding="utf-8", errors="ignore") if ssh_cfg.exists() else ""
            if re.search(r"(?im)^Host\s+hybridbox\b", content):
                updated = re.sub(
                    r"(Host\s+hybridbox\b[\s\S]*?HostName\s+)(\S+)",
                    rf"\g<1>{new_ip}",
                    content,
                    count=1,
                )
                if user_val and user_val != "termux":
                    updated = re.sub(
                        r"(Host\s+hybridbox\b[\s\S]*?User\s+)(\S+)",
                        rf"\g<1>{user_val}",
                        updated,
                        count=1,
                    )
                if updated != content:
                    ssh_cfg.write_text(updated, encoding="utf-8")
            else:
                block = (
                    f"\nHost hybridbox\n"
                    f"    HostName {new_ip}\n"
                    f"    Port {self.ssh_port}\n"
                    f"    User {user_val}\n"
                    f"    StrictHostKeyChecking no\n"
                )
                ssh_cfg.write_text((content.rstrip() + "\n" + block).lstrip(), encoding="utf-8")
        except Exception:
            pass

    def discover_ssh_user(self, force_or_host: Any = False, force: bool = False) -> str:
        """
        Descobre automaticamente o usuário real do Termux (`u0_a...`) via SSH (porta 8022) ou ADB,
        salvando no cache local `.hybridbox_runtime.json` e no `~/.ssh/config`.
        """
        target_host = self.ssh_host
        if isinstance(force_or_host, str) and force_or_host.strip():
            target_host = force_or_host.strip()
        elif isinstance(force_or_host, bool):
            force = force or force_or_host

        env_user = os.environ.get("HYBRIDBOX_SSH_USER", "").strip()
        if env_user:
            self.ssh_user = env_user
            return self.ssh_user

        if os.path.exists("/data/data/com.termux"):
            try:
                out = subprocess.check_output(
                    ["/data/data/com.termux/files/usr/bin/id", "-un"],
                    text=True,
                    timeout=1.5,
                ).strip()
                if out:
                    self.ssh_user = out
                    self._save_runtime_cache(ssh_user=out)
                    return self.ssh_user
            except Exception:
                pass

        if not force and self.ssh_user and self.ssh_user != "termux":
            return self.ssh_user

        ssh_bin = shutil.which("ssh")
        if ssh_bin and target_host and self._tcp_open(target_host, self.ssh_port, 0.35):
            try:
                res = subprocess.run(
                    [
                        ssh_bin,
                        "-n",
                        "-p",
                        str(self.ssh_port),
                        "-o",
                        "BatchMode=yes",
                        "-o",
                        "ConnectTimeout=2",
                        "-o",
                        "StrictHostKeyChecking=no",
                        f"termux@{target_host}",
                        "id -un",
                    ],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=3.0,
                )
                cand = (res.stdout or "").strip().splitlines()
                if cand and re.match(r"^[a-zA-Z0-9_.\-]+$", cand[-1].strip()):
                    self.ssh_user = cand[-1].strip()
                    self._save_runtime_cache(ssh_user=self.ssh_user)
                    self._update_ssh_config_host(target_host, self.ssh_user)
                    return self.ssh_user
            except Exception:
                pass

        adb_bin = self._find_adb()
        if adb_bin:
            try:
                serials = self._get_active_adb_serials(adb_bin)
                if serials:
                    res = subprocess.run(
                        [
                            adb_bin,
                            "-s",
                            serials[0],
                            "shell",
                            "stat -c %U /data/data/com.termux /data/data/com.termux/files/home 2>/dev/null || "
                            "run-as com.termux /data/data/com.termux/files/usr/bin/id -un 2>/dev/null",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=2.5,
                    )
                    for line in (res.stdout or "").splitlines():
                        clean_u = line.strip()
                        if clean_u.startswith("u0_"):
                            self.ssh_user = clean_u
                            self._save_runtime_cache(ssh_user=self.ssh_user)
                            self._update_ssh_config_host(target_host, self.ssh_user)
                            return self.ssh_user
            except Exception:
                pass

        return self.ssh_user or "termux"

    def _record_discovered_phone(self, found_ip: str) -> str:
        if found_ip and not found_ip.startswith("127."):
            self.ssh_host = found_ip
            self._last_ip_check_ts = time.time()
            if self.ssh_user in ("", "termux"):
                self.discover_ssh_user()
            self._save_runtime_cache(phone_ip=found_ip, ssh_user=self.ssh_user)
            self._update_ssh_config_host(found_ip, self.ssh_user)
        return self.ssh_host

    def _get_local_host_ips(self) -> set[str]:
        ips: set[str] = {"127.0.0.1"}
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ips.add(s.getsockname()[0])
        except Exception:
            pass
        try:
            _, _, host_ips = socket.gethostbyname_ex(socket.gethostname())
            for hip in host_ips:
                if hip:
                    ips.add(hip)
        except Exception:
            pass
        return ips

    def _get_local_subnet_prefix(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                parts = ip.split(".")
                if len(parts) == 4:
                    return f"{parts[0]}.{parts[1]}.{parts[2]}."
        except Exception:
            pass
        parts = (self.ssh_host or "").split(".")
        if len(parts) == 4 and all(p.isdigit() for p in parts):
            return f"{parts[0]}.{parts[1]}.{parts[2]}."
        for preferred_first in (("192", "10"), ("172",)):
            for hip in sorted(self._get_local_host_ips()):
                hparts = hip.split(".")
                if len(hparts) == 4 and hparts[0] in preferred_first:
                    return f"{hparts[0]}.{hparts[1]}.{hparts[2]}."
        return "192.168.0."

    def _scan_local_subnet_for_phone(
        self,
        prefixes: Optional[List[str]] = None,
        exclude_ips: Optional[set[str]] = None,
    ) -> str:
        """Varredura paralela ultra-rápida (<1s) na sub-rede /24 pelas portas 8022 (Termux SSH) ou 5555 (ADB TCP)."""
        local_host_ips = self._get_local_host_ips()
        if exclude_ips:
            local_host_ips = local_host_ips | set(exclude_ips)
        prefixes_to_scan = prefixes or [self._get_local_subnet_prefix()]
        scan_ips = [
            f"{pref}{i}"
            for pref in prefixes_to_scan
            for i in range(2, 255)
            if f"{pref}{i}" not in local_host_ips
        ]

        def _probe_phone(cand_ip: str) -> Optional[str]:
            if self._tcp_open(cand_ip, self.ssh_port, 0.14) or self._tcp_open(cand_ip, 5555, 0.14):
                return cand_ip
            return None

        try:
            ex = concurrent.futures.ThreadPoolExecutor(max_workers=96)
            try:
                futures = [ex.submit(_probe_phone, ip) for ip in scan_ips]
                for fut in concurrent.futures.as_completed(futures, timeout=1.8):
                    hit = fut.result()
                    if hit:
                        ex.shutdown(wait=False, cancel_futures=True)
                        return hit
            finally:
                ex.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        return ""

    @classmethod
    def _resolve_mdns_hostname(cls, hostname: str = "hybridbox.local", timeout: float = 0.65) -> str:
        """
        Resolve `hybridbox.local` via resolvedor nativo do SO e, como fallback,
        envia consulta direta mDNS A-record via UDP multicast `224.0.0.251:5353`.
        """
        clean_host = (hostname or "hybridbox.local").strip().strip(".")
        try:
            ip = socket.gethostbyname(clean_host)
            if ip and not ip.startswith("127."):
                if (
                    cls._tcp_open(ip, 8022, 0.35)
                    or cls._tcp_open(ip, 5555, 0.35)
                    or cls._tcp_open(ip, 8080, 0.35)
                ):
                    return ip
        except Exception:
            pass

        # Fallback: consulta UDP mDNS direta em 224.0.0.251:5353
        try:
            import struct

            labels = [lbl.encode("utf-8")[:63] for lbl in clean_host.split(".") if lbl]
            qname = b"".join(struct.pack("B", len(l)) + l for l in labels) + b"\x00"
            query_pkt = struct.pack(">HHHHHH", 0x1337, 0x0000, 1, 0, 0, 0) + qname + struct.pack(">HH", 1, 1)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
                s.settimeout(timeout)
                s.sendto(query_pkt, ("224.0.0.251", 5353))
                deadline = time.time() + timeout
                while time.time() < deadline:
                    data, addr = s.recvfrom(2048)
                    if len(data) >= 16 and (data[2] & 0x80):
                        cand_ip = socket.inet_ntoa(data[-4:])
                        if not cand_ip.startswith("127.") and (
                            cls._tcp_open(cand_ip, 8022, 0.3)
                            or cls._tcp_open(cand_ip, 5555, 0.3)
                            or cls._tcp_open(cand_ip, 8080, 0.3)
                        ):
                            return cand_ip
                        if addr and addr[0] and not addr[0].startswith("127."):
                            if (
                                cls._tcp_open(addr[0], 8022, 0.3)
                                or cls._tcp_open(addr[0], 5555, 0.3)
                                or cls._tcp_open(addr[0], 8080, 0.3)
                            ):
                                return addr[0]
        except Exception:
            pass
        return ""

    def discover_phone_ip(self, force: bool = False) -> str:
        """
        Descobre automaticamente o IP Wi-Fi atual do Redmi Note 8 Pro na LAN ou Hotspot:
        0. Se `HYBRIDBOX_PHONE_IP` estiver definido no ambiente, prioriza-o imediatamente;
        0.5. Se rodando dentro do próprio celular (Termux), lê o IP da interface `wlan0` diretamente;
        1. Testa o IP em cache (`self.ssh_host` / `.hybridbox_runtime.json` / `~/.ssh/config`) nas portas 8022 ou 5555;
        2. Se ADB (USB ou TCP) estiver ativo, consulta `ip -4 addr show wlan0` ou serial `<ip>:5555`;
        3. Resolve via mDNS / ZeroConf (`hybridbox.local`);
        4. Inspeciona a tabela ARP (`arp -a`) e faz varredura paralela rápida (`<1s`) na sub-rede `/24`.
        """
        env_ip = os.environ.get("HYBRIDBOX_PHONE_IP", "").strip()
        if env_ip:
            self.ssh_host = env_ip
            self._last_ip_check_ts = time.time()
            return self.ssh_host

        if os.path.exists("/data/data/com.termux"):
            try:
                import fcntl
                import struct

                for iface in ("wlan0", "wlan1", "ap0", "swlan0", "rndis0"):
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                            ifreq = struct.pack("256s", iface.encode("utf-8")[:15])
                            res = fcntl.ioctl(s.fileno(), 0x8915, ifreq)
                            ip = socket.inet_ntoa(res[20:24])
                            if ip and not ip.startswith("127."):
                                return self._record_discovered_phone(ip)
                    except Exception:
                        continue
            except Exception:
                pass
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    ip = s.getsockname()[0]
                    if ip and not ip.startswith("127."):
                        return self._record_discovered_phone(ip)
            except Exception:
                pass

        now = time.time()
        last_ts = getattr(self, "_last_ip_check_ts", 0.0)
        cooldown = 20.0 if self._is_ipv4(self.ssh_host) else 8.0
        if not force and last_ts > 0 and (now - last_ts < cooldown):
            return self.ssh_host
        self._last_ip_check_ts = now

        if (
            not force
            and self._is_ipv4(self.ssh_host)
            and (
                self._tcp_open(self.ssh_host, self.ssh_port, 0.35)
                or self._tcp_open(self.ssh_host, 5555, 0.35)
            )
        ):
            return self.ssh_host

        # 0.5. Testa candidatos em cache (.hybridbox_runtime.json / ~/.ssh/config / self.ssh_host)
        cache = self._load_runtime_cache()
        for cand in (
            os.environ.get("HYBRIDBOX_SSH_HOST", "").strip(),
            self.ssh_host if self._is_ipv4(self.ssh_host) else "",
            str(cache.get("phone_ip", "")).strip(),
            self._read_ssh_config_host(),
        ):
            if self._is_ipv4(cand) and (
                self._tcp_open(cand, self.ssh_port, 0.3) or self._tcp_open(cand, 5555, 0.3)
            ):
                return self._record_discovered_phone(cand)

        # 1. Tenta via ADB (USB ou TCP já conectado)
        adb_bin = self._find_adb()
        if adb_bin:
            try:
                serials = self._get_active_adb_serials(adb_bin)
                usb_serials = [s for s in serials if ":" not in s and not s.startswith("emulator-")]
                if usb_serials:
                    res = subprocess.run(
                        [adb_bin, "-s", usb_serials[0], "shell", "ip -4 addr show wlan0"],
                        capture_output=True,
                        text=True,
                        timeout=2.0,
                    )
                    m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", res.stdout or "")
                    if m:
                        return self._record_discovered_phone(m.group(1))
                for s in serials:
                    if ":" in s:
                        tcp_ip = s.split(":", 1)[0]
                        if self._is_ipv4(tcp_ip) and not tcp_ip.startswith("127."):
                            if self._tcp_open(tcp_ip, self.ssh_port, 0.3) or self._tcp_open(tcp_ip, 5555, 0.3):
                                return self._record_discovered_phone(tcp_ip)
            except Exception:
                pass

        # 1.5. Tenta resolver via mDNS / ZeroConf (`hybridbox.local`) em qualquer sub-rede Wi-Fi / Hotspot
        mdns_ip = self._resolve_mdns_hostname("hybridbox.local")
        if mdns_ip:
            return self._record_discovered_phone(mdns_ip)

        # 2. Procura na tabela ARP e interfaces locais do host (priorizando LAN/Wi-Fi 192.168.x e 10.x sobre 172.x virtual)
        local_host_ips = self._get_local_host_ips()
        arp_candidates: List[str] = []
        extra_prefixes: List[str] = []
        for preferred_first in (("192", "10"), ("172",)):
            for hip in sorted(local_host_ips):
                parts = hip.split(".")
                if len(parts) == 4 and parts[0] in preferred_first:
                    pref = f"{parts[0]}.{parts[1]}.{parts[2]}."
                    if pref not in extra_prefixes:
                        extra_prefixes.append(pref)
        try:
            arp_out = subprocess.check_output(
                ["arp", "-a"], text=True, timeout=1.5, errors="ignore"
            )
            for line in arp_out.splitlines():
                line_low = line.lower().replace(":", "-")
                m_ip = re.search(r"(\d+\.\d+\.\d+\.\d+)", line_low)
                if not m_ip:
                    continue
                ip_cand = m_ip.group(1)
                if ip_cand in local_host_ips:
                    continue
                if (PHONE_WIFI_MAC and PHONE_WIFI_MAC in line_low) or (
                    PHONE_MAC_SUFFIX and PHONE_MAC_SUFFIX in line_low
                ):
                    if self._tcp_open(ip_cand, self.ssh_port, 0.35) or self._tcp_open(ip_cand, 5555, 0.35):
                        return self._record_discovered_phone(ip_cand)
                if "dynamic" in line_low and not ip_cand.endswith((".1", ".255")):
                    if ip_cand not in arp_candidates:
                        arp_candidates.append(ip_cand)
                    parts = ip_cand.split(".")
                    if len(parts) == 4 and parts[0] in ("192", "10", "172"):
                        pref = f"{parts[0]}.{parts[1]}.{parts[2]}."
                        if pref not in extra_prefixes:
                            extra_prefixes.append(pref)
        except Exception:
            pass

        for hs_pref in ("192.168.43.", "192.168.137.", "172.20.10.", "192.168.42."):
            if hs_pref not in extra_prefixes:
                extra_prefixes.append(hs_pref)

        # 3. Testa portas 8022/5555 nos candidatos ARP
        if arp_candidates:
            for ip_cand in arp_candidates:
                if self._tcp_open(ip_cand, self.ssh_port, 0.2):
                    return self._record_discovered_phone(ip_cand)
            for ip_cand in arp_candidates:
                if self._tcp_open(ip_cand, 5555, 0.2):
                    return self._record_discovered_phone(ip_cand)

        # 4. Varredura paralela ultra-rápida nas sub-redes locais ativas (portas 8022/5555)
        primary_prefix = self._get_local_subnet_prefix()
        prefixes_to_scan = [primary_prefix]
        max_prefixes = 4 if force else 2
        for p in extra_prefixes:
            if p not in prefixes_to_scan and len(prefixes_to_scan) < max_prefixes:
                prefixes_to_scan.append(p)
        hit = self._scan_local_subnet_for_phone(
            prefixes=prefixes_to_scan, exclude_ips=set(arp_candidates)
        )
        if hit:
            return self._record_discovered_phone(hit)

        self._last_ip_check_ts = time.time()
        return self.ssh_host

    def _keepalive_watchdog_loop(self) -> None:
        """
        Thread guardiã no Windows que mantém o ADB Wi-Fi (5555), o SSH (8022) e o servidor
        FastAPI do celular (8080) sempre acordados e reconectados automaticamente.
        """
        while True:
            try:
                time.sleep(20.0)
                phone_ip = self.discover_phone_ip()
                adb_bin = self._find_adb()
                if adb_bin and phone_ip:
                    raw_devs = ""
                    try:
                        res_d = subprocess.run(
                            [adb_bin, "devices"],
                            capture_output=True,
                            text=True,
                            timeout=2.0,
                        )
                        raw_devs = res_d.stdout or ""
                    except Exception:
                        pass
                    serials = [
                        line.split()[0]
                        for line in raw_devs.splitlines()[1:]
                        if "\tdevice" in line
                    ]
                    usb_serials = [s for s in serials if ":" not in s and not s.startswith("emulator-")]
                    wifi_serial = f"{phone_ip}:5555"
                    # Se o alvo TCP estiver preso como 'offline' no adb devices, desconecta antes de reconectar
                    if f"{wifi_serial}\toffline" in raw_devs:
                        subprocess.run(
                            [adb_bin, "disconnect", wifi_serial],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=2.0,
                        )
                    if wifi_serial not in serials:
                        if usb_serials and not self._tcp_open(phone_ip, 5555, 0.35):
                            subprocess.run(
                                [adb_bin, "-s", usb_serials[0], "tcpip", "5555"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                timeout=3.0,
                            )
                            time.sleep(1.0)
                        subprocess.run(
                            [adb_bin, "connect", wifi_serial],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=2.0,
                        )
                # Reconecta pipe shell persistente se necessário
                if not self.is_connected() or self._backend_type == "simulated":
                    with self._lock:
                        if not self.is_connected() or self._backend_type == "simulated":
                            self._connect()
                # Se a porta 8080 no celular caiu, aciona o keep_awake.sh e o watchdog de sistema remotamente
                if usb_serials or (phone_ip and not self._tcp_open(phone_ip, 8080, timeout=0.8)):
                    self.ensure_termux_boot_and_autostart()
                    self.run_adb_shell(
                        "if [ -f /data/local/tmp/hb_system_watchdog.sh ]; then "
                        "chmod 755 /data/local/tmp/hb_system_watchdog.sh 2>/dev/null; "
                        "nohup /system/bin/sh /data/local/tmp/hb_system_watchdog.sh </dev/null >/dev/null 2>&1 & "
                        "fi; "
                        "run-as com.termux /data/data/com.termux/files/usr/bin/env "
                        "HOME=/data/data/com.termux/files/home "
                        "PREFIX=/data/data/com.termux/files/usr "
                        "PATH=/data/data/com.termux/files/usr/bin:/system/bin "
                        "LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib "
                        "/data/data/com.termux/files/usr/bin/bash -c "
                        "'nohup setsid /data/data/com.termux/files/usr/bin/bash "
                        "/data/data/com.termux/files/home/hybridbox-remote-pwa/scripts/keep_awake.sh "
                        "</dev/null >/dev/null 2>&1 &'",
                        timeout=5.0,
                    )
            except Exception:
                pass

    def _find_adb(self) -> Optional[str]:
        adb_bin = shutil.which("adb")
        if adb_bin:
            return adb_bin
        candidates = [
            r"C:\src\Android\Sdk\platform-tools\adb.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
            os.path.expandvars(
                r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe"
            ),
        ]
        for cand in candidates:
            if cand and os.path.exists(cand):
                return cand
        return None

    def _get_active_adb_serials(self, adb_bin: str) -> List[str]:
        try:
            res = subprocess.run(
                [adb_bin, "devices"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            return [
                line.split()[0]
                for line in (res.stdout or "").splitlines()[1:]
                if "\tdevice" in line
            ]
        except Exception:
            return []

    def _resolve_target_serial(self, adb_bin: str, force: bool = False) -> str:
        """Descobre o serial ativo no ADB (priorizando USB/env ou conectando via TCP Wi-Fi 5555)."""
        now = time.time()
        if not force and (now - self._last_adb_check_ts < 3.0):
            return self.active_serial
        self._last_adb_check_ts = now
        active_serials = self._get_active_adb_serials(adb_bin)
        if not active_serials:
            self.discover_phone_ip()
            tcp_targets = []
            if ":" in self.adb_serial:
                tcp_targets.append(self.adb_serial)
            if self.ssh_host:
                wifi_target = f"{self.ssh_host}:5555"
                if wifi_target not in tcp_targets:
                    tcp_targets.append(wifi_target)
            for target in tcp_targets:
                if ":" in target:
                    t_host, t_port = target.split(":", 1)
                    if not self._tcp_open(t_host, int(t_port), 0.22):
                        continue
                try:
                    subprocess.run(
                        [adb_bin, "connect", target],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=1.8,
                    )
                except Exception:
                    pass
            active_serials = self._get_active_adb_serials(adb_bin)
        if self.adb_serial in active_serials:
            self.active_serial = self.adb_serial
        elif f"{self.ssh_host}:5555" in active_serials:
            self.active_serial = f"{self.ssh_host}:5555"
        elif active_serials:
            self.active_serial = active_serials[0]
        else:
            self.active_serial = ""
        return self.active_serial


    def _adapt_cmd_for_ssh(self, shell_cmd: str) -> str:
        """Adapta comandos ADB para execução privilegiada uid=2000(shell) via hb-shell no Termux Wi-Fi SSH."""
        cleaned = re.sub(r"\brun-as\s+com\.termux\s+", "", shell_cmd)
        return (
            "export PATH=/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin; "
            "export LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib; "
            "export HOME=/data/data/com.termux/files/home; "
            "export PREFIX=/data/data/com.termux/files/usr; "
            f"if [ -x /data/data/com.termux/files/usr/bin/hb-shell ]; then "
            f"/data/data/com.termux/files/usr/bin/hb-shell {shlex.quote(cleaned)}; "
            f"else {cleaned}; fi"
        )

    def run_ssh_shell(
        self, shell_cmd: str, timeout: float = 4.5, include_stderr: bool = False
    ) -> str:
        """Executa comando no Android/Termux via Wi-Fi SSH (porta 8022) quando USB está desconectado."""
        ssh_bin = shutil.which("ssh")
        if not ssh_bin:
            return ""
        self.discover_phone_ip()
        if not self._tcp_open(self.ssh_host, self.ssh_port, 0.25):
            return ""
        if self.ssh_user in ("", "termux"):
            self.discover_ssh_user(self.ssh_host)
        try:
            remote_cmd = self._adapt_cmd_for_ssh(shell_cmd)
            res = subprocess.run(
                [
                    ssh_bin,
                    "-p",
                    str(self.ssh_port),
                    "-o",
                    "ConnectTimeout=2",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "StrictHostKeyChecking=no",
                    f"{self.ssh_user}@{self.ssh_host}",
                    remote_cmd,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            out = res.stdout or ""
            if include_stderr and res.stderr:
                out += res.stderr
            return out
        except Exception:
            return ""

    def run_adb_cmd(
        self, args: List[str], timeout: float = 5.0
    ) -> Optional[subprocess.CompletedProcess]:
        """Executa um comando `adb -s <active_serial> ...` com serial explícito."""
        adb_bin = self._find_adb()
        if not adb_bin:
            return None
        serial = self.active_serial or self._resolve_target_serial(adb_bin)
        if not serial:
            return None
        cmd = [adb_bin, "-s", serial] + args
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            if "device '" in (res.stderr or "") and "not found" in (res.stderr or ""):
                serial = self._resolve_target_serial(adb_bin)
                if not serial:
                    return None
                res = subprocess.run(
                    [adb_bin, "-s", serial] + args,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
            return res
        except Exception:
            return None

    def run_adb_shell(self, shell_cmd: str, timeout: float = 5.0, include_stderr: bool = False) -> str:
        """Executa `adb -s <active_serial> shell <cmd>`; se USB estiver desligado, faz fallback automático via Wi-Fi SSH."""
        res = self.run_adb_cmd(["shell", shell_cmd], timeout=timeout)
        if res is not None and not (
            "device '" in (res.stderr or "") and "not found" in (res.stderr or "")
        ):
            out = res.stdout or ""
            if include_stderr and res.stderr:
                out += res.stderr
            if out or res.returncode == 0:
                return out
        # 2. Fallback via Wi-Fi SSH (porta 8022) quando cabo USB está desconectado
        ssh_out = self.run_ssh_shell(
            shell_cmd, timeout=min(timeout, 4.5), include_stderr=include_stderr
        )
        if ssh_out:
            return ssh_out
        # 3. Fallback caso esteja rodando diretamente dentro do próprio Android/Termux
        if os.path.exists("/data/data/com.termux/files/usr/bin/hb-shell"):
            try:
                proc = subprocess.run(
                    ["/data/data/com.termux/files/usr/bin/hb-shell", shell_cmd],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
                out = proc.stdout or ""
                if include_stderr and proc.stderr:
                    out += proc.stderr
                if out or proc.returncode == 0:
                    return out
            except Exception:
                pass
        if os.path.exists("/system/bin/sh"):
            try:
                proc = subprocess.run(
                    ["/system/bin/sh", "-c", shell_cmd],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
                out = proc.stdout or ""
                if include_stderr and proc.stderr:
                    out += proc.stderr
                return out
            except Exception:
                return ""
        return ""

    def _connect(self) -> None:
        """Tenta abrir shell persistente via `adb shell` (USB) ou `ssh -p 8022` (Wi-Fi SSH)."""
        adb_bin = self._find_adb()
        if adb_bin:
            try:
                target_serial = self._resolve_target_serial(adb_bin)
                if target_serial:
                    self._proc = subprocess.Popen(
                        [adb_bin, "-s", target_serial, "shell"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        bufsize=1,
                    )
                    self._backend_type = f"adb-shell ({target_serial})"
                    return
            except Exception:
                self._proc = None

        # 2. Fallback Wi-Fi SSH persistente (porta 8022) quando o cabo USB está desconectado
        ssh_bin = shutil.which("ssh")
        if ssh_bin and not os.path.exists("/system/bin/sh"):
            try:
                if self.ssh_user in ("", "termux"):
                    self.discover_ssh_user(self.ssh_host)
                self._proc = subprocess.Popen(
                    [
                        ssh_bin,
                        "-p",
                        str(self.ssh_port),
                        "-o",
                        "ConnectTimeout=3",
                        "-o",
                        "BatchMode=yes",
                        "-o",
                        "StrictHostKeyChecking=no",
                        f"{self.ssh_user}@{self.ssh_host}",
                        "export PATH=/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin; "
                        "export LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib; "
                        "adb connect 127.0.0.1:5555 >/dev/null 2>&1; "
                        "exec adb -s 127.0.0.1:5555 shell || exec /data/data/com.termux/files/usr/bin/bash",
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
                self._backend_type = f"wifi-ssh ({self.ssh_host}:{self.ssh_port})"
                return
            except Exception:
                self._proc = None

        # 3. Fallback para shell local se rodando diretamente no Android
        if os.path.exists("/system/bin/sh"):
            try:
                self._proc = subprocess.Popen(
                    ["/system/bin/sh"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
                self._backend_type = "android-local-sh"
                return
            except Exception:
                self._proc = None

        self._backend_type = "simulated"


    @property
    def backend_name(self) -> str:
        return self._backend_type

    def is_connected(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def send_raw_command(self, cmd: str) -> None:
        """Envia comando shell diretamente para o pipe persistente sem criar novo processo."""
        with self._lock:
            if not self.is_connected():
                self._connect()
            final_cmd = (
                re.sub(r"\brun-as\s+com\.termux\s+", "", cmd)
                if self._backend_type.startswith("wifi-ssh")
                else cmd
            )
            if self._proc and self._proc.stdin:
                try:
                    self._proc.stdin.write(final_cmd + "\n")
                    self._proc.stdin.flush()
                    return
                except Exception:
                    self._connect()
                    final_cmd = (
                        re.sub(r"\brun-as\s+com\.termux\s+", "", cmd)
                        if self._backend_type.startswith("wifi-ssh")
                        else cmd
                    )
                    if self._proc and self._proc.stdin:
                        try:
                            self._proc.stdin.write(final_cmd + "\n")
                            self._proc.stdin.flush()
                        except Exception:
                            pass

    def send_key(self, key: str) -> None:
        """Dispara `input keyevent` instantaneamente no Android."""
        keycode = KEY_MAP.get(key, key)
        if not str(keycode).startswith("KEYCODE_") and not str(keycode).isdigit():
            keycode = KEY_MAP.get(key.upper(), "KEYCODE_ENTER")
        self.send_raw_command(f"input keyevent {keycode} &")

    def send_gamepad_key(
        self,
        key: str,
        hold_ms: int = 80,
        player: int = 1,
        style: Optional[str] = None,
    ) -> None:
        """
        Aciona botões do Gamepad Virtual PWA de forma híbrida:
        1. Nos emuladores de 60fps (`Snes9x EX+`, `NEO.emu`, `MD.emu`) durante o jogo (`in_emulator_menu=False`),
           usa toque sustentado de `hold_ms` (~5 frames a 60Hz) nas coordenadas calibradas do controle on-screen (`2340x1080`).
        2. Quando o menu do emulador está aberto (`in_emulator_menu=True`), ou em `MAME4droid`/`Lemuroid` ou Player 2..4,
           envia `input keyevent` (`KEYCODE_DPAD_*`, `KEYCODE_ENTER`, `KEYCODE_BACK`) para navegar listas/menus sem tocar em itens acidentais.
        """
        k_up = (key or "").strip().upper()
        if not k_up:
            return
        style_clean = (style or "").strip().lower()
        active_emu = (self.active_emulator or "").strip().lower()

        if (
            (player and int(player) > 1)
            or active_emu in ("mame4droid", "lemuroid")
            or style_clean in ("mame4droid", "lemuroid")
        ):
            self.send_key(k_up)
            return

        emu_target = (
            active_emu
            if active_emu in GAMEPAD_TOUCH_COORDS
            else (style_clean if style_clean in GAMEPAD_TOUCH_COORDS else "snes")
        )

        if k_up == "BACK":
            if not self.in_emulator_menu:
                self.in_emulator_menu = True
                self.send_raw_command("input keyevent KEYCODE_BACK &")
            else:
                self.in_emulator_menu = False
                self.send_raw_command("input tap 2150 110 &")
            return

        if self.in_emulator_menu:
            if k_up in ("UP", "DOWN", "LEFT", "RIGHT"):
                self.send_key(k_up)
                return
            if k_up in ("BTN_A", "OK", "ENTER", "BTN_START"):
                self.send_raw_command("input keyevent KEYCODE_ENTER &")
                return
            if k_up in ("BTN_B", "BTN_Y"):
                self.send_raw_command("input keyevent KEYCODE_BACK &")
                return

        emu_coords = GAMEPAD_TOUCH_COORDS.get(emu_target, GAMEPAD_TOUCH_COORDS["snes"])
        if k_up in emu_coords:
            x, y = emu_coords[k_up]
            self.send_raw_command(f"input touchscreen swipe {x} {y} {x} {y} {hold_ms} &")
            return
        self.send_key(k_up)

    def send_text(self, text: str) -> None:
        """Envia texto para campos de busca do Android TV (SmartTube, Stremio, Kodi)."""
        if not text:
            return
        # Escapa espaços para o comando `input text` do Android
        escaped = text.replace(" ", "%s")
        safe = shlex.quote(escaped)
        self.send_raw_command(f"input text {safe} &")

    def sync_screen_bounds(self, force: bool = False) -> Tuple[int, int]:
        """Sincroniza dimensões lógicas da tela Android (1080x2340 em retrato vs 2340x1080 em paisagem)."""
        now = time.time()
        if not force and (now - self._last_bounds_ts < 2.5):
            return (self.screen_w, self.screen_h)
        self._last_bounds_ts = now
        try:
            out = self.run_adb_shell(
                "dumpsys input 2>/dev/null | grep -m 1 'Viewport INTERNAL:' || "
                "CLASSPATH=/data/local/tmp/hybridbox_bridge.jar "
                "/system/bin/app_process / HybridBoxBridge status 2>/dev/null | grep DISPLAY_BOUNDS",
                timeout=2.5,
            )
            m = re.search(
                r"logicalFrame=\[\d+,\s*\d+,\s*(\d+),\s*(\d+)\]", out or ""
            ) or re.search(r"DISPLAY_BOUNDS=(\d+)x(\d+)", out or "")
            if m:
                new_w, new_h = int(m.group(1)), int(m.group(2))
                if new_w > 0 and new_h > 0 and (new_w != self.screen_w or new_h != self.screen_h):
                    old_w, old_h = self.screen_w, self.screen_h
                    self.screen_w, self.screen_h = new_w, new_h
                    self.cursor_x = max(0, min(new_w, int(self.cursor_x * new_w / max(1, old_w))))
                    self.cursor_y = max(0, min(new_h, int(self.cursor_y * new_h / max(1, old_h))))
        except Exception:
            pass
        finally:
            self._bounds_syncing = False
        return (self.screen_w, self.screen_h)


    def _maybe_refresh_bounds_async(self) -> None:
        if not self._bounds_syncing and (time.time() - self._last_bounds_ts >= 2.5):
            self._bounds_syncing = True
            threading.Thread(
                target=self.sync_screen_bounds, kwargs={"force": True}, daemon=True
            ).start()

    def move_cursor(self, dx: float, dy: float) -> None:
        """Atualiza coordenadas do ponteiro virtual para toques na interface Android."""
        self._maybe_refresh_bounds_async()
        self.cursor_x = max(0, min(self.screen_w, int(self.cursor_x + dx * 1.4)))
        self.cursor_y = max(0, min(self.screen_h, int(self.cursor_y + dy * 1.4)))

    def tap_current(self, button: int = 1) -> None:
        """Executa tap na posição atual (ou botão Voltar no clique direito)."""
        self._maybe_refresh_bounds_async()
        if button == 3:
            self.send_key("BACK")
        else:
            self.send_raw_command(
                f"for i in 1 2 3 4; do input tap {self.cursor_x} {self.cursor_y} 2>/dev/null && break; done &"
            )

    def scroll(self, dx: float = 0.0, dy: float = 0.0) -> None:
        """Converte gesto de scroll com 2 dedos em swipe suave na tela Android (retrato ou paisagem)."""
        self._maybe_refresh_bounds_async()
        cx = self.screen_w // 2
        cy = self.screen_h // 2
        if abs(dy) >= 8:
            y1 = cy
            delta_y = min(380, max(120, (self.screen_h // 2) - 120))
            y2 = max(100, cy - delta_y) if dy < 0 else min(self.screen_h - 100, cy + delta_y)
            self.send_raw_command(
                f"for i in 1 2 3 4; do input swipe {cx} {y1} {cx} {y2} 90 2>/dev/null && break; done &"
            )
        elif abs(dx) >= 8:
            x1 = cx
            delta_x = min(320, max(120, (self.screen_w // 2) - 120))
            x2 = max(100, cx - delta_x) if dx < 0 else min(self.screen_w - 100, cx + delta_x)
            self.send_raw_command(
                f"for i in 1 2 3 4; do input swipe {x1} {cy} {x2} {cy} 90 2>/dev/null && break; done &"
            )

    def run_fallback_chain(self, commands: List[str]) -> None:
        """Executa uma cadeia de comandos Android com fallback (`cmd1 || cmd2`), garantindo tela acesa."""
        if not commands:
            return
        chained = " || ".join(f"({c})" for c in commands)
        self.send_raw_command(
            "(CLASSPATH=/data/local/tmp/hybridbox_bridge.jar "
            "/system/bin/app_process / HybridBoxBridge wake >/dev/null 2>&1; "
            f"input keyevent KEYCODE_WAKEUP 2>/dev/null; wm dismiss-keyguard 2>/dev/null; ({chained})) >/dev/null 2>&1 &"
        )


    def ensure_ghost_touch_shield(self) -> None:
        """Ativa o bloqueio kernel evdev (/dev/input/event2) para impedir toques fantasmas no Android e X11."""
        self.send_raw_command(
            "if [ -x /data/local/tmp/grab_ghost_touch ]; then "
            "/data/local/tmp/grab_ghost_touch --daemon >/dev/null 2>&1; "
            "elif [ -f /sdcard/grab_ghost_touch ]; then "
            "cp /sdcard/grab_ghost_touch /data/local/tmp/grab_ghost_touch && "
            "chmod 755 /data/local/tmp/grab_ghost_touch && "
            "/data/local/tmp/grab_ghost_touch --daemon >/dev/null 2>&1; "
            "fi &"
        )

    def switch_to_linux_desktop(self) -> None:
        """Garante que o servidor Termux:X11 (:0) e XFCE4 estejam ativos, blinda contra toques fantasmas e traz o Termux:X11 para o primeiro plano."""
        self.ensure_ghost_touch_shield()
        self.send_raw_command(
            "run-as com.termux /data/data/com.termux/files/usr/bin/env "
            "DISPLAY=:0 MOZ_DISABLE_CONTENT_SANDBOX=1 "
            "HOME=/data/data/com.termux/files/home "
            "PREFIX=/data/data/com.termux/files/usr "
            "PATH=/data/data/com.termux/files/usr/bin:/system/bin "
            "LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib "
            "/data/data/com.termux/files/usr/bin/bash -c "
            "'pgrep -f \"[t]ermux.x11\" >/dev/null 2>&1 || (nohup termux-x11 :0 -ac </dev/null >/dev/null 2>&1 & sleep 1); "
            "pgrep -f \"[x]fce4-session\" >/dev/null 2>&1 || (nohup env MOZ_DISABLE_CONTENT_SANDBOX=1 dbus-launch --exit-with-session startxfce4 </dev/null >/dev/null 2>&1 &); "
            "python3 /data/data/com.termux/files/home/hybridbox-remote-pwa/scripts/shield_x11_touch.py --full >/dev/null 2>&1 &' "
            ">/dev/null 2>&1 &"
        )
        self.run_fallback_chain(
            [
                "am start -n com.termux.x11/.MainActivity",
                "monkey -p com.termux.x11 -c android.intent.category.LAUNCHER 1",
                "am start -n com.termux/.app.TermuxActivity",
            ]
        )

    def switch_to_tv_box(self) -> None:
        """Retorna para o Projectivy Launcher ou Home do Android TV."""
        self.ensure_ghost_touch_shield()
        self.run_fallback_chain(
            [
                "am start -n com.spocky.projengmenu/.ui.home.MainActivity",
                "am start -n com.spocky.projengmenu/.activities.MainActivity",
                "monkey -p com.spocky.projengmenu -c android.intent.category.LAUNCHER 1",
                "input keyevent KEYCODE_HOME",
            ]
        )

    def switch_to_games_hub(self) -> None:
        """Mantém o emulador atual em primeiro plano (sem interromper o jogo ativo) ou abre o emulador de `active_emulator`."""
        self.ensure_ghost_touch_shield()
        emu_act_map = {
            "snes": "com.explusalpha.Snes9xPlus/com.imagine.BaseActivity",
            "mame": "com.explusalpha.NeoEmu/com.imagine.BaseActivity",
            "megadrive": "com.explusalpha.MdEmu/com.imagine.BaseActivity",
        }
        preferred_act = emu_act_map.get(self.active_emulator, emu_act_map["snes"])
        self.send_raw_command(
            "(if ! dumpsys activity activities 2>/dev/null | grep -E 'mResumedActivity|topResumedActivity' | "
            "grep -qE 'com\\.explusalpha\\.|com\\.swordfish\\.lemuroid|com\\.seleuco\\.'; then "
            f"/system/bin/am start --user 0 -n {preferred_act} >/dev/null 2>&1; "
            "fi) &"
        )

    def get_battery_and_health(self, force: bool = False) -> Dict[str, Any]:
        """
        Retorna o status da bateria e conectividade real do Xiaomi Redmi Note 8 Pro:
        - `phone_online`: True se o celular está ligado e acessível na rede/USB; False se desligou (0% bateria).
        - `level`: 0..100 (%)
        - `charging`: True se conectado ao carregador AC / USB / Wireless
        - `power_source`: 'ac' | 'usb' | 'wireless' | 'battery' | 'offline'
        - `temperature_c`: temperatura em °C
        - `low_battery`: True se <= 20% e fora da tomada
        - `critical_battery`: True se <= 12% e fora da tomada
        - `status_text`: ex: '⚡ 86%' ou '🔋 64%' ou '🪫 14%' ou '🔌 Desligado'
        """
        now = time.time()
        if not force and self._cached_battery and (now - self._last_battery_ts < 12.0):
            return self._cached_battery

        raw = ""
        phone_online = False

        if os.path.exists("/data/data/com.termux"):
            phone_online = True
            raw = self.run_adb_shell("dumpsys battery 2>/dev/null", timeout=2.5)
        else:
            # No Windows PC: verifica primeiro se o Xiaomi responde via TCP (8080/8022/5555) ou USB ADB
            ip = self.ssh_host or "hybridbox.local"
            if (
                self._tcp_open(ip, 8080, 0.4)
                or self._tcp_open(ip, self.ssh_port, 0.4)
                or self._tcp_open(ip, 5555, 0.4)
            ):
                phone_online = True
            else:
                adb_bin = self._find_adb()
                if adb_bin:
                    active_s = self._get_active_adb_serials(adb_bin)
                    if active_s:
                        phone_online = True

            if phone_online:
                raw = self.run_adb_shell("dumpsys battery 2>/dev/null", timeout=2.5)
                if not raw or "level:" not in raw:
                    # Fallback via SSH se o ADB ainda estiver reconectando
                    ssh_bin = shutil.which("ssh")
                    if ssh_bin and self._tcp_open(ip, self.ssh_port, 0.4):
                        try:
                            if self.ssh_user in ("", "termux"):
                                self.discover_ssh_user(ip)
                            r_ssh = subprocess.run(
                                [
                                    ssh_bin,
                                    "-p",
                                    str(self.ssh_port),
                                    "-o",
                                    "BatchMode=yes",
                                    "-o",
                                    "ConnectTimeout=2",
                                    "-o",
                                    "StrictHostKeyChecking=no",
                                    f"{self.ssh_user}@{ip}",
                                    "/data/data/com.termux/files/usr/bin/hb-shell 'dumpsys battery' 2>/dev/null",
                                ],
                                capture_output=True,
                                text=True,
                                timeout=3.0,
                            )
                            raw = r_ssh.stdout or ""
                        except Exception:
                            pass

        if not phone_online and not raw:
            res_offline = {
                "phone_online": False,
                "level": None,
                "charging": False,
                "power_source": "offline",
                "temperature_c": None,
                "low_battery": False,
                "critical_battery": False,
                "status_text": "Offline",
                "offline_reason": (
                    "The Xiaomi Redmi Note 8 Pro is not responding on Wi-Fi or USB "
                    "(it likely drained its battery to 0% and powered off)."
                ),
            }
            self._cached_battery = res_offline
            self._last_battery_ts = now
            return res_offline

        level: Optional[int] = None
        m_lvl = re.search(r"level:\s*(\d+)", raw)
        if m_lvl:
            level = max(0, min(100, int(m_lvl.group(1))))

        ac_pow = bool(re.search(r"AC powered:\s*true", raw, re.IGNORECASE))
        usb_pow = bool(re.search(r"USB powered:\s*true", raw, re.IGNORECASE))
        wl_pow = bool(re.search(r"Wireless powered:\s*true", raw, re.IGNORECASE))
        m_st = re.search(r"status:\s*(\d+)", raw)
        status_code = int(m_st.group(1)) if m_st else 0
        charging = ac_pow or usb_pow or wl_pow or (status_code in (2, 5))

        power_source = "ac" if ac_pow else ("usb" if usb_pow else ("wireless" if wl_pow else "battery"))
        temp_c: Optional[float] = None
        m_tmp = re.search(r"temperature:\s*(\d+)", raw)
        if m_tmp:
            temp_c = round(int(m_tmp.group(1)) / 10.0, 1)

        low_battery = bool(level is not None and level <= 20 and not charging)
        critical_battery = bool(level is not None and level <= 12 and not charging)

        if level is not None:
            icon = "⚡" if charging else ("🪫" if low_battery else "🔋")
            status_text = f"{icon} {level}%"
        else:
            status_text = "⚡ Online" if phone_online else "🔌 Offline"

        res = {
            "phone_online": True,
            "level": level,
            "charging": charging,
            "power_source": power_source,
            "temperature_c": temp_c,
            "low_battery": low_battery,
            "critical_battery": critical_battery,
            "status_text": status_text,
            "offline_reason": "",
        }
        self._cached_battery = res
        self._last_battery_ts = now
        return res

    def ensure_termux_boot_and_autostart(self) -> Dict[str, Any]:
        """
        Instala o APK `Termux:Boot` (`com.termux.boot`) se ainda não estiver instalado no Xiaomi
        e concede as permissões de Autostart da MIUI 12.5 (`OP_AUTO_START = 10008` + `BOOT_COMPLETED`)
        para que o celular inicie `sshd` (8022) e `uvicorn` (8080) sozinho ao ligar no botão Power.
        """
        base_dir = Path(__file__).resolve().parent.parent
        apks_dir = base_dir / "apks"
        pkg_out = self.run_adb_shell("pm list packages com.termux.boot 2>/dev/null", timeout=3.5)
        installed_boot = "package:com.termux.boot" in (pkg_out or "")

        if not installed_boot and os.name == "nt":
            adb_bin = self._find_adb()
            serial = self._resolve_target_serial(adb_bin, force=True) if adb_bin else ""
            if adb_bin and serial:
                for apk_name in ("termux-boot-fdroid.apk", "termux-boot-gh-termux-boot-app_v0.8.1+github.debug.apk"):
                    apk_path = apks_dir / apk_name
                    if apk_path.exists() and apk_path.stat().st_size > 10000:
                        try:
                            r_inst = subprocess.run(
                                [adb_bin, "-s", serial, "install", "-r", str(apk_path)],
                                capture_output=True,
                                text=True,
                                timeout=20.0,
                            )
                            if "Success" in (r_inst.stdout or ""):
                                installed_boot = True
                                break
                        except Exception:
                            pass

        # Configura permissões MIUI 12.5 Autostart (10008), Battery Whitelist e registra o Receiver de Boot
        autostart_cmd = (
            "for pkg in com.termux com.termux.boot com.termux.x11 com.termux.api com.spocky.projengmenu; do "
            "dumpsys deviceidle whitelist +$pkg 2>/dev/null; "
            "cmd appops set $pkg RUN_IN_BACKGROUND allow 2>/dev/null; "
            "cmd appops set $pkg RUN_ANY_IN_BACKGROUND allow 2>/dev/null; "
            "cmd appops set $pkg WAKE_LOCK allow 2>/dev/null; "
            "cmd appops set $pkg SYSTEM_ALERT_WINDOW allow 2>/dev/null; "
            "appops set $pkg 10008 allow 2>/dev/null; "
            "pm enable $pkg 2>/dev/null; "
            "done; "
            "am start -n com.termux.boot/.BootActivity --ez background true >/dev/null 2>&1 || true"
        )
        self.run_adb_shell(autostart_cmd, timeout=5.0)
        return {"ok": True, "termux_boot_installed": installed_boot}

    def revive_phone_connection(self) -> Dict[str, Any]:
        """
        Aciona a recuperação completa ('Plug & Revive') do Xiaomi Redmi Note 8 Pro:
        1. Procura o celular no cabo USB, mDNS (`hybridbox.local`) e Wi-Fi LAN;
        2. Se estiver no USB, ativa `adb tcpip 5555`, sobe `/data/local/tmp/hb_system_watchdog.sh` e `HybridBoxBridge (5558)`;
        3. Garante que `Termux:Boot` + `keep_awake.sh` + `uvicorn (8080)` estejam rodando;
        4. Retorna o diagnóstico completo e nível de bateria.
        """
        adb_bin = self._find_adb()
        usb_found = False
        if adb_bin:
            serials = self._get_active_adb_serials(adb_bin)
            usb_serials = [s for s in serials if ":" not in s and not s.startswith("emulator-")]
            if usb_serials:
                usb_found = True
                usb_s = usb_serials[0]
                try:
                    subprocess.run([adb_bin, "-s", usb_s, "tcpip", "5555"], timeout=4.0, capture_output=True)
                    time.sleep(1.0)
                except Exception:
                    pass

        phone_ip = self.discover_phone_ip(force=True)
        reachable_now = bool(
            usb_found
            or (
                phone_ip
                and (
                    self._tcp_open(phone_ip, 5555, 0.3)
                    or self._tcp_open(phone_ip, self.ssh_port, 0.3)
                    or self._tcp_open(phone_ip, 8080, 0.3)
                )
            )
        )
        if reachable_now:
            if adb_bin and phone_ip and self._tcp_open(phone_ip, 5555, 0.3):
                try:
                    subprocess.run([adb_bin, "connect", f"{phone_ip}:5555"], timeout=2.0, capture_output=True)
                except Exception:
                    pass

            with self._lock:
                self._connect()

            # Tenta levantar o watchdog de sistema e o keep_awake.sh
            self.ensure_termux_boot_and_autostart()
            self.run_adb_shell(
                "if [ -f /data/local/tmp/hb_system_watchdog.sh ]; then "
                "chmod 755 /data/local/tmp/hb_system_watchdog.sh 2>/dev/null; "
                "nohup /system/bin/sh /data/local/tmp/hb_system_watchdog.sh </dev/null >/dev/null 2>&1 & "
                "fi; "
                "run-as com.termux /data/data/com.termux/files/usr/bin/env "
                "HOME=/data/data/com.termux/files/home "
                "PREFIX=/data/data/com.termux/files/usr "
                "PATH=/data/data/com.termux/files/usr/bin:/system/bin "
                "LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib "
                "/data/data/com.termux/files/usr/bin/bash -c "
                "'nohup setsid /data/data/com.termux/files/usr/bin/bash "
                "/data/data/com.termux/files/home/hybridbox-remote-pwa/scripts/keep_awake.sh "
                "</dev/null >/dev/null 2>&1 &'",
                timeout=4.0,
            )

        bat = self.get_battery_and_health(force=True)
        online = bool(bat.get("phone_online"))
        return {
            "ok": online,
            "phone_online": online,
            "usb_connected": usb_found,
            "phone_ip": phone_ip,
            "mdns_url": "http://hybridbox.local:8080",
            "battery": bat,
            "message": (
                f"✅ Xiaomi Redmi Note 8 Pro reconnected ({bat.get('status_text', 'Online')}) at {phone_ip}!"
                if online
                else (
                    "🔌 The Xiaomi Redmi Note 8 Pro is still powered off or charging from 0%. "
                    "Plug it into the USB cable/charger, hold the side Power button for 5–10 seconds until it vibrates, and wait 45s!"
                )
            ),
        }
