@echo off
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

set "PY_EXE=python"
if exist "%PROJECT_DIR%\.venv\Scripts\python.exe" (
    set "PY_EXE=%PROJECT_DIR%\.venv\Scripts\python.exe"
    set "PYTHONPATH=%PROJECT_DIR%\.venv\Lib\site-packages;%PROJECT_DIR%"
) else if exist "%PROJECT_DIR%\.venv314\Scripts\python.exe" (
    set "PY_EXE=%PROJECT_DIR%\.venv314\Scripts\python.exe"
    set "PYTHONPATH=%PROJECT_DIR%\.venv314\Lib\site-packages;%PROJECT_DIR%"
) else if exist "%APPDATA%\uv\python\cpython-3.14.6-windows-x86_64-none\python.exe" (
    set "PY_EXE=%APPDATA%\uv\python\cpython-3.14.6-windows-x86_64-none\python.exe"
    set "PYTHONPATH=%PROJECT_DIR%\.venv314\Lib\site-packages;%PROJECT_DIR%"
) else (
    set "PYTHONPATH=%PROJECT_DIR%"
)

for /f "tokens=1,2 delims=|" %%a in ('""%PY_EXE%" "%PROJECT_DIR%\scripts\pc_usb_autorevive.py" --print-target 2>nul"') do (
    set "PHONE_IP=%%a"
    set "SSH_USER=%%b"
)
if "%PHONE_IP%"=="" set "PHONE_IP=hybridbox.local"
if "%SSH_USER%"=="" set "SSH_USER=%HYBRIDBOX_SSH_USER%"
if "%SSH_USER%"=="" set "SSH_USER=termux"
title HybridBox - Wi-Fi Sync ^& SSH Terminal (%PHONE_IP%:8022)
echo ========================================================================
echo   HYBRIDBOX REMOTE PWA - WI-FI SYNC AND SSH TERMINAL
echo   Target: Android Device (%SSH_USER%@%PHONE_IP% - Port 8022)
echo ========================================================================
echo.
echo [1/2] Uploading updated files over Wi-Fi SSH (SCP)...
ssh -n -p 8022 -o BatchMode=yes -o ConnectTimeout=4 -o StrictHostKeyChecking=no %SSH_USER%@%PHONE_IP% "mkdir -p ~/hybridbox-remote-pwa" 2>nul
scp -P 8022 -o BatchMode=yes -o ConnectTimeout=6 -o StrictHostKeyChecking=no -r "%PROJECT_DIR%\backend" "%PROJECT_DIR%\frontend" "%PROJECT_DIR%\scripts" "%PROJECT_DIR%\tests" "%PROJECT_DIR%\requirements.txt" "%PROJECT_DIR%\README.md" "%PROJECT_DIR%\install.sh" "%PROJECT_DIR%\rescue_wifi.json" %SSH_USER%@%PHONE_IP%:~/hybridbox-remote-pwa/
ssh -n -p 8022 -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no %SSH_USER%@%PHONE_IP% "find ~/hybridbox-remote-pwa -name '__pycache__' -exec rm -rf {} + 2>/dev/null; sed -i 's/\r$//' ~/hybridbox-remote-pwa/scripts/*.sh ~/hybridbox-remote-pwa/scripts/hb-shell ~/hybridbox-remote-pwa/scripts/hb-sudo ~/hybridbox-remote-pwa/install.sh 2>/dev/null; chmod +x ~/hybridbox-remote-pwa/scripts/*.sh ~/hybridbox-remote-pwa/scripts/hb-shell ~/hybridbox-remote-pwa/scripts/hb-sudo ~/hybridbox-remote-pwa/install.sh 2>/dev/null; cp ~/hybridbox-remote-pwa/scripts/hb-shell /data/data/com.termux/files/usr/bin/hb-shell 2>/dev/null; cp ~/hybridbox-remote-pwa/scripts/hb-sudo /data/data/com.termux/files/usr/bin/sudo 2>/dev/null; chmod 755 /data/data/com.termux/files/usr/bin/hb-shell /data/data/com.termux/files/usr/bin/sudo 2>/dev/null; /data/data/com.termux/files/usr/bin/hb-shell 'cp /data/data/com.termux/files/home/hybridbox-remote-pwa/backend/hybridbox_bridge.jar /data/local/tmp/hybridbox_bridge.jar 2>/dev/null; cp /data/data/com.termux/files/home/hybridbox-remote-pwa/scripts/hb_system_watchdog.sh /data/local/tmp/hb_system_watchdog.sh 2>/dev/null; chmod 755 /data/local/tmp/hb_system_watchdog.sh 2>/dev/null' >/dev/null 2>&1 || true; KA=keep_awake.sh; UV=backend.main; APP=app; pkill -9 -f '[s]cripts/'$KA 2>/dev/null || true; pkill -9 -f '[u]vicorn.*'$UV:$APP 2>/dev/null || true; rm -f /data/data/com.termux/files/usr/tmp/hybridbox_keep_awake.pid; (cd ~/hybridbox-remote-pwa && nohup setsid /data/data/com.termux/files/usr/bin/python3 -m uvicorn $UV:$APP --host 0.0.0.0 --port 8080 --log-level warning </dev/null >>~/uvicorn.log 2>&1 & nohup setsid /data/data/com.termux/files/usr/bin/bash ~/hybridbox-remote-pwa/scripts/$KA </dev/null >/dev/null 2>&1 &) </dev/null >/dev/null 2>&1"
if /i "%~1"=="--sync-only" (
    echo [+] Wi-Fi sync and remote service restart completed!
    exit /b 0
)
echo.
echo [2/2] Wi-Fi sync complete! Opening interactive SSH Terminal...
echo (Type 'exit' when you want to close the SSH terminal)
echo.
ssh -p 8022 -o StrictHostKeyChecking=no %SSH_USER%@%PHONE_IP%
pause
