#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# HybridBox Remote PWA — Inicializador de Sessão (Termux:X11 + XFCE4 + ADB + PWA)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR" || exit 1

export PREFIX=/data/data/com.termux/files/usr
export HOME=/data/data/com.termux/files/home
export PATH=$PREFIX/bin:/system/bin:/system/xbin
export LD_LIBRARY_PATH=$PREFIX/lib
export DISPLAY=:0
export PULSE_SERVER=127.0.0.1
export MOZ_DISABLE_CONTENT_SANDBOX=1

echo "[*] Ativando Wake-Lock do Termux..."
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock || true
fi

# 0. Instala hb-shell, sudo (hb-sudo) e garante auto-start no ~/.bashrc e ~/.termux/boot
sed -i 's/\r$//' "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR/hb-shell" "$SCRIPT_DIR/hb-sudo" 2>/dev/null || true
if [ -f "$SCRIPT_DIR/hb-shell" ]; then
  cp "$SCRIPT_DIR/hb-shell" "$PREFIX/bin/hb-shell" 2>/dev/null || true
  chmod 755 "$PREFIX/bin/hb-shell" 2>/dev/null || true
fi
if [ -f "$SCRIPT_DIR/hb-sudo" ]; then
  cp "$SCRIPT_DIR/hb-sudo" "$PREFIX/bin/sudo" 2>/dev/null || true
  chmod 755 "$PREFIX/bin/sudo" 2>/dev/null || true
fi
chmod +x "$SCRIPT_DIR/keep_awake.sh" "$SCRIPT_DIR/hb_system_watchdog.sh" "$SCRIPT_DIR/start.sh" "$SCRIPT_DIR/hb-sudo" 2>/dev/null || true

cat << 'EOF' > "$HOME/.bashrc"
export PREFIX=/data/data/com.termux/files/usr
export HOME=/data/data/com.termux/files/home
export PATH=$PREFIX/bin:/system/bin:/system/xbin
export LD_LIBRARY_PATH=$PREFIX/lib
pgrep -x sshd >/dev/null 2>&1 || sshd 2>/dev/null || true
command -v crond >/dev/null 2>&1 && (pgrep -x crond >/dev/null 2>&1 || crond 2>/dev/null || true)
_hb_ka_pid=$(cat "$PREFIX/tmp/hybridbox_keep_awake.pid" 2>/dev/null)
if [ -z "$_hb_ka_pid" ] || { [ ! -d "/proc/$_hb_ka_pid" ] && ! kill -0 "$_hb_ka_pid" 2>/dev/null && ! (kill -0 "$_hb_ka_pid" 2>&1 | grep -qiE "permission|permitted"); }; then
  nohup setsid "$PREFIX/bin/bash" "$HOME/hybridbox-remote-pwa/scripts/keep_awake.sh" </dev/null >/dev/null 2>&1 &
fi
unset _hb_ka_pid
EOF

mkdir -p "$HOME/.termux/boot" 2>/dev/null || true
cat << 'EOF' > "$HOME/.termux/boot/start-hybridbox.sh"
#!/data/data/com.termux/files/usr/bin/bash
export PREFIX=/data/data/com.termux/files/usr
export HOME=/data/data/com.termux/files/home
export PATH=$PREFIX/bin:/system/bin:/system/xbin
export LD_LIBRARY_PATH=$PREFIX/lib
termux-wake-lock 2>/dev/null || true
sshd 2>/dev/null || true
command -v crond >/dev/null 2>&1 && (pgrep -x crond >/dev/null 2>&1 || crond 2>/dev/null || true)
cd /data/data/com.termux/files/home/hybridbox-remote-pwa 2>/dev/null || true
nohup setsid /data/data/com.termux/files/usr/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8080 --log-level warning </dev/null >>/data/data/com.termux/files/home/uvicorn.log 2>&1 &
nohup setsid /data/data/com.termux/files/usr/bin/bash /data/data/com.termux/files/home/hybridbox-remote-pwa/scripts/keep_awake.sh </dev/null >/dev/null 2>&1 &
EOF
chmod +x "$HOME/.termux/boot/start-hybridbox.sh" 2>/dev/null || true

# 1. Inicia o servidor gráfico Termux:X11 (:0) caso ainda não esteja rodando
if ! pgrep -f "[t]ermux.x11" >/dev/null 2>&1; then
  echo "[*] Iniciando servidor gráfico termux-x11 :0..."
  nohup termux-x11 :0 -ac </dev/null >/dev/null 2>&1 &
  sleep 2
else
  echo "[+] Servidor termux-x11 :0 já está em execução."
fi

# 2. Inicia a sessão gráfica XFCE4 em segundo plano caso ainda não esteja rodando
if ! pgrep -f "[x]fce4-session" >/dev/null 2>&1; then
  echo "[*] Iniciando ambiente gráfico Linux Desktop (XFCE4) no DISPLAY=:0..."
  nohup dbus-launch --exit-with-session startxfce4 </dev/null >/dev/null 2>&1 &
  sleep 2
else
  echo "[+] Sessão XFCE4 já está em execução."
fi

# 2b. Desativa toques fantasmas (Lorie mouse / Lorie touch) no X11 e configura Firefox como WebBrowser padrão
python3 "$SCRIPT_DIR/shield_x11_touch.py" --full >/dev/null 2>&1 || true

# 3. Garante que o servidor OpenSSH (porta 8022) e o crond estejam ativos
if command -v sshd >/dev/null 2>&1; then
  pgrep -x sshd >/dev/null 2>&1 || sshd 2>/dev/null || true
fi
if command -v crond >/dev/null 2>&1; then
  pgrep -x crond >/dev/null 2>&1 || crond 2>/dev/null || true
fi

# 4. Conecta automaticamente ao ADB local (127.0.0.1:5555)
if command -v adb >/dev/null 2>&1; then
  echo "[*] Conectando ao ADB Loopback (127.0.0.1:5555)..."
  adb start-server >/dev/null 2>&1 || true
  adb connect 127.0.0.1:5555 >/dev/null 2>&1 || true
fi

# 5. Inicia o Guardião 24/7 (keep_awake.sh) em segundo plano
echo "[*] Verificando Guardião 24/7 (keep_awake.sh)..."
nohup setsid "$PREFIX/bin/bash" "$SCRIPT_DIR/keep_awake.sh" </dev/null >/dev/null 2>&1 &

# 6. Descobre o IP Wi-Fi local (usando socket UDP em Python para contornar bloqueio netlink do Android 11+)
LOCAL_IP=$(python3 -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); print(s.getsockname()[0]); s.close()" 2>/dev/null)
if [ -z "$LOCAL_IP" ]; then
  LOCAL_IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -n1)
fi
if [ -z "$LOCAL_IP" ]; then
  LOCAL_IP="127.0.0.1"
fi

echo ""
echo "=========================================================="
echo "  🚀 HYBRIDBOX REMOTE PWA ATIVO NA REDE WI-FI LOCAL!"
echo "  📱 Abra no seu Smartphone: http://${LOCAL_IP}:8080"
echo "  🌐 Endereço Universal:     http://hybridbox.local:8080"
echo "  🛡️  Guardião 24/7 Anti-Sleep: ATIVO"
echo "=========================================================="
echo ""

# 7. Se uvicorn ainda não estiver na porta 8080, inicia em background desacoplado (setsid)
if ! python3 -c "import socket; s=socket.create_connection(('127.0.0.1', 8080), 0.6); s.close()" 2>/dev/null; then
  nohup setsid python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8080 --log-level warning </dev/null >>"$HOME/uvicorn.log" 2>&1 &
  sleep 2
fi
echo "[+] Servidor FastAPI/Uvicorn rodando em background na porta 8080 (Log: ~/uvicorn.log)."
