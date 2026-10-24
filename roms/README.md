# 🎮 HybridBox Retro ROMs Directory (`roms/`)

This folder stores your retro game ROMs organized by console system:

- `roms/snes/` — Super Nintendo (`.sfc`, `.smc`, `.zip`)
- `roms/mame/` — NeoGeo & Arcade / MAME (`.zip`, plus `neogeo.zip` BIOS)
- `roms/megadrive/` — Sega Mega Drive / Genesis (`.bin`, `.md`, `.gen`, `.smd`, `.zip`)

## How to Add Games
1. **Via the HybridBox PWA (Over Wi-Fi)**:
   - Open the **🎮 Games** tab in the HybridBox web interface (`http://hybridbox.local:8080`).
   - Tap **📤 Upload ROM** to upload `.sfc`, `.zip`, `.bin`, or `.md` files directly from your phone or PC browser, OR tap the **Install Game Pack** buttons (`scripts/install_game_packs.py`).
2. **Directly on Disk**:
   - Drop your ROM files into `roms/snes/`, `roms/mame/`, or `roms/megadrive/`. HybridBox automatically generates SVG cover art and syncs them to `/sdcard/ROMS/` on the Android console.
