"""İstek sınırlama (kayan pencere).

Bellek içi uygulama tek süreçte çalışır; birden çok backend süreci/sunucusu olduğunda
ortak bir depo (Redis vb.) ile değiştirilmelidir. Arayüz bunun için ayrı tutulmuştur.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from functools import lru_cache
from typing import Protocol

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> float | None:
        """İsteği sayar. Sınır aşıldıysa kaç saniye sonra tekrar denenebileceğini döndürür."""
        ...

    def reset(self) -> None: ...


class MemoryRateLimiter:
    def __init__(self, clock=time.monotonic) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._clock = clock

    def hit(self, key: str, limit: int, window_seconds: int) -> float | None:
        now = self._clock()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= now - window_seconds:
                q.popleft()
            if len(q) >= limit:
                return q[0] + window_seconds - now
            q.append(now)
            if len(self._hits) > 100_000:  # bellek koruması: boş kuyrukları temizle
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return MemoryRateLimiter()


def client_ip(request: Request) -> str:
    """İstemci IP'si. Yalnızca güvenilen vekil sayısı kadar X-Forwarded-For girdisine güvenilir."""
    n = get_settings().trusted_proxy_count
    if n > 0:
        parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(parts) >= n:
            return parts[-n]
    return request.client.host if request.client else "bilinmiyor"


def enforce(scope: str, key: str, limit: int, window_seconds: int) -> None:
    """Sınır aşıldıysa 429 fırlatır."""
    if not get_settings().rate_limit_enabled:
        return
    retry = get_rate_limiter().hit(f"{scope}:{key}", limit, window_seconds)
    if retry is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Çok fazla deneme yapıldı. Lütfen biraz sonra tekrar deneyin.",
            headers={"Retry-After": str(max(1, math.ceil(retry)))},
        )


# Sınırlar: (istek sayısı, pencere saniye)
LIMITS = {
    "login_ip": (20, 15 * 60),
    "login_email": (10, 15 * 60),
    "register_ip": (10, 60 * 60),
    "email_send_ip": (10, 60 * 60),  # şifremi unuttum, doğrulama yeniden gönder
    "email_send_addr": (3, 60 * 60),
    "token_ip": (30, 60 * 60),  # doğrulama ve şifre sıfırlama jetonu denemeleri
    "checkout_user": (10, 60 * 60),
}


def limit(scope: str, key: str) -> None:
    n, window = LIMITS[scope]
    enforce(scope, key, n, window)
