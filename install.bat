@echo off
setlocal EnableDelayedExpansion
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
set "PROJECT_DIR=%~dp0"
if "!PROJECT_DIR:~-1!"=="\" set "PROJECT_DIR=!PROJECT_DIR:~0,-1!"

echo ==============================================================================
echo   [HYBRIDBOX] ONE-CLICK INSTALLER ^& ANDROID CONSOLE PROVISIONER [WINDOWS]
echo ==============================================================================
echo.

echo [1/4] Preparing Python environment and dependencies...
set "PY_EXE="
set "PYTHONPATH=!PROJECT_DIR!"

if exist "!PROJECT_DIR!\.venv\Scripts\python.exe" (
    set "PY_EXE=!PROJECT_DIR!\.venv\Scripts\python.exe"
    set "PYTHONPATH=!PROJECT_DIR!\.venv\Lib\site-packages;!PROJECT_DIR!"
    goto :check_deps
)

if exist "!PROJECT_DIR!\.venv314\Scripts\python.exe" (
    set "PY_EXE=!PROJECT_DIR!\.venv314\Scripts\python.exe"
    set "PYTHONPATH=!PROJECT_DIR!\.venv314\Lib\site-packages;!PROJECT_DIR!"
    goto :check_deps
)

where uv >nul 2>&1
if not errorlevel 1 (
    echo     - Creating virtual environment via uv...
    uv venv "!PROJECT_DIR!\.venv" >nul 2>&1
    if exist "!PROJECT_DIR!\.venv\Scripts\python.exe" (
        set "PY_EXE=!PROJECT_DIR!\.venv\Scripts\python.exe"
        set "PYTHONPATH=!PROJECT_DIR!\.venv\Lib\site-packages;!PROJECT_DIR!"
        goto :check_deps
    )
)

set "SYS_PY="
if exist "%APPDATA%\uv\python\cpython-3.14.6-windows-x86_64-none\python.exe" set "SYS_PY=%APPDATA%\uv\python\cpython-3.14.6-windows-x86_64-none\python.exe"
if not "!SYS_PY!"=="" goto :create_venv

for /f "delims=" %%P in ('where python 2^>nul') do call :try_py "%%~fP"
if not "!SYS_PY!"=="" goto :create_venv

for /f "delims=" %%P in ('where py 2^>nul') do call :try_py "%%~fP"
if not "!SYS_PY!"=="" goto :create_venv

echo [!] Python 3.10+ was not found in PATH.
echo     Please install Python from https://www.python.org/downloads/ and run install.bat again.
if /i not "%~1"=="--check" if /i not "%~1"=="--no-start" pause
exit /b 1

:try_py
if not "!SYS_PY!"=="" exit /b 0
"%~1" -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if not errorlevel 1 set "SYS_PY=%~1"
exit /b 0

:create_venv
echo     - Creating virtual environment in .venv ...
"!SYS_PY!" -m venv "!PROJECT_DIR!\.venv" >nul 2>&1
if exist "!PROJECT_DIR!\.venv\Scripts\python.exe" (
    set "PY_EXE=!PROJECT_DIR!\.venv\Scripts\python.exe"
    set "PYTHONPATH=!PROJECT_DIR!\.venv\Lib\site-packages;!PROJECT_DIR!"
) else (
    set "PY_EXE=!SYS_PY!"
)

:check_deps
"!PY_EXE!" -c "import fastapi, uvicorn, websockets" >nul 2>&1
if not errorlevel 1 goto :deps_ok

echo     - Installing required packages from requirements.txt...
where uv >nul 2>&1
if not errorlevel 1 (
    uv pip install --python "!PY_EXE!" -r "!PROJECT_DIR!\requirements.txt"
    goto :verify_deps
)

"!PY_EXE!" -m ensurepip --upgrade >nul 2>&1
"!PY_EXE!" -m pip install --upgrade pip >nul 2>&1
"!PY_EXE!" -m pip install -r "!PROJECT_DIR!\requirements.txt"

:verify_deps
"!PY_EXE!" -c "import fastapi, uvicorn, websockets" >nul 2>&1
if errorlevel 1 (
    echo [!] Failed to verify Python dependencies [FastAPI + Uvicorn + WebSockets].
    if /i not "%~1"=="--check" if /i not "%~1"=="--no-start" pause
    exit /b 1
)

:deps_ok
echo     - Python dependencies verified [FastAPI + Uvicorn + WebSockets ready].

echo.
echo [2/4] Checking for connected Android device [USB ADB or Wi-Fi]...
"!PY_EXE!" "!PROJECT_DIR!\scripts\pc_usb_autorevive.py" --once

echo.
echo [3/4] Checking optional APK bundles [if device is connected over ADB]...
"!PY_EXE!" "!PROJECT_DIR!\scripts\pc_usb_autorevive.py" --install-apks

echo.
echo [4/4] Installation complete!
if /i "%~1"=="--no-start" exit /b 0
if /i "%~1"=="--check" exit /b 0
echo       Starting HybridBox Remote PWA Server on http://localhost:8080 ...
echo ==============================================================================
call "!PROJECT_DIR!\iniciar_hybridbox_pwa.bat"
