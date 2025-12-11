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
    
    # WhatsApp/Twilio Configuration
    whatsapp_bot_enabled: bool = Field(default=True, description="Whether the WhatsApp bot is enabled for this tenant")
    twilio_account_sid: Optional[str] = Field(None, description="Twilio Account SID")
    twilio_auth_token: Optional[str] = Field(None, description="Twilio Auth Token")
    twilio_whatsapp_number: Optional[str] = Field(None, description="Twilio WhatsApp Number")

    # Dynamic Conversation Configuration
    default_convo_id: Optional[str] = Field(None, description="Default conversation flow ID")

    tenant_convo_auth_url: Optional[str] = Field(None, description="Tenant-specific auth URL")
    tenant_convo_chat_url: Optional[str] = Field(None, description="Tenant-specific chat URL")
    convo_service_email: Optional[str] = Field(None, description="Service account email for auth")
    convo_service_password: Optional[str] = Field(None, description="Service account password for auth")
    tenant_convo_login_url: Optional[str] = Field(None, description="Tenant-specific login URL")

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
                "metadata": {"industry": "technology"},
                "whatsapp_bot_enabled": True,
                "twilio_account_sid": "AC...",
                "twilio_auth_token": "...",
                "twilio_whatsapp_number": "+1234567890",
                "default_convo_id": "flow_123",
                "tenant_convo_auth_url": "https://auth.example.com/tenant_id",
                "tenant_convo_chat_url": "https://chat.example.com/tenant_id",
                "convo_service_email": "service@example.com",
                "convo_service_password": "supersecretpassword",
                "tenant_convo_login_url": "https://login.example.com/tenant_id"
            }
        }

class TenantCreate(BaseModel):
    """Model for creating a new tenant."""
    company_name: str = Field(..., description="Company/organization name")
    contact_name: str = Field(..., description="Primary contact person name")
    contact_surname: str = Field(..., description="Primary contact person surname")
    contact_email: EmailStr = Field(..., description="Primary contact email")
    contact_phone: Optional[str] = Field(None, description="Primary contact phone number")
    address: Optional[str] = Field(None, description="Company address")
    subscription_tier: Optional[str] = Field("free", description="Subscription level")
    max_users: Optional[int] = Field(5, description="Maximum number of users allowed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional flexible data")
    
    # WhatsApp/Twilio Configuration
    whatsapp_bot_enabled: bool = Field(default=True, description="Whether the WhatsApp bot is enabled")
    twilio_account_sid: Optional[str] = Field(None, description="Twilio Account SID")
    twilio_auth_token: Optional[str] = Field(None, description="Twilio Auth Token")
    twilio_whatsapp_number: Optional[str] = Field(None, description="Twilio WhatsApp Number")
    
    # Dynamic Conversation Configuration
    default_convo_id: Optional[str] = Field(None, description="Default conversation flow ID")
    tenant_convo_auth_url: Optional[str] = Field(None, description="Tenant-specific auth URL")
    tenant_convo_chat_url: Optional[str] = Field(None, description="Tenant-specific chat URL")
    convo_service_email: Optional[str] = Field(None, description="Service account email for auth")
    convo_service_password: Optional[str] = Field(None, description="Service account password for auth")
    tenant_convo_login_url: Optional[str] = Field(None, description="Tenant-specific login URL")

class TenantUpdate(BaseModel):
    """Model for updating a tenant."""
    company_name: Optional[str] = Field(None, description="Company/organization name")
    contact_name: Optional[str] = Field(None, description="Primary contact person name")
    contact_surname: Optional[str] = Field(None, description="Primary contact person surname")
    contact_email: Optional[EmailStr] = Field(None, description="Primary contact email")
    contact_phone: Optional[str] = Field(None, description="Primary contact phone number")
    address: Optional[str] = Field(None, description="Company address")
    is_active: Optional[bool] = Field(None, description="Whether the tenant is active")
    subscription_tier: Optional[str] = Field(None, description="Subscription level")
    max_users: Optional[int] = Field(None, description="Maximum number of users allowed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional flexible data")
    
    # WhatsApp/Twilio Configuration
    whatsapp_bot_enabled: Optional[bool] = Field(None, description="Whether the WhatsApp bot is enabled")
    twilio_account_sid: Optional[str] = Field(None, description="Twilio Account SID")
    twilio_auth_token: Optional[str] = Field(None, description="Twilio Auth Token")
    twilio_whatsapp_number: Optional[str] = Field(None, description="Twilio WhatsApp Number")
    
    # Dynamic Conversation Configuration
    default_convo_id: Optional[str] = Field(None, description="Default conversation flow ID")
    tenant_convo_auth_url: Optional[str] = Field(None, description="Tenant-specific auth URL")
    tenant_convo_chat_url: Optional[str] = Field(None, description="Tenant-specific chat URL")
    convo_service_email: Optional[str] = Field(None, description="Service account email for auth")
    convo_service_password: Optional[str] = Field(None, description="Service account password for auth")
    tenant_convo_login_url: Optional[str] = Field(None, description="Tenant-specific login URL")

class TenantResponse(Tenant):
    """Response model for tenant data."""
    pass

class TenantStatistics(BaseModel):
    """Model for tenant usage statistics."""
    tenant_uid: str
    company_name: str
    total_users: int
    active_users: int
    total_convos: int
    total_sessions: int
    created_at: datetime
    subscription_tier: Optional[str] = None
    max_users: Optional[int] = None
