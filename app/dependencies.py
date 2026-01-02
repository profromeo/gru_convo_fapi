import logging
from typing import Optional
from fastapi import Depends, HTTPException

from app.config import get_settings, Settings
from app.core.services.user_service import UserService
from app.db.mongodb import MongoDBManager

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.services.convo_service import ConvoService
from app.db.mongodb import get_database, get_auth_database

def get_convo_service(
    db: AsyncIOMotorDatabase = Depends(get_database),
    auth_db: AsyncIOMotorDatabase = Depends(get_auth_database)
) -> ConvoService:
    """Dependency to get convo service instance."""
    settings = get_settings()
    return ConvoService(settings, db, auth_db)


# Global service instances
_mongodb_manager: Optional[MongoDBManager] = None
_user_service: Optional[UserService] = None


logger = logging.getLogger(__name__)


async def get_mongodb_manager() -> MongoDBManager:
    """Get MongoDB manager instance."""
    global _mongodb_manager
    if _mongodb_manager is None:
        settings = get_settings()
        _mongodb_manager = MongoDBManager(settings)
        await _mongodb_manager.connect()
    return _mongodb_manager







async def get_mongodb_dependency() -> MongoDBManager:
    """FastAPI dependency for MongoDB manager."""
    try:
        return await get_mongodb_manager()
    except Exception as e:
        logger.error(f"Failed to get MongoDB manager: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "message": "MongoDB unavailable",
                "error": str(e),
                "service": "mongodb"
            }
        )



async def get_user_service() -> UserService:
    """Dependency to get user service."""
    global _user_service
    if _user_service is None:
        settings = get_settings()
        mongodb_manager = await get_mongodb_manager()
        _user_service = UserService(settings, mongodb_manager)
        await _user_service.initialize()
    return _user_service





# Service lifecycle management
async def initialize_services():
    """Initialize all services during startup."""
    logger.info("Initializing services...")
    
    try:
        # Initialize in dependency order
        logger.info("Initializing MongoDB manager...")
        await get_mongodb_manager()


        logger.info("Initializing User service...")
        await get_user_service()
        
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Service initialization failed: {e}")
        raise


async def cleanup_services():
    """Cleanup all services during shutdown."""
    global _mongodb_manager, _user_service, _flow_service
    
    logger.info("Cleaning up services...")
    
    # Close services in reverse dependency order
    try:
        
      
        if _mongodb_manager:
            logger.info("Closing MongoDB manager...")
            await _mongodb_manager.close()
            _mongodb_manager = None

        if _user_service:
            logger.info("Closing User service...")
            await _user_service.close()
            _user_service = None

           
        logger.info("Service cleanup complete")
        
    except Exception as e:
        logger.error(f"Error during service cleanup: {e}")


# Health check dependencies
async def check_service_health() -> dict:
    """Check health of all services."""
    health_status = {
        "mongodb": False,
    }
    
    errors = {}
    
    try:
        # Check MongoDB
        try:
            mongodb_manager = await get_mongodb_manager()
            health_status["mongodb"] = await mongodb_manager.health_check()
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            errors["mongodb"] = str(e)


        # Check User Service
        try:
            user_service = await get_user_service()
            health_status["user_service"] = await user_service.health_check()
        except Exception as e:
            logger.error(f"User service health check failed: {e}")
            errors["user_service"] = str(e)
        



        
    except Exception as e:
        logger.error(f"Error checking service health: {e}")
        errors["general"] = str(e)
    
    # Add error details if any
    if errors:
        health_status["errors"] = errors
    
    return health_status


async def check_critical_services() -> bool:
    """Check if critical services are healthy."""
    try:
        health = await check_service_health()
        
        # Define critical services for readiness
        critical_services = ["mongodb", "rag_service"]
        
        return all(health.get(service, False) for service in critical_services)
        
    except Exception as e:
        logger.error(f"Critical service check failed: {e}")
        return False


# Service status utilities
async def get_service_info() -> dict:
    """Get detailed information about all services."""
    settings = get_settings()
    
    info = {
        "application": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "debug": settings.debug
        },
        "services": {},
        "configuration": {

        }
    }
    
    try:
              
        health = await check_service_health()
        info["health"] = health
        
    except Exception as e:
        logger.error(f"Error getting service info: {e}")
        info["error"] = str(e)
    
    return info


# Rate limiting dependency (placeholder for future implementation)
async def rate_limit_dependency():
    """Rate limiting dependency - implement as needed."""
    # TODO: Implement rate limiting logic
    pass


# Authentication dependency (placeholder for future implementation)  
async def auth_dependency():
    """Authentication dependency - implement as needed."""
    # TODO: Implement authentication logic
    pass