from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class Tenant(BaseModel):
    """Tenant/Company model."""
    tenant_uid: str = Field(..., description="Unique tenant identifier")
    company_name: str = Field(..., description="Company/organization name")
    contact_name: str = Field(..., description="Primary contact person name")
    contact_surname: str = Field(..., description="Primary contact person surname")
    contact_email: EmailStr = Field(..., description="Primary contact email")
    contact_phone: Optional[str] = Field(None, description="Primary contact phone number")
    address: Optional[str] = Field(None, description="Company address")
    is_active: bool = Field(default=True, description="Whether the tenant is active")
    subscription_tier: Optional[str] = Field(None, description="Subscription level (e.g., 'free', 'pro', 'enterprise')")
    max_users: Optional[int] = Field(None, description="Maximum number of users allowed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional flexible data")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="User ID who created the tenant")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant_uid": "550e8400-e29b-41d4-a716-446655440000",
                "company_name": "Acme Corporation",
                "contact_name": "John",
                "contact_surname": "Doe",
                "contact_email": "john.doe@acme.com",
                "contact_phone": "+1234567890",
                "address": "123 Business St, City, Country",
                "is_active": True,
                "subscription_tier": "pro",
                "max_users": 50,
                "metadata": {"industry": "technology"}
            }
        }


class TenantCreate(BaseModel):
    """Request model for creating a tenant."""
    company_name: str = Field(..., description="Company/organization name", min_length=1, max_length=200)
    contact_name: str = Field(..., description="Primary contact person name", min_length=1, max_length=100)
    contact_surname: str = Field(..., description="Primary contact person surname", min_length=1, max_length=100)
    contact_email: EmailStr = Field(..., description="Primary contact email")
    contact_phone: Optional[str] = Field(None, description="Primary contact phone number", max_length=50)
    address: Optional[str] = Field(None, description="Company address", max_length=500)
    subscription_tier: Optional[str] = Field(None, description="Subscription level", max_length=50)
    max_users: Optional[int] = Field(None, description="Maximum number of users allowed", ge=1)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional flexible data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "Acme Corporation",
                "contact_name": "John",
                "contact_surname": "Doe",
                "contact_email": "john.doe@acme.com",
                "contact_phone": "+1234567890",
                "address": "123 Business St, City, Country",
                "subscription_tier": "pro",
                "max_users": 50
            }
        }


class TenantUpdate(BaseModel):
    """Request model for updating a tenant."""
    company_name: Optional[str] = Field(None, description="Company/organization name", min_length=1, max_length=200)
    contact_name: Optional[str] = Field(None, description="Primary contact person name", min_length=1, max_length=100)
    contact_surname: Optional[str] = Field(None, description="Primary contact person surname", min_length=1, max_length=100)
    contact_email: Optional[EmailStr] = Field(None, description="Primary contact email")
    contact_phone: Optional[str] = Field(None, description="Primary contact phone number", max_length=50)
    address: Optional[str] = Field(None, description="Company address", max_length=500)
    subscription_tier: Optional[str] = Field(None, description="Subscription level", max_length=50)
    max_users: Optional[int] = Field(None, description="Maximum number of users allowed", ge=1)
    is_active: Optional[bool] = Field(None, description="Whether the tenant is active")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional flexible data")


class TenantResponse(BaseModel):
    """Response model for tenant (without sensitive data)."""
    tenant_uid: str
    company_name: str
    contact_name: str
    contact_surname: str
    contact_email: EmailStr
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    subscription_tier: Optional[str] = None
    max_users: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TenantStatistics(BaseModel):
    """Statistics for a tenant."""
    tenant_uid: str
    company_name: str
    total_users: int = Field(..., description="Total number of users in this tenant")
    active_users: int = Field(..., description="Number of active users")
    total_convos: int = Field(default=0, description="Total number of conversations created")
    total_sessions: int = Field(default=0, description="Total number of chat sessions")
    created_at: datetime
    subscription_tier: Optional[str] = None
    max_users: Optional[int] = None
