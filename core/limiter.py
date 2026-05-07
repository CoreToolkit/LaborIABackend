from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


AUTH_RATE_LIMIT = "10/minute"
AUTH_RATE_LIMIT_RETRY_AFTER_SECONDS = 60


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


auth_rate_limiter = Limiter(
    key_func=get_client_ip,
    headers_enabled=False,
    retry_after="60",
)


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
        headers={"Retry-After": str(AUTH_RATE_LIMIT_RETRY_AFTER_SECONDS)},
    )
