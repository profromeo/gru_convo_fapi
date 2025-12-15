from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List, Optional
from datetime import datetime


class UserLogin(BaseModel):
    """User login request model."""
    email: EmailStr
    password: str
    tenant_uid: Optional[str] = None
    metadata : Optional[dict] = None


class UserRegister(BaseModel):
    """User registration request model."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    role: List[str]  # user, admin
    function: List[str]# e.g., ["doctor", "nurse"]
    tenant_uid: Optional[str] = None
    metadata : Optional[dict] = None


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Refresh token request model."""
    refresh_token: str


class TokenPayload(BaseModel):
    """Complete JWT token payload model."""
    sub: str  # User ID
    email: str
    role: List[str] = []
    function: List[str] = []
    tenant_uid: Optional[str] = None
    exp: datetime
    iat: datetime
    token_type: str = "access"
    live_authorization: bool = False

    
class ChangePasswordRequest(BaseModel):
    """Change password request model."""
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")
    
    @field_validator('new_password')
    def validate_new_password(cls, v, values):
        """Validate new password is different from current."""
        if 'current_password' in values and v == values['current_password']:
            raise ValueError('New password must be different from current password')
        return v
