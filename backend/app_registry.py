"""
Catálogo de aplicativos Android TV e Linux Desktop para o HybridBox Remote PWA.
"""

from typing import Dict, List, Any

ANDROID_APPS: Dict[str, Dict[str, Any]] = {
    "projectivy": {
        "id": "projectivy",
        "name": "Projectivy Launcher",
        "category": "tv",
        "icon": "📺",
        "color": "#6366f1",
        "commands": [
            "am start -n com.spocky.projengmenu/.ui.home.MainActivity",
            "am start -n com.spocky.projengmenu/.activities.MainActivity",
            "monkey -p com.spocky.projengmenu -c android.intent.category.LAUNCHER 1",
            "input keyevent KEYCODE_HOME",
        ],
    },
    "smarttube": {
        "id": "smarttube",
        "name": "SmartTube",
        "category": "tv",
        "icon": "▶️",
        "color": "#ef4444",
        "commands": [
            "am start -n org.smarttube.stable/com.liskovsoft.smartyoutubetv2.tv.ui.main.SplashActivity",
            "monkey -p org.smarttube.stable -c android.intent.category.LEANBACK_LAUNCHER 1",
            "monkey -p org.smarttube.stable -c android.intent.category.LAUNCHER 1",
            "monkey -p org.smarttube.beta -c android.intent.category.LEANBACK_LAUNCHER 1",
            "monkey -p com.liskovsoft.smarttubetv.beta -c android.intent.category.LEANBACK_LAUNCHER 1",
            "monkey -p com.liskovsoft.smarttubetv -c android.intent.category.LEANBACK_LAUNCHER 1",
            "monkey -p com.liskovsoft.smarttubetv.beta -c android.intent.category.LAUNCHER 1",
            "monkey -p com.liskovsoft.smarttubetv -c android.intent.category.LAUNCHER 1",
            "am start -a android.intent.action.VIEW -d https://m.youtube.com",
        ],
    },
    "stremio": {
        "id": "stremio",
        "name": "Stremio",
        "category": "tv",
        "icon": "🎬",
        "color": "#8b5cf6",
        "commands": [
            "monkey -p com.stremio.one -c android.intent.category.LEANBACK_LAUNCHER 1",
            "monkey -p com.stremio.one -c android.intent.category.LAUNCHER 1",
            "am start -a android.intent.action.VIEW -d https://web.stremio.com",
        ],
    },
    "kodi": {
        "id": "kodi",
        "name": "Kodi",
        "category": "tv",
        "icon": "🎞️",
        "color": "#0ea5e9",
        "commands": [
            "am start -n org.xbmc.kodi/.Splash",
            "monkey -p org.xbmc.kodi -c android.intent.category.LAUNCHER 1",
            "monkey -p com.netflix.mediaclient -c android.intent.category.LAUNCHER 1",
        ],
    },
    "projector": {
        "id": "projector",
        "name": "Projector",
        "category": "tv",
        "icon": "📽️",
        "color": "#ec4899",
        "commands": [
            "settings put global wifi_display_on 1 && am start -a android.settings.CAST_SETTINGS",
            "am start -a miui.intent.action.MILINK_SETTING",
        ],
    },
    "wifi_portable": {
        "id": "wifi_portable",
        "name": "Portable Wi-Fi & Travel",
        "category": "system",
        "icon": "📡",
        "color": "#0ea5e9",
        "commands": [
            "svc wifi enable && am start -a android.settings.WIFI_SETTINGS",
        ],
    },
    "displaylink": {
        "id": "displaylink",
        "name": "HDMI Cable / DisplayLink",
        "category": "system",
        "icon": "🔌",
        "color": "#10b981",
        "commands": [
            "monkey -p com.displaylink.presenter -c android.intent.category.LAUNCHER 1",
            "am start -a android.settings.CAST_SETTINGS",
        ],
    },
    "termux_x11": {
        "id": "termux_x11",
        "name": "Termux:X11 (Linux)",
        "category": "linux",
        "icon": "🐧",
        "color": "#f59e0b",
        "commands": [
            "am start -n com.termux.x11/.MainActivity",
            "monkey -p com.termux.x11 -c android.intent.category.LAUNCHER 1",
            "am start -n com.termux/.app.TermuxActivity",
        ],
    },
    "ssh_terminal": {
        "id": "ssh_terminal",
        "name": "SSH Terminal & Wi-Fi Update",
        "category": "linux",
        "icon": "💻",
        "color": "#06b6d4",
        "commands": [
            "am start -n com.termux/.app.TermuxActivity",
        ],
    },
    "snes9x": {
        "id": "snes9x",
        "name": "Super Nintendo (Snes9x EX+)",
        "category": "games",
        "icon": "🍄",
        "color": "#ef4444",
        "commands": [
            "am start -n com.explusalpha.Snes9xPlus/com.imagine.BaseActivity",
            "monkey -p com.explusalpha.Snes9xPlus -c android.intent.category.LAUNCHER 1",
        ],
    },
    "neoemu": {
        "id": "neoemu",
        "name": "Arcade / NeoGeo (NEO.emu)",
        "category": "games",
        "icon": "🕹️",
        "color": "#f59e0b",
        "commands": [
            "am start -n com.explusalpha.NeoEmu/com.imagine.BaseActivity",
            "monkey -p com.explusalpha.NeoEmu -c android.intent.category.LAUNCHER 1",
        ],
    },
    "mame4droid": {
        "id": "mame4droid",
        "name": "MAME4droid (Full Arcade)",
        "category": "games",
        "icon": "🪙",
        "color": "#eab308",
        "commands": [
            "am start -n com.seleuco.mame4d2024/com.seleuco.mame4droid.MAME4droid",
            "am start -n com.seleuco.mame4droid/.MAME4droid",
            "am start -n com.seleuco.mame4all/.MAME4all",
            "monkey -p com.seleuco.mame4d2024 -c android.intent.category.LAUNCHER 1",
        ],
    },
    "mdemu": {
        "id": "mdemu",
        "name": "Mega Drive (MD.emu)",
        "category": "games",
        "icon": "🦔",
        "color": "#3b82f6",
        "commands": [
            "am start -n com.explusalpha.MdEmu/com.imagine.BaseActivity",
            "monkey -p com.explusalpha.MdEmu -c android.intent.category.LAUNCHER 1",
        ],
    },
    "lemuroid": {
        "id": "lemuroid",
        "name": "Lemuroid (SNES + MAME + Multi)",
        "category": "games",
        "icon": "👾",
        "color": "#10b981",
        "commands": [
            "am start -n com.swordfish.lemuroid/.app.mobile.feature.main.MainActivity",
            "monkey -p com.swordfish.lemuroid -c android.intent.category.LAUNCHER 1",
        ],
    },
    "bt_controllers": {
        "id": "bt_controllers",
        "name": "Bluetooth Controllers",
        "category": "games",
        "icon": "🔵",
        "color": "#3b82f6",
        "commands": [
            "svc bluetooth enable && am start --activity-clear-top -a android.settings.BLUETOOTH_SETTINGS",
        ],
    },
    "settings": {
        "id": "settings",
        "name": "Android Settings",
        "category": "system",
        "icon": "⚙️",
        "color": "#64748b",
        "commands": [
            "am start -a android.settings.SETTINGS",
        ],
    },
}

LINUX_APPS: Dict[str, Dict[str, Any]] = {
    "xfce_terminal": {
        "id": "xfce_terminal",
        "name": "XFCE Terminal",
        "category": "linux",
        "icon": "💻",
        "color": "#22c55e",
        "command": "DISPLAY=:0 xfce4-terminal &",
    },
    "browser": {
        "id": "browser",
        "name": "Linux Browser (Firefox)",
        "category": "linux",
        "icon": "🌐",
        "color": "#3b82f6",
        "command": (
            "killall xfce4-mime-helper 2>/dev/null || true; "
            "python3 ~/hybridbox-remote-pwa/scripts/shield_x11_touch.py >/dev/null 2>&1 || true; "
            "WID=$(DISPLAY=:0 xdotool search --onlyvisible --class firefox 2>/dev/null | tail -n 1); "
            "if [ -n \"$WID\" ]; then "
            "DISPLAY=:0 xdotool windowactivate \"$WID\" windowmove \"$WID\" 0 25 windowsize \"$WID\" 100% 97% 2>/dev/null || true; "
            "elif command -v firefox >/dev/null 2>&1; then "
            "(nohup env DISPLAY=:0 MOZ_DISABLE_CONTENT_SANDBOX=1 firefox </dev/null >/dev/null 2>&1 & "
            "for i in 1 2 3 4 5 6; do sleep 0.6; "
            "W=$(DISPLAY=:0 xdotool search --onlyvisible --class firefox 2>/dev/null | tail -n 1); "
            "if [ -n \"$W\" ]; then DISPLAY=:0 xdotool windowactivate \"$W\" windowmove \"$W\" 0 25 windowsize \"$W\" 100% 97% 2>/dev/null; break; fi; "
            "done) & "
            "elif command -v chromium-browser >/dev/null 2>&1; then "
            "nohup env DISPLAY=:0 chromium-browser --no-sandbox </dev/null >/dev/null 2>&1 & "
            "else DISPLAY=:0 exo-open --launch WebBrowser & fi"
        ),
    },
    "file_manager": {
        "id": "file_manager",
        "name": "Files (Thunar)",
        "category": "linux",
        "icon": "📁",
        "color": "#eab308",
        "command": "DISPLAY=:0 thunar &",
    },
}


def get_all_apps() -> List[Dict[str, Any]]:
    """Retorna a lista unificada de aplicativos para exibição na Gaveta de Apps do PWA."""
    items: List[Dict[str, Any]] = []
    for app in ANDROID_APPS.values():
        items.append(
            {
                "id": app["id"],
                "name": app["name"],
                "category": app["category"],
                "icon": app["icon"],
                "color": app["color"],
                "target": "android",
            }
        )
    for app in LINUX_APPS.values():
        items.append(
            {
                "id": app["id"],
                "name": app["name"],
                "category": app["category"],
                "icon": app["icon"],
                "color": app["color"],
                "target": "linux",
            }
        )
    return items
