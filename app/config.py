import os
from pydantic_settings import BaseSettings
from typing import List, Optional, Type, Dict, Any
from functools import lru_cache
from enum import Enum
from pathlib import Path

class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    """Base settings that are common across all environments."""
    
    # App metadata - rarely changes across environments
    app_name: str = "gruCode Convo Service"
    app_version: str = "1.0.0"
    app_description: str = "An gruCode API service that handles chat coversations and management."
    api_prefix: str = "/api/v1"
    
    # Authentication algorithms - stable across environments
    jwt_algorithm: str = "HS256"
    password_hash_algorithm: str = "bcrypt"
    
    ai_system_user: str = "chatbot@grucode.dev"
    ai_system_password: str = "botchat@grucode.dev"
    
    # Password requirements - consistent across environments
    password_min_length: int = 8
    
    # Static paths - same across environments
    base_dir: Path = Path(__file__).parent.parent
    mappings_dir: Path = base_dir / "mappings"
    
    # Log format - consistent formatting
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Database names - defined once
    mongodb_database: str = "gru_convo"
    mongodb_auth_database: str = "gru_convo"
    mongodb_test_database: str = "gru_convo"
    mongodb_tog_database: str = "arb_togmatix_shop"
   
    # Environment tracking
    environment: Environment = Environment.DEVELOPMENT
    
    # Properties that might be overridden by environment-specific settings
    debug: bool = True
    host: str = "0.0.0.0"
    chat_host: str = "http://localhost:4466"
    port: int = 4466
    workers: int = 1
    allowed_origins: List[str] = ["*"]
    
    # JWT settings that might vary by environment
    jwt_secret_key: str = "gruCode2d8e90c07810df0073f2007f912ca3adeb2da51e81197b02f0b8c1d3e2c4a5f"
    jwt_access_token_expire_minutes: int = 2880
    jwt_refresh_token_expire_days: int = 90
    
    # User management settings
    allow_user_registration: bool = True
    require_email_verification: bool = False
    
    # Database connection
    mongodb_url: str = 'mongodb://10.0.1.4:27017,10.0.0.4:27017,10.0.1.3:27017/?retryWrites=true&replicaSet=rs_togmatix_mdn&readPreference=primary&serverSelectionTimeoutMS=5000&connectTimeoutMS=10000'
    
    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10
    
    # Logging level
    log_level: str = "INFO"
    
    # Security
    secret_key: str = "your-secret-key-here"
    
    ai_service_url: str = "https://ai.grucode.dev"  # Default AI service URL
    
    @property
    def database_url(self) -> str:
        """Get database URL based on environment."""
        if self.environment == Environment.TESTING:
            return f"{self.mongodb_url.rstrip('/')}/{self.mongodb_test_database}"
        return f"{self.mongodb_url.rstrip('/')}/{self.mongodb_database}"
    
    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_testing(self) -> bool:
        return self.environment == Environment.TESTING

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class DevelopmentSettings(Settings):
    """Development environment settings."""
    
    app_name: str = "gruCode Convo Service DEV"
    
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    log_level: str = "DEBUG"
    
    # Development-specific overrides
    allowed_origins: List[str] = ["*"]
    
    # More permissive settings for development
    allow_user_registration: bool = True
    require_email_verification: bool = False
    
    # Faster token expiry for testing
    jwt_access_token_expire_minutes: int = 2880
    jwt_refresh_token_expire_days: int = 90
    
    # Development database
    mongodb_url: str = 'mongodb://10.0.1.4:27017,10.0.0.4:27017,10.0.1.3:27017/?retryWrites=true&replicaSet=rs_togmatix_mdn&readPreference=primary&serverSelectionTimeoutMS=5000&connectTimeoutMS=10000'
    # More lenient rate limiting
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 20
    
    class Config:
        env_file = ".env.development"
        env_file_encoding = "utf-8"
        case_sensitive = False


class ProductionSettings(Settings):
    """Production environment settings."""
    
    environment: Environment = Environment.PRODUCTION
    debug: bool = False
    log_level: str = "WARNING"
    workers: int = 4
    
    # Production-specific security
    allowed_origins: List[str] = [
        "https://ai.grucode.co.za",
        "https://api.ai.grucode.co.za"
    ]
    
    # Stricter user management
    require_email_verification: bool = True
    allow_user_registration: bool = False  # Might want to control this in prod
    
    # Shorter token expiry for security
    jwt_access_token_expire_minutes: int = 15  # 15 minutes
    jwt_refresh_token_expire_days: int = 7     # 7 days
    
    # Production database (should be set via environment variables)
    mongodb_url: str = "mongodb://10.0.1.4:27017,10.0.0.4:27017,10.0.1.3:27017/?retryWrites=true&replicaSet=rs_togmatix_mdn&readPreference=primary&serverSelectionTimeoutMS=5000&connectTimeoutMS=10000"
    
    
    # Stricter rate limiting
    rate_limit_per_minute: int = 30
    rate_limit_burst: int = 5
    
   
    class Config:
        env_file = ".env.production"
        env_file_encoding = "utf-8"
        case_sensitive = False


class TestingSettings(Settings):
    """Testing environment settings."""
    
    environment: Environment = Environment.TESTING
    debug: bool = True
    log_level: str = "DEBUG"
    
    # Testing-specific overrides
    allowed_origins: List[str] = ["*"]  # Allow all for testing
    
    # Fast token expiry for testing
    jwt_access_token_expire_minutes: int = 5   # 5 minutes
    jwt_refresh_token_expire_days: int = 1     # 1 day
    
    # Testing database
    mongodb_url: str = "mongodb://localhost:27017"
    
    # Permissive settings for tests
    allow_user_registration: bool = True
    require_email_verification: bool = False
    
    # High rate limits for testing
    rate_limit_per_minute: int = 1000
    rate_limit_burst: int = 100
    
   
    @property
    def database_url(self) -> str:
        """Always use test database for testing."""
        return f"{self.mongodb_url.rstrip('/')}/{self.mongodb_test_database}"
    
    class Config:
        env_file = ".env.testing"
        env_file_encoding = "utf-8"
        case_sensitive = False


class StagingSettings(Settings):
    """Staging environment settings - production-like but less strict."""
    
    environment: Environment = Environment.PRODUCTION  # Treat as production variant
    debug: bool = False
    log_level: str = "INFO"
    workers: int = 2
    
    # Staging-specific settings
    allowed_origins: List[str] = [
        "https://staging.yourdomain.com",
        "https://staging-api.yourdomain.com"
    ]
    
    # Moderate security settings
    require_email_verification: bool = True
    allow_user_registration: bool = True
    
    # Moderate token expiry
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 14
    
    # Staging database
    mongodb_url: str = "mongodb://staging-cluster:27017"
    
    # Moderate rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10
    
    class Config:
        env_file = ".env.staging"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Settings factory
class SettingsFactory:
    """Factory for creating environment-specific settings."""
    
    _settings_map: Dict[str, Type[Settings]] = {
        Environment.DEVELOPMENT: DevelopmentSettings,
        Environment.PRODUCTION: ProductionSettings,
        Environment.TESTING: TestingSettings,
        "staging": StagingSettings,  # Additional environment
    }
    
    @classmethod
    def create_settings(cls, environment: Optional[str] = None) -> Settings:
        """Create settings instance for the specified environment."""
        if environment is None:
            environment = os.getenv("FASTAPI_ENV", Environment.DEVELOPMENT)
        
        # Normalize environment string
        environment = environment.lower().strip()
        
        # Get the appropriate settings class
        settings_class = cls._settings_map.get(environment, DevelopmentSettings)
        
        return settings_class()
    
    @classmethod
    def register_environment(cls, env_name: str, settings_class: Type[Settings]):
        """Register a new environment settings class."""
        cls._settings_map[env_name] = settings_class
    
    @classmethod
    def available_environments(cls) -> List[str]:
        """Get list of available environments."""
        return list(cls._settings_map.keys())


# Cached settings instances
@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance based on current environment."""
    return SettingsFactory.create_settings()


def get_development_settings() -> DevelopmentSettings:
    """Get development settings instance."""
    return DevelopmentSettings()


def get_production_settings() -> ProductionSettings:
    """Get production settings instance."""
    return ProductionSettings()


def get_testing_settings() -> TestingSettings:
    """Get testing settings instance."""
    return TestingSettings()


def get_staging_settings() -> StagingSettings:
    """Get staging settings instance."""
    return StagingSettings()


# Utility functions
def create_settings_for_environment(env: str) -> Settings:
    """Create settings for a specific environment without caching."""
    return SettingsFactory.create_settings(env)


def validate_environment_config(env: str) -> Dict[str, Any]:
    """Validate and return configuration for an environment."""
    try:
        settings = create_settings_for_environment(env)
        return {
            "environment": settings.environment,
            "debug": settings.debug,
            "database_url": settings.database_url,
            "log_level": settings.log_level,
            "workers": settings.workers,
            "valid": True
        }
    except Exception as e:
        return {
            "environment": env,
            "error": str(e),
            "valid": False
        }


# Example: Register a custom environment
# SettingsFactory.register_environment("custom", CustomSettings)