
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum



class NodeType(str, Enum):
    """Types of nodes in the convo."""
    START = "start"
    END = "end"
    MESSAGE = "message"
    QUESTION = "question"
    ACTION = "action"
    CONDITION = "condition"
    API_CALL = "api_call"
    JUMP = "jump"
    COLLECT_INPUT = "collect_input"
    VALIDATION = "validation"
    MENU = "menu"
    AI_CHAT = "ai_chat"

class TransitionConditionType(str, Enum):
    """Types of conditions for transitions."""
    EQUALS = "equals"
    CONTAINS = "contains"
    REGEX = "regex"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IN_LIST = "in_list"
    ALWAYS = "always"
    CUSTOM = "custom"


class TransitionCondition(BaseModel):
    """Condition for transitioning between nodes."""
    type: TransitionConditionType
    field: Optional[str] = Field(None, description="Field to check in user input or context")
    value: Optional[Any] = Field(None, description="Value to compare against")
    operator: Optional[str] = Field(None, description="Custom operator for complex conditions")
    
    class Config:
        use_enum_values = True


class NodeTransition(BaseModel):
    """Transition from one node to another."""
    target_node_id: str = Field(..., description="ID of the target node")
    condition: Optional[TransitionCondition] = Field(None, description="Condition for this transition")
    label: Optional[str] = Field(None, description="Label for this transition (e.g., 'Yes', 'No')")
    priority: int = Field(default=0, description="Priority when multiple conditions match (higher = first)")


class ApiAction(BaseModel):
    """API action configuration."""
    url: str = Field(..., description="API endpoint URL")
    method: str = Field(default="POST", description="HTTP method (GET, POST, PUT, DELETE)")
    input: List[str] = Field(default_factory=list, description="Input variables from session context")
    output: List[str] = Field(default_factory=list, description="Output variables to store in session context")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Additional HTTP headers")
    timeout: Optional[int] = Field(default=30, description="Request timeout in seconds")

class NodeAction(BaseModel):
    """Action to perform when node is executed."""
    type: str = Field(..., description="Type of action (e.g., 'save_to_context', 'api_call', 'send_email')")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the action")
    api_action: Optional[ApiAction] = Field(None, description="API action configuration")
    on_success: Optional[str] = Field(None, description="Node to jump to on success")
    on_failure: Optional[str] = Field(None, description="Node to jump to on failure")


class ValidationRule(BaseModel):
    """Validation rule for user input."""
    type: str = Field(..., description="Type of validation (e.g., 'email', 'phone', 'regex', 'length')")
    params: Dict[str, Any] = Field(default_factory=dict, description="Validation parameters")
    error_message: str = Field(..., description="Error message to show if validation fails")


class AINodeConfig(BaseModel):
    """Configuration for AI chat nodes."""
    system_prompt: Optional[str] = Field(None, description="System prompt to guide AI behavior")
    llm_model: str = Field(default="qwen2.5:7b-instruct-q5_K_S", description="LLM model to use")
    llm_provider: str = Field(default="ollama", description="LLM model to use")
    query_type: str = Field(default="agent", description="What type of query to perform")
    include_chat_history: bool = Field(default=True, description="Include conversation history")
    max_history_messages: int = Field(default=10, ge=1, le=50, description="Maximum history messages")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum tokens in response")
    context_variables: List[str] = Field(default_factory=list, description="Session context variables to include")
    exit_keywords: List[str] = Field(default_factory=list, description="Keywords to exit AI chat mode")
    exit_node_id: Optional[str] = Field(None, description="Node ID to jump to when exit keyword is detected")

class ConvoNode(BaseModel):
    """Base model for a convo node."""
    id: str = Field(..., description="Unique identifier for the node")
    type: NodeType
    name: str = Field(..., description="Human-readable name for the node")
    description: Optional[str] = Field(None, description="Description of what this node does")
    
    # Content
    message: Optional[str] = Field(None, description="Message to display to user")
    message_template: Optional[str] = Field(None, description="Message template with variables")
    
    # Input collection
    collect_input: bool = Field(default=False, description="Whether to collect user input")
    input_field: Optional[str] = Field(None, description="Field name to store collected input")
    input_type: Optional[str] = Field(None, description="Type of input expected (text, number, email, etc.)")
    validations: List[ValidationRule] = Field(default_factory=list, description="Validation rules for input")
    
    # Actions
    actions: List[NodeAction] = Field(default_factory=list, description="Actions to perform")
    
    # AI Configuration (for AI_CHAT nodes)
    ai_config: Optional[AINodeConfig] = Field(None, description="AI chat configuration")
    
    # Transitions
    transitions: List[NodeTransition] = Field(default_factory=list, description="Possible transitions from this node")
    default_transition: Optional[str] = Field(None, description="Default next node if no conditions match")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        use_enum_values = True


class ConvoDefinition(BaseModel):
    """Complete convo definition."""
    id: str = Field(..., description="Unique identifier for the convo")
    name: str = Field(..., description="Name of the convo")
    description: Optional[str] = Field(None, description="Description of the convo")
    version: str = Field(default="1.0.0", description="Version of the convo")
    
    start_node_id: str = Field(..., description="ID of the starting node")
    nodes: List[ConvoNode] = Field(..., description="All nodes in the convo")
    
    # Global settings
    timeout_minutes: int = Field(default=30, description="Session timeout in minutes")
    max_retries: int = Field(default=3, description="Maximum retries for failed actions")
    
    # Tenant tracking
    tenant_uid: Optional[str] = Field(None, description="Tenant/company identifier for tracking and billing")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "onboarding_flow",
                "name": "User Onboarding Flow",
                "description": "Guides new users through onboarding",
                "version": "1.0.0",
                "start_node_id": "welcome",
                "nodes": [
                    {
                        "id": "welcome",
                        "type": "message",
                        "name": "Welcome Message",
                        "message": "Welcome! Let's get you started.",
                        "default_transition": "ask_name"
                    }
                ]
            }
        }


class ChatSession(BaseModel):
    """Active chat session."""
    session_id: str = Field(..., description="Unique session identifier")
    convo_id: str = Field(..., description="ID of the convo being executed")
    user_id: Optional[str] = Field(None, description="ID of the user")
    tenant_uid: Optional[str] = Field(None, description="Tenant/company identifier for tracking and billing")
    
    current_node_id: str = Field(..., description="Current node in the flow")
    context: Dict[str, Any] = Field(default_factory=dict, description="Session context/variables")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Conversation history")
    
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    completed: bool = Field(default=False)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AIChatSessionCreate(BaseModel):
    """Request model for creating an AI chat session."""
    user_id: Optional[str] = Field(None, description="User identifier (optional)")
    title: Optional[str] = Field(None, description="Session title")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class AIChatSession(BaseModel):
    """AI chat session model."""
    session_id: str = Field(..., description="Unique session identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    tenant_uid: Optional[str] = Field(None, description="Tenant/company identifier for tracking and billing")
    title: Optional[str] = Field(None, description="Session title")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: datetime = Field(default_factory=datetime.utcnow)
    active: bool = Field(default=True)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AIChatQuery(BaseModel):
    """Request model for AI chat query."""
    query: str = Field(..., description="User query/message")
    session_id: Optional[str] = Field(None, description="Existing session ID (optional)")
    include_chat_history: bool = Field(default=True, description="Include chat history in context")
    max_history_messages: int = Field(default=10, ge=1, le=50, description="Maximum number of history messages")
    llm_model: str = Field(default="qwen2.5:7b-instruct-q5_K_S", description="LLM model to use")
    llm_provider: str = Field(default="ollama", description="LLM provider to use")
    
class AIChatResponse(BaseModel):
    """Response model for AI chat."""
    answer: str = Field(..., description="AI response")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AIChatMessage(BaseModel):
    """Model for a single chat message."""
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AIChatInteraction(BaseModel):
    """Model for logging AI chat interactions."""
    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(..., description="User identifier")
    tenant_uid: Optional[str] = Field(None, description="Tenant/company identifier for tracking and billing")
    query: str = Field(..., description="User query")
    response: str = Field(..., description="AI response")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """Message in a chat session."""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    node_id: Optional[str] = Field(None, description="Node that generated this message")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """Request to interact with convo."""
    session_id: Optional[str] = Field(None, description="Existing session ID (if continuing)")
    convo_id: str = Field(..., description="ID of the convo to use")
    user_id: Optional[str] = Field(None, description="User identifier")
    tenant_uid: Optional[str] = Field(None, description="Tenant/company identifier for tracking and billing")
    message: Optional[str] = Field(None, description="User message/input")
    action: Optional[str] = Field(None, description="Specific action to perform")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ChatResponse(BaseModel):
    """Response from convo interaction."""
    session_id: str
    message: str
    node_id: str
    node_type: NodeType
    
    # Input collection
    expects_input: bool = Field(default=False)
    input_type: Optional[str] = None
    input_field: Optional[str] = None
    
    convo_id: Optional[str] = None
    
    # Options for user
    options: List[Dict[str, str]] = Field(default_factory=list, description="Available options/buttons")
    
    # Session info
    completed: bool = Field(default=False)
    context: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    

    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = "bearer"
    expires_in: Optional[str] = None


    
    class Config:
        use_enum_values = True
