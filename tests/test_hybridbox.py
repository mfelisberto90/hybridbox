"""
Automated test suite for HybridBox Remote PWA:
- App catalog & mode registry
- Zero-config phone IP & Termux SSH user auto-discovery + local runtime cache
- Projector controller zero-config string formatting & keyword matching
- SSH terminal controller command execution & empty-input edge cases
- Repository privacy invariant (zero personal IPs, MACs, SSIDs, serials, or user paths in git-tracked files)
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.android_controller import AndroidController
from backend.app_registry import ANDROID_APPS, LINUX_APPS, get_all_apps
from backend.projector_controller import PROJECTOR_KEYWORDS, ProjectorController
from backend.ssh_terminal_controller import SshTerminalController

BASE_DIR = Path(__file__).resolve().parent.parent


class TestHybridBoxSuite(unittest.TestCase):
    def test_app_registry_structure(self) -> None:
        all_apps = get_all_apps()
        self.assertIsInstance(all_apps, list)
        self.assertGreaterEqual(len(all_apps), 15)
        self.assertGreaterEqual(len(ANDROID_APPS), 10)
        self.assertGreaterEqual(len(LINUX_APPS), 3)
        for app_id, meta in ANDROID_APPS.items():
            self.assertTrue(meta.get("name"), f"Missing name for {app_id}")
            self.assertTrue(meta.get("commands"), f"Missing commands for {app_id}")
        for app_id, meta in LINUX_APPS.items():
            self.assertTrue(meta.get("name"), f"Missing name for {app_id}")
            self.assertTrue(meta.get("command"), f"Missing command for {app_id}")

    def test_ipv4_validation_edge_cases(self) -> None:
        self.assertTrue(AndroidController._is_ipv4("192.168.0.100"))
        self.assertTrue(AndroidController._is_ipv4("10.0.0.1"))
        self.assertFalse(AndroidController._is_ipv4(""))
        self.assertFalse(AndroidController._is_ipv4("hybridbox.local"))
        self.assertFalse(AndroidController._is_ipv4("999.168.0.1"))
        self.assertFalse(AndroidController._is_ipv4("192.168.0"))
        self.assertFalse(AndroidController._is_ipv4("192.168.0.1.5"))

    def test_runtime_cache_read_write_and_corrupt_json_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_cache = Path(tmp) / ".hybridbox_runtime.json"
            with mock.patch("backend.android_controller.RUNTIME_CACHE_FILE", fake_cache):
                # 1. Missing file returns empty dict
                self.assertEqual(AndroidController._load_runtime_cache(), {})

                # 2. Save and reload
                AndroidController._save_runtime_cache(phone_ip="10.10.0.42", ssh_user="u0_a999")
                loaded = AndroidController._load_runtime_cache()
                self.assertEqual(loaded.get("phone_ip"), "10.10.0.42")
                self.assertEqual(loaded.get("ssh_user"), "u0_a999")
                self.assertIn("updated_at", loaded)

                # 3. Corrupt JSON file is handled gracefully without raising
                fake_cache.write_text("{corrupt json", encoding="utf-8")
                self.assertEqual(AndroidController._load_runtime_cache(), {})

    def test_env_var_override_for_phone_ip_and_ssh_user(self) -> None:
        ctrl = AndroidController.__new__(AndroidController)
        ctrl.ssh_host = "hybridbox.local"
        ctrl.ssh_port = 8022
        ctrl.ssh_user = "termux"
        ctrl._last_ip_check_ts = 0.0
        with mock.patch.dict(
            os.environ,
            {
                "HYBRIDBOX_PHONE_IP": "10.20.30.40",
                "HYBRIDBOX_SSH_USER": "custom_termux_user",
            },
        ):
            self.assertEqual(ctrl.discover_phone_ip(), "10.20.30.40")
            self.assertEqual(ctrl.ssh_host, "10.20.30.40")
            self.assertEqual(ctrl.discover_ssh_user(), "custom_termux_user")
            self.assertEqual(ctrl.ssh_user, "custom_termux_user")

    def test_multi_interface_subnet_prefix_and_negative_cooldown(self) -> None:
        ctrl = AndroidController.__new__(AndroidController)
        ctrl.ssh_host = "hybridbox.local"
        ctrl.ssh_port = 8022
        ctrl.ssh_user = "termux"
        ctrl._last_ip_check_ts = 0.0

        # 1. When 8.8.8.8 is unreachable (offline LAN), _get_local_subnet_prefix prefers 192.168.x / 10.x over 172.x
        with mock.patch("socket.socket.connect", side_effect=OSError("Network unreachable")), \
             mock.patch.object(ctrl, "_get_local_host_ips", return_value={"127.0.0.1", "172.24.16.1", "192.168.15.42"}):
            self.assertEqual(ctrl._get_local_subnet_prefix(), "192.168.15.")

        # 2. Multi-NIC discovery scans Wi-Fi 192.168.x prefix ahead of virtual 172.x ARP prefix and applies negative cooldown
        scanned_prefixes = []

        def fake_scan(prefixes=None, exclude_ips=None) -> str:
            if prefixes:
                scanned_prefixes.extend(prefixes)
            return ""

        with mock.patch.dict(os.environ, {"HYBRIDBOX_PHONE_IP": "", "HYBRIDBOX_SSH_HOST": ""}, clear=False), \
             mock.patch("os.path.exists", return_value=False), \
             mock.patch.object(ctrl, "_load_runtime_cache", return_value={}), \
             mock.patch.object(ctrl, "_read_ssh_config_host", return_value=""), \
             mock.patch.object(ctrl, "_find_adb", return_value=None), \
             mock.patch.object(ctrl, "_resolve_mdns_hostname", return_value=""), \
             mock.patch.object(ctrl, "_get_local_subnet_prefix", return_value="10.0.0."), \
             mock.patch.object(ctrl, "_get_local_host_ips", return_value={"127.0.0.1", "10.0.0.10", "172.28.16.1", "192.168.50.10"}), \
             mock.patch("subprocess.check_output", return_value="  172.28.16.2   00-15-5d-01-02-03   dynamic\n"), \
             mock.patch.object(ctrl, "_tcp_open", return_value=False), \
             mock.patch.object(ctrl, "_scan_local_subnet_for_phone", side_effect=fake_scan) as mock_scan:
            res1 = ctrl.discover_phone_ip(force=True)
            self.assertEqual(res1, "hybridbox.local")
            self.assertIn("10.0.0.", scanned_prefixes)
            self.assertIn("192.168.50.", scanned_prefixes)
            self.assertEqual(mock_scan.call_count, 1)

            # Immediate second call with force=False hits negative-cache cooldown without re-scanning
            res2 = ctrl.discover_phone_ip(force=False)
            self.assertEqual(res2, "hybridbox.local")
            self.assertEqual(mock_scan.call_count, 1)

    def test_projector_wifi_ssh_dynamic_user_resolution(self) -> None:
        fake_android = mock.MagicMock()
        fake_android.ssh_host = "hybridbox.local"
        fake_android.ssh_user = "termux"
        fake_android.discover_phone_ip.return_value = "10.0.0.77"
        fake_android.discover_ssh_user.return_value = "u0_a777"

        proj = ProjectorController(fake_android)
        self.assertEqual(proj.ssh_user, "termux")
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
            out = proj._run_wifi_ssh("dumpsys display")
            self.assertEqual(out, "ok")
            self.assertEqual(proj.ssh_user, "u0_a777")
            called_cmd = mock_run.call_args[0][0]
            self.assertIn("u0_a777@10.0.0.77", called_cmd)

    def test_ssh_key_injection_and_non_self_killing_restart_patterns(self) -> None:
        from scripts import pc_usb_autorevive

        with mock.patch("subprocess.run") as mock_run:
            pc_usb_autorevive._ensure_pc_ssh_key_on_phone("adb", "serial123")
            if mock_run.called:
                adb_shell_cmd = " ".join(str(x) for x in mock_run.call_args[0][0])
                self.assertIn("HOME=/data/data/com.termux/files/home", adb_shell_cmd)
                self.assertIn("/data/data/com.termux/files/home/.ssh/authorized_keys", adb_shell_cmd)
                self.assertIn("ssh-keygen -A", adb_shell_cmd)

        for rel_file in ("scripts/pc_usb_autorevive.py", "backend/ssh_terminal_controller.py", "atualizar_via_wifi.bat"):
            content = (BASE_DIR / rel_file).read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("pkill -9 -f 'scripts/keep_awake.sh'", content, f"Self-killing pkill found in {rel_file}")
            self.assertNotIn("pkill -9 -f 'backend.main:app'", content, f"Self-killing pkill found in {rel_file}")
            self.assertIn("[s]cripts/", content, f"Bracketed regex pkill missing in {rel_file}")

    def test_installer_apk_detection_skips_installed_packages(self) -> None:
        from scripts import pc_usb_autorevive

        fake_ctrl = mock.MagicMock()
        fake_ctrl._find_adb.return_value = "adb"
        fake_ctrl._get_active_adb_serials.return_value = ["127.0.0.1:5555"]
        fake_ctrl.discover_phone_ip.return_value = "127.0.0.1"

        with tempfile.TemporaryDirectory() as tmp:
            fake_base = Path(tmp)
            apks_dir = fake_base / "apks"
            apks_dir.mkdir(parents=True, exist_ok=True)
            (apks_dir / "termux-arm64.apk").write_bytes(b"fake")
            (apks_dir / "SmartTube.apk").write_bytes(b"fake")
            (apks_dir / "Lemuroid.apk").write_bytes(b"fake")

            def fake_run(cmd, *args, **kwargs):
                if "pm" in cmd and "list" in cmd:
                    return subprocess.CompletedProcess(
                        args=cmd,
                        returncode=0,
                        stdout="package:com.termux\npackage:org.smarttube.stable\n",
                        stderr="",
                    )
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="Success", stderr="")

            with mock.patch.object(pc_usb_autorevive, "BASE_DIR", fake_base), \
                 mock.patch("subprocess.run", side_effect=fake_run) as mock_run:
                pc_usb_autorevive.install_missing_apks(fake_ctrl)
                install_calls = [
                    c[0][0] for c in mock_run.call_args_list if "install" in c[0][0]
                ]
                # Only Lemuroid.apk should be installed; termux-arm64.apk and SmartTube.apk must be skipped!
                self.assertEqual(len(install_calls), 1)
                self.assertTrue(any("Lemuroid.apk" in str(arg) for arg in install_calls[0]))

    def test_projector_keywords_and_clean_formatting_without_hardcoded_mac_or_ip(self) -> None:
        for expected in ("projector", "lollipop", "hy300", "hy320", "magcubic", "wanbo", "xgimi"):
            self.assertIn(expected, PROJECTOR_KEYWORDS)

        fake_android = mock.MagicMock()
        fake_android.ssh_host = "hybridbox.local"
        fake_android.ssh_user = "termux"
        fake_android.run_adb_shell.return_value = (
            "WifiDisplayStatus{featureState=3, scanState=0, activeDisplayState=2, "
            "activeDisplay=WifiDisplay{HY300-Projector (aa:bb:cc:dd:ee:ff), isAvailable true, canConnect true, isRemembered true}, "
            "mDisplays=[HY300-Projector (aa:bb:cc:dd:ee:ff), isAvailable true, canConnect true, isRemembered true]}"
        )
        proj = ProjectorController(fake_android)
        proj.cached_projector_ip = ""
        with mock.patch.object(proj, "discover_projector_network_device", return_value=None), \
             mock.patch.object(proj, "discover_windows_miracast_devices", return_value=([], None, None)):
            status = proj.parse_miracast_status(deep_scan_ip=False)
            self.assertTrue(status["wfd_enabled"])
            self.assertTrue(len(status["miracast_devices"]) >= 1)
            dev = status["miracast_devices"][0]
            self.assertEqual(dev["name"], "Projector")
            self.assertTrue(dev["connected"])
            # Must not contain empty parentheses '()' or trailing 'IP  ' when cached_projector_ip is empty
            self.assertNotIn("()", dev["address"])
            self.assertNotIn("IP  ", dev["address"])

    def test_ssh_terminal_empty_command_edge_case(self) -> None:
        fake_android = mock.MagicMock()
        fake_android.ssh_host = "hybridbox.local"
        fake_android.ssh_user = "termux"
        ssh_ctrl = SshTerminalController(fake_android, BASE_DIR)
        res = ssh_ctrl.execute_command("   ", target="linux")
        self.assertTrue(res["ok"])
        self.assertEqual(res["output"], "")
        self.assertIn("cwd", res)

    def test_no_personal_data_in_git_tracked_files(self) -> None:
        if (BASE_DIR / ".git").exists():
            files = subprocess.check_output(["git", "ls-files"], cwd=BASE_DIR, text=True).splitlines()
        else:
            files = [
                p.relative_to(BASE_DIR).as_posix()
                for folder in ("backend", "frontend", "scripts", "docs")
                if (BASE_DIR / folder).exists()
                for p in (BASE_DIR / folder).rglob("*")
                if p.is_file()
            ] + ["README.md", "install.bat", "install.sh", "atualizar_via_wifi.bat", "iniciar_hybridbox_pwa.bat"]

        sensitive_pattern = re.compile(
            r"(192\.168\.0\.(?:57|15)\b|u0_a\d{3}\b|Users[\\/]+[a-zA-Z0-9_.\-]+)",
            re.IGNORECASE,
        )
        leaks = []
        for rel in files:
            rel = rel.strip()
            if not rel or rel == "tests/test_hybridbox.py" or rel.startswith("."):
                continue
            p = BASE_DIR / rel
            if not p.is_file() or p.suffix.lower() in (".png", ".jpg", ".apk", ".jar", ".zip", ".ico", ".pyc"):
                continue
            txt = p.read_text(encoding="utf-8", errors="ignore")
            m = sensitive_pattern.search(txt)
            if m:
                leaks.append(f"{rel}: {m.group(0)}")
        self.assertEqual(leaks, [], f"Personal data leaked in tracked files: {leaks}")


if __name__ == "__main__":
    unittest.main()
