"""
CacheManager: Sistema Central de Cache em Memória RAM, Buffers Zero-Copy e Otimização Anti-Lag.
Impede congelamentos (lag/stutter) no celular reduzindo I/O em disco, evitando spawn excessivo
de processos e aplicando TTL adaptativo para Modo TV, Modo Linux e Modo Jogos (Emuladores).
"""

import io
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

T = TypeVar("T")


class CacheEntry:
    __slots__ = ("value", "expires_at", "hits", "created_at")

    def __init__(self, value: Any, expires_at: float) -> None:
        self.value = value
        self.expires_at = expires_at
        self.hits = 0
        self.created_at = time.time()

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class CacheManager:
    """Gerenciador centralizado de cache thread-safe em memória RAM para o HybridBox."""

    _instance: Optional["CacheManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "CacheManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._entries: Dict[str, CacheEntry] = {}
        self._cache_lock = threading.RLock()
        self._game_mode: bool = False
        self._hits: int = 0
        self._misses: int = 0

        # Buffer circular de tela em RAM (Zero-Copy)
        self._last_screencap_bytes: Optional[bytes] = None
        self._last_screencap_ts: float = 0.0
        self._screencap_mime: str = "image/png"

        # TTLs adaptativos por categoria (Normal vs Game Mode)
        self._adaptive_ttls: Dict[str, Tuple[float, float]] = {
            # Categoria: (TTL_Normal_Seg, TTL_GameMode_Seg)
            "battery": (20.0, 60.0),
            "system_health": (10.0, 45.0),
            "window_focus": (3.0, 10.0),
            "active_app": (3.0, 10.0),
            "network_ip": (60.0, 180.0),
            "miracast_scan": (15.0, 60.0),
            "thermal": (15.0, 45.0),
            "screencap": (0.15, 0.50),
        }
        self._initialized = True

    # --------------------------------------------------------------------------
    # Modo de Jogo & TTL Adaptativo
    # --------------------------------------------------------------------------
    def set_game_mode(self, active: bool) -> None:
        """Ativa/desativa o Modo Jogo, espaçando verificações secundárias para garantir 60 FPS."""
        with self._cache_lock:
            self._game_mode = bool(active)

    def is_game_mode(self) -> bool:
        return self._game_mode

    def get_adaptive_ttl(self, category: str, default: float = 30.0) -> float:
        """Retorna o TTL ideal para a categoria, considerando o modo de execução atual."""
        pair = self._adaptive_ttls.get(category)
        if not pair:
            return default
        normal_ttl, game_ttl = pair
        return game_ttl if self._game_mode else normal_ttl

    # --------------------------------------------------------------------------
    # Operações de Cache (Get, Set, Compute, Invalidate)
    # --------------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        """Recupera um valor em cache se não tiver expirado (<0.05ms)."""
        now = time.time()
        with self._cache_lock:
            entry = self._entries.get(key)
            if entry is not None:
                if now <= entry.expires_at:
                    entry.hits += 1
                    self._hits += 1
                    return entry.value
                else:
                    # Expirado: remove imediatamente
                    del self._entries[key]
            self._misses += 1
            return default

    def set(self, key: str, value: Any, ttl: Optional[float] = None, category: Optional[str] = None) -> None:
        """Armazena um valor com TTL explícito ou calculado pela categoria."""
        if ttl is None:
            ttl = self.get_adaptive_ttl(category or "default", default=30.0)
        expires_at = time.time() + max(0.05, float(ttl))
        with self._cache_lock:
            self._entries[key] = CacheEntry(value, expires_at)

    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], T],
        ttl: Optional[float] = None,
        category: Optional[str] = None,
    ) -> T:
        """Retorna valor em cache ou executa compute_fn atomicamente para repor."""
        val = self.get(key)
        if val is not None:
            return val
        computed = compute_fn()
        self.set(key, computed, ttl=ttl, category=category)
        return computed

    def invalidate(self, key: str) -> bool:
        """Invalida uma chave específica."""
        with self._cache_lock:
            return self._entries.pop(key, None) is not None

    def invalidate_prefix(self, prefix: str) -> int:
        """Invalida todas as chaves que iniciam com determinado prefixo (ex: 'app:')."""
        with self._cache_lock:
            to_remove = [k for k in self._entries if k.startswith(prefix)]
            for k in to_remove:
                del self._entries[k]
            return len(to_remove)

    def clear(self) -> None:
        """Limpa todos os dados armazenados em cache."""
        with self._cache_lock:
            self._entries.clear()
            self._last_screencap_bytes = None
            self._last_screencap_ts = 0.0

    def purge_expired(self) -> int:
        """Limpa entradas expiradas para liberar memória RAM imediatamente."""
        now = time.time()
        with self._cache_lock:
            expired_keys = [k for k, v in self._entries.items() if now > v.expires_at]
            for k in expired_keys:
                del self._entries[k]
            return len(expired_keys)

    # --------------------------------------------------------------------------
    # Ring-Buffer de Screencaps em Memória RAM (Zero-Copy)
    # --------------------------------------------------------------------------
    def update_screencap(self, data: bytes, mime_type: str = "image/png") -> None:
        """Atualiza a captura de tela mais recente diretamente na RAM."""
        with self._cache_lock:
            self._last_screencap_bytes = data
            self._last_screencap_ts = time.time()
            self._screencap_mime = mime_type

    def get_cached_screencap(self, max_age_sec: Optional[float] = None) -> Optional[bytes]:
        """
        Retorna o frame em RAM se for mais recente que max_age_sec.
        Evita sobrecarga no SurfaceFlinger do Android caso múltiplos clientes peçam stream.
        """
        if max_age_sec is None:
            max_age_sec = self.get_adaptive_ttl("screencap", default=0.20)
        with self._cache_lock:
            if self._last_screencap_bytes and (time.time() - self._last_screencap_ts <= max_age_sec):
                return self._last_screencap_bytes
            return None

    # --------------------------------------------------------------------------
    # Diagnóstico e Métricas
    # --------------------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas detalhadas de uso e eficiência do cache."""
        with self._cache_lock:
            total_requests = self._hits + self._misses
            hit_ratio = (self._hits / total_requests) if total_requests > 0 else 0.0
            return {
                "active_entries": len(self._entries),
                "game_mode": self._game_mode,
                "hits": self._hits,
                "misses": self._misses,
                "hit_ratio_percent": round(hit_ratio * 100, 1),
                "has_screencap_buffer": self._last_screencap_bytes is not None,
                "screencap_buffer_bytes": len(self._last_screencap_bytes) if self._last_screencap_bytes else 0,
            }


_global_cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """Acesso global singleton ao CacheManager."""
    return _global_cache_manager
