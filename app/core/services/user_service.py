# app/core/services/user_service.py
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorCollection
import uuid

from app.config import Settings
from app.core.models.users import User, UserUpdate
from app.core.auth.jwt_handler import jwt_handler
from app.core.utils.exceptions import APIServiceException
from app.db.mongodb import MongoDBManager
import uuid
from bson import ObjectId

import logging

logger = logging.getLogger(__name__)

class UserServiceError(APIServiceException):
    """User service specific exceptions."""
    pass


class UserService:
    """User management service working with MongoDB Manager."""
    
    def __init__(self, settings: Settings, mongodb_manager: MongoDBManager):
        self.settings = settings
        self.mongodb_manager = mongodb_manager
        self.logger = logging.getLogger(__name__)
        
        # Collections will be set after initialization
        self.users_collection: Optional[AsyncIOMotorCollection] = None
        self.user_sessions_collection: Optional[AsyncIOMotorCollection] = None
        
        # Security settings
        self.max_failed_attempts = 5
        self.lockout_duration_minutes = 30
    
    async def initialize(self):
        """Initialize MongoDB collections."""
        try:
            # Get database and collections
            db = self.mongodb_manager.get_auth_database()
            self.users_collection = db.users
            self.user_sessions_collection = db.user_sessions
            
            self.logger.info("User service initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing user service: {e}")
            raise UserServiceError(f"Failed to initialize user service: {str(e)}")
    
    async def create_user(self, email: str, password: str, full_name: str, role: List[str] = ["user"], function: List[str] = [], metadata: Dict[str, Any] = {}) -> User:
        """Create new user with consistent ID handling."""
        try:
            # Use string UUID instead of MongoDB ObjectId for consistency
            user_id = str(uuid.uuid4())
            hashed_password = jwt_handler.hash_password(password)
            
            user_doc = {
                "_id": user_id,  # Store as string _id, not ObjectId
                "email": email.lower().strip(),
                "full_name": full_name.strip(),
                "hashed_password": hashed_password,
                "role": role,
                "function": function,
                "is_active": True,
                "is_verified": not self.settings.require_email_verification,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
                "failed_login_attempts": 0,
                "locked_until": None,
                "metadata": metadata
            }
            
            await self.users_collection.insert_one(user_doc)
            
            # Return User with correct ID mapping
            return User(**user_doc)
            
        except Exception as e:
            self.logger.error(f"Error creating user {email}: {e}")
            raise UserServiceError(f"Failed to create user: {str(e)}")
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID with proper handling."""
        try:
            # Make sure we're searching with the right format
            self.logger.info(f"Looking up user with ID: {user_id}")
            
            # Try as string first (recommended approach)
            user_data = await self.users_collection.find_one({"_id": user_id})
            
            if not user_data:
                # Fallback: try as ObjectId if the ID looks like one
                if ObjectId.is_valid(user_id):
                    user_data = await self.users_collection.find_one({"_id": ObjectId(user_id)})
            
            if user_data:
                # Ensure the _id is converted to string for the model
                user_data["_id"] = str(user_data["_id"])
                return User(**user_data)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting user by ID {user_id}: {e}")
            return None
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user credentials with detailed debugging."""
        try:
            logger.info(f"=== AUTHENTICATE_USER DEBUG ===")
            logger.info(f"Email: {email}, Password length: {len(password)}")
            
            user = await self.get_user_by_email(email)
            if not user:
                logger.warning("User not found in authenticate_user")
                return None
            
            logger.info(f"User found: {user.email}, Active: {user.is_active}")
            
            # Check if account is locked
            if user.locked_until and user.locked_until > datetime.utcnow():
                logger.warning(f"Account locked until: {user.locked_until}")
                raise UserServiceError("Account is temporarily locked due to too many failed attempts")
            
            # Check if account is active
            if not user.is_active:
                logger.warning("Account is not active")
                raise UserServiceError("Account is disabled")
            
            # Verify password
            logger.info("Verifying password in authenticate_user...")
            password_valid = jwt_handler.verify_password(password, user.hashed_password)
            logger.info(f"Password verification result: {password_valid}")
            
            if not password_valid:
                logger.warning("Password verification failed in authenticate_user")
                await self._handle_failed_login(user.user_id)
                return None
            
            # Successful authentication
            logger.info("Authentication successful, updating login info...")
            await self._handle_successful_login(user.user_id)
            
            # Return fresh user data
            updated_user = await self.get_user_by_id(user.user_id)
            logger.info("=== AUTHENTICATE_USER SUCCESS ===")
            return updated_user
            
        except UserServiceError as e:
            logger.error(f"UserServiceError in authenticate_user: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in authenticate_user: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise UserServiceError(f"Authentication failed: {str(e)}")
    
    async def _handle_failed_login(self, user_id: str):
        """Handle failed login attempt."""
        try:
            # Increment failed attempts
            result = await self.users_collection.find_one_and_update(
                {"_id": user_id},
                {
                    "$inc": {"failed_login_attempts": 1},
                    "$set": {"updated_at": datetime.utcnow()}
                },
                return_document=True
            )
            
            if result and result["failed_login_attempts"] >= self.max_failed_attempts:
                # Lock the account
                lock_until = datetime.utcnow() + timedelta(minutes=self.lockout_duration_minutes)
                await self.users_collection.update_one(
                    {"_id": user_id},
                    {
                        "$set": {
                            "locked_until": lock_until,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                self.logger.warning(f"Account locked for user {user_id} until {lock_until}")
                
        except Exception as e:
            self.logger.error(f"Error handling failed login for user {user_id}: {e}")
    
    async def _handle_successful_login(self, user_id: str):
        """Handle successful login."""
        try:
            await self.users_collection.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "last_login": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "failed_login_attempts": 0,
                        "locked_until": None
                    }
                }
            )
        except Exception as e:
            self.logger.error(f"Error updating successful login for user {user_id}: {e}")
    
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        try:
            user_data = await self.users_collection.find_one({"email": email.lower().strip()})
            if user_data:
                return User(**user_data)
            return None
        except Exception as e:
            self.logger.error(f"Error getting user by email {email}: {e}")
            raise UserServiceError(f"Failed to get user: {str(e)}")
    
    async def update_user(self, user_id: str, updates: UserUpdate) -> Optional[User]:
        """Update user information."""
        try:
            # Prepare update document
            update_doc = {"updated_at": datetime.utcnow()}
            
            # Only update provided fields
            update_data = updates.dict(exclude_unset=True)
            for field, value in update_data.items():
                if field == "email" and value:
                    # Check if email is already taken by another user
                    existing_user = await self.get_user_by_email(value)
                    if existing_user and existing_user.user_id != user_id:
                        raise UserServiceError("Email is already taken by another user")
                    update_doc["email"] = value.lower().strip()
                elif field == "full_name" and value:
                    update_doc["full_name"] = value.strip()
                elif field in ["role", "is_active"] and value is not None:
                    update_doc[field] = value
            
            # Update user
            result = await self.users_collection.find_one_and_update(
                {"_id": user_id},
                {"$set": update_doc},
                return_document=True
            )
            
            if result:
                self.logger.info(f"Updated user {user_id}")
                return User(**result)
            
            return None
            
        except UserServiceError:
            raise
        except Exception as e:
            self.logger.error(f"Error updating user {user_id}: {e}")
            raise UserServiceError(f"Failed to update user: {str(e)}")
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete user (soft delete by deactivating)."""
        try:
            result = await self.users_collection.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                self.logger.info(f"Deactivated user {user_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting user {user_id}: {e}")
            raise UserServiceError(f"Failed to delete user: {str(e)}")
    
    async def get_users(self, 
                       skip: int = 0, 
                       limit: int = 50, 
                       role: Optional[str] = None,
                       is_active: Optional[bool] = None) -> List[User]:
        """Get list of users with filtering and pagination."""
        try:
            # Build filter
            filter_doc = {}
            if role:
                filter_doc["role"] = role
            if is_active is not None:
                filter_doc["is_active"] = is_active
            
            # Query with pagination
            cursor = self.users_collection.find(filter_doc).skip(skip).limit(limit).sort("created_at", -1)
            users_data = await cursor.to_list(length=limit)
            
            return [User(**user_data) for user_data in users_data]
            
        except Exception as e:
            self.logger.error(f"Error getting users: {e}")
            raise UserServiceError(f"Failed to get users: {str(e)}")
    
    async def count_users(self, role: Optional[str] = None, is_active: Optional[bool] = None) -> int:
        """Count users with filtering."""
        try:
            # Build filter
            filter_doc = {}
            if role:
                filter_doc["role"] = role
            if is_active is not None:
                filter_doc["is_active"] = is_active
            
            return await self.users_collection.count_documents(filter_doc)
            
        except Exception as e:
            self.logger.error(f"Error counting users: {e}")
            raise UserServiceError(f"Failed to count users: {str(e)}")
    
    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """Change user password."""
        try:
            # Get user
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserServiceError("User not found")
            
            # Verify current password
            if not jwt_handler.verify_password(current_password, user.hashed_password):
                raise UserServiceError("Current password is incorrect")
            
            # Validate new password
            if len(new_password) < self.settings.password_min_length:
                raise UserServiceError(f"New password must be at least {self.settings.password_min_length} characters long")
            
            # Hash new password
            new_hashed_password = jwt_handler.hash_password(new_password)
            
            # Update password
            result = await self.users_collection.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "hashed_password": new_hashed_password,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                self.logger.info(f"Password changed for user {user_id}")
                return True
            
            return False
            
        except UserServiceError:
            raise
        except Exception as e:
            self.logger.error(f"Error changing password for user {user_id}: {e}")
            raise UserServiceError(f"Failed to change password: {str(e)}")
    
    async def unlock_user(self, user_id: str) -> bool:
        """Manually unlock a locked user account."""
        try:
            result = await self.users_collection.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "locked_until": None,
                        "failed_login_attempts": 0,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                self.logger.info(f"Unlocked user account {user_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error unlocking user {user_id}: {e}")
            raise UserServiceError(f"Failed to unlock user: {str(e)}")
    
    async def store_refresh_token(self, user_id: str, refresh_token_jti: str, expires_at: datetime):
        """Store refresh token information for session management."""
        try:
            session_doc = {
                "user_id": user_id,
                "refresh_token_jti": refresh_token_jti,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at
            }
            
            await self.user_sessions_collection.insert_one(session_doc)
            self.logger.debug(f"Stored refresh token for user {user_id}")
            
        except Exception as e:
            self.logger.error(f"Error storing refresh token for user {user_id}: {e}")
            raise UserServiceError(f"Failed to store refresh token: {str(e)}")
    
    async def revoke_refresh_token(self, refresh_token_jti: str) -> bool:
        """Revoke a specific refresh token."""
        try:
            result = await self.user_sessions_collection.delete_one({"refresh_token_jti": refresh_token_jti})
            
            if result.deleted_count > 0:
                self.logger.debug(f"Revoked refresh token {refresh_token_jti}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error revoking refresh token {refresh_token_jti}: {e}")
            raise UserServiceError(f"Failed to revoke refresh token: {str(e)}")
    
    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all refresh tokens for a user."""
        try:
            result = await self.user_sessions_collection.delete_many({"user_id": user_id})
            
            self.logger.info(f"Revoked {result.deleted_count} tokens for user {user_id}")
            return result.deleted_count
            
        except Exception as e:
            self.logger.error(f"Error revoking all tokens for user {user_id}: {e}")
            raise UserServiceError(f"Failed to revoke user tokens: {str(e)}")
    
    async def is_refresh_token_valid(self, refresh_token_jti: str) -> bool:
        """Check if a refresh token is still valid."""
        try:
            session = await self.user_sessions_collection.find_one({"refresh_token_jti": refresh_token_jti})
            return session is not None
            
        except Exception as e:
            self.logger.error(f"Error checking refresh token validity {refresh_token_jti}: {e}")
            return False

    async def health_check(self) -> bool:
        """Check if User service is healthy."""
        try:
            # Test database connection by trying to count documents
            await self.users_collection.estimated_document_count()

            return True
        except Exception as e:
            self.logger.error(f"User service health check failed: {e}")
            return False



    async def close(self):
        """Close all connections and cleanup resources."""
        self.logger.info("Closing User service...")
        
        # Components will be closed by their respective managers
        # This method is for any User-specific cleanup 2
        
        self.logger.info("User service closed")

# Global service instance
_user_service: Optional[UserService] = None


async def get_user_service() -> UserService:
    """Get user service instance."""
    global _user_service
    if _user_service is None:
        from app.config import get_settings
        from app.dependencies import get_mongodb_manager
        
        settings = get_settings()
        mongodb_manager = await get_mongodb_manager()
        _user_service = UserService(settings, mongodb_manager)
        await _user_service.initialize()
    return _user_service