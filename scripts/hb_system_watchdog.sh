#!/system/bin/sh
# ==============================================================================
# HybridBox System Watchdog (uid=2000 shell) — Guardião Cruzado em /data/local/tmp
# Mantém ADB TCP (5555), Daemon (5558), Anti-Ghost-Touch, Anti-Doze e revigora
# o guardião do Termux (keep_awake.sh) caso a MIUI mate processos em background.
# ==============================================================================

trap '' HUP INT TERM

LOCK="/data/local/tmp/hb_sys_watchdog.pid"
if [ -f "$LOCK" ]; then
  OPID=$(cat "$LOCK" 2>/dev/null)
  if [ -n "$OPID" ] && [ "$OPID" != "$$" ] && kill -0 "$OPID" 2>/dev/null; then
    exit 0
  fi
fi
echo "$$" > "$LOCK"

# Blindagem contra Doze Mode, Wi-Fi Sleep, MIUI PowerKeeper e Phantom Process Killer
settings put global wifi_sleep_policy 2 2>/dev/null
settings put global wifi_scan_throttle_enabled 0 2>/dev/null
settings put global stay_on_while_plugged_in 7 2>/dev/null
settings put system screen_off_timeout 2147483647 2>/dev/null
settings put global settings_enable_monitor_phantom_procs false 2>/dev/null
device_config put activity_manager max_phantom_processes 2147483647 2>/dev/null
dumpsys deviceidle disable 2>/dev/null

# Neutraliza matança em background do com.miui.powerkeeper e com.xiaomi.joyose (sem desinstalar para evitar bootloop)
for badpkg in com.miui.powerkeeper com.xiaomi.joyose; do
  cmd appops set $badpkg WRITE_SETTINGS deny 2>/dev/null
  cmd appops set $badpkg GET_USAGE_STATS deny 2>/dev/null
  cmd appops set $badpkg RUN_IN_BACKGROUND deny 2>/dev/null
  cmd appops set $badpkg RUN_ANY_IN_BACKGROUND deny 2>/dev/null
  cmd appops set $badpkg WAKE_LOCK deny 2>/dev/null
  appops set $badpkg 10008 deny 2>/dev/null
done

TERMUX_UID=$(stat -c %u /data/data/com.termux 2>/dev/null)
if [ -n "$TERMUX_UID" ]; then
  cmd netpolicy add restrict-background-whitelist "$TERMUX_UID" >/dev/null 2>&1
fi

for pkg in com.termux com.termux.boot com.termux.x11 com.termux.api com.spocky.projengmenu \
  com.explusalpha.Snes9xPlus com.explusalpha.NeoEmu com.explusalpha.MdEmu \
  com.swordfish.lemuroid com.seleuco.mame4d2024 com.seleuco.mame4droid; do
  dumpsys deviceidle whitelist +$pkg 2>/dev/null
  cmd appops set $pkg RUN_IN_BACKGROUND allow 2>/dev/null
  cmd appops set $pkg RUN_ANY_IN_BACKGROUND allow 2>/dev/null
  cmd appops set $pkg WAKE_LOCK allow 2>/dev/null
  appops set $pkg 10008 allow 2>/dev/null
done

# Blindagem de permissões do Projectivy Launcher para nunca abrir Onboarding/Notification Settings nem cair na Home MIUI em retrato
cmd notification allow_listener com.spocky.projengmenu/com.spocky.projengmenu.services.notification.NotificationListener 2>/dev/null
settings put secure enabled_accessibility_services com.spocky.projengmenu/com.spocky.projengmenu.services.ProjectivyAccessibilityService 2>/dev/null
settings put secure accessibility_enabled 1 2>/dev/null
appops set com.spocky.projengmenu SYSTEM_ALERT_WINDOW allow 2>/dev/null
appops set com.spocky.projengmenu READ_EXTERNAL_STORAGE allow 2>/dev/null
appops set com.spocky.projengmenu LEGACY_STORAGE allow 2>/dev/null
cmd role add-role-holder android.app.role.HOME com.spocky.projengmenu 2>/dev/null
settings put system accelerometer_rotation 0 2>/dev/null
settings put system user_rotation 1 2>/dev/null

# Inicializa configuração padrão do Hotspot de Resgate (Modo Viagem) se ainda não existir
RESCUE_CONF="/data/local/tmp/hb_rescue_wifi.conf"
if [ ! -f "$RESCUE_CONF" ]; then
  cat << 'EOF' > "$RESCUE_CONF"
RESCUE_SSID='HybridBox'
RESCUE_PASS='hybridbox123'
RESCUE_SEC='wpa2'
RESCUE_ENABLED='1'
EOF
  chmod 644 "$RESCUE_CONF" 2>/dev/null
fi
. "$RESCUE_CONF" 2>/dev/null
cmd wifi set-scan-always-available enabled 2>/dev/null
if [ -n "$RESCUE_SSID" ]; then
  if [ "$RESCUE_SEC" = "open" ] || [ -z "$RESCUE_PASS" ]; then
    cmd wifi add-network "$RESCUE_SSID" open >/dev/null 2>&1
  else
    cmd wifi add-network "$RESCUE_SSID" "${RESCUE_SEC:-wpa2}" "$RESCUE_PASS" >/dev/null 2>&1
  fi
fi

WIFI_DOWN_CYCLES=0

while true; do
  if [ "$(settings get system user_rotation 2>/dev/null)" != "1" ]; then
    settings put system accelerometer_rotation 0 2>/dev/null
    settings put system user_rotation 1 2>/dev/null
  fi
  if [ "$(getprop service.adb.tcp.port)" != "5555" ] || [ "$(getprop init.svc.adbd)" != "running" ]; then
    setprop service.adb.tcp.port 5555 2>/dev/null
    start adbd 2>/dev/null
  fi

  # Verifica conectividade Wi-Fi (wlan0): se ficar >20s (3 ciclos de 8s) sem IP, aciona o Hotspot de Resgate
  if ip -4 addr show wlan0 2>/dev/null | grep -q "inet "; then
    WIFI_DOWN_CYCLES=0
  else
    WIFI_DOWN_CYCLES=$((WIFI_DOWN_CYCLES + 1))
    if [ "$WIFI_DOWN_CYCLES" -ge 3 ]; then
      WIFI_DOWN_CYCLES=0
      [ -f "$RESCUE_CONF" ] && . "$RESCUE_CONF" 2>/dev/null
      if [ "${RESCUE_ENABLED:-1}" = "1" ] && [ -n "$RESCUE_SSID" ]; then
        svc wifi enable 2>/dev/null
        cmd wifi set-wifi-enabled enabled 2>/dev/null
        cmd wifi set-scan-always-available enabled 2>/dev/null
        if [ "$RESCUE_SEC" = "open" ] || [ -z "$RESCUE_PASS" ]; then
          cmd wifi add-network "$RESCUE_SSID" open >/dev/null 2>&1
        else
          cmd wifi add-network "$RESCUE_SSID" "${RESCUE_SEC:-wpa2}" "$RESCUE_PASS" >/dev/null 2>&1
        fi
        cmd wifi start-scan >/dev/null 2>&1
        if cmd wifi list-scan-results 2>/dev/null | grep -qF "$RESCUE_SSID"; then
          if [ "$RESCUE_SEC" = "open" ] || [ -z "$RESCUE_PASS" ]; then
            cmd wifi connect-network "$RESCUE_SSID" open >/dev/null 2>&1
          else
            cmd wifi connect-network "$RESCUE_SSID" "${RESCUE_SEC:-wpa2}" "$RESCUE_PASS" >/dev/null 2>&1
          fi
        fi
      fi
    fi
  fi

  if ! ps -ef | grep -q "[H]ybridBoxBridge daemon"; then
    if [ ! -s /data/local/tmp/hybridbox_bridge.jar ]; then
      run-as com.termux /data/data/com.termux/files/usr/bin/cat /data/data/com.termux/files/home/hybridbox-remote-pwa/backend/hybridbox_bridge.jar > /data/local/tmp/hybridbox_bridge.jar.tmp 2>/dev/null
      if [ -s /data/local/tmp/hybridbox_bridge.jar.tmp ]; then
        mv /data/local/tmp/hybridbox_bridge.jar.tmp /data/local/tmp/hybridbox_bridge.jar 2>/dev/null
      fi
    fi
    nohup env CLASSPATH=/data/local/tmp/hybridbox_bridge.jar /system/bin/app_process / HybridBoxBridge daemon 5558 </dev/null >/data/local/tmp/hb_daemon.log 2>&1 &
  fi
  if [ -x /data/local/tmp/grab_ghost_touch ] && ! ps -ef | grep -q "[g]rab_ghost_touch"; then
    /data/local/tmp/grab_ghost_touch --daemon >/dev/null 2>&1 &
  fi
  KA_PID=$(run-as com.termux /data/data/com.termux/files/usr/bin/cat /data/data/com.termux/files/usr/tmp/hybridbox_keep_awake.pid 2>/dev/null)
  if [ -z "$KA_PID" ] || [ ! -d "/proc/$KA_PID" ]; then
    # Prioriza iniciar via SSH local (127.0.0.1:8022) para herdar o domínio SELinux real do Termux (untrusted_app_27)
    run-as com.termux /data/data/com.termux/files/usr/bin/env \
      HOME=/data/data/com.termux/files/home \
      PREFIX=/data/data/com.termux/files/usr \
      PATH=/data/data/com.termux/files/usr/bin:/system/bin \
      LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib \
      /data/data/com.termux/files/usr/bin/bash -c \
      "ssh -p 8022 -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=no 127.0.0.1 'nohup setsid /data/data/com.termux/files/usr/bin/bash /data/data/com.termux/files/home/hybridbox-remote-pwa/scripts/keep_awake.sh </dev/null >/dev/null 2>&1 &' 2>/dev/null || nohup setsid /data/data/com.termux/files/usr/bin/bash /data/data/com.termux/files/home/hybridbox-remote-pwa/scripts/keep_awake.sh </dev/null >/dev/null 2>&1 &" >/dev/null 2>&1 &
  fi
  sleep 8
done
