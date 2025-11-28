from app.api.v1.endpoints import auth, convo
from fastapi import APIRouter

# Create main API router
api_router = APIRouter()

# Public endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Protected endpoints
api_router.include_router(convo.router, prefix="/convo", tags=["Convo"])