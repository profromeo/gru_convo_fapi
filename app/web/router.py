from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.config import get_settings
from app.core.models.auth import UserLogin
from app.core.services.user_service import get_user_service
from app.core.auth.jwt_handler import jwt_handler
from app.core.auth.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")
settings = get_settings()

@router.get("/chat")
async def chat(request: Request):
    """Serve the chat interface"""
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "api_base_url": f"{settings.chat_host}{settings.api_prefix}",
            "app_name": settings.app_name
        }
    )

@router.get("/login")
async def login_page(request: Request):
    """Serve the login page"""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "app_name": settings.app_name
        }
    )

@router.post("/login")
async def login(
    user_data: UserLogin,
    response: Response,
    user_service = Depends(get_user_service)
):
    """Handle login and set cookie"""
    user = await user_service.get_user_by_email(user_data.email)
    if not user or not user.is_active:
            return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
    
    # Verify password (simplified for this context, ideally use same logic as auth endpoint)
    password_valid = jwt_handler.verify_password(user_data.password, user.hashed_password)
    if not password_valid:
            return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})

    access_token = jwt_handler.create_access_token(user.user_id, user.email, user.role, user.function, user.live_authorization, user.tenant_uid)
    
    # Set cookie
    response = JSONResponse(content={"success": True})
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        secure=settings.is_production,
        samesite="lax"
    )
    return response

@router.get("/convo-editor")
async def convo_editor(
    request: Request,
    current_user = Depends(get_current_user)
):
    """Serve the convo editor interface"""
    return templates.TemplateResponse(
        "convo_editor.html",
        {
            "request": request,
            "api_base_url": f"{settings.chat_host}{settings.api_prefix}",
            "app_name": settings.app_name
        }
    )
