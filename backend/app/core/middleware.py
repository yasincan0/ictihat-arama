"""Güvenlik ara katmanları: güvenlik başlıkları, Origin denetimi (CSRF), gövde boyutu sınırı."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Üçüncü taraflarca (ödeme kuruluşu) çağrılan uçlar Origin denetiminden muaftır;
# bunlar kendi doğrulamalarını yapar (jeton eşleme / imza + sağlayıcıdan sorgulama).
ORIGIN_EXEMPT_PATHS = {"/payments/callback", "/payments/webhook/iyzico"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.hsts = settings.cookie_secure

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # API yanıtları (oturum, kota, abonelik) önbelleğe alınmamalı
        h.setdefault("Cache-Control", "no-store")
        if self.hsts:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Çerezle kimlik doğrulayan API'de CSRF koruması: durum değiştiren isteklerde tarayıcının
    gönderdiği Origin başlığı izinli kökenlerden biri olmalıdır. Origin göndermeyen
    (tarayıcı dışı) istemciler etkilenmez; SameSite=Lax çerez ek bir katmandır."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.allowed = {o.rstrip("/") for o in settings.cors_origin_list}
        self.allowed.add(settings.backend_url.rstrip("/"))

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in UNSAFE_METHODS and request.url.path not in ORIGIN_EXEMPT_PATHS:
            origin = request.headers.get("origin")
            if origin is not None and origin.rstrip("/") not in self.allowed:
                return JSONResponse({"detail": "İstek kaynağı reddedildi"}, status_code=403)
        return await call_next(request)


class BodySizeLimitMiddleware:
    """Büyük gövdeli istekleri (Content-Length veya akış sırasında) 413 ile reddeder."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        too_big = JSONResponse({"detail": "İstek çok büyük"}, status_code=413)
        if declared is not None:
            try:
                if int(declared) > self.max_bytes:
                    await too_big(scope, receive, send)
                    return
            except ValueError:
                await JSONResponse({"detail": "Geçersiz istek"}, status_code=400)(scope, receive, send)
                return

        # Gövde sınır dahilinde önceden okunur (en fazla max_bytes) ve uygulamaya tekrar verilir.
        chunks: list[bytes] = []
        received = 0
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            received += len(body)
            if received > self.max_bytes:
                await too_big(scope, receive, send)
                return
            chunks.append(body)
            more = message.get("more_body", False)

        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)
