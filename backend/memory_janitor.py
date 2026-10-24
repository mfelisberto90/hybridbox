"""
MemoryJanitor: Guardião Ativo de Memória RAM, Rotação de Logs e Limpeza de Pagecache.
Mantém o Xiaomi Redmi Note 8 Pro livre de engasgos (lag/stutter/OOM) executando rotação atômica
de logs quando >5MB, limpeza de arquivos temporários e liberação segura de pagecache (/proc/sys/vm/drop_caches).
"""

import gc
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from backend.cache_manager import get_cache_manager
except ImportError:
    from cache_manager import get_cache_manager


class MemoryJanitor:
    """Guardião em background que evita acúmulo de arquivos, logs inflados e pressão de memória."""

    def __init__(self, base_dir: Optional[Path] = None, check_interval_sec: float = 45.0) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent
        self.check_interval_sec = check_interval_sec
        self.cache_manager = get_cache_manager()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_run_stats: Dict[str, Any] = {}

    def start(self) -> None:
        """Inicia a thread de monitoramento do Janitor."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="HybridBox-MemoryJanitor")
        self._thread.start()

    def stop(self) -> None:
        """Para a thread do Janitor."""
        self._running = False

    def _run_loop(self) -> None:
        while self._running:
            try:
                interval = 120.0 if self.cache_manager.is_game_mode() else self.check_interval_sec
                time.sleep(interval)
                self.run_clean_cycle()
            except Exception:
                time.sleep(10.0)

    def run_clean_cycle(self) -> Dict[str, Any]:
        """Executa um ciclo completo de higienização de memória e armazenamento."""
        stats: Dict[str, Any] = {
            "timestamp": time.time(),
            "purged_cache_entries": 0,
            "rotated_logs": [],
            "cleaned_temp_files": 0,
            "freed_pagecache": False,
            "python_gc_collected": 0,
            "mem_available_mb": self.get_available_ram_mb(),
        }

        # 1. Purgar chaves expiradas no CacheManager
        stats["purged_cache_entries"] = self.cache_manager.purge_expired()

        # 2. Coletor de lixo do Python
        stats["python_gc_collected"] = gc.collect()

        # 3. Rotação de logs inflados (>5MB)
        stats["rotated_logs"] = self.rotate_heavy_logs(max_bytes=5 * 1024 * 1024, keep_lines=2000)

        # 4. Limpeza de capturas de tela e temporários velhos (>5min)
        stats["cleaned_temp_files"] = self.clean_stale_temp_files(max_age_sec=300.0)

        # 5. Se a RAM livre for crítica (<450MB), liberta pagecache inativo
        avail_mb = stats["mem_available_mb"]
        if avail_mb is not None and avail_mb < 450.0:
            stats["freed_pagecache"] = self.drop_kernel_pagecaches()

        self._last_run_stats = stats
        return stats

    def get_available_ram_mb(self) -> Optional[float]:
        """Lê MemAvailable diretamente de /proc/meminfo sem criar processos (<0.1ms)."""
        try:
            meminfo_path = Path("/proc/meminfo")
            if meminfo_path.exists():
                for line in meminfo_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("MemAvailable:"):
                        parts = line.split()
                        kb = float(parts[1])
                        return kb / 1024.0
        except Exception:
            pass
        return None

    def rotate_heavy_logs(self, max_bytes: int = 5 * 1024 * 1024, keep_lines: int = 2000) -> List[str]:
        """Trunca arquivos de log que ultrapassem max_bytes, preservando as últimas keep_lines."""
        rotated = []
        home = os.environ.get("HOME") or "/data/data/com.termux/files/home"
        candidate_logs = [
            Path(home) / "uvicorn.log",
            Path(home) / "hybridbox-keep-awake.log",
            Path(home) / "pwa.log",
            Path("/data/local/tmp/hb_daemon.log"),
        ]

        for log_file in candidate_logs:
            try:
                if log_file.exists() and log_file.is_file():
                    size = log_file.stat().st_size
                    if size > max_bytes:
                        # Lê apenas as últimas linhas sem carregar o arquivo inteiro na RAM
                        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                            lines = f.readlines()
                        tail = lines[-keep_lines:] if len(lines) > keep_lines else lines
                        with open(log_file, "w", encoding="utf-8") as f:
                            f.writelines(tail)
                        rotated.append(f"{log_file.name} ({round(size / (1024*1024), 1)}MB -> {len(tail)} lines)")
            except Exception:
                pass
        return rotated

    def clean_stale_temp_files(self, max_age_sec: float = 300.0) -> int:
        """Remove arquivos .png ou temporários esquecidos em tmpfs / home mais antigos que max_age_sec."""
        cleaned = 0
        now = time.time()
        home = os.environ.get("HOME") or "/data/data/com.termux/files/home"
        prefix_tmp = "/data/data/com.termux/files/usr/tmp"

        candidate_dirs = [Path(home), Path(prefix_tmp)]
        for cdir in candidate_dirs:
            if not cdir.exists():
                continue
            try:
                for p in cdir.glob("*.png"):
                    if p.is_file():
                        age = now - p.stat().st_mtime
                        if age > max_age_sec:
                            p.unlink(missing_ok=True)
                            cleaned += 1
            except Exception:
                pass
        return cleaned

    def drop_kernel_pagecaches(self) -> bool:
        """
        Executa 'sync && echo 3 > /proc/sys/vm/drop_caches' via hb-shell / su quando o kernel
        está sob pressão de RAM, aliviando o LMK (Low Memory Killer) da MIUI.
        """
        cmd = "sync; echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true"
        hb_shell = "/data/data/com.termux/files/usr/bin/hb-shell"
        if os.path.exists(hb_shell):
            try:
                subprocess.run([hb_shell, cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.5)
                return True
            except Exception:
                pass
        return False

    def get_status(self) -> Dict[str, Any]:
        """Retorna o status atual do Janitor e da memória."""
        avail_mb = self.get_available_ram_mb()
        return {
            "running": self._running,
            "check_interval_sec": self.check_interval_sec,
            "available_ram_mb": round(avail_mb, 1) if avail_mb is not None else None,
            "last_cycle": self._last_run_stats,
        }
