#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# HybridBox Remote PWA — Script de Instalação Completa para Termux
# Dispositivo Alvo: Xiaomi Redmi Note 8 Pro (begonia) + Cabo USB DisplayLink
# ==============================================================================

set -e

echo "=========================================================="
echo "   INSTALANDO HYBRIDBOX REMOTE PWA (TERMUX + X11 + ADB)   "
echo "=========================================================="

# 1. Atualiza pacotes base e habilita repositório X11 (modo não-interativo sem travar em prompts do dpkg)
export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"
pkg install -y x11-repo tur-repo

# 2. Instala dependências de sistema, servidor X11, XFCE4, xdotool, OpenSSH, PRoot e ADB
pkg install -y \
  libc++ \
  clang \
  python \
  python-pip \
  openssh \
  git \
  rsync \
  proot \
  proot-distro \
  tsu \
  termux-x11-nightly \
  xfce4 \
  xfce4-terminal \
  thunar \
  firefox \
  xdotool \
  android-tools \
  dbus \
  iproute2 \
  cronie \
  termux-api

# 3. Instala bibliotecas Python para o servidor FastAPI + WebSockets + Xlib
# (Nota: no Termux aarch64 usamos pydantic<2 pure-python para não exigir compilação Rust do pydantic-core)
pip install \
  "pydantic<2" \
  "fastapi>=0.110.0,<0.116.0" \
  "uvicorn>=0.29.0" \
  "websockets>=12.0" \
  "python-xlib>=0.33"

# 4. Garante permissão de execução no script de inicialização, sudo sem senha (hb-sudo), hb-shell e sshd automático
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
chmod +x "$SCRIPT_DIR/start.sh" "$SCRIPT_DIR/hb-shell" "$SCRIPT_DIR/hb-sudo" 2>/dev/null || true
if command -v clang >/dev/null 2>&1 && [ -f "$SCRIPT_DIR/grab_ghost_touch.c" ]; then
  clang -O2 "$SCRIPT_DIR/grab_ghost_touch.c" -o "$SCRIPT_DIR/grab_ghost_touch" 2>/dev/null || true
  chmod 755 "$SCRIPT_DIR/grab_ghost_touch" 2>/dev/null || true
fi
cp "$SCRIPT_DIR/hb-shell" "$PREFIX/bin/hb-shell" 2>/dev/null || true
cp "$SCRIPT_DIR/hb-sudo" "$PREFIX/bin/sudo" 2>/dev/null || true
chmod 755 "$PREFIX/bin/hb-shell" "$PREFIX/bin/sudo" 2>/dev/null || true
grep -q "sshd" "$HOME/.bashrc" 2>/dev/null || echo "pgrep -x sshd >/dev/null 2>&1 || sshd" >> "$HOME/.bashrc"

# 4b. (Opcional) Configura Debian PRoot com sudo sem senha caso proot-distro esteja presente
if command -v proot-distro >/dev/null 2>&1; then
  if [ ! -d "$PREFIX/var/lib/proot-distro/containers/debian/rootfs" ] && [ ! -d "$PREFIX/var/lib/proot-distro/installed-rootfs/debian" ]; then
    echo "[*] Instalando Debian Linux rootfs via proot-distro (para suporte completo a pacotes Debian via sudo)..."
    proot-distro install -n debian public.ecr.aws/debian/debian:bookworm-slim || proot-distro install debian || true
  fi
  if [ -d "$PREFIX/var/lib/proot-distro/containers/debian/rootfs" ] || [ -d "$PREFIX/var/lib/proot-distro/installed-rootfs/debian" ]; then
    proot-distro login debian --shared-tmp -- bash -c "apt-get update && apt-get install -y sudo && mkdir -p /etc/sudoers.d && echo 'ALL ALL=(ALL:ALL) NOPASSWD: ALL' > /etc/sudoers.d/hybridbox && chmod 440 /etc/sudoers.d/hybridbox" 2>/dev/null || true
  fi
fi

# 5. Configura inicialização automática via Termux:Boot (~/.termux/boot/)
mkdir -p "$HOME/.termux/boot"
cat <<EOF > "$HOME/.termux/boot/start-hybridbox.sh"
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
bash "$PROJECT_DIR/scripts/start.sh" > "$HOME/hybridbox.log" 2>&1 &
EOF
chmod +x "$HOME/.termux/boot/start-hybridbox.sh"

echo ""
echo "[+] Instalação concluída com sucesso!"
echo "[+] Para iniciar o servidor agora, execute:"
echo "    bash $SCRIPT_DIR/start.sh"
