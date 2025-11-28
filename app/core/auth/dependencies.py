from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.core.auth.jwt_handler import jwt_handler, JWTError
from app.core.models.auth import TokenPayload
from app.core.models.users import User
from app.core.services.user_service import get_user_service

import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()


async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenPayload:
    """Get current user from JWT token with debugging."""
    try:
        token = credentials.credentials
        logger.info(f"Received token: {token[:20]}...")
        
        payload = jwt_handler.verify_token(token, "access")
        logger.info(f"Token decoded successfully. User ID: {payload.sub}, Email: {payload.email}")
        
        return payload
    except JWTError as e:
        logger.error(f"JWT verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    payload: TokenPayload = Depends(get_current_user_payload)
) -> User:
    """Get current user with ID mismatch handling."""
    user_service = await get_user_service()
    
    # Try to find user by the ID in the token
    user = await user_service.get_user_by_id(payload.sub)
    
    if not user:
        logger.warning(f"User not found by ID: {payload.sub}, trying email fallback")
        
        # Fallback: find by email and update token ID reference
        user = await user_service.get_user_by_email(payload.email)
        
        if user:
            logger.info(f"Found user by email. Correct ID is: {user.user_id}")
            # You might want to refresh the token here with correct ID
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    return current_user


def require_roles(allowed_roles: list[str]):
    """Dependency factory for multiple role-based access control."""
    async def role_checker(current_user: User = Depends(get_current_active_user)):
        # Check if any of the user's roles match any of the allowed roles
        if not any(role in allowed_roles for role in current_user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role permissions. Required roles: {', '.join(allowed_roles)}. User roles: {', '.join(current_user.role)}"
            )
        return current_user
    return role_checker


def require_functions(allowed_functions: list[str]):
    """Dependency factory for multiple function-based access control."""
    async def function_checker(current_user: User = Depends(get_current_active_user)):
        # Check if any of the user's functions match any of the allowed functions
        if not any(function in allowed_functions for function in current_user.function):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient function permissions. Required functions: {', '.join(allowed_functions)}. User functions: {', '.join(current_user.function)}"
            )
        return current_user
    return function_checker

# Define your role dependencies
require_admin_or_owner = require_roles(["admin", "owner"])