# app/core/services/tenant_service.py
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorCollection
import uuid

from app.config import Settings
from app.core.models.tenant import (
    Tenant,
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantStatistics
)
from app.core.utils.exceptions import APIServiceException
from app.db.mongodb import MongoDBManager

logger = logging.getLogger(__name__)


class TenantServiceError(APIServiceException):
    """Tenant service specific exceptions."""
    pass


class TenantService:
    """Tenant management service."""
    
    def __init__(self, settings: Settings, mongodb_manager: MongoDBManager):
        self.settings = settings
        self.mongodb_manager = mongodb_manager
        self.logger = logging.getLogger(__name__)
        
        # Collections will be set after initialization
        self.tenants_collection: Optional[AsyncIOMotorCollection] = None
        self.users_collection: Optional[AsyncIOMotorCollection] = None
        self.convos_collection: Optional[AsyncIOMotorCollection] = None
        self.sessions_collection: Optional[AsyncIOMotorCollection] = None
    
    async def initialize(self):
        """Initialize MongoDB collections."""
        try:
            # Get auth database for tenants and users
            auth_db = self.mongodb_manager.get_auth_database()
            self.tenants_collection = auth_db.tenants
            self.users_collection = auth_db.users
            
            # Get service database for convos and sessions
            service_db = self.mongodb_manager.get_database()
            self.convos_collection = service_db.chat_convos
            self.sessions_collection = service_db.chat_sessions
            
            self.logger.info("Tenant service initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing tenant service: {e}")
            raise TenantServiceError(f"Failed to initialize tenant service: {str(e)}")
    
    async def create_tenant(
        self,
        tenant_data: TenantCreate,
        created_by: Optional[str] = None
    ) -> Tenant:
        """Create a new tenant."""
        try:
            # Generate tenant UID
            tenant_uid = str(uuid.uuid4())
            
            # Check if company name already exists
            existing = await self.tenants_collection.find_one(
                {"company_name": tenant_data.company_name}
            )
            if existing:
                raise TenantServiceError(
                    f"Tenant with company name '{tenant_data.company_name}' already exists"
                )
            
            # Create tenant document
            tenant_doc = {
                "tenant_uid": tenant_uid,
                "company_name": tenant_data.company_name,
                "contact_name": tenant_data.contact_name,
                "contact_surname": tenant_data.contact_surname,
                "contact_email": tenant_data.contact_email.lower(),
                "contact_phone": tenant_data.contact_phone,
                "address": tenant_data.address,
                "is_active": True,
                "subscription_tier": tenant_data.subscription_tier,
                "max_users": tenant_data.max_users,
                "metadata": tenant_data.metadata,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": created_by
            }
            
            await self.tenants_collection.insert_one(tenant_doc)
            
            self.logger.info(f"Created tenant: {tenant_uid} ({tenant_data.company_name})")
            return Tenant(**tenant_doc)
            
        except TenantServiceError:
            raise
        except Exception as e:
            self.logger.error(f"Error creating tenant: {e}")
            raise TenantServiceError(f"Failed to create tenant: {str(e)}")
    
    async def get_tenant(self, tenant_uid: str) -> Optional[Tenant]:
        """Get tenant by UID."""
        try:
            tenant_data = await self.tenants_collection.find_one(
                {"tenant_uid": tenant_uid}
            )
            if tenant_data:
                tenant_data.pop("_id", None)
                return Tenant(**tenant_data)
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting tenant {tenant_uid}: {e}")
            raise TenantServiceError(f"Failed to get tenant: {str(e)}")
    
    async def get_tenant_by_company_name(self, company_name: str) -> Optional[Tenant]:
        """Get tenant by company name."""
        try:
            tenant_data = await self.tenants_collection.find_one(
                {"company_name": company_name}
            )
            if tenant_data:
                tenant_data.pop("_id", None)
                return Tenant(**tenant_data)
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting tenant by company name {company_name}: {e}")
            raise TenantServiceError(f"Failed to get tenant: {str(e)}")
    
    async def list_tenants(
        self,
        skip: int = 0,
        limit: int = 50,
        is_active: Optional[bool] = None,
        subscription_tier: Optional[str] = None
    ) -> List[Tenant]:
        """List all tenants with filtering and pagination."""
        try:
            # Build filter
            filter_doc = {}
            if is_active is not None:
                filter_doc["is_active"] = is_active
            if subscription_tier:
                filter_doc["subscription_tier"] = subscription_tier
            
            # Query with pagination
            cursor = self.tenants_collection.find(filter_doc).skip(skip).limit(limit).sort("created_at", -1)
            tenants_data = await cursor.to_list(length=limit)
            
            tenants = []
            for tenant_data in tenants_data:
                tenant_data.pop("_id", None)
                tenants.append(Tenant(**tenant_data))
            
            return tenants
            
        except Exception as e:
            self.logger.error(f"Error listing tenants: {e}")
            raise TenantServiceError(f"Failed to list tenants: {str(e)}")
    
    async def update_tenant(
        self,
        tenant_uid: str,
        updates: TenantUpdate
    ) -> Optional[Tenant]:
        """Update tenant information."""
        try:
            # Check if tenant exists
            existing = await self.get_tenant(tenant_uid)
            if not existing:
                raise TenantServiceError(f"Tenant '{tenant_uid}' not found")
            
            # Prepare update document
            update_doc = {"updated_at": datetime.utcnow()}
            
            # Only update provided fields
            update_data = updates.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if field == "company_name" and value:
                    # Check if company name is already taken by another tenant
                    existing_tenant = await self.get_tenant_by_company_name(value)
                    if existing_tenant and existing_tenant.tenant_uid != tenant_uid:
                        raise TenantServiceError("Company name is already taken by another tenant")
                    update_doc["company_name"] = value
                elif field == "contact_email" and value:
                    update_doc["contact_email"] = value.lower()
                elif field == "metadata" and value is not None:
                    # Merge metadata instead of replacing
                    update_doc["metadata"] = {**existing.metadata, **value}
                elif value is not None:
                    update_doc[field] = value
            
            # Update tenant
            result = await self.tenants_collection.find_one_and_update(
                {"tenant_uid": tenant_uid},
                {"$set": update_doc},
                return_document=True
            )
            
            if result:
                result.pop("_id", None)
                self.logger.info(f"Updated tenant {tenant_uid}")
                return Tenant(**result)
            
            return None
            
        except TenantServiceError:
            raise
        except Exception as e:
            self.logger.error(f"Error updating tenant {tenant_uid}: {e}")
            raise TenantServiceError(f"Failed to update tenant: {str(e)}")
    
    async def delete_tenant(self, tenant_uid: str) -> bool:
        """Delete tenant (soft delete by deactivating)."""
        try:
            result = await self.tenants_collection.update_one(
                {"tenant_uid": tenant_uid},
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                self.logger.info(f"Deactivated tenant {tenant_uid}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting tenant {tenant_uid}: {e}")
            raise TenantServiceError(f"Failed to delete tenant: {str(e)}")
    
    async def activate_tenant(self, tenant_uid: str) -> bool:
        """Activate a deactivated tenant."""
        try:
            result = await self.tenants_collection.update_one(
                {"tenant_uid": tenant_uid},
                {
                    "$set": {
                        "is_active": True,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                self.logger.info(f"Activated tenant {tenant_uid}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error activating tenant {tenant_uid}: {e}")
            raise TenantServiceError(f"Failed to activate tenant: {str(e)}")
    
    async def deactivate_tenant(self, tenant_uid: str) -> bool:
        """Deactivate a tenant."""
        return await self.delete_tenant(tenant_uid)
    
    async def get_tenant_users(
        self,
        tenant_uid: str,
        skip: int = 0,
        limit: int = 50,
        is_active: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """Get all users belonging to a tenant."""
        try:
            # Build filter
            filter_doc = {"tenant_uid": tenant_uid}
            if is_active is not None:
                filter_doc["is_active"] = is_active
            
            # Query with pagination
            cursor = self.users_collection.find(filter_doc).skip(skip).limit(limit).sort("created_at", -1)
            users_data = await cursor.to_list(length=limit)
            
            # Remove sensitive data
            for user in users_data:
                user.pop("hashed_password", None)
                user.pop("_id", None)
            
            return users_data
            
        except Exception as e:
            self.logger.error(f"Error getting tenant users for {tenant_uid}: {e}")
            raise TenantServiceError(f"Failed to get tenant users: {str(e)}")
    
    async def get_tenant_user_count(
        self,
        tenant_uid: str,
        is_active: Optional[bool] = None
    ) -> int:
        """Count users in a tenant."""
        try:
            # Build filter
            filter_doc = {"tenant_uid": tenant_uid}
            if is_active is not None:
                filter_doc["is_active"] = is_active
            
            return await self.users_collection.count_documents(filter_doc)
            
        except Exception as e:
            self.logger.error(f"Error counting tenant users for {tenant_uid}: {e}")
            raise TenantServiceError(f"Failed to count tenant users: {str(e)}")
    
    async def assign_user_to_tenant(
        self,
        user_id: str,
        tenant_uid: str
    ) -> bool:
        """Assign a user to a tenant."""
        try:
            # Check if tenant exists
            tenant = await self.get_tenant(tenant_uid)
            if not tenant:
                raise TenantServiceError(f"Tenant '{tenant_uid}' not found")
            
            # Check if tenant is active
            if not tenant.is_active:
                raise TenantServiceError(f"Tenant '{tenant_uid}' is not active")
            
            # Check max users limit
            if tenant.max_users:
                current_count = await self.get_tenant_user_count(tenant_uid, is_active=True)
                if current_count >= tenant.max_users:
                    raise TenantServiceError(
                        f"Tenant has reached maximum user limit ({tenant.max_users})"
                    )
            
            # Update user
            result = await self.users_collection.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "tenant_uid": tenant_uid,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                self.logger.info(f"Assigned user {user_id} to tenant {tenant_uid}")
                return True
            
            return False
            
        except TenantServiceError:
            raise
        except Exception as e:
            self.logger.error(f"Error assigning user {user_id} to tenant {tenant_uid}: {e}")
            raise TenantServiceError(f"Failed to assign user to tenant: {str(e)}")
    
    async def remove_user_from_tenant(
        self,
        user_id: str,
        tenant_uid: str
    ) -> bool:
        """Remove a user from a tenant."""
        try:
            # Update user
            result = await self.users_collection.update_one(
                {"_id": user_id, "tenant_uid": tenant_uid},
                {
                    "$set": {
                        "tenant_uid": None,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                self.logger.info(f"Removed user {user_id} from tenant {tenant_uid}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error removing user {user_id} from tenant {tenant_uid}: {e}")
            raise TenantServiceError(f"Failed to remove user from tenant: {str(e)}")
    
    async def get_tenant_statistics(self, tenant_uid: str) -> TenantStatistics:
        """Get usage statistics for a tenant."""
        try:
            # Get tenant
            tenant = await self.get_tenant(tenant_uid)
            if not tenant:
                raise TenantServiceError(f"Tenant '{tenant_uid}' not found")
            
            # Count users
            total_users = await self.get_tenant_user_count(tenant_uid)
            active_users = await self.get_tenant_user_count(tenant_uid, is_active=True)
            
            # Count convos
            total_convos = await self.convos_collection.count_documents(
                {"tenant_uid": tenant_uid}
            )
            
            # Count sessions
            total_sessions = await self.sessions_collection.count_documents(
                {"tenant_uid": tenant_uid}
            )
            
            return TenantStatistics(
                tenant_uid=tenant_uid,
                company_name=tenant.company_name,
                total_users=total_users,
                active_users=active_users,
                total_convos=total_convos,
                total_sessions=total_sessions,
                created_at=tenant.created_at,
                subscription_tier=tenant.subscription_tier,
                max_users=tenant.max_users
            )
            
        except TenantServiceError:
            raise
        except Exception as e:
            self.logger.error(f"Error getting tenant statistics for {tenant_uid}: {e}")
            raise TenantServiceError(f"Failed to get tenant statistics: {str(e)}")
    
    async def count_tenants(
        self,
        is_active: Optional[bool] = None,
        subscription_tier: Optional[str] = None
    ) -> int:
        """Count tenants with filtering."""
        try:
            # Build filter
            filter_doc = {}
            if is_active is not None:
                filter_doc["is_active"] = is_active
            if subscription_tier:
                filter_doc["subscription_tier"] = subscription_tier
            
            return await self.tenants_collection.count_documents(filter_doc)
            
        except Exception as e:
            self.logger.error(f"Error counting tenants: {e}")
            raise TenantServiceError(f"Failed to count tenants: {str(e)}")


# Global service instance
_tenant_service: Optional[TenantService] = None


async def get_tenant_service() -> TenantService:
    """Get tenant service instance."""
    global _tenant_service
    if _tenant_service is None:
        from app.config import get_settings
        from app.dependencies import get_mongodb_manager
        
        settings = get_settings()
        mongodb_manager = await get_mongodb_manager()
        _tenant_service = TenantService(settings, mongodb_manager)
        await _tenant_service.initialize()
    return _tenant_service
