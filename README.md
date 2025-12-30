# gru_chat_fapi

## Node Types & Configuration

The chat flow is built using various node types, each serving a specific purpose. Below are examples and configuration details for the available node types, based on `example_support_flow.json`.

### 1. Collect Input Node
Used to gather information from the user. It can validate input and perform API calls.

**Example: Collecting Customer Code**
```json
{
  "id": "collect_customer_number",
  "type": "collect_input",
  "name": "Collect Customer Code",
  "message": "👋 Welcome to Customer Support!\n\nTo get started, please provide your Customer Code:",
  "collect_input": true,
  "input_field": "customer_number",
  "input_type": "text",
  "validations": [
    {
      "type": "required",
      "error_message": "⚠️ Customer Code is required."
    },
    {
      "type": "length",
      "params": { "min": 4, "max": 10 },
      "error_message": "⚠️ Customer Code must be between 4 and 10 digits."
    }
  ],
  "actions": [
    {
      "type": "api_call",
      "api_action": {
        "url": "https://api.example.com/search_customer",
        "method": "POST",
        "input": ["customer_number"],
        "output": ["lastname"],
        "headers": {
            "Authorization": "Bearer TOKEN"
        }
      },
      "on_success": "collect_email",
      "on_failure": "collect_customer_number"
    }
  ],
  "transitions": [
    {
      "target_node_id": "collect_email",
      "label": "Continue"
    }
  ]
}
```

### 2. Menu Node
Presents a set of options to the user and branches the flow based on their choice.

**Example: Main Menu**
```json
{
  "id": "main_menu",
  "type": "menu",
  "name": "Main Menu",
  "message": "How can we assist you today?\n1. Chat with AI\n2. Open Ticket\n\nPlease type the number of your choice:",
  "collect_input": true,
  "telegram_config": {
    "telegram_options": [
      { "label": "Chat with AI", "value": "1" },
      { "label": "Open Ticket", "value": "2" }
    ]
  },
  "transitions": [
    {
      "target_node_id": "ai_chat_intro",
      "condition": {
        "type": "equals",
        "field": "input",
        "value": "1"
      },
      "label": "AI Chat Assistant"
    },
    {
      "target_node_id": "support_ticket_info",
      "condition": {
        "type": "equals",
        "field": "input",
        "value": "2"
      },
      "label": "Open Support Ticket"
    }
  ],
  "default_transition": "invalid_main_menu"
}
```

### 3. Message Node
Sends a static message to the user without expecting input (unless configured otherwise).

**Example: End Chat Message**
```json
{
  "id": "end",
  "type": "message",
  "name": "End Chat",
  "message": "👋 Thank you for using customer Support! Have a great day!",
  "collect_input": false,
  "transitions": []
}
```

### 4. AI Chat Node
Initiates or continues an interaction with an LLM (Large Language Model).

**Example: AI Assistant**
```json
{
  "id": "ai_chat_node",
  "type": "ai_chat",
  "name": "AI Chat Assistant",
  "message": "🤖 AI Assistant is listening...",
  "collect_input": true,
  "ai_config": {
    "system_prompt": "You are a helpful customer support AI assistant...",
    "llm_model": "qwen2.5:7b-instruct-q5_K_S",
    "llm_provider": "ollama",
    "include_chat_history": true,
    "context_variables": ["customer_number", "user_email"],
    "exit_keywords": ["exit", "menu", "quit"],
    "exit_node_id": "ai_chat_exit"
  }
}
```

### 5. Process Media Node
Handles media uploads (images, audio, etc.) and processes them via external services.

**Example: Media Upload**
```json
{
  "id": "process_media_node",
  "type": "process_media",
  "name": "Process Media",
  "message": "Please provide a media file",
  "process_media_config": {
    "action_type": "service",
    "output_variable": "file_url",
    "service_config": {
      "url": "http://service.api/upload",
      "method": "POST",
      "input": ["customer_number"],
      "output": ["file_url", "media_result"]
    }
  },
  "transitions": [
    {
      "target_node_id": "media_result_message"
    }
  ]
}
```