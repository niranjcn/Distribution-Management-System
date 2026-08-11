from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings
from app.core.activity_logger import build_meaningful_activity_description, log_api_activity
from app.services.auth_service import get_current_user_from_token
from app.utils.helpers import get_client_ip


class ApiActivityLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(settings.API_V1_PREFIX):
            return await call_next(request)
        if request.method.upper() == "OPTIONS":
            return await call_next(request)
        if request.url.path == "/metrics":
            return await call_next(request)

        actor_id = None
        actor_name = "Anonymous"
        actor_role = None

        auth_header = request.headers.get("authorization", "")
        token = None
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        if not token:
            token = request.cookies.get("access_token")

        if token:
            try:
                user = await get_current_user_from_token(token)
                if user:
                    actor_id = str(user.get("id") or user.get("_id") or user.get("user_id") or user.get("sub") or "")
                    actor_name = str(user.get("name") or user.get("email") or "Anonymous")
                    actor_role = str(user.get("role") or "")
                    request.state.current_user = user
            except Exception:
                pass

        ip_address = get_client_ip(request)

        try:
            response = await call_next(request)
            description = build_meaningful_activity_description(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
            )
            if not description:
                return response

            await log_api_activity(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                actor_id=actor_id,
                actor_name=actor_name,
                actor_role=actor_role,
                ip_address=ip_address,
                description=description,
            )
            return response
        except Exception:
            description = build_meaningful_activity_description(
                method=request.method,
                path=request.url.path,
                status_code=500,
            )
            if not description:
                raise

            await log_api_activity(
                method=request.method,
                path=request.url.path,
                status_code=500,
                actor_id=actor_id,
                actor_name=actor_name,
                actor_role=actor_role,
                ip_address=ip_address,
                description=description,
            )
            raise
