import logging
from logging.handlers import RotatingFileHandler
import sys

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import re
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from starlette_csrf import CSRFMiddleware

from app.config import settings
from app.database import init_db
from app.routes import (
    auth, users, devices, distributions, 
    defects, returns, operators,
    notifications, reports, dashboard, change_requests,
    external_inventory, reassignment_requests, digital_ids
)
from app.middleware.error_handler import add_exception_handlers
from app.middleware.auth_middleware import get_current_user, require_admin
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.https_enforcement import HttpsEnforcementMiddleware
from app.middleware.api_activity_logging import ApiActivityLoggingMiddleware
from app.core.rate_limiter import limiter
from app.core.audit import audit_logger
from app.core.metrics import MetricsMiddleware, metrics_endpoint

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
def _setup_logging() -> None:
    _logs_dir = Path(__file__).resolve().parents[1] / "logs"
    _logs_dir.mkdir(parents=True, exist_ok=True)

    _root_logger = logging.getLogger()
    # Remove any handlers uvicorn may have attached
    for h in list(_root_logger.handlers):
        _root_logger.removeHandler(h)

    _root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    _file_handler = RotatingFileHandler(
        _logs_dir / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )

    _console_handler = logging.StreamHandler(sys.stdout)
    _console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    _console_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )

    _root_logger.addHandler(_file_handler)
    _root_logger.addHandler(_console_handler)

    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    # Re-enable loggers that might have been disabled by uvicorn's dictConfig
    # and configure uvicorn loggers to propagate to the root logger.
    for name, logger in logging.root.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):
            logger.disabled = False
            if name.startswith("uvicorn"):
                for handler in list(logger.handlers):
                    logger.removeHandler(handler)
                logger.propagate = True

_setup_logging()
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, force=True,
                        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    _setup_logging()
    await init_db()
    
    # Seed initial data
    from app.services.seed_service import seed_initial_data
    from app.services.backup_scheduler import monthly_backup_scheduler_loop
    from app.services.db_backup_scheduler import start_db_backup_scheduler, shutdown_db_backup_scheduler
    await seed_initial_data()

    backup_task = asyncio.create_task(monthly_backup_scheduler_loop())
    app.state.monthly_backup_task = backup_task

    app.state.db_backup_scheduler = await start_db_backup_scheduler()

    from app.services.activity_log_cleanup import start_activity_log_cleanup_scheduler, shutdown_activity_log_cleanup_scheduler
    app.state.activity_log_cleanup_scheduler = await start_activity_log_cleanup_scheduler()

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

    log_scheduler = getattr(app.state, "activity_log_cleanup_scheduler", None)
    if log_scheduler:
        shutdown_activity_log_cleanup_scheduler()

    metrics_task = getattr(app.state, "metrics_collector_task", None)
    if metrics_task:
        metrics_task.cancel()
        try:
            await metrics_task
        except asyncio.CancelledError:
            pass

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
app.include_router(operators.router, prefix=f"{settings.API_V1_PREFIX}/operators", tags=["Operators"])
app.include_router(notifications.router, prefix=f"{settings.API_V1_PREFIX}/notifications", tags=["Notifications"])
app.include_router(reports.router, prefix=f"{settings.API_V1_PREFIX}/reports", tags=["Reports"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_PREFIX}/dashboard", tags=["Dashboard"])
app.include_router(change_requests.router, prefix=f"{settings.API_V1_PREFIX}/change-requests", tags=["Change Requests"])
app.include_router(external_inventory.router, prefix=f"{settings.API_V1_PREFIX}/external-inventory", tags=["External Inventory"])
app.include_router(reassignment_requests.router, prefix=f"{settings.API_V1_PREFIX}/reassignment-requests", tags=["Reassignment Requests"])
app.include_router(digital_ids.router, prefix=f"{settings.API_V1_PREFIX}/digital-ids", tags=["Digital IDs"])


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

