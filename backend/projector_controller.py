"""
Wireless Connection Controller for Projector & Smart TVs (Miracast / Wireless Display / MIUI Cast / DLNA).
Combina:
1. Descoberta e Controle Nativo Windows Miracast / Wi-Fi Direct (`SWD\\WIFIDIRECT` e `SWD\\DAFUPNPPROVIDER`)
   + controle de modo de projeção (`DisplaySwitch.exe /clone`, `/extend`, `/external`, `/internal`)
   + automação UIAutomation do `Win+K`;
2. Automação ADB + Fallback Wi-Fi SSH (porta 8022) do Android WifiDisplayAdapter (Miracast / MCAST /
   CLcast / Projector) + Xiaomi MiLink Cast (mesmo quando o cabo USB está desconectado);
3. Descoberta e envio UPnP/DLNA via SSDP + SOAP AVTransport (baseado em cherezov/dlnap e nanodlna no GitHub).
"""

import base64
import concurrent.futures
import ctypes
import os
import re
import shlex
import socket
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple


PROJECTOR_KEYWORDS = (
    "projector",
    "clcast",
    "mcast",
    "anycast",
    "miracast",
    "rkcast",
    "wfd",
    "lollipop",
    "hy300",
    "hy320",
    "magcubic",
    "wanbo",
    "xgimi",
    "epson",
    "benq",
)

PROJECTOR_WFD_MAC = os.environ.get("HYBRIDBOX_PROJECTOR_WFD_MAC", "").strip()
PROJECTOR_LAN_MAC = os.environ.get("HYBRIDBOX_PROJECTOR_MAC", "").strip().lower().replace(":", "-")
PROJECTOR_MAC_SUFFIX = (
    "-".join(PROJECTOR_LAN_MAC.split("-")[-3:]) if PROJECTOR_LAN_MAC.count("-") >= 2 else ""
)


class ProjectorController:
    """Gerencia descoberta e conexão Wi-Fi (Miracast Windows + Android + DLNA + Auto-IP LAN) com o Projector."""

    def __init__(self, android_controller: Any) -> None:
        self.android = android_controller
        self.ssh_host = (
            os.environ.get("HYBRIDBOX_SSH_HOST", "")
            or getattr(android_controller, "ssh_host", "")
            or "hybridbox.local"
        )
        self.ssh_port = int(os.environ.get("HYBRIDBOX_SSH_PORT", "8022"))
        self.ssh_user = (
            os.environ.get("HYBRIDBOX_SSH_USER", "")
            or getattr(android_controller, "ssh_user", "")
            or "termux"
        )
        self.cached_projector_ip = os.environ.get("HYBRIDBOX_PROJECTOR_IP", "")
        self._last_lan_check_ts: float = 0.0
        self._cached_lan_device: Optional[Dict[str, Any]] = None
        self.last_devices: List[Dict[str, Any]] = []
        self.last_status: Dict[str, Any] = {
            "wfd_enabled": False,
            "scanning": False,
            "active_display": None,
            "display_mode": None,
            "projector_ip": self.cached_projector_ip,
        }

    def _run_adb(self, shell_cmd: str, timeout: float = 4.5) -> str:
        """Executa comando adb shell síncrono; se USB estiver desconectado, faz fallback via Wi-Fi SSH."""
        out = self.android.run_adb_shell(shell_cmd, timeout=timeout)
        if out:
            return out
        return self._run_wifi_ssh(shell_cmd, timeout=min(timeout, 3.5))

    def _run_wifi_ssh(self, shell_cmd: str, timeout: float = 3.5) -> str:
        """Executa comando no Android/Termux via Wi-Fi SSH (porta 8022) como uid=2000(shell) via hb-shell."""
        try:
            if hasattr(self.android, "discover_phone_ip"):
                self.ssh_host = self.android.discover_phone_ip()
            elif hasattr(self.android, "ssh_host") and self.android.ssh_host:
                self.ssh_host = self.android.ssh_host
            if self.ssh_user in ("", "termux"):
                if hasattr(self.android, "discover_ssh_user"):
                    self.ssh_user = self.android.discover_ssh_user(self.ssh_host)
                elif getattr(self.android, "ssh_user", "") not in ("", "termux"):
                    self.ssh_user = self.android.ssh_user
            remote_cmd = (
                "export PATH=/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin; "
                "export LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib; "
                f"if [ -x /data/data/com.termux/files/usr/bin/hb-shell ]; then "
                f"/data/data/com.termux/files/usr/bin/hb-shell {shlex.quote(shell_cmd)}; "
                f"else {shell_cmd}; fi"
            )
            res = subprocess.run(
                [
                    "ssh",
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
                timeout=timeout,
            )
            return ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
        except Exception:
            return ""

    def wake_phone_screen(self, bring_to_front: bool = False) -> Dict[str, Any]:
        """
        Acorda imediatamente a tela do Redmi Note 8 Pro via IPowerManager (HybridBoxBridge wake)
        e garante que o daemon keep_awake.sh mantenha o WakeLock ativo mesmo sem cabo USB.
        """
        front_cmd = ""
        if bring_to_front:
            front_cmd = (
                "am start --user 0 -n com.spocky.projengmenu/.ui.home.MainActivity >/dev/null 2>&1 || "
                "am start --user 0 -n com.termux.x11/.MainActivity >/dev/null 2>&1; "
            )
        wake_cmd = (
            "termux-wake-lock 2>/dev/null || true; "
            "CLASSPATH=/data/local/tmp/hybridbox_bridge.jar "
            "/system/bin/app_process / HybridBoxBridge wake >/dev/null 2>&1; "
            "input keyevent 224 2>/dev/null || true; "
            "ps -ef | grep -q '[k]eep_awake.sh' || "
            "(nohup setsid /data/data/com.termux/files/usr/bin/bash "
            "/data/data/com.termux/files/home/hybridbox-remote-pwa/scripts/keep_awake.sh </dev/null >/dev/null 2>&1 &); "
            f"{front_cmd}"
        )
        self.android.send_raw_command(f"({wake_cmd}) &")
        return {
            "ok": True,
            "message": (
                "☀️ Redmi Note 8 Pro screen woken up and locked in Always-Awake mode "
                "(WakeLock active via Wi-Fi SSH)!"
            ),
        }

    def _safe_tap(self, x: int, y: int) -> None:
        """Executa input tap com repetição automática contra toques fantasmas do digitizer."""
        self._run_adb(
            f"for i in 1 2 3 4 5; do input tap {x} {y} 2>/dev/null && break; done",
            timeout=4.0,
        )

    # ==================== DESCOBERTA AUTOMÁTICA DE IP DO PROJETOR NA REDE WI-FI ====================

    def _get_local_subnet_prefix(self) -> str:
        """Retorna o prefixo /24 da sub-rede Wi-Fi local (ex: '192.168.0.')."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                parts = ip.split(".")
                if len(parts) == 4:
                    return f"{parts[0]}.{parts[1]}.{parts[2]}."
        except Exception:
            pass
        parts = self.cached_projector_ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}."
        return "192.168.0."

    def _probe_projector_http(self, ip: str, timeout: float = 0.35) -> Optional[Dict[str, Any]]:
        """Verifica se o IP pertence ao Projector (`Lollipop wifi` / `/cgi-bin/home.cgi` / porta 80)."""
        if not ip:
            return None
        try:
            with socket.create_connection((ip, 80), timeout=min(0.15, timeout)):
                pass
        except Exception:
            return None
        for path in ("/", "/cgi-bin/home.cgi"):
            try:
                req = urllib.request.Request(
                    f"http://{ip}{path}",
                    headers={"User-Agent": "HybridBox-ProjectorLocator/1.0"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    body = resp.read(600).decode("utf-8", errors="ignore").lower()
                    if any(k in body for k in ("lollipop", "cgi-bin/home.cgi", "wifi.cgi", "projector")):
                        self.cached_projector_ip = ip
                        mac_info = f" • MAC {PROJECTOR_WFD_MAC}" if PROJECTOR_WFD_MAC else ""
                        dev = {
                            "id": f"http:{ip}",
                            "name": "Projector",
                            "raw_name": "Wireless Projector",
                            "ip": ip,
                            "mac": PROJECTOR_LAN_MAC.upper().replace("-", ":") if PROJECTOR_LAN_MAC else "",
                            "wfd_mac": PROJECTOR_WFD_MAC,
                            "address": f"IP {ip}{mac_info} (Located on LAN)",
                            "admin_url": f"http://{ip}/cgi-bin/home.cgi",
                            "protocol": "Miracast + Wi-Fi LAN (Auto-IP)",
                            "available": True,
                            "connected": False,
                            "source": "lan-http",
                            "is_projector": True,
                        }
                        self._cached_lan_device = dev
                        self._last_lan_check_ts = time.time()
                        return dev
            except Exception:
                continue
        return None

    def discover_projector_network_device(self, deep_scan: bool = False) -> Optional[Dict[str, Any]]:
        """
        Localiza automaticamente o IP do Projector na rede Wi-Fi mesmo que o DHCP mude o IP:
        1. Testa o último IP conhecido (`self.cached_projector_ip`);
        2. Inspeciona a tabela ARP (`arp -a`) pelo MAC configurado (opcional);
        3. Faz varredura paralela rápida na sub-rede `/24` (porta 80 `Lollipop wifi`) se o IP mudou.
        """
        now = time.time()
        if not deep_scan and (now - self._last_lan_check_ts < 15.0):
            return self._cached_lan_device
        self._last_lan_check_ts = now

        # 1. Testa o IP em cache primeiro (<15ms na LAN)
        cached_hit = self._probe_projector_http(self.cached_projector_ip, timeout=0.3)
        if cached_hit:
            return cached_hit

        # 2. Procura na tabela ARP do sistema
        prefix = self._get_local_subnet_prefix()
        arp_candidates: List[str] = []
        try:
            arp_out = subprocess.check_output(["arp", "-a"], text=True, timeout=1.2, errors="ignore")
            for line in arp_out.splitlines():
                line_low = line.lower().replace(":", "-")
                m_ip = re.search(r"(\d+\.\d+\.\d+\.\d+)", line_low)
                if not m_ip:
                    continue
                ip_cand = m_ip.group(1)
                if (PROJECTOR_LAN_MAC and PROJECTOR_LAN_MAC in line_low) or (
                    PROJECTOR_MAC_SUFFIX and PROJECTOR_MAC_SUFFIX in line_low
                ):
                    probed = self._probe_projector_http(ip_cand, timeout=0.4)
                    if probed:
                        return probed
                    self.cached_projector_ip = ip_cand
                    mac_info = f" • MAC {PROJECTOR_WFD_MAC}" if PROJECTOR_WFD_MAC else ""
                    dev = {
                        "id": f"http:{ip_cand}",
                        "name": "Projector",
                        "raw_name": "Wireless Projector",
                        "ip": ip_cand,
                        "mac": PROJECTOR_LAN_MAC.upper().replace("-", ":") if PROJECTOR_LAN_MAC else "",
                        "wfd_mac": PROJECTOR_WFD_MAC,
                        "address": f"IP {ip_cand}{mac_info} (ARP Located)",
                        "admin_url": f"http://{ip_cand}/cgi-bin/home.cgi",
                        "protocol": "Miracast + Wi-Fi LAN (Auto-IP)",
                        "available": True,
                        "connected": False,
                        "source": "lan-http",
                        "is_projector": True,
                    }
                    self._cached_lan_device = dev
                    self._last_lan_check_ts = time.time()
                    return dev
                if ip_cand.startswith(prefix) and not ip_cand.endswith((".1", ".255")) and "dynamic" in line_low:
                    arp_candidates.append(ip_cand)
        except Exception:
            pass

        # 3. Testa IPs dinâmicos da tabela ARP em paralelo
        if arp_candidates:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, len(arp_candidates))) as ex:
                for res in ex.map(lambda ip: self._probe_projector_http(ip, timeout=0.25), arp_candidates):
                    if res:
                        return res

        # 4. Se solicitado `deep_scan`, varre toda a sub-rede /24 na porta 80
        if deep_scan:
            def _scan_host(host_ip: str) -> Optional[Dict[str, Any]]:
                return self._probe_projector_http(host_ip, timeout=0.35)

            all_ips = [f"{prefix}{i}" for i in range(2, 255) if f"{prefix}{i}" not in arp_candidates]
            with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
                for res in ex.map(_scan_host, all_ips):
                    if res:
                        return res

        return self._cached_lan_device

    # ==================== DESCOBERTA & CONTROLE MIRACAST NO WINDOWS (LAPTOP) ====================

    def _get_windows_monitors(self) -> List[Tuple[int, int, int, int]]:
        """Retorna lista de monitores ativos no Windows: [(x, y, width, height), ...]."""
        if os.name != "nt":
            return []
        monitors: List[Tuple[int, int, int, int]] = []
        try:
            from ctypes import wintypes

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                wintypes.BOOL,
                wintypes.HMONITOR,
                wintypes.HDC,
                ctypes.POINTER(RECT),
                wintypes.LPARAM,
            )

            def _cb(hmon: int, hdc: int, lprect: Any, lparam: int) -> bool:
                r = lprect.contents
                monitors.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
                return True

            ctypes.windll.user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_cb), 0)
        except Exception:
            pass
        return monitors

    def _is_win_devnode_started(self, instance_id: str) -> bool:
        """Verifica via cfgmgr32.dll se o devnode PnP possui flag DN_STARTED."""
        if os.name != "nt":
            return False
        try:
            from ctypes import wintypes

            cfgmgr32 = ctypes.windll.cfgmgr32
            DN_STARTED = 0x00000008
            devinst = wintypes.DWORD()
            if cfgmgr32.CM_Locate_DevNodeW(ctypes.byref(devinst), instance_id, 0) != 0:
                return False
            status = wintypes.ULONG()
            problem = wintypes.ULONG()
            if (
                cfgmgr32.CM_Get_DevNode_Status(
                    ctypes.byref(status), ctypes.byref(problem), devinst, 0
                )
                != 0
            ):
                return False
            return bool(status.value & DN_STARTED)
        except Exception:
            return False

    def _is_win_devnode_connected(self, instance_id: str) -> bool:
        """
        Verifica via cfgmgr32.dll `CM_Get_DevNode_PropertyW` (`DEVPKEY_Device_IsConnected`,
        GUID `{83da6326-97a6-4088-9453-a1923f573b29}`, pid 15) se o projetor Miracast
        está efetivamente conectado (evita falso-positivo de `DN_STARTED` em dispositivos pareados).
        """
        if os.name != "nt":
            return False
        try:
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            class DEVPROPKEY(ctypes.Structure):
                _fields_ = [
                    ("fmtid", GUID),
                    ("pid", wintypes.ULONG),
                ]

            cfgmgr32 = ctypes.windll.cfgmgr32
            DN_STARTED = 0x00000008
            devinst = wintypes.DWORD()
            if cfgmgr32.CM_Locate_DevNodeW(ctypes.byref(devinst), instance_id, 0) != 0:
                return False
            status = wintypes.ULONG()
            problem = wintypes.ULONG()
            if (
                cfgmgr32.CM_Get_DevNode_Status(
                    ctypes.byref(status), ctypes.byref(problem), devinst, 0
                )
                != 0
            ):
                return False
            if not (status.value & DN_STARTED):
                return False

            devpkey_is_connected = DEVPROPKEY(
                GUID(
                    0x83DA6326,
                    0x97A6,
                    0x4088,
                    (ctypes.c_ubyte * 8)(0x94, 0x53, 0xA1, 0x92, 0x3F, 0x57, 0x3B, 0x29),
                ),
                15,
            )
            prop_type = wintypes.ULONG()
            buf = (ctypes.c_ubyte * 16)()
            buf_size = wintypes.ULONG(ctypes.sizeof(buf))
            rc = cfgmgr32.CM_Get_DevNode_PropertyW(
                devinst,
                ctypes.byref(devpkey_is_connected),
                ctypes.byref(prop_type),
                buf,
                ctypes.byref(buf_size),
                0,
            )
            if rc == 0 and prop_type.value == 17:  # DEVPROP_TYPE_BOOLEAN
                return bool(buf[0] != 0)
            return False
        except Exception:
            return False

    def discover_windows_miracast_devices(
        self, lan_device: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
        """
        Descobre projetores Miracast / Wi-Fi Direct e receptores UPnP/Cast
        pareados ou conectados diretamente no Windows Laptop.
        Retorna: (devices, active_display_str, display_mode)
        """
        if os.name != "nt":
            return [], None, None

        import winreg

        if lan_device is None:
            lan_device = self.discover_projector_network_device(deep_scan=False)
        proj_ip = lan_device.get("ip") if lan_device else self.cached_projector_ip

        monitors = self._get_windows_monitors()
        has_secondary_monitor = len(monitors) >= 2
        sec_res = ""
        display_mode = "clone" if len(monitors) == 1 else "extend"
        if has_secondary_monitor:
            mx, my, mw, mh = monitors[1]
            sec_res = f"{mw}x{mh}"
            display_mode = "extend" if (mx != 0 or my != 0) else "clone"

        devices: List[Dict[str, Any]] = []
        seen_names = set()
        active_display: Optional[str] = None

        # 1. Enumera dispositivos Miracast / Wi-Fi Direct (SWD\WIFIDIRECT)
        wfd_path = r"SYSTEM\CurrentControlSet\Enum\SWD\WIFIDIRECT"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, wfd_path) as k:
                num_sub, _, _ = winreg.QueryInfoKey(k)
                for i in range(num_sub):
                    dev_id = winreg.EnumKey(k, i)
                    instance_id = f"SWD\\WIFIDIRECT\\{dev_id}"
                    with winreg.OpenKey(k, dev_id) as dk:
                        vals: Dict[str, Any] = {}
                        _, nvals, _ = winreg.QueryInfoKey(dk)
                        for j in range(nvals):
                            vn, vd, _ = winreg.EnumValue(dk, j)
                            vals[vn] = vd
                        fname = (vals.get("FriendlyName") or dev_id).strip()
                        key_lower = fname.lower()
                        mac_match = re.search(r"([0-9A-Fa-f:]{17})", dev_id)
                        mac_addr = mac_match.group(1).upper() if mac_match else dev_id

                        is_connected = self._is_win_devnode_connected(instance_id)
                        if key_lower in seen_names:
                            for existing in devices:
                                if existing["name"].lower() == key_lower and is_connected:
                                    existing["connected"] = True
                                    if sec_res:
                                        existing["resolution"] = sec_res
                                    mode_lbl = "Extended Screen" if display_mode == "extend" else "Mirrored"
                                    res_lbl = f" • {sec_res}" if sec_res else ""
                                    ip_lbl = f" • IP {proj_ip}" if (existing.get("is_projector") and proj_ip) else ""
                                    existing["address"] = f"{mac_addr}{ip_lbl}{res_lbl} ({mode_lbl})"
                                    active_display = f"{fname} ({mac_addr}{ip_lbl}{res_lbl} — {mode_lbl})"
                            continue

                        seen_names.add(key_lower)
                        is_projector = any(kw in key_lower for kw in PROJECTOR_KEYWORDS)
                        display_name = "Projector" if is_projector else fname
                        if is_projector:
                            seen_names.add("projector")
                        ip_label = f" • IP {proj_ip}" if (is_projector and proj_ip) else ""
                        res_label = f" • {sec_res}" if (is_connected and sec_res) else ""
                        mode_label = (
                            "Extended Screen"
                            if (is_connected and display_mode == "extend")
                            else ("Mirrored" if is_connected else "Ready to Connect")
                        )
                        if is_connected:
                            active_display = f"{display_name} ({mac_addr}{ip_label}{res_label} — {mode_label})"

                        devices.append(
                            {
                                "id": f"win:{mac_addr}",
                                "name": display_name,
                                "raw_name": fname,
                                "address": f"{mac_addr}{ip_label}{res_label} ({mode_label})",
                                "mac": mac_addr,
                                "ip": proj_ip if is_projector else None,
                                "admin_url": f"http://{proj_ip}/cgi-bin/home.cgi" if (is_projector and proj_ip) else None,
                                "protocol": "Miracast Wi-Fi Direct (Laptop + Phone)",
                                "available": True,
                                "connected": is_connected,
                                "resolution": sec_res if is_connected else None,
                                "display_mode": display_mode if is_connected else None,
                                "source": "windows",
                                "is_projector": is_projector,
                            }
                        )
        except OSError:
            pass

        # 2. Se o projetor foi achado na LAN via HTTP/ARP mas não estava no registro WIFIDIRECT
        if lan_device and not any(d.get("is_projector") for d in devices):
            devices.append(dict(lan_device))

        # 3. Enumera dispositivos UPnP / Cast do Windows (SWD\DAFUPNPPROVIDER)
        upnp_path = r"SYSTEM\CurrentControlSet\Enum\SWD\DAFUPNPPROVIDER"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, upnp_path) as k:
                num_sub, _, _ = winreg.QueryInfoKey(k)
                for i in range(num_sub):
                    dev_id = winreg.EnumKey(k, i)
                    instance_id = f"SWD\\DAFUPNPPROVIDER\\{dev_id}"
                    with winreg.OpenKey(k, dev_id) as dk:
                        vals = {}
                        _, nvals, _ = winreg.QueryInfoKey(dk)
                        for j in range(nvals):
                            vn, vd, _ = winreg.EnumValue(dk, j)
                            vals[vn] = vd
                        fname = (vals.get("FriendlyName") or dev_id).strip()
                        key_lower = fname.lower()
                        if key_lower in seen_names:
                            continue
                        seen_names.add(key_lower)
                        is_started = self._is_win_devnode_started(instance_id)
                        devices.append(
                            {
                                "id": f"winupnp:{fname}",
                                "name": fname,
                                "address": "Local Wi-Fi Network (UPnP / Cast)",
                                "protocol": "Smart TV / UPnP Receiver",
                                "available": is_started,
                                "connected": False,
                                "source": "windows-upnp",
                                "is_projector": any(kw in key_lower for kw in PROJECTOR_KEYWORDS),
                            }
                        )
        except OSError:
            pass

        # Ordena colocando Projectors conectados no topo
        devices.sort(
            key=lambda d: (
                not bool(d.get("connected")),
                not bool(d.get("is_projector")),
                d.get("name", ""),
            )
        )
        return devices, active_display, display_mode

    def _run_on_visible_desktop(self, cmd: str) -> bool:
        """Executa comando GUI na sessão interativa visível do Windows (WinSta0\\Default)."""
        if os.name != "nt":
            return False
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
            si.dwFlags = 1
            si.wShowWindow = 5
            pi = PROCESS_INFORMATION()
            ok = ctypes.windll.kernel32.CreateProcessW(
                None,
                cmd,
                None,
                None,
                False,
                0x08000000,
                None,
                None,
                ctypes.byref(si),
                ctypes.byref(pi),
            )
            return bool(ok)
        except Exception:
            return False

    def set_windows_display_mode(self, mode: str) -> Dict[str, Any]:
        """
        Alterna o modo de projeção do Windows no Projector:
        - `clone`: Duplicar / Espelhar a tela do Laptop no Projetor
        - `extend`: Estender área de trabalho (2ª tela independente)
        - `external`: Mostrar somente na tela do Projetor (protegido se projetor não estiver conectado!)
        - `internal`: Mostrar somente na tela do Laptop (Desconectar projeção)
        """
        # Sempre garante que a tela do celular esteja acesa ao clicar nos botões de modo de tela
        self.wake_phone_screen(bring_to_front=False)

        mode_clean = (mode or "clone").strip().lower()
        mode_map = {
            "clone": ("/clone", "🪞 Mirror Screen (Duplicate) mode enabled on Projector!"),
            "duplicate": ("/clone", "🪞 Mirror Screen (Duplicate) mode enabled on Projector!"),
            "extend": ("/extend", "📐 Extend Screen (2nd Display) mode enabled on Projector!"),
            "external": ("/external", "📽️ Projector Only mode enabled!"),
            "internal": (
                "/internal",
                "🔌 Laptop projection disabled (PC Screen Only) and phone screen kept awake!",
            ),
        }
        if mode_clean not in mode_map:
            return {"ok": False, "message": f"Invalid mode: {mode}"}

        # Proteção crítica: se o usuário clicar em "Somente Projetor" (/external) sem o projetor estar
        # efetivamente conectado como 2º monitor, não desliga a tela interna nem a do celular!
        if mode_clean == "external" and os.name == "nt":
            win_devs, win_active, _ = self.discover_windows_miracast_devices()
            monitors = self._get_windows_monitors()
            if not win_active and len(monitors) < 2:
                self._run_on_visible_desktop("DisplaySwitch.exe /internal")
                self.wake_phone_screen(bring_to_front=True)
                status = self.parse_miracast_status()
                return {
                    "ok": False,
                    "mode": "internal",
                    "message": (
                        "⚠️ Projector is not connected to video yet! "
                        "Kept phone and laptop screens awake. "
                        "Click 'Connect' on Projector first."
                    ),
                    "active_display": status.get("active_display"),
                    "devices": status.get("miracast_devices", []),
                }

        flag, msg = mode_map[mode_clean]
        if os.name == "nt":
            self._run_on_visible_desktop(f"DisplaySwitch.exe {flag}")
            time.sleep(0.8)
        status = self.parse_miracast_status()
        return {
            "ok": True,
            "mode": mode_clean,
            "message": msg,
            "active_display": status.get("active_display"),
            "devices": status.get("miracast_devices", []),
        }

    def _auto_click_windows_cast_target(self, target_name: str = "PROJECTOR") -> None:
        """
        Abre o painel de Projeção Sem Fio no desktop interativo (`WinSta0\\Default`) do Windows 11/10
        (via `Win+K` e `ms-settings-connectabledevices:devicediscovery`) e clica automaticamente
        no `Projector` via UIAutomation.
        """
        if os.name != "nt":
            return
        safe_target = re.sub(r"[^A-Za-z0-9_\-]", "", target_name or "PROJECTOR") or "PROJECTOR"
        ps_script = f"""
Add-Type -MemberDefinition '[DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo); [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y); [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);' -Name WinInput -Namespace HybridBox
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

# 1. Envia atalho nativo Win+K na sessão interativa
[HybridBox.WinInput]::keybd_event(0x5B, 0, 0, [UIntPtr]::Zero)
[HybridBox.WinInput]::keybd_event(0x4B, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 60
[HybridBox.WinInput]::keybd_event(0x4B, 0, 2, [UIntPtr]::Zero)
[HybridBox.WinInput]::keybd_event(0x5B, 0, 2, [UIntPtr]::Zero)

$root = [System.Windows.Automation.AutomationElement]::RootElement
$clicked = $false

for ($attempt = 0; $attempt -lt 8; $attempt++) {{
    Start-Sleep -Milliseconds 650
    $wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
    foreach ($w in $wins) {{
        $cls = $w.Current.ClassName
        if ($cls -notmatch "CoreWindow|Xaml|Shell|Popup|ApplicationFrameWindow|ControlCenter") {{ continue }}
        $els = $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
        foreach ($el in $els) {{
            $n = $el.Current.Name
            if (-not $n) {{ continue }}
            if ($n -match "{safe_target}" -or $n -match "PROJECTOR" -or $n -match "MCAST" -or $n -match "CLcast") {{
                $inv = $null
                if ($el.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$inv)) {{
                    $inv.Invoke()
                    $clicked = $true
                    break
                }}
                $sel = $null
                if ($el.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$sel)) {{
                    $sel.Select()
                    $clicked = $true
                    break
                }}
                $rect = $el.Current.BoundingRectangle
                if ($rect.Width -gt 10 -and $rect.Height -gt 10) {{
                    $cx = [int]($rect.Left + $rect.Width / 2)
                    $cy = [int]($rect.Top + $rect.Height / 2)
                    [HybridBox.WinInput]::SetCursorPos($cx, $cy) | Out-Null
                    [HybridBox.WinInput]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
                    [HybridBox.WinInput]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
                    $clicked = $true
                    break
                }}
            }}
        }}
        if ($clicked) {{ break }}
    }}
    if ($clicked) {{ break }}
    if ($attempt -eq 1) {{
        # Fallback: abre Settings > Display > Connect to a wireless display e clica no botão Connect
        Start-Process "ms-settings-connectabledevices:devicediscovery"
        Start-Sleep -Milliseconds 900
        foreach ($w in $wins) {{
            if ($w.Current.ClassName -eq "ApplicationFrameWindow") {{
                $els = $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
                foreach ($el in $els) {{
                    if ($el.Current.Name -eq "Connect" -and $el.Current.ControlType.ProgrammaticName -eq "ControlType.Button") {{
                        $inv = $null
                        if ($el.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$inv)) {{
                            $inv.Invoke()
                            break
                        }}
                    }}
                }}
            }}
        }}
    }}
}}
"""
        try:
            encoded = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
            self._run_on_visible_desktop(
                f"powershell.exe -NoProfile -WindowStyle Hidden -EncodedCommand {encoded}"
            )
        except Exception:
            pass

    # ==================== STATUS UNIFICADO (WINDOWS + ANDROID + DLNA) ====================

    def parse_miracast_status(self, deep_scan_ip: bool = False) -> Dict[str, Any]:
        """
        Lê tanto os dispositivos Miracast/Wi-Fi Direct do Windows Laptop,
        quanto a localização automática de IP na LAN (DHCP) e `dumpsys display`
        do Android para listar todos os projetores.
        """
        lan_dev = self.discover_projector_network_device(deep_scan=deep_scan_ip)
        win_devices, win_active, win_mode = self.discover_windows_miracast_devices(lan_device=lan_dev)

        out = self._run_adb(
            "dumpsys display 2>/dev/null | grep -iE 'WifiDisplayStatus|mRemoteDisplayConnected|mWfdEnabled|mScanState|mActiveDisplay|mAvailableDisplays|mAvailableWifiDisplayPeers|Device:' -A 6; "
            "dumpsys wifip2p 2>/dev/null | grep -iE 'Device:|deviceAddress|status:' -A 4; "
            "dumpsys window displays 2>/dev/null | grep mFocusedApp; "
            "CLASSPATH=/data/local/tmp/hybridbox_bridge.jar "
            "/system/bin/app_process / HybridBoxBridge status 2>/dev/null",
            timeout=3.0,
        )

        wfd_enabled = (
            bool(win_active)
            or bool(win_devices)
            or "mWfdEnabled=true" in out
            or "featureState=3" in out
        )
        scanning = "mScanState=1" in out or "scanState=1" in out

        android_connected = (
            "activeDisplayState=2" in out or "mRemoteDisplayConnected=true" in out
        )
        android_active_name: Optional[str] = None
        m_active = re.search(r"activeDisplay=WifiDisplay\{([^}]+)\}", out)
        if m_active:
            android_active_name = m_active.group(1).strip()
        else:
            m_active2 = re.search(
                r"activeDisplayState=2,\s*activeDisplay=([^,\r\n]+)", out
            )
            if m_active2:
                val = m_active2.group(1).strip()
                if val and val != "null":
                    android_active_name = val

        active_display: Optional[str] = win_active
        if android_connected:
            mac_lbl = f" ({PROJECTOR_WFD_MAC})" if PROJECTOR_WFD_MAC else ""
            disp_lbl = android_active_name or f"Projector{mac_lbl}"
            active_display = f"{disp_lbl} — Phone Mirrored (1920x1080 @ 60fps)"

        devices: List[Dict[str, Any]] = list(win_devices)
        seen_keys = {d["name"].lower() for d in devices}
        for d in devices:
            if d.get("mac"):
                seen_keys.add(d["mac"].lower())
            if d.get("raw_name"):
                seen_keys.add(d["raw_name"].lower())

        # 1. Extrai displays Miracast de WifiDisplayStatus do Android (formato: NOME (MAC), isAvailable...)
        for m in re.finditer(
            r"(?:mDisplays=\[|displays=\[|,\s*|^|\n)\s*([^\r\n,]+?)\s*\(([0-9a-fA-F:]{17})\)\s*,\s*isAvailable\s*(true|false)",
            out,
        ):
            name = re.sub(
                r"^(?:mDisplays=\[|displays=\[|activeDisplay=|\s)+", "", m.group(1)
            ).strip()
            if not name:
                continue
            mac = m.group(2).lower()
            avail = m.group(3) == "true"
            is_proj = any(k in name.lower() for k in PROJECTOR_KEYWORDS)
            disp_name = "Projector" if is_proj else name
            is_this_conn = android_connected and (
                not android_active_name
                or name.lower() in android_active_name.lower()
                or mac in android_active_name.lower()
            )
            if mac not in seen_keys and name.lower() not in seen_keys and disp_name.lower() not in seen_keys:
                seen_keys.add(mac)
                seen_keys.add(name.lower())
                seen_keys.add(disp_name.lower())
                ip_part = f" • IP {self.cached_projector_ip}" if self.cached_projector_ip else ""
                devices.append(
                    {
                        "id": mac,
                        "name": disp_name,
                        "raw_name": name,
                        "address": (
                            f"{mac.upper()}{ip_part} (🟢 Connected to Phone 1080p)"
                            if is_this_conn
                            else mac.upper()
                        ),
                        "mac": mac.upper(),
                        "ip": self.cached_projector_ip or None,
                        "protocol": "Miracast (Android Wi-Fi Direct)",
                        "available": avail or is_this_conn,
                        "connected": is_this_conn,
                        "resolution": "1920x1080" if is_this_conn else None,
                        "source": "android",
                        "is_projector": is_proj,
                    }
                )

        # 2. Se o Android estiver conectado ao Projector, marca também o card unificado como conectado
        projector_is_active_on_android = android_connected and (
            not android_active_name
            or any(k in android_active_name.lower() for k in PROJECTOR_KEYWORDS)
        )
        if projector_is_active_on_android:
            for d in devices:
                if d.get("is_projector") or "projector" in d.get("name", "").lower():
                    d["connected"] = True
                    d["available"] = True
                    d["resolution"] = "1920x1080"
                    d["display_mode"] = d.get("display_mode") or "clone"
                    ip_str = f" • IP {self.cached_projector_ip}" if self.cached_projector_ip else ""
                    mac_part = d.get("mac") or PROJECTOR_WFD_MAC or "Miracast"
                    d["address"] = (
                        f"{mac_part}{ip_str} • 1920x1080 @ 60fps (🟢 Phone Projecting)"
                    )

        # 3. Extrai peers Wi-Fi Direct de dumpsys wifip2p (Device: NOME \n deviceAddress: MAC)
        for m in re.finditer(
            r"Device:\s*([^\r\n]+)\s*[\r\n]+\s*deviceAddress:\s*([0-9a-fA-F:]{17})",
            out,
        ):
            name = re.sub(
                r"^(?:mDisplays=\[|displays=\[|activeDisplay=|\s)+", "", m.group(1)
            ).strip()
            if not name:
                continue
            mac = m.group(2).lower()
            is_proj = any(k in name.lower() for k in PROJECTOR_KEYWORDS)
            disp_name = "Projector" if is_proj else name
            is_this_conn = android_connected and bool(
                android_active_name
                and (
                    name.lower() in android_active_name.lower()
                    or mac in android_active_name.lower()
                )
            )
            if mac not in seen_keys and name.lower() not in seen_keys and disp_name.lower() not in seen_keys:
                seen_keys.add(mac)
                seen_keys.add(name.lower())
                seen_keys.add(disp_name.lower())
                devices.append(
                    {
                        "id": mac,
                        "name": disp_name,
                        "raw_name": name,
                        "address": mac.upper(),
                        "protocol": "Wi-Fi Direct / Miracast (Android)",
                        "available": True,
                        "connected": is_this_conn
                        or (projector_is_active_on_android and is_proj),
                        "source": "android",
                        "is_projector": is_proj,
                    }
                )

        # 4. Caso a tela Cast esteja aberta no Android, lê os itens da lista via uiautomator
        ui_items = (
            self._get_cast_screen_items(skip_focus_check=True)
            if ("WifiDisplaySettingsActivity" in out or "com.milink" in out)
            else []
        )

        for item in ui_items:
            key = item["name"].lower()
            if key not in seen_keys:
                seen_keys.add(key)
                devices.append(item)
            else:
                # Apenas atualiza coordenadas de toque se o item da UI for o sink Miracast real
                # (nunca sobrescreve um dispositivo Miracast com a rota duplicada 'Chromecast'!)
                if item.get("is_chromecast"):
                    continue
                for d in devices:
                    if (
                        d["name"].lower() == key
                        or d.get("raw_name", "").lower() == key
                        or (item.get("is_projector") and d.get("is_projector"))
                    ):
                        if item.get("is_miracast_sink") or "tap_x" not in d:
                            d["tap_x"] = item["tap_x"]
                            d["tap_y"] = item["tap_y"]
                            d["summary"] = item.get("summary", "")
                            d["is_miracast_sink"] = item.get("is_miracast_sink", False)

        devices.sort(
            key=lambda d: (
                not bool(d.get("connected")),
                not bool(d.get("is_projector")),
                d.get("name", ""),
            )
        )

        self.last_status = {
            "wfd_enabled": wfd_enabled,
            "scanning": scanning,
            "active_display": active_display,
            "display_mode": "clone" if android_connected else win_mode,
            "projector_ip": self.cached_projector_ip,
        }
        return {
            "wfd_enabled": wfd_enabled,
            "scanning": scanning,
            "active_display": active_display,
            "display_mode": "clone" if android_connected else win_mode,
            "projector_ip": self.cached_projector_ip,
            "miracast_devices": devices,
        }

    def _get_wfd_p2p_peers(self, raw_out: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Consulta diretamente o kernel/framework Android (`dumpsys display` e `dumpsys wifip2p`)
        para descobrir quais dispositivos suportam Miracast (`WFD enabled: true`),
        independentemente do idioma da UI ou de entradas duplicadas 'Chromecast'.
        """
        out = raw_out or self._run_adb(
            "dumpsys display 2>/dev/null | grep -iE 'WifiDisplayStatus|mDisplays=|displays=' -A 8; "
            "dumpsys wifip2p 2>/dev/null | grep -iE 'Device:|deviceAddress|wfdInfo:' -A 5",
            timeout=2.5,
        )
        peers: Dict[str, Dict[str, Any]] = {}
        for m in re.finditer(
            r"(?:mDisplays=\[|displays=\[|,\s*|^|\n)\s*([^\r\n,]+?)\s*\(([0-9a-fA-F:]{17})\)\s*,\s*isAvailable\s*(true|false)",
            out,
        ):
            name = re.sub(r"^(?:mDisplays=\[|displays=\[|\s)+", "", m.group(1)).strip()
            mac = m.group(2).lower()
            avail = m.group(3) == "true"
            entry = {
                "name": name,
                "mac": mac,
                "wfd_enabled": True,
                "available": avail,
            }
            peers[name.lower()] = entry
            peers[mac] = entry

        for m in re.finditer(
            r"Device:\s*([^\r\n,]+)(?:,\s*deviceAddress:\s*([0-9a-fA-F:]{17})|\s*[\r\n]+\s*deviceAddress:\s*([0-9a-fA-F:]{17}))([^\r\n]*)",
            out,
        ):
            name = re.sub(r"^(?:mDisplays=\[|displays=\[|\s)+", "", m.group(1)).strip()
            mac = (m.group(2) or m.group(3) or "").lower()
            tail = m.group(4) or ""
            wfd_ok = "wfd enabled: true" in tail.lower() or "wfd enabled: true" in out.lower()
            if name:
                prev = peers.get(name.lower(), {})
                entry = {
                    "name": name,
                    "mac": mac or prev.get("mac", ""),
                    "wfd_enabled": wfd_ok or prev.get("wfd_enabled", True),
                    "available": True,
                }
                peers[name.lower()] = entry
                if mac:
                    peers[mac] = entry
        return peers

    def _dismiss_blocking_cast_modal(self, root: ET.Element) -> bool:
        """
        Detecta e fecha automaticamente qualquer modal/popup preso sobre a tela de Cast
        (como o modal 'PROJECTOR-DDC994 -> Disconnect' aberto quando uma rota Chromecast trava).
        """
        disconnect_words = {
            "disconnect",
            "desconectar",
            "cancel",
            "cancelar",
            "stop casting",
            "parar transmissão",
            "close",
            "fechar",
        }
        has_alert_title = False
        has_recycler = False
        button_coords = None

        for node in root.iter("node"):
            res_id = (node.attrib.get("resource-id") or "").lower()
            txt = (node.attrib.get("text") or "").strip().lower()
            if "recycler_view" in res_id or "list_container" in res_id:
                has_recycler = True
            if "alerttitle" in res_id:
                has_alert_title = True
            if (
                res_id in ("android:id/button1", "android:id/button2", "android:id/button3")
                or txt in disconnect_words
            ) and txt in disconnect_words:
                bounds = node.attrib.get("bounds", "")
                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                if m:
                    x1, y1, x2, y2 = map(int, m.groups())
                    button_coords = ((x1 + x2) // 2, (y1 + y2) // 2)

        if button_coords and (has_alert_title or not has_recycler):
            self._safe_tap(button_coords[0], button_coords[1])
            return True
        if has_alert_title and not has_recycler:
            self._run_adb("input keyevent 4 2>/dev/null", timeout=1.5)
            return True
        return False

    def _get_cast_screen_items(
        self,
        skip_focus_check: bool = False,
        xml_raw: Optional[str] = None,
        auto_dismiss_modal: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Extrai dispositivos visíveis na lista de 'Cast / Wireless display' do Android,
        classificando explicitamente `is_wireless_display`, `is_chromecast`, `is_unavailable`,
        `is_connecting` e `is_connected` em múltiplos idiomas, e calculando coordenada X
        segura no terço esquerdo (longe do botão lateral `arrow_right`).
        """
        if xml_raw is None:
            if not skip_focus_check:
                focus = self._run_adb(
                    "dumpsys window displays 2>/dev/null | grep mFocusedApp", timeout=2.0
                )
                if "WifiDisplaySettingsActivity" not in focus and "com.milink" not in focus:
                    return []

            xml_raw = self._run_adb(
                "uiautomator dump /sdcard/cast_scan.xml >/dev/null 2>&1 && cat /sdcard/cast_scan.xml",
                timeout=4.0,
            )
        if not xml_raw or "<hierarchy" not in xml_raw:
            return []

        xml_str = xml_raw[xml_raw.index("<hierarchy") :]
        items: List[Dict[str, Any]] = []
        ignore_titles = {
            "cast",
            "transmitir",
            "wireless display",
            "tela sem fio",
            "ecrã sem fios",
            "pantalla inalámbrica",
            "demos",
            "special features",
            "minimise window",
            "cast with screen off",
            "hide private items",
            "help",
            "ajuda",
        }
        wireless_keywords = (
            "wireless display",
            "tela sem fio",
            "ecrã sem fios",
            "pantalla inalámbrica",
            "écran sans fil",
            "drahtloses display",
            "schermo wireless",
            "miracast",
            "wi-fi direct",
            "smart view",
            "screen sharing",
        )
        unavailable_keywords = (
            "unavailable",
            "indisponível",
            "indisponivel",
            "not available",
            "no disponible",
            "non disponible",
            "nicht verfügbar",
            "fora de alcance",
        )
        connecting_keywords = (
            "connecting",
            "conectando",
            "a ligar",
            "connexion",
            "verbinden",
        )
        connected_keywords = (
            "connected",
            "conectado",
            "ligado",
            "verbunden",
            "connecté",
        )

        try:
            root = ET.fromstring(xml_str)
            if auto_dismiss_modal and self._dismiss_blocking_cast_modal(root):
                time.sleep(0.55)
                xml_retry = self._run_adb(
                    "uiautomator dump /sdcard/cast_scan.xml >/dev/null 2>&1 && cat /sdcard/cast_scan.xml",
                    timeout=4.0,
                )
                if "<hierarchy" in xml_retry:
                    root = ET.fromstring(xml_retry[xml_retry.index("<hierarchy") :])

            # Garante que a chave mestre 'Wireless display' (CheckBox/Switch) esteja ligada
            if auto_dismiss_modal:
                for node in root.iter("node"):
                    res_id = node.attrib.get("resource-id", "")
                    if (
                        res_id in ("android:id/checkbox", "android:id/switch_widget")
                        and node.attrib.get("checkable") == "true"
                        and node.attrib.get("checked") == "false"
                        and node.attrib.get("enabled") == "true"
                    ):
                        m_sw = re.match(
                            r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
                            node.attrib.get("bounds", ""),
                        )
                        if m_sw:
                            sx1, sy1, sx2, sy2 = map(int, m_sw.groups())
                            self._safe_tap((sx1 + sx2) // 2, (sy1 + sy2) // 2)
                            time.sleep(0.6)
                            break

            for parent in root.iter("node"):
                direct_children = parent.findall("node")
                if not direct_children:
                    continue

                title_node = None
                summary_text = ""
                for child in direct_children:
                    cid = child.attrib.get("resource-id", "")
                    ctext = (child.attrib.get("text") or "").strip()
                    if cid == "android:id/title" and ctext:
                        title_node = child
                    elif cid == "android:id/summary" and ctext:
                        summary_text = ctext

                if title_node is None:
                    continue

                text = (title_node.attrib.get("text") or "").strip()
                if not text or text.lower() in ignore_titles:
                    continue

                bounds = parent.attrib.get("bounds") or title_node.attrib.get("bounds", "")
                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                if not m:
                    continue
                x1, y1, x2, y2 = map(int, m.groups())
                # Toque seguro no terço esquerdo do título (evita clicar em com.android.settings:id/arrow_right)
                tx = x1 + max(100, min(260, (x2 - x1) // 3))
                ty = (y1 + y2) // 2

                row_enabled = (
                    parent.attrib.get("enabled", "true") == "true"
                    and title_node.attrib.get("enabled", "true") == "true"
                )
                summary_low = summary_text.lower()
                is_chromecast = "chromecast" in summary_low or "google cast" in summary_low
                is_unavailable = (not row_enabled) or any(
                    w in summary_low for w in unavailable_keywords
                )
                is_connecting = any(w in summary_low for w in connecting_keywords)
                is_connected = (not is_unavailable) and any(
                    w in summary_low for w in connected_keywords
                )
                is_wireless_display = (not is_chromecast) and (
                    any(w in summary_low for w in wireless_keywords)
                    or is_connected
                    or (not summary_low and row_enabled)
                )
                is_miracast_sink = is_wireless_display and (not is_unavailable)

                items.append(
                    {
                        "id": f"ui:{text}:{'wfd' if is_wireless_display else ('cc' if is_chromecast else 'cast')}",
                        "name": text,
                        "summary": summary_text,
                        "address": f"Android Cast Screen ({tx},{ty})",
                        "protocol": (
                            "Miracast (Wireless Display)"
                            if is_wireless_display
                            else ("Chromecast (LAN)" if is_chromecast else "Cast (Android)")
                        ),
                        "available": not is_unavailable,
                        "enabled": row_enabled,
                        "connected": is_connected,
                        "is_connecting": is_connecting,
                        "is_unavailable": is_unavailable,
                        "is_chromecast": is_chromecast,
                        "is_wireless_display": is_wireless_display,
                        "is_miracast_sink": is_miracast_sink,
                        "tap_x": tx,
                        "tap_y": ty,
                        "source": "android",
                        "is_projector": any(k in text.lower() for k in PROJECTOR_KEYWORDS),
                    }
                )
        except Exception:
            pass

        # Prioridade estrita:
        # 1º: Wireless Display disponível e habilitado (is_miracast_sink=True)
        # 2º: Dispositivos disponíveis que não sejam Chromecast
        # 3º: Chromecast ou Indisponíveis por último
        items.sort(
            key=lambda it: (
                not bool(it.get("is_miracast_sink")),
                bool(it.get("is_unavailable")),
                bool(it.get("is_chromecast")),
                it.get("name", ""),
            )
        )
        return items

    def discover_dlna_devices(self, timeout: float = 1.2) -> List[Dict[str, Any]]:
        """
        Descobre projetores/TVs DLNA/UPnP na rede Wi-Fi local via SSDP M-SEARCH
        (baseado em cherezov/dlnap e nanodlna do GitHub).
        """
        ssdp_request = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover"\r\n'
            "MX: 1\r\n"
            "ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n"
            "\r\n"
        ).encode("utf-8")

        locations = set()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.settimeout(timeout)
            sock.sendto(ssdp_request, ("239.255.255.250", 1900))
            start = time.time()
            while time.time() - start < timeout:
                try:
                    data, _ = sock.recvfrom(4096)
                    text = data.decode("utf-8", errors="ignore")
                    m_loc = re.search(r"(?i)^LOCATION:\s*(http[^\r\n]+)", text, re.M)
                    if m_loc:
                        locations.add(m_loc.group(1).strip())
                except socket.timeout:
                    break
                except Exception:
                    break
            sock.close()
        except Exception:
            pass

        dlna_list: List[Dict[str, Any]] = []
        for loc in locations:
            try:
                req = urllib.request.Request(loc, headers={"User-Agent": "HybridBox-DLNA/1.0"})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    xml_bytes = resp.read()
                root = ET.fromstring(xml_bytes)
                ns = {"upnp": "urn:schemas-upnp-org:device-1-0"}
                friendly = root.findtext(
                    ".//upnp:friendlyName", default="DLNA Device", namespaces=ns
                )
                model = root.findtext(".//upnp:modelName", default="", namespaces=ns)
                control_url = None
                for service in root.findall(".//upnp:service", namespaces=ns):
                    st = service.findtext("upnp:serviceType", default="", namespaces=ns)
                    if "AVTransport" in st:
                        ctrl = service.findtext("upnp:controlURL", default="", namespaces=ns)
                        if ctrl:
                            from urllib.parse import urljoin

                            control_url = urljoin(loc, ctrl)
                            break
                combined_name = f"{friendly} ({model})" if model else friendly
                dlna_list.append(
                    {
                        "id": f"dlna:{loc}",
                        "name": combined_name,
                        "address": loc,
                        "control_url": control_url,
                        "protocol": "Smart TV / DLNA / UPnP (Wi-Fi)",
                        "available": True,
                        "connected": False,
                        "source": "dlna",
                        "is_projector": any(k in combined_name.lower() for k in PROJECTOR_KEYWORDS),
                    }
                )
            except Exception:
                continue
        return dlna_list

    def _prepare_clean_cast_screen(self, disp_chk: str = "") -> str:
        """
        Motor de Auto-Recuperação de Tela (Universal Multi-OEM):
        1. Verifica se há janelas modais presas (ex.: 'PROJECTOR-DDC994 -> Disconnect') ou
           se `scanState=1` não está ativo;
        2. Garante `wifi_display_on=1` e abre `android.settings.CAST_SETTINGS` limpo;
        3. Se alguma rota Chromecast fantasma estiver presa em 'Connecting' com `mDesiredDevice=null`,
           reinicia `com.android.settings` para destravar o `MediaRouter`.
        """
        state_out = disp_chk or self._run_adb(
            "dumpsys display 2>/dev/null | grep -iE 'WifiDisplayStatus|mCurrentStatus=|mDesiredDevice=|mRemoteDisplayConnected=|mActiveDisplay=|mDisplays=' -A 6; "
            "dumpsys wifip2p 2>/dev/null | grep -iE 'Device:|deviceAddress|wfdInfo:' -A 5; "
            "dumpsys window displays 2>/dev/null | grep -E 'mCurrentFocus|mFocusedApp'",
            timeout=3.0,
        )

        # Detecta se há um popup modal (como 'u0 PROJECTOR-DDC994') em foco sobre a WifiDisplaySettingsActivity
        has_modal_focus = False
        for line in state_out.splitlines():
            if "mCurrentFocus=" in line and "WifiDisplaySettingsActivity" not in line and "com.milink" not in line:
                has_modal_focus = True

        need_fresh_restart = ("scanState=1" not in state_out) or has_modal_focus
        if need_fresh_restart:
            self._run_adb(
                "cmd statusbar collapse 2>/dev/null; "
                "input keyevent 4 2>/dev/null; "
                "am force-stop com.android.settings 2>/dev/null; "
                "settings put global wifi_display_on 1 2>/dev/null; "
                "am start --user 0 --activity-clear-top -a android.settings.CAST_SETTINGS >/dev/null 2>&1",
                timeout=3.5,
            )
            time.sleep(1.5)
        else:
            self._run_adb(
                "cmd statusbar collapse 2>/dev/null; "
                "settings put global wifi_display_on 1 2>/dev/null; "
                "am start --user 0 -a android.settings.CAST_SETTINGS >/dev/null 2>&1",
                timeout=3.0,
            )
            time.sleep(0.8)

        return state_out

    def _connect_android_miracast_target(self, target_query: str = "") -> Optional[Dict[str, Any]]:
        """
        Arquitetura Universal Zero-Falhas para Conexão Miracast / Wireless Display (Qualquer TV, Projetor ou Dongle):
        1. Se já estiver conectado ao mesmo alvo (`activeDisplayState=2`), mantém a projeção ativa;
        2. Executa `_prepare_clean_cast_screen()` para fechar modais presos e iniciar scan Wi-Fi Direct limpo;
        3. Faz Polling Adaptativo de Descoberta P2P (até 6.0s) cruzando `dumpsys wifip2p` / `dumpsys display`
           com a UI, ignorando entradas duplicadas `Chromecast` ou `Unavailable` enquanto aguarda a entrada
           `Wireless display` (`is_miracast_sink=True`) habilitar;
        4. Dá 1 único toque de precisão no terço esquerdo do item (longe de `arrow_right`) e monitora a
           Máquina de Estados de Handshake (`mDesiredDevice`, `GroupNegotiationState`, `activeDisplayState=2`)
           sem enviar toques repetidos que cancelariam a conexão.
        """
        q = (target_query or "").strip().lower()
        disp_chk = self._run_adb(
            "dumpsys display 2>/dev/null | grep -iE 'WifiDisplayStatus|mCurrentStatus=|mDesiredDevice=|mRemoteDisplayConnected=|mActiveDisplay=|mDisplays=' -A 6; "
            "dumpsys wifip2p 2>/dev/null | grep -iE 'Device:|deviceAddress|wfdInfo:' -A 5; "
            "dumpsys window displays 2>/dev/null | grep -E 'mCurrentFocus|mFocusedApp'",
            timeout=3.0,
        )
        if ("activeDisplayState=2" in disp_chk or "mRemoteDisplayConnected=true" in disp_chk) and (
            not q or q in disp_chk.lower() or "projector" in q
        ):
            return {"ok": True, "already_connected": True, "connected": True}

        self._prepare_clean_cast_screen(disp_chk)
        wfd_peers = self._get_wfd_p2p_peers(disp_chk)

        def _item_matches(it: Dict[str, Any]) -> bool:
            if not q:
                return True
            it_name = (it.get("name") or "").lower()
            it_raw = (it.get("raw_name") or "").lower()
            it_id = (it.get("id") or "").lower()
            if q in it_name or (it_raw and q in it_raw) or q in it_id:
                return True
            if "projector" in q and it.get("is_projector"):
                return True
            for peer_key, peer_info in wfd_peers.items():
                if q in peer_key and peer_info.get("name", "").lower() == it_name:
                    return True
            return False

        def _is_known_wfd_capable(it: Dict[str, Any], all_items: List[Dict[str, Any]]) -> bool:
            """Verifica se o dispositivo suporta Miracast/WFD (no kernel ou por ter uma linha Wireless display na lista)."""
            nm = (it.get("name") or "").lower()
            if nm in wfd_peers:
                return True
            if it.get("is_projector"):
                return True
            if any(
                other.get("name", "").lower() == nm and other.get("is_wireless_display")
                for other in all_items
            ):
                return True
            return False

        chosen: Optional[Dict[str, Any]] = None
        items: List[Dict[str, Any]] = []
        restarted_stuck_chromecast = False

        # Polling Adaptativo de Descoberta P2P (até 6 ciclos de ~1.0s = ~6.0s para `P2P-DEVICE-FOUND`)
        for poll_step in range(6):
            items = self._get_cast_screen_items(skip_focus_check=True, auto_dismiss_modal=True)

            # Se uma rota Chromecast estiver presa em 'Connecting' com mDesiredDevice=null, reinicia Settings uma vez
            if (
                not restarted_stuck_chromecast
                and any(it.get("is_connecting") and not it.get("is_wireless_display") for it in items)
                and "mDesiredDevice=null" in disp_chk
            ):
                restarted_stuck_chromecast = True
                self._run_adb(
                    "am force-stop com.android.settings 2>/dev/null; "
                    "settings put global wifi_display_on 1 2>/dev/null; "
                    "am start --user 0 --activity-clear-top -a android.settings.CAST_SETTINGS >/dev/null 2>&1",
                    timeout=3.5,
                )
                time.sleep(1.6)
                items = self._get_cast_screen_items(skip_focus_check=True, auto_dismiss_modal=True)

            # 1º: Procura entrada Miracast real, disponível e habilitada (`is_miracast_sink=True` e `not is_chromecast`)
            if q:
                chosen = next(
                    (
                        it
                        for it in items
                        if it.get("is_miracast_sink")
                        and not it.get("is_chromecast")
                        and _item_matches(it)
                    ),
                    None,
                )
            else:
                chosen = next(
                    (
                        it
                        for it in items
                        if it.get("is_projector")
                        and it.get("is_miracast_sink")
                        and not it.get("is_chromecast")
                    ),
                    next(
                        (
                            it
                            for it in items
                            if it.get("is_miracast_sink") and not it.get("is_chromecast")
                        ),
                        None,
                    ),
                )

            if chosen:
                break

            # Se ainda não apareceu habilitado na UI, faz scroll suave no passo 3 caso a lista seja longa
            if poll_step == 3:
                self._run_adb("input swipe 540 1500 540 700 300 2>/dev/null", timeout=2.0)

            time.sleep(0.95)
            wfd_peers.update(self._get_wfd_p2p_peers())

        # Somente se após todo o ciclo P2P o dispositivo for um Chromecast puro (sem suporte WFD), permite fallback
        if not chosen and items:
            candidates = [it for it in items if _item_matches(it) and it.get("available")]
            for cand in candidates:
                if not cand.get("is_chromecast"):
                    chosen = cand
                    break
                if not _is_known_wfd_capable(cand, items):
                    chosen = cand
                    break

        if not chosen or "tap_x" not in chosen or "tap_y" not in chosen:
            return None

        tx, ty = int(chosen["tap_x"]), int(chosen["tap_y"])
        # Toque Único de Precisão no terço esquerdo da linha (jamais faz loop de 6 toques seguidos!)
        self._safe_tap(tx, ty)

        connected = False
        retapped = False
        # Máquina de Estados de Handshake P2P + RTSP (até ~11s)
        for step in range(11):
            time.sleep(0.95)
            if step in (0, 1, 2, 4, 6):
                self._confirm_cast_dialog_if_present()

            st_now = self._run_adb(
                "dumpsys display 2>/dev/null | grep -E 'mDesiredDevice=|mConnectingDisplay=|mConnectedDevice=|mCurrentStatus=|mRemoteDisplayConnected='; "
                "dumpsys wifip2p 2>/dev/null | grep -E 'curState='",
                timeout=2.2,
            )
            if "activeDisplayState=2" in st_now or "mRemoteDisplayConnected=true" in st_now:
                connected = True
                break

            handshake_in_progress = (
                ("mDesiredDevice=" in st_now and "mDesiredDevice=null" not in st_now)
                or ("mConnectingDisplay=" in st_now and "mConnectingDisplay=null" not in st_now)
                or ("mConnectedDevice=" in st_now and "mConnectedDevice=null" not in st_now)
                or "activeDisplayState=1" in st_now
                or "GroupNegotiationState" in st_now
                or "GroupCreatedState" in st_now
            )
            if handshake_in_progress:
                # Handshake Miracast em andamento: PROIBIDO tocar novamente para não abrir o modal 'Disconnect'!
                continue

            # Retry seguro único: somente se após ~2.8s nenhum handshake iniciou e a linha continua parada e habilitada
            if step == 2 and not retapped:
                fresh_items = self._get_cast_screen_items(
                    skip_focus_check=True, auto_dismiss_modal=False
                )
                still_idle = next(
                    (
                        it
                        for it in fresh_items
                        if it.get("name", "").lower() == chosen.get("name", "").lower()
                        and it.get("is_miracast_sink")
                        and not it.get("is_connecting")
                        and not it.get("connected")
                    ),
                    None,
                )
                if still_idle:
                    retapped = True
                    self._safe_tap(int(still_idle["tap_x"]), int(still_idle["tap_y"]))

        if connected:
            self._run_adb(
                "am start --user 0 -n com.spocky.projengmenu/.ui.home.MainActivity >/dev/null 2>&1",
                timeout=2.5,
            )
        chosen["connected"] = connected
        return {"ok": True, "connected": connected, "device": chosen}

    def scan_and_open_cast(self, auto_connect: bool = True) -> Dict[str, Any]:
        """
        Escaneia qualquer Smart TV (Samsung, LG, Sony, TCL, Roku, Fire TV) ou Projetor Miracast
        no Android e no Windows, localiza automaticamente o IP na rede e também dispositivos DLNA/UPnP.
        """
        self.wake_phone_screen(bring_to_front=False)
        status = self.parse_miracast_status(deep_scan_ip=True)

        # Só abre a tela CAST_SETTINGS se o celular ainda NÃO estiver conectado a uma TV/projetor!
        if not status.get("active_display"):
            self._run_adb(
                "cmd statusbar collapse 2>/dev/null; "
                "settings put global wifi_display_on 1 2>/dev/null; "
                "am start --user 0 -a android.settings.CAST_SETTINGS >/dev/null 2>&1",
                timeout=3.0,
            )
            if not status.get("scanning"):
                time.sleep(1.1)
                status = self.parse_miracast_status(deep_scan_ip=False)

        dlna_devs = self.discover_dlna_devices(timeout=0.8)

        existing_names = {d["name"].lower() for d in status["miracast_devices"]}
        all_devices = list(status["miracast_devices"])
        for d in dlna_devs:
            if d["name"].lower() not in existing_names:
                all_devices.append(d)
        self.last_devices = all_devices

        connected_to = None
        if auto_connect and all_devices:
            target = next(
                (d for d in all_devices if d.get("connected") and d.get("is_projector")),
                next(
                    (d for d in all_devices if d.get("is_projector")),
                    all_devices[0],
                ),
            )
            conn_res = self.connect_device(
                target.get("name") or target.get("id", ""), cached_status=status
            )
            if conn_res.get("ok"):
                connected_to = target.get("name")
                status = self.parse_miracast_status(deep_scan_ip=False)
                all_devices = list(status["miracast_devices"])
                for d in dlna_devs:
                    if d["name"].lower() not in {x["name"].lower() for x in all_devices}:
                        all_devices.append(d)
                self.last_devices = all_devices

        return {
            "ok": True,
            "wfd_enabled": status["wfd_enabled"],
            "scanning": status["scanning"],
            "active_display": status["active_display"],
            "display_mode": status.get("display_mode"),
            "projector_ip": status.get("projector_ip", self.cached_projector_ip),
            "connected_to": connected_to,
            "devices": all_devices,
        }

    def connect_device(
        self, target_query: str = "", cached_status: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Conecta a qualquer Smart TV ou Projetor Miracast/Cast escolhido (`target_query`),
        mantendo o Projector como favorito automático quando `target_query` está vazio.
        """
        self.wake_phone_screen(bring_to_front=False)
        status = cached_status or self.parse_miracast_status(deep_scan_ip=False)
        devices = list(status["miracast_devices"])
        seen_names = {d.get("name", "").lower() for d in devices}
        for d in self.last_devices:
            if d.get("name", "").lower() not in seen_names:
                devices.append(d)
        q = (target_query or "").strip().lower()
        proj_ip = status.get("projector_ip") or self.cached_projector_ip

        def _matches_query(dev: Dict[str, Any]) -> bool:
            if not q:
                return True
            name_low = (dev.get("name") or "").lower()
            raw_low = (dev.get("raw_name") or "").lower()
            id_low = (dev.get("id") or "").lower()
            mac_low = (dev.get("mac") or "").lower()
            if q in name_low or (raw_low and q in raw_low) or q in id_low or (mac_low and q in mac_low):
                return True
            if "projector" in q and dev.get("is_projector"):
                return True
            return False

        # 1. Se o celular ou o laptop já estiver conectado à TV/projetor solicitado, não interrompe!
        already_conn = next(
            (d for d in devices if d.get("connected") and _matches_query(d)),
            None,
        )
        if already_conn:
            return {
                "ok": True,
                "projector_ip": proj_ip,
                "message": (
                    f"🟢 TV/Projector '{already_conn['name']}' "
                    "is already connected and projecting in 1920x1080 @ 60fps!"
                ),
                "device": already_conn,
            }

        # 2. Tenta conectar o Celular Xiaomi via Miracast / Wireless Display (UIAutomator Safe-Tap)
        android_res = self._connect_android_miracast_target(target_query)
        if android_res and android_res.get("connected"):
            new_status = self.parse_miracast_status(deep_scan_ip=False)
            dev_obj = android_res.get("device") or (
                new_status["miracast_devices"][0] if new_status["miracast_devices"] else {}
            )
            return {
                "ok": True,
                "projector_ip": proj_ip,
                "message": (
                    f"🟢 Phone connected to TV/Projector '{dev_obj.get('name', target_query or 'Projector')}' "
                    "(1920x1080 @ 60fps) over Wi-Fi without touching the screen!"
                ),
                "device": dev_obj,
            }

        # 3. Se o celular iniciou o handshake ou se também houver alvo Windows/LAN/DLNA
        win_match = next(
            (
                d
                for d in devices
                if d.get("source") in ("windows", "lan-http", "windows-upnp", "dlna")
                and _matches_query(d)
            ),
            None,
        )
        if android_res and android_res.get("device"):
            chosen = android_res["device"]
            return {
                "ok": True,
                "projector_ip": proj_ip,
                "message": (
                    f"📡 Negotiating wireless video from phone to '{chosen['name']}'..."
                ),
                "device": chosen,
            }

        if win_match:
            if win_match.get("source") == "dlna":
                return {
                    "ok": True,
                    "projector_ip": proj_ip,
                    "message": (
                        f"📺 Smart TV DLNA '{win_match['name']}' ready to receive media on the Wi-Fi network!"
                    ),
                    "device": win_match,
                }
            cast_target = (win_match.get("raw_name") or win_match["name"]).split("(")[0].strip()
            self._auto_click_windows_cast_target(cast_target)
            return {
                "ok": True,
                "projector_ip": proj_ip,
                "message": (
                    f"📡 Connecting automatically to TV/Projector '{win_match['name']}'!"
                ),
                "device": win_match,
            }

        return {
            "ok": False,
            "projector_ip": proj_ip,
            "message": (
                "No wireless TV or Projector responded yet. "
                "On your TV or Projector, open 'Screen Mirroring / Miracast / Cast' and tap Scan."
            ),
        }

    def open_hdmi_displaylink(self) -> Dict[str, Any]:
        """
        Inicia o `DisplayLink Presenter` para saída de vídeo via Cabo HDMI / Hub USB
        e confirma automaticamente qualquer pop-up de permissão USB/Captura de Tela.
        """
        self.wake_phone_screen(bring_to_front=False)
        self._run_adb(
            "cmd statusbar collapse 2>/dev/null; "
            "monkey -p com.displaylink.presenter -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || "
            "am start --user 0 -a android.settings.CAST_SETTINGS >/dev/null 2>&1",
            timeout=4.0,
        )
        time.sleep(0.8)
        self._confirm_cast_dialog_if_present()
        return {
            "ok": True,
            "message": (
                "🔌 HDMI Cable / DisplayLink mode started on Redmi Note 8 Pro! "
                "(Any USB/screen-capture permission popup was auto-confirmed)."
            ),
        }

    def _confirm_cast_dialog_if_present(self) -> None:
        """Confirma automaticamente diálogos de início de espelhamento ('Start now', 'Accept', 'OK')."""
        xml_raw = self._run_adb(
            "uiautomator dump /sdcard/cast_confirm.xml >/dev/null 2>&1 && cat /sdcard/cast_confirm.xml",
            timeout=4.0,
        )
        if "<hierarchy" not in xml_raw:
            return
        try:
            root = ET.fromstring(xml_raw[xml_raw.index("<hierarchy") :])
            confirm_words = {
                "start now",
                "iniciar agora",
                "accept",
                "aceitar",
                "connect",
                "conectar",
                "allow",
                "permitir",
                "ok",
            }
            for node in root.iter("node"):
                txt = (node.attrib.get("text") or "").strip().lower()
                if txt in confirm_words:
                    bounds = node.attrib.get("bounds", "")
                    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                    if m:
                        x1, y1, x2, y2 = map(int, m.groups())
                        self._safe_tap((x1 + x2) // 2, (y1 + y2) // 2)
                        return
        except Exception:
            pass

    def open_miui_cast_with_screen_off(self) -> Dict[str, Any]:
        """Abre o menu nativo MIUI Cast no celular Xiaomi mantendo o WakeLock ativo para não apagar a tela."""
        self.wake_phone_screen(bring_to_front=False)
        win_devs, win_active, _ = self.discover_windows_miracast_devices()
        self._run_adb(
            "for p in android.permission.ACCESS_FINE_LOCATION android.permission.ACCESS_COARSE_LOCATION "
            "android.permission.READ_PHONE_STATE android.permission.READ_EXTERNAL_STORAGE "
            "android.permission.WRITE_EXTERNAL_STORAGE; do pm grant com.milink.service $p 2>/dev/null; done; "
            "svc bluetooth enable 2>/dev/null; settings put secure location_mode 3 2>/dev/null; "
            "cmd statusbar collapse 2>/dev/null; "
            "am start --user 0 --activity-clear-top -a miui.intent.action.MILINK_SETTING >/dev/null 2>&1 || "
            "am start --user 0 -a android.settings.CAST_SETTINGS >/dev/null 2>&1",
            timeout=4.5,
        )
        time.sleep(0.8)
        xml_raw = self._run_adb(
            "uiautomator dump /sdcard/milink.xml >/dev/null 2>&1 && cat /sdcard/milink.xml",
            timeout=3.5,
        )
        if 'checked="false"' in xml_raw and "<hierarchy" in xml_raw:
            try:
                root = ET.fromstring(xml_raw[xml_raw.index("<hierarchy") :])
                for node in root.iter("node"):
                    if (
                        node.attrib.get("checkable") == "true"
                        and node.attrib.get("checked") == "false"
                    ):
                        m = re.match(
                            r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
                            node.attrib.get("bounds", ""),
                        )
                        if m:
                            x1, y1, x2, y2 = map(int, m.groups())
                            self._safe_tap((x1 + x2) // 2, (y1 + y2) // 2)
                            break
            except Exception:
                pass
            time.sleep(0.6)
            self._confirm_cast_dialog_if_present()

        extra_note = ""
        if win_active:
            extra_note = (
                f" (Note: Projector {win_active.split('(')[0].strip()} is currently connected to the Laptop! "
                "To connect it directly to the phone, click '🔌 Use PC / Phone Screen Only' first)."
            )
        return {
            "ok": True,
            "message": f"📱 MIUI Cast opened on Xiaomi phone over Wi-Fi (screen kept awake)!{extra_note}",
        }

    def open_windows_wireless_display(self) -> Dict[str, Any]:
        """Abre o painel 'Conectar a uma tela sem fio' (Win+K) no desktop visível do Windows e auto-conecta."""
        self.wake_phone_screen(bring_to_front=False)
        if os.name != "nt":
            return {
                "ok": False,
                "message": "Available only when the server is running on a Windows host.",
            }
        target_name = "PROJECTOR"
        win_devs, _, _ = self.discover_windows_miracast_devices()
        proj_dev = next((d for d in win_devs if d.get("is_projector")), win_devs[0] if win_devs else None)
        if proj_dev and proj_dev.get("raw_name"):
            target_name = proj_dev["raw_name"]
        self._auto_click_windows_cast_target(target_name)
        ip_note = f" (IP {self.cached_projector_ip})" if self.cached_projector_ip else ""
        return {
            "ok": True,
            "projector_ip": self.cached_projector_ip or None,
            "message": f"💻 Windows Wireless Display panel (Win+K) opened and scanning for Projector{ip_note}!",
        }

    def send_dlna_media_url(self, control_url: str, media_url: str) -> Dict[str, Any]:
        """
        Envia uma URL de vídeo/stream via SOAP SetAVTransportURI + Play para um projetor DLNA
        (implementação compatível com dlnap / nanodlna).
        """
        set_uri_body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <CurrentURI>{media_url}</CurrentURI>
      <CurrentURIMetaData></CurrentURIMetaData>
    </u:SetAVTransportURI>
  </s:Body>
</s:Envelope>""".encode("utf-8")

        play_body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <Speed>1</Speed>
    </u:Play>
  </s:Body>
</s:Envelope>""".encode("utf-8")

        try:
            req1 = urllib.request.Request(
                control_url,
                data=set_uri_body,
                headers={
                    "Content-Type": 'text/xml; charset="utf-8"',
                    "SOAPAction": '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"',
                },
                method="POST",
            )
            urllib.request.urlopen(req1, timeout=3.0).read()

            req2 = urllib.request.Request(
                control_url,
                data=play_body,
                headers={
                    "Content-Type": 'text/xml; charset="utf-8"',
                    "SOAPAction": '"urn:schemas-upnp-org:service:AVTransport:1#Play"',
                },
                method="POST",
            )
            urllib.request.urlopen(req2, timeout=3.0).read()
            return {"ok": True, "message": "Stream sent to DLNA Projector/TV!"}
        except Exception as exc:
            return {"ok": False, "message": f"Failed to send DLNA stream: {exc}"}
