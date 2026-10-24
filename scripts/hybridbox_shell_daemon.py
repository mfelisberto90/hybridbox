#!/data/data/com.termux/files/usr/bin/python3
"""
Persistent uid=2000(shell) command bridge & Wi-Fi ADB watchdog on Redmi Note 8 Pro.
Runs in /data/local/tmp under u:r:shell:s0 so that unplugging the USB cable
never revokes shell-level permissions (uiautomator, input tap, dumpsys, settings, am).
"""
import os
import socket
import subprocess
import threading
import time

HOST = "127.0.0.1"
PORT = 5558


def watchdog_loop() -> None:
    """Keeps Wi-Fi ADB (port 5555) and stay_on_while_plugged_in active even after USB unplug."""
    while True:
        try:
            port_val = subprocess.check_output(
                ["/system/bin/getprop", "service.adb.tcp.port"], text=True
            ).strip()
            adbd_svc = subprocess.check_output(
                ["/system/bin/getprop", "init.svc.adbd"], text=True
            ).strip()
            if port_val != "5555" or adbd_svc != "running":
                subprocess.run(["/system/bin/setprop", "service.adb.tcp.port", "5555"])
                subprocess.run(["/system/bin/start", "adbd"])
        except Exception:
            pass
        time.sleep(10)


def handle_client(conn: socket.socket) -> None:
    try:
        conn.settimeout(15.0)
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n__END_CMD__\n" in data:
                break
        cmd = data.replace(b"\n__END_CMD__\n", b"").decode("utf-8", errors="ignore").strip()
        if cmd:
            env = os.environ.copy()
            env["PATH"] = "/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin"
            env["LD_LIBRARY_PATH"] = "/data/data/com.termux/files/usr/lib"
            res = subprocess.run(
                ["/system/bin/sh", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=14.0,
                env=env,
            )
            out = (res.stdout or "") + (res.stderr or "")
            conn.sendall(out.encode("utf-8", errors="ignore"))
    except Exception as exc:
        try:
            conn.sendall(f"ERR: {exc}\n".encode("utf-8"))
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main() -> None:
    t = threading.Thread(target=watchdog_loop, daemon=True)
    t.start()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(16)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle_client, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    main()
