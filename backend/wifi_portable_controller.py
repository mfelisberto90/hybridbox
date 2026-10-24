"""
Controlador de Portabilidade Universal Wi-Fi, Hotspot de Resgate (Zero-Toque)
e Anunciador mDNS / ZeroConf (`http://hybridbox.local:8080`) para o HybridBox Remote PWA.

Permite levar o Xiaomi Redmi Note 8 Pro para qualquer lugar, conectar em qualquer rede
Wi-Fi direto pelo App PWA (sem tocar na tela quebrada), reconectar automaticamente ao
Hotspot de Resgate do celular do usuário quando fora de casa e acessar o controle
pelo endereço universal `http://hybridbox.local:8080`.
"""

import json
import os
import re
import shlex
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


MDNS_GROUP_IP = "224.0.0.251"
MDNS_PORT = 5353
DEFAULT_MDNS_HOSTNAME = "hybridbox.local"


def _encode_dns_name(name: str) -> bytes:
    """Codifica um nome DNS (ex: 'hybridbox.local.') no formato wire RFC 1035."""
    clean = name.strip().strip(".")
    if not clean:
        return b"\x00"
    parts = [p.encode("utf-8")[:63] for p in clean.split(".") if p]
    return b"".join(struct.pack("B", len(p)) + p for p in parts) + b"\x00"


def _decode_dns_name(packet: bytes, offset: int) -> Tuple[str, int]:
    """Decodifica um nome DNS do pacote com suporte a ponteiros de compressão (0xC0)."""
    labels: List[str] = []
    curr = offset
    next_offset: Optional[int] = None
    visited = set()

    while curr < len(packet):
        if curr in visited:
            break
        visited.add(curr)
        length = packet[curr]
        if length == 0:
            curr += 1
            if next_offset is None:
                next_offset = curr
            break
        if (length & 0xC0) == 0xC0:
            if curr + 1 >= len(packet):
                curr += 1
                break
            ptr = ((length & 0x3F) << 8) | packet[curr + 1]
            if next_offset is None:
                next_offset = curr + 2
            curr = ptr
            continue
        curr += 1
        if curr + length > len(packet):
            break
        labels.append(packet[curr : curr + length].decode("utf-8", errors="ignore"))
        curr += length

    if next_offset is None:
        next_offset = curr
    return ".".join(labels).lower(), next_offset


class MdnsZeroConfService:
    """
    Servidor e Anunciador mDNS / ZeroConf leve em Python puro (UDP 224.0.0.251:5353).
    Responde a consultas A-record para `hybridbox.local` e anuncia `_http._tcp.local.` na porta 8080.
    """

    def __init__(
        self,
        ip_provider: Callable[[], str],
        hostname: str = DEFAULT_MDNS_HOSTNAME,
        http_port: int = 8080,
    ) -> None:
        self.ip_provider = ip_provider
        self.hostname = hostname.strip().strip(".").lower()
        self.http_port = http_port
        self._running = False
        self._sock: Optional[socket.socket] = None
        self._joined_ips: set[str] = set()
        self._last_announced_ip: str = ""
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="HybridBox-mDNS", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    @staticmethod
    def get_iface_ipv4(iface: str = "wlan0") -> str:
        """Obtém o IPv4 diretamente da interface de rede no Linux/Android via ioctl SIOCGIFADDR (sem precisar de rota default)."""
        if os.name == "nt":
            return ""
        try:
            import fcntl

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                ifreq = struct.pack("256s", iface.encode("utf-8")[:15])
                res = fcntl.ioctl(s.fileno(), 0x8915, ifreq)  # SIOCGIFADDR
                ip = socket.inet_ntoa(res[20:24])
                if ip and ip != "127.0.0.1":
                    return ip
        except Exception:
            pass
        return ""

    def get_local_bind_ip(self) -> str:
        """Retorna o IP da interface local desta máquina (para bind de socket e multicast membership)."""
        if os.name != "nt":
            for iface in ("wlan0", "wlan1", "ap0", "swlan0", "rndis0"):
                ip = self.get_iface_ipv4(iface)
                if ip:
                    return ip
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                if ip and ip != "127.0.0.1":
                    return ip
        except Exception:
            pass
        return "127.0.0.1"

    def get_target_ip(self) -> str:
        try:
            ip = (self.ip_provider() or "").strip()
            if ip and ip != "127.0.0.1":
                socket.inet_aton(ip)
                return ip
        except Exception:
            pass
        return self.get_local_bind_ip()

    def _ensure_multicast_membership(self, sock: socket.socket, bind_ip: str) -> None:
        if not bind_ip or bind_ip == "127.0.0.1":
            return
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(bind_ip))
        except Exception:
            pass
        if bind_ip not in self._joined_ips:
            try:
                mreq = struct.pack("4s4s", socket.inet_aton(MDNS_GROUP_IP), socket.inet_aton(bind_ip))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                self._joined_ips.add(bind_ip)
            except Exception:
                pass

    def build_response_packet(
        self,
        ip_str: str,
        tx_id: int = 0,
        include_service: bool = True,
        cache_flush: bool = True,
    ) -> bytes:
        """Constrói pacote DNS Authoritative Answer para `hybridbox.local` e `_http._tcp.local`."""
        try:
            ip_bytes = socket.inet_aton(ip_str)
        except Exception:
            ip_bytes = socket.inet_aton("127.0.0.1")

        host_wire = _encode_dns_name(self.hostname)
        service_wire = _encode_dns_name("_http._tcp.local")
        instance_wire = _encode_dns_name("HybridBox._http._tcp.local")
        rclass = 0x8001 if cache_flush else 0x0001

        records: List[bytes] = []

        # 1. A Record: hybridbox.local -> IPv4
        records.append(
            host_wire
            + struct.pack(">HHIH", 1, rclass, 120, 4)
            + ip_bytes
        )

        if include_service:
            # 2. PTR Record: _http._tcp.local -> HybridBox._http._tcp.local
            records.append(
                service_wire
                + struct.pack(">HHIH", 12, 0x0001, 120, len(instance_wire))
                + instance_wire
            )
            # 3. SRV Record: HybridBox._http._tcp.local -> port 8080 hybridbox.local
            srv_rdata = struct.pack(">HHH", 0, 0, self.http_port) + host_wire
            records.append(
                instance_wire
                + struct.pack(">HHIH", 33, rclass, 120, len(srv_rdata))
                + srv_rdata
            )
            # 4. TXT Record
            txt_entries = [b"path=/", b"app=HybridBox Remote PWA"]
            txt_rdata = b"".join(struct.pack("B", len(t)) + t for t in txt_entries)
            records.append(
                instance_wire
                + struct.pack(">HHIH", 16, rclass, 120, len(txt_rdata))
                + txt_rdata
            )

        header = struct.pack(">HHHHHH", tx_id, 0x8400, 0, len(records), 0, 0)
        return header + b"".join(records)

    def parse_is_matching_query(self, data: bytes) -> Tuple[bool, int, bool]:
        """
        Analisa se o pacote UDP recebido é uma consulta DNS/mDNS para `hybridbox.local`
        ou `_http._tcp.local`. Retorna (matched, tx_id, wants_service).
        """
        if len(data) < 12:
            return False, 0, False
        try:
            tx_id, flags, qdcount, _, _, _ = struct.unpack(">HHHHHH", data[:12])
        except Exception:
            return False, 0, False

        # Se bit QR (0x8000) == 1, é resposta, ignora
        if (flags & 0x8000) != 0 or qdcount == 0:
            return False, tx_id, False

        offset = 12
        matched = False
        wants_service = False
        target_names = {
            self.hostname,
            "hybridbox",
            "hybridbox-pwa.local",
        }
        service_names = {
            "_http._tcp.local",
            "hybridbox._http._tcp.local",
            "_services._dns-sd._udp.local",
        }

        for _ in range(min(qdcount, 16)):
            if offset >= len(data):
                break
            qname, offset = _decode_dns_name(data, offset)
            if offset + 4 > len(data):
                break
            qtype, _ = struct.unpack(">HH", data[offset : offset + 4])
            offset += 4

            qname_clean = qname.strip(".")
            if qname_clean in target_names and qtype in (1, 28, 255):  # A, AAAA, ANY
                matched = True
            elif qname_clean in service_names:
                matched = True
                wants_service = True

        return matched, tx_id, wants_service

    def announce_now(self) -> None:
        if not self._sock:
            return
        ip_str = self.get_target_ip()
        bind_ip = self.get_local_bind_ip()
        if not ip_str or ip_str == "127.0.0.1":
            return
        self._ensure_multicast_membership(self._sock, bind_ip)
        pkt = self.build_response_packet(ip_str, tx_id=0, include_service=True, cache_flush=True)
        try:
            self._sock.sendto(pkt, (MDNS_GROUP_IP, MDNS_PORT))
            self._last_announced_ip = ip_str
        except Exception:
            pass

    def _create_udp_socket(self, bind_addr: str) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception:
                pass
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        s.bind((bind_addr, MDNS_PORT))
        s.setblocking(False)
        return s

    def _run_loop(self) -> None:
        import select

        while self._running:
            mcast_sock: Optional[socket.socket] = None
            ucast_sock: Optional[socket.socket] = None
            ucast_bound_ip: str = ""
            try:
                mcast_sock = self._create_udp_socket("")
                try:
                    mreq_any = struct.pack(
                        "4s4s", socket.inet_aton(MDNS_GROUP_IP), socket.inet_aton("0.0.0.0")
                    )
                    mcast_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq_any)
                except Exception:
                    pass

                self._sock = mcast_sock
                self._joined_ips.clear()

                last_announce_ts = 0.0
                while self._running:
                    now = time.time()
                    curr_ip = self.get_target_ip()
                    bind_ip = self.get_local_bind_ip()
                    if bind_ip and bind_ip != "127.0.0.1":
                        self._ensure_multicast_membership(mcast_sock, bind_ip)
                        if bind_ip != ucast_bound_ip:
                            if ucast_sock:
                                try:
                                    ucast_sock.close()
                                except Exception:
                                    pass
                                ucast_sock = None
                            try:
                                ucast_sock = self._create_udp_socket(bind_ip)
                                ucast_bound_ip = bind_ip
                            except Exception:
                                ucast_sock = None
                                ucast_bound_ip = bind_ip  # Evita retentar bind na mesma interface a cada 2s

                    if curr_ip and curr_ip != "127.0.0.1":
                        if curr_ip != self._last_announced_ip or (now - last_announce_ts >= 25.0):
                            pkt = self.build_response_packet(
                                curr_ip, tx_id=0, include_service=True, cache_flush=True
                            )
                            try:
                                mcast_sock.sendto(pkt, (MDNS_GROUP_IP, MDNS_PORT))
                                self._last_announced_ip = curr_ip
                                last_announce_ts = now
                            except Exception:
                                pass

                    read_socks = [s for s in (mcast_sock, ucast_sock) if s is not None]
                    try:
                        readable, _, _ = select.select(read_socks, [], [], 2.0)
                    except Exception:
                        continue

                    for r_sock in readable:
                        try:
                            data, addr = r_sock.recvfrom(4096)
                        except Exception:
                            continue

                        matched, tx_id, wants_service = self.parse_is_matching_query(data)
                        if matched and curr_ip and curr_ip != "127.0.0.1":
                            is_mdns_peer = addr[1] == MDNS_PORT
                            resp_unicast = self.build_response_packet(
                                curr_ip,
                                tx_id=tx_id,
                                include_service=wants_service,
                                cache_flush=is_mdns_peer,
                            )
                            resp_mcast = self.build_response_packet(
                                curr_ip,
                                tx_id=0,
                                include_service=wants_service,
                                cache_flush=True,
                            )
                            try:
                                r_sock.sendto(resp_unicast, addr)
                            except Exception:
                                pass
                            try:
                                mcast_sock.sendto(resp_mcast, (MDNS_GROUP_IP, MDNS_PORT))
                            except Exception:
                                pass
            except Exception:
                time.sleep(3.0)
            finally:
                for s in (mcast_sock, ucast_sock):
                    if s:
                        try:
                            s.close()
                        except Exception:
                            pass
                self._sock = None


class WifiPortableController:
    """
    Controla conexões Wi-Fi no Xiaomi Redmi Note 8 Pro (Android 11 / MIUI 12.5)
    via `cmd wifi` (UID 2000 shell) e gerencia o Hotspot de Resgate para Modo Viagem.
    """

    def __init__(self, android_controller: Any, base_dir: Path) -> None:
        self.android = android_controller
        self.base_dir = base_dir
        self.config_path = base_dir / "rescue_wifi.json"
        self.device_conf_path = "/data/local/tmp/hb_rescue_wifi.conf"
        self._cached_wlan_ip: str = ""
        self._config: Dict[str, Any] = self._load_config()
        self.mdns = MdnsZeroConfService(
            ip_provider=self.get_best_phone_ip,
            hostname=DEFAULT_MDNS_HOSTNAME,
            http_port=8080,
        )
        self.mdns.start()
        threading.Thread(
            target=self._bootstrap_rescue_hotspot_on_android,
            name="HybridBox-WifiBootstrap",
            daemon=True,
        ).start()

    def _default_config(self) -> Dict[str, Any]:
        return {
            "ssid": "HybridBox",
            "password": "hybridbox123",
            "security": "wpa2",
            "auto_connect": True,
            "saved_networks": [
                {
                    "ssid": "HybridBox",
                    "password": "hybridbox123",
                    "security": "wpa2",
                    "is_rescue": True,
                }
            ],
        }

    def _load_config(self) -> Dict[str, Any]:
        default = self._default_config()
        if not self.config_path.exists():
            self._save_config(default)
            return default
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return default
            for k, v in default.items():
                if k not in raw:
                    raw[k] = v
            return raw
        except Exception:
            return default

    def _save_config(self, cfg: Dict[str, Any]) -> None:
        self._config = cfg
        try:
            self.config_path.write_text(
                json.dumps(cfg, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _run_shell(self, cmd: str, timeout: float = 5.0) -> str:
        try:
            return (self.android.run_adb_shell(cmd, timeout=timeout, include_stderr=True) or "").strip()
        except Exception:
            return ""

    def get_best_phone_ip(self) -> str:
        """Retorna o IP Wi-Fi (`wlan0`) atual do Redmi Note 8 Pro (ou IP de hotspot/local como fallback)."""
        if os.name != "nt":
            # Quando rodando diretamente no celular (Termux), lê o IP direto da interface wlan0 via ioctl SIOCGIFADDR
            for iface in ("wlan0", "wlan1", "ap0", "swlan0", "rndis0"):
                ip = MdnsZeroConfService.get_iface_ipv4(iface)
                if ip:
                    self._cached_wlan_ip = ip
                    return ip
            if self._cached_wlan_ip and self._cached_wlan_ip != "127.0.0.1":
                return self._cached_wlan_ip
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    ip = s.getsockname()[0]
                    if ip and ip != "127.0.0.1":
                        return ip
            except Exception:
                pass
        if self._cached_wlan_ip and self._cached_wlan_ip != "127.0.0.1":
            return self._cached_wlan_ip
        if hasattr(self.android, "discover_phone_ip"):
            try:
                phone_ip = self.android.discover_phone_ip(force=False)
                if phone_ip and phone_ip != "127.0.0.1":
                    return phone_ip
            except Exception:
                pass
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def _sync_rescue_conf_to_android(self) -> str:
        """
        Grava `/data/local/tmp/hb_rescue_wifi.conf` e pré-salva o Hotspot de Resgate
        no gerenciador Wi-Fi nativo do Android 11 (`cmd wifi add-network`).
        """
        ssid = (self._config.get("ssid") or "HybridBox").strip()
        password = (self._config.get("password") or "hybridbox123").strip()
        security = (self._config.get("security") or "wpa2").strip().lower()
        if security not in ("open", "owe", "wpa2", "wpa3"):
            security = "wpa2" if password else "open"
        auto_conn = "1" if self._config.get("auto_connect", True) else "0"

        conf_lines = (
            f"RESCUE_SSID={shlex.quote(ssid)}\n"
            f"RESCUE_PASS={shlex.quote(password)}\n"
            f"RESCUE_SEC={shlex.quote(security)}\n"
            f"RESCUE_ENABLED={shlex.quote(auto_conn)}\n"
        )
        add_cmd = (
            f"cmd wifi add-network {shlex.quote(ssid)} {security} {shlex.quote(password)}"
            if security in ("wpa2", "wpa3") and password
            else f"cmd wifi add-network {shlex.quote(ssid)} {security}"
        )
        shell_script = (
            f"cat << 'EOF' > {self.device_conf_path}\n{conf_lines}EOF\n"
            f"chmod 644 {self.device_conf_path} 2>/dev/null || true; "
            f"cmd wifi set-scan-always-available enabled 2>/dev/null || true; "
            f"{add_cmd} 2>/dev/null || true"
        )
        return self._run_shell(shell_script, timeout=4.5)

    def _bootstrap_rescue_hotspot_on_android(self) -> None:
        time.sleep(1.5)
        try:
            self._sync_rescue_conf_to_android()
        except Exception:
            pass

    @staticmethod
    def rssi_to_percent(rssi: int) -> int:
        if rssi >= -50:
            return 100
        if rssi <= -100:
            return 0
        return max(0, min(100, 2 * (rssi + 100)))

    @staticmethod
    def parse_security_from_flags(flags: str) -> Tuple[str, str, bool]:
        """
        Extrai (security_type, security_label, is_protected) a partir das flags de `cmd wifi list-scan-results`.
        """
        f_up = (flags or "").upper()
        if "WPA2" in f_up and ("SAE" in f_up or "WPA3" in f_up):
            return "wpa2", "WPA2/WPA3", True
        if "SAE" in f_up or "WPA3" in f_up:
            return "wpa3", "WPA3-SAE", True
        if "WPA2" in f_up or "RSN" in f_up or "WPA-" in f_up:
            return "wpa2", "WPA2-PSK", True
        if "OWE" in f_up:
            return "owe", "Open (OWE)", False
        if "WEP" in f_up:
            return "wpa2", "WEP", True
        return "open", "Open (No Password)", False

    def _parse_saved_networks(self, raw_networks: str) -> List[Dict[str, Any]]:
        saved: List[Dict[str, Any]] = []
        seen_ssids = set()
        for line in (raw_networks or "").splitlines():
            m = re.match(r"^\s*(\d+)\s+(.+?)\s+(open|owe|wpa2|wpa3|wep|eap\S*)\s*$", line.strip(), re.I)
            if not m:
                continue
            net_id = int(m.group(1))
            ssid = m.group(2).strip()
            sec = m.group(3).strip().lower()
            if not ssid or ssid.lower() in seen_ssids:
                continue
            seen_ssids.add(ssid.lower())
            saved.append(
                {
                    "network_id": net_id,
                    "ssid": ssid,
                    "security": sec,
                    "is_rescue": ssid.lower() == (self._config.get("ssid") or "").strip().lower(),
                }
            )
        return saved

    def _parse_scan_results(
        self,
        raw_scan: str,
        current_ssid: str = "",
        saved_ssids: Optional[set[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Faz parse de `cmd wifi list-scan-results`, deduplica por SSID mantendo o maior sinal,
        identifica frequências 2.4GHz / 5GHz e ordena por potência de sinal (RSSI).
        """
        saved_set = saved_ssids or set()
        rescue_ssid_low = (self._config.get("ssid") or "HybridBox").strip().lower()
        curr_low = (current_ssid or "").strip().lower()

        by_ssid: Dict[str, Dict[str, Any]] = {}
        for line in (raw_scan or "").splitlines():
            m = re.match(
                r"^\s*([0-9a-fA-F:]{17})\s+(\d+)\s+(-?\d+)\s+(\S+)\s+(.*?)\s+((?:\[[^\]]*\])+)\s*$",
                line,
            )
            if not m:
                continue
            bssid = m.group(1).lower()
            freq = int(m.group(2))
            rssi = int(m.group(3))
            ssid = m.group(5).strip()
            flags = m.group(6).strip()

            if not ssid or ssid.startswith("\\x00"):
                continue

            band = "5GHz" if freq >= 4900 else "2.4GHz"
            sec_type, sec_label, is_protected = self.parse_security_from_flags(flags)
            sig_pct = self.rssi_to_percent(rssi)
            key = ssid.lower()

            if key not in by_ssid:
                by_ssid[key] = {
                    "ssid": ssid,
                    "bssid": bssid,
                    "frequency_mhz": freq,
                    "band": band,
                    "bands": [band],
                    "rssi": rssi,
                    "signal_percent": sig_pct,
                    "security": sec_type,
                    "security_label": sec_label,
                    "protected": is_protected,
                    "flags": flags,
                    "connected": key == curr_low and bool(curr_low),
                    "is_current": key == curr_low and bool(curr_low),
                    "saved": key in saved_set,
                    "is_saved": key in saved_set,
                    "is_rescue": key == rescue_ssid_low,
                }
            else:
                existing = by_ssid[key]
                if band not in existing["bands"]:
                    existing["bands"].append(band)
                    existing["bands"].sort(reverse=True)  # ["5GHz", "2.4GHz"]
                if rssi > existing["rssi"]:
                    existing["rssi"] = rssi
                    existing["signal_percent"] = sig_pct
                    existing["bssid"] = bssid
                    existing["frequency_mhz"] = freq
                    existing["band"] = band

        results = list(by_ssid.values())
        for item in results:
            item["band_label"] = " / ".join(item["bands"])

        results.sort(
            key=lambda x: (
                -int(x.get("rssi", -100)),
                not bool(x.get("connected")),
                not bool(x.get("is_rescue")),
                x.get("ssid", "").lower(),
            )
        )
        return results

    def get_wifi_status(self) -> Dict[str, Any]:
        """
        Retorna status completo do Wi-Fi do Redmi Note 8 Pro:
        SSID conectado, IP (`wlan0` e eventual interface de hotspot), RSSI/%, banda,
        gateway, endereço universal `http://hybridbox.local:8080`, redes salvas e Hotspot de Resgate.
        """
        out = self._run_shell(
            "cmd wifi status 2>/dev/null; "
            "echo '===IP_ADDR==='; "
            "ip -4 addr show 2>/dev/null; "
            "echo '===ROUTE==='; "
            "ip -4 route show table all 2>/dev/null | grep -E 'default.*wlan0|default via' | head -n 4; "
            "echo '===NETWORKS==='; "
            "cmd wifi list-networks 2>/dev/null; "
            "echo '===SCAN==='; "
            "cmd wifi list-scan-results 2>/dev/null",
            timeout=4.5,
        )

        status_part = out.split("===IP_ADDR===")[0] if "===IP_ADDR===" in out else out
        ip_part = (
            out.split("===IP_ADDR===", 1)[1].split("===ROUTE===")[0]
            if "===IP_ADDR===" in out and "===ROUTE===" in out
            else ""
        )
        route_part = (
            out.split("===ROUTE===", 1)[1].split("===NETWORKS===")[0]
            if "===ROUTE===" in out and "===NETWORKS===" in out
            else ""
        )
        net_part = (
            out.split("===NETWORKS===", 1)[1].split("===SCAN===")[0]
            if "===NETWORKS===" in out and "===SCAN===" in out
            else (out.split("===NETWORKS===", 1)[1] if "===NETWORKS===" in out else "")
        )
        scan_part = out.split("===SCAN===", 1)[1] if "===SCAN===" in out else ""

        wifi_enabled = "Wifi is enabled" in status_part or "Wifi is connected" in status_part
        connected = (
            "Wifi is connected to" in status_part
            or "Supplicant state: COMPLETED" in status_part
        )

        ssid = ""
        m_ssid = re.search(r'Wifi is connected to\s+"([^"]+)"', status_part)
        if m_ssid:
            ssid = m_ssid.group(1).strip()
        else:
            m_ssid2 = re.search(r"SSID:\s*([^,\r\n]+)", status_part)
            if m_ssid2:
                cand = m_ssid2.group(1).strip().strip('"')
                if cand and cand != "<unknown ssid>":
                    ssid = cand

        bssid = ""
        m_bssid = re.search(r"BSSID:\s*([0-9a-fA-F:]{17})", status_part)
        if m_bssid:
            bssid = m_bssid.group(1).lower()

        mac = ""
        m_mac = re.search(r"MAC:\s*([0-9a-fA-F:]{17})", status_part)
        if m_mac:
            mac = m_mac.group(1).lower()

        rssi = -70
        m_rssi = re.search(r"RSSI:\s*(-?\d+)", status_part)
        if m_rssi:
            rssi = int(m_rssi.group(1))
        signal_percent = self.rssi_to_percent(rssi) if connected else 0

        freq = 0
        m_freq = re.search(r"Frequency:\s*(\d+)MHz", status_part)
        if m_freq:
            freq = int(m_freq.group(1))
        band = "5GHz" if freq >= 4900 else ("2.4GHz" if freq > 0 else "")

        link_speed = 0
        m_speed = re.search(r"Link speed:\s*(\d+)Mbps", status_part)
        if m_speed:
            link_speed = int(m_speed.group(1))

        wlan_ip = ""
        hotspot_ip: Optional[str] = None
        for line in ip_part.splitlines():
            m_inet = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/\d+.*?\s(\S+)\s*$", line.strip())
            if not m_inet:
                continue
            addr_ip, iface = m_inet.group(1), m_inet.group(2)
            if addr_ip == "127.0.0.1":
                continue
            if iface == "wlan0":
                wlan_ip = addr_ip
            elif any(iface.startswith(p) for p in ("wlan1", "ap", "swlan", "rndis", "p2p")):
                hotspot_ip = addr_ip

        if wlan_ip and wlan_ip != "127.0.0.1":
            self._cached_wlan_ip = wlan_ip
            if hasattr(self.android, "ssh_host"):
                self.android.ssh_host = wlan_ip
        else:
            wlan_ip = self.get_best_phone_ip()

        gateway = ""
        m_gw = re.search(r"default via\s+(\d+\.\d+\.\d+\.\d+)", route_part)
        if m_gw:
            gateway = m_gw.group(1)
        elif wlan_ip and not wlan_ip.startswith("127.") and wlan_ip.count(".") == 3:
            gateway = ".".join(wlan_ip.split(".")[:3]) + ".1"

        saved_networks = self._parse_saved_networks(net_part)
        saved_ssids = {n["ssid"].lower() for n in saved_networks}
        cached_networks = self._parse_scan_results(
            scan_part,
            current_ssid=ssid,
            saved_ssids=saved_ssids,
        )
        rescue_cfg = {
            "ssid": self._config.get("ssid", "HybridBox"),
            "password": self._config.get("password", "hybridbox123"),
            "security": self._config.get("security", "wpa2"),
            "auto_connect": bool(self._config.get("auto_connect", True)),
        }
        mdns_url = f"http://{DEFAULT_MDNS_HOSTNAME}:8080"
        current_obj = {
            "wifi_enabled": wifi_enabled,
            "connected": connected,
            "ssid": ssid,
            "bssid": bssid,
            "mac": mac,
            "ip": wlan_ip,
            "hotspot_ip": hotspot_ip,
            "rssi": rssi if connected else None,
            "signal_percent": signal_percent,
            "frequency_mhz": freq,
            "band": band,
            "frequency_band": band,
            "link_speed_mbps": link_speed,
            "gateway": gateway,
            "mdns_url": mdns_url,
        }

        return {
            "ok": True,
            "current": current_obj,
            "wifi_enabled": wifi_enabled,
            "connected": connected,
            "ssid": ssid,
            "bssid": bssid,
            "mac": mac,
            "ip": wlan_ip,
            "hotspot_ip": hotspot_ip,
            "rssi": rssi if connected else None,
            "signal_percent": signal_percent,
            "frequency_mhz": freq,
            "band": band,
            "frequency_band": band,
            "link_speed_mbps": link_speed,
            "gateway": gateway,
            "mdns_hostname": DEFAULT_MDNS_HOSTNAME,
            "mdns_url": mdns_url,
            "direct_url": f"http://{wlan_ip}:8080" if wlan_ip else mdns_url,
            "networks": cached_networks,
            "saved_networks": saved_networks,
            "rescue_hotspot": rescue_cfg,
        }

    def scan_wifi_networks(self) -> Dict[str, Any]:
        """
        Dispara `cmd wifi start-scan` no Redmi Note 8 Pro e retorna todas as redes
        Wi-Fi próximas ordenadas por potência de sinal, sem duplicatas de SSID.
        """
        out = self._run_shell(
            "svc wifi enable 2>/dev/null; "
            "cmd wifi set-wifi-enabled enabled 2>/dev/null; "
            "cmd wifi set-scan-always-available enabled 2>/dev/null; "
            "cmd wifi start-scan 2>/dev/null; "
            "sleep 1.1; "
            "cmd wifi status 2>/dev/null; "
            "echo '===NETWORKS==='; "
            "cmd wifi list-networks 2>/dev/null; "
            "echo '===SCAN==='; "
            "cmd wifi list-scan-results 2>/dev/null",
            timeout=7.5,
        )

        status_part = out.split("===NETWORKS===")[0] if "===NETWORKS===" in out else ""
        net_part = (
            out.split("===NETWORKS===", 1)[1].split("===SCAN===")[0]
            if "===NETWORKS===" in out and "===SCAN===" in out
            else ""
        )
        scan_part = out.split("===SCAN===", 1)[1] if "===SCAN===" in out else out

        current_ssid = ""
        m_ssid = re.search(r'Wifi is connected to\s+"([^"]+)"', status_part)
        if m_ssid:
            current_ssid = m_ssid.group(1).strip()

        saved_list = self._parse_saved_networks(net_part)
        saved_ssids = {n["ssid"].lower() for n in saved_list}

        networks = self._parse_scan_results(
            scan_part,
            current_ssid=current_ssid,
            saved_ssids=saved_ssids,
        )

        status_info = self.get_wifi_status()
        return {
            "ok": True,
            "count": len(networks),
            "current": status_info.get("current"),
            "current_ssid": status_info.get("ssid") or current_ssid,
            "ip": status_info.get("ip"),
            "mdns_url": status_info.get("mdns_url", f"http://{DEFAULT_MDNS_HOSTNAME}:8080"),
            "networks": networks,
            "saved_networks": saved_list,
            "rescue_hotspot": status_info.get("rescue_hotspot"),
            "message": (
                f"📡 {len(networks)} Wi-Fi network(s) found around the Redmi Note 8 Pro! "
                "Tap any network below to connect or pre-save."
            ),
        }

    def connect_wifi_network(
        self,
        ssid: str,
        password: str = "",
        security: str = "wpa2",
        save_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Conecta ou pré-salva uma rede Wi-Fi no Android 11 via `cmd wifi add-network` / `connect-network`
        sem precisar tocar na tela quebrada.
        Se a rede não estiver no alcance no momento, salva-a na lista de redes do Android sem
        derrubar a conexão Wi-Fi atual!
        """
        clean_ssid = (ssid or "").strip()
        if not clean_ssid:
            return {"ok": False, "message": "⚠️ Please enter the Wi-Fi network name (SSID)."}

        clean_pass = (password or "").strip()
        clean_sec = (security or "wpa2").strip().lower()
        if clean_sec not in ("open", "owe", "wpa2", "wpa3"):
            return {
                "ok": False,
                "message": "⚠️ Invalid Wi-Fi security type (use wpa2, wpa3, open, or owe).",
            }

        if clean_sec in ("wpa2", "wpa3") and len(clean_pass) < 8:
            return {
                "ok": False,
                "message": "⚠️ WPA2/WPA3 Wi-Fi passwords must be at least 8 characters.",
            }

        # Save to persistent local list
        saved_Entry = {
            "ssid": clean_ssid,
            "password": clean_pass,
            "security": clean_sec,
            "is_rescue": clean_ssid.lower() == (self._config.get("ssid") or "").strip().lower(),
        }
        existing_saved = [
            n
            for n in self._config.get("saved_networks", [])
            if isinstance(n, dict) and n.get("ssid", "").lower() != clean_ssid.lower()
        ]
        existing_saved.insert(0, saved_Entry)
        self._config["saved_networks"] = existing_saved[:30]
        self._save_config(self._config)

        # Check if network is in range to decide between immediate connect-network or add-network
        check_out = self._run_shell(
            "svc wifi enable 2>/dev/null; "
            "cmd wifi set-wifi-enabled enabled 2>/dev/null; "
            "cmd wifi status 2>/dev/null; "
            "echo '===SCAN==='; "
            "cmd wifi list-scan-results 2>/dev/null",
            timeout=4.5,
        )
        scan_networks = self._parse_scan_results(
            check_out.split("===SCAN===", 1)[1] if "===SCAN===" in check_out else check_out
        )
        in_range = any(n["ssid"].lower() == clean_ssid.lower() for n in scan_networks)

        add_args = (
            f"{shlex.quote(clean_ssid)} {clean_sec} {shlex.quote(clean_pass)}"
            if clean_sec in ("wpa2", "wpa3")
            else f"{shlex.quote(clean_ssid)} {clean_sec}"
        )

        if save_only or not in_range:
            cmd_out = self._run_shell(f"cmd wifi add-network {add_args}", timeout=4.5)
            status = self.get_wifi_status()
            reason_msg = (
                f"💾 Wi-Fi network '<strong>{clean_ssid}</strong>' pre-saved on Android! "
                "As soon as the phone is in range of this network, it will connect automatically."
                if save_only
                else f"💾 Network '<strong>{clean_ssid}</strong>' saved with Auto-Connect on Android! "
                f"(Since it is not in range right now, we kept the current Wi-Fi "
                f"'<strong>{status.get('ssid') or 'Active'}</strong>' connected)."
            )
            return {
                "ok": True,
                "saved": True,
                "in_range": in_range,
                "connected_now": status.get("ssid", "").lower() == clean_ssid.lower(),
                "current": status.get("current"),
                "ssid": status.get("ssid"),
                "ip": status.get("ip"),
                "mdns_url": f"http://{DEFAULT_MDNS_HOSTNAME}:8080",
                "networks": status.get("networks", []),
                "saved_networks": status.get("saved_networks", []),
                "rescue_hotspot": status.get("rescue_hotspot"),
                "raw_output": cmd_out,
                "message": reason_msg,
            }

        # Network is in range and user requested immediate connection:
        self._run_shell(
            f"cmd wifi add-network {add_args} 2>/dev/null; "
            f"(nohup sh -c 'cmd wifi connect-network {add_args}' </dev/null >/dev/null 2>&1 &)",
            timeout=4.0,
        )
        time.sleep(2.2)
        status = self.get_wifi_status()
        self.mdns.announce_now()
        new_ip = status.get("ip") or self.get_best_phone_ip()
        is_conn = (status.get("ssid") or "").lower() == clean_ssid.lower()

        return {
            "ok": True,
            "saved": True,
            "in_range": True,
            "connected_now": is_conn,
            "current": status.get("current"),
            "ssid": status.get("ssid") or clean_ssid,
            "ip": new_ip,
            "mdns_url": f"http://{DEFAULT_MDNS_HOSTNAME}:8080",
            "direct_url": f"http://{new_ip}:8080",
            "networks": status.get("networks", []),
            "saved_networks": status.get("saved_networks", []),
            "rescue_hotspot": status.get("rescue_hotspot"),
            "message": (
                f"🟢 Connected to Wi-Fi '<strong>{clean_ssid}</strong>' "
                f"(IP <code>{new_ip}</code> • <code>http://{DEFAULT_MDNS_HOSTNAME}:8080</code>)!"
                if is_conn
                else f"📡 Connecting to Wi-Fi '<strong>{clean_ssid}</strong>'... "
                f"If the IP changes, open <code>http://{DEFAULT_MDNS_HOSTNAME}:8080</code>!"
            ),
        }

    def configure_rescue_hotspot(
        self,
        ssid: str,
        password: str,
        security: str = "wpa2",
        auto_connect: bool = True,
        connect_now: bool = False,
    ) -> Dict[str, Any]:
        """
        Configura e salva no Android (`cmd wifi add-network` + `/data/local/tmp/hb_rescue_wifi.conf` +
        `rescue_wifi.json`) o Hotspot de Resgate (Roteador Wi-Fi do celular do usuário).
        """
        clean_ssid = (ssid or "HybridBox").strip()
        clean_pass = (password or "").strip()
        clean_sec = (security or "wpa2").strip().lower()
        if clean_sec not in ("open", "owe", "wpa2", "wpa3"):
            clean_sec = "wpa2" if clean_pass else "open"

        if clean_sec in ("wpa2", "wpa3") and len(clean_pass) < 8:
            return {
                "ok": False,
                "message": "⚠️ The Rescue Hotspot password (WPA2/WPA3) must be at least 8 characters.",
            }

        self._config["ssid"] = clean_ssid
        self._config["password"] = clean_pass
        self._config["security"] = clean_sec
        self._config["auto_connect"] = bool(auto_connect)
        self._save_config(self._config)

        sync_out = self._sync_rescue_conf_to_android()
        if connect_now:
            conn_res = self.connect_wifi_network(
                ssid=clean_ssid,
                password=clean_pass,
                security=clean_sec,
                save_only=False,
            )
            conn_res["rescue_hotspot"] = {
                "ssid": clean_ssid,
                "password": clean_pass,
                "security": clean_sec,
                "auto_connect": bool(auto_connect),
            }
            return conn_res

        status = self.get_wifi_status()
        return {
            "ok": True,
            "current": status.get("current"),
            "rescue_hotspot": {
                "ssid": clean_ssid,
                "password": clean_pass,
                "security": clean_sec,
                "auto_connect": bool(auto_connect),
            },
            "ip": status.get("ip"),
            "mdns_url": f"http://{DEFAULT_MDNS_HOSTNAME}:8080",
            "networks": status.get("networks", []),
            "saved_networks": status.get("saved_networks", []),
            "raw_output": sync_out,
            "message": (
                f"🆘 Rescue Hotspot '<strong>{clean_ssid}</strong>' saved on Android and in the 24/7 Watchdog! "
                "On any trip, simply turn on your phone's Wi-Fi Hotspot with that SSID and password "
                "and the Redmi Note 8 Pro will connect automatically within 20 seconds!"
            ),
        }
