import uuid
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class User(BaseModel):
    """User model with consistent ID handling."""
    
    # Option A: Use string ID (recommended for consistency)
    id: str = Field(alias="_id")  # Maps MongoDB's _id to id field
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    full_name: str
    hashed_password: str
    role: List[str] = Field(default_factory=lambda: ["user"])  # Default to ["user"]
    function: List[str] = Field(default_factory=lambda: [])  # Default to []
    tenant_uid: Optional[str] = Field(None, description="Tenant/company identifier")
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    live_authorization: bool = True
    
    class Config:
        populate_by_name = True  # Allows both 'id' and '_id'
        arbitrary_types_allowed = True


class UserResponse(BaseModel):
    """User response model (without sensitive data)."""
    id: str
    email: EmailStr
    full_name: str
    role: List[str]
    function: List[str]
    tenant_uid: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class UserUpdate(BaseModel):
    """User update model."""
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None