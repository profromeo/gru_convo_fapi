# app/db/mongodb.py
import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from fastapi import HTTPException
from typing import Any, Dict, Optional

from app.config import Settings
from app.core.utils.exceptions import ServiceException


class MongoDBManager:
    """MongoDB connection manager with separate auth and service databases."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None  # Service database
        self.auth_database: Optional[AsyncIOMotorDatabase] = None  # Auth database
        self.tog_database: Optional[AsyncIOMotorDatabase] = None  # DAS database

    async def connect(self):
        """Initialize MongoDB connection."""
        try:
            self.logger.info(f"Connecting to MongoDB: {self.settings.mongodb_url}")
            
            self.client = AsyncIOMotorClient(
                self.settings.mongodb_url,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000
            )
            
            # Test connection
            await self.client.admin.command('ping')
            self.logger.info("MongoDB connection established")
            
            # Initialize databases
            if self.settings.is_testing:
                service_database_name = self.settings.mongodb_test_database
                auth_database_name = self.settings.mongodb_auth_database
                tog_database_name = self.settings.mongodb_tog_database
            else:
                service_database_name = self.settings.mongodb_database
                auth_database_name =  self.settings.mongodb_auth_database
                tog_database_name = self.settings.mongodb_tog_database

            self.database = self.client[service_database_name]
            self.auth_database = self.client[auth_database_name]
            self.tog_database = self.client[tog_database_name]
            
            self.logger.info(f"Service database: {service_database_name}")
            self.logger.info(f"Auth database: {auth_database_name}")
            self.logger.info(f"DAS database: {tog_database_name}")
            
            # Initialize auth collections
            await self._initialize_auth_collections()
            
            # Initialize service collections
            await self._initialize_service_collections()
            
        except Exception as e:
            self.logger.error(f"MongoDB connection failed: {e}")
            raise ServiceException(f"MongoDB initialization failed: {str(e)}")
    
    def get_client(self) -> AsyncIOMotorClient:
        """Get MongoDB client."""
        if self.client is None:
            raise ServiceException("MongoDB client not initialized")
        return self.client
    
    def get_database(self) -> AsyncIOMotorDatabase:
        """Get service MongoDB database."""
        if self.database is None:
            raise ServiceException("MongoDB service database not initialized")
        return self.database

    def get_tog_database(self) -> AsyncIOMotorDatabase:
        """Get DAS MongoDB database."""
        if self.tog_database is None:
            raise ServiceException("MongoDB DAS database not initialized")
        return self.tog_database
    
    def get_auth_database(self) -> AsyncIOMotorDatabase:
        """Get auth MongoDB database."""
        if self.auth_database is None:
            raise ServiceException("MongoDB auth database not initialized")
        return self.auth_database
    
    async def health_check(self) -> bool:
        """Check if MongoDB connection is healthy."""
        try:
            if self.client is None:
                return False
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            self.logger.error(f"MongoDB health check failed: {e}")
            return False
    
    async def create_indexes(self, collection_configs: dict, database: Optional[AsyncIOMotorDatabase] = None):
        """Create indexes for collections."""
        try:
            target_db = database or self.database
            
            for collection_name, config in collection_configs.items():
                collection = target_db[collection_name]
                
                if "indexes" in config:
                    for index_config in config["indexes"]:
                        await collection.create_index(
                            index_config["keys"],
                            **index_config.get("options", {})
                        )
                    self.logger.info(f"Created indexes for {collection_name}")
                    
        except Exception as e:
            self.logger.error(f"Index creation failed: {e}")
            raise ServiceException(f"Index creation failed: {str(e)}")
    
    async def create_service_indexes(self, collection_configs: dict):
        """Create indexes for service database collections."""
        await self.create_indexes(collection_configs, self.database)
    
    async def create_auth_indexes(self, collection_configs: dict):
        """Create indexes for auth database collections."""
        await self.create_indexes(collection_configs, self.auth_database)
    
    async def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.database = None
            self.auth_database = None
            self.tog_database = None
            self.logger.info("MongoDB connection closed")

    async def _initialize_auth_collections(self):
        """Initialize auth database collections and indexes."""
        try:
            # Create users collection indexes
            users_collection = self.auth_database["users"]
            
            # Email index (unique)
            await users_collection.create_index("email", unique=True)
            
            # Username index (unique, sparse for optional usernames)
            await users_collection.create_index("username", unique=True, sparse=True)
            
            # Role index for queries
            await users_collection.create_index("role")
            
            # Active status index
            await users_collection.create_index("is_active")
            
            # Created at index for sorting
            await users_collection.create_index("created_at")
            
            # Tenant UID index for filtering users by tenant
            await users_collection.create_index("tenant_uid")
            
            # Create tenants collection indexes
            tenants_collection = self.auth_database["tenants"]
            
            # Tenant UID index (unique)
            await tenants_collection.create_index("tenant_uid", unique=True)
            
            # Company name index for queries
            await tenants_collection.create_index("company_name")
            
            # Contact email index
            await tenants_collection.create_index("contact_email")
            
            # Active status index
            await tenants_collection.create_index("is_active")
            
            # Created at index for sorting
            await tenants_collection.create_index("created_at")
            
            self.logger.info("Auth collections initialized with tenant indexes")
            
        except Exception as e:
            self.logger.error(f"Auth collections initialization failed: {e}")
            raise ServiceException(f"Auth collections initialization failed: {str(e)}")
    
    
    async def _initialize_service_collections(self):
        """Initialize service database collections and indexes."""
        try:
            # Create chat_convos collection indexes
            convos_collection = self.database["chat_convos"]
            
            # Convo ID index (unique)
            await convos_collection.create_index("id", unique=True)
            
            # Tenant UID index for filtering
            await convos_collection.create_index("tenant_uid")
            
            # Created by index
            await convos_collection.create_index("created_by")
            
            # Create chat_sessions collection indexes
            sessions_collection = self.database["chat_sessions"]
            
            # Session ID index (unique)
            await sessions_collection.create_index("session_id", unique=True)
            
            # Tenant UID index for filtering
            await sessions_collection.create_index("tenant_uid")
            
            # User ID index
            await sessions_collection.create_index("user_id")
            
            # Convo ID index
            await sessions_collection.create_index("convo_id")
            
            # Create ai_chat_sessions collection indexes
            ai_sessions_collection = self.database["ai_chat_sessions"]
            
            # Session ID index (unique)
            await ai_sessions_collection.create_index("session_id", unique=True)
            
            # Tenant UID index for filtering
            await ai_sessions_collection.create_index("tenant_uid")
            
            # User ID index
            await ai_sessions_collection.create_index("user_id")
            
            # Create ai_chat_history collection indexes
            ai_history_collection = self.database["ai_chat_history"]
            
            # Session ID index for querying history
            await ai_history_collection.create_index("session_id")
            
            # Tenant UID index for filtering
            await ai_history_collection.create_index("tenant_uid")
            
            # Timestamp index for sorting
            await ai_history_collection.create_index("timestamp")
            
            self.logger.info("Service collections initialized with tenant_uid indexes")
            
        except Exception as e:
            self.logger.error(f"Service collections initialization failed: {e}")
            raise ServiceException(f"Service collections initialization failed: {str(e)}")
    
    async def _create_default_admin_user(self):
        """Create default admin user if none exists."""
        # This is handled by user service
        pass


# Global instance
_mongodb_manager: Optional[MongoDBManager] = None


async def get_mongodb_manager() -> MongoDBManager:
    """Get MongoDB manager instance."""
    global _mongodb_manager
    if _mongodb_manager is None:
        raise ServiceException("MongoDB manager not initialized")
    return _mongodb_manager


async def init_mongodb(settings: Settings) -> MongoDBManager:
    """Initialize MongoDB manager."""
    global _mongodb_manager
    _mongodb_manager = MongoDBManager(settings)
    await _mongodb_manager.connect()
    return _mongodb_manager


async def close_mongodb():
    """Close MongoDB connection."""
    global _mongodb_manager
    if _mongodb_manager:
        await _mongodb_manager.close()
        _mongodb_manager = None


# Dependency functions for FastAPI
async def get_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency to get service database."""
    manager = await get_mongodb_manager()
    return manager.get_database()


async def get_auth_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency to get auth database."""
    manager = await get_mongodb_manager()
    return manager.get_auth_database()


async def get_tog_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency to get DAS database."""
    manager = await get_mongodb_manager()
    return manager.get_tog_database()
