from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import jwt
from passlib.context import CryptContext

from app.config import get_settings
from app.core.models.auth import TokenPayload
from app.core.utils.exceptions import APIServiceException
import logging

class JWTError(APIServiceException):
    """JWT-related exceptions."""
    pass


class JWTHandler:
    """JWT token handler."""
    
    def __init__(self):
        self.settings = get_settings()
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.logger = logging.getLogger(__name__)

    def create_access_token(self, user_id: str, email: str, role: List[str], function: List[str], live_authorization: bool, tenant_uid: Optional[str] = None) -> str:
        """Create access token."""
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.settings.jwt_access_token_expire_minutes)
        
        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "function": function,
            "tenant_uid": tenant_uid,
            "exp": expire,
            "iat": now,
            "token_type": "access",
            "live_authorization": live_authorization
        }
        
        return jwt.encode(
            payload, 
            self.settings.jwt_secret_key, 
            algorithm=self.settings.jwt_algorithm
        )
    
    def create_refresh_token(self, user_id: str, email: str, role: List[str], function: List[str], live_authorization: bool, tenant_uid: Optional[str] = None) -> str:
        """Create refresh token."""
        now = datetime.utcnow()
        expire = now + timedelta(days=self.settings.jwt_refresh_token_expire_days)
        
        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "function": function,
            "tenant_uid": tenant_uid,
            "exp": expire,
            "iat": now,
            "token_type": "refresh",
            "live_authorization": live_authorization
        }
        
        return jwt.encode(
            payload, 
            self.settings.jwt_secret_key, 
            algorithm=self.settings.jwt_algorithm
        )
    
    def verify_token(self, token: str, token_type: str = "access") -> TokenPayload:
        """Verify and decode token."""
        try:
            payload = jwt.decode(
                token, 
                self.settings.jwt_secret_key, 
                algorithms=[self.settings.jwt_algorithm]
            )
            
            if payload.get("token_type") != token_type:
                raise JWTError("Invalid token type")
            
            return TokenPayload(**payload)
            
        except jwt.ExpiredSignatureError:
            raise JWTError("Token has expired")
        except jwt.InvalidTokenError:
            raise JWTError("Invalid token")
    
    def hash_password(self, password: str) -> str:
        """Hash password."""
        hashed = self.pwd_context.hash(password)
        self.logger.debug(f"Password hashed successfully, length: {len(hashed)}")
        return hashed
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password."""
        try:
            result = self.pwd_context.verify(plain_password, hashed_password)
            self.logger.debug(f"Password verification result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Password verification error: {str(e)}")
            return False


# Global instance
jwt_handler = JWTHandler()