from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.core.models.tenant import (
    Tenant,
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantStatistics
)
from app.core.services.tenant_service import TenantService, get_tenant_service
from app.core.auth.dependencies import get_current_user
from app.core.models.users import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin role."""
    if "admin" not in current_user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_tenant_access(tenant_uid: str, current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require tenant access (admin or tenant member)."""
    if "admin" not in current_user.role and current_user.tenant_uid != tenant_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this tenant"
        )
    return current_user


# Basic CRUD Endpoints

@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant: TenantCreate,
    service: TenantService = Depends(get_tenant_service),
    current_user: User = Depends(require_admin)
):
    """
    Create a new tenant.
    
    Requires admin role.
    """
    try:
        result = await service.create_tenant(tenant, created_by=current_user.user_id)
        logger.info(f"Admin {current_user.email} created tenant: {result.tenant_uid}")
        return TenantResponse(**result.model_dump())
    except Exception as e:
        logger.error(f"Error creating tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    subscription_tier: Optional[str] = Query(None, description="Filter by subscription tier"),
    service: TenantService = Depends(get_tenant_service),
    current_user: User = Depends(require_admin)
):
    """
    List all tenants.
    
    Requires admin role.
    """
    try:
        tenants = await service.list_tenants(
            skip=skip,
            limit=limit,
            is_active=is_active,
            subscription_tier=subscription_tier
        )
        return [TenantResponse(**t.model_dump()) for t in tenants]
    except Exception as e:
        logger.error(f"Error listing tenants: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tenants"
        )


@router.get("/tenants/{tenant_uid}", response_model=TenantResponse)
async def get_tenant(
    tenant_uid: str,
    service: TenantService = Depends(get_tenant_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific tenant by UID.
    
    Admin can access any tenant. Regular users can only access their own tenant.
    """
    try:
        # Check access
        if "admin" not in current_user.role and current_user.tenant_uid != tenant_uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this tenant"
            )
        
        tenant = await service.get_tenant(tenant_uid)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_uid}' not found"
            )
        return TenantResponse(**tenant.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tenant"
        )


@router.put("/tenants/{tenant_uid}", response_model=TenantResponse)
async def update_tenant(
    tenant_uid: str,
    updates: TenantUpdate,
    service: TenantService = Depends(get_tenant_service),
    current_user: User = Depends(get_current_user)
):
    """
    Update a tenant.
    
    Admin can update any tenant. Tenant members can update their own tenant.
    """
    try:
        # Check access
        if "admin" not in current_user.role and current_user.tenant_uid != tenant_uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this tenant"
            )
        
        result = await service.update_tenant(tenant_uid, updates)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_uid}' not found"
            )
        logger.info(f"User {current_user.email} updated tenant: {tenant_uid}")
        return TenantResponse(**result.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/tenants/{tenant_uid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_uid: str,
    service: TenantService = Depends(get_tenant_service),
    current_user: User = Depends(require_admin)
):
    """
    Delete (deactivate) a tenant.
    
    Requires admin role.
    """
    try:
        success = await service.delete_tenant(tenant_uid)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_uid}' not found"
            )
        logger.info(f"Admin {current_user.email} deleted tenant: {tenant_uid}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Administrative Endpoints

@router.get("/tenants/{tenant_uid}/users")
async def get_tenant_users(
    tenant_uid: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    service: TenantService = Depends(get_tenant_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get all users belonging to a tenant.
    
    Admin can access any tenant. Regular users can only access their own tenant.
    """
    try:
        # Check access
        if "admin" not in current_user.role and current_user.tenant_uid != tenant_uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this tenant"
            )
        
        users = await service.get_tenant_users(tenant_uid, skip=skip, limit=limit, is_active=is_active)
        return users
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tenant users"
        )


@router.post("/tenants/{tenant_uid}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def assign_user_to_tenant(
    tenant_uid: str,
    user_id: str,
    service: TenantService = Depends(get_tenant_service),
    current_user: User = Depends(require_admin)
):
    """
    Assign a user to a tenant.
    
    Requires admin role.
    """
    try:
        success = await service.assign_user_to_tenant(user_id, tenant_uid)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' not found"
            )
        logger.info(f"Admin {current_user.email} assigned user {user_id} to tenant {tenant_uid}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning user to tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/tenants/{tenant_uid}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_tenant(
    tenant_uid: str,
    user_id: str,
    service: TenantService = Depends(get_tenant_service),
    current_user: User = Depends(require_admin)
):
    """
    Remove a user from a tenant.
    
    Requires admin role.
    """
    try:
        success = await service.remove_user_from_tenant(user_id, tenant_uid)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' not found in tenant '{tenant_uid}'"
            )
        logger.info(f"Admin {current_user.email} removed user {user_id} from tenant {tenant_uid}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing user from tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/tenants/{tenant_uid}/statistics", response_model=TenantStatistics)
async def get_tenant_statistics(
    tenant_uid: str,
    service: TenantService = Depends(get_tenant_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get usage statistics for a tenant.
    
    Admin can access any tenant. Regular users can only access their own tenant.
    """
    try:
        # Check access
        if "admin" not in current_user.role and current_user.tenant_uid != tenant_uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this tenant"
            )
        
        stats = await service.get_tenant_statistics(tenant_uid)
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tenant statistics"
        )


@router.post("/tenants/{tenant_uid}/activate", status_code=status.HTTP_204_NO_CONTENT)
async def activate_tenant(
    tenant_uid: str,
    service: TenantService = Depends(get_tenant_service),
    current_user: User = Depends(require_admin)
):
    """
    Activate a deactivated tenant.
    
    Requires admin role.
    """
    try:
        success = await service.activate_tenant(tenant_uid)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_uid}' not found"
            )
        logger.info(f"Admin {current_user.email} activated tenant: {tenant_uid}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/tenants/{tenant_uid}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_tenant(
    tenant_uid: str,
    service: TenantService = Depends(get_tenant_service),
    current_user: User = Depends(require_admin)
):
    """
    Deactivate a tenant.
    
    Requires admin role.
    """
    try:
        success = await service.deactivate_tenant(tenant_uid)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{tenant_uid}' not found"
            )
        logger.info(f"Admin {current_user.email} deactivated tenant: {tenant_uid}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
