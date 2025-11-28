
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.models.auth import UserLogin, UserRegister, TokenResponse, RefreshTokenRequest, ChangePasswordRequest
from app.core.models.users import UserResponse
from app.core.services.user_service import get_user_service
from app.core.auth.jwt_handler import jwt_handler, JWTError
from app.core.auth.dependencies import get_current_active_user, require_admin_or_owner, require_roles, require_functions
from app.core.utils.exceptions import APIServiceException

from datetime import datetime

import logging

security = HTTPBearer()

logger = logging.getLogger(__name__)

router = APIRouter()



@router.get("/users")
async def debug_users(user_service = Depends(get_user_service),
    current_user = Depends(get_current_active_user),
    require_roles = Depends(require_roles(["admin", "superuser"]))
):
    """Debug endpoint to check users in database."""
    try:
        users = await user_service.get_users(limit=10)
        return {
            "total_users": len(users),
            "users": [
                {
                    "id": user.user_id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                    "function": user.function,
                    "is_active": user.is_active,
                    "created_at": user.created_at,
                    "live_authorization": user.live_authorization
                } for user in users
            ]
        }
    except Exception as e:
        logger.error(f"Debug users error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/debug/test_password")
async def debug_password_verification(
    request: dict,
    user_service = Depends(get_user_service)
):
    email = request.get("email")
    password = request.get("password")
    
    user = await user_service.get_user_by_email(email)
    if not user:
        return {"error": "User not found"}
    
    from app.core.auth.jwt_handler import jwt_handler
    is_valid = jwt_handler.verify_password(password, user.hashed_password)
    
    return {
        "email": email,
        "password_length": len(password),
        "hash_length": len(user.hashed_password),
        "hash_starts_with": user.hashed_password[:20],
        "verification_result": is_valid
    }



@router.get("/debug/user/{email}")
async def debug_user_by_email(email: str, user_service = Depends(get_user_service)):
    """Debug endpoint to check specific user."""
    try:
        user = await user_service.get_user_by_email(email)
        if not user:
            return {"found": False, "email": email}
        
        return {
            "found": True,
            "user": {
                "id": user.user_id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "function": user.function,
                "is_active": user.is_active,
                "has_password": bool(user.hashed_password),
                "password_length": len(user.hashed_password) if user.hashed_password else 0,
                "created_at": user.created_at,
                "live_authorization": user.live_authorization
            }
        }
    except Exception as e:
        logger.error(f"Debug user error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get("/debug/token_info")
async def debug_token_info(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Debug endpoint to decode and inspect JWT token."""
    try:
        token = credentials.credentials
        
        # Decode without verification to see what's inside
        import jwt
        from app.config import get_settings
        settings = get_settings()
        
        # Decode token payload
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key, 
            algorithms=[settings.jwt_algorithm]
        )
        
        return {
            "token_valid": True,
            "payload": payload,
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role"),
            "function": payload.get("function"),
            "expires": payload.get("exp"),
            "issued_at": payload.get("iat"),
            "live_authorization": payload.get("live_authorization")
        }
        
    except Exception as e:
        return {
            "token_valid": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

