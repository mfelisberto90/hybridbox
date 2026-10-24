"""
Controlador de Controles Bluetooth e Hub de Jogos Retrô (SNES, MAME/Arcade, Lemuroid)
para o HybridBox Remote PWA no Xiaomi Redmi Note 8 Pro.

Funcionalidades:
1. Pareamento e conexão de Controles Bluetooth (Xbox, PlayStation, 8BitDo, Ipega, Genéricos)
   100% via ADB + UIAutomator com Safe-Tap (sem precisar tocar na tela quebrada do celular)
   e confirmação automática do pop-up "Parear / Pair / OK".
2. Detecção de Gamepads ativos no subsistema de Input do Android (`dumpsys input`).
3. Gerenciamento de Emuladores Open-Source do GitHub (Snes9x EX+, NEO.emu Arcade, Lemuroid,
   MAME4droid, MD.emu) com instalação 1-clique via ADB e concessão automática de permissões de armazenamento.
4. Upload e sincronização de ROMs (.sfc, .smc, .zip, .7z) direto pelo navegador para `/sdcard/ROMs/snes`
   e `/sdcard/ROMs/mame`, além de disponibilização para o player Web EmulatorJS integrado.
"""

import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional


EMULATORS_CATALOG: Dict[str, Dict[str, Any]] = {
    "snes9x": {
        "id": "snes9x",
        "name": "Snes9x EX+ (Super Nintendo)",
        "system": "SNES (Super Nintendo)",
        "icon": "🍄",
        "badge": "SNES 16-Bit",
        "package": "com.explusalpha.Snes9xPlus",
        "activity": "com.explusalpha.Snes9xPlus/com.imagine.BaseActivity",
        "github_repo": "Rakashazi/emu-ex-plus-alpha",
        "download_url": "https://github.com/Rakashazi/emu-ex-plus-alpha/releases/download/Pre-release/Snes9xEXPlus.zip",
        "is_zip": True,
        "rom_dir": "/sdcard/ROMs/snes",
        "description": "Ultra-fast SNES emulator with native Bluetooth controller support and save states.",
    },
    "neoemu": {
        "id": "neoemu",
        "name": "NEO.emu (Arcade / NeoGeo / MAME)",
        "system": "MAME / NeoGeo Arcade",
        "icon": "🕹️",
        "badge": "Arcade / MVS",
        "package": "com.explusalpha.NeoEmu",
        "activity": "com.explusalpha.NeoEmu/com.imagine.BaseActivity",
        "github_repo": "Rakashazi/emu-ex-plus-alpha",
        "download_url": "https://github.com/Rakashazi/emu-ex-plus-alpha/releases/download/Pre-release/NeoEmu.zip",
        "is_zip": True,
        "rom_dir": "/sdcard/ROMs/mame",
        "description": "Arcade classics (Metal Slug, KOF, Fatal Fury, Aero Fighters) running at locked 60 FPS.",
    },
    "lemuroid": {
        "id": "lemuroid",
        "name": "Lemuroid Retro Hub (SNES + MAME + Multi)",
        "system": "Multi-Console (Libretro)",
        "icon": "👾",
        "badge": "All-in-One TV",
        "package": "com.swordfish.lemuroid",
        "activity": "com.swordfish.lemuroid/com.swordfish.lemuroid.app.mobile.feature.main.MainActivity",
        "github_repo": "Swordfish90/Lemuroid",
        "download_url": "https://github.com/Swordfish90/Lemuroid/releases/download/1.17.0/lemuroid-app-free-dynamic-release.apk",
        "is_zip": False,
        "rom_dir": "/sdcard/ROMs",
        "description": "Modern Libretro frontend with automatic box art for SNES, Arcade/FBNeo, Mega Drive, GBA, PS1, and N64.",
    },
    "mame4droid": {
        "id": "mame4droid",
        "name": "MAME4droid (Full Arcade)",
        "system": "MAME Arcade",
        "icon": "🪙",
        "badge": "MAME 0.260+",
        "package": "com.seleuco.mame4d2024",
        "alt_packages": ["com.seleuco.mame4droid", "com.seleuco.mame4all"],
        "activity": "com.seleuco.mame4d2024/com.seleuco.mame4droid.MAME4droid",
        "github_repo": "seleuco/MAME4droid-2024",
        "download_url": "https://github.com/seleuco/MAME4droid-Current/releases/download/v1.41.2/MAME4droid.2026-1.41.2-release.apk",
        "is_zip": False,
        "rom_dir": "/sdcard/ROMs/mame",
        "description": "Official MAME emulator for Android supporting thousands of classic arcade boards.",
    },
    "mdemu": {
        "id": "mdemu",
        "name": "MD.emu (Mega Drive / Sega Genesis)",
        "system": "Sega Mega Drive",
        "icon": "🦔",
        "badge": "16-Bit Sega",
        "package": "com.explusalpha.MdEmu",
        "activity": "com.explusalpha.MdEmu/com.imagine.BaseActivity",
        "github_repo": "Rakashazi/emu-ex-plus-alpha",
        "download_url": "https://github.com/Rakashazi/emu-ex-plus-alpha/releases/download/Pre-release/MdEmu.zip",
        "is_zip": True,
        "rom_dir": "/sdcard/ROMs/megadrive",
        "description": "Lightweight and responsive Mega Drive / Sega CD emulator for Bluetooth controllers.",
    },
}

CONTROLLER_SKINS_CATALOG: List[Dict[str, Any]] = [
    {
        "skin_id": "snes",
        "name": "Super Nintendo (SNES / Super Famicom)",
        "short_name": "SNES Classic",
        "system": "snes",
        "icon": "🍄",
        "photo_url": "/static/icons/snes-controller-photo.jpg",
        "layout": "4btn",
        "description": "Authentic gray Super Nintendo controller with classic D-Pad, slanted Select/Start, and 4-color X/Y/A/B diamond.",
    },
    {
        "skin_id": "snes_us",
        "name": "Super Nintendo US (Purple / Lavender)",
        "short_name": "SNES US Purple",
        "system": "snes",
        "icon": "🟣",
        "photo_url": "/static/icons/snes-us-controller-photo.jpg",
        "layout": "4btn_us",
        "description": "North American edition with concave lavender X/Y and convex purple A/B buttons on an SNES shell.",
    },
    {
        "skin_id": "mame",
        "name": "Arcade Fightstick (MAME / NeoGeo 6-Btn)",
        "short_name": "Arcade Stick",
        "system": "mame",
        "icon": "🕹️",
        "photo_url": "/static/icons/arcade-controller-photo.jpg",
        "layout": "6btn_arcade",
        "description": "Arcade fightstick with red Sanwa joystick, 6 illuminated buttons, and quick Insert Coin button.",
    },
    {
        "skin_id": "megadrive",
        "name": "Sega Mega Drive (6-Button Arcade Pad)",
        "short_name": "Mega Drive 6-Btn",
        "system": "megadrive",
        "icon": "🦔",
        "photo_url": "/static/icons/megadrive-controller-photo.jpg",
        "layout": "6btn_sega",
        "description": "Classic 6-button controller (X, Y, Z + A, B, C) ideal for Street Fighter II, Mortal Kombat, and Sega classics.",
    },
]


class BluetoothGamingController:
    """Gerencia Controles Bluetooth via ADB e Emuladores/ROMs de SNES e MAME."""

    def __init__(self, android_controller: Any, base_dir: Path) -> None:
        self.android = android_controller
        self.base_dir = base_dir
        self.apks_dir = base_dir / "apks"
        self.roms_dir = base_dir / "roms"
        self.apks_dir.mkdir(parents=True, exist_ok=True)
        (self.roms_dir / "snes").mkdir(parents=True, exist_ok=True)
        (self.roms_dir / "mame").mkdir(parents=True, exist_ok=True)
        (self.roms_dir / "megadrive").mkdir(parents=True, exist_ok=True)
        self._initialized_sdcard = False
        self.active_controller_id: str = "ctrl_snes_p1"
        self.controllers: List[Dict[str, Any]] = [
            {
                "id": "ctrl_snes_p1",
                "name": "Controller 1 • Super Nintendo (SNES)",
                "skin_id": "snes",
                "system": "snes",
                "player": 1,
                "icon": "🍄",
                "photo_url": "/static/icons/snes-controller-photo.jpg",
                "builtin": True,
            },
            {
                "id": "ctrl_snes_us_p1",
                "name": "Controller 1 • SNES US (Purple)",
                "skin_id": "snes_us",
                "system": "snes",
                "player": 1,
                "icon": "🟣",
                "photo_url": "/static/icons/snes-us-controller-photo.jpg",
                "builtin": True,
            },
            {
                "id": "ctrl_arcade_p1",
                "name": "Controller 1 • Arcade Fightstick (MAME/NeoGeo)",
                "skin_id": "mame",
                "system": "mame",
                "player": 1,
                "icon": "🕹️",
                "photo_url": "/static/icons/arcade-controller-photo.jpg",
                "builtin": True,
            },
            {
                "id": "ctrl_megadrive_p1",
                "name": "Controller 1 • Sega Mega Drive (6-Button)",
                "skin_id": "megadrive",
                "system": "megadrive",
                "player": 1,
                "icon": "🦔",
                "photo_url": "/static/icons/megadrive-controller-photo.jpg",
                "builtin": True,
            },
            {
                "id": "ctrl_snes_p2",
                "name": "Controller 2 • Super Nintendo (Player 2)",
                "skin_id": "snes",
                "system": "snes",
                "player": 2,
                "icon": "🎮",
                "photo_url": "/static/icons/snes-controller-photo.jpg",
                "builtin": False,
            },
        ]

    def _run_adb(self, shell_cmd: str, timeout: float = 5.0) -> str:
        """Executa comando `adb shell` síncrono com serial explícito e retorna stdout."""
        return self.android.run_adb_shell(shell_cmd, timeout=timeout)

    def _safe_tap(self, x: int, y: int) -> None:
        """Executa input tap com repetição contra o toque fantasma da tela quebrada."""
        self._run_adb(
            f"for i in 1 2 3 4 5; do input tap {x} {y} 2>/dev/null && break; done",
            timeout=4.0,
        )

    def ensure_rom_directories_and_permissions(self) -> None:
        """Cria pastas `/sdcard/ROMs/{snes,mame,megadrive}` no celular e concede permissões aos emuladores e Termux."""
        if self._initialized_sdcard:
            return
        self._run_adb(
            "mkdir -p /sdcard/ROMs/snes /sdcard/ROMs/mame /sdcard/ROMs/megadrive /sdcard/MAME4droid/roms; "
            "for pkg in com.termux com.termux.x11 com.explusalpha.Snes9xPlus com.explusalpha.NeoEmu com.explusalpha.MdEmu "
            "com.swordfish.lemuroid com.seleuco.mame4d2024 com.seleuco.mame4droid com.seleuco.mame4all; do "
            "pm grant $pkg android.permission.READ_EXTERNAL_STORAGE 2>/dev/null; "
            "pm grant $pkg android.permission.WRITE_EXTERNAL_STORAGE 2>/dev/null; "
            "appops set $pkg MANAGE_EXTERNAL_STORAGE allow 2>/dev/null; "
            "appops set --uid $pkg MANAGE_EXTERNAL_STORAGE allow 2>/dev/null; "
            "appops set $pkg LEGACY_STORAGE allow 2>/dev/null; "
            "appops set --uid $pkg LEGACY_STORAGE allow 2>/dev/null; "
            "appops set $pkg NO_ISOLATED_STORAGE allow 2>/dev/null; "
            "appops set --uid $pkg NO_ISOLATED_STORAGE allow 2>/dev/null; "
            "done",
            timeout=6.0,
        )
        self._initialized_sdcard = True

    # ==================== BLUETOOTH CONTROLLERS MANAGER ====================

    def get_bluetooth_status(self) -> Dict[str, Any]:
        """Lê `dumpsys bluetooth_manager`, `dumpsys input` (ou `HybridBoxBridge` via Wi-Fi SSH) e a tela Bluetooth do Android."""
        out = self._run_adb(
            "dumpsys bluetooth_manager 2>&1 | head -n 120; "
            "echo '===INPUT_DEVICES==='; "
            "dumpsys input 2>&1 | grep -iE 'Device [0-9]+:|Classes:|Path:' -A 1 | head -n 80",
            timeout=5.0,
        )
        if "Permission Denial" in out or not out.strip():
            bridge_out = self._run_adb(
                "CLASSPATH=/data/local/tmp/hybridbox_bridge.jar "
                "/system/bin/app_process / HybridBoxBridge status 2>/dev/null",
                timeout=4.0,
            )
            if bridge_out:
                out = out + "\n" + bridge_out

        enabled = (
            "enabled: true" in out
            or "State: ON" in out
            or "BT_ENABLED=true" in out
        )
        discovering = "Discovering: true" in out


        m_name = re.search(r"Name:\s*([^\r\n]+)", out)
        adapter_name = m_name.group(1).strip() if m_name else "Redmi Note 8 Pro"

        m_addr = re.search(r"Address:\s*([0-9A-Fa-f:]{17})", out)
        adapter_address = m_addr.group(1).strip() if m_addr else ""

        conn_state = "DISCONNECTED"
        m_conn = re.search(r"ConnectionState:\s*STATE_([A-Z_]+)", out)
        if m_conn:
            conn_state = m_conn.group(1)

        # Extrai dispositivos pareados (Bonded devices)
        bonded_devices: List[Dict[str, Any]] = []
        if "Bonded devices:" in out:
            bonded_section = out.split("Bonded devices:", 1)[1].split("AdapterState:", 1)[0]
            for line in bonded_section.splitlines():
                line_s = line.strip()
                if not line_s or line_s.startswith("mSnoop"):
                    continue
                m_mac = re.search(r"([0-9A-Fa-f:]{17})", line_s)
                if m_mac:
                    mac = m_mac.group(1).upper()
                    rest = line_s.replace(mac, "").strip(" -()[]\t")
                    dev_name = rest if rest else f"Controle Bluetooth ({mac})"
                    bonded_devices.append(
                        {
                            "id": mac,
                            "name": dev_name,
                            "address": mac,
                            "status": "Pareado (Salvo)",
                            "bonded": True,
                            "connected": conn_state == "CONNECTED",
                        }
                    )

        # Extrai Gamepads/Joysticks ativos em `dumpsys input`
        active_gamepads: List[str] = []
        if "===INPUT_DEVICES===" in out:
            inp_sec = out.split("===INPUT_DEVICES===", 1)[1]
            blocks = re.split(r"(?=(?:Device\s+)?\d+:\s*)", inp_sec)
            for blk in blocks:
                if any(
                    k in blk.upper()
                    for k in ("GAMEPAD", "JOYSTICK", "BUTTON_A", "CONTROLLER", "XBOX", "PLAYSTATION", "8BITDO")
                ):
                    m_dev = re.search(r"(?:Device\s+)?\d+:\s*([^\r\n]+)", blk)
                    if m_dev:
                        gname = m_dev.group(1).strip()
                        if (
                            gname not in active_gamepads
                            and "NVTCapacitive" not in gname
                            and "uinput-fpc" not in gname.lower()
                            and "fpc_irq" not in gname.lower()
                        ):
                            active_gamepads.append(gname)

        # Lê também itens visíveis na tela `BLUETOOTH_SETTINGS` caso esteja aberta
        ui_devices = self._get_bluetooth_screen_items()
        seen_names = {d["name"].lower() for d in bonded_devices}
        all_devices = list(bonded_devices)
        for item in ui_devices:
            key = item["name"].lower()
            if key not in seen_names:
                seen_names.add(key)
                all_devices.append(item)
            else:
                for d in all_devices:
                    if d["name"].lower() == key:
                        d["tap_x"] = item.get("tap_x")
                        d["tap_y"] = item.get("tap_y")
                        if item.get("status"):
                            d["status"] = item["status"]

        return {
            "ok": True,
            "enabled": enabled,
            "discovering": discovering,
            "adapter_name": adapter_name,
            "adapter_address": adapter_address,
            "connection_state": conn_state,
            "active_gamepads": active_gamepads,
            "devices": all_devices,
        }

    def _get_bluetooth_screen_items(self) -> List[Dict[str, Any]]:
        """Lê a lista de dispositivos visíveis na tela Bluetooth do Android via UIAutomator."""
        xml_raw = self._run_adb(
            "uiautomator dump /sdcard/bt_scan.xml >/dev/null 2>&1 && cat /sdcard/bt_scan.xml",
            timeout=6.0,
        )
        if "<hierarchy" not in xml_raw or "com.android.settings" not in xml_raw:
            return []

        xml_str = xml_raw[xml_raw.index("<hierarchy") :]
        items: List[Dict[str, Any]] = []
        ignore_titles = {
            "bluetooth",
            "device name",
            "available devices",
            "paired devices",
            "bluetooth settings",
            "additional settings",
            "received files",
            "pair new device",
            "dispositivos disponíveis",
            "dispositivos pareados",
            "nome do dispositivo",
            "configurações adicionais",
        }
        try:
            root = ET.fromstring(xml_str)
            for node in root.iter("node"):
                res_id = node.attrib.get("resource-id", "")
                text = (node.attrib.get("text") or "").strip()
                bounds = node.attrib.get("bounds", "")
                if (
                    res_id == "android:id/title"
                    and text
                    and text.lower() not in ignore_titles
                ):
                    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                    if m:
                        x1, y1, x2, y2 = map(int, m.groups())
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                        is_rare = "rarely used" in text.lower() or "pouco usados" in text.lower()
                        items.append(
                            {
                                "id": f"bt:{text}",
                                "name": text,
                                "address": f"Toque Automático ({cx},{cy})",
                                "status": "Grupo de Dispositivos Adicionais" if is_rare else "Disponível para Parear / Conectar",
                                "bonded": False,
                                "connected": False,
                                "is_group": is_rare,
                                "tap_x": cx,
                                "tap_y": cy,
                            }
                        )
        except Exception:
            pass
        return items

    def _tap_bluetooth_refresh(self) -> None:
        """Localiza e toca no ícone de atualizar/buscar da tela Bluetooth em retrato ou paisagem."""
        xml_raw = self._run_adb(
            "uiautomator dump /sdcard/bt_refresh.xml >/dev/null 2>&1 && cat /sdcard/bt_refresh.xml",
            timeout=5.0,
        )
        w, h = self.android.sync_screen_bounds()
        if "<hierarchy" in xml_raw:
            try:
                root = ET.fromstring(xml_raw[xml_raw.index("<hierarchy") :])
                for node in root.iter("node"):
                    desc = (node.attrib.get("content-desc") or "").strip().lower()
                    res_id = (node.attrib.get("resource-id") or "").strip().lower()
                    text = (node.attrib.get("text") or "").strip().lower()
                    bounds = node.attrib.get("bounds", "")
                    if any(k in desc or k in res_id for k in ("refresh", "atualizar", "scanning_progress", "action_refresh")):
                        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                        if m:
                            x1, y1, x2, y2 = map(int, m.groups())
                            self._safe_tap((x1 + x2) // 2, (y1 + y2) // 2)
                            return
                    if text in ("available devices", "dispositivos disponíveis"):
                        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                        if m:
                            _, y1, _, y2 = map(int, m.groups())
                            self._safe_tap(int(w * 0.89), (y1 + y2) // 2)
                            return
            except Exception:
                pass
        self._safe_tap(int(w * 0.89), int(h * 0.40))

    def scan_bluetooth_devices(self, open_rarely_used: bool = False) -> Dict[str, Any]:
        """
        Ativa o Bluetooth no Redmi Note 8 Pro, abre a tela `BLUETOOTH_SETTINGS`
        (que inicia automaticamente a descoberta Bluetooth) e lista todos os controles encontrados.
        """
        self._run_adb(
            "cmd statusbar collapse; "
            "svc bluetooth enable; "
            "settings put secure location_mode 3; "
            "am start --activity-clear-top -a android.settings.BLUETOOTH_SETTINGS",
            timeout=5.0,
        )
        time.sleep(3.5)

        # Só clica no ícone de atualizar se o adaptador não entrou em Discovering automaticamente
        bt_dump = self._run_adb("dumpsys bluetooth_manager | grep -i 'Discovering:'", timeout=3.0)
        if "Discovering: false" in bt_dump and not open_rarely_used:
            self._tap_bluetooth_refresh()
            time.sleep(1.8)

        if open_rarely_used:
            items = self._get_bluetooth_screen_items()
            rare = next((it for it in items if it.get("is_group")), None)
            if rare and "tap_x" in rare:
                self._safe_tap(int(rare["tap_x"]), int(rare["tap_y"]))
                time.sleep(1.2)

        status = self.get_bluetooth_status()
        status["message"] = (
            "Bluetooth scan active on Redmi Note 8 Pro! Put your Bluetooth controller in pairing mode "
            "(e.g., hold START+X / HOME / SHARE+PS until the LED flashes rapidly) and tap Pair below."
        )
        return status

    def pair_or_connect_device(self, target_query: str) -> Dict[str, Any]:
        """
        Toca no controle Bluetooth desejado na lista do Android e confirma automaticamente
        o diálogo 'Pair / Parear / OK' caso apareça na tela!
        """
        items = self._get_bluetooth_screen_items()
        if not items:
            self._run_adb(
                "cmd statusbar collapse; svc bluetooth enable; "
                "am start --activity-clear-top -a android.settings.BLUETOOTH_SETTINGS",
                timeout=4.0,
            )
            time.sleep(1.0)
            items = self._get_bluetooth_screen_items()

        q = (target_query or "").strip().lower()
        chosen = next(
            (it for it in items if q and (q in it["name"].lower() or q in it["id"].lower())),
            None,
        )
        if not chosen and items:
            # Evita clicar em "Rarely used devices" por engano se não foi pedido
            non_group = [it for it in items if not it.get("is_group")]
            chosen = non_group[0] if non_group else items[0]

        if chosen and "tap_x" in chosen and "tap_y" in chosen:
            self._safe_tap(int(chosen["tap_x"]), int(chosen["tap_y"]))
            time.sleep(1.5)
            # Se for o grupo "Rarely used devices", lê os dispositivos dentro dele
            if chosen.get("is_group"):
                sub_status = self.get_bluetooth_status()
                return {
                    "ok": True,
                    "message": f"Opened '{chosen['name']}' list! Select your controller below:",
                    "devices": sub_status["devices"],
                }

            # Verifica até 2 vezes se a caixa de confirmação de pareamento ("Pair" / "Parear") apareceu
            paired_confirmed = False
            for _ in range(2):
                if self._confirm_bluetooth_pair_dialog():
                    paired_confirmed = True
                    break
                time.sleep(1.0)

            status = self.get_bluetooth_status()
            msg = (
                f"✅ Pairing automatically confirmed with '{chosen['name']}'!"
                if paired_confirmed
                else f"📡 Connection/pairing request sent to '{chosen['name']}'!"
            )
            return {
                "ok": True,
                "message": msg,
                "device": chosen,
                "devices": status["devices"],
            }

        return {
            "ok": False,
            "message": (
                f"Device '{target_query}' not found on the current screen. "
                "Tap '🔍 Scan Bluetooth Controllers' while your controller is flashing in pairing mode."
            ),
        }

    def _confirm_bluetooth_pair_dialog(self) -> bool:
        """Procura e clica automaticamente no botão 'Pair / Parear / OK / Conectar' do diálogo Bluetooth."""
        xml_raw = self._run_adb(
            "uiautomator dump /sdcard/bt_pair_confirm.xml >/dev/null 2>&1 && cat /sdcard/bt_pair_confirm.xml",
            timeout=4.0,
        )
        if "<hierarchy" not in xml_raw:
            return False
        try:
            root = ET.fromstring(xml_raw[xml_raw.index("<hierarchy") :])
            # Primeiro marca eventual checkbox de permissão se existir e depois clica no botão positivo
            confirm_words = {"pair", "parear", "ok", "connect", "conectar", "accept", "aceitar", "allow", "permitir"}
            confirm_res_ids = {"android:id/button1", "miui:id/button1"}
            for node in root.iter("node"):
                txt = (node.attrib.get("text") or "").strip().lower()
                res_id = node.attrib.get("resource-id", "")
                if txt in confirm_words or res_id in confirm_res_ids:
                    bounds = node.attrib.get("bounds", "")
                    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                    if m:
                        x1, y1, x2, y2 = map(int, m.groups())
                        self._safe_tap((x1 + x2) // 2, (y1 + y2) // 2)
                        return True
        except Exception:
            pass
        return False

    # ==================== EMULATORS & ROMS HUB ====================

    def get_games_status(self) -> Dict[str, Any]:
        """Retorna lista de emuladores (instalados e disponíveis), ROMs no celular e controles Bluetooth."""
        if not self._initialized_sdcard:
            threading.Thread(
                target=self.ensure_rom_directories_and_permissions, daemon=True
            ).start()

        combined_out = self._run_adb(
            "pm list packages 2>/dev/null; "
            "echo '===ROMS_LIST==='; "
            "ls -1 /sdcard/ROMs/snes 2>/dev/null | sed 's/^/snes:/'; "
            "ls -1 /sdcard/ROMs/mame 2>/dev/null | sed 's/^/mame:/'; "
            "ls -1 /sdcard/ROMs/megadrive 2>/dev/null | sed 's/^/megadrive:/'",
            timeout=5.0,
        )
        if "===ROMS_LIST===" in combined_out:
            pkgs_out, roms_out = combined_out.split("===ROMS_LIST===", 1)
        else:
            pkgs_out, roms_out = combined_out, ""

        installed_pkgs = {
            line.replace("package:", "").strip()
            for line in pkgs_out.splitlines()
            if line.startswith("package:")
        }

        emulators: List[Dict[str, Any]] = []
        for emu_id, info in EMULATORS_CATALOG.items():
            alt_pkgs = info.get("alt_packages", [])
            is_inst = info["package"] in installed_pkgs or any(
                p in installed_pkgs for p in alt_pkgs
            )
            emulators.append(
                {
                    **info,
                    "installed": is_inst,
                }
            )

        # Lista ROMs no celular (/sdcard/ROMs/snes, /sdcard/ROMs/mame, /sdcard/ROMs/megadrive) + locais
        try:
            from scripts.install_game_packs import ROM_TITLES_MAP, get_rom_metadata
        except Exception:
            ROM_TITLES_MAP = {}
            get_rom_metadata = None

        valid_rom_exts = {
            ".sfc",
            ".smc",
            ".fig",
            ".md",
            ".bin",
            ".gen",
            ".smd",
            ".zip",
            ".7z",
            ".nes",
            ".gba",
        }
        ignored_rom_names = {"neogeo.zip", "puzzledp.zip"}
        ignored_substrings = (
            ".0a.",
            ".frz",
            ".srm",
            ".sta",
            ".memcard",
            ".nv",
            ".gp",
            ".sav",
            ".state",
            ".oops",
        )

        def _is_playable_rom(filename: str) -> bool:
            low = filename.strip().lower()
            if not low or low.startswith(".") or low in ignored_rom_names:
                return False
            if any(sub in low for sub in ignored_substrings):
                return False
            _, ext = os.path.splitext(low)
            return ext in valid_rom_exts

        def _build_rom_entry(
            sys_name: str, fname: str, local_exists: bool, size_kb: Optional[float]
        ) -> Dict[str, Any]:
            if get_rom_metadata is not None:
                meta = get_rom_metadata(sys_name, fname)
            else:
                meta = {
                    "title": ROM_TITLES_MAP.get(fname.lower(), fname),
                    "subtitle": sys_name.upper(),
                    "genre": "Arcade / Retro",
                    "console_badge": sys_name.upper(),
                    "icon": "🎮",
                    "accent_color": "#38bdf8",
                    "cover_svg": "",
                    "cover_url": "",
                }
            return {
                "system": sys_name,
                "filename": fname,
                "title": meta.get("title", fname),
                "subtitle": meta.get("subtitle", sys_name.upper()),
                "genre": meta.get("genre", "Arcade / Retro"),
                "console_badge": meta.get("console_badge", sys_name.upper()),
                "icon": meta.get("icon", "🎮"),
                "accent_color": meta.get("accent_color", "#38bdf8"),
                "cover_svg": meta.get("cover_svg", ""),
                "cover_url": meta.get("cover_url", ""),
                "is_bios": False,
                "size_kb": size_kb,
                "sdcard_path": f"/sdcard/ROMs/{sys_name}/{fname}",
                "web_url": f"/roms/{sys_name}/{fname}" if local_exists else None,
            }
        roms: List[Dict[str, Any]] = []
        seen_roms = set()
        for line in roms_out.splitlines():
            if ":" not in line:
                continue
            sys_name, fname = line.split(":", 1)
            fname = fname.strip()
            if not _is_playable_rom(fname):
                continue
            key = f"{sys_name}:{fname}"
            seen_roms.add(key)
            local_file = self.roms_dir / sys_name / fname
            local_exists = local_file.exists()
            size_kb = round(local_file.stat().st_size / 1024, 1) if local_exists else None
            roms.append(_build_rom_entry(sys_name, fname, local_exists, size_kb))

        for sys_name in ("snes", "mame", "megadrive"):
            folder = self.roms_dir / sys_name
            if folder.exists():
                for f in folder.iterdir():
                    if (
                        f.is_file()
                        and _is_playable_rom(f.name)
                        and f"{sys_name}:{f.name}" not in seen_roms
                    ):
                        seen_roms.add(f"{sys_name}:{f.name}")
                        roms.append(
                            _build_rom_entry(
                                sys_name,
                                f.name,
                                True,
                                round(f.stat().st_size / 1024, 1),
                            )
                        )

        sys_order = {"mame": 0, "snes": 1, "megadrive": 2}
        roms.sort(
            key=lambda r: (
                sys_order.get(r["system"], 9),
                r.get("title", r["filename"]).lower(),
            )
        )

        return {
            "ok": True,
            "emulators": emulators,
            "roms": roms,
            "rom_count": len(roms),
            "rom_folders": {
                "snes": "/sdcard/ROMs/snes",
                "mame": "/sdcard/ROMs/mame",
                "megadrive": "/sdcard/ROMs/megadrive",
            },
        }

    def install_rom_pack(self, pack_id: str = "all") -> Dict[str, Any]:
        """Baixa o pack de jogos do GitHub/MAMEdev e sincroniza com `/sdcard/ROMs` no celular."""
        try:
            from scripts.install_game_packs import install_packs

            res = install_packs(pack_id=pack_id)
            self._initialized_sdcard = False
            self.ensure_rom_directories_and_permissions()
            return res
        except Exception as exc:
            return {"ok": False, "message": f"Failed to install game pack: {exc}"}

    def launch_rom(self, system: str, filename: str) -> Dict[str, Any]:
        """
        Abre uma ROM específica diretamente no emulador correspondente no celular/TV
        (`Snes9x EX+`, `NEO.emu`/`MAME4droid`, ou `MD.emu`), forçando orientação horizontal
        (Landscape 2340x1080) e reiniciando a instância anterior (`am start -S`) para carregar
        o jogo imediatamente sem parar no menu `Open Content`.
        """
        sys_clean = (system or "snes").strip().lower()
        safe_name = os.path.basename(filename or "")
        sdcard_path = f"/sdcard/ROMs/{sys_clean}/{safe_name}"
        if not self._initialized_sdcard:
            threading.Thread(
                target=self.ensure_rom_directories_and_permissions, daemon=True
            ).start()
        self.android.ensure_ghost_touch_shield()
        self.android.active_emulator = sys_clean
        self.android.in_emulator_menu = False

        emu_map = {
            "snes": "snes9x",
            "mame": "neoemu",
            "megadrive": "mdemu",
        }
        emu_id = emu_map.get(sys_clean, "lemuroid")
        info = EMULATORS_CATALOG[emu_id]
        act = info["activity"]
        pkg = info["package"]

        try:
            from scripts.install_game_packs import get_rom_metadata

            meta = get_rom_metadata(sys_clean, safe_name)
        except Exception:
            meta = {
                "title": safe_name,
                "subtitle": sys_clean.upper(),
                "genre": "Arcade / Retro",
                "console_badge": sys_clean.upper(),
                "icon": "🎮",
                "accent_color": "#38bdf8",
                "cover_url": "",
            }
        pretty_title = meta.get("title") or safe_name

        # Atualiza também o controle ativo para o sistema correspondente (Jogador 1)
        skin_for_sys = {
            "snes": "snes",
            "mame": "mame",
            "megadrive": "megadrive",
        }.get(sys_clean, "snes")
        for c in self.controllers:
            if c.get("skin_id") == skin_for_sys and c.get("player") == 1:
                self.active_controller_id = c["id"]
                break

        launch_cmd = (
            "input keyevent KEYCODE_WAKEUP 2>/dev/null; wm dismiss-keyguard 2>/dev/null; "
            "settings put system accelerometer_rotation 0 2>/dev/null; "
            "settings put system user_rotation 1 2>/dev/null; "
            "content insert --uri content://settings/system --bind name:s:accelerometer_rotation --bind value:i:0 2>/dev/null; "
            "content insert --uri content://settings/system --bind name:s:user_rotation --bind value:i:1 2>/dev/null; "
            f'/system/bin/am start -S --user 0 -n {act} -a android.intent.action.VIEW -d "file://{sdcard_path}" >/dev/null 2>&1 || '
            f"/system/bin/am start --user 0 -n {act} >/dev/null 2>&1 || "
            f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1"
        )
        self._run_adb(launch_cmd, timeout=6.0)
        return {
            "ok": True,
            "system": sys_clean,
            "filename": safe_name,
            "title": pretty_title,
            "subtitle": meta.get("subtitle", ""),
            "genre": meta.get("genre", ""),
            "console_badge": meta.get("console_badge", sys_clean.upper()),
            "icon": meta.get("icon", "🎮"),
            "accent_color": meta.get("accent_color", "#38bdf8"),
            "cover_url": meta.get("cover_url", ""),
            "emulator": info,
            "message": f"🎮 '{pretty_title}' launched on TV/Projector via {info['name']}! Controller synced.",
        }

    def launch_emulator(self, emu_id: str) -> Dict[str, Any]:
        """Abre um emulador instalado no Redmi Note 8 Pro em modo Paisagem (Landscape) e garante permissões."""
        if emu_id not in EMULATORS_CATALOG:
            return {"ok": False, "message": f"Unknown emulator '{emu_id}'."}

        info = EMULATORS_CATALOG[emu_id]
        pkg = info["package"]
        act = info["activity"]
        emu_sys_map = {
            "snes9x": "snes",
            "neoemu": "mame",
            "mame4droid": "mame4droid",
            "mdemu": "megadrive",
            "lemuroid": "lemuroid",
        }
        self.android.active_emulator = emu_sys_map.get(emu_id, "snes")
        self.android.in_emulator_menu = True
        if not self._initialized_sdcard:
            threading.Thread(
                target=self.ensure_rom_directories_and_permissions, daemon=True
            ).start()
        self.android.ensure_ghost_touch_shield()
        self._run_adb(
            "settings put system accelerometer_rotation 0 2>/dev/null; "
            "settings put system user_rotation 1 2>/dev/null",
            timeout=3.0,
        )
        chain = [
            f"/system/bin/am start --user 0 -n {act}",
            f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1",
            f"monkey -p {pkg} -c android.intent.category.LEANBACK_LAUNCHER 1",
        ]
        for alt_pkg in info.get("alt_packages", []):
            chain.append(f"monkey -p {alt_pkg} -c android.intent.category.LAUNCHER 1")
        self.android.run_fallback_chain(chain)
        return {
            "ok": True,
            "message": f"🎮 {info['name']} opened on Redmi Note 8 Pro! Use the Virtual Gamepad or your Bluetooth Controller.",
            "emulator": info,
        }

    def install_emulator(self, emu_id: str) -> Dict[str, Any]:
        """Baixa o APK oficial do GitHub (se ainda não estiver em cache) e instala via `adb install -r`."""
        if emu_id not in EMULATORS_CATALOG:
            return {"ok": False, "message": f"Emulator '{emu_id}' not found in catalog."}

        info = EMULATORS_CATALOG[emu_id]
        adb_bin = self.android._find_adb()
        if not adb_bin:
            return {"ok": False, "message": "ADB binary not found on the server."}

        target_dir = self.apks_dir / emu_id
        target_dir.mkdir(parents=True, exist_ok=True)

        # Verifica se já temos um .apk baixado em cache
        cached_apks = list(target_dir.glob("*.apk"))
        if not cached_apks and emu_id == "snes9x":
            cached_apks = list((self.apks_dir / "snes9x").glob("*.apk"))
        if not cached_apks and emu_id == "lemuroid" and (self.apks_dir / "Lemuroid.apk").exists():
            cached_apks = [self.apks_dir / "Lemuroid.apk"]

        apk_path: Optional[Path] = cached_apks[0] if cached_apks else None

        if not apk_path:
            url = info["download_url"]
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "HybridBox-PWA/1.0"})
                if info["is_zip"]:
                    zip_path = target_dir / f"{emu_id}.zip"
                    with urllib.request.urlopen(req, timeout=45.0) as resp, open(zip_path, "wb") as out_f:
                        shutil.copyfileobj(resp, out_f)
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        zf.extractall(target_dir)
                    found = list(target_dir.rglob("*.apk"))
                    if found:
                        apk_path = found[0]
                else:
                    apk_path = target_dir / f"{emu_id}.apk"
                    with urllib.request.urlopen(req, timeout=90.0) as resp, open(apk_path, "wb") as out_f:
                        shutil.copyfileobj(resp, out_f)
            except Exception as exc:
                return {"ok": False, "message": f"Failed to download APK from GitHub: {exc}"}

        if not apk_path or not apk_path.exists():
            return {"ok": False, "message": "APK file not found after download."}

        try:
            res = self.android.run_adb_cmd(["install", "-r", str(apk_path)], timeout=90.0)
            if res is not None and "Success" in (res.stdout or ""):
                self._initialized_sdcard = False
                self.ensure_rom_directories_and_permissions()
                return {
                    "ok": True,
                    "message": f"✅ {info['name']} installed on Redmi Note 8 Pro!",
                }
            err_msg = (res.stderr or res.stdout or "").strip() if res else "Failed to invoke ADB"
            return {
                "ok": False,
                "message": f"ADB installation failed: {err_msg}",
            }
        except Exception as exc:
            return {"ok": False, "message": f"Error executing adb install: {exc}"}

    def save_and_push_rom(self, system: str, filename: str, content: bytes) -> Dict[str, Any]:
        """Salva uma ROM enviada pelo navegador em `roms/<system>/` e envia via cópia local, `adb push` ou `scp` para `/sdcard/ROMs/<system>/`."""
        sys_clean = system.strip().lower()
        if sys_clean not in ("snes", "mame", "megadrive"):
            sys_clean = "snes"

        safe_name = re.sub(r"[^A-Za-z0-9_\-\.\(\)\[\]\s]", "_", os.path.basename(filename))
        if not safe_name:
            safe_name = "game.sfc"

        local_folder = self.roms_dir / sys_clean
        local_folder.mkdir(parents=True, exist_ok=True)
        local_path = local_folder / safe_name
        local_path.write_bytes(content)

        self.ensure_rom_directories_and_permissions()
        remote_path = f"/sdcard/ROMs/{sys_clean}/{safe_name}"
        pushed = False

        # 1. Cópia direta se rodando localmente no próprio Android/Termux
        if os.path.exists(f"/sdcard/ROMs/{sys_clean}"):
            try:
                shutil.copyfile(str(local_path), remote_path)
                if sys_clean == "mame" and os.path.exists("/sdcard/MAME4droid/roms"):
                    shutil.copyfile(str(local_path), f"/sdcard/MAME4droid/roms/{safe_name}")
                pushed = True
            except Exception:
                pass

        # 2. Envio via ADB (USB ou Wi-Fi 5555)
        if not pushed:
            res = self.android.run_adb_cmd(["push", str(local_path), remote_path], timeout=30.0)
            pushed = bool(res is not None and res.returncode == 0)
            if pushed and sys_clean == "mame":
                self.android.run_adb_cmd(
                    ["push", str(local_path), f"/sdcard/MAME4droid/roms/{safe_name}"],
                    timeout=30.0,
                )

        # 3. Fallback Wi-Fi SCP (porta 8022) caso ADB esteja indisponível
        if not pushed:
            scp_bin = shutil.which("scp")
            if scp_bin:
                try:
                    phone_ip = self.android.discover_phone_ip()
                    scp_res = subprocess.run(
                        [
                            scp_bin,
                            "-P",
                            str(self.android.ssh_port),
                            "-o",
                            "BatchMode=yes",
                            "-o",
                            "StrictHostKeyChecking=no",
                            str(local_path),
                            f"{self.android.ssh_user}@{phone_ip}:{remote_path}",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30.0,
                    )
                    pushed = scp_res.returncode == 0
                except Exception:
                    pass

        return {
            "ok": True,
            "pushed_to_phone": pushed,
            "system": sys_clean,
            "filename": safe_name,
            "sdcard_path": remote_path,
            "web_url": f"/roms/{sys_clean}/{safe_name}",
            "message": (
                f"✅ ROM '{safe_name}' pushed to {remote_path} on Redmi Note 8 Pro and ready to play!"
                if pushed
                else f"✅ ROM '{safe_name}' saved on server (ready for EmulatorJS)!"
            ),
        }

    # ==================== MULTI-CONTROLLERS & SKINS MANAGER ====================

    def get_controllers_config(self, host_ip: str = "hybridbox.local") -> Dict[str, Any]:
        """Retorna lista de skins/fotos de controles disponíveis, perfis de controles adicionados e links Multiplayer."""
        active_ctrl = next(
            (c for c in self.controllers if c["id"] == self.active_controller_id),
            self.controllers[0],
        )
        multiplayer_links = {
            f"player_{p}": f"http://{host_ip}:8080/?mode=games&player={p}&skin=snes&fullscreen=1"
            for p in (1, 2, 3, 4)
        }
        return {
            "ok": True,
            "skins": CONTROLLER_SKINS_CATALOG,
            "controllers": self.controllers,
            "active_controller_id": self.active_controller_id,
            "active_controller": active_ctrl,
            "multiplayer_links": multiplayer_links,
        }

    def manage_controllers(
        self, action: str, payload: Dict[str, Any], host_ip: str = "hybridbox.local"
    ) -> Dict[str, Any]:
        """Adiciona, seleciona ou remove controles virtuais/multiplayer."""
        act = (action or "select").strip().lower()
        skin_map = {s["skin_id"]: s for s in CONTROLLER_SKINS_CATALOG}

        if act == "add":
            skin_id = str(payload.get("skin_id") or "snes").strip().lower()
            if skin_id not in skin_map:
                skin_id = "snes"
            skin_info = skin_map[skin_id]
            player = max(1, min(4, int(payload.get("player") or 2)))
            custom_name = str(payload.get("name") or "").strip()
            if not custom_name:
                custom_name = f"Controller {player} • {skin_info['short_name']} (P{player})"
            new_id = f"ctrl_{skin_id}_p{player}_{int(time.time() * 1000) % 100000}"
            new_ctrl = {
                "id": new_id,
                "name": custom_name,
                "skin_id": skin_id,
                "system": skin_info["system"],
                "player": player,
                "icon": skin_info["icon"],
                "photo_url": skin_info["photo_url"],
                "builtin": False,
            }
            self.controllers.append(new_ctrl)
            self.active_controller_id = new_id
            if skin_info["system"] in ("snes", "mame", "megadrive"):
                self.android.active_emulator = skin_info["system"]
            msg = f"✅ New controller '{custom_name}' added and activated!"

        elif act == "remove":
            ctrl_id = str(payload.get("controller_id") or "").strip()
            before_len = len(self.controllers)
            self.controllers = [
                c for c in self.controllers if c.get("builtin") or c["id"] != ctrl_id
            ]
            if not any(c["id"] == self.active_controller_id for c in self.controllers):
                self.active_controller_id = self.controllers[0]["id"]
            msg = (
                "🗑️ Controller removed from list!"
                if len(self.controllers) < before_len
                else "⚠️ Built-in system controllers cannot be removed."
            )

        else:
            # select by controller_id, exact name, or (skin_id, player)
            ctrl_id = str(payload.get("controller_id") or "").strip()
            skin_id = str(payload.get("skin_id") or "").strip().lower()
            player = int(payload.get("player") or 0)
            req_name = str(payload.get("name") or "").strip()
            matched = None
            if ctrl_id:
                matched = next((c for c in self.controllers if c["id"] == ctrl_id), None)
            if not matched and req_name:
                matched = next(
                    (
                        c
                        for c in self.controllers
                        if c["name"] == req_name
                        and (not skin_id or c["skin_id"] == skin_id)
                        and (not player or c["player"] == player)
                    ),
                    None,
                )
            if not matched and skin_id:
                matched = next(
                    (
                        c
                        for c in self.controllers
                        if c["skin_id"] == skin_id and (not player or c["player"] == player)
                    ),
                    None,
                )
                if not matched and skin_id in skin_map:
                    s_info = skin_map[skin_id]
                    p_num = max(1, min(4, player or 1))
                    matched = {
                        "id": f"ctrl_{skin_id}_p{p_num}",
                        "name": req_name or f"Controller {p_num} • {s_info['short_name']}",
                        "skin_id": skin_id,
                        "system": s_info["system"],
                        "player": p_num,
                        "icon": s_info["icon"],
                        "photo_url": s_info["photo_url"],
                        "builtin": False,
                    }
                    self.controllers.append(matched)
            if matched:
                self.active_controller_id = matched["id"]
                if matched.get("system") in ("snes", "mame", "megadrive"):
                    self.android.active_emulator = matched["system"]
                msg = f"🎮 Active controller: {matched['name']}!"
            else:
                msg = "🎮 Controller updated!"

        res = self.get_controllers_config(host_ip=host_ip)
        res["message"] = msg
        return res
