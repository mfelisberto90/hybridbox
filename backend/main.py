"""
Servidor Principal FastAPI + WebSockets do HybridBox Remote PWA.
Hospeda o PWA instalável e roteia comandos de controle remoto / trackpad / teclado
com latência zero entre Android TV Box (ADB Loopback) e Linux Desktop (Termux:X11).
"""

import asyncio
import base64
import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.android_controller import AndroidController
from backend.app_registry import ANDROID_APPS, LINUX_APPS, get_all_apps
from backend.bluetooth_gaming_controller import BluetoothGamingController
from backend.cache_manager import get_cache_manager
from backend.memory_janitor import MemoryJanitor
from backend.projector_controller import ProjectorController
from backend.ssh_terminal_controller import SshTerminalController
from backend.wifi_portable_controller import WifiPortableController
from backend.x11_controller import X11Controller

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
ROMS_DIR = BASE_DIR / "roms"
ROMS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="HybridBox Remote PWA",
    description="Controle Remoto Híbrido (Android TV Box + Linux XFCE4 Desktop) para Redmi Note 8 Pro",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_local_ip() -> str:
    """Descobre o IP da rede Wi-Fi local para exibir no painel/terminal (mesmo sem internet)."""
    try:
        from backend.wifi_portable_controller import MdnsZeroConfService

        ip = MdnsZeroConfService.get_local_bind_ip()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


class HybridBoxState:
    def __init__(self) -> None:
        self.mode: str = "tv"  # "tv", "linux" ou "games"
        self.cache = get_cache_manager()
        self.android = AndroidController(adb_serial="127.0.0.1:5555")
        self.x11 = X11Controller(display_name=":0", android_controller=self.android)
        self.projector = ProjectorController(self.android)
        self.wifi = WifiPortableController(self.android, BASE_DIR)
        self.gaming = BluetoothGamingController(self.android, BASE_DIR)
        self.ssh_terminal = SshTerminalController(self.android, BASE_DIR)
        self.janitor = MemoryJanitor(base_dir=BASE_DIR)
        self.janitor.start()
        self.clients: Set[WebSocket] = set()


state = HybridBoxState()


class ModeRequest(BaseModel):
    mode: str


class LaunchRequest(BaseModel):
    app_id: str


class ProjectorConnectRequest(BaseModel):
    target: str = ""
    target_name: str = ""
    auto_connect: bool = True


class ProjectorDisplayModeRequest(BaseModel):
    mode: str = "clone"


class DlnaCastRequest(BaseModel):
    control_url: str
    media_url: str


class WifiConnectRequest(BaseModel):
    ssid: str
    password: str = ""
    security: str = "wpa2"
    save_only: bool = False


class WifiRescueHotspotRequest(BaseModel):
    ssid: str = "HybridBox"
    password: str = "hybridbox123"
    security: str = "wpa2"
    auto_connect: bool = True
    connect_now: bool = False


class BluetoothScanRequest(BaseModel):
    open_rarely_used: bool = False


class BluetoothPairRequest(BaseModel):
    target: str = ""


class EmulatorActionRequest(BaseModel):
    emulator_id: str


class RomUploadRequest(BaseModel):
    system: str = "snes"
    filename: str
    data_base64: str


class RomPackInstallRequest(BaseModel):
    pack_id: str = "all"


class RomLaunchRequest(BaseModel):
    system: str = "snes"
    filename: str


class ControllerManageRequest(BaseModel):
    action: str = "select"  # "select" | "add" | "remove"
    controller_id: str = ""
    skin_id: str = "snes"
    player: int = 1
    name: str = ""


class SshExecRequest(BaseModel):
    command: str
    target: str = "android"


class StandbyRequest(BaseModel):
    standby: Optional[bool] = None
    auto_standby_minutes: Optional[int] = None
    reason: str = "manual"


class KeyActionRequest(BaseModel):
    key: str
    target: str = ""


async def broadcast_state() -> None:
    """Notifica todos os smartphones conectados sobre mudança de modo, Eco-Standby e bateria."""
    bat = state.android.get_battery_and_health()
    standby_info = state.android.get_standby_state()
    payload = json.dumps(
        {
            "type": "state",
            "mode": state.mode,
            "x11_backend": state.x11.backend_name,
            "android_backend": state.android.backend_name,
            "phone_online": bat.get("phone_online", True),
            "battery": bat,
            "standby_mode": state.android.standby_mode,
            "standby": standby_info,
        }
    )
    dead: List[WebSocket] = []
    for ws in list(state.clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        state.clients.discard(ws)


def apply_mode_switch(target_mode: str) -> str:
    """Alterna entre Android TV Box, Linux Desktop (Termux:X11) e Console de Games."""
    normalized = target_mode.strip().lower()
    if normalized not in ("tv", "linux", "games"):
        raise ValueError("Modo inválido. Use 'tv', 'linux' ou 'games'.")

    state.android.touch_activity(wake_if_standby=True)
    state.mode = normalized
    if normalized == "linux":
        state.cache.set_game_mode(False)
        state.android.switch_to_linux_desktop()
    elif normalized == "games":
        state.cache.set_game_mode(True)
        state.android.switch_to_games_hub()
    else:
        state.cache.set_game_mode(False)
        state.android.switch_to_tv_box()
    return state.mode


def execute_app_launch(app_id: str) -> Dict[str, Any]:
    """Abre um aplicativo do catálogo Android TV, Linux Desktop ou Games."""
    state.android.touch_activity(wake_if_standby=True)
    if app_id in ANDROID_APPS:
        app_info = ANDROID_APPS[app_id]
        if app_id == "displaylink":
            res = state.projector.open_hdmi_displaylink()
            return {
                "ok": True,
                "launched": app_info["name"],
                "mode": state.mode,
                "message": res.get("message", ""),
            }
        if app_info["category"] == "games":
            state.cache.set_game_mode(True)
            state.gaming.ensure_rom_directories_and_permissions()
            emu_sys_map = {
                "snes9x": "snes",
                "neoemu": "mame",
                "mame4droid": "mame4droid",
                "mdemu": "megadrive",
                "lemuroid": "lemuroid",
            }
            if app_id in emu_sys_map:
                state.android.active_emulator = emu_sys_map[app_id]
        state.android.run_fallback_chain(app_info["commands"])
        if app_id == "termux_x11":
            state.mode = "linux"
        elif app_info["category"] == "games":
            state.mode = "games"
        elif app_info["category"] == "tv":
            state.mode = "tv"
        return {"ok": True, "launched": app_info["name"], "mode": state.mode}

    if app_id in LINUX_APPS:
        app_info = LINUX_APPS[app_id]
        state.mode = "linux"
        state.android.switch_to_linux_desktop()
        state.x11.launch_linux_command(app_info["command"])
        return {"ok": True, "launched": app_info["name"], "mode": state.mode}

    raise KeyError(f"Aplicativo '{app_id}' não encontrado.")


def dispatch_dpad_key(key: str, target_mode: str) -> None:
    """Roteia comando D-Pad / mídia de acordo com o modo ativo (`tv`, `linux` ou `games`)."""
    state.android.touch_activity(wake_if_standby=True)
    if key in ("VOL_UP", "VOL_DOWN", "MUTE", "PLAY_PAUSE", "PREV", "NEXT"):
        state.android.send_key(key)
    elif target_mode == "games" and key in ("UP", "DOWN", "LEFT", "RIGHT", "OK"):
        state.android.send_gamepad_key(key)
    elif target_mode == "linux":
        linux_dpad_map = {
            "UP": "Up",
            "DOWN": "Down",
            "LEFT": "Left",
            "RIGHT": "Right",
            "OK": "Return",
            "BACK": "Escape",
            "HOME": "Super_L",
        }
        state.x11.send_key(linux_dpad_map.get(key, key))
    else:
        state.android.send_key(key)


@app.get("/api/status")
async def api_status() -> JSONResponse:
    bat = state.android.get_battery_and_health()
    standby_info = state.android.get_standby_state()
    return JSONResponse(
        {
            "ok": True,
            "mode": state.mode,
            "ip": get_local_ip(),
            "phone_ip": state.wifi.get_best_phone_ip(),
            "mdns_url": "http://hybridbox.local:8080",
            "x11_backend": state.x11.backend_name,
            "android_backend": state.android.backend_name,
            "phone_online": bat.get("phone_online", True),
            "battery": bat,
            "standby_mode": state.android.standby_mode,
            "standby": standby_info,
            "apps": get_all_apps(),
        }
    )


@app.get("/api/battery")
async def api_battery(force: bool = False) -> JSONResponse:
    if force:
        bat = await asyncio.to_thread(state.android.get_battery_and_health, True)
    else:
        bat = state.android.get_battery_and_health(force=False)
    return JSONResponse(
        {
            "ok": True,
            "battery": bat,
            "standby_mode": state.android.standby_mode,
            "standby": state.android.get_standby_state(),
        }
    )


@app.get("/api/system/standby")
async def api_system_standby_get() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "standby_mode": state.android.standby_mode,
            "standby": state.android.get_standby_state(),
            "mode": state.mode,
        }
    )


@app.post("/api/system/standby")
async def api_system_standby_post(req: StandbyRequest) -> JSONResponse:
    if req.standby is None and req.auto_standby_minutes is not None:
        state.android.auto_standby_minutes = max(0, int(req.auto_standby_minutes))
        state.android._save_runtime_cache(
            auto_standby_minutes=state.android.auto_standby_minutes
        )
        standby_info = state.android.get_standby_state()
        await broadcast_state()
        return JSONResponse(
            {
                "ok": True,
                "standby_mode": state.android.standby_mode,
                "standby": standby_info,
                "mode": state.mode,
                "message": (
                    f"⏱️ Auto-Hibernation timer set to {state.android.auto_standby_minutes} min."
                    if state.android.auto_standby_minutes > 0
                    else "⏱️ Auto-Hibernation timer disabled (Manual only)."
                ),
            }
        )

    target_standby = (
        (not state.android.standby_mode) if req.standby is None else bool(req.standby)
    )
    res = await asyncio.to_thread(
        state.android.set_standby_mode,
        target_standby,
        req.reason or "manual",
        req.auto_standby_minutes,
    )
    if not res.get("standby_mode"):
        state.mode = "tv"
    res["mode"] = state.mode
    await broadcast_state()
    return JSONResponse(res)


@app.post("/api/system/revive")
async def api_system_revive() -> JSONResponse:
    res = await asyncio.to_thread(state.android.revive_phone_connection)
    await broadcast_state()
    return JSONResponse(res)


@app.get("/api/system/memory")
async def api_system_memory() -> JSONResponse:
    """Retorna estatísticas detalhadas de memória RAM, cache e status do Janitor."""
    return JSONResponse(
        {
            "ok": True,
            "cache": state.cache.get_stats(),
            "janitor": state.janitor.get_status(),
        }
    )


@app.post("/api/system/cache/clear")
async def api_system_cache/clear() -> JSONResponse:
    """Limpa o cache em memória e dispara ciclo manual de higienização do Janitor."""
    state.cache.clear()
    clean_stats = await asyncio.to_thread(state.janitor.run_clean_cycle)
    return JSONResponse(
        {
            "ok": True,
            "cleaned": clean_stats,
            "cache": state.cache.get_stats(),
        }
    )


@app.post("/api/mode")
async def api_set_mode(req: ModeRequest) -> JSONResponse:
    try:
        new_mode = await asyncio.to_thread(apply_mode_switch, req.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await broadcast_state()
    return JSONResponse({"ok": True, "mode": new_mode})


@app.post("/api/launch")
async def api_launch(req: LaunchRequest) -> JSONResponse:
    try:
        result = await asyncio.to_thread(execute_app_launch, req.app_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await broadcast_state()
    return JSONResponse(result)


@app.post("/api/dpad")
async def api_dpad(req: KeyActionRequest) -> JSONResponse:
    target_mode = req.target or state.mode
    dispatch_dpad_key(req.key, target_mode)
    return JSONResponse({"ok": True, "key": req.key, "mode": target_mode})


@app.post("/api/key")
async def api_key(req: KeyActionRequest) -> JSONResponse:
    target_mode = req.target or state.mode
    state.android.touch_activity(wake_if_standby=True)
    if target_mode == "linux":
        state.x11.send_key(req.key)
    else:
        state.android.send_key(req.key)
    return JSONResponse({"ok": True, "key": req.key, "mode": target_mode})


@app.get("/api/projector/status")
async def api_projector_status() -> JSONResponse:
    status = await asyncio.to_thread(state.projector.parse_miracast_status)
    return JSONResponse(
        {
            "ok": True,
            "wfd_enabled": status["wfd_enabled"],
            "scanning": status["scanning"],
            "active_display": status["active_display"],
            "display_mode": status.get("display_mode"),
            "projector_ip": status.get("projector_ip"),
            "devices": status["miracast_devices"],
        }
    )


@app.post("/api/projector/scan")
async def api_projector_scan(req: ProjectorConnectRequest) -> JSONResponse:
    res = await asyncio.to_thread(
        state.projector.scan_and_open_cast, req.auto_connect
    )
    return JSONResponse(res)


@app.post("/api/projector/connect")
async def api_projector_connect(req: ProjectorConnectRequest) -> JSONResponse:
    query = (req.target_name or req.target or "").strip()
    res = await asyncio.to_thread(state.projector.connect_device, query)
    return JSONResponse(res)


@app.post("/api/projector/disconnect")
async def api_projector_disconnect() -> JSONResponse:
    res = await asyncio.to_thread(state.projector.disconnect_device)
    return JSONResponse(res)


@app.post("/api/projector/display-mode")
async def api_projector_display_mode(req: ProjectorDisplayModeRequest) -> JSONResponse:
    res = await asyncio.to_thread(state.projector.set_windows_display_mode, req.mode)
    return JSONResponse(res)


@app.post("/api/projector/wake-phone")
async def api_projector_wake_phone() -> JSONResponse:
    res = await asyncio.to_thread(state.projector.wake_phone_screen, True)
    return JSONResponse(res)


@app.post("/api/projector/locate-ip")
async def api_projector_locate_ip() -> JSONResponse:
    lan_dev = await asyncio.to_thread(
        state.projector.discover_projector_network_device, True
    )
    status = await asyncio.to_thread(state.projector.parse_miracast_status, False)
    ip_found = (lan_dev or {}).get("ip") or status.get("projector_ip")
    return JSONResponse(
        {
            "ok": bool(ip_found),
            "projector_ip": ip_found,
            "device": lan_dev,
            "devices": status.get("miracast_devices", []),
            "message": (
                f"📍 Projector automatically located on Wi-Fi LAN at IP {ip_found}!"
                if ip_found
                else "⚠️ Projector did not respond on the Wi-Fi subnet."
            ),
        }
    )


@app.post("/api/projector/miui-cast")
async def api_projector_miui_cast() -> JSONResponse:
    res = await asyncio.to_thread(state.projector.open_miui_cast_with_screen_off)
    return JSONResponse(res)


@app.post("/api/projector/windows-cast")
async def api_projector_windows_cast() -> JSONResponse:
    res = await asyncio.to_thread(state.projector.open_windows_wireless_display)
    return JSONResponse(res)


@app.post("/api/projector/hdmi")
async def api_projector_hdmi() -> JSONResponse:
    res = await asyncio.to_thread(state.projector.open_hdmi_displaylink)
    return JSONResponse(res)


@app.post("/api/projector/dlna-cast")
async def api_projector_dlna_cast(req: DlnaCastRequest) -> JSONResponse:
    res = await asyncio.to_thread(
        state.projector.send_dlna_media_url, req.control_url, req.media_url
    )
    return JSONResponse(res)


# ==================== ENDPOINTS WI-FI PORTÁTIL & HOTSPOT DE RESGATE ====================


@app.get("/api/wifi/status")
async def api_wifi_status() -> JSONResponse:
    res = await asyncio.to_thread(state.wifi.get_wifi_status)
    return JSONResponse(res)


@app.get("/api/wifi/scan")
@app.post("/api/wifi/scan")
async def api_wifi_scan() -> JSONResponse:
    res = await asyncio.to_thread(state.wifi.scan_wifi_networks)
    return JSONResponse(res)


@app.post("/api/wifi/connect")
async def api_wifi_connect(req: WifiConnectRequest) -> JSONResponse:
    res = await asyncio.to_thread(
        state.wifi.connect_wifi_network,
        req.ssid,
        req.password,
        req.security,
        req.save_only,
    )
    return JSONResponse(res)


@app.get("/api/wifi/rescue-hotspot")
async def api_wifi_rescue_hotspot_get() -> JSONResponse:
    status = await asyncio.to_thread(state.wifi.get_wifi_status)
    return JSONResponse(
        {
            "ok": True,
            "rescue_hotspot": status.get("rescue_hotspot"),
            "mdns_url": status.get("mdns_url"),
            "ip": status.get("ip"),
        }
    )


@app.post("/api/wifi/rescue-hotspot")
async def api_wifi_rescue_hotspot_set(req: WifiRescueHotspotRequest) -> JSONResponse:
    res = await asyncio.to_thread(
        state.wifi.configure_rescue_hotspot,
        req.ssid,
        req.password,
        req.security,
        req.auto_connect,
        req.connect_now,
    )
    return JSONResponse(res)


# ==================== ENDPOINTS SESSÃO GAMES & BLUETOOTH ====================


@app.get("/api/games/status")
async def api_games_status() -> JSONResponse:
    res = await asyncio.to_thread(state.gaming.get_games_status)
    return JSONResponse(res)


@app.post("/api/games/launch")
async def api_games_launch(req: EmulatorActionRequest) -> JSONResponse:
    state.android.touch_activity(wake_if_standby=True)
    res = await asyncio.to_thread(state.gaming.launch_emulator, req.emulator_id)
    if res.get("ok"):
        state.mode = "games"
        await broadcast_state()
    return JSONResponse(res)


@app.post("/api/games/install")
async def api_games_install(req: EmulatorActionRequest) -> JSONResponse:
    res = await asyncio.to_thread(state.gaming.install_emulator, req.emulator_id)
    return JSONResponse(res)


@app.post("/api/games/upload-rom")
async def api_games_upload_rom(req: RomUploadRequest) -> JSONResponse:
    try:
        raw_b64 = req.data_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        content = base64.b64decode(raw_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Base64 inválido: {exc}") from exc

    res = await asyncio.to_thread(
        state.gaming.save_and_push_rom, req.system, req.filename, content
    )
    return JSONResponse(res)


@app.post("/api/games/install-pack")
async def api_games_install_pack(req: RomPackInstallRequest) -> JSONResponse:
    res = await asyncio.to_thread(state.gaming.install_rom_pack, req.pack_id)
    return JSONResponse(res)


@app.post("/api/games/launch-rom")
async def api_games_launch_rom(req: RomLaunchRequest) -> JSONResponse:
    state.android.touch_activity(wake_if_standby=True)
    res = await asyncio.to_thread(
        state.gaming.launch_rom, req.system, req.filename
    )
    if res.get("ok"):
        state.mode = "games"
        await broadcast_state()
    return JSONResponse(res)


@app.get("/api/games/controllers")
async def api_games_controllers_get() -> JSONResponse:
    host_label = os.environ.get("HYBRIDBOX_PUBLIC_HOST", "hybridbox.local")
    res = await asyncio.to_thread(state.gaming.get_controllers_config, host_label)
    return JSONResponse(res)


@app.post("/api/games/controllers")
async def api_games_controllers_manage(req: ControllerManageRequest) -> JSONResponse:
    host_label = os.environ.get("HYBRIDBOX_PUBLIC_HOST", "hybridbox.local")
    res = await asyncio.to_thread(
        state.gaming.manage_controllers,
        req.action,
        {
            "controller_id": req.controller_id,
            "skin_id": req.skin_id,
            "player": req.player,
            "name": req.name,
        },
        host_label,
    )
    return JSONResponse(res)


@app.get("/api/bluetooth/status")
async def api_bluetooth_status() -> JSONResponse:
    res = await asyncio.to_thread(state.gaming.get_bluetooth_status)
    return JSONResponse(res)


@app.post("/api/bluetooth/scan")
async def api_bluetooth_scan(req: BluetoothScanRequest) -> JSONResponse:
    res = await asyncio.to_thread(
        state.gaming.scan_bluetooth_devices, req.open_rarely_used
    )
    return JSONResponse(res)


@app.post("/api/bluetooth/pair")
async def api_bluetooth_pair(req: BluetoothPairRequest) -> JSONResponse:
    res = await asyncio.to_thread(state.gaming.pair_or_connect_device, req.target)
    return JSONResponse(res)


# ==================== ENDPOINTS TERMINAL SSH & ATUALIZAÇÃO WI-FI ====================


@app.get("/api/ssh/status")
async def api_ssh_status() -> JSONResponse:
    res = await asyncio.to_thread(state.ssh_terminal.get_ssh_status)
    return JSONResponse(res)


@app.post("/api/ssh/exec")
async def api_ssh_exec(req: SshExecRequest) -> JSONResponse:
    res = await asyncio.to_thread(
        state.ssh_terminal.execute_command, req.command, req.target
    )
    return JSONResponse(res)


@app.post("/api/ssh/sync-wifi")
async def api_ssh_sync_wifi() -> JSONResponse:
    res = await asyncio.to_thread(state.ssh_terminal.sync_update_over_wifi)
    return JSONResponse(res)


@app.post("/api/ssh/open-laptop")
async def api_ssh_open_laptop() -> JSONResponse:
    res = await asyncio.to_thread(state.ssh_terminal.open_laptop_ssh_terminal)
    return JSONResponse(res)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    state.clients.add(ws)
    try:
        bat = state.android.get_battery_and_health()
        standby_info = state.android.get_standby_state()
        await ws.send_text(
            json.dumps(
                {
                    "type": "state",
                    "mode": state.mode,
                    "x11_backend": state.x11.backend_name,
                    "android_backend": state.android.backend_name,
                    "phone_online": bat.get("phone_online", True),
                    "battery": bat,
                    "standby_mode": state.android.standby_mode,
                    "standby": standby_info,
                }
            )
        )
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "ping":
                bat_now = state.android.get_battery_and_health()
                standby_now = state.android.get_standby_state()
                await ws.send_text(
                    json.dumps(
                        {
                            "type": "pong",
                            "ts": msg.get("ts", time.time()),
                            "phone_online": bat_now.get("phone_online", True),
                            "battery": bat_now,
                            "standby_mode": state.android.standby_mode,
                            "standby": standby_now,
                        }
                    )
                )
                continue

            if msg_type == "standby":
                raw_standby = msg.get("standby")
                auto_mins = msg.get("auto_standby_minutes")
                if raw_standby is None and auto_mins is not None:
                    state.android.auto_standby_minutes = max(0, int(auto_mins))
                    state.android._save_runtime_cache(
                        auto_standby_minutes=state.android.auto_standby_minutes
                    )
                else:
                    target_standby = (
                        (not state.android.standby_mode)
                        if raw_standby is None
                        else bool(raw_standby)
                    )
                    res = await asyncio.to_thread(
                        state.android.set_standby_mode,
                        target_standby,
                        str(msg.get("reason") or "manual"),
                        int(auto_mins) if auto_mins is not None else None,
                    )
                    if not res.get("standby_mode"):
                        state.mode = "tv"
                await broadcast_state()
                continue

            if msg_type == "mode":
                target = msg.get("mode", "tv")
                await asyncio.to_thread(apply_mode_switch, target)
                await broadcast_state()
                continue

            if msg_type == "launch":
                app_id = msg.get("app_id", "")
                if app_id:
                    await asyncio.to_thread(execute_app_launch, app_id)
                    await broadcast_state()
                continue

            # Roteamento inteligente de eventos de acordo com o modo ativo (ou override explícito)
            target_mode = msg.get("target") or state.mode
            state.android.touch_activity(wake_if_standby=True)

            if msg_type == "move":
                dx = float(msg.get("dx", 0.0))
                dy = float(msg.get("dy", 0.0))
                if target_mode == "linux":
                    state.x11.move_relative(dx, dy)
                else:
                    state.android.move_cursor(dx, dy)

            elif msg_type == "click":
                button = int(msg.get("button", 1))
                count = int(msg.get("count", 1))
                if target_mode == "linux":
                    state.x11.click(button=button, count=count)
                else:
                    state.android.tap_current(button=button)

            elif msg_type == "mousedown":
                button = int(msg.get("button", 1))
                if target_mode == "linux":
                    state.x11.mouse_button(button=button, down=True)

            elif msg_type == "mouseup":
                button = int(msg.get("button", 1))
                if target_mode == "linux":
                    state.x11.mouse_button(button=button, down=False)

            elif msg_type == "scroll":
                dx = float(msg.get("dx", 0.0))
                dy = float(msg.get("dy", 0.0))
                if target_mode == "linux":
                    state.x11.scroll(dx=dx, dy=dy)
                else:
                    state.android.scroll(dx=dx, dy=dy)

            elif msg_type == "dpad":
                key = str(msg.get("key", ""))
                dispatch_dpad_key(key, target_mode)

            elif msg_type == "gamepad":
                key = str(msg.get("key", ""))
                player = int(msg.get("player", 1) or 1)
                style = str(msg.get("style", "") or "")
                if key:
                    state.android.send_gamepad_key(
                        key, player=player, style=style or None
                    )

            elif msg_type == "key":
                key = str(msg.get("key", ""))
                if target_mode == "linux":
                    state.x11.send_key(key)
                else:
                    state.android.send_key(key)

            elif msg_type == "text":
                text = str(msg.get("text", ""))
                if target_mode == "linux":
                    state.x11.send_text(text)
                else:
                    state.android.send_text(text)

    except WebSocketDisconnect:
        state.clients.discard(ws)
    except Exception:
        state.clients.discard(ws)


# Rotas de raiz para PWA (manifest.json, sw.js, index.html)
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/manifest.json")
async def serve_manifest() -> FileResponse:
    return FileResponse(
        FRONTEND_DIR / "manifest.json",
        media_type="application/manifest+json",
        headers=NO_CACHE_HEADERS,
    )


@app.get("/sw.js")
async def serve_sw() -> FileResponse:
    return FileResponse(
        FRONTEND_DIR / "sw.js",
        media_type="application/javascript",
        headers=NO_CACHE_HEADERS,
    )


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(
        FRONTEND_DIR / "index.html",
        media_type="text/html",
        headers=NO_CACHE_HEADERS,
    )


app.mount("/roms", StaticFiles(directory=str(ROMS_DIR)), name="roms")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
