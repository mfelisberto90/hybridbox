# 📖 HybridBox — Complete Technical Documentation & Engineering Guide

> **Upcycling a Broken-Screen Smartphone into a 3-in-1 Smart TV Box, Linux XFCE4 Desktop & Retro Gaming Console**
>
> *Tested on a **Xiaomi Redmi Note 8 Pro (`begonia`)** with a shattered screen — compatible with **any Android smartphone, tablet, or gadget** (Samsung, Xiaomi, Redmi, readMi, Motorola, OnePlus, Asus, Pixel, etc.).*

---

## Table of Contents

1. [Project Purpose & Philosophy](#1-project-purpose--philosophy)
2. [Tested Hardware & Compatibility](#2-tested-hardware--compatibility)
3. [System Architecture](#3-system-architecture)
4. [How We Built It (The Engineering Journey)](#4-how-we-built-it-the-engineering-journey)
   - [4.1. Defeating Ghost Touches on a Broken Screen (`EVIOCGRAB`)](#41-defeating-ghost-touches-on-a-broken-screen-eviocgrab)
   - [4.2. Privileged Android Bridge Without Root (`HybridBoxBridge` `uid=2000`)](#42-privileged-android-bridge-without-root-hybridboxbridge-uid2000)
   - [4.3. Surviving Android Doze Mode & MIUI Phantom Process Killer](#43-surviving-android-doze-mode--miui-phantom-process-killer)
   - [4.4. Full Linux XFCE4 Desktop & Passwordless `sudo`](#44-full-linux-xfce4-desktop--passwordless-sudo)
   - [4.5. Connecting to Any TV or Projector (Miracast, DLNA, HDMI DisplayLink)](#45-connecting-to-any-tv-or-projector-miracast-dlna-hdmi-displaylink)
   - [4.6. Portable Travel Wi-Fi, mDNS (`hybridbox.local`) & Rescue Hotspot](#46-portable-travel-wi-fi-mdns-hybridboxlocal--rescue-hotspot)
   - [4.7. Retro Game Console & Multi-Player Touch Controller PWA](#47-retro-game-console--multi-player-touch-controller-pwa)
   - [4.8. 0% Battery Recovery ("Plug & Revive")](#48-0-battery-recovery-plug--revive)
5. [Installing Any Linux Application via `sudo`](#5-installing-any-linux-application-via-sudo)
6. [Step-by-Step Reproduction Guide (How to Do It Yourself)](#6-step-by-step-reproduction-guide-how-to-do-it-yourself)
7. [REST & WebSocket API Reference](#7-rest--websocket-api-reference)
8. [Troubleshooting & FAQ](#8-troubleshooting--faq)

---

## 1. Project Purpose & Philosophy

Millions of powerful smartphones are discarded every year in drawers because of a **cracked or completely broken screen (`screen broken` / `broken phone`)**, even though their octacore ARM64 CPU, GPU, RAM, Wi-Fi, and Bluetooth are 100% functional.

**HybridBox** was born as a personal project—built collaboratively with **AI pair-programming**—to rescue a **Xiaomi Redmi Note 8 Pro** whose screen was broken and firing constant "ghost touches" across the digitizer. Instead of throwing the phone away or paying more than the phone's value for a replacement screen, we engineered a self-hosted software stack that turns **any Android phone or gadget** into a headless, zero-touch **3-in-1 Hybrid Console**:

1. 📺 **Android TV Box & Projector Hub**: Runs *Projectivy Launcher*, *SmartTube* (ad-free YouTube TV), *Stremio*, and *Kodi* in locked 1080p landscape, casting wirelessly to any **Projector** or **Smart TV** (or via a USB-to-HDMI DisplayLink adapter).
2. 🐧 **Full Linux Desktop (`Termux:X11` + `XFCE4` + `Debian PRoot`)**: Runs a real desktop Linux environment with Firefox, Thunar File Manager, XFCE Terminal, and a smart passwordless `sudo` wrapper so you can install any Linux software (`sudo apt install ...`).
3. 🎮 **Retro Gaming Console**: Launches SNES, NeoGeo/Arcade, MAME, and Sega Mega Drive games directly from a visual cover gallery in the browser, using your main phone as a low-latency touch gamepad (or pairing physical Bluetooth controllers).

### 📸 Real Screenshots of the Live HybridBox Portals

| 📺 TV Portal (D-Pad & Media Deck) | 🚀 System Quick Launcher Drawer | 🖱️ Linux X11 Multi-Touch Trackpad |
| :---: | :---: | :---: |
| <img src="screenshots/01-tv-portal-dpad.png" alt="TV Portal" width="260" /> | <img src="screenshots/02-system-app-launcher.png" alt="System Quick Launcher" width="260" /> | <img src="screenshots/03-linux-trackpad-portal.png" alt="Linux Trackpad Portal" width="260" /> |

| 💻 Web SSH Terminal (`sudo` in Action) | 📚 Visual ROM Cover Library (53+ Games) | 🍄 Tactile Super Nintendo Controller |
| :---: | :---: | :---: |
| <img src="screenshots/04-linux-ssh-sudo-portal.png" alt="Web SSH Terminal with sudo" width="260" /> | <img src="screenshots/05-games-rom-library-portal.png" alt="Retro Game Cover Library" width="260" /> | <img src="screenshots/06-games-snes-controller-portal.png" alt="SNES Tactile Controller" width="260" /> |

<p align="center">
  <img src="screenshots/07-games-landscape-arcade-hud.png" alt="Fullscreen Landscape Arcade 6-Button Fightstick HUD" width="800" />
</p>

| 🎮 Controllers, Skins & Multiplayer | 📽️ Any TV or Projector Auto-Connect | 📡 Portable Wi-Fi & Rescue Hotspot | ⚡ Live Battery & 0% Recovery Guide |
| :---: | :---: | :---: | :---: |
| <img src="screenshots/08-controllers-multiplayer-modal.png" alt="Controllers and Multiplayer Modal" width="200" /> | <img src="screenshots/09-projector-tv-modal.png" alt="Any TV or Projector Modal" width="200" /> | <img src="screenshots/10-portable-wifi-travel-modal.png" alt="Portable Wi-Fi and Rescue Hotspot Modal" width="200" /> | <img src="screenshots/11-battery-recovery-guide.png" alt="Live Battery and Recovery Guide" width="200" /> |

---

## 2. Tested Hardware & Compatibility

### Primary Testbed
| Component | Specification |
| :--- | :--- |
| **Device** | **Xiaomi Redmi Note 8 Pro** (codename `begonia`) |
| **SoC / CPU** | MediaTek Helio G90T (2x Cortex-A76 @ 2.05 GHz + 6x Cortex-A55 @ 2.0 GHz) |
| **RAM / Storage** | 6 GB LPDDR4X / 128 GB UFS 2.1 |
| **OS** | Android 11 (MIUI 12.5 Global, **Unrooted**) |
| **Screen Condition** | Physically broken digitizer (`NVTCapacitiveTouchScreen` on `/dev/input/event2`) generating 60Hz ghost touches |
| **Display Output** | Wireless **Projector** (`1920x1080 @ 60fps` via Miracast / Wi-Fi Direct), Smart TVs, and USB DisplayLink HDMI |

### Universal Android Compatibility
Although developed and stress-tested on a Xiaomi Redmi Note 8 Pro, **HybridBox works on virtually any Android 8.0+ smartphone, tablet, or TV box**:
- **Samsung Galaxy** (S8, S9, S10, S20, S21, S22, S23, Note series, A-series, Tab series — including Samsung DeX or Miracast Smart View)
- **Xiaomi / Redmi / readMi / POCO** (Redmi Note 7/8/9/10/11/12/13, Mi 9/10/11, Poco X3/F3)
- **Motorola** (Moto G, Moto Edge, Ready For)
- **OnePlus, Google Pixel, Asus ROG / Zenfone, Realme, OPPO, Vivo**

> **No root required!** Every privileged operation uses Android's standard `ADB Loopback` (`uid=2000 shell`) which is built into every Android device via *USB Debugging / Wireless Debugging*.

---

## 3. System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                    USER'S MAIN PHONE / LAPTOP BROWSER                   │
│             Progressive Web App (PWA) @ http://hybridbox.local:8080     │
│  [📺 TV D-Pad & AirMouse] [🐧 Linux Trackpad & SSH] [🎮 Gamepad & ROMs] │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ WebSocket (/ws) + REST API (:8080)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│             BROKEN-SCREEN ANDROID PHONE (HybridBox Host)                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Termux (untrusted_app)                                            │  │
│  │  • FastAPI + Uvicorn Server (:8080)                               │  │
│  │  • OpenSSH Server (:8022) + Cron + keep_awake.sh Watchdog         │  │
│  │  • Termux:X11 (:0) + XFCE4 Desktop + Firefox + Thunar             │  │
│  │  • Smart Passwordless `sudo` (scripts/hb-sudo + Debian PRoot)     │  │
│  └───────────────┬───────────────────────────────────┬───────────────┘  │
│                  │ XTEST (:0)                        │ TCP 127.0.0.1:5558│
│                  ▼                                   ▼                  │
│  ┌──────────────────────────────┐   ┌────────────────────────────────┐  │
│  │ Linux X11 Desktop            │   │ Privileged ADB Shell (uid=2000)│  │
│  │ • python-xlib / xdotool      │   │ • HybridBoxBridge.jar Daemon   │  │
│  │ • shield_x11_touch.py        │   │ • grab_ghost_touch (EVIOCGRAB) │  │
│  │ • Debian PRoot Rootfs        │   │ • hb_system_watchdog.sh        │  │
│  └──────────────────────────────┘   └────────────────────────────────┘  │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ Miracast 1080p60 / DLNA / HDMI
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     📽️ PROJECTOR OR 📺 SMART TV                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. How We Built It (The Engineering Journey)

Here is the exact technical breakdown of the challenges we faced turning a broken-screen Xiaomi Redmi Note 8 Pro into a reliable 24/7 console, and how we solved each one:

### 4.1. Defeating Ghost Touches on a Broken Screen (`EVIOCGRAB`)
- **The Problem**: A cracked capacitive screen constantly fires phantom touch events (`ABS_MT_SLOT`, `BTN_TOUCH`) at 60Hz. This makes Android unusable: menus click themselves, video players pause randomly, and the X11 cursor jumps erratically.
- **How We Solved It**:
  1. On Android, the `shell` user (`uid=2000`, `gid=1004 input`) has read/write access to `/dev/input/event*`.
  2. We wrote [`scripts/grab_ghost_touch.c`](../scripts/grab_ghost_touch.c) and compiled it on the phone with `clang` to `/data/local/tmp/grab_ghost_touch`.
  3. On startup, `grab_ghost_touch` locates the physical touchscreen digitizer (`NVTCapacitiveTouchScreen` / `fts_ts` / `goodix_ts` on `/dev/input/event2`), injects multi-touch slot release events (`ABS_MT_TRACKING_ID = -1`, `BTN_TOUCH = 0`, `SYN_REPORT`) to unstick any held phantom fingers, and calls `ioctl(fd, EVIOCGRAB, 1)`.
  4. `EVIOCGRAB` gives our tiny daemon exclusive kernel access to the broken physical digitizer and discards all hardware touch events into `/dev/null`, while **preserving 100% of synthetic input** (`input tap`, `input swipe`, `input keyevent`, Bluetooth controllers, and X11 `XTEST`).
  5. For the Linux XFCE4 desktop, we also wrote [`scripts/shield_x11_touch.py`](../scripts/shield_x11_touch.py), which detaches the `Lorie touch` / `Lorie mouse` slave pointers from the X11 Virtual Core Pointer while leaving `Virtual core XTEST pointer` active.

### 4.2. Privileged Android Bridge Without Root (`HybridBoxBridge` `uid=2000`)
- **The Problem**: Spawning a new `adb shell input ...` process on every button press takes 150–300ms, which feels laggy for D-Pad navigation or gaming. Furthermore, when the phone screen is turned off or locked, Android blocks standard wake-ups unless a system `WakeLock` is held.
- **How We Solved It**:
  1. We wrote [`backend/HybridBoxBridge.java`](../backend/HybridBoxBridge.java) and compiled it into [`backend/hybridbox_bridge.jar`](../backend/hybridbox_bridge.jar).
  2. Launched via `/system/bin/app_process / HybridBoxBridge daemon 5558` under `uid=2000 (shell)`, it uses reflection on Android's internal `ServiceManager` (`IPowerManager`) to acquire a permanent system `PARTIAL_WAKE_LOCK` and listens on `127.0.0.1:5558` for sub-5ms shell execution via [`scripts/hb-shell`](../scripts/hb-shell).

### 4.3. Surviving Android Doze Mode & MIUI Phantom Process Killer
- **The Problem**: Xiaomi's MIUI and Android 11+ aggressively kill background processes (Termux, SSH, Uvicorn) after a few minutes of inactivity.
- **How We Solved It**:
  1. Our system watchdog [`scripts/hb_system_watchdog.sh`](../scripts/hb_system_watchdog.sh) runs as `uid=2000 (shell)` in `/data/local/tmp` and disables Doze Mode (`dumpsys deviceidle disable`), disables the Phantom Process Killer (`settings put global settings_enable_monitor_phantom_procs false`), sets `max_phantom_processes` to `2147483647`, and grants MIUI's hidden Autostart permission (`appops set <pkg> 10008 allow`) to Termux, Termux:Boot, Termux:X11, Projectivy Launcher, and all emulators.
  2. When running on battery power, `keep_awake.sh` automatically sets the broken phone's physical screen backlight to `0` (`screen_brightness 0`) so it wastes zero power while still streaming 1080p60 video to the Projector or TV!

### 4.4. Full Linux XFCE4 Desktop & Passwordless `sudo`
- **The Problem**: Users switching to the **Linux** tab want a real desktop experience where they can open a terminal and run `sudo apt install <app>` without hitting Termux's unrooted permission errors.
- **How We Solved It**:
  1. We built [`scripts/hb-sudo`](../scripts/hb-sudo) and installed it at `/data/data/com.termux/files/usr/bin/sudo`.
  2. We also added `proot-distro` with a full **Debian Linux** rootfs (`/data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/debian`) configured with `/etc/sudoers.d/hybridbox` (`ALL ALL=(ALL:ALL) NOPASSWD: ALL`).
  3. Whether you type `sudo apt install htop`, `sudo apt install gimp`, `sudo -i`, or `sudo settings put ...`, `hb-sudo` routes the command automatically with zero password prompts.

### 4.5. Connecting to Any TV or Projector (Miracast, DLNA, HDMI DisplayLink)
- **The Problem**: With a broken screen, you cannot tap Android's "Cast / Wireless Display" menu or click the "Start Now" confirmation dialog when connecting to a Projector or Smart TV.
- **How We Solved It**:
  1. [`backend/projector_controller.py`](../backend/projector_controller.py) combines Miracast Wi-Fi Direct discovery (`dumpsys display` + `dumpsys wifip2p`), LAN HTTP/ARP auto-discovery, and SSDP/UPnP DLNA scanning.
  2. When you click **Scan Any TV or Projector** in the PWA, the backend opens Android's Wireless Display settings in the background, parses the UI hierarchy via `uiautomator dump`, taps the target **Projector** or **Smart TV** automatically, and auto-accepts any confirmation dialog (`_confirm_cast_dialog_if_present`).

### 4.6. Portable Travel Wi-Fi, mDNS (`hybridbox.local`), Zero-Config Auto-Discovery & Rescue Hotspot
- **The Problem**: If you take your broken-screen phone to a hotel, a friend's house, or another room, it won't know the new Wi-Fi password—and you can't use the broken screen to connect to the new Wi-Fi! Moreover, DHCP IP addresses change across routers, and open-source users cloning the repo must never have to edit hardcoded IPs, MACs, or Termux UIDs.
- **How We Solved It**:
  1. **Zero-Config Auto-Discovery Pipeline (`backend/android_controller.py`)**:
     - When running directly inside Termux on the phone, it reads the active IP of `wlan0` via kernel `SIOCGIFADDR` ioctl.
     - When running on a companion PC, it automatically discovers the phone's IP and Termux SSH username (`u0_a...`) in `<1s` via: (a) local gitignored runtime cache (`.hybridbox_runtime.json`) and `~/.ssh/config` (`Host hybridbox`), (b) active USB or Wireless ADB (`adb devices`), (c) multicast mDNS (`hybridbox.local`), and (d) a 96-worker parallel `/24` LAN & Hotspot subnet scanner probing ports `8022` (Termux OpenSSH) and `5555` (Wireless ADB).
     - Optional environment variables (`HYBRIDBOX_PHONE_IP`, `HYBRIDBOX_SSH_USER`, `HYBRIDBOX_SSH_PORT`, `HYBRIDBOX_ADB_SERIAL`, `HYBRIDBOX_PROJECTOR_IP`) can also override any setting.
  2. **Pre-Save Wi-Fi**: Before leaving home, you can pre-save the destination Wi-Fi SSID and password in the **Portable Wi-Fi & Travel** tab.
  3. **Automatic Rescue Hotspot**: If the phone loses Wi-Fi for more than 20 seconds, `hb_system_watchdog.sh` automatically scans for a **Rescue Wi-Fi Hotspot** (default SSID: `HybridBox`, password: `hybridbox123`). Simply turn on the Wi-Fi Hotspot on your main phone with those credentials, and the broken phone connects to your phone automatically!
  4. **mDNS Zero-Config**: Built-in multicast DNS responder (`MdnsZeroConfService` in [`backend/wifi_portable_controller.py`](../backend/wifi_portable_controller.py)) broadcasts `http://hybridbox.local:8080` on UDP port `5353`, so you never need to guess the phone's IP address.

### 4.7. Retro Game Console & Multi-Player Touch Controller PWA
- **The Problem**: Launching emulators and selecting ROMs normally requires touching the phone's screen, and different emulators use different Android `Intent` formats and keycodes.
- **How We Solved It**:
  1. [`backend/bluetooth_gaming_controller.py`](../backend/bluetooth_gaming_controller.py) indexes all ROMs in `/sdcard/ROMS/{snes,mame,megadrive}`, generates SVG cover art for each game, and configures emulator config files (`Snes9x EX+`, `NEO.emu`, `MD.emu`, `MAME4droid`, `Lemuroid`) to lock into landscape and hide on-screen touch overlays on the TV/Projector.
  2. Tapping any game cover in the PWA launches the ROM directly on the TV/Projector and switches your smartphone browser into a full-screen tactile controller (SNES, Arcade 6-Button NeoGeo, or Sega Mega Drive 6-Button skin) with multi-player support (Player 1 & Player 2 via QR/link).

### 4.8. 0% Battery Recovery ("Plug & Revive")
- **The Problem**: If the phone battery completely drains to `0%` and powers off, Android resets `adb tcpip 5555` on reboot.
- **How We Solved It**:
  1. `Termux:Boot` (`~/.termux/boot/start-hybridbox.sh`) automatically starts `sshd`, `uvicorn`, and `keep_awake.sh` as soon as Android boots.
  2. If the phone is plugged into the PC via USB, [`scripts/pc_usb_autorevive.py`](../scripts/pc_usb_autorevive.py) detects the USB ADB connection within 5 seconds, automatically injects your PC's SSH public key (`~/.ssh/id_ed25519.pub`) into Termux's `~/.ssh/authorized_keys`, re-enables `adb tcpip 5555`, restarts `HybridBoxBridge` (`5558`) and `grab_ghost_touch`, syncs any updated files, and brings the whole console back online automatically.

---

## 5. Installing Any Linux Application via `sudo`

In HybridBox's **Linux Mode** (`Termux:X11` + `XFCE4` + `Debian PRoot`), a smart passwordless `sudo` command (`/data/data/com.termux/files/usr/bin/sudo`, powered by [`scripts/hb-sudo`](../scripts/hb-sudo)) is pre-installed.

You can open either:
- **XFCE Terminal** directly on your TV/Projector, or
- The built-in **Web SSH Terminal** inside the HybridBox PWA (`🐧 Linux` -> `💻 SSH & Wi-Fi`), or
- Any SSH client on your laptop (`ssh -p 8022 termux@hybridbox.local`)

and run standard `sudo` commands without any password prompt:

### Examples of Installing Linux Desktop & CLI Apps
```bash
# Update repositories
sudo apt update && sudo apt upgrade -y

# Install productivity & media apps (runs on the XFCE4 Desktop on your TV/Projector!)
sudo apt install -y vlc gimp libreoffice inkscape audacity

# Install developer tools & editors
sudo apt install -y git curl wget htop neofetch tmux vim nano nodejs python3-pip clang

# Launch any installed GUI app directly onto the TV/Projector screen (:0)
DISPLAY=:0 vlc &
DISPLAY=:0 gimp &
```

### Entering a Full Debian Root Shell
If a package is only available in upstream Debian ARM64 repositories (and not in Termux's native repositories), `sudo apt install <pkg>` automatically falls back to installing it inside the Debian PRoot container! You can also open an interactive Debian root shell at any time:
```bash
sudo -i
# You are now root@debian with full apt-get access and shared DISPLAY=:0!
apt update && apt install -y chromium
DISPLAY=:0 chromium --no-sandbox &
```

### Running Privileged Android System Commands via `sudo`
Our `sudo` wrapper also bridges Android OS commands (`pm`, `am`, `cmd`, `settings`, `svc`, `dumpsys`, `setprop`, `input`, `wm`, `appops`) directly to the `uid=2000 (shell)` daemon:
```bash
# Install an Android APK from the Linux terminal
sudo pm install -r /sdcard/Download/app.apk

# Change Android screen density or resolution
sudo wm density 240

# Inspect battery status
sudo dumpsys battery
```

---

## 6. Step-by-Step Reproduction Guide (How to Do It Yourself)

Want to turn your own broken-screen Android phone (or old phone in a drawer) into a **HybridBox**? Follow these exact steps:

### Prerequisites
1. **Any Android phone or tablet** (Android 8.0+ recommended; tested on Xiaomi Redmi Note 8 Pro).
2. **USB Debugging enabled** in *Developer Options* on the phone.
   - *(Tip: If your screen is completely black/unusable, plug a cheap USB OTG mouse into the phone or use a USB-C HDMI hub for 2 minutes just to tap "Allow USB Debugging" once!)*
3. **A PC (Windows, Linux, or macOS)** with `adb` (Android Platform Tools) and Python 3.10+ for the initial 2-minute setup.

### Step 1: Clone the Repository
```bash
git clone https://github.com/mfelisberto90/hybridbox.git
cd hybridbox
```

### Step 2: One-Click Installation from Your PC
- **On Windows**: Double-click **`install.bat`** (or run it in PowerShell/CMD):
  ```bat
  .\install.bat
  ```
- **On Linux / macOS**:
  ```bash
  bash install.sh
  ```

### Step 3: One-Command Setup Inside Termux (On the Phone)
Once Termux, Termux:X11, and Termux:Boot are installed on the phone, run via SSH or ADB:
```bash
cd ~/hybridbox-remote-pwa
bash scripts/setup.sh
bash scripts/start.sh
```

### Step 4: Compile & Activate the Broken-Screen Ghost-Touch Blocker (If Screen is Cracked)
If your phone has a cracked digitizer causing ghost touches, run this once inside Termux/SSH:
```bash
clang -O2 ~/hybridbox-remote-pwa/scripts/grab_ghost_touch.c -o ~/grab_ghost_touch
sudo cp ~/grab_ghost_touch /data/local/tmp/grab_ghost_touch
sudo chmod 755 /data/local/tmp/grab_ghost_touch
sudo /data/local/tmp/grab_ghost_touch --daemon
```
*(From then on, `hb_system_watchdog.sh` keeps `grab_ghost_touch` running automatically 24/7!)*

### Step 5: Open the Remote PWA on Your Main Phone
1. On your daily smartphone (iPhone or Android), open Chrome or Safari and navigate to:
   - **`http://hybridbox.local:8080`** *(or `http://<PHONE_IP>:8080`)*
2. Tap **"Add to Home Screen"** to install **HybridBox** as a full-screen native-feeling Progressive Web App.
3. Tap **📽️ Any TV / Projector** in the top bar to connect wirelessly to your **Projector** or **Smart TV**!

---

## 7. REST & WebSocket API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/status` | `GET` | Returns active mode (`tv`, `linux`, `games`), local IP, mDNS URL, battery telemetry, and app catalog |
| `/api/battery` | `GET` | Real-time battery percentage, charging status (AC/USB), temperature (°C), voltage, and health |
| `/api/mode` | `POST` | Switches the phone between `tv` (Projectivy Launcher), `linux` (Termux:X11 XFCE4), and `games` |
| `/api/launch` | `POST` | Launches any registered Android TV, Linux Desktop, or Emulator app by `app_id` |
| `/api/projector/status` | `GET` | Lists discovered Miracast, Wi-Fi Direct, LAN HTTP, and DLNA Projectors & Smart TVs |
| `/api/projector/scan` | `POST` | Wakes the phone, scans for any Smart TV or Projector, and optionally auto-connects |
| `/api/projector/connect` | `POST` | Connects wirelessly to a specific Projector or Smart TV via UIAutomator Safe-Tap |
| `/api/wifi/status` | `GET` | Returns current Wi-Fi SSID, signal strength, IP/Gateway, and Rescue Hotspot configuration |
| `/api/wifi/scan` | `POST` | Scans nearby 2.4GHz / 5GHz Wi-Fi networks |
| `/api/wifi/connect` | `POST` | Connects immediately or pre-saves a Wi-Fi network for travel |
| `/api/wifi/rescue-hotspot` | `POST` | Configures the automatic fallback Rescue Hotspot (`HybridBox` / `hybridbox123`) |
| `/api/games/status` | `GET` | Lists installed emulators (`snes9x`, `neoemu`, `mame4droid`, `mdemu`, `lemuroid`) and all ROM covers |
| `/api/games/launch-rom` | `POST` | Launches a specific ROM file directly in full-screen landscape on the TV/Projector |
| `/api/ssh/exec` | `POST` | Executes a shell command on `android` (`hb-shell`) or `linux` (`DISPLAY=:0`) and returns output |
| `/ws` | `WS` | Zero-latency bidirectional WebSocket for trackpad cursor movement, multi-touch scroll, D-Pad, keyboard, and 60fps gamepad buttons |

---

## 8. Troubleshooting & FAQ

- **Q: My phone's battery died completely (0%) and it turned off. How do I recover it without touching the broken screen?**
  - **A**: Plug the phone into your PC via USB for 10 seconds while `iniciar_hybridbox_pwa.bat` (or `python scripts/pc_usb_autorevive.py --once`) is running. It will automatically re-enable `adb tcpip 5555`, start the `HybridBoxBridge` daemon, and launch the PWA server.
- **Q: Can I use a USB-to-HDMI cable instead of wireless Miracast?**
  - **A**: Yes! If your phone supports USB-C DisplayPort Alt Mode (e.g., Samsung Galaxy S/Note, OnePlus, Motorola Edge), HDMI works natively. If your phone only has USB 2.0 (like Xiaomi Redmi / Note series), plug in a **DisplayLink USB-to-HDMI adapter**, install the *DisplayLink Presenter* app, and click **🔌 Use HDMI Cable / DisplayLink** in the PWA—HybridBox automatically accepts the USB screen-capture permission popup for you!
- **Q: Why does `sudo apt install` work without root?**
  - **A**: HybridBox includes [`scripts/hb-sudo`](../scripts/hb-sudo), which translates `sudo apt` commands into native Termux package installations or executes them inside a full Debian ARM64 container powered by `proot-distro`.
