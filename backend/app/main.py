from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import re
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from starlette_csrf import CSRFMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings
from app.database import init_db, close_pool
from app.routes import (
    auth, users, devices, distributions, 
    defects, returns, approvals, operators,
    notifications, reports, dashboard, change_requests,
    external_inventory, reassignment_requests
)
from app.middleware.error_handler import add_exception_handlers
from app.middleware.auth_middleware import get_current_user, require_admin
from app.core.rate_limiter import limiter
from app.core.audit import audit_logger
from app.core.activity_logger import build_meaningful_activity_description, log_api_activity
from app.core.metrics import MetricsMiddleware, metrics_endpoint
from app.services.auth_service import get_current_user_from_token


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply standard security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        docs_paths = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
        if request.url.path not in docs_paths:
            csp = (
                "default-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:"
            )
            response.headers["Content-Security-Policy"] = csp
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class HttpsEnforcementMiddleware(BaseHTTPMiddleware):
    """Redirect plaintext HTTP requests to HTTPS when explicitly enabled.
    Skips internal-only paths that may be scraped by Prometheus over HTTP.
    """

    EXEMPT_PATHS = {"/metrics", "/health"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        if settings.ENFORCE_HTTPS:
            forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            if forwarded_proto.lower() != "https":
                https_url = request.url.replace(scheme="https")
                return RedirectResponse(url=str(https_url), status_code=307)

        return await call_next(request)


class ApiActivityLoggingMiddleware(BaseHTTPMiddleware):
    """Log API request activity for admin audit timeline."""

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
            except Exception:
                pass

        ip_address = request.client.host if request.client else None

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup - initialize SQLite database
    await init_db()
    
    # Seed initial data
    from app.services.seed_service import seed_initial_data
    from app.services.backup_scheduler import monthly_backup_scheduler_loop
    from app.services.db_backup_scheduler import start_db_backup_scheduler, shutdown_db_backup_scheduler
    await seed_initial_data()

    backup_task = asyncio.create_task(monthly_backup_scheduler_loop())
    app.state.monthly_backup_task = backup_task

    app.state.db_backup_scheduler = await start_db_backup_scheduler()

    from app.services.metrics_collector import metrics_collector_loop
    metrics_task = asyncio.create_task(metrics_collector_loop())
    app.state.metrics_collector_task = metrics_task

    yield
    
    # Shutdown - stop monthly backup loop.
    task = getattr(app.state, "monthly_backup_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    scheduler = getattr(app.state, "db_backup_scheduler", None)
    if scheduler:
        shutdown_db_backup_scheduler()

    metrics_task = getattr(app.state, "metrics_collector_task", None)
    if metrics_task:
        metrics_task.cancel()
        try:
            await metrics_task
        except asyncio.CancelledError:
            pass

    await close_pool()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for Distribution Management System",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

uploads_root = Path(__file__).resolve().parents[1] / "uploads"
uploads_root.mkdir(parents=True, exist_ok=True)

app.add_middleware(MetricsMiddleware)

app.add_middleware(
    CSRFMiddleware,
    secret=settings.SECRET_KEY,
    cookie_name=settings.CSRF_COOKIE_NAME,
    cookie_secure=settings.CSRF_COOKIE_SECURE,
    cookie_samesite="strict",
    sensitive_cookies={"access_token", "refresh_token"},
    exempt_urls=[re.compile(r"^/api/auth/login$"), re.compile(r"^/metrics$")],
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(HttpsEnforcementMiddleware)
app.add_middleware(ApiActivityLoggingMiddleware)

# Keep CORS as the outermost middleware so all responses (including
# auth failures, redirects, and handled exceptions) include CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)

# Add exception handlers
add_exception_handlers(app)

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["Users"])
app.include_router(devices.router, prefix=f"{settings.API_V1_PREFIX}/devices", tags=["Devices"])
app.include_router(distributions.router, prefix=f"{settings.API_V1_PREFIX}/distributions", tags=["Distributions"])
app.include_router(defects.router, prefix=f"{settings.API_V1_PREFIX}/defects", tags=["Defects"])
app.include_router(returns.router, prefix=f"{settings.API_V1_PREFIX}/returns", tags=["Returns"])
app.include_router(approvals.router, prefix=f"{settings.API_V1_PREFIX}/approvals", tags=["Approvals"])
app.include_router(operators.router, prefix=f"{settings.API_V1_PREFIX}/operators", tags=["Operators"])
app.include_router(notifications.router, prefix=f"{settings.API_V1_PREFIX}/notifications", tags=["Notifications"])
app.include_router(reports.router, prefix=f"{settings.API_V1_PREFIX}/reports", tags=["Reports"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_PREFIX}/dashboard", tags=["Dashboard"])
app.include_router(change_requests.router, prefix=f"{settings.API_V1_PREFIX}/change-requests", tags=["Change Requests"])
app.include_router(external_inventory.router, prefix=f"{settings.API_V1_PREFIX}/external-inventory", tags=["External Inventory"])
app.include_router(reassignment_requests.router, prefix=f"{settings.API_V1_PREFIX}/reassignment-requests", tags=["Reassignment Requests"])


@app.get("/", tags=["Root"], summary="Root endpoint")
async def root():
    """Root endpoint"""
    return {
        "message": "Distribution Management System API",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else None
    }


@app.get("/health", tags=["Health"], summary="Health check endpoint")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/metrics", tags=["Metrics"], summary="Prometheus metrics endpoint")
async def metrics():
    """Prometheus metrics endpoint"""
    return await metrics_endpoint()


@app.get(f"{settings.API_V1_PREFIX}/uploads/{{file_path:path}}", tags=["Uploads"], summary="Serve uploaded files only to authenticated users")
async def serve_upload(file_path: str, current_user: dict = Depends(get_current_user)):
    """Serve uploaded files only to authenticated users."""
    resolved_root = uploads_root.resolve()
    safe_path = (resolved_root / file_path).resolve()

    if resolved_root not in safe_path.parents and safe_path != resolved_root:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if safe_path.is_file():
        return FileResponse(path=str(safe_path))

    if file_path.startswith("defect_payments/") or file_path.startswith("defect_photos/"):
        from app.services.rclone_storage import get_rclone_file_content
        import mimetypes
        from fastapi.responses import Response
        
        # Determine the rclone folder based on the prefix
        rclone_folder = file_path.split("/")[0]
        file_name = file_path.split("/")[-1]
        
        try:
            content = await get_rclone_file_content(rclone_folder, file_name)
            mime_type, _ = mimetypes.guess_type(file_name)
            return Response(content=content, media_type=mime_type or "application/octet-stream")
        except RuntimeError:
            pass
            
    raise HTTPException(status_code=404, detail="File not found")


@app.post("/reset-and-seed", tags=["Seed"], dependencies=[Depends(require_admin)])
async def reset_and_seed_endpoint(request: Request, current_user: dict = Depends(get_current_user)):
    """Reset database and seed with fresh user accounts - ADMIN ONLY"""
    if settings.ENVIRONMENT != "development":
        raise HTTPException(status_code=403, detail="Not allowed in production")

    audit_logger.critical(
        "DB_RESET | user_id=%s | email=%s | ip=%s",
        current_user.get("id"),
        current_user.get("email"),
        request.client.host if request.client else "unknown",
    )

    from app.services.seed_service import reset_and_seed
    result = await reset_and_seed()
    return {"success": True, **result}

