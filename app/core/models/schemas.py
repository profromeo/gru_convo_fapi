
"""
Pydantic models for request/response schemas - Updated with XML to JSON support.
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class RequestMessageFields(BaseModel):
    system: Optional[str] = Field(None, description="System identifier")
    interface: Optional[str] = Field(None, description="Interface identifier")
    method: Optional[str] = Field(None, description="Method identifier")
    database: Optional[str] = Field(None, description="Database identifier")
    route_info: Optional[str] = Field(None, description="Route information for RouteInfo CDATA section")

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    success: bool = Field(default=False)

class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    environment: str = Field(..., description="Service environment")

class MappingListResponse(BaseModel):
    mappings: List[str] = Field(..., description="List of available mapping names")
    count: int = Field(..., description="Number of available mappings")

class ConditionalConfig(BaseModel):
    """Configuration for conditional value transformation"""
    type: str = Field(
        default="value_match",
        description="Type of condition: 'value_match', 'xpath_match', or 'attribute_match'"
    )
    xpath: Optional[str] = Field(None, description="XPath for xpath_match type")
    attribute: Optional[str] = Field(None, description="Attribute name for attribute_match type")
    conditions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of condition mappings with 'match' and 'output' keys"
    )
    default: Optional[Any] = Field(None, description="Default value if no condition matches")

class ValueMapConfig(BaseModel):
    """Configuration for simple value mapping"""
    mappings: Dict[str, Any] = Field(..., description="Value mapping dictionary")
    default: Optional[Any] = Field(None, description="Default value if no mapping found")
