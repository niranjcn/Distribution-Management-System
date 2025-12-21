from fastapi import APIRouter, HTTPException, status, Depends
from app.models.auth import LoginRequest, Token
from app.models.user import PasswordChange
from app.services import auth_service
from app.middleware.auth_middleware import get_current_user
from app.schemas.responses import StandardResponse

router = APIRouter()


@router.post("/login", response_model=dict)
async def login(credentials: LoginRequest):
    """User login endpoint"""
    user = await auth_service.authenticate_user(credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if user.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active"
        )
    
    token_data = await auth_service.create_user_token(user)
    
    return {
        "success": True,
        "message": "Login successful",
        "data": token_data
    }


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """User logout endpoint"""
    # In a real app, you might blacklist the token here
    return {
        "success": True,
        "message": "Logout successful"
    }


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    # Remove sensitive fields
    user_data = {k: v for k, v in current_user.items() if k != "password_hash"}
    
    return {
        "success": True,
        "message": "User info retrieved",
        "data": user_data
    }


@router.put("/password")
async def change_password(
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """Change user password"""
    success = await auth_service.change_user_password(
        user_id=current_user["id"],
        current_password=password_data.current_password,
        new_password=password_data.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    return {
        "success": True,
        "message": "Password changed successfully"
    }
