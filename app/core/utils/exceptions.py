
from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class ServiceException(Exception):
    """Base exception for RAG service."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class APIServiceException(ServiceException):
    """Exception for API service errors with HTTP status code support."""
    
    def __init__(
        self, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        http_status_code: int = 500
    ):
        super().__init__(message, details)
        self.http_status_code = http_status_code


class DatabaseException(ServiceException):
    """Exception for database-related errors."""
    pass


class ValidationException(ServiceException):
    """Exception for validation errors."""
    pass


class AuthenticationException(ServiceException):
    """Exception for authentication errors."""
    pass


class AuthorizationException(ServiceException):
    """Exception for authorization errors."""
    pass


class ResourceNotFoundException(ServiceException):
    """Exception for resource not found errors."""
    pass


class ConfigurationException(ServiceException):
    """Exception for configuration errors."""
    pass


class TransformError(ServiceException):
    """Exception for transformation errors."""
    pass




class DatabaseError(ServiceException):
    """Exception for database operations."""
    pass


class AuthenticationError(ServiceException):
    """Exception for authentication issues."""
    pass




# HTTP Exception creators
def create_http_exception(
    status_code: int, 
    message: str, 
    details: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None
) -> HTTPException:
    """Create standardized HTTP exception."""
    detail = {
        "success": False,
        "message": message
    }
    
    if error_code:
        detail["error_code"] = error_code
    
    if details:
        detail["details"] = details
    
    return HTTPException(status_code=status_code, detail=detail)


def create_validation_error(errors: list) -> HTTPException:
    """Create validation error response."""
    return HTTPException(
        status_code=422,
        detail={
            "success": False,
            "message": "Validation error",
            "errors": errors
        }
    )


def create_not_found_error(resource: str, identifier: str) -> HTTPException:
    """Create not found error response."""
    return HTTPException(
        status_code=404,
        detail={
            "success": False,
            "message": f"{resource} not found",
            "details": {"identifier": identifier}
        }
    )


def create_service_unavailable_error(service: str, error: str) -> HTTPException:
    """Create service unavailable error response."""
    return HTTPException(
        status_code=503,
        detail={
            "success": False,
            "message": f"{service} service unavailable",
            "details": {"error": error}
        }
    )


def create_rate_limit_error(limit: int, window: str) -> HTTPException:
    """Create rate limit error response."""
    return HTTPException(
        status_code=429,
        detail={
            "success": False,
            "message": "Rate limit exceeded",
            "details": {
                "limit": limit,
                "window": window
            }
        }
    )


def create_unauthorized_error(message: str = "Unauthorized") -> HTTPException:
    """Create unauthorized error response."""
    return HTTPException(
        status_code=401,
        detail={
            "success": False,
            "message": message
        }
    )


def create_forbidden_error(message: str = "Forbidden") -> HTTPException:
    """Create forbidden error response."""
    return HTTPException(
        status_code=403,
        detail={
            "success": False,
            "message": message
        }
    )


def create_bad_request_error(message: str, details: Optional[Dict[str, Any]] = None) -> HTTPException:
    """Create bad request error response."""
    detail = {
        "success": False,
        "message": message
    }
    
    if details:
        detail["details"] = details
    
    return HTTPException(status_code=400, detail=detail)


def create_internal_server_error(message: str = "Internal server error") -> HTTPException:
    """Create internal server error response."""
    return HTTPException(
        status_code=500,
        detail={
            "success": False,
            "message": message
        }
    )


# Exception mapping for automatic HTTP error conversion
EXCEPTION_TO_HTTP_MAP = {
    TransformError: lambda e: create_internal_server_error(e.message),
    DatabaseError: lambda e: create_service_unavailable_error("Database", e.message),
    AuthenticationError: lambda e: create_unauthorized_error(e.message),
}


def convert_exception_to_http(exc: ServiceException) -> HTTPException:
    """Convert service exception to HTTP exception."""
    
    # Map exception types to HTTP status codes
    status_code_map = {
        ValidationException: status.HTTP_400_BAD_REQUEST,
        AuthenticationException: status.HTTP_401_UNAUTHORIZED,
        AuthorizationException: status.HTTP_403_FORBIDDEN,
        ResourceNotFoundException: status.HTTP_404_NOT_FOUND,
        DatabaseException: status.HTTP_503_SERVICE_UNAVAILABLE,
        ConfigurationException: status.HTTP_500_INTERNAL_SERVER_ERROR,
    }
    
    # Get status code from exception type or use custom http_status_code
    if isinstance(exc, APIServiceException):
        status_code = exc.http_status_code
    else:
        status_code = status_code_map.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Build detail dictionary
    detail = {
        "success": False,
        "message": exc.message,
    }
    
    if exc.details:
        detail["details"] = exc.details
    
    return HTTPException(
        status_code=status_code,
        detail=detail
    )
