# 📖 HybridBox — Documentação Completa (Português / PT-BR)

> **Transformando um Celular com Tela Quebrada em um Console Híbrido 3-em-1: Android TV Box, Linux Desktop XFCE4 e Vídeo Game Retrô**
>
> *Testado em um **Xiaomi Redmi Note 8 Pro (`begonia`)** com a tela quebrada — compatível com **qualquer celular, tablet ou gadget Android** (Samsung, Xiaomi, Redmi, readMi, Motorola, Asus, OnePlus, etc.).*

---

## Sumário

1. [Finalidade do Projeto](#1-finalidade-do-projeto)
2. [Aparelho Testado e Compatibilidade Universal](#2-aparelho-testado-e-compatibilidade-universal)
3. [Como Nós Fizemos (Passo a Passo da Engenharia)](#3-como-nós-fizemos-passo-a-passo-da-engenharia)
4. [Instalando Outros Aplicativos via `sudo` no Linux](#4-instalando-outros-aplicativos-via-sudo-no-linux)
5. [Como Instalar e Reproduzir em Casa (Modo Mais Fácil Possível)](#5-como-instalar-e-reproduzir-em-casa-modo-mais-fácil-possível)
6. [Conectando em Qualquer TV ou Projetor (`Projector`)](#6-conectando-em-qualquer-tv-ou-projetor-projector)
7. [Modo Viagem (Wi-Fi Portátil e Hotspot de Resgate)](#7-modo-viagem-wi-fi-portátil-e-hotspot-de-resgate)
8. [Recuperação de Bateria 0% (Plug & Revive)](#8-recuperação-de-bateria-0-plug--revive)

---

## 1. Finalidade do Projeto

Sabe aquele smartphone excelente que ficou esquecido na gaveta porque a **tela quebrou (`screen broken` / `broken phone`)** ou o touch ficou disparando "toques fantasmas" sozinho, e o conserto da tela custa quase o preço de um aparelho usado?

O **HybridBox** nasceu exatamente para reaproveitar esse hardware! Em vez de descartar um aparelho com processador Octa-Core, 6 GB de RAM, Wi-Fi 5GHz e Bluetooth, nós criamos uma plataforma completa que transforma o celular sem tela útil em um **Console Híbrido 3-em-1 controlado 100% pelo navegador do seu celular principal (via PWA)**:

1. 📺 **Android TV Box & Central de Projetor (`Projector`)**: Interface de TV em modo paisagem (*Projectivy Launcher*, *SmartTube*, *Stremio*, *Kodi*), transmitindo imagem e som em 1080p @ 60fps sem fio via Miracast/Cast para qualquer **Projector** ou **Smart TV**, ou via cabo USB-HDMI (DisplayLink).
2. 🐧 **Computador Linux Desktop Completo (`Termux:X11` + `XFCE4` + `Debian`)**: Ambiente de área de trabalho Linux real com navegador Firefox, gerenciador de arquivos Thunar, terminal XFCE e comando **`sudo` sem senha** configurado para instalar qualquer programa Linux (`sudo apt install ...`).
3. 🎮 **Console de Jogos Retrô (SNES, NeoGeo, Arcade/MAME e Mega Drive)**: Galeria visual com capas dos jogos que abre a ROM escolhida direto na TV/Projetor em tela cheia horizontal, transformando a tela do seu celular principal em um controle de vídeo game (ou pareando controles Bluetooth).

> 🤖 **Nota de Transparência e Fase de Testes**: Este é um **projeto pessoal desenvolvido com auxílio de Inteligência Artificial (IA)** e disponibilizado gratuitamente como código aberto (Licença MIT) para ajudar outras pessoas a reaproveitarem celulares com tela quebrada. O projeto está atualmente em **fase de testes (Beta)** e **aceitamos sugestões, ideias, issues e Pull Requests!**

### 📸 Fotos Reais dos Portais Principais do App em Funcionamento

Todas as capturas abaixo foram tiradas diretamente do **HybridBox Remote PWA** (`http://hybridbox.local:8080`) conectado em tempo real ao **Xiaomi Redmi Note 8 Pro (`begonia`)**:

| 📺 Portal TV (D-Pad & Mídia) | 🚀 Gaveta Rápida de Aplicativos | 🖱️ Trackpad Multitoque Linux X11 |
| :---: | :---: | :---: |
| <img src="screenshots/01-tv-portal-dpad.png" alt="Portal TV D-Pad" width="260" /> | <img src="screenshots/02-system-app-launcher.png" alt="Gaveta de Aplicativos" width="260" /> | <img src="screenshots/03-linux-trackpad-portal.png" alt="Trackpad Linux X11" width="260" /> |

| 💻 Terminal SSH Web (`sudo` em Ação) | 📚 Galeria Visual de Jogos (53+ ROMs) | 🍄 Controle Super Nintendo Tátil |
| :---: | :---: | :---: |
| <img src="screenshots/04-linux-ssh-sudo-portal.png" alt="Terminal SSH Web com sudo" width="260" /> | <img src="screenshots/05-games-rom-library-portal.png" alt="Galeria Visual de Jogos" width="260" /> | <img src="screenshots/06-games-snes-controller-portal.png" alt="Controle Super Nintendo" width="260" /> |

<p align="center">
  <img src="screenshots/07-games-landscape-arcade-hud.png" alt="Controle Arcade / NeoGeo 6 Botões em Tela Cheia Paisagem" width="800" />
</p>

| 🎮 Controles, Skins & Multiplayer | 📽️ Qualquer TV ou Projetor (`Projector`) | 📡 Wi-Fi Portátil & Hotspot de Resgate | ⚡ Bateria ao Vivo & Guia de Resgate 0% |
| :---: | :---: | :---: | :---: |
| <img src="screenshots/08-controllers-multiplayer-modal.png" alt="Modal de Controles e Multiplayer" width="200" /> | <img src="screenshots/09-projector-tv-modal.png" alt="Modal de TV e Projetor" width="200" /> | <img src="screenshots/10-portable-wifi-travel-modal.png" alt="Modal de Wi-Fi Portátil e Hotspot de Resgate" width="200" /> | <img src="screenshots/11-battery-recovery-guide.png" alt="Telemetria de Bateria e Guia de Recuperação" width="200" /> |

---

## 2. Aparelho Testado e Compatibilidade Universal

### Celular Utilizado nos Testes Reais
- **Modelo**: **Xiaomi Redmi Note 8 Pro** (codinome `begonia`)
- **Processador**: MediaTek Helio G90T Octa-Core
- **Memória**: 6 GB RAM / 128 GB Armazenamento
- **Sistema**: Android 11 / MIUI 12.5 (**Sem Root**)
- **Condição da Tela**: Tela quebrada com digitizer (`NVTCapacitiveTouchScreen` em `/dev/input/event2`) disparando toques fantasmas contínuos a 60Hz.
- **Saída de Vídeo Testada**: **Projector** sem fio via Miracast (`1920x1080 @ 60fps`), Smart TVs e adaptador USB DisplayLink HDMI.

### Funciona em Qualquer Celular ou Gadget Android!
A arquitetura do HybridBox não depende de peças exclusivas da Xiaomi. Ela funciona em **qualquer celular, tablet ou gadget Android (Android 8.0 ou superior)**:
- **Samsung Galaxy** (Linha S, Note, A, M, J, Tab — funciona tanto via Smart View/Miracast quanto via cabo USB-C HDMI / Samsung DeX)
- **Xiaomi / Redmi / readMi / POCO** (Redmi Note 7, 8, 8 Pro, 9, 10, 11, 12, 13, Poco X3, Mi 9/10/11)
- **Motorola** (Moto G, Moto One, Moto Edge)
- **Asus, OnePlus, Realme, LG, Google Pixel, TV Boxes e Dongles Android**

---

## 3. Como Nós Fizemos (Passo a Passo da Engenharia)

Para transformar o Xiaomi Redmi Note 8 Pro com tela quebrada em um console autônomo que nunca trava e nunca precisa ser tocado fisicamente, nós construímos 7 soluções técnicas fundamentais:

1. **Bloqueio de Toques Fantasmas no Kernel (`scripts/grab_ghost_touch.c`)**:
   - Telas quebradas enviam cliques falsos ininterruptos para o Android. Como o usuário `shell` (`uid=2000`) do ADB pertence ao grupo `input` (`gid=1004`), escrevemos um daemon em C que abre `/dev/input/event2` (`NVTCapacitiveTouchScreen`), limpa os slots multi-touch presos (`ABS_MT_TRACKING_ID = -1`) e executa `ioctl(fd, EVIOCGRAB, 1)`.
   - Isso bloqueia 100% dos toques físicos da tela quebrada na raiz do kernel Linux, mas mantém funcionando perfeitamente os comandos do controle remoto (`input tap`, `input keyevent`, controles Bluetooth e mouse do Linux X11).
2. **Ponte Java Privilegiada Sem Root (`backend/HybridBoxBridge.java`)**:
   - Compilamos o `hybridbox_bridge.jar` que roda via `/system/bin/app_process` na porta local `5558` como `uid=2000 (shell)`. Ele segura um `PARTIAL_WAKE_LOCK` de sistema via `IPowerManager` para o celular nunca dormir e executa comandos Android em menos de 5 milissegundos através do utilitário `hb-shell`.
3. **Guardiões Gêmeos 24/7 (`keep_awake.sh` + `hb_system_watchdog.sh`)**:
   - A MIUI e o Android 11+ costumam fechar apps em segundo plano. Nosso watchdog desativa o *Doze Mode*, desativa o *Phantom Process Killer* do Android, concede permissão de *Autostart* da MIUI (`appops 10008 allow`) e zera o brilho físico da tela quebrada quando está fora da tomada para economizar bateria sem interromper a projeção na TV/Projector.
4. **Servidor FastAPI + WebSockets + PWA (`backend/main.py` & `frontend/`)**:
   - O celular hospeda na porta `8080` um aplicativo web progressivo (PWA) que você instala na tela inicial do seu celular principal. Ele oferece D-Pad de TV, Trackpad multitoque com filtro anti-tremor para o Linux, teclado virtual e controles de vídeo game com resposta imediata via WebSocket.
5. **Automação de Conexão com Qualquer TV ou `Projector` (`backend/projector_controller.py`)**:
   - Quando você clica em **"Scan Any TV or Projector"**, o celular abre as configurações de transmissão sem fio (`WifiDisplaySettings`), lê a lista de TVs e projetores na tela via `uiautomator dump`, clica automaticamente no **Projector** ou Smart TV e confirma sozinho qualquer janela de permissão ("Iniciar agora" / "Aceitar").
6. **Ambiente Linux XFCE4 com `sudo` Sem Senha (`scripts/hb-sudo`)**:
   - Integramos o servidor gráfico `Termux:X11 (:0)` com a área de trabalho `XFCE4` e uma distribuição **Debian Linux** (`proot-distro`) com o wrapper inteligente `/data/data/com.termux/files/usr/bin/sudo`.
7. **Recuperação Automática de Bateria 0% (`scripts/pc_usb_autorevive.py` + `Termux:Boot`)**:
   - Se a bateria acabar completamente (`0%`), basta plugar o cabo USB ou ligar o aparelho: o `Termux:Boot` e o guardião `pc_usb_autorevive.py` religam o ADB sem fio (`5555`), o daemon (`5558`) e o servidor (`8080`) sem precisar tocar na tela quebrada.

---

## 4. Instalando Outros Aplicativos via `sudo` no Linux

Uma das funções mais poderosas do **HybridBox** é que, no modo **🐧 Linux**, você tem um computador Linux completo na sua TV ou **Projector** e pode instalar novos aplicativos usando o comando **`sudo`** exatamente como em um PC Ubuntu/Debian!

Nós criamos o utilitário [`scripts/hb-sudo`](../scripts/hb-sudo) (instalado automaticamente em `/data/data/com.termux/files/usr/bin/sudo`) aliado ao container **Debian (`proot-distro`)** com `NOPASSWD: ALL`.

### Como usar o `sudo`:
Você pode abrir o **XFCE Terminal** na tela da TV/Projector ou usar a aba **💻 SSH & Wi-Fi** direto na tela do seu celular principal e digitar:

```bash
# Atualizar a lista de pacotes
sudo apt update && sudo apt upgrade -y

# Instalar programas gráficos de escritório, imagem, áudio e vídeo
sudo apt install -y vlc gimp libreoffice inkscape audacity

# Instalar ferramentas de desenvolvimento e utilitários de terminal
sudo apt install -y git curl wget htop neofetch vim nano tmux nodejs python3-pip

# Abrir qualquer programa instalado direto na tela da TV / Projector (:0)
DISPLAY=:0 vlc &
DISPLAY=:0 gimp &
```

### Entrando como `root` no Debian Linux completo:
Se você quiser instalar um pacote `.deb` específico do Debian ou abrir um shell `root` completo:
```bash
sudo -i
# Agora você está como root@debian compartilhando a mesma tela gráfica DISPLAY=:0!
apt update && apt install -y chromium
```

### Usando `sudo` para comandos privilegiados do Android:
Você também pode usar `sudo` para executar comandos internos do sistema Android (`pm`, `am`, `settings`, `cmd`, `svc`, `dumpsys`, `wm`):
```bash
# Instalar um arquivo APK no Android pelo terminal Linux
sudo pm install -r /sdcard/Download/meu_app.apk
```

---

## 5. Como Instalar e Reproduzir em Casa (Modo Mais Fácil Possível — Zero-Config)

Nós empacotamos o projeto com instaladores de **1 clique** (`install.bat` para Windows e `install.sh` para Linux/macOS/Termux) e **Auto-Descoberta Zero-Config**: você não precisa editar nenhum IP, endereço MAC ou nome de usuário do Termux no código! O sistema descobre automaticamente o IP do celular e o usuário SSH (`u0_a...`) em menos de 1 segundo via mDNS (`hybridbox.local`), ADB ou varredura paralela na sub-rede `/24`, salvando o cache localmente em `.hybridbox_runtime.json` (ignorado pelo Git).

### Opção A: Instalação Rápida em 1 Clique pelo PC (Windows)
1. Ative a **Depuração USB** nas *Opções do Desenvolvedor* do celular Android e conecte-o ao PC via cabo USB.
2. Baixe ou clone este repositório:
   ```bash
   git clone https://github.com/mfelisberto90/hybridbox.git
   cd hybridbox
   ```
3. Dê dois cliques no arquivo **`install.bat`** (ou execute `.\install.bat` no terminal; use `.\install.bat --no-start` se quiser apenas provisionar sem iniciar o loop do servidor).
   - O instalador cria automaticamente o ambiente Python, instala as dependências, detecta o celular via ADB/Wi-Fi, injeta automaticamente a chave SSH pública do PC (`~/.ssh/id_ed25519.pub`) no Termux, instala os APKs da pasta `apks/` (Termux, Termux:X11, Termux:Boot, Projectivy Launcher, SmartTube e Emuladores), sincroniza os scripts e abre o painel em `http://localhost:8080`!
   - Para enviar atualizações futuras pelo Wi-Fi a qualquer momento, basta rodar **`atualizar_via_wifi.bat`** (ou `atualizar_via_wifi.bat --sync-only`).

### Opção B: Instalação Direta no Celular via Termux (`install.sh`)
Dentro do aplicativo **Termux** no celular Android (ou via SSH), execute apenas:
```bash
git clone https://github.com/mfelisberto90/hybridbox.git ~/hybridbox-remote-pwa
cd ~/hybridbox-remote-pwa
bash install.sh
```
O script `install.sh` detecta automaticamente que está rodando no Termux, instala o `Termux:X11`, `XFCE4`, `Firefox`, `Thunar`, `OpenSSH`, `Python/FastAPI`, `proot-distro` (Debian Bookworm) e o comando `sudo`, configura o `Termux:Boot` e já inicia o servidor na porta `8080`!

---

## 6. Conectando em Qualquer TV ou Projetor (`Projector`)

1. Abra o controle **HybridBox** no navegador do seu celular principal (`http://hybridbox.local:8080`).
2. Toque no botão **📽️ Any TV / Projector** na barra superior.
3. No seu **Projector** ou **Smart TV** (Samsung, LG, Sony, TCL, Roku, Fire TV), abra a função **Screen Mirroring / Miracast / Cast**.
4. Toque em **📡 Scan Any TV or Projector (Auto-Connect)** no PWA. O celular acende a lógica de vídeo, localiza o **Projector** ou TV e inicia o espelhamento em 1080p @ 60fps sem você precisar tocar na tela quebrada!

---

## 7. Modo Viagem (Wi-Fi Portátil e Hotspot de Resgate)

- **Pré-salvar Wi-Fi de Viagem**: Na aba **📡 Portable Wi-Fi & Travel**, você pode salvar o nome e a senha do Wi-Fi de um hotel ou casa de amigo antes de sair de casa.
- **Hotspot de Resgate (`HybridBox` / `hybridbox123`)**: Se você chegar a um local novo e o celular com tela quebrada ficar sem conexão Wi-Fi por 20 segundos, ele procura automaticamente uma rede chamada **`HybridBox`** com a senha **`hybridbox123`**. Basta ligar o Roteador Wi-Fi (Hotspot) do seu celular principal com esse nome e senha que o console conecta no seu celular sozinho!

---

## 8. Modo de Economia de Bateria / Hibernação (`Eco-Standby`) + Interruptor (`⏻`) e Conexão 24/7 Anti-Queda

- **Conexão 24/7 Sem Quedas (`WIFI_MODE_FULL_LOW_LATENCY = 4`)**: O daemon `HybridBoxBridge` (`127.0.0.1:5558`, rodando como `uid=2000 shell`) mantém bloqueios permanentes `WIFI_MODE_FULL_LOW_LATENCY` (`type=4`), `WIFI_MODE_FULL_HIGH_PERF` (`type=3`) e `MulticastLock` no `IWifiManager` do Android, impedindo que o chip Wi-Fi entre em *WMM Power Save* quando a tela apaga. Além disso, o `hb_system_watchdog.sh` neutraliza o `com.miui.powerkeeper` e o `com.xiaomi.joyose` via `appops deny`, coloca o Termux na *whitelist* do `netpolicy` e mantém a tabela ARP aquecida a cada 4 segundos.
- **Auto-Hibernação por Inatividade (`5 min`, `15 min`, `30 min`, `60 min` ou `Off`)**: Se o HybridBox ficar `X` minutos parado (padrão **15 min**) sem uso em **TV**, **Linux** ou **Games** (e sem vídeo/filme em reprodução ativa no `media_session`), ele entra automaticamente em **Eco-Standby**: troca o WakeLock para `PARTIAL_WAKE_LOCK`, apaga a tela física e a GPU (`KEYCODE_SLEEP` + brilho `0`) e pausa os processos gráficos do X11 (`SIGSTOP`), mantendo o Wi-Fi Low-Latency e o servidor `8080` **100% online**.
- **Interruptor (`⏻`) no Topo e na Tela de Hibernação**: Você pode ativar ou desativar o modo de economia a qualquer momento pelo botão interruptor **`⏻`** no topo do app. Quando acionado para sair da hibernação, ele acorda o Xiaomi em `<200ms` e leva o aplicativo **direto para a tela principal (`TV Box` / `Projectivy Launcher`)**.

---

## 9. Recuperação de Bateria 0% (Plug & Revive)

Se a bateria do celular descarregar até `0%` e ele desligar:
1. Conecte o celular na tomada ou na porta USB do computador e ligue-o no botão físico Power.
2. O **Termux:Boot** sobe automaticamente o servidor SSH (`8022`), o servidor web (`8080`) e os guardiões em segundo plano.
3. Se conectado ao PC com `iniciar_hybridbox_pwa.bat` aberto (ou rodando `python scripts/pc_usb_autorevive.py --once`), o script detecta o celular via USB, sincroniza os arquivos e reativa o ADB sem fio (`5555`) e o bloqueador de toques fantasmas em menos de 10 segundos!
