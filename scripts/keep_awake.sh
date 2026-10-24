#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# HybridBox Remote PWA — Guardião 24/7 Anti-Sleep & Auto-Heal (Termux + Android)
# Mantém CPU, Wi-Fi (ARP), SSH (8022), ADB TCP (5555), Daemon Shell (5558),
# Termux:X11 (:0) e Servidor FastAPI/Uvicorn (8080) sempre ativos.
# ==============================================================================

trap '' HUP INT TERM

export PREFIX=/data/data/com.termux/files/usr
export HOME=/data/data/com.termux/files/home
export PATH=$PREFIX/bin:/system/bin:/system/xbin
export LD_LIBRARY_PATH=$PREFIX/lib
export DISPLAY=:0
export PULSE_SERVER=127.0.0.1
export MOZ_DISABLE_CONTENT_SANDBOX=1

PROJECT_DIR="$HOME/hybridbox-remote-pwa"
LOCK_FILE="$PREFIX/tmp/hybridbox_keep_awake.pid"
mkdir -p "$PREFIX/tmp" 2>/dev/null || true

# Verifica se um PID está vivo mesmo quando pertence a outro domínio SELinux (untrusted_app_27 vs runas_app)
is_pid_alive() {
  local p="$1"
  [ -z "$p" ] && return 1
  [ -d "/proc/$p" ] && return 0
  local kout
  kout=$(kill -0 "$p" 2>&1) && return 0
  echo "$kout" | grep -qiE "permission|permitted" && return 0
  return 1
}

tcp_open() {
  "$PREFIX/bin/python3" -c "import socket,sys; s=socket.create_connection(('127.0.0.1', int(sys.argv[1])), 0.5); s.close()" "$1" >/dev/null 2>&1
}

# Se iniciado em u:r:runas_app:s0 e o sshd local (8022) estiver ativo em untrusted_app_27, migra para untrusted_app_27
if id -Z 2>/dev/null | grep -q "runas_app" && tcp_open 8022; then
  if ssh -p 8022 -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=no 127.0.0.1 \
    "nohup setsid /data/data/com.termux/files/usr/bin/bash /data/data/com.termux/files/home/hybridbox-remote-pwa/scripts/keep_awake.sh </dev/null >/dev/null 2>&1 &" 2>/dev/null; then
    exit 0
  fi
fi

# Garante instância única do guardião (à prova de falso-negativo entre runas_app e untrusted_app_27)
if [ -f "$LOCK_FILE" ]; then
  OLD_PID=$(cat "$LOCK_FILE" 2>/dev/null)
  if [ -n "$OLD_PID" ] && [ "$OLD_PID" != "$$" ] && is_pid_alive "$OLD_PID"; then
    exit 0
  fi
fi
echo "$$" > "$LOCK_FILE"

cd "$PROJECT_DIR" 2>/dev/null || true

# 1. Ativa WakeLock nativo do Termux
termux-wake-lock 2>/dev/null || true

# 2. Garante chave SSH local em ~/.ssh/authorized_keys para loopback 127.0.0.1:8022
mkdir -p "$HOME/.ssh" 2>/dev/null || true
chmod 700 "$HOME/.ssh" 2>/dev/null || true
if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
  ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" >/dev/null 2>&1 || true
fi
if [ -f "$HOME/.ssh/id_ed25519.pub" ]; then
  PUB_KEY=$(cat "$HOME/.ssh/id_ed25519.pub" 2>/dev/null)
  if [ -n "$PUB_KEY" ] && ! grep -qF "$PUB_KEY" "$HOME/.ssh/authorized_keys" 2>/dev/null; then
    echo "$PUB_KEY" >> "$HOME/.ssh/authorized_keys"
  fi
  chmod 600 "$HOME/.ssh/authorized_keys" "$HOME/.ssh/id_ed25519" 2>/dev/null || true
fi

# 3. Garante utilitários hb-shell e sudo (hb-sudo) instalados no PATH do Termux
sed -i 's/\r$//' "$PROJECT_DIR/scripts"/*.sh "$PROJECT_DIR/scripts/hb-shell" "$PROJECT_DIR/scripts/hb-sudo" 2>/dev/null || true
if [ -f "$PROJECT_DIR/scripts/hb-shell" ]; then
  cp "$PROJECT_DIR/scripts/hb-shell" "$PREFIX/bin/hb-shell" 2>/dev/null || true
  chmod 755 "$PREFIX/bin/hb-shell" 2>/dev/null || true
fi
if [ -f "$PROJECT_DIR/scripts/hb-sudo" ]; then
  cp "$PROJECT_DIR/scripts/hb-sudo" "$PREFIX/bin/sudo" 2>/dev/null || true
  chmod 755 "$PREFIX/bin/sudo" 2>/dev/null || true
fi

# 4. Garante servidor OpenSSH ativo na porta 8022 e crond (cronie) ativo como guardião extra
tcp_open 8022 || "$PREFIX/bin/sshd" 2>/dev/null || true
if command -v crontab >/dev/null 2>&1; then
  if ! crontab -l 2>/dev/null | grep -q "keep_awake.sh"; then
    (crontab -l 2>/dev/null; echo "* * * * * /data/data/com.termux/files/usr/bin/bash /data/data/com.termux/files/home/hybridbox-remote-pwa/scripts/keep_awake.sh >/dev/null 2>&1") | crontab - 2>/dev/null || true
  fi
fi
if command -v crond >/dev/null 2>&1; then
  pgrep -x crond >/dev/null 2>&1 || crond 2>/dev/null || true
fi

# 5. Instala e inicia (ou atualiza) o watchdog privilegiado uid=2000(shell) em /data/local/tmp de forma atômica
ensure_system_watchdog() {
  if [ -x "$PREFIX/bin/hb-shell" ] && [ -f "$PROJECT_DIR/scripts/hb_system_watchdog.sh" ]; then
    "$PREFIX/bin/hb-shell" "if [ ! -s /data/local/tmp/hybridbox_bridge.jar ]; then run-as com.termux /data/data/com.termux/files/usr/bin/cat $PROJECT_DIR/backend/hybridbox_bridge.jar > /data/local/tmp/hybridbox_bridge.jar.tmp 2>/dev/null && [ -s /data/local/tmp/hybridbox_bridge.jar.tmp ] && mv /data/local/tmp/hybridbox_bridge.jar.tmp /data/local/tmp/hybridbox_bridge.jar && chmod 644 /data/local/tmp/hybridbox_bridge.jar; fi; run-as com.termux /data/data/com.termux/files/usr/bin/cat $PROJECT_DIR/scripts/hb_system_watchdog.sh > /data/local/tmp/hb_system_watchdog.sh.tmp 2>/dev/null; OPID=\$(cat /data/local/tmp/hb_sys_watchdog.pid 2>/dev/null); NEED_START=0; if [ -s /data/local/tmp/hb_system_watchdog.sh.tmp ]; then if ! cmp -s /data/local/tmp/hb_system_watchdog.sh.tmp /data/local/tmp/hb_system_watchdog.sh 2>/dev/null; then mv /data/local/tmp/hb_system_watchdog.sh.tmp /data/local/tmp/hb_system_watchdog.sh && chmod 755 /data/local/tmp/hb_system_watchdog.sh; [ -n \"\$OPID\" ] && kill -9 \"\$OPID\" 2>/dev/null; rm -f /data/local/tmp/hb_sys_watchdog.pid; NEED_START=1; else rm -f /data/local/tmp/hb_system_watchdog.sh.tmp; fi; fi; if [ \"\$NEED_START\" = \"1\" ] || [ -z \"\$OPID\" ] || [ ! -d \"/proc/\$OPID\" ]; then (nohup /system/bin/sh /data/local/tmp/hb_system_watchdog.sh </dev/null >/dev/null 2>&1 &); fi" >/dev/null 2>&1 || true
  fi
}

ensure_system_watchdog

LOOP_COUNT=0
UNPLUGGED_CYCLES=0

while true; do
  LOOP_COUNT=$((LOOP_COUNT + 1))
  echo "$$" > "$LOCK_FILE"

  # A. Garante OpenSSH (porta 8022) e crond sempre rodando
  tcp_open 8022 || "$PREFIX/bin/sshd" 2>/dev/null || true
  if command -v crond >/dev/null 2>&1; then
    pgrep -x crond >/dev/null 2>&1 || crond 2>/dev/null || true
  fi

  # B. Garante servidor FastAPI / Uvicorn (porta 8080) sempre rodando no celular
  if ! tcp_open 8080; then
    if ! pgrep -f "[u]vicorn.*backend.main:app" >/dev/null 2>&1; then
      cd "$PROJECT_DIR" 2>/dev/null || true
      nohup setsid "$PREFIX/bin/python3" -m uvicorn backend.main:app --host 0.0.0.0 --port 8080 --log-level warning </dev/null >>"$HOME/uvicorn.log" 2>&1 &
      sleep 4
    fi
  fi

  # C. Garante daemon privilegiado uid=2000(shell) na porta 5558 (que mantém o WakeLock de sistema)
  if ! tcp_open 5558; then
    CLASSPATH="/data/local/tmp/hybridbox_bridge.jar" \
      /system/bin/app_process / HybridBoxBridge wake >/dev/null 2>&1 || true
    adb connect 127.0.0.1:5555 >/dev/null 2>&1
    adb -s 127.0.0.1:5555 shell "nohup sh -c 'CLASSPATH=/data/local/tmp/hybridbox_bridge.jar /system/bin/app_process / HybridBoxBridge daemon 5558 </dev/null >/data/local/tmp/hb_daemon.log 2>&1 &' >/dev/null 2>&1" 2>/dev/null || true
  fi

  # D. Garante Termux:X11 (:0) e proteção contra toques fantasmas
  if ! pgrep -f "[t]ermux.x11" >/dev/null 2>&1; then
    nohup termux-x11 :0 -ac </dev/null >/dev/null 2>&1 &
  fi
  DISPLAY=:0 "$PREFIX/bin/python3" "$PROJECT_DIR/scripts/shield_x11_touch.py" >/dev/null 2>&1 || true

  # E. A cada ~24s (3 ciclos): Ping no Gateway Wi-Fi para evitar ARP drop / MediaTek Wi-Fi sleep + Hotspot de Resgate se sem Wi-Fi
  if [ $((LOOP_COUNT % 3)) -eq 0 ]; then
    termux-wake-lock 2>/dev/null || true
    pkill -f "[t]ermux-battery-status" 2>/dev/null || true
    pkill -f "[t]ermux-api BatteryStatus" 2>/dev/null || true
    if [ -x "$PREFIX/bin/hb-shell" ]; then
      "$PREFIX/bin/hb-shell" "if ip -4 addr show wlan0 2>/dev/null | grep -q 'inet '; then GW=\$(ip -4 route show table all 2>/dev/null | awk '/default via .* dev wlan0/ {print \$3; exit}'); [ -z \"\$GW\" ] && GW='192.168.0.1'; /system/bin/ping -c 1 -W 1 \"\$GW\" >/dev/null 2>&1; else RESCUE_SSID='HybridBox'; RESCUE_PASS='hybridbox123'; RESCUE_SEC='wpa2'; RESCUE_ENABLED='1'; [ -f /data/local/tmp/hb_rescue_wifi.conf ] && . /data/local/tmp/hb_rescue_wifi.conf 2>/dev/null; if [ \"\$RESCUE_ENABLED\" = '1' ] && [ -n \"\$RESCUE_SSID\" ]; then svc wifi enable 2>/dev/null; cmd wifi set-wifi-enabled enabled 2>/dev/null; cmd wifi set-scan-always-available enabled 2>/dev/null; cmd wifi start-scan >/dev/null 2>&1; if cmd wifi list-scan-results 2>/dev/null | grep -qF \"\$RESCUE_SSID\"; then if [ \"\$RESCUE_SEC\" = 'open' ] || [ -z \"\$RESCUE_PASS\" ]; then cmd wifi connect-network \"\$RESCUE_SSID\" open >/dev/null 2>&1; else cmd wifi connect-network \"\$RESCUE_SSID\" \"\$RESCUE_SEC\" \"\$RESCUE_PASS\" >/dev/null 2>&1; fi; fi; fi; fi" >/dev/null 2>&1 || true
    else
      GW_IP=$(ip -4 route show table all 2>/dev/null | awk '/default via .* dev wlan0/ {print $3; exit}')
      [ -z "$GW_IP" ] && GW_IP="192.168.0.1"
      /system/bin/ping -c 1 -W 1 "$GW_IP" >/dev/null 2>&1 || true
    fi
  fi

  # F. A cada ~96s (12 ciclos): Revalida watchdog de sistema, permissões MIUI Autostart (10008) e Eco-Standby (<15% bateria)
  SLEEP_SEC=8
  if [ $((LOOP_COUNT % 12)) -eq 0 ]; then
    ensure_system_watchdog
    if [ -x "$PREFIX/bin/hb-shell" ]; then
      BAT_STATE=$("$PREFIX/bin/hb-shell" "dumpsys deviceidle disable 2>/dev/null; settings put global wifi_sleep_policy 2 2>/dev/null; for p in com.termux com.termux.boot com.termux.x11 com.termux.api; do appops set \$p 10008 allow 2>/dev/null; cmd appops set \$p RUN_IN_BACKGROUND allow 2>/dev/null; done; dumpsys battery 2>/dev/null" 2>/dev/null)
      if echo "$BAT_STATE" | grep -q "USB powered: false" && echo "$BAT_STATE" | grep -q "AC powered: false"; then
        UNPLUGGED_CYCLES=$((UNPLUGGED_CYCLES + 1))
        BAT_LVL=$(echo "$BAT_STATE" | awk '/level:/ {print $2; exit}')
        # Reduz brilho da tela quebrada para 0 em modo manual para economizar bateria sem interromper jogos ou Miracast
        "$PREFIX/bin/hb-shell" "settings put system screen_brightness_mode 0 2>/dev/null; settings put system screen_brightness 0 2>/dev/null" >/dev/null 2>&1 || true
        if [ -n "$BAT_LVL" ] && [ "$BAT_LVL" -le 15 ] 2>/dev/null; then
          SLEEP_SEC=16
        fi
      else
        UNPLUGGED_CYCLES=0
      fi
    fi
  fi

  sleep "$SLEEP_SEC"
done
