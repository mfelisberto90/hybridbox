#!/data/data/com.termux/files/usr/bin/bash
export PREFIX=/data/data/com.termux/files/usr
export HOME=/data/data/com.termux/files/home
export PATH=$PREFIX/bin:$PATH
export LD_LIBRARY_PATH=$PREFIX/lib
export DEBIAN_FRONTEND=noninteractive

mkdir -p $HOME/.ssh
chmod 700 $HOME/.ssh
touch $HOME/.ssh/authorized_keys
if [ -n "$HYBRIDBOX_SSH_PUBKEY" ]; then
    grep -qxF "$HYBRIDBOX_SSH_PUBKEY" $HOME/.ssh/authorized_keys 2>/dev/null || echo "$HYBRIDBOX_SSH_PUBKEY" >> $HOME/.ssh/authorized_keys
fi
chmod 600 $HOME/.ssh/authorized_keys

if [ ! -x "$PREFIX/bin/sshd" ]; then
    apt-get update -y
    apt-get install -y -o Dpkg::Options::="--force-confnew" openssh git rsync
fi

ssh-keygen -A
pkill sshd 2>/dev/null || true
$PREFIX/bin/sshd
echo "=== SSHD INICIADO NA PORTA 8022 (USER: $(whoami)) ==="
