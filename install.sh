#!/usr/bin/env bash
# ==============================================================================
# HybridBox — Universal One-Command Installer (Termux on Android OR Linux/macOS)
# ==============================================================================
# Usage:
#   1. Directly inside Termux on your Android phone:
#        git clone https://github.com/mfelisberto90/hybridbox.git ~/hybridbox-remote-pwa
#        cd ~/hybridbox-remote-pwa && bash install.sh
#   2. Or on a Linux / macOS PC with your Android phone plugged into USB:
#        git clone https://github.com/mfelisberto90/hybridbox.git
#        cd hybridbox && bash install.sh
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================================================="
echo "  🚀 HYBRIDBOX — UNIVERSAL INSTALLER (ANDROID TV + LINUX XFCE4 + RETRO GAMES)"
echo "=============================================================================="

# Detect if running directly inside Termux on Android
if [ -d "/data/data/com.termux/files/usr" ] || [ -n "${TERMUX_VERSION:-}" ]; then
  echo "[*] Detected Termux environment on Android!"
  if [ "${1:-}" = "--check" ]; then
    python3 -c "import fastapi, uvicorn, websockets; print('[+] Termux Python dependencies OK')"
    exit 0
  fi
  bash "$SCRIPT_DIR/scripts/setup.sh"
  if [ "${1:-}" = "--no-start" ]; then
    echo "[+] Termux setup completed (--no-start)."
    exit 0
  fi
  bash "$SCRIPT_DIR/scripts/start.sh"
  exit 0
fi

# Otherwise, running on a PC (Linux / macOS / WSL)
echo "[*] Detected Desktop OS ($(uname -s)). Setting up Python environment..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "[!] Error: python3 is required. Please install Python 3.10+ and re-run."
  exit 1
fi

if [ ! -d "$SCRIPT_DIR/.venv" ]; then
  python3 -m venv "$SCRIPT_DIR/.venv"
fi

"$SCRIPT_DIR/.venv/bin/pip" install --upgrade pip >/dev/null 2>&1 || true
"$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

echo "[*] Provisioning connected Android device via ADB / Wi-Fi..."
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/scripts/pc_usb_autorevive.py" --once || true
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/scripts/pc_usb_autorevive.py" --install-apks || true

echo ""
if [ "${1:-}" = "--no-start" ] || [ "${1:-}" = "--check" ]; then
  echo "[+] HybridBox installation check completed!"
  exit 0
fi
echo "[+] HybridBox is ready! Starting server on http://0.0.0.0:8080 ..."
exec "$SCRIPT_DIR/.venv/bin/python" -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
