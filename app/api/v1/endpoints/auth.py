
from app.core.models.convo import ChatRequest, ChatResponse
from app.core.services.convo_service import ConvoService
from app.dependencies import get_convo_service
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




@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister,
    user_service = Depends(get_user_service),

):
    """Register new user."""
    try:
        logger.info(f"Attempting to register user: {user_data.email}")
        
        user = await user_service.create_user(
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role=user_data.role,
            function=user_data.function,
            metadata = user_data.metadata if user_data.metadata else {}
        )
        
        logger.info(f"Successfully registered user: {user.email} with ID: {user.user_id}")
        return UserResponse(**user.dict())
        
    except APIServiceException as e:
        logger.error(f"Registration failed for {user_data.email}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected registration error for {user_data.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    user_service = Depends(get_user_service)
):
    """Login user with detailed debugging."""
    try:
        logger.info(f"=== LOGIN DEBUG START ===")
        logger.info(f"Email received: '{user_data.email}'")
        logger.info(f"Password length: {len(user_data.password)}")
        
        # Step 1: Check if user exists
        logger.info("Step 1: Looking up user by email...")
        user = await user_service.get_user_by_email(user_data.email)
        
        if not user:
            logger.warning(f"Step 1 FAILED: User not found for email: {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        logger.info(f"Step 1 SUCCESS: User found - ID: {user.user_id}, Active: {user.is_active}")
        
        # Step 2: Check if account is active
        if not user.is_active:
            logger.warning(f"Step 2 FAILED: Account inactive for user: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled"
            )
        
        logger.info("Step 2 SUCCESS: Account is active")
        
        # Step 3: Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            logger.warning(f"Step 3 FAILED: Account locked until {user.locked_until}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is temporarily locked"
            )
        
        logger.info("Step 3 SUCCESS: Account not locked")
        
        # Step 4: Verify password
        logger.info("Step 4: Verifying password...")
        from app.core.auth.jwt_handler import jwt_handler
        
        password_valid = jwt_handler.verify_password(user_data.password, user.hashed_password)
        logger.info(f"Step 4 RESULT: Password valid = {password_valid}")
        
        if not password_valid:
            logger.warning("Step 4 FAILED: Password verification failed")
            # Note: We're calling authenticate_user which might have different logic
            # Let's check what authenticate_user returns
            auth_result = await user_service.authenticate_user(user_data.email, user_data.password)
            logger.info(f"authenticate_user result: {auth_result is not None}")
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        logger.info("Step 4 SUCCESS: Password verified")
        
        # Step 5: Create tokens
        logger.info("Step 5: Creating tokens...")
        try:
            access_token = jwt_handler.create_access_token(user.user_id, user.email, user.role, user.function, user.live_authorization, user.tenant_uid)
            refresh_token = jwt_handler.create_refresh_token(user.user_id, user.email, user.role, user.function, user.live_authorization, user.tenant_uid)
            logger.info("Step 5 SUCCESS: Tokens created")
            
            # Step 6: Update last login
            await user_service._handle_successful_login(user.user_id)
            logger.info("Step 6 SUCCESS: Last login updated")
            
            logger.info("=== LOGIN DEBUG SUCCESS ===")
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=jwt_handler.settings.jwt_access_token_expire_minutes * 60
            )
            
        except Exception as token_error:
            logger.error(f"Step 5 FAILED: Token creation error: {str(token_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token creation failed"
            )
        
    except HTTPException as he:
        logger.error(f"=== LOGIN DEBUG FAILED === HTTP {he.status_code}: {he.detail}")
        raise
    except Exception as e:
        logger.error(f"=== LOGIN DEBUG ERROR === Unexpected error: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
        



@router.post("/login_register_session", response_model=ChatResponse)
async def login_register_session(
    user_data: UserLogin,
    service: ConvoService = Depends(get_convo_service),
    user_service = Depends(get_user_service)
):
    """Login user with detailed debugging."""
    try:
        logger.info(f"=== LOGIN DEBUG START ===")
        logger.info(f"Email received: '{user_data.email}'")
        logger.info(f"Password length: {len(user_data.password)}")
        
        # Step 1: Check if user exists
        logger.info("Step 1: Looking up user by email...")
        user = await user_service.get_user_by_email(user_data.email)
        
        if not user:
            logger.warning(f"Step 1 FAILED: User not found for email: {user_data.email}")
            user = await user_service.create_user(
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.email,
            role=['user'],
            function=[],
            metadata = {"origin": "chat_interface_debug_login_register"}
            )
        
        user = await user_service.get_user_by_email(user_data.email)
        
        logger.info(f"Step 1 SUCCESS: User found - ID: {user.user_id}, Active: {user.is_active}")
        
        
        
        if not user:
            logger.warning(f"Step 1 FAILED: User not found for email: {user_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Step 2: Check if account is active
        if not user.is_active:
            logger.warning(f"Step 2 FAILED: Account inactive for user: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled"
            )
        
        logger.info("Step 2 SUCCESS: Account is active")
        
        # Step 3: Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            logger.warning(f"Step 3 FAILED: Account locked until {user.locked_until}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is temporarily locked"
            )
        
        logger.info("Step 3 SUCCESS: Account not locked")
        
        # Step 4: Verify password
        logger.info("Step 4: Verifying password...")
        from app.core.auth.jwt_handler import jwt_handler
        
        password_valid = jwt_handler.verify_password(user_data.password, user.hashed_password)
        logger.info(f"Step 4 RESULT: Password valid = {password_valid}")
        
        if not password_valid:
            logger.warning("Step 4 FAILED: Password verification failed")
            # Note: We're calling authenticate_user which might have different logic
            # Let's check what authenticate_user returns
            auth_result = await user_service.authenticate_user(user_data.email, user_data.password)
            logger.info(f"authenticate_user result: {auth_result is not None}")
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        logger.info("Step 4 SUCCESS: Password verified")
        
        # Step 5: Create tokens
        logger.info("Step 5: Creating tokens...")
        try:
            access_token = jwt_handler.create_access_token(user.user_id, user.email, user.role, user.function, user.live_authorization, user.tenant_uid)
            refresh_token = jwt_handler.create_refresh_token(user.user_id, user.email, user.role, user.function, user.live_authorization, user.tenant_uid)
            logger.info("Step 5 SUCCESS: Tokens created")
            
            # Step 6: Update last login
            await user_service._handle_successful_login(user.user_id)
            logger.info("Step 6 SUCCESS: Last login updated")
            
            logger.info("=== LOGIN DEBUG SUCCESS ===")
            
            session = await service.get_chat_session(user_data.metadata.get('session_id'))
            if not session:
                        
                new_chat_request = ChatRequest(
                    user_id=user.user_id,
                    convo_id=user_data.metadata['convo_id'],     
                )
                
                response = await service.start_chat_session(new_chat_request)
            else:

                response = await service.continue_chat_session(user_data.metadata['session_id'],user_data.metadata['user_message'])
                
            response.access_token = access_token
            response.refresh_token = refresh_token
            response.expires_in = jwt_handler.settings.jwt_access_token_expire_minutes * 60
            response.token_type = "Bearer"  
            
            return response
        
        except Exception as token_error:
            logger.error(f"Step 5 FAILED: Token creation error: {str(token_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token creation failed"
            )
        
    except HTTPException as he:
        logger.error(f"=== LOGIN DEBUG FAILED === HTTP {he.status_code}: {he.detail}")
        raise
    except Exception as e:
        logger.error(f"=== LOGIN DEBUG ERROR === Unexpected error: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_data: RefreshTokenRequest):
    """Refresh access token."""
    try:
        payload = jwt_handler.verify_token(refresh_data.refresh_token, "refresh")
        
        access_token = jwt_handler.create_access_token(
            payload.sub, payload.email, payload.role, payload.function
        , payload.live_authorization, payload.tenant_uid)
        refresh_token = jwt_handler.create_refresh_token(
            payload.sub, payload.email, payload.role, payload.function
        , payload.live_authorization, payload.tenant_uid)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=jwt_handler.settings.jwt_access_token_expire_minutes * 60
        )
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_active_user)
):
    """Get current user information."""
    return UserResponse(**current_user.dict())



@router.post("/change_password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user = Depends(get_current_active_user),
    user_service = Depends(get_user_service)
):
    """
    Change user password.
    
    Requires authentication. User can only change their own password.
    """
    try:
        success = await user_service.change_password(
            user_id=current_user.user_id,
            current_password=password_data.current_password,
            new_password=password_data.new_password
        )
        
        if success:
            logger.info(f"Password changed successfully for user {current_user.email}")
            return {
                "message": "Password changed successfully",
                "user_id": current_user.user_id,
                "email": current_user.email
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to change password"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password for user {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
