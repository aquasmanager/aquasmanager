"""
Renseigne le contexte de chaque requête HTTP pour les journaux (middleware/context.py).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from middleware.context import request_context


class LogContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ctx = {"client_ip": request.client.host, "method": request.method, "path": request.url.path}

        request_context.set(ctx)

        response = await call_next(request)

        return response
