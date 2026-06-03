"""中间件：限流 + 统一响应格式。"""

import time
import uuid
from collections import defaultdict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .log_config import get_logger

log = get_logger(__name__)


# ═══ Rate Limiter ═══

class RateLimiter:
    """Token bucket 限流器。默认 60 req/min。
    每 1000 次请求自动清理不活跃的 IP bucket。"""

    def __init__(self, rate: int = 60, window: int = 60):
        self.rate = rate
        self.window = window
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._hits = 0

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        self._hits += 1
        # Periodic cleanup: every ~1000 requests, purge stale buckets
        if self._hits % 1000 == 0:
            cutoff = now - max(self.window, 300)
            stale = [k for k, v in self._buckets.items() if not v or max(v) < cutoff]
            for k in stale:
                del self._buckets[k]
        bucket = self._buckets[key]
        # Clean expired timestamps
        cutoff = now - self.window
        self._buckets[key] = [t for t in bucket if t > cutoff]
        if len(self._buckets[key]) >= self.rate:
            return False
        self._buckets[key].append(now)
        return True


_limiter = RateLimiter(rate=60, window=60)  # 60 req/min per IP


class RateLimitMiddleware(BaseHTTPMiddleware):
    """全局限流中间件。"""

    async def dispatch(self, request: Request, call_next):
        client_ip = (request.client.host if request.client else None) or "127.0.0.1"  # TestClient has no client

        # Skip localhost / TestClient
        if client_ip in ("127.0.0.1", "testclient"):
            return await call_next(request)

        path = request.url.path
        if path.startswith("/assets") or path in ("/docs", "/openapi.json"):
            return await call_next(request)

        if not _limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={"error": "Too Many Requests", "detail": "Rate limit: 60 req/min"},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)


# ═══ Response Envelope ═══

class ResponseEnvelopeMiddleware(BaseHTTPMiddleware):
    """统一响应格式包装 {data, error, meta}。"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only wrap JSON responses from API endpoints
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Skip already wrapped, streaming, and docs
        path = request.url.path
        if path in ("/docs", "/openapi.json"):
            return response

        # Read body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        import json
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(content=body, status_code=response.status_code,
                          media_type=response.media_type, headers=dict(response.headers))

        # Wrap in envelope
        if 200 <= response.status_code < 300:
            enveloped = {"data": data, "error": None, "meta": {"request_id": getattr(request.state, "request_id", "")}}
        else:
            enveloped = {"data": None, "error": data, "meta": {"request_id": getattr(request.state, "request_id", "")}}

        return JSONResponse(content=enveloped, status_code=response.status_code)


# ═══ Request ID ═══

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
