from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from services.token_service import extract_bearer_token, validate_jwt_token


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, excluded_paths: list[str] | None = None):
        super().__init__(app)
        self.excluded_paths = excluded_paths or []

    async def dispatch(self, request: Request, call_next):
        # BaseHTTPMiddleware recibe también conexiones WebSocket como scope type "websocket".
        # Intentar procesarlas como HTTP rompe el handshake WS.
        # Las dejamos pasar directamente — la autenticación WS se maneja en el endpoint.
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        path = request.url.path

        # Permitir preflight CORS sin exigir token
        if request.method == "OPTIONS":
            return await call_next(request)

        if self._is_excluded(path):
            return await call_next(request)

        try:
            token = extract_bearer_token(request)
            payload = validate_jwt_token(token)
            request.state.user = payload
        except Exception as exc:
            # Si ya es un HTTPException, reutilizamos su contenido
            if hasattr(exc, "status_code"):
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": getattr(exc, "detail", "Unauthorized")},
                )
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        return await call_next(request)

    def _is_excluded(self, path: str) -> bool:
        for prefix in self.excluded_paths:
            if path.startswith(prefix):
                return True
        return False
