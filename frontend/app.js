/**
 * HybridBox Remote PWA — Frontend Client
 * Controla D-Pad Android TV, Trackpad Multitoque X11 (com curva de aceleração),
 * Teclado Virtual e Alternador Instantâneo TV Box <-> Linux Desktop via WebSocket.
 */

(() => {
  "use strict";

  // Estado Global do Cliente
  const clientState = {
    mode: "tv", // "tv" | "linux" | "games"
    tvSubTab: "dpad", // "dpad" | "cursor"
    linuxSubTab: "trackpad", // "trackpad" | "ssh"
    gamesSubTab: "pad", // "pad" | "consoles" | "bluetooth"
    turboEnabled: false,
    activeSkin: "snes", // "snes" | "snes_us" | "mame" | "megadrive"
    activePlayer: 1, // 1..4
    photoModeEnabled: true,
    fullscreenLandscape: false,
    coinCount: 0,
    controllersList: [],
    ws: null,
    connected: false,
    consecutiveOfflineFailures: 0,
    standbyMode: false,
    autoStandbyMinutes: 15,
    standbyReason: "",
    apps: [],
    sensitivity: 1.65,
    scrollSensitivity: 0.45,
  };

  // Referências DOM
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const btnModeTv = document.getElementById("btnModeTv");
  const btnModeLinux = document.getElementById("btnModeLinux");
  const btnModeGames = document.getElementById("btnModeGames");
  const viewTv = document.getElementById("viewTv");
  const viewLinux = document.getElementById("viewLinux");
  const viewGames = document.getElementById("viewGames");
  const tabTvDpad = document.getElementById("tabTvDpad");
  const tabTvCursor = document.getElementById("tabTvCursor");
  const linuxSubTabs = document.getElementById("linuxSubTabs");
  const tvCursorSubTabs = document.getElementById("tvCursorSubTabs");
  const tabTvCursorBackDpad = document.getElementById("tabTvCursorBackDpad");
  const trackpadSurface = document.getElementById("trackpadSurface");
  const trackpadBadgeIcon = document.getElementById("trackpadBadgeIcon");
  const trackpadBadgeTitle = document.getElementById("trackpadBadgeTitle");
  const touchRipple = document.getElementById("touchRipple");
  const btnMouseLeft = document.getElementById("btnMouseLeft");
  const btnMouseRight = document.getElementById("btnMouseRight");
  const scrollStrip = document.getElementById("scrollStrip");
  const btnKeyboardToggle = document.getElementById("btnKeyboardToggle");
  const keyboardBar = document.getElementById("keyboardBar");
  const virtualKeyboardInput = document.getElementById("virtualKeyboardInput");
  const btnSendText = document.getElementById("btnSendText");
  const btnAppsDrawer = document.getElementById("btnAppsDrawer");
  const appsModal = document.getElementById("appsModal");
  const btnCloseModal = document.getElementById("btnCloseModal");
  const appsGrid = document.getElementById("appsGrid");

  /**
   * Feedback háptico curto no smartphone ao clicar em botões ou fazer tap no trackpad
   */
  function vibrate(ms = 12) {
    if (navigator.vibrate) {
      try {
        navigator.vibrate(ms);
      } catch (_) {
        // Ignora caso o navegador bloqueie vibração
      }
    }
  }

  /**
   * Envia pacote JSON pelo WebSocket se conectado
   */
  function sendWs(payload) {
    if (clientState.ws && clientState.ws.readyState === WebSocket.OPEN) {
      clientState.ws.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }

  /**
   * Atualiza a interface de acordo com o modo ativo ("tv", "linux" ou "games")
   */
  function renderModeUI() {
    const mode = clientState.mode;
    btnModeTv.classList.toggle("active", mode === "tv");
    btnModeLinux.classList.toggle("active", mode === "linux");
    if (btnModeGames) {
      btnModeGames.classList.toggle("active", mode === "games");
    }

    viewTv.classList.remove("active");
    viewLinux.classList.remove("active");
    if (viewGames) {
      viewGames.classList.remove("active");
    }

    const tpContainer = document.getElementById("linuxTrackpadContainer");
    const sshContainer = document.getElementById("linuxSshContainer");

    if (mode === "games" && viewGames) {
      viewGames.classList.add("active");
    } else if (mode === "linux") {
      viewLinux.classList.add("active");
      if (linuxSubTabs) linuxSubTabs.classList.remove("hidden");
      if (tvCursorSubTabs) tvCursorSubTabs.classList.add("hidden");
      if (tpContainer) tpContainer.classList.toggle("active", clientState.linuxSubTab === "trackpad");
      if (sshContainer) sshContainer.classList.toggle("active", clientState.linuxSubTab === "ssh");
      trackpadBadgeIcon.textContent = "🐧";
      trackpadBadgeTitle.textContent = "X11 Multitouch Trackpad (Linux Desktop)";
    } else if (clientState.tvSubTab === "cursor") {
      viewLinux.classList.add("active");
      if (linuxSubTabs) linuxSubTabs.classList.add("hidden");
      if (tvCursorSubTabs) tvCursorSubTabs.classList.remove("hidden");
      if (tpContainer) tpContainer.classList.add("active");
      if (sshContainer) sshContainer.classList.remove("active");
      trackpadBadgeIcon.textContent = "📺";
      trackpadBadgeTitle.textContent = "Android TV Virtual Cursor";
    } else {
      viewTv.classList.add("active");
    }
  }

  /**
   * Switch between TV, Linux Desktop, and Console Games
   */
  function switchSystemMode(targetMode) {
    vibrate(20);
    clientState.mode = targetMode;
    if (targetMode === "tv") {
      clientState.tvSubTab = "dpad";
      tabTvDpad.classList.add("active");
      tabTvCursor.classList.remove("active");
    }
    renderModeUI();
    if (!sendWs({ type: "mode", mode: targetMode })) {
      fetch("/api/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: targetMode }),
      }).catch(() => {});
    }
  }

  /**
   * Launch Android TV app, Linux app, or Emulator with HTTP fallback
   */
  function triggerAppLaunch(appId) {
    if (!appId) return;
    const gameConsoleLabels = {
      snes9x: "SNES (Super Nintendo)",
      neoemu: "MAME / NeoGeo Arcade",
      mame4droid: "MAME Arcade",
      mdemu: "Sega Mega Drive",
      lemuroid: "Multi-Console (Libretro)",
    };
    const linuxAppIds = ["browser", "xfce_terminal", "file_manager", "termux_x11"];
    if (gameConsoleLabels[appId]) {
      clientState.mode = "games";
      const lbl = document.getElementById("activeConsoleLabel");
      if (lbl) lbl.textContent = gameConsoleLabels[appId];
      if (typeof switchGamesSubTab === "function") {
        switchGamesSubTab("pad");
      }
      renderModeUI();
    } else if (linuxAppIds.includes(appId)) {
      clientState.mode = "linux";
      clientState.linuxSubTab = "trackpad";
      if (typeof switchLinuxSubTab === "function") {
        switchLinuxSubTab("trackpad");
      }
      renderModeUI();
    }
    if (!sendWs({ type: "launch", app_id: appId })) {
      fetch("/api/launch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ app_id: appId }),
      }).catch(() => {});
    }
  }

  // Unified Status & Battery Pill + Offline Recovery + Eco-Standby Switch Elements (v24)
  const batteryPill = document.getElementById("batteryPill");
  const offlineRecoveryBanner = document.getElementById("offlineRecoveryBanner");
  const offlineBannerTitle = document.getElementById("offlineBannerTitle");
  const offlineBannerDesc = document.getElementById("offlineBannerDesc");
  const btnDismissOfflineBanner = document.getElementById("btnDismissOfflineBanner");
  const btnReviveNow = document.getElementById("btnReviveNow");
  const btnToggleOfflineGuide = document.getElementById("btnToggleOfflineGuide");
  const offlineGuideSteps = document.getElementById("offlineGuideSteps");
  const btnStandbySwitch = document.getElementById("btnStandbySwitch");
  const btnQuickStandby = document.getElementById("btnQuickStandby");
  const standbyOverlay = document.getElementById("standbyOverlay");
  const btnStandbyWakeSwitch = document.getElementById("btnStandbyWakeSwitch");
  const standbySubtitle = document.getElementById("standbySubtitle");
  const standbyBatteryLabel = document.getElementById("standbyBatteryLabel");
  const standbyNetLabel = document.getElementById("standbyNetLabel");
  const standbyTimerPills = document.getElementById("standbyTimerPills");
  let offlineBannerDismissedUntil = 0;
  let wsReconnectTimer = null;

  function updateStandbyUI(standbyInfo, fallbackBool) {
    const isStandby =
      standbyInfo && typeof standbyInfo.standby_mode === "boolean"
        ? standbyInfo.standby_mode
        : typeof fallbackBool === "boolean"
        ? fallbackBool
        : Boolean(clientState.standbyMode);

    clientState.standbyMode = isStandby;
    if (standbyInfo) {
      if (standbyInfo.auto_standby_minutes != null) {
        clientState.autoStandbyMinutes = Number(standbyInfo.auto_standby_minutes);
      }
      if (typeof standbyInfo.standby_reason === "string") {
        clientState.standbyReason = standbyInfo.standby_reason;
      }
    }

    if (btnStandbySwitch) {
      btnStandbySwitch.classList.toggle("sleeping", isStandby);
      btnStandbySwitch.classList.toggle("awake", !isStandby);
      btnStandbySwitch.setAttribute("aria-pressed", isStandby ? "false" : "true");
      btnStandbySwitch.title = isStandby
        ? "🌙 Eco-Standby Active (Tap Power Switch to Wake Up & Return to Main Screen)"
        : "⚡ System ON (Tap Power Switch to Enter Eco-Standby / Battery Saver)";
    }

    if (btnQuickStandby) {
      btnQuickStandby.classList.toggle("sleeping", isStandby);
      btnQuickStandby.textContent = isStandby ? "🌙 Wake Up" : "⏻ Eco-Standby";
    }

    if (standbyOverlay) {
      standbyOverlay.classList.toggle("hidden", !isStandby);
    }

    if (standbySubtitle) {
      if (clientState.standbyReason === "idle_timeout") {
        standbySubtitle.textContent = `Entered Eco-Standby automatically after ${
          clientState.autoStandbyMinutes || 15
        } min of inactivity. Screen, GPU & X11 are sleeping to save battery while Wi-Fi stays 100% ready.`;
      } else {
        standbySubtitle.textContent =
          "Screen, GPU & X11 are sleeping to save battery while not in use. Wi-Fi Low-Latency remains 100% online.";
      }
    }

    if (standbyTimerPills) {
      standbyTimerPills.querySelectorAll("[data-standby-mins]").forEach((btn) => {
        const mins = Number(btn.getAttribute("data-standby-mins"));
        btn.classList.toggle("active", mins === clientState.autoStandbyMinutes);
      });
    }
  }

  async function setStandbyMode(targetStandby, reason = "manual") {
    vibrate(22);
    const desired = typeof targetStandby === "boolean" ? targetStandby : !clientState.standbyMode;

    if (!desired) {
      // Waking from Eco-Standby -> immediately navigate to the Main Screen (TV Box mode)
      if (btnStandbyWakeSwitch) {
        btnStandbyWakeSwitch.classList.add("waking");
        setTimeout(() => btnStandbyWakeSwitch.classList.remove("waking"), 450);
      }
      clientState.urlModeLocked = false;
      if (clientState.fullscreenLandscape && typeof setGamepadFullscreenLandscape === "function") {
        setGamepadFullscreenLandscape(false);
      }
      ["appsModal", "projectorModal", "moreControllersModal", "hudGameDrawer"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.classList.add("hidden");
      });
      clientState.mode = "tv";
      clientState.tvSubTab = "dpad";
      if (tabTvDpad) tabTvDpad.classList.add("active");
      if (tabTvCursor) tabTvCursor.classList.remove("active");
      renderModeUI();
    }

    updateStandbyUI(
      {
        standby_mode: desired,
        standby_reason: reason,
        auto_standby_minutes: clientState.autoStandbyMinutes,
      },
      desired
    );

    sendWs({ type: "standby", standby: desired, reason });
    try {
      const res = await fetch("/api/system/standby", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ standby: desired, reason }),
      });
      const data = await res.json();
      if (data && data.standby) {
        updateStandbyUI(data.standby, data.standby_mode);
      }
      if (!desired && data && data.mode) {
        clientState.mode = "tv";
        renderModeUI();
      }
    } catch (_) {}
  }

  async function setAutoStandbyMinutes(minutes) {
    vibrate(14);
    const mins = Math.max(0, Number(minutes) || 0);
    clientState.autoStandbyMinutes = mins;
    updateStandbyUI(
      {
        standby_mode: clientState.standbyMode,
        standby_reason: clientState.standbyReason,
        auto_standby_minutes: mins,
      },
      clientState.standbyMode
    );
    sendWs({ type: "standby", auto_standby_minutes: mins });
    try {
      await fetch("/api/system/standby", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ auto_standby_minutes: mins }),
      });
    } catch (_) {}
  }

  if (btnStandbySwitch) {
    btnStandbySwitch.addEventListener("click", () => {
      setStandbyMode(!clientState.standbyMode, "manual_topbar_switch");
    });
  }

  if (btnQuickStandby) {
    btnQuickStandby.addEventListener("click", () => {
      setStandbyMode(!clientState.standbyMode, "manual_quick_chip");
    });
  }

  if (btnStandbyWakeSwitch) {
    btnStandbyWakeSwitch.addEventListener("click", () => {
      setStandbyMode(false, "manual_wake_switch");
    });
  }

  if (standbyTimerPills) {
    standbyTimerPills.querySelectorAll("[data-standby-mins]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const mins = Number(btn.getAttribute("data-standby-mins"));
        setAutoStandbyMinutes(mins);
      });
    });
  }

  function updateBatteryAndHealthUI(battery, wsConnected = clientState.connected, forceOfflineNow = false) {
    const phoneOnline = Boolean(wsConnected && (!battery || battery.phone_online !== false));
    if (battery) {
      clientState.battery = battery;
      if (battery.standby || typeof battery.standby_mode === "boolean") {
        updateStandbyUI(battery.standby, battery.standby_mode);
      }
    }

    if (!phoneOnline) {
      if (!forceOfflineNow && clientState.consecutiveOfflineFailures < 3) {
        // Keep last known good status while fast reconnect / HTTP verification runs
        return;
      }
      if (statusDot) statusDot.className = "status-dot offline";
      if (statusText) statusText.textContent = "Offline";
      if (standbyNetLabel) standbyNetLabel.textContent = "🔌 Reconnecting...";
      if (batteryPill) {
        batteryPill.className = "status-battery-pill offline";
        batteryPill.title = "Xiaomi Redmi Note 8 Pro is offline or out of battery (Tap for recovery guide)";
      }
      if (offlineRecoveryBanner && Date.now() > offlineBannerDismissedUntil) {
        offlineRecoveryBanner.classList.remove("hidden", "low-battery-mode");
        if (offlineBannerTitle) {
          offlineBannerTitle.textContent = "🔌 Xiaomi Offline — Likely Powered Off (Out of Battery)";
        }
        if (offlineBannerDesc) {
          offlineBannerDesc.textContent =
            (battery && battery.offline_reason) ||
            "The Xiaomi Redmi Note 8 Pro is not responding on Wi-Fi or USB. Plug it into the USB cable and hold the Power button for 5–10s!";
        }
      }
      return;
    }

    clientState.consecutiveOfflineFailures = 0;
    if (statusDot) statusDot.className = "status-dot online";
    if (standbyNetLabel) standbyNetLabel.textContent = "🟢 Wi-Fi Low-Latency Ready";

    if (battery) {
      const lvl = battery.level;
      const isChg = Boolean(battery.charging);
      const isCrit = Boolean(battery.critical_battery);
      const isLow = Boolean(battery.low_battery);
      const tempStr = battery.temperature_c != null ? ` • ${battery.temperature_c}°C` : "";
      const srcLabel = isChg ? "Charging on Cable" : "On Battery (Unplugged)";
      const basePillText =
        battery.status_text || (lvl != null ? `${isChg ? "⚡" : isLow ? "🪫" : "🔋"} ${lvl}%` : "⚡ Online");
      const pillText = clientState.standbyMode ? `🌙 ${lvl != null ? lvl + "%" : "Eco"}` : basePillText;

      if (statusText) statusText.textContent = pillText;
      if (standbyBatteryLabel) {
        standbyBatteryLabel.textContent = `${basePillText} (${isChg ? "Charging" : "Eco-Saving"})`;
      }
      if (batteryPill) {
        batteryPill.className =
          "status-battery-pill" + (isChg ? " charging" : isCrit ? " critical" : isLow ? " low" : "");
        batteryPill.title = `Xiaomi Battery: ${lvl != null ? lvl + "%" : "OK"} (${srcLabel}${tempStr})`;
      }

      if (offlineRecoveryBanner) {
        if ((isLow || isCrit) && Date.now() > offlineBannerDismissedUntil) {
          offlineRecoveryBanner.classList.remove("hidden");
          offlineRecoveryBanner.classList.add("low-battery-mode");
          if (offlineBannerTitle) {
            offlineBannerTitle.textContent = `🪫 Xiaomi Battery at ${lvl}% (Unplugged!)`;
          }
          if (offlineBannerDesc) {
            offlineBannerDesc.textContent =
              "Plug the USB cable into the Xiaomi Redmi Note 8 Pro so the battery doesn't reach 0% and power off.";
          }
        } else {
          offlineRecoveryBanner.classList.add("hidden");
        }
      }
    } else {
      if (statusText && (!statusText.textContent || statusText.textContent === "Connecting" || statusText.textContent === "Offline")) {
        statusText.textContent = "Online";
      }
      if (batteryPill) {
        batteryPill.className = "status-battery-pill";
      }
      if (offlineRecoveryBanner) {
        offlineRecoveryBanner.classList.add("hidden");
      }
    }
  }

  if (batteryPill) {
    batteryPill.addEventListener("click", () => {
      vibrate(12);
      offlineBannerDismissedUntil = 0;
      if (offlineRecoveryBanner) {
        offlineRecoveryBanner.classList.toggle("hidden");
        if (!offlineRecoveryBanner.classList.contains("hidden")) {
          const bat = clientState.battery;
          if (bat && bat.phone_online) {
            const lvl = bat.level != null ? `${bat.level}%` : "OK";
            const src = bat.charging ? "Charging on Cable" : "On Battery";
            const temp = bat.temperature_c != null ? ` • ${bat.temperature_c}°C` : "";
            if (offlineBannerTitle) {
              offlineBannerTitle.textContent = `${bat.charging ? "⚡" : "🔋"} Xiaomi Online — Battery at ${lvl} (${src}${temp})`;
            }
            if (offlineBannerDesc) {
              offlineBannerDesc.textContent =
                "Everything is connected and ready! Below is the quick recovery guide in case the battery ever reaches 0%:";
            }
          }
          if (offlineGuideSteps) {
            offlineGuideSteps.classList.remove("hidden");
          }
        }
      }
    });
  }

  if (btnDismissOfflineBanner && offlineRecoveryBanner) {
    btnDismissOfflineBanner.addEventListener("click", () => {
      vibrate(10);
      offlineBannerDismissedUntil = Date.now() + 60000;
      offlineRecoveryBanner.classList.add("hidden");
    });
  }

  if (btnToggleOfflineGuide && offlineGuideSteps) {
    btnToggleOfflineGuide.addEventListener("click", () => {
      vibrate(12);
      offlineGuideSteps.classList.toggle("hidden");
    });
  }

  if (btnReviveNow) {
    btnReviveNow.addEventListener("click", async () => {
      vibrate(18);
      const origText = btnReviveNow.textContent;
      btnReviveNow.disabled = true;
      btnReviveNow.textContent = "⏳ Searching for Xiaomi on USB / Wi-Fi...";
      try {
        const res = await fetch("/api/system/revive", { method: "POST" });
        const data = await res.json();
        if (data.battery) {
          clientState.consecutiveOfflineFailures = 0;
          updateBatteryAndHealthUI(data.battery, true);
        }
        if (offlineBannerDesc && data.message) {
          offlineBannerDesc.textContent = data.message;
        }
        if (data.phone_online) {
          connectWebSocket();
        }
      } catch (_) {
        if (offlineBannerDesc) {
          offlineBannerDesc.textContent =
            "Still no response. Make sure the Xiaomi is plugged into USB and hold the Power button for 5–10 seconds until it vibrates!";
        }
        connectWebSocket();
      } finally {
        btnReviveNow.disabled = false;
        btnReviveNow.textContent = origText;
      }
    });
  }

  async function probeBackendHealth() {
    if (document.visibilityState === "hidden") {
      return;
    }
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), 2800) : null;
    try {
      const res = await fetch("/api/battery", {
        cache: "no-store",
        signal: ctrl ? ctrl.signal : undefined,
      });
      if (timer) clearTimeout(timer);
      if (!res.ok) throw new Error("status not ok");
      const d = await res.json();
      if (d && d.standby) {
        updateStandbyUI(d.standby, d.standby_mode);
      }
      if (d && d.battery && d.battery.phone_online !== false) {
        clientState.consecutiveOfflineFailures = 0;
        updateBatteryAndHealthUI(d.battery, true);
        if (!clientState.ws || clientState.ws.readyState !== WebSocket.OPEN) {
          connectWebSocket();
        }
        return;
      }
      clientState.consecutiveOfflineFailures += 1;
      updateBatteryAndHealthUI(d ? d.battery : null, false);
    } catch (_) {
      if (timer) clearTimeout(timer);
      clientState.consecutiveOfflineFailures += 1;
      updateBatteryAndHealthUI(null, false);
    }
  }

  // Periodic Xiaomi battery & health heartbeat every 8s
  setInterval(() => {
    if (!sendWs({ type: "ping", ts: Date.now() })) {
      probeBackendHealth();
    }
  }, 8000);

  // Instant Reconnect when unlocking the controller phone or returning to the PWA tab
  function handleAppForegroundResume() {
    if (document.visibilityState === "hidden") return;
    clientState.consecutiveOfflineFailures = 0;
    if (!clientState.ws || clientState.ws.readyState !== WebSocket.OPEN) {
      connectWebSocket();
    }
    probeBackendHealth();
  }

  document.addEventListener("visibilitychange", handleAppForegroundResume);
  window.addEventListener("pageshow", handleAppForegroundResume);
  window.addEventListener("online", handleAppForegroundResume);

  /**
   * Connect to WebSocket with automatic zero-flicker reconnect
   */
  function connectWebSocket() {
    if (wsReconnectTimer) {
      clearTimeout(wsReconnectTimer);
      wsReconnectTimer = null;
    }
    if (
      clientState.ws &&
      (clientState.ws.readyState === WebSocket.OPEN ||
        clientState.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);
    clientState.ws = ws;

    ws.addEventListener("open", () => {
      if (ws !== clientState.ws) return;
      clientState.connected = true;
      clientState.consecutiveOfflineFailures = 0;
      if (statusDot) statusDot.className = "status-dot online";
      if (!clientState.battery && statusText) {
        statusText.textContent = "Online";
      }
    });

    ws.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "state" || data.type === "pong") {
          clientState.consecutiveOfflineFailures = 0;
          if (data.standby || typeof data.standby_mode === "boolean") {
            updateStandbyUI(data.standby, data.standby_mode);
          }
          if (data.battery) {
            updateBatteryAndHealthUI(data.battery, true);
          }
          if (data.type === "state" && data.mode) {
            if (!clientState.fullscreenLandscape && !clientState.urlModeLocked) {
              clientState.mode = data.mode;
              renderModeUI();
            }
          }
        }
      } catch (_) {
        // Ignora pacotes malformados
      }
    });

    ws.addEventListener("close", () => {
      if (ws !== clientState.ws) return;
      clientState.ws = null;
      clientState.connected = false;
      // Do NOT immediately flash the red Offline banner when a phone unlocks;
      // verify via HTTP and reconnect immediately.
      probeBackendHealth();
      wsReconnectTimer = setTimeout(connectWebSocket, 900);
    });

    ws.addEventListener("error", () => {
      try {
        ws.close();
      } catch (_) {}
    });
  }

  /**
   * Carrega status inicial e catálogo de apps para a Gaveta de Apps
   */
  async function loadInitialStatus() {
    try {
      const res = await fetch("/api/status", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      clientState.consecutiveOfflineFailures = 0;
      if (data.standby || typeof data.standby_mode === "boolean") {
        updateStandbyUI(data.standby, data.standby_mode);
      }
      if (data.battery) {
        updateBatteryAndHealthUI(data.battery, true);
      }
      if (data.mode && !clientState.fullscreenLandscape && !clientState.urlModeLocked) {
        clientState.mode = data.mode;
        renderModeUI();
      }
      if (Array.isArray(data.apps)) {
        clientState.apps = data.apps;
        renderAppsGrid();
      }
    } catch (_) {
      probeBackendHealth();
    }
  }

  function renderAppsGrid() {
    appsGrid.innerHTML = "";
    clientState.apps.forEach((app) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "app-card";
      const tagLabel =
        app.target === "linux"
          ? "Linux X11"
          : app.category === "games"
          ? "Console Games"
          : "Android TV";
      btn.innerHTML = `
        <span class="app-card-icon">${app.icon}</span>
        <span class="app-card-info">
          <span class="app-card-name">${app.name}</span>
          <span class="app-card-tag">${tagLabel}</span>
        </span>
      `;
      btn.addEventListener("click", () => {
        vibrate(18);
        appsModal.classList.add("hidden");
        if (app.id === "projector") {
          openProjectorModal(true, "projector");
          return;
        }
        if (app.id === "wifi_portable") {
          openProjectorModal(false, "wifi");
          return;
        }
        if (app.id === "bt_controllers") {
          switchSystemMode("games");
          switchGamesSubTab("bluetooth");
          scanBluetoothControllers(false);
          return;
        }
        if (app.id === "ssh_terminal") {
          switchSystemMode("linux");
          switchLinuxSubTab("ssh");
          return;
        }
        triggerAppLaunch(app.id);
      });
      appsGrid.appendChild(btn);
    });
  }

  // ==================== EVENTOS DE BOTÕES DE TOPO E SUB-ABAS ====================
  btnModeTv.addEventListener("click", () => switchSystemMode("tv"));
  btnModeLinux.addEventListener("click", () => switchSystemMode("linux"));
  if (btnModeGames) {
    btnModeGames.addEventListener("click", () => switchSystemMode("games"));
  }

  function selectTvDpadTab() {
    vibrate(10);
    clientState.tvSubTab = "dpad";
    tabTvDpad.classList.add("active");
    tabTvCursor.classList.remove("active");
    renderModeUI();
  }

  tabTvDpad.addEventListener("click", selectTvDpadTab);
  if (tabTvCursorBackDpad) {
    tabTvCursorBackDpad.addEventListener("click", selectTvDpadTab);
  }

  tabTvCursor.addEventListener("click", () => {
    vibrate(10);
    clientState.tvSubTab = "cursor";
    tabTvCursor.classList.add("active");
    tabTvDpad.classList.remove("active");
    renderModeUI();
  });

  // Atalhos rápidos na faixa superior
  document.querySelectorAll("[data-launch]").forEach((btn) => {
    btn.addEventListener("click", () => {
      vibrate(15);
      const appId = btn.getAttribute("data-launch");
      triggerAppLaunch(appId);
    });
  });

  // ==================== CONTROLE D-PAD COM REPETIÇÃO AO SEGURAR ====================
  let holdTimer = null;
  let repeatInterval = null;

  function stopDpadRepeat() {
    if (holdTimer) {
      clearTimeout(holdTimer);
      holdTimer = null;
    }
    if (repeatInterval) {
      clearInterval(repeatInterval);
      repeatInterval = null;
    }
  }

  function sendDpadCommand(key) {
    if (!sendWs({ type: "dpad", key })) {
      connectWebSocket();
      fetch("/api/dpad", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, target: clientState.mode }),
      }).catch(() => {});
    }
  }

  document.querySelectorAll("[data-dpad]").forEach((btn) => {
    const key = btn.getAttribute("data-dpad");
    const repeatable = ["UP", "DOWN", "LEFT", "RIGHT", "VOL_UP", "VOL_DOWN"].includes(key);

    btn.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      vibrate(12);
      sendDpadCommand(key);
      stopDpadRepeat();
      if (repeatable) {
        holdTimer = setTimeout(() => {
          repeatInterval = setInterval(() => {
            sendDpadCommand(key);
          }, 110);
        }, 360);
      }
    });

    btn.addEventListener("pointerup", stopDpadRepeat);
    btn.addEventListener("pointercancel", stopDpadRepeat);
    btn.addEventListener("pointerleave", stopDpadRepeat);
  });

  // ==================== TRACKPAD MULTITOQUE COM FILTRO ANTI-TREMOR E ANTI-CLIQUE FANTASMA ====================
  const TRACKPAD_DEADZONE_PX = 1.25;
  const TRACKPAD_MOVE_UNLOCK_PX = 3.2;
  const TRACKPAD_TAP_MAX_MOVE_PX = 4.2;

  const touchState = {
    activeCount: 0,
    maxFingers: 0,
    startTime: 0,
    startX: 0,
    startY: 0,
    lastX: 0,
    lastY: 0,
    smoothDx: 0,
    smoothDy: 0,
    lastMoveTs: 0,
    totalMoved: 0,
    didSendMove: false,
    multiTouchCooldown: false,
    lastClickSentTs: 0,
    lastTouchEventTs: 0,
    accumDx: 0,
    accumDy: 0,
    rafPending: false,
  };

  function flushPointerMove() {
    touchState.rafPending = false;
    const dx = touchState.accumDx;
    const dy = touchState.accumDy;
    touchState.accumDx = 0;
    touchState.accumDy = 0;
    if (Math.abs(dx) >= 0.45 || Math.abs(dy) >= 0.45) {
      touchState.didSendMove = true;
      sendWs({
        type: "move",
        dx: Number(dx.toFixed(2)),
        dy: Number(dy.toFixed(2)),
      });
    }
  }

  function showRipple(clientX, clientY) {
    const rect = trackpadSurface.getBoundingClientRect();
    touchRipple.style.left = `${clientX - rect.left}px`;
    touchRipple.style.top = `${clientY - rect.top}px`;
    touchRipple.classList.remove("hidden");
  }

  function hideRipple() {
    touchRipple.classList.add("hidden");
  }

  trackpadSurface.addEventListener(
    "touchstart",
    (e) => {
      e.preventDefault();
      const touches = e.touches;
      const now = performance.now();
      touchState.lastTouchEventTs = now;
      touchState.activeCount = touches.length;
      touchState.maxFingers = Math.max(touchState.maxFingers, touches.length);

      if (touches.length === 1 && !touchState.multiTouchCooldown) {
        touchState.startTime = now;
        touchState.startX = touches[0].clientX;
        touchState.startY = touches[0].clientY;
        touchState.lastX = touches[0].clientX;
        touchState.lastY = touches[0].clientY;
        touchState.smoothDx = 0;
        touchState.smoothDy = 0;
        touchState.lastMoveTs = now;
        touchState.totalMoved = 0;
        touchState.didSendMove = false;
        showRipple(touches[0].clientX, touches[0].clientY);
      } else if (touches.length >= 2) {
        touchState.multiTouchCooldown = true;
        touchState.lastX = (touches[0].clientX + touches[1].clientX) * 0.5;
        touchState.lastY = (touches[0].clientY + touches[1].clientY) * 0.5;
        touchState.lastMoveTs = now;
      }
    },
    { passive: false }
  );

  trackpadSurface.addEventListener(
    "touchmove",
    (e) => {
      e.preventDefault();
      const touches = e.touches;
      const now = performance.now();
      touchState.lastTouchEventTs = now;
      const dt = Math.max(6, now - touchState.lastMoveTs);

      if (touches.length === 1) {
        if (touchState.multiTouchCooldown) {
          touchState.lastX = touches[0].clientX;
          touchState.lastY = touches[0].clientY;
          touchState.lastMoveTs = now;
          return;
        }

        const cx = touches[0].clientX;
        const cy = touches[0].clientY;
        const rawDx = cx - touchState.lastX;
        const rawDy = cy - touchState.lastY;
        const stepDist = Math.hypot(rawDx, rawDy);

        // Ignora micro-oscilações capacitivas do dedo parado (evita que o cursor fique tremendo)
        if (stepDist < TRACKPAD_DEADZONE_PX) {
          return;
        }

        touchState.lastX = cx;
        touchState.lastY = cy;
        touchState.lastMoveTs = now;
        touchState.totalMoved += stepDist;
        showRipple(cx, cy);

        const netFromStart = Math.hypot(cx - touchState.startX, cy - touchState.startY);
        if (touchState.totalMoved >= TRACKPAD_TAP_MAX_MOVE_PX) {
          touchState.didSendMove = true;
        }
        if (netFromStart < TRACKPAD_MOVE_UNLOCK_PX) {
          return;
        }

        // Filtro passa-baixa EMA + curva de aceleração suave proporcional à velocidade do dedo
        touchState.smoothDx = touchState.smoothDx * 0.35 + rawDx * 0.65;
        touchState.smoothDy = touchState.smoothDy * 0.35 + rawDy * 0.65;

        const velocity = stepDist / dt;
        const accel = clientState.sensitivity * (1 + Math.min(1.8, velocity * 0.75));

        touchState.accumDx += touchState.smoothDx * accel;
        touchState.accumDy += touchState.smoothDy * accel;

        if (!touchState.rafPending) {
          touchState.rafPending = true;
          requestAnimationFrame(flushPointerMove);
        }
      } else if (touches.length >= 2) {
        const cx = (touches[0].clientX + touches[1].clientX) * 0.5;
        const cy = (touches[0].clientY + touches[1].clientY) * 0.5;
        const rawDx = cx - touchState.lastX;
        const rawDy = cy - touchState.lastY;
        const dist = Math.hypot(rawDx, rawDy);

        if (dist < 1.8) {
          return;
        }

        touchState.lastX = cx;
        touchState.lastY = cy;
        touchState.lastMoveTs = now;
        touchState.totalMoved += dist;
        touchState.didSendMove = true;

        if (Math.abs(rawDx) > 2.0 || Math.abs(rawDy) > 2.0) {
          sendWs({
            type: "scroll",
            dx: Number((rawDx * clientState.scrollSensitivity * 10).toFixed(1)),
            dy: Number((-rawDy * clientState.scrollSensitivity * 10).toFixed(1)),
          });
        }
      }
    },
    { passive: false }
  );

  function handleTrackpadTouchEnd(e, isCancel = false) {
    e.preventDefault();
    const now = performance.now();
    touchState.lastTouchEventTs = now;
    const elapsed = now - touchState.startTime;

    if (e.touches.length === 1) {
      // Quando solta 1 dos 2 dedos após scroll, realinha coordenadas para não dar salto no cursor
      touchState.lastX = e.touches[0].clientX;
      touchState.lastY = e.touches[0].clientY;
      touchState.multiTouchCooldown = true;
      return;
    }

    if (e.touches.length === 0) {
      hideRipple();
      if (
        !isCancel &&
        !touchState.didSendMove &&
        touchState.totalMoved < TRACKPAD_TAP_MAX_MOVE_PX &&
        elapsed >= 22 &&
        elapsed < 220 &&
        now - touchState.lastClickSentTs >= 130
      ) {
        if (touchState.maxFingers === 1) {
          vibrate(10);
          sendWs({ type: "click", button: 1, count: 1 });
          touchState.lastClickSentTs = now;
        } else if (touchState.maxFingers === 2) {
          vibrate(16);
          sendWs({ type: "click", button: 3, count: 1 });
          touchState.lastClickSentTs = now;
        }
      }
      touchState.activeCount = 0;
      touchState.maxFingers = 0;
      touchState.totalMoved = 0;
      touchState.didSendMove = false;
      touchState.multiTouchCooldown = false;
      touchState.accumDx = 0;
      touchState.accumDy = 0;
    }
  }

  trackpadSurface.addEventListener("touchend", (e) => handleTrackpadTouchEnd(e, false), {
    passive: false,
  });
  trackpadSurface.addEventListener("touchcancel", (e) => handleTrackpadTouchEnd(e, true), {
    passive: false,
  });

  // Suporte também a mouse no navegador desktop para testes locais (ignorado se veio de tela touch)
  let desktopMouseDown = false;
  trackpadSurface.addEventListener("mousedown", (e) => {
    if (performance.now() - touchState.lastTouchEventTs < 1000) return;
    desktopMouseDown = true;
    touchState.lastX = e.clientX;
    touchState.lastY = e.clientY;
  });
  window.addEventListener("mousemove", (e) => {
    if (!desktopMouseDown) return;
    if (performance.now() - touchState.lastTouchEventTs < 1000) return;
    const dx = (e.clientX - touchState.lastX) * clientState.sensitivity;
    const dy = (e.clientY - touchState.lastY) * clientState.sensitivity;
    if (Math.hypot(dx, dy) < 0.8) return;
    touchState.lastX = e.clientX;
    touchState.lastY = e.clientY;
    sendWs({ type: "move", dx, dy });
  });
  window.addEventListener("mouseup", () => {
    desktopMouseDown = false;
  });

  // Botões Físicos Inferiores (Clique Esquerdo / Direito / Scroll Strip)
  let leftMouseHeld = false;
  function releaseLeftMouseButton() {
    btnMouseLeft.classList.remove("pressed");
    if (!leftMouseHeld) return;
    leftMouseHeld = false;
    if (clientState.mode === "linux") {
      sendWs({ type: "mouseup", button: 1 });
    }
  }

  btnMouseLeft.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    vibrate(12);
    try {
      btnMouseLeft.setPointerCapture(e.pointerId);
    } catch (_) {}
    btnMouseLeft.classList.add("pressed");
    if (clientState.mode === "linux") {
      leftMouseHeld = true;
      sendWs({ type: "mousedown", button: 1 });
    } else {
      sendWs({ type: "click", button: 1 });
    }
  });

  btnMouseLeft.addEventListener("pointerup", (e) => {
    e.preventDefault();
    releaseLeftMouseButton();
  });
  btnMouseLeft.addEventListener("pointercancel", releaseLeftMouseButton);
  btnMouseLeft.addEventListener("pointerleave", releaseLeftMouseButton);
  btnMouseLeft.addEventListener("lostpointercapture", releaseLeftMouseButton);

  btnMouseRight.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    vibrate(15);
    btnMouseRight.classList.add("pressed");
    sendWs({ type: "click", button: 3 });
  });

  btnMouseRight.addEventListener("pointerup", () => {
    btnMouseRight.classList.remove("pressed");
  });
  btnMouseRight.addEventListener("pointercancel", () => {
    btnMouseRight.classList.remove("pressed");
  });
  btnMouseRight.addEventListener("pointerleave", () => {
    btnMouseRight.classList.remove("pressed");
  });

  let scrollStripLastY = 0;
  scrollStrip.addEventListener(
    "touchstart",
    (e) => {
      e.preventDefault();
      scrollStripLastY = e.touches[0].clientY;
    },
    { passive: false }
  );
  scrollStrip.addEventListener(
    "touchmove",
    (e) => {
      e.preventDefault();
      const cy = e.touches[0].clientY;
      const dy = cy - scrollStripLastY;
      if (Math.abs(dy) >= 6) {
        scrollStripLastY = cy;
        vibrate(6);
        sendWs({ type: "scroll", dx: 0, dy: dy * 2 });
      }
    },
    { passive: false }
  );

  // Macros de Teclado Linux / Cursor Android TV
  document.querySelectorAll("[data-linux-key]").forEach((btn) => {
    btn.addEventListener("click", () => {
      vibrate(12);
      const key = btn.getAttribute("data-linux-key");
      const target = clientState.mode === "linux" ? "linux" : "tv";
      sendWs({ type: "key", key, target });
    });
  });

  // ==================== TECLADO VIRTUAL ====================
  btnKeyboardToggle.addEventListener("click", () => {
    vibrate(10);
    keyboardBar.classList.toggle("hidden");
    if (!keyboardBar.classList.contains("hidden")) {
      virtualKeyboardInput.focus();
    }
  });

  function flushKeyboardText() {
    const text = virtualKeyboardInput.value;
    if (text) {
      vibrate(12);
      sendWs({ type: "text", text });
      virtualKeyboardInput.value = "";
    }
  }

  btnSendText.addEventListener("click", flushKeyboardText);

  virtualKeyboardInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (virtualKeyboardInput.value) {
        flushKeyboardText();
      }
      sendWs({ type: "key", key: "Return" });
    } else if (e.key === "Backspace" && !virtualKeyboardInput.value) {
      sendWs({ type: "key", key: "BackSpace" });
    }
  });

  document.querySelectorAll("[data-key]").forEach((btn) => {
    btn.addEventListener("click", () => {
      vibrate(10);
      sendWs({ type: "key", key: btn.getAttribute("data-key") });
    });
  });

  // ==================== GAVETA DE APPS ====================
  btnAppsDrawer.addEventListener("click", () => {
    vibrate(12);
    appsModal.classList.remove("hidden");
  });

  btnCloseModal.addEventListener("click", () => {
    appsModal.classList.add("hidden");
  });

  appsModal.addEventListener("click", (e) => {
    if (e.target === appsModal) {
      appsModal.classList.add("hidden");
    }
  });

  // ==================== PROJETOR & SMART TV UNIVERSAL + WI-FI PORTÁTIL & HOTSPOT DE RESGATE ====================
  const btnProjectorOpen = document.getElementById("btnProjectorOpen");
  const btnQuickProjector = document.getElementById("btnQuickProjector");
  const btnQuickWifi = document.getElementById("btnQuickWifi");
  const projectorModal = document.getElementById("projectorModal");
  const btnCloseProjectorModal = document.getElementById("btnCloseProjectorModal");

  const tabModalProjector = document.getElementById("tabModalProjector");
  const tabModalWifi = document.getElementById("tabModalWifi");
  const modalTabProjectorContent = document.getElementById("modalTabProjectorContent");
  const modalTabWifiContent = document.getElementById("modalTabWifiContent");

  const projectorStatusBanner = document.getElementById("projectorStatusBanner");
  const btnScanProjector = document.getElementById("btnScanProjector");
  const btnDisconnectProjector = document.getElementById("btnDisconnectProjector");
  const btnUseHdmiCable = document.getElementById("btnUseHdmiCable");
  const btnWakePhoneScreen = document.getElementById("btnWakePhoneScreen");
  const btnLocateProjectorIp = document.getElementById("btnLocateProjectorIp");
  const btnMiuiCast = document.getElementById("btnMiuiCast");
  const btnWindowsCast = document.getElementById("btnWindowsCast");
  const projectorDevicesList = document.getElementById("projectorDevicesList");

  // Elementos da Aba 2: Wi-Fi Portátil & Viagem
  const wifiStatusBanner = document.getElementById("wifiStatusBanner");
  const wifiCurrentSsidText = document.getElementById("wifiCurrentSsidText");
  const wifiCurrentSignalBadge = document.getElementById("wifiCurrentSignalBadge");
  const wifiCurrentIpCode = document.getElementById("wifiCurrentIpCode");
  const wifiCurrentGwCode = document.getElementById("wifiCurrentGwCode");
  const wifiMdnsUrlDisplay = document.getElementById("wifiMdnsUrlDisplay");
  const btnCopyMdnsUrl = document.getElementById("btnCopyMdnsUrl");
  const btnScanWifiNetworks = document.getElementById("btnScanWifiNetworks");
  const wifiTargetSsidInput = document.getElementById("wifiTargetSsidInput");
  const wifiTargetSecSelect = document.getElementById("wifiTargetSecSelect");
  const wifiPasswordRow = document.getElementById("wifiPasswordRow");
  const wifiTargetPassInput = document.getElementById("wifiTargetPassInput");
  const btnToggleWifiPass = document.getElementById("btnToggleWifiPass");
  const btnConnectWifiSubmit = document.getElementById("btnConnectWifiSubmit");
  const btnPreSaveWifiSubmit = document.getElementById("btnPreSaveWifiSubmit");
  const wifiNetworksList = document.getElementById("wifiNetworksList");
  const rescueHotspotSsidInput = document.getElementById("rescueHotspotSsidInput");
  const rescueHotspotPassInput = document.getElementById("rescueHotspotPassInput");
  const btnSaveRescueHotspot = document.getElementById("btnSaveRescueHotspot");
  const btnTestRescueHotspot = document.getElementById("btnTestRescueHotspot");

  function switchProjectorModalTab(tabName) {
    vibrate(12);
    const isWifi = tabName === "wifi";
    if (tabModalProjector) tabModalProjector.classList.toggle("active", !isWifi);
    if (tabModalWifi) tabModalWifi.classList.toggle("active", isWifi);
    if (modalTabProjectorContent) {
      modalTabProjectorContent.classList.toggle("active", !isWifi);
      modalTabProjectorContent.classList.toggle("hidden", isWifi);
    }
    if (modalTabWifiContent) {
      modalTabWifiContent.classList.toggle("active", isWifi);
      modalTabWifiContent.classList.toggle("hidden", !isWifi);
    }
    if (isWifi) {
      loadWifiPortableStatus(true);
    }
  }

  if (tabModalProjector) {
    tabModalProjector.addEventListener("click", () => switchProjectorModalTab("projector"));
  }
  if (tabModalWifi) {
    tabModalWifi.addEventListener("click", () => switchProjectorModalTab("wifi"));
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function buildSignalBarsHtml(pct) {
    const p = Number(pct) || 0;
    const b1 = p >= 10 ? "active" : "";
    const b2 = p >= 38 ? "active" : "";
    const b3 = p >= 65 ? "active" : "";
    const b4 = p >= 85 ? "active" : "";
    const levelClass = p >= 65 ? "good" : p >= 38 ? "mid" : "weak";
    return `<span class="wifi-signal-bars ${levelClass}" title="Signal ${p}%"><i class="wifi-bar b1 ${b1}"></i><i class="wifi-bar b2 ${b2}"></i><i class="wifi-bar b3 ${b3}"></i><i class="wifi-bar b4 ${b4}"></i></span>`;
  }

  async function disconnectProjector() {
    vibrate(18);
    if (btnDisconnectProjector) {
      btnDisconnectProjector.disabled = true;
      btnDisconnectProjector.textContent = "⏳ Disconnecting TV / Projector...";
    }
    if (projectorStatusBanner) {
      projectorStatusBanner.innerHTML =
        "🔌 Disconnecting wireless projection and returning video to the phone / PC screen...";
    }
    try {
      const res = await fetch("/api/projector/disconnect", { method: "POST" });
      const data = await res.json();
      if (projectorStatusBanner) {
        projectorStatusBanner.innerHTML =
          data.message || "🔌 Disconnected from TV / Projector!";
      }
      if (Array.isArray(data.devices)) {
        renderProjectorDevices(data.devices);
      }
    } catch (_) {
      if (projectorStatusBanner) {
        projectorStatusBanner.textContent = "Error disconnecting from TV / Projector.";
      }
    } finally {
      if (btnDisconnectProjector) {
        btnDisconnectProjector.disabled = false;
        btnDisconnectProjector.textContent = "🔴 Disconnect TV / Projector";
      }
    }
  }

  function renderProjectorDevices(devices) {
    if (!projectorDevicesList) return;
    projectorDevicesList.innerHTML = "";
    if (!Array.isArray(devices) || devices.length === 0) {
      projectorDevicesList.innerHTML = `
        <div class="projector-empty">
          No Smart TV or projector detected yet.<br/>
          On your TV (Samsung, LG, Sony, TCL, Roku, Fire TV) or <strong>Projector</strong>, enable <strong>Screen Mirroring / Miracast / Cast</strong> and tap <strong>Scan Any TV or Projector</strong>.
        </div>
      `;
      return;
    }

    devices.forEach((dev) => {
      const card = document.createElement("div");
      card.className = "projector-device-card";
      const isConn = Boolean(dev.connected);
      const isFav = Boolean(dev.is_projector) || /projector/i.test(dev.name || "");
      const favBadge = isFav
        ? '<span style="color:#fbbf24;font-weight:700;font-size:0.72rem;margin-left:4px;">⭐ Favorite</span>'
        : "";
      const badgeHtml = isConn
        ? '<span style="color:#4ade80;font-weight:700;font-size:0.75rem;">🟢 CONNECTED</span>'
        : '<span style="color:#38bdf8;font-weight:600;font-size:0.75rem;">📡 READY TO CONNECT</span>';
      const safeName = escapeHtml(dev.name);
      const safeProto = escapeHtml(dev.protocol || "Miracast / Cast");
      const safeAddr = escapeHtml(dev.address || "");
      card.innerHTML = `
        <div class="projector-device-info">
          <span class="projector-device-name">📽️ ${safeName}${favBadge} ${badgeHtml}</span>
          <span class="projector-device-meta">${safeProto}${safeAddr ? " • " + safeAddr : ""}</span>
        </div>
        <div class="projector-card-actions">
          ${
            isConn
              ? '<button type="button" class="projector-connect-btn disconnect-btn">🔌 Disconnect</button>'
              : '<button type="button" class="projector-connect-btn">Connect</button>'
          }
        </div>
      `;
      const actionBtn = card.querySelector(".projector-connect-btn");
      actionBtn.addEventListener("click", async () => {
        if (isConn) {
          actionBtn.textContent = "Disconnecting...";
          await disconnectProjector();
          return;
        }
        vibrate(15);
        actionBtn.textContent = "Connecting...";
        try {
          const res = await fetch("/api/projector/connect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target: dev.name, target_name: dev.name, auto_connect: true }),
          });
          const data = await res.json();
          projectorStatusBanner.innerHTML = data.message || "Command sent!";
          fetch("/api/projector/status")
            .then((r) => r.json())
            .then((st) => {
              if (st.devices) renderProjectorDevices(st.devices);
            })
            .catch(() => {});
        } catch (_) {
          projectorStatusBanner.textContent = "Error connecting to TV/Projector.";
        } finally {
          actionBtn.textContent = "Connect";
        }
      });
      projectorDevicesList.appendChild(card);
    });
  }

  async function scanAndConnectProjector(autoConnect = true) {
    vibrate(18);
    btnScanProjector.disabled = true;
    const origText = btnScanProjector.textContent;
    btnScanProjector.textContent = "⏳ Scanning Smart TVs & Projectors...";
    projectorStatusBanner.innerHTML =
      "📡 Waking phone screen, scanning Smart TVs (Samsung, LG, Sony, TCL, Roku) and Projectors (Miracast / Wireless Display / DLNA)...";

    try {
      const res = await fetch("/api/projector/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: "", auto_connect: autoConnect }),
      });
      const data = await res.json();
      renderProjectorDevices(data.devices || []);
      const ipBadge = data.projector_ip ? ` (IP <strong>${escapeHtml(data.projector_ip)}</strong>)` : "";
      if (data.connected_to) {
        projectorStatusBanner.innerHTML = `✅ Automatically connecting to TV/Projector: <strong>${escapeHtml(data.connected_to)}</strong>${ipBadge}!`;
      } else if (data.active_display) {
        projectorStatusBanner.innerHTML = `🟢 Active Projection: <strong>${escapeHtml(data.active_display)}</strong>${ipBadge}`;
      } else if ((data.devices || []).length > 0) {
        projectorStatusBanner.innerHTML = `✅ Found ${data.devices.length} device(s)${ipBadge}! Tap <strong>Connect</strong> below.`;
      } else {
        projectorStatusBanner.innerHTML =
          "📡 Miracast/Cast discovery active! On your TV or Projector, open <strong>Screen Mirroring / Miracast / Cast</strong> and tap Scan again.";
      }
    } catch (_) {
      projectorStatusBanner.textContent = "Error querying the projection controller.";
    } finally {
      btnScanProjector.disabled = false;
      btnScanProjector.textContent = origText;
    }
  }

  // ==================== TAB 2 FUNCTIONS: PORTABLE WI-FI & RESCUE HOTSPOT ====================
  function updateWifiCurrentCard(data) {
    if (!data) return;
    const cur = data.current || data;
    if (wifiCurrentSsidText) {
      if (cur.connected && cur.ssid) {
        wifiCurrentSsidText.textContent = `🟢 ${cur.ssid}`;
      } else {
        wifiCurrentSsidText.textContent = "🔴 No Wi-Fi (Rescue Hotspot Active)";
      }
    }
    if (wifiCurrentSignalBadge) {
      const freq = cur.frequency_band || "Wi-Fi";
      const pct = cur.signal_percent != null ? `${cur.signal_percent}%` : "--";
      wifiCurrentSignalBadge.textContent = `${freq} • ${pct}`;
    }
    if (wifiCurrentIpCode && cur.ip) {
      wifiCurrentIpCode.textContent = cur.ip;
    }
    if (wifiCurrentGwCode && cur.gateway) {
      wifiCurrentGwCode.textContent = cur.gateway;
    }
    if (wifiMdnsUrlDisplay && (data.mdns_url || cur.mdns_url)) {
      wifiMdnsUrlDisplay.textContent = data.mdns_url || cur.mdns_url;
    }
    if (data.rescue_hotspot) {
      if (rescueHotspotSsidInput && data.rescue_hotspot.ssid && !rescueHotspotSsidInput.dataset.edited) {
        rescueHotspotSsidInput.value = data.rescue_hotspot.ssid;
      }
      if (rescueHotspotPassInput && data.rescue_hotspot.password && !rescueHotspotPassInput.dataset.edited) {
        rescueHotspotPassInput.value = data.rescue_hotspot.password;
      }
    }
  }

  function renderWifiNetworksList(networks) {
    if (!wifiNetworksList) return;
    wifiNetworksList.innerHTML = "";
    if (!Array.isArray(networks) || networks.length === 0) {
      wifiNetworksList.innerHTML = `
        <div class="projector-empty">
          No Wi-Fi networks listed yet. Tap <strong>🔍 Scan Nearby Wi-Fi Networks</strong>.
        </div>
      `;
      return;
    }

    networks.forEach((net) => {
      const card = document.createElement("div");
      card.className = "projector-device-card";
      const isCur = Boolean(net.is_current);
      const isSaved = Boolean(net.is_saved);
      const isRescue = Boolean(net.is_rescue);
      const secIcon = net.security === "open" ? "🔓 Open" : `🔒 ${escapeHtml((net.security || "WPA2").toUpperCase())}`;
      const statusBadges = [
        isCur ? '<span style="color:#4ade80;font-weight:700;font-size:0.73rem;">🟢 CONNECTED</span>' : "",
        !isCur && isSaved ? '<span style="color:#38bdf8;font-weight:700;font-size:0.72rem;">💾 SAVED</span>' : "",
        isRescue ? '<span style="color:#fbbf24;font-weight:700;font-size:0.72rem;">🆘 RESCUE</span>' : "",
      ]
        .filter(Boolean)
        .join(" ");

      const btnLabel = isCur ? "Reconnect" : "Select";
      const safeSsid = escapeHtml(net.ssid);
      const bandText = escapeHtml(net.band_label || net.band || "2.4GHz");
      const barsHtml = buildSignalBarsHtml(net.signal_percent || 0);
      card.innerHTML = `
        <div class="projector-device-info">
          <span class="projector-device-name">${barsHtml} ${safeSsid} ${statusBadges}</span>
          <span class="projector-device-meta">${bandText} • Signal ${net.signal_percent || 0}% (${net.rssi || -70} dBm) • ${secIcon}</span>
        </div>
        <button type="button" class="projector-connect-btn">${btnLabel}</button>
      `;

      const selectAction = () => {
        vibrate(14);
        if (wifiTargetSsidInput) {
          wifiTargetSsidInput.value = net.ssid;
        }
        if (wifiTargetSecSelect) {
          const secVal = net.security === "open" ? "open" : net.security === "wpa3" ? "wpa3" : "wpa2";
          wifiTargetSecSelect.value = secVal;
          if (wifiPasswordRow) {
            wifiPasswordRow.classList.toggle("hidden", secVal === "open");
          }
        }
        if (wifiStatusBanner) {
          wifiStatusBanner.innerHTML =
            net.security === "open"
              ? `🔓 Open network <strong>${safeSsid}</strong> selected! Tap <strong>🔗 Connect / Save Wi-Fi</strong>.`
              : `🔒 Network <strong>${safeSsid}</strong> selected! Enter the password below and tap <strong>🔗 Connect / Save Wi-Fi</strong>.`;
        }
        if (net.security !== "open" && wifiTargetPassInput) {
          wifiTargetPassInput.focus();
        }
      };

      const btn = card.querySelector(".projector-connect-btn");
      if (btn) btn.addEventListener("click", selectAction);
      card.addEventListener("click", (e) => {
        if (e.target !== btn) selectAction();
      });

      wifiNetworksList.appendChild(card);
    });
  }

  async function loadWifiPortableStatus(autoScanIfEmpty = false) {
    try {
      const res = await fetch("/api/wifi/status");
      const data = await res.json();
      updateWifiCurrentCard(data);
      if (Array.isArray(data.networks) && data.networks.length > 0) {
        renderWifiNetworksList(data.networks);
      } else if (autoScanIfEmpty) {
        scanWifiPortableNetworks();
      }
    } catch (_) {
      if (wifiStatusBanner) {
        wifiStatusBanner.textContent = "Error reading Wi-Fi status from Redmi Note 8 Pro.";
      }
    }
  }

  async function scanWifiPortableNetworks() {
    vibrate(16);
    if (btnScanWifiNetworks) {
      btnScanWifiNetworks.disabled = true;
      btnScanWifiNetworks.textContent = "⏳ Scanning Nearby Wi-Fi Networks...";
    }
    if (wifiStatusBanner) {
      wifiStatusBanner.innerHTML = "📡 Scanning all 2.4GHz and 5GHz Wi-Fi networks around the Redmi Note 8 Pro...";
    }
    try {
      const res = await fetch("/api/wifi/scan", { method: "POST" });
      const data = await res.json();
      updateWifiCurrentCard(data);
      renderWifiNetworksList(data.networks || []);
      if (wifiStatusBanner) {
        wifiStatusBanner.innerHTML = `✅ Found <strong>${(data.networks || []).length}</strong> Wi-Fi networks! Tap any network below to fill in or connect.`;
      }
    } catch (_) {
      if (wifiStatusBanner) {
        wifiStatusBanner.textContent = "Error scanning Wi-Fi networks.";
      }
    } finally {
      if (btnScanWifiNetworks) {
        btnScanWifiNetworks.disabled = false;
        btnScanWifiNetworks.textContent = "🔍 Scan Nearby Wi-Fi Networks";
      }
    }
  }

  async function submitWifiConnection(saveOnly = false) {
    vibrate(18);
    const ssid = (wifiTargetSsidInput ? wifiTargetSsidInput.value : "").trim();
    const security = wifiTargetSecSelect ? wifiTargetSecSelect.value : "wpa2";
    const password = wifiTargetPassInput ? wifiTargetPassInput.value : "";

    if (!ssid) {
      if (wifiStatusBanner) {
        wifiStatusBanner.innerHTML = "⚠️ Select a Wi-Fi network from the list below or enter the <strong>Wi-Fi Name (SSID)</strong>.";
      }
      if (wifiTargetSsidInput) wifiTargetSsidInput.focus();
      return;
    }
    if (security !== "open" && password.length < 8) {
      if (wifiStatusBanner) {
        wifiStatusBanner.innerHTML = "⚠️ WPA2/WPA3 Wi-Fi passwords must be at least <strong>8 characters</strong>.";
      }
      if (wifiTargetPassInput) wifiTargetPassInput.focus();
      return;
    }

    const safeSsid = escapeHtml(ssid);
    if (wifiStatusBanner) {
      wifiStatusBanner.innerHTML = saveOnly
        ? `💾 Saving Wi-Fi network <strong>${safeSsid}</strong> on the Redmi Note 8 Pro for automatic travel connection...`
        : `🔗 Connecting and saving Wi-Fi <strong>${safeSsid}</strong> on the Redmi Note 8 Pro (if switching networks, open <code>http://hybridbox.local:8080</code>)...`;
    }

    try {
      const res = await fetch("/api/wifi/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ssid, password, security, save_only: saveOnly }),
      });
      const data = await res.json();
      if (wifiStatusBanner) {
        wifiStatusBanner.innerHTML = data.message || "✅ Wi-Fi command executed!";
      }
      updateWifiCurrentCard(data);
      if (Array.isArray(data.networks) && data.networks.length > 0) {
        renderWifiNetworksList(data.networks);
      }
    } catch (_) {
      if (wifiStatusBanner) {
        wifiStatusBanner.innerHTML =
          "📡 Wi-Fi switch in progress! Connect your phone to the same Wi-Fi and open <code>http://hybridbox.local:8080</code>.";
      }
    }
  }

  async function submitRescueHotspot(connectNow = false) {
    vibrate(18);
    const ssid = (rescueHotspotSsidInput ? rescueHotspotSsidInput.value : "HybridBox").trim();
    const password = (rescueHotspotPassInput ? rescueHotspotPassInput.value : "hybridbox123").trim();

    if (!ssid || password.length < 8) {
      if (wifiStatusBanner) {
        wifiStatusBanner.innerHTML =
          "⚠️ The Rescue Hotspot requires a name (SSID) and a password of at least <strong>8 characters</strong>.";
      }
      return;
    }

    const safeSsid = escapeHtml(ssid);
    if (wifiStatusBanner) {
      wifiStatusBanner.innerHTML = connectNow
        ? `🆘 Saving and connecting to Rescue Hotspot <strong>${safeSsid}</strong>...`
        : `🆘 Saving Rescue Hotspot <strong>${safeSsid}</strong> on the Redmi Note 8 Pro and in the automatic Watchdog...`;
    }

    try {
      const res = await fetch("/api/wifi/rescue-hotspot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ssid, password, security: "wpa2", connect_now: connectNow }),
      });
      const data = await res.json();
      if (wifiStatusBanner) {
        wifiStatusBanner.innerHTML = data.message || "🆘 Rescue Hotspot configured!";
      }
      updateWifiCurrentCard(data);
      if (Array.isArray(data.networks) && data.networks.length > 0) {
        renderWifiNetworksList(data.networks);
      }
    } catch (_) {
      if (wifiStatusBanner) {
        wifiStatusBanner.textContent = "Error saving Rescue Hotspot.";
      }
    }
  }

  if (rescueHotspotSsidInput) {
    rescueHotspotSsidInput.addEventListener("input", () => {
      rescueHotspotSsidInput.dataset.edited = "1";
    });
  }
  if (rescueHotspotPassInput) {
    rescueHotspotPassInput.addEventListener("input", () => {
      rescueHotspotPassInput.dataset.edited = "1";
    });
  }

  if (wifiTargetSecSelect) {
    wifiTargetSecSelect.addEventListener("change", () => {
      const isOpen = wifiTargetSecSelect.value === "open";
      if (wifiPasswordRow) {
        wifiPasswordRow.classList.toggle("hidden", isOpen);
      }
    });
  }

  if (btnToggleWifiPass && wifiTargetPassInput) {
    btnToggleWifiPass.addEventListener("click", () => {
      vibrate(10);
      const isPass = wifiTargetPassInput.type === "password";
      wifiTargetPassInput.type = isPass ? "text" : "password";
      btnToggleWifiPass.textContent = isPass ? "🙈 Hide" : "👁️ Show";
    });
  }

  if (btnCopyMdnsUrl) {
    btnCopyMdnsUrl.addEventListener("click", async () => {
      vibrate(14);
      const urlText = wifiMdnsUrlDisplay ? wifiMdnsUrlDisplay.textContent : "http://hybridbox.local:8080";
      try {
        await navigator.clipboard.writeText(urlText);
        btnCopyMdnsUrl.textContent = "✅ Copied!";
        setTimeout(() => {
          btnCopyMdnsUrl.textContent = "📋 Copy Link";
        }, 2000);
      } catch (_) {
        btnCopyMdnsUrl.textContent = "📋 http://hybridbox.local:8080";
      }
    });
  }

  if (btnScanWifiNetworks) {
    btnScanWifiNetworks.addEventListener("click", () => scanWifiPortableNetworks());
  }
  if (btnConnectWifiSubmit) {
    btnConnectWifiSubmit.addEventListener("click", () => submitWifiConnection(false));
  }
  if (btnPreSaveWifiSubmit) {
    btnPreSaveWifiSubmit.addEventListener("click", () => submitWifiConnection(true));
  }
  if (btnSaveRescueHotspot) {
    btnSaveRescueHotspot.addEventListener("click", () => submitRescueHotspot(false));
  }
  if (btnTestRescueHotspot) {
    btnTestRescueHotspot.addEventListener("click", () => submitRescueHotspot(true));
  }

  function openProjectorModal(triggerScan = false, initialTab = "projector") {
    vibrate(15);
    projectorModal.classList.remove("hidden");
    switchProjectorModalTab(initialTab);
    if (initialTab === "wifi") {
      return;
    }
    if (triggerScan) {
      scanAndConnectProjector(true);
    } else {
      fetch("/api/projector/status")
        .then((r) => r.json())
        .then((data) => {
          if (data.devices && data.devices.length > 0) {
            renderProjectorDevices(data.devices);
          }
          const ipInfo = data.projector_ip ? ` • Wi-Fi IP: <strong>${data.projector_ip}</strong>` : "";
          if (data.active_display) {
            projectorStatusBanner.innerHTML = `🟢 Connected to: <strong>${data.active_display}</strong>${ipInfo}`;
          } else if (data.projector_ip) {
            projectorStatusBanner.innerHTML = `📍 TV / Projector found on LAN (${ipInfo}). Tap <strong>Connect</strong> below:`;
          }
        })
        .catch(() => {});
    }
  }

  if (btnProjectorOpen) {
    btnProjectorOpen.addEventListener("click", () => openProjectorModal(false, "projector"));
  }
  if (btnQuickProjector) {
    btnQuickProjector.addEventListener("click", () => openProjectorModal(true, "projector"));
  }
  if (btnQuickWifi) {
    btnQuickWifi.addEventListener("click", () => openProjectorModal(false, "wifi"));
  }
  if (btnCloseProjectorModal) {
    btnCloseProjectorModal.addEventListener("click", () => {
      projectorModal.classList.add("hidden");
    });
  }
  if (projectorModal) {
    projectorModal.addEventListener("click", (e) => {
      if (e.target === projectorModal) {
        projectorModal.classList.add("hidden");
      }
    });
  }
  if (btnScanProjector) {
    btnScanProjector.addEventListener("click", () => scanAndConnectProjector(true));
  }
  if (btnDisconnectProjector) {
    btnDisconnectProjector.addEventListener("click", () => disconnectProjector());
  }
  if (btnUseHdmiCable) {
    btnUseHdmiCable.addEventListener("click", async () => {
      vibrate(15);
      projectorStatusBanner.textContent = "🔌 Activating HDMI Cable / USB-C DisplayLink output and waking screen...";
      try {
        const res = await fetch("/api/projector/hdmi", { method: "POST" });
        const data = await res.json();
        projectorStatusBanner.innerHTML = data.message || "🔌 HDMI Cable / DisplayLink mode activated!";
      } catch (_) {
        projectorStatusBanner.textContent = "Error activating HDMI / DisplayLink output.";
      }
    });
  }
  if (btnWakePhoneScreen) {
    btnWakePhoneScreen.addEventListener("click", async () => {
      vibrate(15);
      projectorStatusBanner.textContent = "☀️ Waking phone screen and enabling WakeLock over Wi-Fi SSH...";
      try {
        const res = await fetch("/api/projector/wake-phone", { method: "POST" });
        const data = await res.json();
        projectorStatusBanner.innerHTML = data.message || "☀️ Phone screen is awake!";
      } catch (_) {
        projectorStatusBanner.textContent = "Error waking phone screen.";
      }
    });
  }
  if (btnLocateProjectorIp) {
    btnLocateProjectorIp.addEventListener("click", async () => {
      vibrate(15);
      projectorStatusBanner.textContent = "📍 Scanning Wi-Fi LAN (ARP + /24 subnet) for Smart TVs and Projectors...";
      try {
        const res = await fetch("/api/projector/locate-ip", { method: "POST" });
        const data = await res.json();
        projectorStatusBanner.innerHTML = data.message || "IP scan complete!";
        if (data.devices) {
          renderProjectorDevices(data.devices);
        }
      } catch (_) {
        projectorStatusBanner.textContent = "Error locating TV/Projector on LAN.";
      }
    });
  }
  document.querySelectorAll("[data-proj-mode]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      vibrate(14);
      const mode = btn.getAttribute("data-proj-mode") || "clone";
      projectorStatusBanner.textContent = `⏳ Applying display mode (${mode})...`;
      try {
        const res = await fetch("/api/projector/display-mode", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode }),
        });
        const data = await res.json();
        projectorStatusBanner.innerHTML = data.message || "Display mode applied!";
        if (data.devices) {
          renderProjectorDevices(data.devices);
        }
      } catch (_) {
        projectorStatusBanner.textContent = "Error changing display mode.";
      }
    });
  });

  if (btnMiuiCast) {
    btnMiuiCast.addEventListener("click", async () => {
      vibrate(14);
      projectorStatusBanner.textContent = "📱 Opening MIUI Cast on phone (keeping screen awake)...";
      try {
        const res = await fetch("/api/projector/miui-cast", { method: "POST" });
        const data = await res.json();
        projectorStatusBanner.textContent = data.message || "MIUI Cast opened!";
      } catch (_) {
        projectorStatusBanner.textContent = "Error opening MIUI Cast.";
      }
    });
  }
  if (btnWindowsCast) {
    btnWindowsCast.addEventListener("click", async () => {
      vibrate(14);
      projectorStatusBanner.textContent = "💻 Opening Windows Wireless Display (Win+K) on laptop...";
      try {
        const res = await fetch("/api/projector/windows-cast", { method: "POST" });
        const data = await res.json();
        projectorStatusBanner.textContent = data.message || "Windows Cast panel opened!";
      } catch (_) {
        projectorStatusBanner.textContent = "Error opening Windows Cast panel.";
      }
    });
  }

  // ==================== GAMES SESSION (SNES, MAME, FULL SCREEN LANDSCAPE, PHOTO SKIN & MORE CONTROLLERS) ====================
  const tabGamesPad = document.getElementById("tabGamesPad");
  const tabGamesConsoles = document.getElementById("tabGamesConsoles");
  const tabGamesBluetooth = document.getElementById("tabGamesBluetooth");
  const gamesPadContainer = document.getElementById("gamesPadContainer");
  const gamesConsolesContainer = document.getElementById("gamesConsolesContainer");
  const gamesBluetoothContainer = document.getElementById("gamesBluetoothContainer");
  const btnQuickBt = document.getElementById("btnQuickBt");
  const btnPhysicalGamepadStatus = document.getElementById("btnPhysicalGamepadStatus");
  const btnTurboToggle = document.getElementById("btnTurboToggle");
  const activeConsoleIcon = document.getElementById("activeConsoleIcon");
  const activeConsoleLabel = document.getElementById("activeConsoleLabel");
  const activePlayerBadge = document.getElementById("activePlayerBadge");
  const coinCounterBadge = document.getElementById("coinCounterBadge");
  const btnGamepadFullscreen = document.getElementById("btnGamepadFullscreen");
  const btnTogglePhotoMode = document.getElementById("btnTogglePhotoMode");
  const snesControllerShell = document.getElementById("snesControllerShell");
  const activeControllerPhoto = document.getElementById("activeControllerPhoto");
  const shellBrandTitle = document.getElementById("shellBrandTitle");
  const shellBrandSub = document.getElementById("shellBrandSub");
  const controllerQuickStrip = document.getElementById("controllerQuickStrip");
  const btnMoreControllersTop = document.getElementById("btnMoreControllersTop");
  const btnQuickMoreControllers = document.getElementById("btnQuickMoreControllers");
  const moreControllersModal = document.getElementById("moreControllersModal");
  const btnCloseControllersModal = document.getElementById("btnCloseControllersModal");
  const controllersModalBanner = document.getElementById("controllersModalBanner");
  const btnModalEnterFullscreen = document.getElementById("btnModalEnterFullscreen");
  const btnModalPairBluetooth = document.getElementById("btnModalPairBluetooth");
  const newCtrlPlayerSelect = document.getElementById("newCtrlPlayerSelect");
  const newCtrlSkinSelect = document.getElementById("newCtrlSkinSelect");
  const newCtrlNameInput = document.getElementById("newCtrlNameInput");
  const btnAddCustomController = document.getElementById("btnAddCustomController");
  const configuredControllersList = document.getElementById("configuredControllersList");
  const player2WifiUrl = document.getElementById("player2WifiUrl");
  const btnCopyPlayer2Link = document.getElementById("btnCopyPlayer2Link");
  const btnSwitchThisPhoneToP2 = document.getElementById("btnSwitchThisPhoneToP2");
  const gamesStatusBanner = document.getElementById("gamesStatusBanner");
  const emulatorsList = document.getElementById("emulatorsList");
  const romSystemSelect = document.getElementById("romSystemSelect");
  const romFileInput = document.getElementById("romFileInput");
  const btnPickRomFile = document.getElementById("btnPickRomFile");
  const romListContainer = document.getElementById("romListContainer");
  const webEmulatorCard = document.getElementById("webEmulatorCard");
  const webEmuTitle = document.getElementById("webEmuTitle");
  const btnCloseWebEmu = document.getElementById("btnCloseWebEmu");
  const emulatorJsHost = document.getElementById("emulatorJsHost");
  const btStatusBanner = document.getElementById("btStatusBanner");
  const btnScanBluetooth = document.getElementById("btnScanBluetooth");
  const btnOpenRareBluetooth = document.getElementById("btnOpenRareBluetooth");
  const btnRefreshBluetooth = document.getElementById("btnRefreshBluetooth");
  const btActiveGamepadsBox = document.getElementById("btActiveGamepadsBox");
  const btDevicesList = document.getElementById("btDevicesList");

  const snesPhotoShowcase = document.getElementById("snesPhotoShowcase");

  function escapeHtml(raw) {
    return String(raw || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  const CONTROLLER_SKINS_META = {
    snes: {
      icon: "🍄",
      shortName: "SNES Classic",
      label: "Super Nintendo (SNES Classic)",
      brandTitle: "SUPER NINTENDO",
      brandSub: "ENTERTAINMENT SYSTEM",
      photo: "/static/icons/snes-controller-photo.jpg",
      system: "snes",
    },
    snes_us: {
      icon: "🟣",
      shortName: "SNES US Purple",
      label: "Super Nintendo US (Purple / Lavender)",
      brandTitle: "SUPER NINTENDO",
      brandSub: "NORTH AMERICA EDITION",
      photo: "/static/icons/snes-us-controller-photo.jpg",
      system: "snes",
    },
    mame: {
      icon: "🕹️",
      shortName: "Arcade Stick",
      label: "Arcade Fightstick (MAME / NeoGeo)",
      brandTitle: "ARCADE NEOGEO",
      brandSub: "6-BUTTON FIGHTSTICK",
      photo: "/static/icons/arcade-controller-photo.jpg",
      system: "mame",
    },
    megadrive: {
      icon: "🦔",
      shortName: "Mega Drive 6-Btn",
      label: "Sega Mega Drive (6-Button)",
      brandTitle: "SEGA MEGA DRIVE",
      brandSub: "6 BUTTON ARCADE PAD",
      photo: "/static/icons/megadrive-controller-photo.jpg",
      system: "megadrive",
    },
  };

  /**
   * Envia comando de botão do Gamepad Virtual com informação de Player (P1..P4) e Estilo/Console
   */
  function sendGamepadCommand(key) {
    if (!key) return;
    if (key === "BTN_COIN") {
      clientState.coinCount += 1;
      if (coinCounterBadge) {
        coinCounterBadge.textContent = String(clientState.coinCount);
      }
      vibrate([16, 25, 20]);
    }
    const meta = CONTROLLER_SKINS_META[clientState.activeSkin] || CONTROLLER_SKINS_META.snes;
    sendWs({
      type: "gamepad",
      key,
      player: clientState.activePlayer || 1,
      style: meta.system || "snes",
    });
  }

  /**
   * Ativa ou desativa o Modo Full Screen Landscape (Tela Cheia em Paisagem com fallback de rotação CSS 90°)
   */
  function setGamepadFullscreenLandscape(enable) {
    vibrate(18);
    clientState.fullscreenLandscape = Boolean(enable);

    if (clientState.fullscreenLandscape) {
      if (clientState.mode !== "games") {
        switchSystemMode("games");
      }
      if (clientState.gamesSubTab !== "pad") {
        switchGamesSubTab("pad");
      }
      document.body.classList.add("gamepad-fullscreen-landscape");
      if (btnGamepadFullscreen) {
        btnGamepadFullscreen.classList.add("active");
        btnGamepadFullscreen.innerHTML = "✕ EXIT FULL";
      }

      const docEl = document.documentElement;
      const reqFs =
        docEl.requestFullscreen || docEl.webkitRequestFullscreen || docEl.msRequestFullscreen;
      if (reqFs && !document.fullscreenElement && !document.webkitFullscreenElement) {
        try {
          Promise.resolve(reqFs.call(docEl)).catch(() => {});
        } catch (_) {}
      }
      if (window.screen && window.screen.orientation && typeof window.screen.orientation.lock === "function") {
        try {
          window.screen.orientation.lock("landscape").catch(() => {});
        } catch (_) {}
      }
    } else {
      clientState.nativeFullscreenActive = false;
      document.body.classList.remove("gamepad-fullscreen-landscape");
      if (btnGamepadFullscreen) {
        btnGamepadFullscreen.classList.remove("active");
        btnGamepadFullscreen.innerHTML = "⛶ FULL LANDSCAPE";
      }

      const exitFs =
        document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen;
      if (exitFs && (document.fullscreenElement || document.webkitFullscreenElement)) {
        try {
          Promise.resolve(exitFs.call(document)).catch(() => {});
        } catch (_) {}
      }
      if (
        window.screen &&
        window.screen.orientation &&
        typeof window.screen.orientation.unlock === "function"
      ) {
        try {
          window.screen.orientation.unlock();
        } catch (_) {}
      }
    }
  }

  function toggleGamepadFullscreenLandscape() {
    setGamepadFullscreenLandscape(!clientState.fullscreenLandscape);
  }

  if (btnGamepadFullscreen) {
    btnGamepadFullscreen.addEventListener("click", toggleGamepadFullscreenLandscape);
  }

  function handleNativeFullscreenChange() {
    const isFs = Boolean(document.fullscreenElement || document.webkitFullscreenElement);
    if (isFs) {
      clientState.nativeFullscreenActive = true;
    } else if (clientState.nativeFullscreenActive && clientState.fullscreenLandscape) {
      clientState.nativeFullscreenActive = false;
      setGamepadFullscreenLandscape(false);
    }
  }

  document.addEventListener("fullscreenchange", handleNativeFullscreenChange);
  document.addEventListener("webkitfullscreenchange", handleNativeFullscreenChange);

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (hudGameDrawer && !hudGameDrawer.classList.contains("hidden")) {
        closeHudGameDrawer();
      } else if (moreControllersModal && !moreControllersModal.classList.contains("hidden")) {
        closeMoreControllersModal();
      } else if (clientState.fullscreenLandscape) {
        setGamepadFullscreenLandscape(false);
      }
    }
  });

  /**
   * Toggle between Highlighted Realistic Photo Mode and 3D Shell Mode
   */
  function updatePhotoModeUI() {
    if (snesControllerShell) {
      snesControllerShell.classList.toggle("photo-mode-active", clientState.photoModeEnabled);
    }
    if (btnTogglePhotoMode) {
      btnTogglePhotoMode.classList.toggle("active", clientState.photoModeEnabled);
      const skinShort =
        clientState.activeSkin === "mame"
          ? "Arcade"
          : clientState.activeSkin === "megadrive"
          ? "Sega"
          : "SNES";
      btnTogglePhotoMode.textContent = `📸 ${skinShort} Photo: ${
        clientState.photoModeEnabled ? "ON" : "OFF"
      }`;
    }
  }

  if (btnTogglePhotoMode) {
    btnTogglePhotoMode.addEventListener("click", () => {
      vibrate(14);
      clientState.photoModeEnabled = !clientState.photoModeEnabled;
      updatePhotoModeUI();
    });
  }

  if (snesPhotoShowcase) {
    snesPhotoShowcase.addEventListener("click", openMoreControllersModal);
  }

  /**
   * Apply a controller skin/photo (SNES Classic, SNES US Purple, Arcade Stick, Mega Drive 6-Btn) and Player (P1..P4)
   */
  function applyControllerSkin(
    skinId,
    playerNum = null,
    customLabel = "",
    notifyBackend = true,
    controllerId = ""
  ) {
    const cleanSkin = CONTROLLER_SKINS_META[skinId] ? skinId : "snes";
    const meta = CONTROLLER_SKINS_META[cleanSkin];
    clientState.activeSkin = cleanSkin;
    if (playerNum !== null && playerNum !== undefined) {
      clientState.activePlayer = Math.max(1, Math.min(4, Number(playerNum) || 1));
    }
    if (controllerId) {
      clientState.activeControllerId = controllerId;
    }
    const pNum = clientState.activePlayer;

    if (gamesPadContainer) {
      gamesPadContainer.setAttribute("data-active-skin", cleanSkin);
      gamesPadContainer.setAttribute("data-active-player", String(pNum));
    }
    if (snesControllerShell) {
      snesControllerShell.setAttribute("data-skin", cleanSkin);
    }
    if (activeControllerPhoto) {
      activeControllerPhoto.src = meta.photo;
      activeControllerPhoto.alt = meta.label;
    }
    if (activeConsoleIcon) {
      activeConsoleIcon.textContent = meta.icon;
    }
    if (activeConsoleLabel) {
      activeConsoleLabel.textContent = `${customLabel || meta.label} • P${pNum}`;
    }
    if (activePlayerBadge) {
      activePlayerBadge.textContent = `P${pNum}`;
    }
    if (shellBrandTitle) {
      shellBrandTitle.textContent = meta.brandTitle;
    }
    if (shellBrandSub) {
      shellBrandSub.textContent = `${meta.brandSub} • P${pNum}`;
    }

    updatePhotoModeUI();

    // Update active chips in the quick strip
    document.querySelectorAll("[data-skin-select]").forEach((chip) => {
      const chipSkin = chip.getAttribute("data-skin-select");
      const chipPlayer = Number(chip.getAttribute("data-player-select") || "1");
      const chipCtrlId = chip.getAttribute("data-ctrl-id") || "";
      const isMatch = chipCtrlId
        ? chipCtrlId === clientState.activeControllerId
        : chipSkin === cleanSkin && chipPlayer === pNum && !chip.classList.contains("custom-added-chip");
      chip.classList.toggle("active", isMatch);
    });

    // Update cards in the modal gallery
    document.querySelectorAll("[data-skin-card]").forEach((card) => {
      card.classList.toggle("active", card.getAttribute("data-skin-card") === cleanSkin);
    });

    try {
      localStorage.setItem(
        "hybridbox_controller_pref",
        JSON.stringify({
          skin: cleanSkin,
          player: pNum,
          label: customLabel || "",
          controller_id: clientState.activeControllerId || "",
        })
      );
    } catch (_) {}

    if (notifyBackend) {
      fetch("/api/games/controllers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "select",
          controller_id: controllerId || "",
          skin_id: cleanSkin,
          player: pNum,
          name: customLabel || "",
        }),
      })
        .then((r) => r.json())
        .then((data) => {
          if (data && data.active_controller_id) {
            clientState.activeControllerId = data.active_controller_id;
          }
          if (data && Array.isArray(data.controllers)) {
            clientState.controllersList = data.controllers;
            renderConfiguredControllersList(data);
          }
        })
        .catch(() => {});
    }
  }

  function bindQuickStripChips() {
    document.querySelectorAll("[data-skin-select]").forEach((chip) => {
      if (chip.dataset.bound === "1") return;
      chip.dataset.bound = "1";
      chip.addEventListener("click", () => {
        vibrate(14);
        const sId = chip.getAttribute("data-skin-select") || "snes";
        const pId = Number(chip.getAttribute("data-player-select") || "1");
        const cName = chip.getAttribute("data-ctrl-name") || "";
        const cId = chip.getAttribute("data-ctrl-id") || "";
        applyControllerSkin(sId, pId, cName, true, cId);
      });
    });
  }
  bindQuickStripChips();

  // ==================== MANAGE & ADD MORE CONTROLLERS MODAL ====================
  async function loadControllersConfig() {
    const hostOrigin = window.location.origin;
    if (player2WifiUrl) {
      player2WifiUrl.textContent = `${hostOrigin}/?mode=games&player=2&skin=${clientState.activeSkin}&fullscreen=1`;
    }
    try {
      const res = await fetch("/api/games/controllers");
      if (!res.ok) return;
      const data = await res.json();
      if (data.active_controller_id) {
        clientState.activeControllerId = data.active_controller_id;
      }
      if (Array.isArray(data.controllers)) {
        clientState.controllersList = data.controllers;
        renderConfiguredControllersList(data);
      }
      if (data.multiplayer_links && data.multiplayer_links.player_2 && player2WifiUrl) {
        player2WifiUrl.textContent = data.multiplayer_links.player_2;
      }
    } catch (_) {}
  }

  function renderConfiguredControllersList(data) {
    if (!configuredControllersList) return;
    const list = (data && data.controllers) || clientState.controllersList || [];
    const activeId = (data && data.active_controller_id) || clientState.activeControllerId || "";
    configuredControllersList.innerHTML = "";

    // Sync extra controllers into the quick strip (#controllerQuickStrip)
    if (controllerQuickStrip && btnQuickMoreControllers) {
      controllerQuickStrip.querySelectorAll(".custom-added-chip").forEach((el) => el.remove());
      list.forEach((ctrl) => {
        if (!ctrl.builtin && !(ctrl.skin_id === "snes" && ctrl.player === 2 && ctrl.id === "ctrl_snes_p2")) {
          const chip = document.createElement("button");
          chip.type = "button";
          chip.className = "ctrl-skin-chip custom-added-chip";
          chip.setAttribute("data-skin-select", ctrl.skin_id);
          chip.setAttribute("data-player-select", String(ctrl.player));
          chip.setAttribute("data-ctrl-name", ctrl.name);
          chip.setAttribute("data-ctrl-id", ctrl.id);
          if (activeId ? ctrl.id === activeId : ctrl.skin_id === clientState.activeSkin && ctrl.player === clientState.activePlayer) {
            chip.classList.add("active");
          }
          chip.textContent = `${ctrl.icon || "🎮"} ${ctrl.name}`;
          controllerQuickStrip.insertBefore(chip, btnQuickMoreControllers);
        }
      });
      bindQuickStripChips();
    }

    list.forEach((ctrl) => {
      const isActive = activeId
        ? ctrl.id === activeId
        : ctrl.skin_id === clientState.activeSkin && Number(ctrl.player) === Number(clientState.activePlayer);
      const safeName = escapeHtml(ctrl.name);
      const safeIcon = escapeHtml(ctrl.icon || "🎮");
      const safePhoto = escapeHtml(ctrl.photo_url || "/static/icons/snes-controller-photo.jpg");
      const safeSkin = escapeHtml(String(ctrl.skin_id || "snes").toUpperCase());
      const card = document.createElement("div");
      card.className = "projector-device-card ctrl-room-card";
      card.innerHTML = `
        <div class="ctrl-room-left">
          <img src="${safePhoto}" alt="${safeName}" class="ctrl-room-thumb" />
          <div class="projector-device-info">
            <span class="projector-device-name">${safeIcon} ${safeName}</span>
            <span class="projector-device-meta">Player P${Number(ctrl.player) || 1} • Skin: ${safeSkin} ${isActive ? "• 🟢 ACTIVE" : ""}</span>
          </div>
        </div>
        <div class="ctrl-room-actions">
          <button type="button" class="projector-connect-btn" data-select-ctrl="${escapeHtml(ctrl.id)}">
            ${isActive ? "Active ✅" : "Use"}
          </button>
          ${
            !ctrl.builtin
              ? `<button type="button" class="icon-btn ctrl-room-del-btn" data-remove-ctrl="${escapeHtml(ctrl.id)}" title="Remove controller">🗑️</button>`
              : ""
          }
        </div>
      `;
      const useBtn = card.querySelector("[data-select-ctrl]");
      if (useBtn) {
        useBtn.addEventListener("click", () => {
          vibrate(14);
          applyControllerSkin(ctrl.skin_id, ctrl.player, ctrl.name, true, ctrl.id);
          if (controllersModalBanner) {
            controllersModalBanner.innerHTML = `✅ Active controller switched to: <strong>${safeName} (Player ${Number(ctrl.player) || 1})</strong>!`;
          }
        });
      }
      const delBtn = card.querySelector("[data-remove-ctrl]");
      if (delBtn) {
        delBtn.addEventListener("click", async () => {
          vibrate(14);
          try {
            const res = await fetch("/api/games/controllers", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ action: "remove", controller_id: ctrl.id }),
            });
            const updated = await res.json();
            if (updated && updated.active_controller_id) {
              clientState.activeControllerId = updated.active_controller_id;
            }
            if (controllersModalBanner && updated.message) {
              controllersModalBanner.innerHTML = escapeHtml(updated.message);
            }
            renderConfiguredControllersList(updated);
          } catch (_) {}
        });
      }
      configuredControllersList.appendChild(card);
    });
  }

  function openMoreControllersModal() {
    vibrate(15);
    if (!moreControllersModal) return;
    moreControllersModal.classList.remove("hidden");
    loadControllersConfig();
  }

  function closeMoreControllersModal() {
    if (moreControllersModal) {
      moreControllersModal.classList.add("hidden");
    }
  }

  if (btnMoreControllersTop) {
    btnMoreControllersTop.addEventListener("click", openMoreControllersModal);
  }
  if (btnQuickMoreControllers) {
    btnQuickMoreControllers.addEventListener("click", openMoreControllersModal);
  }
  if (btnCloseControllersModal) {
    btnCloseControllersModal.addEventListener("click", closeMoreControllersModal);
  }
  if (moreControllersModal) {
    moreControllersModal.addEventListener("click", (e) => {
      if (e.target === moreControllersModal) {
        closeMoreControllersModal();
      }
    });
  }

  document.querySelectorAll("[data-apply-skin]").forEach((btn) => {
    btn.addEventListener("click", () => {
      vibrate(15);
      const skinId = btn.getAttribute("data-apply-skin") || "snes";
      applyControllerSkin(skinId, clientState.activePlayer, "", true);
      if (controllersModalBanner) {
        const meta = CONTROLLER_SKINS_META[skinId] || CONTROLLER_SKINS_META.snes;
        controllersModalBanner.innerHTML = `✅ Controller skin switched to <strong>${escapeHtml(meta.label)} (Player ${clientState.activePlayer})</strong>!`;
      }
      closeMoreControllersModal();
    });
  });

  if (btnAddCustomController) {
    btnAddCustomController.addEventListener("click", async () => {
      vibrate(18);
      const player = newCtrlPlayerSelect ? Number(newCtrlPlayerSelect.value || "2") : 2;
      const skinId = newCtrlSkinSelect ? newCtrlSkinSelect.value || "snes" : "snes";
      const customName = newCtrlNameInput ? newCtrlNameInput.value.trim() : "";
      try {
        const res = await fetch("/api/games/controllers", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "add",
            skin_id: skinId,
            player,
            name: customName,
          }),
        });
        const data = await res.json();
        if (newCtrlNameInput) newCtrlNameInput.value = "";
        if (data && data.active_controller_id) {
          clientState.activeControllerId = data.active_controller_id;
        }
        if (Array.isArray(data.controllers)) {
          clientState.controllersList = data.controllers;
        }
        const added = data.active_controller || { skin_id: skinId, player, name: customName, id: "" };
        applyControllerSkin(
          added.skin_id || skinId,
          added.player || player,
          added.name || customName,
          false,
          added.id || ""
        );
        renderConfiguredControllersList(data);
        if (controllersModalBanner && data.message) {
          controllersModalBanner.innerHTML = escapeHtml(data.message);
        }
      } catch (_) {
        applyControllerSkin(skinId, player, customName, false);
      }
    });
  }

  if (btnModalEnterFullscreen) {
    btnModalEnterFullscreen.addEventListener("click", () => {
      closeMoreControllersModal();
      setGamepadFullscreenLandscape(true);
    });
  }

  if (btnModalPairBluetooth) {
    btnModalPairBluetooth.addEventListener("click", () => {
      closeMoreControllersModal();
      if (clientState.fullscreenLandscape) {
        setGamepadFullscreenLandscape(false);
      }
      switchSystemMode("games");
      switchGamesSubTab("bluetooth");
      scanBluetoothControllers(false);
    });
  }

  if (btnCopyPlayer2Link) {
    btnCopyPlayer2Link.addEventListener("click", async () => {
      vibrate(12);
      const urlText = player2WifiUrl
        ? player2WifiUrl.textContent
        : `${window.location.origin}/?mode=games&player=2&skin=snes&fullscreen=1`;
      try {
        await navigator.clipboard.writeText(urlText);
        btnCopyPlayer2Link.textContent = "✅ Player 2 Link Copied!";
        setTimeout(() => {
          btnCopyPlayer2Link.textContent = "📋 Copy Player 2 Link";
        }, 1800);
      } catch (_) {}
    });
  }

  if (btnSwitchThisPhoneToP2) {
    btnSwitchThisPhoneToP2.addEventListener("click", () => {
      vibrate(15);
      applyControllerSkin(clientState.activeSkin, 2, "Controller 2 (Multiplayer)", true);
      if (controllersModalBanner) {
        controllersModalBanner.innerHTML =
          "🎮 This device is now configured as <strong>Controller 2 (Player 2)</strong>!";
      }
    });
  }

  function switchGamesSubTab(subTab) {
    vibrate(12);
    clientState.gamesSubTab = subTab;
    if (subTab !== "pad" && clientState.fullscreenLandscape) {
      setGamepadFullscreenLandscape(false);
    }
    if (tabGamesPad) tabGamesPad.classList.toggle("active", subTab === "pad");
    if (tabGamesConsoles) tabGamesConsoles.classList.toggle("active", subTab === "consoles");
    if (tabGamesBluetooth) tabGamesBluetooth.classList.toggle("active", subTab === "bluetooth");

    if (gamesPadContainer) gamesPadContainer.classList.toggle("active", subTab === "pad");
    if (gamesConsolesContainer) gamesConsolesContainer.classList.toggle("active", subTab === "consoles");
    if (gamesBluetoothContainer) gamesBluetoothContainer.classList.toggle("active", subTab === "bluetooth");

    if (subTab === "consoles") {
      loadGamesStatus();
    } else if (subTab === "bluetooth") {
      loadBluetoothStatus();
    }
  }

  if (tabGamesPad) tabGamesPad.addEventListener("click", () => switchGamesSubTab("pad"));
  if (tabGamesConsoles) tabGamesConsoles.addEventListener("click", () => switchGamesSubTab("consoles"));
  if (tabGamesBluetooth) tabGamesBluetooth.addEventListener("click", () => switchGamesSubTab("bluetooth"));

  if (btnQuickBt) {
    btnQuickBt.addEventListener("click", () => {
      switchSystemMode("games");
      switchGamesSubTab("bluetooth");
      scanBluetoothControllers(false);
    });
  }

  if (btnPhysicalGamepadStatus) {
    btnPhysicalGamepadStatus.addEventListener("click", () => {
      if (clientState.fullscreenLandscape) {
        setGamepadFullscreenLandscape(false);
      }
      switchGamesSubTab("bluetooth");
      loadBluetoothStatus();
    });
  }

  if (btnTurboToggle) {
    btnTurboToggle.addEventListener("click", () => {
      vibrate(15);
      clientState.turboEnabled = !clientState.turboEnabled;
      btnTurboToggle.classList.toggle("active", clientState.turboEnabled);
      btnTurboToggle.textContent = clientState.turboEnabled ? "⚡ TURBO: ON" : "⚡ TURBO: OFF";
    });
  }

  // Virtual Gamepad Buttons (SNES / Arcade / Mega Drive — Independent Per-Button Multitouch)
  const gamepadTimers = new Map();

  function stopGamepadButton(timerKey, btnEl) {
    if (btnEl) btnEl.classList.remove("pressed");
    const timerObj = gamepadTimers.get(timerKey);
    if (timerObj) {
      if (timerObj.hold) clearTimeout(timerObj.hold);
      if (timerObj.interval) clearInterval(timerObj.interval);
      gamepadTimers.delete(timerKey);
    }
  }

  document.querySelectorAll("[data-gamepad]").forEach((btn, idx) => {
    const key = btn.getAttribute("data-gamepad");
    const timerKey = `${key}_${idx}`;
    const isDir = ["UP", "DOWN", "LEFT", "RIGHT"].includes(key);
    const isAction = ["BTN_A", "BTN_B", "BTN_C", "BTN_X", "BTN_Y", "BTN_Z", "BTN_L", "BTN_R"].includes(key);

    btn.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      vibrate(10);
      btn.classList.add("pressed");
      sendGamepadCommand(key);
      stopGamepadButton(timerKey, btn);
      btn.classList.add("pressed");

      if (isDir || (isAction && clientState.turboEnabled)) {
        const delay = clientState.turboEnabled && isAction ? 90 : 220;
        const rate = clientState.turboEnabled && isAction ? 65 : 95;
        const hold = setTimeout(() => {
          const interval = setInterval(() => {
            sendGamepadCommand(key);
          }, rate);
          gamepadTimers.set(timerKey, { hold: null, interval });
        }, delay);
        gamepadTimers.set(timerKey, { hold, interval: null });
      }
    });

    btn.addEventListener("pointerup", () => stopGamepadButton(timerKey, btn));
    btn.addEventListener("pointercancel", () => stopGamepadButton(timerKey, btn));
    btn.addEventListener("pointerleave", () => stopGamepadButton(timerKey, btn));
  });

  // Quick console launcher shortcuts at the bottom of the Gamepad
  document.querySelectorAll("[data-emu-launch]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const emuId = btn.getAttribute("data-emu-launch");
      if (emuId === "snes9x") applyControllerSkin("snes", clientState.activePlayer, "", false);
      else if (emuId === "neoemu" || emuId === "mame4droid")
        applyControllerSkin("mame", clientState.activePlayer, "", false);
      else if (emuId === "mdemu")
        applyControllerSkin("megadrive", clientState.activePlayer, "", false);
      launchEmulator(emuId);
    });
  });

  // Web Gamepad API Bridge (Forwards Bluetooth gamepads connected to phone/PC to Android)
  const prevGamepadState = {};

  function pollWebGamepads() {
    if (!navigator.getGamepads) return;
    const pads = navigator.getGamepads();
    let activePad = null;
    for (let i = 0; i < pads.length; i++) {
      if (pads[i] && pads[i].connected) {
        activePad = pads[i];
        break;
      }
    }

    if (activePad) {
      if (btnPhysicalGamepadStatus && !btnPhysicalGamepadStatus.classList.contains("connected")) {
        btnPhysicalGamepadStatus.classList.add("connected");
        btnPhysicalGamepadStatus.textContent = "🟢 BT Controller Active";
      }
      // Standard W3C Gamepad -> Android Keycodes (SNES / MAME)
      const mapButtons = [
        [0, "BTN_B"],
        [1, "BTN_A"],
        [2, "BTN_Y"],
        [3, "BTN_X"],
        [4, "BTN_L"],
        [5, "BTN_R"],
        [6, "BTN_L2"],
        [7, "BTN_R2"],
        [8, "BTN_SELECT"],
        [9, "BTN_START"],
        [12, "UP"],
        [13, "DOWN"],
        [14, "LEFT"],
        [15, "RIGHT"],
      ];
      mapButtons.forEach(([idx, keyName]) => {
        const pressed = Boolean(activePad.buttons[idx] && activePad.buttons[idx].pressed);
        if (pressed && !prevGamepadState[keyName]) {
          sendGamepadCommand(keyName);
        }
        prevGamepadState[keyName] = pressed;
      });

      // Left Analog Stick -> D-Pad
      const axX = activePad.axes[0] || 0;
      const axY = activePad.axes[1] || 0;
      const stickDirs = [
        ["STICK_LEFT", axX < -0.55, "LEFT"],
        ["STICK_RIGHT", axX > 0.55, "RIGHT"],
        ["STICK_UP", axY < -0.55, "UP"],
        ["STICK_DOWN", axY > 0.55, "DOWN"],
      ];
      stickDirs.forEach(([stateKey, active, keyName]) => {
        if (active && !prevGamepadState[stateKey]) {
          sendGamepadCommand(keyName);
        }
        prevGamepadState[stateKey] = active;
      });
    }
    requestAnimationFrame(pollWebGamepads);
  }

  window.addEventListener("gamepadconnected", (e) => {
    if (btnPhysicalGamepadStatus) {
      btnPhysicalGamepadStatus.classList.add("connected");
      btnPhysicalGamepadStatus.textContent = `🟢 ${e.gamepad.id.slice(0, 18)}`;
    }
  });
  requestAnimationFrame(pollWebGamepads);

  // ==================== TAB 2 & HUD DRAWER: VISUAL GAME COVER GALLERY ====================
  let cachedRomsList = [];
  let activeRomFilter = "all";
  let romSearchQuery = "";
  const btnInstallGamePack = document.getElementById("btnInstallGamePack");
  const romCountBadge = document.getElementById("romCountBadge");
  const romSearchInput = document.getElementById("romSearchInput");
  const btnClearRomSearch = document.getElementById("btnClearRomSearch");
  const btnTopChooseGame = document.getElementById("btnTopChooseGame");
  const activeConsoleBadgeBtn = document.getElementById("activeConsoleBadgeBtn");
  const hudGameDrawer = document.getElementById("hudGameDrawer");
  const btnCloseHudGameDrawer = document.getElementById("btnCloseHudGameDrawer");
  const hudRomSearchInput = document.getElementById("hudRomSearchInput");
  const hudRomCoverGrid = document.getElementById("hudRomCoverGrid");

  function openHudGameDrawer() {
    vibrate(14);
    if (!hudGameDrawer) {
      switchGamesSubTab("consoles");
      return;
    }
    hudGameDrawer.classList.remove("hidden");
    if (cachedRomsList.length === 0) {
      loadGamesStatus();
    } else {
      renderRomsList(cachedRomsList);
    }
  }

  function closeHudGameDrawer() {
    if (hudGameDrawer) {
      hudGameDrawer.classList.add("hidden");
    }
  }

  if (btnTopChooseGame) {
    btnTopChooseGame.addEventListener("click", openHudGameDrawer);
  }
  if (activeConsoleBadgeBtn) {
    activeConsoleBadgeBtn.addEventListener("click", openHudGameDrawer);
  }
  if (btnCloseHudGameDrawer) {
    btnCloseHudGameDrawer.addEventListener("click", closeHudGameDrawer);
  }
  if (hudGameDrawer) {
    hudGameDrawer.addEventListener("click", (e) => {
      if (e.target === hudGameDrawer) {
        closeHudGameDrawer();
      }
    });
  }

  function syncRomSearchInputs(newVal, sourceEl) {
    romSearchQuery = String(newVal || "").trim();
    if (romSearchInput && sourceEl !== romSearchInput) {
      romSearchInput.value = newVal;
    }
    if (hudRomSearchInput && sourceEl !== hudRomSearchInput) {
      hudRomSearchInput.value = newVal;
    }
    if (btnClearRomSearch) {
      btnClearRomSearch.classList.toggle("hidden", !romSearchQuery);
    }
    renderRomsList(cachedRomsList);
  }

  if (romSearchInput) {
    romSearchInput.addEventListener("input", () => {
      syncRomSearchInputs(romSearchInput.value, romSearchInput);
    });
  }
  if (hudRomSearchInput) {
    hudRomSearchInput.addEventListener("input", () => {
      syncRomSearchInputs(hudRomSearchInput.value, hudRomSearchInput);
    });
  }
  if (btnClearRomSearch) {
    btnClearRomSearch.addEventListener("click", () => {
      vibrate(10);
      syncRomSearchInputs("", null);
    });
  }

  function buildFallbackCoverUrl(rom) {
    if (rom.cover_url) return rom.cover_url;
    const title = escapeHtml(rom.title || rom.filename || "Retro Game");
    const badge = escapeHtml(
      rom.console_badge || (rom.system === "mame" ? "NEOGEO" : rom.system === "snes" ? "SNES" : "MEGA DRIVE")
    );
    const genre = escapeHtml(rom.genre || "Arcade / Retro");
    const accent = rom.accent_color || "#38bdf8";
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 480" width="360" height="480"><rect width="360" height="480" rx="22" fill="#0f172a"/><rect x="14" y="14" width="128" height="32" rx="9" fill="#090d16" stroke="${accent}" stroke-width="2"/><text x="78" y="35" text-anchor="middle" fill="#fff" font-family="sans-serif" font-weight="900" font-size="14">${badge}</text><text x="180" y="220" text-anchor="middle" fill="#f8fafc" font-family="sans-serif" font-weight="900" font-size="24">${title.slice(0, 20)}</text><text x="180" y="420" text-anchor="middle" fill="${accent}" font-family="sans-serif" font-weight="700" font-size="15">${genre}</text></svg>`;
    return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  }

  function updateRomFilterCounts(roms) {
    const list = Array.isArray(roms) ? roms : [];
    const totalCount = list.length;
    const counts = {
      all: totalCount,
      mame: list.filter((r) => r.system === "mame").length,
      snes: list.filter((r) => r.system === "snes").length,
      megadrive: list.filter((r) => r.system === "megadrive").length,
    };
    if (romCountBadge) {
      romCountBadge.textContent = String(totalCount);
    }
    const labels = {
      all: `🔥 All (${counts.all})`,
      mame: `🕹️ NeoGeo / Arcade (${counts.mame})`,
      snes: `🍄 Super Nintendo (${counts.snes})`,
      megadrive: `🦔 Mega Drive (${counts.megadrive})`,
    };
    document.querySelectorAll("[data-rom-filter]").forEach((btn) => {
      const f = btn.getAttribute("data-rom-filter") || "all";
      if (labels[f]) {
        btn.textContent = labels[f];
      }
      btn.classList.toggle("active", f === activeRomFilter);
    });
  }

  async function loadGamesStatus() {
    try {
      const res = await fetch("/api/games/status");
      const data = await res.json();
      cachedRomsList = data.roms || [];
      updateRomFilterCounts(cachedRomsList);
      renderEmulatorsList(data.emulators || []);
      renderRomsList(cachedRomsList);
    } catch (_) {
      if (gamesStatusBanner) {
        gamesStatusBanner.textContent = "Error loading game catalog.";
      }
    }
  }

  document.querySelectorAll("[data-rom-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      vibrate(10);
      activeRomFilter = btn.getAttribute("data-rom-filter") || "all";
      document.querySelectorAll("[data-rom-filter]").forEach((b) => {
        b.classList.toggle("active", b.getAttribute("data-rom-filter") === activeRomFilter);
      });
      renderRomsList(cachedRomsList);
    });
  });

  if (btnInstallGamePack) {
    btnInstallGamePack.addEventListener("click", async () => {
      vibrate(18);
      btnInstallGamePack.disabled = true;
      btnInstallGamePack.textContent = "⏳ Downloading & Syncing Game Pack...";
      if (gamesStatusBanner) {
        gamesStatusBanner.innerHTML =
          "⏳ Downloading Game Pack (SNES, Arcade/NeoGeo, and Mega Drive) and syncing to <code>/sdcard/ROMs</code>...";
      }
      try {
        const res = await fetch("/api/games/install-pack", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pack_id: "all" }),
        });
        const data = await res.json();
        if (gamesStatusBanner && data.message) {
          gamesStatusBanner.innerHTML = data.message;
        }
        await loadGamesStatus();
      } catch (_) {
        if (gamesStatusBanner) {
          gamesStatusBanner.textContent = "Error installing game pack.";
        }
      } finally {
        btnInstallGamePack.disabled = false;
        btnInstallGamePack.textContent = "📦 Sync Full Game Pack";
      }
    });
  }

  async function launchRomOnPhone(system, filename) {
    vibrate(18);
    closeHudGameDrawer();
    const matchedRom = cachedRomsList.find(
      (r) => r.system === system && r.filename === filename
    );
    if (system && CONTROLLER_SKINS_META[system]) {
      applyControllerSkin(system, clientState.activePlayer, "", false);
    }
    if (activeConsoleLabel) {
      const immediateTitle = (matchedRom && matchedRom.title) || filename;
      const immediateBadge =
        (matchedRom && matchedRom.console_badge) || system.toUpperCase();
      activeConsoleLabel.textContent = `${immediateTitle} (${immediateBadge})`;
    }
    switchGamesSubTab("pad");
    try {
      const res = await fetch("/api/games/launch-rom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ system, filename }),
      });
      const data = await res.json();
      if (activeConsoleLabel && data.title) {
        const sysBadge =
          data.console_badge ||
          (data.emulator && data.emulator.system) ||
          system.toUpperCase();
        activeConsoleLabel.textContent = `${data.title} (${sysBadge})`;
      }
      if (gamesStatusBanner && data.message) {
        gamesStatusBanner.innerHTML = data.message;
      }
    } catch (_) {}
  }

  async function launchEmulator(emuId) {
    vibrate(18);
    try {
      const res = await fetch("/api/games/launch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emulator_id: emuId }),
      });
      const data = await res.json();
      if (emuId && CONTROLLER_SKINS_META[emuId]) {
        applyControllerSkin(emuId, clientState.activePlayer, "", false);
      }
      if (data.emulator && activeConsoleLabel) {
        activeConsoleLabel.textContent = data.emulator.system;
      }
      if (gamesStatusBanner && data.message) {
        gamesStatusBanner.innerHTML = data.message;
      }
      switchGamesSubTab("pad");
    } catch (_) {}
  }

  async function installEmulator(emuId, btnEl) {
    vibrate(18);
    if (btnEl) {
      btnEl.disabled = true;
      btnEl.textContent = "⏳ Downloading & Installing...";
    }
    if (gamesStatusBanner) {
      gamesStatusBanner.innerHTML =
        "⏳ Downloading official APK from GitHub and installing on Redmi Note 8 Pro via ADB...";
    }
    try {
      const res = await fetch("/api/games/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emulator_id: emuId }),
      });
      const data = await res.json();
      if (gamesStatusBanner) {
        gamesStatusBanner.innerHTML = data.message || "Process complete!";
      }
      await loadGamesStatus();
    } catch (_) {
      if (gamesStatusBanner) {
        gamesStatusBanner.textContent = "Error installing emulator.";
      }
    }
  }

  function renderEmulatorsList(emulators) {
    if (!emulatorsList) return;
    emulatorsList.innerHTML = "";
    emulators.forEach((emu) => {
      const card = document.createElement("div");
      card.className = "emu-card";
      card.innerHTML = `
        <div class="emu-card-top">
          <div class="emu-card-title-group">
            <span class="emu-icon">${emu.icon}</span>
            <div>
              <div class="emu-name">${emu.name}</div>
              <div class="emu-meta">${emu.description}</div>
            </div>
          </div>
          <span class="emu-badge ${emu.installed ? "" : "not-installed"}">
            ${emu.installed ? "Installed ✅" : "Available"}
          </span>
        </div>
        <div class="emu-card-actions">
          ${
            emu.installed
              ? `<button type="button" class="emu-btn play" data-action="launch">▶ Launch Console on TV</button>`
              : `<button type="button" class="emu-btn install" data-action="install">⬇️ Install on Phone (1-Click)</button>`
          }
        </div>
      `;
      const actionBtn = card.querySelector("button[data-action]");
      if (actionBtn) {
        actionBtn.addEventListener("click", () => {
          if (emu.installed) {
            launchEmulator(emu.id);
          } else {
            installEmulator(emu.id, actionBtn);
          }
        });
      }
      emulatorsList.appendChild(card);
    });
  }

  function createRomCoverCardElement(rom, isCompact = false) {
    const card = document.createElement("div");
    card.className = "rom-cover-card";
    card.setAttribute("data-rom-system", rom.system);
    card.setAttribute("data-rom-filename", rom.filename);

    const displayTitle = escapeHtml(rom.title || rom.filename);
    const displaySub = escapeHtml(
      rom.subtitle ||
        (rom.system === "mame"
          ? "SNK NeoGeo • Arcade"
          : rom.system === "snes"
          ? "Super Nintendo • 16-Bit"
          : "Sega Mega Drive • 16-Bit")
    );
    const displayGenre = escapeHtml(rom.genre || "Arcade / Retro");
    const coverSrc = buildFallbackCoverUrl(rom);

    card.innerHTML = `
      <div class="rom-cover-art-wrap" data-play-trigger="cover" title="Tap to play ${displayTitle} on TV">
        <img class="rom-cover-img" src="${coverSrc}" alt="${displayTitle}" loading="lazy" />
        <div class="rom-cover-play-overlay">
          <span class="rom-cover-play-badge">▶ PLAY ON TV</span>
        </div>
      </div>
      <div class="rom-cover-body">
        <div class="rom-cover-title" title="${displayTitle}">${displayTitle}</div>
        <div class="rom-cover-subtitle">${displaySub}</div>
        <div class="rom-cover-genre-row">
          <span class="rom-cover-genre-tag">${displayGenre}</span>
        </div>
      </div>
      <div class="rom-cover-actions">
        <button type="button" class="rom-play-primary-btn" data-mode="android">
          ▶ Play Now
        </button>
        ${
          !isCompact && rom.web_url
            ? `<button type="button" class="rom-play-web-btn" data-mode="web" title="Play in Browser (EmulatorJS)">🌐</button>`
            : ""
        }
      </div>
    `;

    const coverWrap = card.querySelector('[data-play-trigger="cover"]');
    if (coverWrap) {
      coverWrap.addEventListener("click", () => {
        launchRomOnPhone(rom.system, rom.filename);
      });
    }
    const btnAndroid = card.querySelector('[data-mode="android"]');
    if (btnAndroid) {
      btnAndroid.addEventListener("click", () => {
        launchRomOnPhone(rom.system, rom.filename);
      });
    }
    const btnWeb = card.querySelector('[data-mode="web"]');
    if (btnWeb && rom.web_url) {
      btnWeb.addEventListener("click", (e) => {
        e.stopPropagation();
        openWebEmulatorJS(rom.system, rom.filename, rom.web_url);
      });
    }
    return card;
  }

  function renderRomsList(roms) {
    const q = romSearchQuery.toLowerCase();
    let filtered = Array.isArray(roms)
      ? roms.filter((r) => {
          if (r.is_bios) return false;
          if (activeRomFilter !== "all" && r.system !== activeRomFilter) return false;
          if (!q) return true;
          const hay = `${r.title || ""} ${r.subtitle || ""} ${r.genre || ""} ${r.console_badge || ""} ${
            r.filename || ""
          }`.toLowerCase();
          return hay.includes(q);
        })
      : [];

    if (activeRomFilter === "all" && !q && filtered.length > 0) {
      const priorityTitles = [
        "Metal Slug",
        "Mega Family Bros",
        "Bare Knuckle Princess",
        "The King of Fighters '97",
        "Super Boss Gaiden",
        "Cave Story MD",
      ];
      const bySystem = {
        snes: filtered.filter((r) => r.system === "snes"),
        mame: filtered.filter((r) => r.system === "mame"),
        megadrive: filtered.filter((r) => r.system === "megadrive"),
        other: filtered.filter((r) => !["snes", "mame", "megadrive"].includes(r.system)),
      };
      const sortFeaturedFirst = (arr) =>
        arr.slice().sort((a, b) => {
          const ia = priorityTitles.indexOf(a.title);
          const ib = priorityTitles.indexOf(b.title);
          if (ia !== -1 && ib !== -1) return ia - ib;
          if (ia !== -1) return -1;
          if (ib !== -1) return 1;
          return String(a.title || "").localeCompare(String(b.title || ""));
        });
      const sList = sortFeaturedFirst(bySystem.snes);
      const mList = sortFeaturedFirst(bySystem.mame);
      const dList = sortFeaturedFirst(bySystem.megadrive);
      const oList = sortFeaturedFirst(bySystem.other);
      const interleaved = [];
      const maxLen = Math.max(sList.length, mList.length, dList.length);
      for (let i = 0; i < maxLen; i++) {
        if (i < sList.length) interleaved.push(sList[i]);
        if (i < mList.length) interleaved.push(mList[i]);
        if (i < dList.length) interleaved.push(dList[i]);
      }
      if (oList.length > 0) {
        interleaved.push(...oList);
      }
      filtered = interleaved;
    }

    const emptyHtml = `
      <div class="projector-empty" style="grid-column: 1 / -1;">
        No games found for this filter/search.
      </div>
    `;

    if (romListContainer) {
      romListContainer.innerHTML = "";
      if (filtered.length === 0) {
        romListContainer.innerHTML = emptyHtml;
      } else {
        filtered.forEach((rom) => {
          romListContainer.appendChild(createRomCoverCardElement(rom, false));
        });
      }
    }

    if (hudRomCoverGrid) {
      hudRomCoverGrid.innerHTML = "";
      if (filtered.length === 0) {
        hudRomCoverGrid.innerHTML = emptyHtml;
      } else {
        filtered.forEach((rom) => {
          hudRomCoverGrid.appendChild(createRomCoverCardElement(rom, true));
        });
      }
    }
  }

  // Preload cover catalog in background for instant opening
  setTimeout(() => {
    loadGamesStatus();
  }, 450);

  if (btnPickRomFile && romFileInput) {
    btnPickRomFile.addEventListener("click", () => {
      vibrate(12);
      romFileInput.click();
    });

    romFileInput.addEventListener("change", () => {
      const file = romFileInput.files && romFileInput.files[0];
      if (!file) return;
      const sys = romSystemSelect ? romSystemSelect.value : "snes";
      btnPickRomFile.disabled = true;
      btnPickRomFile.textContent = `⏳ Uploading ${file.name}...`;

      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const res = await fetch("/api/games/upload-rom", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              system: sys,
              filename: file.name,
              data_base64: String(reader.result || ""),
            }),
          });
          const data = await res.json();
          if (gamesStatusBanner && data.message) {
            gamesStatusBanner.innerHTML = data.message;
          }
          await loadGamesStatus();
        } catch (_) {
          if (gamesStatusBanner) {
            gamesStatusBanner.textContent = "Error uploading ROM file.";
          }
        } finally {
          btnPickRomFile.disabled = false;
          btnPickRomFile.textContent = "➕ Upload ROM File (.sfc / .zip)";
          romFileInput.value = "";
        }
      };
      reader.readAsDataURL(file);
    });
  }

  function openWebEmulatorJS(system, filename, romUrl) {
    if (!webEmulatorCard || !emulatorJsHost) return;
    webEmulatorCard.classList.remove("hidden");
    if (webEmuTitle) {
      webEmuTitle.textContent = `🌐 EmulatorJS: ${filename}`;
    }
    const core = system === "snes" ? "snes" : system === "megadrive" ? "segaMD" : "arcade";
    const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>html,body,#game{margin:0;padding:0;width:100%;height:100%;background:#000;overflow:hidden;}</style></head>
<body>
  <div id="game"></div>
  <script>
    EJS_player = "#game";
    EJS_core = "${core}";
    EJS_gameUrl = "${romUrl}";
    EJS_pathtodata = "https://cdn.emulatorjs.org/stable/data/";
    EJS_startOnLoaded = true;
  </script>
  <script src="https://cdn.emulatorjs.org/stable/data/loader.js"></script>
</body>
</html>`;
    emulatorJsHost.innerHTML = "";
    const iframe = document.createElement("iframe");
    iframe.style.width = "100%";
    iframe.style.height = "100%";
    iframe.style.border = "none";
    iframe.srcdoc = html;
    emulatorJsHost.appendChild(iframe);
  }

  if (btnCloseWebEmu) {
    btnCloseWebEmu.addEventListener("click", () => {
      if (webEmulatorCard) webEmulatorCard.classList.add("hidden");
      if (emulatorJsHost) emulatorJsHost.innerHTML = "";
    });
  }

  // ==================== TAB 3: BLUETOOTH CONTROLLER MANAGER ====================
  function renderBluetoothDevices(data) {
    if (!btDevicesList) return;
    btDevicesList.innerHTML = "";

    const activePads = data.active_gamepads || [];
    if (btActiveGamepadsBox) {
      if (activePads.length > 0) {
        btActiveGamepadsBox.classList.remove("hidden");
        btActiveGamepadsBox.innerHTML = `🎮 <strong>Active Gamepad on Android:</strong> ${activePads.join(", ")}`;
        if (btnPhysicalGamepadStatus) {
          btnPhysicalGamepadStatus.classList.add("connected");
          btnPhysicalGamepadStatus.textContent = `🟢 ${activePads[0].slice(0, 18)}`;
        }
      } else {
        btActiveGamepadsBox.classList.add("hidden");
      }
    }

    const devices = data.devices || [];
    if (devices.length === 0) {
      btDevicesList.innerHTML = `
        <div class="projector-empty">
          No Bluetooth controllers visible yet.<br/>
          Turn on your controller in <strong>pairing mode</strong> and tap <strong>🔍 Scan Nearby Bluetooth Controllers</strong>.
        </div>
      `;
      return;
    }

    devices.forEach((dev) => {
      const card = document.createElement("div");
      card.className = "projector-device-card";
      const icon = dev.is_group ? "📂" : dev.bonded ? "🎮" : "🔵";
      const btnLabel = dev.is_group ? "Open List" : dev.bonded ? "Connect" : "Pair";
      card.innerHTML = `
        <div class="projector-device-info">
          <span class="projector-device-name">${icon} ${dev.name}</span>
          <span class="projector-device-meta">${dev.status || "Bluetooth"} • ${dev.address || ""}</span>
        </div>
        <button type="button" class="projector-connect-btn">${btnLabel}</button>
      `;
      const pairBtn = card.querySelector(".projector-connect-btn");
      pairBtn.addEventListener("click", async () => {
        vibrate(15);
        pairBtn.disabled = true;
        pairBtn.textContent = "Please wait...";
        try {
          const res = await fetch("/api/bluetooth/pair", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target: dev.name }),
          });
          const resData = await res.json();
          if (btStatusBanner && resData.message) {
            btStatusBanner.innerHTML = resData.message;
          }
          if (resData.devices) {
            renderBluetoothDevices(resData);
          }
        } catch (_) {
          if (btStatusBanner) {
            btStatusBanner.textContent = "Error pairing Bluetooth controller.";
          }
        } finally {
          pairBtn.disabled = false;
          pairBtn.textContent = btnLabel;
        }
      });
      btDevicesList.appendChild(card);
    });
  }

  async function loadBluetoothStatus() {
    try {
      const res = await fetch("/api/bluetooth/status");
      const data = await res.json();
      renderBluetoothDevices(data);
    } catch (_) {}
  }

  async function scanBluetoothControllers(openRare = false) {
    vibrate(18);
    if (btnScanBluetooth) {
      btnScanBluetooth.disabled = true;
      btnScanBluetooth.textContent = "⏳ Scanning Bluetooth Controllers on Phone...";
    }
    if (btStatusBanner) {
      btStatusBanner.innerHTML =
        "📡 Enabling Bluetooth on the Redmi Note 8 Pro and scanning for controllers in pairing mode...";
    }
    try {
      const res = await fetch("/api/bluetooth/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ open_rarely_used: openRare }),
      });
      const data = await res.json();
      if (btStatusBanner && data.message) {
        btStatusBanner.innerHTML = data.message;
      }
      renderBluetoothDevices(data);
    } catch (_) {
      if (btStatusBanner) {
        btStatusBanner.textContent = "Error scanning for Bluetooth controllers.";
      }
    } finally {
      if (btnScanBluetooth) {
        btnScanBluetooth.disabled = false;
        btnScanBluetooth.textContent = "🔍 Scan Nearby Bluetooth Controllers";
      }
    }
  }

  if (btnScanBluetooth) {
    btnScanBluetooth.addEventListener("click", () => scanBluetoothControllers(false));
  }
  if (btnOpenRareBluetooth) {
    btnOpenRareBluetooth.addEventListener("click", () => scanBluetoothControllers(true));
  }
  if (btnRefreshBluetooth) {
    btnRefreshBluetooth.addEventListener("click", () => {
      vibrate(12);
      loadBluetoothStatus();
    });
  }

  // ==================== SSH TERMINAL & WI-FI OTA UPDATE ====================
  const tabLinuxTrackpad = document.getElementById("tabLinuxTrackpad");
  const tabLinuxSsh = document.getElementById("tabLinuxSsh");
  const linuxTrackpadContainer = document.getElementById("linuxTrackpadContainer");
  const linuxSshContainer = document.getElementById("linuxSshContainer");
  const btnQuickSsh = document.getElementById("btnQuickSsh");
  const sshStatusBadge = document.getElementById("sshStatusBadge");
  const btnCopySshCmd = document.getElementById("btnCopySshCmd");
  const sshCommandDisplay = document.getElementById("sshCommandDisplay");
  const btnSyncWifiUpdate = document.getElementById("btnSyncWifiUpdate");
  const btnOpenLaptopSsh = document.getElementById("btnOpenLaptopSsh");
  const sshTargetSelect = document.getElementById("sshTargetSelect");
  const btnClearTerminal = document.getElementById("btnClearTerminal");
  const sshTerminalOutput = document.getElementById("sshTerminalOutput");
  const sshCommandInput = document.getElementById("sshCommandInput");
  const btnRunSshCommand = document.getElementById("btnRunSshCommand");

  let currentSshCmdText = "ssh -p 8022 termux@hybridbox.local";
  const sshHistory = [];
  let sshHistoryIdx = -1;

  function switchLinuxSubTab(sub) {
    vibrate(12);
    clientState.linuxSubTab = sub;
    if (tabLinuxTrackpad) tabLinuxTrackpad.classList.toggle("active", sub === "trackpad");
    if (tabLinuxSsh) tabLinuxSsh.classList.toggle("active", sub === "ssh");
    if (linuxTrackpadContainer) linuxTrackpadContainer.classList.toggle("active", sub === "trackpad");
    if (linuxSshContainer) linuxSshContainer.classList.toggle("active", sub === "ssh");
    if (sub === "ssh") {
      loadSshStatus();
      setTimeout(() => {
        if (sshCommandInput) sshCommandInput.focus();
      }, 80);
    }
  }

  if (tabLinuxTrackpad) tabLinuxTrackpad.addEventListener("click", () => switchLinuxSubTab("trackpad"));
  if (tabLinuxSsh) tabLinuxSsh.addEventListener("click", () => switchLinuxSubTab("ssh"));
  if (btnQuickSsh) {
    btnQuickSsh.addEventListener("click", () => {
      switchSystemMode("linux");
      switchLinuxSubTab("ssh");
    });
  }

  function appendTerminalLine(text, cls = "") {
    if (!sshTerminalOutput) return;
    const div = document.createElement("div");
    div.className = `term-line ${cls}`.trim();
    div.textContent = text;
    sshTerminalOutput.appendChild(div);
    sshTerminalOutput.scrollTop = sshTerminalOutput.scrollHeight;
  }

  async function loadSshStatus() {
    try {
      const res = await fetch("/api/ssh/status");
      const data = await res.json();
      if (data.ssh_command) {
        currentSshCmdText = data.ssh_command;
      }
      if (sshCommandDisplay) {
        sshCommandDisplay.textContent = `${data.ssh_alias || "ssh hybridbox"}   # or: ${data.ssh_command}`;
      }
      if (sshStatusBadge) {
        if (data.sshd_running) {
          sshStatusBadge.textContent = `🟢 Wi-Fi SSH Online (${data.phone_ip}:${data.ssh_port})`;
        } else {
          sshStatusBadge.textContent = `🟡 ADB + Termux Active (${data.phone_ip})`;
        }
      }
    } catch (_) {}
  }

  async function runSshTerminalCommand(rawCmd) {
    const cmd = (rawCmd !== undefined ? rawCmd : sshCommandInput ? sshCommandInput.value : "").trim();
    if (!cmd) return;
    vibrate(10);
    const target = sshTargetSelect ? sshTargetSelect.value : "android";
    const prefix = target === "host" ? "PS Laptop>" : "termux@hybridbox:~$";
    appendTerminalLine(`${prefix} ${cmd}`, "cmd");

    sshHistory.push(cmd);
    sshHistoryIdx = sshHistory.length;
    if (sshCommandInput && rawCmd === undefined) {
      sshCommandInput.value = "";
    }

    try {
      const res = await fetch("/api/ssh/exec", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: cmd, target }),
      });
      const data = await res.json();
      appendTerminalLine(data.output || "[No output]", data.ok ? "" : "err");
    } catch (err) {
      appendTerminalLine(`Terminal connection error: ${err}`, "err");
    }
  }

  if (btnRunSshCommand) {
    btnRunSshCommand.addEventListener("click", () => runSshTerminalCommand());
  }

  if (sshCommandInput) {
    sshCommandInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        runSshTerminalCommand();
      } else if (e.key === "ArrowUp") {
        if (sshHistory.length > 0 && sshHistoryIdx > 0) {
          sshHistoryIdx--;
          sshCommandInput.value = sshHistory[sshHistoryIdx];
        }
      } else if (e.key === "ArrowDown") {
        if (sshHistoryIdx < sshHistory.length - 1) {
          sshHistoryIdx++;
          sshCommandInput.value = sshHistory[sshHistoryIdx];
        } else {
          sshHistoryIdx = sshHistory.length;
          sshCommandInput.value = "";
        }
      }
    });
  }

  document.querySelectorAll("[data-ssh-cmd]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cmd = btn.getAttribute("data-ssh-cmd");
      if (cmd) runSshTerminalCommand(cmd);
    });
  });

  if (btnClearTerminal) {
    btnClearTerminal.addEventListener("click", () => {
      vibrate(10);
      if (sshTerminalOutput) sshTerminalOutput.innerHTML = "";
      appendTerminalLine("=== Terminal Cleared ===", "system");
    });
  }

  if (btnCopySshCmd) {
    btnCopySshCmd.addEventListener("click", async () => {
      vibrate(12);
      try {
        await navigator.clipboard.writeText(currentSshCmdText);
        btnCopySshCmd.textContent = "✅ Copied!";
        setTimeout(() => {
          btnCopySshCmd.textContent = "📋 Copy SSH Command";
        }, 1600);
      } catch (_) {}
    });
  }

  if (btnSyncWifiUpdate) {
    btnSyncWifiUpdate.addEventListener("click", async () => {
      vibrate(18);
      btnSyncWifiUpdate.disabled = true;
      const orig = btnSyncWifiUpdate.textContent;
      btnSyncWifiUpdate.textContent = "⏳ Syncing over Wi-Fi SSH...";
      appendTerminalLine("🔄 Starting OTA sync over Wi-Fi SSH (Laptop -> Redmi Note 8 Pro)...", "system");
      try {
        const res = await fetch("/api/ssh/sync-wifi", { method: "POST" });
        const data = await res.json();
        if (data.log) appendTerminalLine(data.log, "info");
        appendTerminalLine(data.message || "✅ Sync complete!", "cmd");
      } catch (_) {
        appendTerminalLine("❌ Failed to sync files over Wi-Fi.", "err");
      } finally {
        btnSyncWifiUpdate.disabled = false;
        btnSyncWifiUpdate.textContent = orig;
      }
    });
  }

  if (btnOpenLaptopSsh) {
    btnOpenLaptopSsh.addEventListener("click", async () => {
      vibrate(16);
      appendTerminalLine("💻 Opening native SSH Terminal window on your Laptop...", "system");
      try {
        const res = await fetch("/api/ssh/open-laptop", { method: "POST" });
        const data = await res.json();
        appendTerminalLine(data.message || "Window opened!", "cmd");
      } catch (_) {
        appendTerminalLine("Error opening SSH window on laptop.", "err");
      }
    });
  }

  // Bloqueia menu de contexto em toques longos
  window.addEventListener("contextmenu", (e) => e.preventDefault());

  // Registra Service Worker para instalação como PWA
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    });
  }

  // Inicialização de Preferências de Controle e Parâmetros de URL (Multiplayer / Fullscreen)
  function initControllerPreferencesAndUrl() {
    try {
      const saved = JSON.parse(localStorage.getItem("hybridbox_controller_pref") || "null");
      if (saved && saved.skin) {
        applyControllerSkin(saved.skin, saved.player || 1, saved.label || "", false, saved.controller_id || "");
      } else {
        applyControllerSkin("snes", 1, "", false);
      }
    } catch (_) {
      applyControllerSkin("snes", 1, "", false);
    }

    const params = new URLSearchParams(window.location.search);
    const urlMode = params.get("mode");
    const urlPlayer = params.get("player");
    const urlSkin = params.get("skin") || params.get("style");
    const urlFs = params.get("fullscreen");

    if (urlSkin || urlPlayer) {
      applyControllerSkin(
        urlSkin || clientState.activeSkin,
        urlPlayer ? Number(urlPlayer) : clientState.activePlayer,
        "",
        true
      );
    }
    if (urlMode && ["tv", "linux", "games"].includes(urlMode)) {
      clientState.mode = urlMode;
      clientState.urlModeLocked = true;
    }
    if (urlFs === "1" || urlFs === "true") {
      clientState.mode = "games";
      clientState.urlModeLocked = true;
      setGamepadFullscreenLandscape(true);
    }
  }

  // Inicialização
  initControllerPreferencesAndUrl();
  renderModeUI();
  loadInitialStatus();
  loadControllersConfig();
  loadGamesStatus();
  connectWebSocket();
})();
