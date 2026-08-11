import logging
from fastapi import APIRouter, HTTPException, status, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from app.models.auth import LoginRequest, RefreshTokenRequest
from app.models.user import PasswordChange, ForcedCredentialUpdateRequest
from app.services import auth_service
from app.middleware.auth_middleware import get_current_user, security
from app.schemas.responses import StandardResponse
from app.core.rate_limiter import limiter
from app.core.audit import audit_logger
from app.core.activity_logger import log_api_activity
from app.config import settings

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/login", response_model=dict, summary="User login endpoint")
@limiter.limit("5/minute")
async def login(request: Request, response: Response, credentials: LoginRequest):
    """User login endpoint"""
    try:
        client_ip = request.client.host if request.client else "unknown"
        user = await auth_service.authenticate_user(credentials.email, credentials.password)

        if not user:
            audit_logger.warning(
                "LOGIN_FAILED | email=%s | ip=%s",
                credentials.email.lower(),
                client_ip,
            )
            await log_api_activity(
                method="POST",
                path="/api/auth/login",
                status_code=status.HTTP_401_UNAUTHORIZED,
                actor_name=credentials.email.lower(),
                description="Attempted login (rejected: 401)",
                ip_address=client_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email/phone or password"
            )

        if user.get("status") != "active":
            audit_logger.warning(
                "LOGIN_BLOCKED_INACTIVE | user_id=%s | email=%s | ip=%s",
                user.get("id"),
                user.get("email"),
                client_ip,
            )
            await log_api_activity(
                method="POST",
                path="/api/auth/login",
                status_code=status.HTTP_403_FORBIDDEN,
                actor_id=str(user.get("id") or ""),
                actor_name=str(user.get("name") or user.get("email") or credentials.email.lower()),
                actor_role=str(user.get("role") or ""),
                description="Attempted login (rejected: 403)",
                ip_address=client_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active"
            )

        token_data = await auth_service.create_user_token(user)

        # Backward-compatible auth hardening: keep response tokens while also setting
        # secure httpOnly cookies for cookie-based auth and CSRF-protected requests.
        is_secure_cookie = settings.CSRF_COOKIE_SECURE
        response.set_cookie(
            key="access_token",
            value=token_data["access_token"],
            httponly=True,
            secure=is_secure_cookie,
            samesite="strict",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
        )
        response.set_cookie(
            key="refresh_token",
            value=token_data["refresh_token"],
            httponly=True,
            secure=is_secure_cookie,
            samesite="strict",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/",
        )

        audit_logger.info(
            "LOGIN_SUCCESS | user_id=%s | email=%s | role=%s | ip=%s",
            user.get("id"),
            user.get("email"),
            user.get("role"),
            client_ip,
        )

        await log_api_activity(
            method="POST",
            path="/api/auth/login",
            status_code=status.HTTP_200_OK,
            actor_id=str(user.get("id") or ""),
            actor_name=str(user.get("name") or user.get("email") or "Unknown"),
            actor_role=str(user.get("role") or ""),
            description="User logged in",
            ip_address=client_ip,
        )

        # Tokens are delivered exclusively via httpOnly cookies. They are
        # intentionally omitted from the response body so a single XSS cannot
        # exfiltrate them from the JSON payload.
        return {
            "success": True,
            "message": "Login successful",
            "data": {
                "user": token_data["user"],
                "token_type": token_data.get("token_type", "bearer"),
                "expires_in": token_data["expires_in"],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/logout", summary="User logout endpoint")
@limiter.limit("30/minute")
async def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    current_user: dict = Depends(get_current_user)
):
    """User logout endpoint"""
    try:
        token = credentials.credentials if credentials else request.cookies.get("access_token")
        refresh_token = request.cookies.get("refresh_token")
        if token:
            await auth_service.blacklist_token(token)
        if refresh_token:
            await auth_service.blacklist_token(refresh_token)

        response.delete_cookie("access_token", path="/")
        response.delete_cookie("refresh_token", path="/")

        audit_logger.info(
            "LOGOUT_SUCCESS | user_id=%s | email=%s | ip=%s",
            current_user.get("id"),
            current_user.get("email"),
            request.client.host if request.client else "unknown",
        )

        return {
            "success": True,
            "message": "Logout successful"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/refresh", response_model=dict, summary="Issue a new access token from a valid refresh token.")
@limiter.limit("10/minute")
async def refresh_token(
    request: Request,
    response: Response,
    refresh_req: RefreshTokenRequest | None = None,
):
    """Issue a new access token from a valid refresh token.

    Reads the refresh token from the httpOnly cookie first;
    falls back to the request body for backward compatibility.
    """
    try:
        refresh_token_value = refresh_req.refresh_token if (refresh_req and refresh_req.refresh_token) else request.cookies.get("refresh_token")
        if not refresh_token_value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not provided"
            )

        token_data = await auth_service.refresh_access_token(refresh_token_value)
        if not token_data:
            audit_logger.warning(
                "TOKEN_REFRESH_FAILED | ip=%s",
                request.client.host if request.client else "unknown",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        audit_logger.info(
            "TOKEN_REFRESH_SUCCESS | ip=%s",
            request.client.host if request.client else "unknown",
        )

        is_secure_cookie = settings.CSRF_COOKIE_SECURE
        response.set_cookie(
            key="access_token",
            value=token_data["access_token"],
            httponly=True,
            secure=is_secure_cookie,
            samesite="strict",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
        )
        if "refresh_token" in token_data:
            response.set_cookie(
                key="refresh_token",
                value=token_data["refresh_token"],
                httponly=True,
                secure=is_secure_cookie,
                samesite="strict",
                max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
                path="/",
            )

        # Tokens are delivered exclusively via httpOnly cookies; the response
        # body carries only metadata so tokens cannot be read from JSON by XSS.
        return {
            "success": True,
            "message": "Token refreshed successfully",
            "data": {
                "token_type": token_data.get("token_type", "bearer"),
                "expires_in": token_data["expires_in"],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


# Fields the authenticated client needs to render the UI. Server-only account
# metadata (status, timestamps, login counters, lockout state, creator id) and
# password_hash are deliberately excluded so they are never stored in the
# browser's sessionStorage.
_ME_USER_FIELDS = {
    "id", "email", "name", "role",
    "phone", "designation", "address", "pincode", "parent_id",
    "force_email_change", "force_password_change",
}


@router.get("/me", summary="Get current user information")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    try:
        # Return only the fields the frontend actually needs
        user_data = {k: v for k, v in current_user.items() if k in _ME_USER_FIELDS}

        return {
            "success": True,
            "message": "User info retrieved",
            "data": user_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.put("/password", summary="Change user password")
async def change_password(
    request: Request,
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """Change user password"""
    try:
        success = await auth_service.change_user_password(
            user_id=current_user["id"],
            current_password=password_data.current_password,
            new_password=password_data.new_password
        )

        if not success:
            audit_logger.warning(
                "PASSWORD_CHANGE_FAILED | user_id=%s | ip=%s",
                current_user.get("id"),
                request.client.host if request.client else "unknown",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )

        audit_logger.info(
            "PASSWORD_CHANGE_SUCCESS | user_id=%s | ip=%s",
            current_user.get("id"),
            request.client.host if request.client else "unknown",
        )

        return {
            "success": True,
            "message": "Password changed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/complete-forced-update", summary="Complete mandatory first-login email and password rotation.")
async def complete_forced_update(
    request: Request,
    response: Response,
    payload: ForcedCredentialUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Complete mandatory first-login email and password rotation."""
    try:
        if not (current_user.get("force_email_change") or current_user.get("force_password_change")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No forced update is required for this account",
            )

        updated_user = await auth_service.complete_forced_credential_update(
            user_id=current_user["id"],
            current_password=payload.current_password,
            new_email=payload.new_email,
            new_phone=payload.new_phone,
            new_password=payload.new_password,
        )

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        token_data = await auth_service.create_user_token(updated_user)

        is_secure_cookie = settings.CSRF_COOKIE_SECURE
        response.set_cookie(
            key="access_token",
            value=token_data["access_token"],
            httponly=True,
            secure=is_secure_cookie,
            samesite="strict",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
        )
        response.set_cookie(
            key="refresh_token",
            value=token_data["refresh_token"],
            httponly=True,
            secure=is_secure_cookie,
            samesite="strict",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/",
        )

        audit_logger.info(
            "FORCED_CREDENTIAL_ROTATION_COMPLETE | user_id=%s | ip=%s",
            current_user.get("id"),
            request.client.host if request.client else "unknown",
        )
        await log_api_activity(
            method="POST",
            path="/api/auth/complete-forced-update",
            status_code=status.HTTP_200_OK,
            actor_id=str(current_user.get("id") or ""),
            actor_name=str(current_user.get("name") or current_user.get("email") or "Unknown"),
            actor_role=str(current_user.get("role") or ""),
            description="Completed forced first-login credential rotation",
            ip_address=request.client.host if request.client else "unknown",
        )

        # Tokens are delivered exclusively via httpOnly cookies; the response
        # body carries only the user profile and metadata.
        return {
            "success": True,
            "message": "Credentials updated successfully",
            "data": {
                "user": token_data["user"],
                "token_type": token_data.get("token_type", "bearer"),
                "expires_in": token_data["expires_in"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )



