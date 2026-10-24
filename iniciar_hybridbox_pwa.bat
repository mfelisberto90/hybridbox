@echo off
setlocal EnableDelayedExpansion
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
set "PROJECT_DIR=%~dp0"
if "!PROJECT_DIR:~-1!"=="\" set "PROJECT_DIR=!PROJECT_DIR:~0,-1!"

:: Auto-detect Python interpreter (.venv, .venv314, uv cpython, or system python)
set "PY_EXE=python"
if exist "!PROJECT_DIR!\.venv\Scripts\python.exe" (
    set "PY_EXE=!PROJECT_DIR!\.venv\Scripts\python.exe"
    set "PYTHONPATH=!PROJECT_DIR!\.venv\Lib\site-packages;!PROJECT_DIR!"
) else if exist "!PROJECT_DIR!\.venv314\Scripts\python.exe" (
    set "PY_EXE=!PROJECT_DIR!\.venv314\Scripts\python.exe"
    set "PYTHONPATH=!PROJECT_DIR!\.venv314\Lib\site-packages;!PROJECT_DIR!"
) else if exist "%APPDATA%\uv\python\cpython-3.14.6-windows-x86_64-none\python.exe" (
    set "PY_EXE=%APPDATA%\uv\python\cpython-3.14.6-windows-x86_64-none\python.exe"
    set "PYTHONPATH=!PROJECT_DIR!\.venv314\Lib\site-packages;!PROJECT_DIR!"
) else (
    set "PYTHONPATH=!PROJECT_DIR!"
)

"!PY_EXE!" -c "import fastapi, uvicorn, websockets" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    call "!PROJECT_DIR!\install.bat" --no-start
    if exist "!PROJECT_DIR!\.venv\Scripts\python.exe" (
        set "PY_EXE=!PROJECT_DIR!\.venv\Scripts\python.exe"
        set "PYTHONPATH=!PROJECT_DIR!\.venv\Lib\site-packages;!PROJECT_DIR!"
    )
)

start /b "" "!PY_EXE!" "!PROJECT_DIR!\scripts\pc_usb_autorevive.py"
start "" "http://localhost:8080"
:loop
"!PY_EXE!" -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
timeout /t 2 /nobreak >nul
goto loop
