
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config import Settings
from app.core.models.convo import (
    ConvoDefinition,
    ChatSession,
    ConvoNode,
    ChatRequest,
    ChatResponse,
    ChatMessage,
    NodeType, 
    NodeAction,
    AIChatSession,
    AIChatSessionCreate,
    AIChatQuery,
    AIChatResponse,
    AIChatMessage,
    ProcessMediaConfig,
    ProcessMediaActionType,
    Union,
    TransitionCondition,
    TransitionConditionType
)
from app.core.utils.exceptions import APIServiceException
from app.core.services.storage_service import StorageService
import httpx

logger = logging.getLogger(__name__)


class ConvoService:
    """Service for managing convos and chat sessions."""
    
    def __init__(self, settings: Settings, database: AsyncIOMotorDatabase):
        self.settings = settings
        self.database = database
        self.convos_collection = database["chat_convos"]
        self.sessions_collection = database["chat_sessions"]
        self.ai_sessions_collection = database["ai_chat_sessions"]
        self.ai_interactions_collection = database["ai_interactions"]
        self.storage_service = StorageService(settings)
        self.logger = logging.getLogger(__name__)
        
        # AI service configuration
        self.ai_service_url = self.settings.ai_service_url or "http://localhost:8001"
    
    def _get_tenant_uid(self, provided_tenant_uid: Optional[str], user: Optional[Any] = None) -> Optional[str]:
        """Get tenant_uid from provided value or extract from user context.
        
        Args:
            provided_tenant_uid: Explicitly provided tenant_uid
            user: User object that may contain tenant_uid
            
        Returns:
            tenant_uid if found, None otherwise
        """
        if provided_tenant_uid:
            return provided_tenant_uid
        
        # Try to extract from user object if available
        if user and hasattr(user, 'tenant_uid'):
            return user.tenant_uid
        
        return None
    
    def _validate_convo(self, convo: ConvoDefinition) -> None:
        """Validate convo structure."""
        if not convo.id:
            raise APIServiceException(
                message="Convo must have an ID",
                http_status_code=400
            )
            
        if not convo.start_node_id:
            raise APIServiceException(
                message="Convo must have a start node ID",
                http_status_code=400
            )
            
        # Validate that start node exists
        start_node = next((node for node in convo.nodes if node.id == convo.start_node_id), None)
        if not start_node:
            raise APIServiceException(
                message=f"Start node '{convo.start_node_id}' not found in convo",
                http_status_code=400
            )
            
        # Validate that all transitions point to valid nodes
        node_ids = {n.id for n in convo.nodes}
        for node in convo.nodes:
            for transition in node.transitions or []:
                if transition.target_node_id not in node_ids:
                    raise APIServiceException(
                        message=f"Transition from node '{node.id}' points to non-existent node '{transition.target_node_id}'",
                        http_status_code=400
                    )
    
    async def create_convo(self, convo: ConvoDefinition) -> ConvoDefinition:
        """Create a new convo definition."""
        try:
            # Validate convo
            self._validate_convo(convo)
            
            # Check if convo with same ID exists
            existing = await self.convos_collection.find_one({"id": convo.id})
            if existing:
                raise APIServiceException(
                    message=f"Convo with ID '{convo.id}' already exists",
                    http_status_code=400
                )
            
            # Insert convo
            convo_dict = convo.model_dump()
            await self.convos_collection.insert_one(convo_dict)
            
            logger.info(f"Created convo: {convo.id}")
            return convo
            
        except APIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error creating convo: {e}")
            raise APIServiceException(
                message="Failed to create convo",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def get_convo(self, convo_id: str) -> Optional[ConvoDefinition]:
        """Get a convo by ID."""
        try:
            convo_dict = await self.convos_collection.find_one({"id": convo_id})
            if not convo_dict:
                return None
            
            # Remove MongoDB _id field
            convo_dict.pop("_id", None)
            return ConvoDefinition(**convo_dict)
            
        except Exception as e:
            logger.error(f"Error getting convo: {e}")
            raise APIServiceException(
                message="Failed to get convo",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def list_convos(
        self, 
        skip: int = 0, 
        limit: int = 100,
        created_by: Optional[str] = None,
        tenant_uid: Optional[str] = None
    ) -> List[ConvoDefinition]:
        """List all convos with optional filtering."""
        try:
            query = {}
            if created_by:
                query["created_by"] = created_by
            if tenant_uid:
                query["tenant_uid"] = tenant_uid
            
            cursor = self.convos_collection.find(query).skip(skip).limit(limit)
            convos = []
            
            async for convo_dict in cursor:
                convo_dict.pop("_id", None)
                convos.append(ConvoDefinition(**convo_dict))
            
            return convos
            
        except Exception as e:
            logger.error(f"Error listing convos: {e}")
            raise APIServiceException(
                message="Failed to list convos",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def update_convo(
        self, 
        convo_id: str, 
        convo: ConvoDefinition
    ) -> ConvoDefinition:
        """Update an existing convo."""
        try:
            # Validate convo
            self._validate_convo(convo)
            
            # Check if convo exists
            existing = await self.convos_collection.find_one({"id": convo_id})
            if not existing:
                raise APIServiceException(
                    message=f"Convo '{convo_id}' not found",
                    http_status_code=404
                )
            
            # Update convo
            convo_dict = convo.model_dump()
            convo_dict["updated_at"] = datetime.utcnow()
            
            await self.convos_collection.replace_one(
                {"id": convo_id},
                convo_dict
            )
            
            logger.info(f"Updated convo: {convo_id}")
            return convo
            
        except APIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error updating convo: {e}")
            raise APIServiceException(
                message="Failed to update convo",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def delete_convo(self, convo_id: str) -> bool:
        """Delete a convo."""
        try:
            result = await self.convos_collection.delete_one({"id": convo_id})
            
            if result.deleted_count == 0:
                raise APIServiceException(
                    message=f"Convo '{convo_id}' not found",
                    http_status_code=404
                )
            
            logger.info(f"Deleted convo: {convo_id}")
            return True
            
        except APIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error deleting convo: {e}")
            raise APIServiceException(
                message="Failed to delete convo",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def start_chat_session(
        self,
        request: ChatRequest
    ) -> ChatResponse:
        """Start a new chat session."""
        try:
            # Get convo
            convo = await self.get_convo(request.convo_id)
            if not convo:
                raise APIServiceException(
                    message=f"Convo '{request.convo_id}' not found",
                    http_status_code=404
                )
        
            logger.info(f"Starting chat session for convo: {convo.id}")
            logger.info(f"Start node ID: {convo.start_node_id}")
        
            # Create session with generated session_id
            session = ChatSession(
                session_id=str(uuid.uuid4()),
                convo_id=request.convo_id,
                user_id=request.user_id,
                tenant_uid=request.tenant_uid,
                current_node_id=convo.start_node_id,
                context=request.context or {},
                history=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                last_activity=datetime.utcnow()
            )
        
            # Get the start node
            start_node = next(
                (node for node in convo.nodes if node.id == convo.start_node_id),
                None
            )
        
            if not start_node:
                raise APIServiceException(
                    message=f"Start node '{convo.start_node_id}' not found in convo",
                    http_status_code=500
                )
        
            logger.info(f"Start node found: {start_node.id} (type: {start_node.type})")
            logger.info(f"Start node has {len(start_node.transitions)} transitions")
        
            # For the initial node, don't pass user input (empty string)
            # This will just display the node's message and options
            try:
                response_data = await self._process_initial_node(session, start_node, convo)
            except Exception as e:
                logger.error(f"Error processing initial node: {e}", exc_info=True)
                raise APIServiceException(
                    message="Failed to process initial node",
                    details={"error": str(e), "node_id": start_node.id},
                    http_status_code=500
                )
        
            # Update session with any context changes
            session.last_activity = datetime.utcnow()
        
            # Insert session into database
            session_dict = session.model_dump()
            await self.sessions_collection.insert_one(session_dict)
        
            logger.info(f"Created chat session: {session.session_id}")
        
            # Create response
            response = ChatResponse(
                session_id=session.session_id,
                message=response_data.get("message", start_node.message or "Welcome!"),
                node_id=start_node.id,
                node_type=start_node.type,
                expects_input=response_data.get("requires_input", True),
                input_type=start_node.input_type if start_node.collect_input else None,
                input_field=start_node.input_field if start_node.collect_input else None,
                completed=response_data.get("completed", False),
                context=session.context,
                options=response_data.get("options", []),
                convo_id=request.convo_id
            )
        
            return response
        
        except APIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error starting chat session: {e}", exc_info=True)
            raise APIServiceException(
                message="Failed to start chat session",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def get_chat_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a chat session by ID."""
        try:
            session_dict = await self.sessions_collection.find_one({"session_id": session_id})
            if not session_dict:
                return None
            
            session_dict.pop("_id", None)
            return ChatSession(**session_dict)
            
        except Exception as e:
            logger.error(f"Error getting chat session: {e}")
            raise APIServiceException(
                message="Failed to get chat session",
                details={"error": str(e)},
                http_status_code=500
            )
        
        
    async def continue_chat_session(
        self,
        session_id: str,
        user_message: str,
        media_url: Optional[str] = None
    ) -> ChatResponse:
        """Continue an existing chat session with a user message."""
        try:
            # Get session
            session = await self.get_chat_session(session_id)
            if not session:
                new_chat_request = ChatRequest(
                    convo_id="enhanced_customer_support_flow"  # You may choose a default convo ID
                )
                session = await self.start_chat_session(new_chat_request)
            
            # Update context with media_url if provided
            if media_url:
                session.context['media_url'] = media_url
                logger.info(f"Updated session context with media_url: {media_url}")
                #raise APIServiceException(
                #    message=f"Chat session '{session_id}' not found",
                #    http_status_code=404
                #)
            
            if session.completed:
                new_chat_request = ChatRequest(
                    convo_id=session.convo_id  # You may choose a default convo ID
                )
                session = await self.start_chat_session(new_chat_request)
                
                return session
            
            # Get convo
            convo = await self.get_convo(session.convo_id)
            if not convo:
                raise APIServiceException(
                    message=f"Convo '{session.convo_id}' not found",
                    http_status_code=404
                )
            
            # Get current node
            current_node = next(
                (node for node in convo.nodes if node.id == session.current_node_id),
                None
            )
            if not current_node:
                raise APIServiceException(
                    message=f"Current node '{session.current_node_id}' not found",
                    http_status_code=500
                )
            
            # Check for navigation commands FIRST
            nav_response = await self._handle_navigation_commands(user_message, session, convo)
            if nav_response:
                # Navigation command was handled
                # Update session in database
                await self._update_session(session)
                
                response_message = self._render_template(
                nav_response.get("message", "") or "",
                session.context
            )
                
                # Create response
                return ChatResponse(
                    session_id=session.session_id,
                    message=response_message,
                    node_id=nav_response.get("node_id"),
                    node_type=nav_response.get("node_type"),
                    expects_input=nav_response.get("requires_input", False),
                    input_type=nav_response.get("input_type"),
                    input_field=nav_response.get("input_field"),
                    completed=nav_response.get("completed", False),
                    context=session.context,
                    options=nav_response.get("options", [])
                )
            
            # Add user message to history
            session.history.append({
                "role": "user",
                "content": user_message,
                "node_id": current_node.id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Process node and get response
            response_data = await self._process_node(session, current_node, user_message, convo)
            
            # Determine which node we're actually on after processing
            actual_node_id = response_data.get("next_node_id") or current_node.id
            actual_node = next(
                (node for node in convo.nodes if node.id == actual_node_id),
                current_node
            )
            
            # Add bot response to history
            # session.history.append({
            #     "role": "assistant",
            #     "content": response_data["message"],
            #     "node_id": actual_node_id,
            #     "timestamp": datetime.utcnow().isoformat()
            # })
            
            
            
            session.history.append(ChatMessage(
                    role="assistant",
                    content=response_data["message"],
                    node_id=actual_node_id,
                    timestamp= datetime.utcnow().isoformat()
                ).model_dump())
            
            # Update current node if there's a next node
            if response_data.get("next_node_id"):
                session.current_node_id = response_data["next_node_id"]
            
            # Mark as completed if needed
            if response_data.get("completed"):
                session.completed = True
            
            # Update session in database
            await self._update_session(session)
            
            # Create response using the actual node we're on
            response = ChatResponse(
                session_id=session.session_id,
                message=response_data.get("message", ""),
                node_id=actual_node_id,
                node_type=actual_node.type,
                expects_input=response_data.get("requires_input", False),
                input_type=actual_node.input_type if actual_node.collect_input else None,
                input_field=actual_node.input_field if actual_node.collect_input else None,
                completed=response_data.get("completed", False),
                context=session.context,
                options=response_data.get("options", [])
            )
            
            logger.info(f"Continued chat session: {session.session_id}")
            return response
            
        except APIServiceException as apie:
            logger.error(f"Error continuing chat session: {apie}")
            raise
        except Exception as e:
            logger.error(f"Error continuing chat session: {e}")
            raise APIServiceException(
                message="Failed to continue chat session",
                details={"error": str(e)},
                http_status_code=500
            )
            
                

    async def _process_ai_chat_node(
            self,
            session: ChatSession,
            node: ConvoNode,
            user_input: str,
            convo: ConvoDefinition
        ) -> Dict[str, Any]:
            """Process an AI chat node."""
            try:
                if not node.ai_config:
                    raise APIServiceException(
                        message="AI node missing configuration",
                        http_status_code=500
                    )
                
                ai_config = node.ai_config
                
                # Check for exit keywords
                if user_input and ai_config.exit_keywords:
                    user_input_lower = user_input.lower().strip()
                    for keyword in ai_config.exit_keywords:
                        if keyword.lower() in user_input_lower:
                            # Exit AI chat mode
                            if ai_config.exit_node_id:
                                next_node = next(
                                    (n for n in convo.nodes if n.id == ai_config.exit_node_id),
                                    None
                                )
                                if next_node:
                                    session.current_node_id = next_node.id
                                    session.history.append(ChatMessage(
                                        role="assistant",
                                        content=next_node.message or "Exiting AI chat...",
                                        node_id=next_node.id,
                                        timestamp=datetime.utcnow()
                                    ).model_dump())
                                    
                                    return {
                                        "message": next_node.message or "Exiting AI chat...",
                                        "node_id": next_node.id,
                                        "node_type": next_node.type,
                                        "requires_input": next_node.collect_input,
                                        "input_type": next_node.input_type if next_node.collect_input else None,
                                        "input_field": next_node.input_field if next_node.collect_input else None,
                                        "completed": next_node.type == NodeType.END,
                                        "options": []
                                    }
                
                # Get or create AI chat session for this convo session
                ai_session_id = session.context.get("ai_session_id")
                if not ai_session_id:
                    # Create new AI chat session
                    ai_session = await self.create_ai_chat_session(
                        AIChatSessionCreate(
                            user_id=session.user_id,
                            title=f"AI Chat - {convo.name}",
                            metadata={
                                "convo_id": session.convo_id,
                                "convo_session_id": session.session_id,
                                "node_id": node.id
                            }
                        ),
                        user_id=session.user_id
                    )
                    ai_session_id = ai_session.session_id
                    session.context["ai_session_id"] = ai_session_id
                
                # Build chat history
                chat_history = []
                if ai_config.include_chat_history:
                    chat_history = await self._get_ai_chat_history(
                        ai_session_id,
                        limit=ai_config.max_history_messages
                    )
                
                # Add system prompt if provided
                query_context = {}
                # if ai_config.system_prompt:
                #     query_context["system_prompt"] = ai_config.system_prompt
                
                # Add context variables if specified
                if ai_config.context_variables:
                    for var in ai_config.context_variables:
                        if var in session.context:
                            query_context[var] = session.context[var]
                
                # Prepare the query
                query_text = user_input
                if query_context:
                    # Prepend context to query
                    context_str = "\n".join([f"{k}: {v}" for k, v in query_context.items()])
                    query_text = f"Context:\n{context_str}\n\nUser: {user_input}"
                
                # Save user message
                await self._save_ai_chat_message(ai_session_id, "user", user_input, session.tenant_uid)
                
                # Call AI service
                ai_response = await self._call_ai_service(
                    ai_session_id,
                    query_text,
                    chat_history,
                    ai_config
                )
                
                # Save AI response
                await self._save_ai_chat_message(ai_session_id, "assistant", ai_response, session.tenant_uid)
                
                # Add to session history
                session.history.append(ChatMessage(
                    role="user",
                    content=user_input,
                    node_id=node.id,
                    timestamp=datetime.utcnow()
                ).model_dump())
                
                session.history.append(ChatMessage(
                    role="assistant",
                    content=ai_response,
                    node_id=node.id,
                    timestamp=datetime.utcnow()
                ).model_dump())
                
                # Build exit instructions
                exit_instructions = ""
                if ai_config.exit_keywords:
                    exit_instructions = f"\n\n(Type '{ai_config.exit_keywords[0]}' to exit AI chat)"
                
                return {
                    "message": ai_response + exit_instructions,
                    "node_id": node.id,
                    "node_type": node.type,
                    "requires_input": True,  # AI chat always expects input
                    "input_type": "text",
                    "input_field": None,
                    "completed": False,
                    "options": []
                }
                
            except APIServiceException:
                raise
            except Exception as e:
                logger.error(f"Error processing AI chat node: {e}", exc_info=True)
                raise APIServiceException(
                    message="Failed to process AI chat",
                    details={"error": str(e), "node_id": node.id},
                    http_status_code=500
                )

    async def _process_process_media_node(
        self,
        session: ChatSession,
        node: ConvoNode,
        user_input: str,
        convo: ConvoDefinition
    ) -> Dict[str, Any]:
        """Process a Process Media node."""
        logger.info(f"Processing media node: {node.id}")
        
        media_url = session.context.get("media_url")
        processed_successfully = False
        result_details = ""
        
        if media_url and node.process_media_config:
            import tempfile
            import os
            
            config = node.process_media_config
            local_file_path = None
            
            try:
                # Create temp file
                # Use suffix from url if possible to help with extension detection
                suffix = ""
                if "." in media_url.split("/")[-1]:
                    suffix = "." + media_url.split("/")[-1].split(".")[-1]
                    
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    local_file_path = tmp_file.name
                
                download_success = False
                
                # 1. Custom MinIO Config
                if config.minio_config:
                    logger.info(f"Attempting download with custom MinIO config: {config.minio_config.endpoint}")
                    download_success = self.storage_service.download_file(
                        media_url, 
                        local_file_path, 
                        minio_config=config.minio_config
                    )
                
                # 2. Direct URL
                elif media_url.startswith(("http://", "https://")):
                    logger.info(f"Attempting direct HTTP download: {media_url}")
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(media_url, timeout=30.0)
                        if resp.status_code == 200:
                            with open(local_file_path, "wb") as f:
                                f.write(resp.content)
                            download_success = True
                        else:
                            logger.error(f"Failed to download media. Status: {resp.status_code}")
                
                # 3. Default MinIO
                else:
                    logger.info(f"Attempting download with default MinIO config")
                    download_success = self.storage_service.download_file(media_url, local_file_path)
                
                if download_success:
                    logger.info(f"Media downloaded successfully to {local_file_path}")
                    
                    # Update session context with media info for downstream usage
                    session.context["media_local_path"] = local_file_path
                    session.context["media_url"] = media_url # Ensure this is present
                    
                    # Process based on action type
                    action_type = config.action_type
                    
                    if action_type == ProcessMediaActionType.SERVICE:
                        if config.service_config:
                             # Use specialized service action handling to include file
                             result_str = await self._process_media_service_action(
                                 session, 
                                 config.service_config, 
                                 local_file_path,
                                 media_url
                             )
                             result_details = f"Forwarded to service: {result_str}"
                             processed_successfully = True
                        else:
                             raise APIServiceException("Service config missing for SERVICE action")
                             
                    elif action_type == ProcessMediaActionType.EMAIL:
                        if config.email_config:
                            await self._process_media_email_action(session, config.email_config, local_file_path, media_url)
                            result_details = f"Emailed to {config.email_config.to_email}"
                            processed_successfully = True
                        else:
                             raise APIServiceException("Email config missing for EMAIL action")
                             
                    elif action_type == ProcessMediaActionType.AI_SERVICE:
                        if config.ai_service_config:
                            response = await self._process_media_ai_service_action(session, config.ai_service_config, local_file_path)
                            result_details = response
                            processed_successfully = True
                        else:
                             raise APIServiceException("AI service config missing for AI_SERVICE action")
                             
                    elif action_type == ProcessMediaActionType.OCR:
                        # Placeholder for OCR
                         processed_successfully = True
                         result_details = f"Processed {media_url} via {config.action_type}"
                         
                    else:
                        # Default or basic forward/save
                        processed_successfully = True
                        result_details = f"Processed {media_url} via {config.action_type}"
                    
                    # Store result
                    if config.output_variable:
                        session.context[config.output_variable] = result_details
                    
                    session.context["processed_media_result"] = result_details
                    
                else:
                    logger.error("Failed to download media file")
                    result_details = "Failed to retrieve media file"

            except Exception as e:
                logger.error(f"Error processing media: {e}", exc_info=True)
                result_details = f"Error: {str(e)}"
            finally:
                # Cleanup temp file
                if local_file_path and os.path.exists(local_file_path):
                    try:
                        os.remove(local_file_path)
                        # clean up context path
                        session.context.pop("media_local_path", None)
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file {local_file_path}: {e}")

        # Determine next node based on transitions or default
        next_node_id = None
        if node.transitions:
            # Check conditions if needed, otherwise take first
            # For now taking first match or default
            for transition in node.transitions:
                 next_node_id = transition.target_node_id
                 break
        
        # If no explicit transition found, check default_transition
        if not next_node_id and node.default_transition:
            next_node_id = node.default_transition

        # Fallback to first transition if exists (legacy behavior?)
        if not next_node_id and node.transitions:
            next_node_id = node.transitions[0].target_node_id
        
        next_node = next(
            (n for n in convo.nodes if n.id == next_node_id),
            None
        ) if next_node_id else None

        if next_node:
            session.current_node_id = next_node.id
            return await self._chain_nodes(session, convo, next_node.id)
        else:
            # If no next node, stay on current node or end
            message = self._render_template(node.message or f"Media processing complete: {result_details}", session.context)
            return {
                "message": message,
                "node_id": node.id,
                "next_node_id": None,
                "node_type": node.type,
                "requires_input": False, 
                "input_type": None,
                "input_field": None,
                "completed": node.type == NodeType.END,
                "options": []
            }


    async def _process_node(
        self,
        session: ChatSession,
        node: ConvoNode,
        user_input: str,
        convo: ConvoDefinition
    ) -> Dict[str, Any]:
        """Process a node and return response data."""
        try:
            # Check if this is an AI chat node
            if node.type == NodeType.AI_CHAT:
                return await self._process_ai_chat_node(session, node, user_input, convo)
            
            # Check if this is a Process Media node
            if node.type == NodeType.PROCESS_MEDIA:
                return await self._process_process_media_node(session, node, user_input, convo)
            
            # Add user message to history if provided
            if user_input:
                session.history.append(ChatMessage(
                    role="user",
                    content=user_input,
                    node_id=node.id,
                    timestamp=datetime.utcnow()
                ).model_dump())
            
            # Render node message with context variables
            response_message = self._render_template(
                node.message or "",
                session.context
            )
            
            # Determine next node based on user input
            next_node_id = None
            validation_error = None
            
            if user_input and node.transitions:
                # Process user input to find next node
                next_node_id, error_msg = await self._process_user_input(
                    session, node, user_input, convo
                )
                
                if error_msg:
                    # Invalid input - stay on current node and return validation error
                    validation_error = error_msg
                    next_node_id = None
            
            # If we have a validation error, return it immediately
            if validation_error:
                # Add validation error to history
                session.history.append(ChatMessage(
                    role="assistant",
                    content=validation_error,
                    node_id=node.id,
                    timestamp=datetime.utcnow()
                ).model_dump())
                
                # Build options for current node
                options = []
                if node.type == NodeType.MENU and node.transitions:
                    for idx, transition in enumerate(node.transitions, 1):
                        label = self._render_template(
                            transition.label or f"Option {idx}",
                            session.context
                        )
                        options.append({
                            "value": str(idx),
                            "label": label,
                            "target_node_id": transition.target_node_id
                        })
                
                return {
                    "message": validation_error,
                    "node_id": node.id,
                    "next_node_id": None,
                    "node_type": node.type,
                    "requires_input": node.collect_input,
                    "input_type": node.input_type if node.collect_input else None,
                    "input_field": node.input_field if node.collect_input else None,
                    "completed": False,
                    "options": options
                }
            
            # If we have a next node, transition to it (and chain if needed)
            if next_node_id:
                return await self._chain_nodes(session, convo, next_node_id)
            else:
                # No transition - stay on current node
                session.history.append(ChatMessage(
                    role="assistant",
                    content=response_message,
                    node_id=node.id,
                    timestamp=datetime.utcnow()
                ).model_dump())
                
                # Build options for current node
                options = []
                if node.type == NodeType.MENU and node.transitions:
                    for idx, transition in enumerate(node.transitions, 1):
                        # Render transition labels with context
                        label = self._render_template(
                            transition.label or f"Option {idx}",
                            session.context
                        )
                        options.append({
                            "value": str(idx),
                            "label": label,
                            "target_node_id": transition.target_node_id
                        })
                
                return {
                    "message": response_message,
                    "node_id": node.id,
                    "next_node_id": None,
                    "node_type": node.type,
                    "requires_input": node.collect_input,
                    "input_type": node.input_type if node.collect_input else None,
                    "input_field": node.input_field if node.collect_input else None,
                    "completed": False,
                    "options": options
                }    

                

                
        except APIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error processing node: {e}", exc_info=True)
            raise APIServiceException(
                message="Failed to process node",
                details={"error": str(e), "node_id": node.id},
                http_status_code=500
            )
    async def _process_initial_node(
        self,
        session: ChatSession,
        node: ConvoNode,
        convo: ConvoDefinition
    ) -> Dict[str, Any]:
        """Process the initial node without user input."""
        try:
            # Render node message with context variables
            rendered_message = self._render_template(
                node.message or "Welcome!",
                session.context
            )
            
            # Add initial bot message to history
            session.history.append(ChatMessage(
                role="assistant",
                content=rendered_message,
                node_id=node.id,
                timestamp=datetime.utcnow()
            ).model_dump())
            
            # Build options for the initial node
            options = []
            if node.type == NodeType.MENU and node.transitions:
                for idx, transition in enumerate(node.transitions, 1):
                    # Render transition labels with context
                    label = self._render_template(
                        transition.label or f"Option {idx}",
                        session.context
                    )
                    options.append({
                        "value": str(idx),
                        "label": label,
                        "target_node_id": transition.target_node_id
                    })
            
            return {
                "message": rendered_message,
                "node_id": node.id,
                "node_type": node.type,
                "requires_input": node.collect_input or (node.type == NodeType.MENU),
                "input_type": node.input_type if node.collect_input else None,
                "input_field": node.input_field if node.collect_input else None,
                "completed": node.type == NodeType.END,
                "options": options
            }
            
        except Exception as e:
            logger.error(f"Error processing initial node: {e}", exc_info=True)
            raise APIServiceException(
                message="Failed to process initial node",
                details={"error": str(e), "node_id": node.id},
                http_status_code=500
            )
    
    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """Render a message template with context variables.
        
        Replaces {{variable_name}} with values from context.
        Supports nested variables like {{user.name}}.
        """
        if not template:
            return template
            
        try:
            import re
            
            # Find all template variables in the format {{variable_name}}
            pattern = r'\{\{([^}]+)\}\}'
            
            def replace_variable(match):
                var_name = match.group(1).strip()
                
                # Handle nested variables (e.g., user.name)
                if '.' in var_name:
                    parts = var_name.split('.')
                    value = context
                    for part in parts:
                        if isinstance(value, dict) and part in value:
                            value = value[part]
                        else:
                            # Variable not found, keep original placeholder
                            logger.warning(f"Context variable '{var_name}' not found in session context")
                            return match.group(0)
                    return str(value)
                else:
                    # Simple variable lookup
                    if var_name in context:
                        return str(context[var_name])
                    else:
                        # Variable not found, keep original placeholder
                        logger.warning(f"Context variable '{var_name}' not found in session context")
                        return match.group(0)
            
            rendered = re.sub(pattern, replace_variable, template)
            return rendered
            
        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            return template
    
    async def _chain_nodes(
        self,
        session: ChatSession,
        convo: ConvoDefinition,
        start_node_id: str,
        initial_messages: List[str] = None
    ) -> Dict[str, Any]:
        """Process a chain of nodes automatically."""
        combined_messages = initial_messages or []
        next_node_id = start_node_id
        
        loop_counter = 0
        max_loops = 50
        
        node = None
        
        while next_node_id:
            # Loop protection
            loop_counter += 1
            if loop_counter > max_loops:
                logger.error(f"Infinite loop detected in node chaining: {next_node_id}")
                break
                
            node = next(
                (n for n in convo.nodes if n.id == next_node_id),
                None
            )
            
            if not node:
                raise APIServiceException(
                    message=f"Target node '{next_node_id}' not found",
                    http_status_code=500
                )
            
            # Update session to new node
            session.current_node_id = next_node_id
            
            # Render node's message with context variables
            # Note: For the *very first* node in the chain, if it came from an external process (like process_media),
            # the message might have already been processed or needs to be skipped if we just want to leverage transitions?
            # Actually, `start_node_id` here is usually the *next* node we want to jump to.
            # So we should process it fully.
            
            node_message = self._render_template(
                node.message or "",
                session.context
            )
            
            # Add bot response to history
            session.history.append(ChatMessage(
                role="assistant",
                content=node_message,
                node_id=node.id,
                timestamp=datetime.utcnow()
            ).model_dump())
            
            # Accumulate message
            combined_messages.append(node_message)
            
            # Check if we should chain to next node (MESSAGE type)
            should_chain = False
            next_next_node_id = None
            
            if node.type == NodeType.MESSAGE:
                # 1. Evaluate conditional transitions
                next_next_node_id = await self._evaluate_transitions(session, node, "")
                
                if not next_next_node_id:
                    # 2. Check for first unconditional transition
                    if node.transitions:
                        for transition in node.transitions:
                            if not transition.condition:
                                next_next_node_id = transition.target_node_id
                                break
                
                if not next_next_node_id:
                     # 3. Check default transition
                     next_next_node_id = node.default_transition
                     
                if next_next_node_id:
                    should_chain = True
                    next_node_id = next_next_node_id
            
            if not should_chain:
                # Stop here
                next_node_id = None
                
        # We stopped at `node`. Return response.
        response_message = "\n\n".join(combined_messages)
        
        options = []
        if node.type == NodeType.MENU and node.transitions:
            for idx, transition in enumerate(node.transitions, 1):
                label = self._render_template(
                    transition.label or f"Option {idx}",
                    session.context
                )
                options.append({
                    "value": str(idx),
                    "label": label,
                    "target_node_id": transition.target_node_id
                })
        
        return {
            "message": response_message,
            "node_id": node.id,
            "next_node_id": None,
            "node_type": node.type,
            "requires_input": node.collect_input,
            "input_type": node.input_type if node.collect_input else None,
            "input_field": node.input_field if node.collect_input else None,
            "completed": node.type == NodeType.END,
            "options": options
        }

    async def _evaluate_transitions(
        self,
        session: ChatSession,
        node: ConvoNode,
        user_input: str
    ) -> Optional[str]:
        """Evaluate node transitions and return the target node ID."""
        user_input_stripped = str(user_input).strip()
        
        for idx, transition in enumerate(node.transitions):
            # Check if user input matches the option number (1-indexed)
            if user_input_stripped == str(idx + 1):
                return transition.target_node_id
            
            # Check if transition has a label and user input matches it
            if hasattr(transition, 'label') and transition.label:
                if user_input_stripped.lower() == transition.label.lower():
                    return transition.target_node_id
            
            # Check if transition has conditions
            if hasattr(transition, 'condition') and transition.condition:
                condition = transition.condition
                
                # Handle dict-based conditions
                if isinstance(condition, dict):
                    condition_type = condition.get("type")
                    field = condition.get("field")
                    value = condition.get("value")
                    
                    if condition_type == "equals":
                        # Check if user input matches the expected value
                        if field and field in session.context:
                            if str(session.context[field]) == str(value):
                                return transition.target_node_id
                        # Also check direct user input match
                        elif user_input_stripped == str(value):
                            return transition.target_node_id
                            
                    elif condition_type == "contains":
                        if field and field in session.context:
                            if str(value).lower() in str(session.context[field]).lower():
                                return transition.target_node_id
                        elif str(value).lower() in user_input_stripped.lower():
                            return transition.target_node_id
                            
                    elif condition_type == "greater_than":
                        try:
                            input_val = float(session.context.get(field, user_input_stripped))
                            if input_val > float(value):
                                return transition.target_node_id
                        except (ValueError, TypeError):
                            pass
                            
                    elif condition_type == "less_than":
                        try:
                            input_val = float(session.context.get(field, user_input_stripped))
                            if input_val < float(value):
                                return transition.target_node_id
                        except (ValueError, TypeError):
                            pass
                            
                    elif condition_type == "in_list":
                        if isinstance(value, list):
                            if field and field in session.context:
                                if session.context[field] in value:
                                    return transition.target_node_id
                            elif user_input_stripped in value:
                                return transition.target_node_id
                                
                # Handle string-based conditions (simple expressions)
                elif isinstance(condition, str):
                    if self._evaluate_condition(condition, session.context, user_input_stripped):
                        return transition.target_node_id
        
        return None
    
    def _evaluate_condition(
        self,
        condition: Union[str, TransitionCondition],
        context: Dict[str, Any],
        user_input: str
    ) -> bool:
        """Evaluate a condition."""
        try:
            # Handle object-based condition
            if isinstance(condition, TransitionCondition):
                if condition.type == TransitionConditionType.ALWAYS:
                    return True
                    
                value_to_check = user_input
                if condition.field:
                    # Extract from context if field is specified
                    found, val = self._find_value_in_nested_dict(context, condition.field)
                    if found:
                        value_to_check = str(val)
                
                target_value = str(condition.value) if condition.value is not None else None
                
                if condition.type == TransitionConditionType.EQUALS:
                    return value_to_check == target_value
                elif condition.type == TransitionConditionType.CONTAINS:
                    return target_value in value_to_check if target_value else False
                elif condition.type == TransitionConditionType.REGEX:
                    import re
                    return bool(re.search(target_value, value_to_check)) if target_value else False
                # Add other types as needed
                return False

            # Handle string-based condition (legacy/custom)
            if isinstance(condition, str):
                # Add user_input to context for evaluation
                eval_context = {**context, "user_input": user_input}
                # WARNING: Using eval is dangerous
                return eval(condition, {"__builtins__": {}}, eval_context)
                
            return False
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False
    
    async def _execute_node_actions(
        self,
        session: ChatSession,
        node: ConvoNode
    ) -> None:
        """Execute actions defined in a node."""
        for action in node.actions:
            try:
                if action.type == "save_to_context":
                    # Save data to session context
                    for key, value in action.params.items():
                        session.context[key] = value
                        
                elif action.type == "api_call":
                    # Make an API call
                    await self._execute_api_action(session, action)
                    
                elif action.type == "send_email":
                    # Send email (implement as needed)
                    logger.info(f"Send email action: {action.params}")
                    # TODO: Implement email sending logic
                    
                else:
                    logger.warning(f"Unknown action type: {action.type}")
                    
            except Exception as e:
                logger.error(f"Error executing action {action.type}: {e}")
                # Decide whether to continue or stop on action failure
                if action.on_failure:
                    # Could implement jumping to failure node
                    pass
    
    async def _execute_api_action(
        self,
        session: ChatSession,
        action: NodeAction
    ) -> None:
        """Execute an API action."""
        if not action.api_action:
            logger.warning("API action called but no api_action configuration found")
            return
        
        api_config = action.api_action
        
        try:
            # Prepare input data from session context
            input_data = {}
            for input_var in api_config.input:
                if input_var in session.context:
                    input_data[input_var] = session.context[input_var]
                else:
                    logger.warning(f"Input variable '{input_var}' not found in session context")
            
            # Prepare headers
            headers = api_config.headers or {}
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
            
            # Make the API call
            async with httpx.AsyncClient(timeout=api_config.timeout) as client:
                logger.info(f"Making {api_config.method} request to {api_config.url}")
                logger.debug(f"Request data: {input_data}")
                
                if api_config.method.upper() == "GET":
                    response = await client.get(
                        api_config.url,
                        params=input_data,
                        headers=headers
                    )
                elif api_config.method.upper() == "POST":
                    response = await client.post(
                        api_config.url,
                        json=input_data,
                        headers=headers
                    )
                elif api_config.method.upper() == "PUT":
                    response = await client.put(
                        api_config.url,
                        json=input_data,
                        headers=headers
                    )
                elif api_config.method.upper() == "DELETE":
                    response = await client.delete(
                        api_config.url,
                        json=input_data,
                        headers=headers
                    )
                else:
                    logger.error(f"Unsupported HTTP method: {api_config.method}")
                    return
                
                # Check response status
                response.raise_for_status()
                
                # Parse response
                response_data = response.json()
                logger.info(f"API call successful: {response.status_code}")
                logger.debug(f"Response data: {response_data}")
                
                # Store output variables in session context
                for output_var in api_config.output:
                    found, value = self._find_value_in_nested_dict(response_data, output_var)
                    if found:
                        session.context[output_var] = value
                        logger.debug(f"Stored '{output_var}' in session context: {value}")
                    else:
                        logger.warning(f"Output variable '{output_var}' not found in API response")
                                
                # Mark action as successful
                if action.on_success:
                    logger.info(f"Action successful, could jump to node: {action.on_success}")
                    
        except httpx.HTTPStatusError as e:
            logger.error(f"API call failed with status {e.response.status_code}: {e}")
            if action.on_failure:
                logger.info(f"Action failed, could jump to node: {action.on_failure}")
        except httpx.RequestError as e:
            logger.error(f"API request error: {e}")
            if action.on_failure:
                logger.info(f"Action failed, could jump to node: {action.on_failure}")
        except Exception as e:
            logger.error(f"Unexpected error during API call: {e}", exc_info=True)
            if action.on_failure:
                logger.info(f"Action failed, could jump to node: {action.on_failure}")

    async def _process_media_service_action(
        self,
        session: ChatSession,
        api_config: Any, # ApiAction
        file_path: str,
        media_url: str
    ) -> str:
        """
        Execute a service action with media upload.
        Returns a summary string of the result.
        """
        import os
        try:
            # Prepare input data (form fields)
            input_data = {}
            for input_var in api_config.input:
                if input_var in session.context:
                    # Form data usually expects strings
                    input_data[input_var] = str(session.context[input_var])
                else:
                    logger.warning(f"Input variable '{input_var}' not found in session context")
            
            # headers
            headers = api_config.headers or {}
            # Do NOT set Content-Type to application/json, httpx will set multipart/form-data with boundary
            if "Content-Type" in headers and "json" in headers["Content-Type"]:
                del headers["Content-Type"]
            
            # Prepare file
            filename = os.path.basename(file_path)
            
            # Using context manager for file
            async with httpx.AsyncClient(timeout=api_config.timeout or 60.0) as client:
                logger.info(f"Uploading media to {api_config.url} ({api_config.method})")
                
                with open(file_path, 'rb') as f:
                    # 'files' dict: key is field name, value is (filename, file_object, content_type)
                    files = {
                        'file': (filename, f, 'application/octet-stream') 
                    }
                    
                    if api_config.method.upper() == "POST":
                        response = await client.post(
                            api_config.url,
                            data=input_data,
                            files=files,
                            headers=headers
                        )
                    elif api_config.method.upper() == "PUT":
                        response = await client.put(
                            api_config.url,
                            data=input_data,
                            files=files,
                            headers=headers
                        )
                    else:
                         logger.warning(f"Method {api_config.method} might not support file upload body.")
                         raise APIServiceException(f"Method {api_config.method} not supported for media upload")

                response.raise_for_status()

                response_data = response.json()
                logger.debug(f"API output: {api_config.output}")
                logger.debug(f"API call successful: {response.status_code}")
                logger.debug(f"Response data: {response_data}")
                
                # Store output variables in session context
                for output_var in api_config.output:
                    found, value = self._find_value_in_nested_dict(response_data, output_var)
                    if found:
                        session.context[output_var] = value
                        logger.debug(f"Stored '{output_var}' in session context: {value}")
                    else:
                        logger.warning(f"Output variable '{output_var}' not found in API response")

                return f"Success {response.status_code}"
            
        except Exception as e:
            logger.error(f"Error in media service action: {e}", exc_info=True)
            raise APIServiceException(f"Service upload failed: {str(e)}")

    async def _process_media_email_action(
        self,
        session: ChatSession,
        config: Any, # EmailConfig
        file_path: str,
        media_url: str
    ) -> None:
        """Send an email with the media attachment."""
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        
        try:
            # Render templates
            to_email = self._render_template(config.to_email, session.context)
            subject = self._render_template(config.subject, session.context)
            body = self._render_template(config.body, session.context)
            
            msg = MIMEMultipart()
            msg['From'] = config.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach file
            filename = media_url.split("/")[-1]
            if not filename:
                filename = "attachment"
                
            with open(file_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f"attachment; filename= {filename}",
                )
                msg.attach(part)
            
            # Connect to SMTP server
            # Note: synchronous smtplib is used here. For high throughput, use aiosmtplib.
            # Assuming low volume for now or wrap in run_in_executor if needed.
            server = smtplib.SMTP(config.smtp_server, config.smtp_port)
            server.starttls()
            server.login(config.username, config.password)
            text = msg.as_string()
            server.sendmail(config.from_email, to_email, text)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise APIServiceException(f"Failed to send email: {str(e)}")

    async def _process_media_ai_service_action(
        self,
        session: ChatSession,
        config: Any, # AiMediaConfig
        file_path: str
    ) -> str:
        """Process media with AI service."""
        import base64
        
        try:
            # Encode image to base64
            with open(file_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Authenticate with AI Service
            login_url = f"{self.ai_service_url}/api/v1/auth/login"
            login_payload = {
                "email": self.settings.ai_system_user,
                "password": self.settings.ai_system_password
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                login_response = await client.post(login_url, json=login_payload)
                login_response.raise_for_status()
                token = login_response.json()["access_token"]
            
            # Prepare payload
            query = self._render_template(config.query, session.context)
            
            payload = {
                "query": query,
                "image_base64": encoded_string,
                "system_message": config.system_message,
                "session_id": session.session_id,
                "max_documents": 10,
                "min_score": 0.7,
                "metadata": config.metadata,
                "include_metadata": True,
                "include_chat_history": config.include_chat_history,
                "max_history_messages": config.max_history_messages,
                "temperature": config.temperature,
                "llm_model": config.llm_model,
                "llm_provider": config.llm_provider,
                "evaluation_metrics": False,
                # "context": str(session.context) # Optional
            }
            
            # Call AI Service
            # Assuming a generic chat endpoint that handles images if image_base64 is present
            # or a specific endpoint if needed. Using the query endpoint as per standard.
            url = f"{self.ai_service_url}/api/v1/query/agent" # Defaulting to agent or configurable?
            # User example schema matches the query endpoint payload structure usually seen.
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {token}"
            }
            
            async with httpx.AsyncClient(timeout=120.0) as client: # Longer timeout for image processing
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code != 200:
                    logger.error(f"AI service error: {response.status_code} - {response.text}")
                    raise APIServiceException(f"AI service returned error: {response.text}")
                
                result = response.json()
                return result.get("answer", "")
                
        except Exception as e:
            logger.error(f"Error calling AI service for media: {e}")
            raise APIServiceException(f"Failed to process media with AI service: {str(e)}")
    async def _validate_input(
        self,
        user_input: str,
        validations: List[Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate user input against validation rules."""
        import re
        
        for validation in validations:
            # Handle ValidationRule objects
            if hasattr(validation, 'type'):
                validation_type = validation.type
                params = validation.params if hasattr(validation, 'params') else {}
                error_message = validation.error_message if hasattr(validation, 'error_message') else "Validation failed"
                
                # Required validation
                if validation_type == "required":
                    if not user_input or not user_input.strip():
                        return False, error_message or "This field is required."
                
                # Minimum length validation
                elif validation_type == "min_length":
                    min_len = params.get("value", params.get("min", 0))
                    if len(user_input) < min_len:
                        return False, error_message or f"Input must be at least {min_len} characters."
                
                # Maximum length validation
                elif validation_type == "max_length":
                    max_len = params.get("value", params.get("max", 1000))
                    if len(user_input) > max_len:
                        return False, error_message or f"Input must not exceed {max_len} characters."
                
                # Length range validation
                elif validation_type == "length":
                    min_len = params.get("min", 0)
                    max_len = params.get("max", float('inf'))
                    if len(user_input) < min_len or len(user_input) > max_len:
                        return False, error_message or f"Input must be between {min_len} and {max_len} characters."
                
                # Email validation
                elif validation_type == "email":
                    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                    if not re.match(email_pattern, user_input.strip()):
                        return False, error_message or "Please enter a valid email address."
                
                # Phone validation
                elif validation_type == "phone":
                    # Remove common phone number characters
                    phone_digits = re.sub(r'[\s\-\(\)\+]', '', user_input)
                    # Check if it's a valid phone number (10-15 digits)
                    if not re.match(r'^\d{10,15}$', phone_digits):
                        return False, error_message or "Please enter a valid phone number."
                
                # Number validation
                elif validation_type == "number":
                    try:
                        float(user_input.strip())
                    except ValueError:
                        return False, error_message or "Please enter a valid number."
                
                # Integer validation
                elif validation_type == "integer":
                    try:
                        int(user_input.strip())
                    except ValueError:
                        return False, error_message or "Please enter a valid integer."
                
                # Regex pattern validation
                elif validation_type == "regex":
                    pattern = params.get("pattern", params.get("value"))
                    if pattern and not re.match(pattern, user_input):
                        return False, error_message or "Input does not match the required format."
                
                # Range validation (for numbers)
                elif validation_type == "range":
                    try:
                        value = float(user_input.strip())
                        min_val = params.get("min", float('-inf'))
                        max_val = params.get("max", float('inf'))
                        if value < min_val or value > max_val:
                            return False, error_message or f"Value must be between {min_val} and {max_val}."
                    except ValueError:
                        return False, error_message or "Please enter a valid number."
                
                # URL validation
                elif validation_type == "url":
                    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
                    if not re.match(url_pattern, user_input.strip(), re.IGNORECASE):
                        return False, error_message or "Please enter a valid URL."
                
                # Date validation
                elif validation_type == "date":
                    date_format = params.get("format", "%Y-%m-%d")
                    try:
                        from datetime import datetime
                        datetime.strptime(user_input.strip(), date_format)
                    except ValueError:
                        return False, error_message or f"Please enter a valid date in format {date_format}."
                
                # Alphanumeric validation
                elif validation_type == "alphanumeric":
                    if not re.match(r'^[a-zA-Z0-9]+$', user_input):
                        return False, error_message or "Input must contain only letters and numbers."
                
                # Alpha (letters only) validation
                elif validation_type == "alpha":
                    if not re.match(r'^[a-zA-Z]+$', user_input):
                        return False, error_message or "Input must contain only letters."
                
                # In list validation
                elif validation_type == "in_list":
                    allowed_values = params.get("values", params.get("list", []))
                    if user_input.strip() not in allowed_values:
                        return False, error_message or f"Input must be one of: {', '.join(allowed_values)}."
                
                # Not in list validation
                elif validation_type == "not_in_list":
                    forbidden_values = params.get("values", params.get("list", []))
                    if user_input.strip() in forbidden_values:
                        return False, error_message or "This value is not allowed."
                
                # Custom validation (if needed)
                else:
                    logger.warning(f"Unknown validation type: {validation_type}")
        
        # All validations passed
        return True, None

    def _find_value_in_nested_dict(self, data: Any, key: str) -> tuple[bool, Any]:
        """
        Recursively search for a key in nested dictionaries and lists.
        Returns: (found: bool, value: Any)
        """
        if isinstance(data, dict):
            # Check if key exists at current level
            if key in data:
                return True, data[key]
            
            # Search in nested dictionaries
            for value in data.values():
                found, result = self._find_value_in_nested_dict(value, key)
                if found:
                    return True, result
        
        elif isinstance(data, list):
            # Search in list items
            for item in data:
                found, result = self._find_value_in_nested_dict(item, key)
                if found:
                    return True, result
        
        return False, None

    async def _update_session(self, session: ChatSession) -> None:
        """Update session in database."""
        try:
            session_dict = session.model_dump()
            session_dict["updated_at"] = datetime.utcnow()
            await self.sessions_collection.replace_one(
                {"session_id": session.session_id},
                session_dict
            )
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            raise APIServiceException(
                message="Failed to update session",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def end_chat_session(self, session_id: str) -> bool:
        """End a chat session."""
        try:
            session = await self.get_chat_session(session_id)
            if not session:
                raise APIServiceException(
                    message=f"Chat session '{session_id}' not found",
                    http_status_code=404
                )
            
            session.completed = True
            await self._update_session(session)
            
            logger.info(f"Ended chat session: {session_id}")
            return True
            
        except APIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error ending chat session: {e}")
            raise APIServiceException(
                message="Failed to end chat session",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a chat session by ID."""
        try:
            session_data = await self.sessions_collection.find_one({"session_id": session_id})
            if not session_data:
                return None
        
            return ChatSession(**session_data)
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            raise APIServiceException(
                message="Failed to get session",
                details={"error": str(e)},
                http_status_code=500
            )


    async def end_session(self, session_id: str) -> None:
        """End a chat session."""
        try:
            result = await self.sessions_collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "completed": True,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        
            if result.matched_count == 0:
                raise APIServiceException(
                    message=f"Session '{session_id}' not found",
                    http_status_code=404
                )
        
            logger.info(f"Ended session: {session_id}")
        except APIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            raise APIServiceException(
                message="Failed to end session",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def _process_user_input(
        self, 
        session: ChatSession, 
        node: ConvoNode, 
        user_input: str,
        convo: ConvoDefinition
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Process user input and determine next node.
        Returns: (next_node_id, error_message)
        """
        # Validate input if node has validation rules
        if node.collect_input and hasattr(node, 'validations') and node.validations:
            is_valid, validation_error = await self._validate_input(user_input, node.validations)
            if not is_valid:
                logger.warning(f"Input validation failed: {validation_error}")
                return None, validation_error
        
        # Store input if node collects it
        if node.collect_input and node.input_field:
            session.context[node.input_field] = user_input
            logger.info(f"Stored input field '{node.input_field}' in session context: {user_input}")
        
        # Execute node actions after collecting input
        if node.actions:
            await self._execute_node_actions(session, node)
        
        # Handle option-based transitions (MENU nodes)
        if node.type == NodeType.MENU and node.transitions:
            user_input_clean = user_input.strip()
            
            # Try to match by number (1-indexed)
            try:
                option_num = int(user_input_clean)
                if 1 <= option_num <= len(node.transitions):
                    transition = node.transitions[option_num - 1]
                    logger.info(f"Matched option {option_num} -> {transition.target_node_id}")
                    return transition.target_node_id, None
            except ValueError:
                pass
            
            # Try to match by label (case-insensitive)
            user_input_lower = user_input_clean.lower()
            for transition in node.transitions:
                if transition.label and user_input_lower == transition.label.lower():
                    logger.info(f"Matched label '{transition.label}' -> {transition.target_node_id}")
                    return transition.target_node_id, None
            
            # No match found
            error_msg = f"⚠️ Invalid selection for {node.name}. Please choose from the options provided.\n\nType 'menu' to return to main menu."
            logger.warning(f"No match found for input '{user_input}' on node {node.id}")
            return None, error_msg
        
        # Handle conditional transitions
        for transition in sorted(node.transitions, key=lambda t: t.priority, reverse=True):
            if not transition.condition:
                # Unconditional transition
                return transition.target_node_id, None
            
            # Evaluate condition
            if self._evaluate_condition(transition.condition, session.context, user_input):
                return transition.target_node_id, None
        
        # Use default transition if available
        if node.default_transition:
            return node.default_transition, None
        
        # No valid transition found
        return None, "I'm not sure how to proceed. Please try again or type 'menu' to return to the main menu."
    
    async def process_message(
        self,
        session_id: str,
        message: str
    ) -> ChatResponse:
        """Process a user message in a chat session."""
        try:
            # Get session
            session_data = await self.sessions_collection.find_one({"session_id": session_id})
            if not session_data:
                raise APIServiceException(
                    message=f"Session '{session_id}' not found",
                    http_status_code=404
                )
            
            session = ChatSession(**session_data)
            
            # Get convo
            convo = await self.get_convo(session.convo_id)
            if not convo:
                raise APIServiceException(
                    message=f"Convo '{session.convo_id}' not found",
                    http_status_code=404
                )
            
            # Get current node
            current_node = next(
                (node for node in convo.nodes if node.id == session.current_node_id),
                None
            )
            
            if not current_node:
                raise APIServiceException(
                    message=f"Current node '{session.current_node_id}' not found",
                    http_status_code=500
                )
            
            logger.info(f"Processing message on node {current_node.id} (type: {current_node.type})")
            logger.info(f"Node has {len(current_node.transitions)} transitions")
            logger.info(f"User input: '{message}'")
            
            # Process the node with user input
            response_data = await self._process_node(session, current_node, message, convo)
            
            # Update session in database
            session.last_activity = datetime.utcnow()
            await self.sessions_collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "current_node_id": session.current_node_id,
                        "context": session.context,
                        "history": [msg.model_dump() for msg in session.history],
                        "last_activity": session.last_activity,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"After processing: current_node_id = {session.current_node_id}")
            
            # Create response
            response = ChatResponse(
                session_id=session.session_id,
                message=response_data.get("message", ""),
                node_id=response_data.get("node_id"),
                node_type=response_data.get("node_type"),
                expects_input=response_data.get("requires_input", False),
                input_type=response_data.get("input_type"),
                input_field=response_data.get("input_field"),
                completed=response_data.get("completed", False),
                context=session.context,
                options=response_data.get("options", [])
            )
            
            return response
            
        except APIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            raise APIServiceException(
                message="Failed to process message",
                details={"error": str(e)},
                http_status_code=500
            )
            
            
            
            
    
    async def _handle_navigation_commands(
        self,
        user_input: str,
        session: ChatSession,
        convo: ConvoDefinition
    ) -> Optional[Dict[str, Any]]:
        """Handle special navigation commands like 'menu', 'back', 'restart'."""
        command = user_input.strip().lower()
        
        if command in ["menu", "main menu", "main"]:
            # Return to start node
            start_node = next(
                (node for node in convo.nodes if node.type == NodeType.START or node.type == NodeType.MENU),
                None
            )
            
            if not start_node:
                logger.error("No start node found in convo")
                return None
            
            # Add user message to history
            session.history.append({
                "role": "user",
                "content": user_input,
                "node_id": session.current_node_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Update session to start node
            session.current_node_id = start_node.id
            
            # Add bot response to history
            session.history.append({
                "role": "assistant",
                "content": start_node.message or "Returning to main menu...",
                "node_id": start_node.id,
                "timestamp": datetime.utcnow().isoformat()
            }.model_dump())
            
            # Build options for start node
            options = []
            if start_node.type == NodeType.MENU and start_node.transitions:
                for idx, transition in enumerate(start_node.transitions, 1):
                    options.append({
                        "value": str(idx),
                        "label": transition.label or f"Option {idx}",
                        "target_node_id": transition.target_node_id
                    })
            
            logger.info(f"Navigation: Returned to main menu (node: {start_node.id})")
            
            return {
                "message": start_node.message or "Returning to main menu...",
                "node_id": start_node.id,
                "node_type": start_node.type,
                "requires_input": start_node.collect_input,
                "input_type": start_node.input_type if start_node.collect_input else None,
                "input_field": start_node.input_field if start_node.collect_input else None,
                "completed": False,
                "options": options
            }
        
        elif command in ["back", "previous"]:
            # Go back to previous node (if history exists)
            if len(session.history) >= 2:
                # Find the last assistant message before the current one
                for i in range(len(session.history) - 1, -1, -1):
                    msg = session.history[i]
                    if msg.get("role") == "assistant" and msg.get("node_id") != session.current_node_id:
                        previous_node_id = msg.get("node_id")
                        previous_node = next(
                            (node for node in convo.nodes if node.id == previous_node_id),
                            None
                        )
                        
                        if previous_node:
                            # Add user message to history
                            session.history.append({
                                "role": "user",
                                "content": user_input,
                                "node_id": session.current_node_id,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                            
                            # Update session to previous node
                            session.current_node_id = previous_node.id
                            
                            # Add bot response to history
                            session.history.append({
                                "role": "assistant",
                                "content": previous_node.message or "Going back...",
                                "node_id": previous_node.id,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                            
                            # Build options
                            options = []
                            if previous_node.type == NodeType.MENU and previous_node.transitions:
                                for idx, transition in enumerate(previous_node.transitions, 1):
                                    options.append({
                                        "value": str(idx),
                                        "label": transition.label or f"Option {idx}",
                                        "target_node_id": transition.target_node_id
                                    })
                            
                            logger.info(f"Navigation: Went back to node {previous_node.id}")
                            
                            return {
                                "message": previous_node.message or "Going back...",
                                "node_id": previous_node.id,
                                "node_type": previous_node.type,
                                "requires_input": previous_node.collect_input,
                                "input_type": previous_node.input_type if previous_node.collect_input else None,
                                "input_field": previous_node.input_field if previous_node.collect_input else None,
                                "completed": False,
                                "options": options
                            }
                        break
        
        elif command in ["restart", "start over", "hello", "hi"]:
            # Restart the conversation
            start_node = next(
                (node for node in convo.nodes if node.id == convo.start_node_id),
                None
            )
            
            if start_node:
                # Clear context and history
                session.context = {}
                session.history = []
                session.current_node_id = start_node.id
                
                # Add initial bot message
                session.history.append({
                    "role": "assistant",
                    "content": start_node.message or "Starting over...",
                    "node_id": start_node.id,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Build options
                options = []
                if start_node.type == NodeType.MENU and start_node.transitions:
                    for idx, transition in enumerate(start_node.transitions, 1):
                        options.append({
                            "value": str(idx),
                            "label": transition.label or f"Option {idx}",
                            "target_node_id": transition.target_node_id
                        })
                
                logger.info("Navigation: Restarted conversation")
                
                return {
                    "message": start_node.message or "Starting over...",
                    "node_id": start_node.id,
                    "node_type": start_node.type,
                    "requires_input": start_node.collect_input,
                    "input_type": start_node.input_type if start_node.collect_input else None,
                    "input_field": start_node.input_field if start_node.collect_input else None,
                    "completed": False,
                    "options": options
                }
        
        return None
    
    async def create_ai_chat_session(
        self,
        request: AIChatSessionCreate,
        user_id: Optional[str] = None
    ) -> AIChatSession:
        """Create a new AI chat session."""
        try:
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Use provided user_id or from request
            final_user_id = user_id or request.user_id
            
            # Create session object
            session = AIChatSession(
                session_id=session_id,
                user_id=final_user_id,
                tenant_uid=request.metadata.get('tenant_uid') if request.metadata else None,
                title=request.title or f"Chat Session {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                created_at=datetime.utcnow(),
                last_used=datetime.utcnow(),
                active=True,
                metadata=request.metadata
            )
            
            # Save to database
            session_dict = session.model_dump()
            await self.ai_chat_sessions_collection.insert_one(session_dict)
            
            logger.info(f"Created AI chat session: {session_id} for user: {final_user_id}")
            return session
            
        except Exception as e:
            logger.error(f"Error creating AI chat session: {e}")
            raise APIServiceException(
                message="Failed to create AI chat session",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def get_ai_chat_session(self, session_id: str) -> Optional[AIChatSession]:
        """Get an AI chat session by ID."""
        try:
            session_dict = await self.ai_chat_sessions_collection.find_one(
                {"session_id": session_id}
            )
            if not session_dict:
                return None
            
            session_dict.pop("_id", None)
            return AIChatSession(**session_dict)
            
        except Exception as e:
            logger.error(f"Error getting AI chat session: {e}")
            raise APIServiceException(
                message="Failed to get AI chat session",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def list_ai_chat_sessions(
        self,
        user_id: Optional[str] = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 50
    ) -> List[AIChatSession]:
        """List AI chat sessions."""
        try:
            query = {}
            if user_id:
                query["user_id"] = user_id
            if active_only:
                query["active"] = True
            
            cursor = self.ai_chat_sessions_collection.find(query)\
                .sort("last_used", -1)\
                .skip(skip)\
                .limit(limit)
            
            sessions = []
            async for session_dict in cursor:
                session_dict.pop("_id", None)
                sessions.append(AIChatSession(**session_dict))
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error listing AI chat sessions: {e}")
            raise APIServiceException(
                message="Failed to list AI chat sessions",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def send_ai_chat_message(
        self,
        query: AIChatQuery,
        user_id: Optional[str] = None
    ) -> AIChatResponse:
        """Send a message to the AI chat service."""
        try:
            # Get or create session
            session = None
            if query.session_id:
                session = await self.get_ai_chat_session(query.session_id)
                if not session:
                    raise APIServiceException(
                        message=f"AI chat session '{query.session_id}' not found",
                        http_status_code=404
                    )
            else:
                # Create new session
                session = await self.create_ai_chat_session(
                    AIChatSessionCreate(user_id=user_id),
                    user_id=user_id
                )
            
            # Get chat history if requested
            chat_history = []
            if query.include_chat_history:
                chat_history = await self._get_ai_chat_history(
                    session.session_id,
                    limit=query.max_history_messages
                )
            
            # Save user message to history
            await self._save_ai_chat_message(
                session.session_id,
                "user",
                query.query,
                session.tenant_uid
            )
            
            # Call AI service
            ai_response = await self._call_ai_service(
                session.session_id,
                query.query,
                chat_history,
                query.llm_model,
                query.llm_provider
            )
            
            # Save AI response to history
            await self._save_ai_chat_message(
                session.session_id,
                "assistant",
                ai_response,
                session.tenant_uid
            )
            
            # Update session last_used
            await self.ai_chat_sessions_collection.update_one(
                {"session_id": session.session_id},
                {
                    "$set": {
                        "last_used": datetime.utcnow()
                    }
                }
            )
            
            # Create response
            response = AIChatResponse(
                answer=ai_response,
                session_id=session.session_id,
                timestamp=datetime.utcnow(),
                metadata={
                    "model": query.llm_model,
                    "history_included": query.include_chat_history
                }
            )
            
            logger.info(f"AI chat message processed for session: {session.session_id}")
            return response
            
        except APIServiceException:
            raise
        except Exception as e:
            logger.error(f"Error sending AI chat message: {e}")
            raise APIServiceException(
                message="Failed to send AI chat message",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def _call_ai_service(
        self,
        session_id: str,
        query: str,
        chat_history: List[Dict[str, str]],
        ai_config: Dict[str, str],
       
    ) -> str:
        """Call the external AI service."""
        try:
            
            login_url = f"{self.ai_service_url}/api/v1/auth/login"

            login_payload = {
                "email": self.settings.ai_system_user,
                "password": self.settings.ai_system_password
            }
            login_headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                login_response = await client.post(
                    login_url,
                    json=login_payload,
                    headers=login_headers
                )
                
                login_response.raise_for_status()
                login_json = login_response.json()
                token = login_json["access_token"]
            
            url = f"{self.ai_service_url}/api/v1/query/" + ai_config.query_type
            
            payload = {
                "session_id": session_id,
                "query": query,
                "chat_history": chat_history,
                "llm_model": ai_config.llm_model,
                "llm_provider": ai_config.llm_provider,
                "system_message": ai_config.system_prompt,
                "max_history_messages": 10,
                "max_documents": 10,
                "min_score": 0.1,
                "strategy": "simple",
                "include_metadata": True,
                "include_chat_history": False,
                "max_history_messages": 5,
                "temperature": 0.1,
                "filter": {"source_table": "frequently_asked_questions"}
            }
            
            headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f"Bearer {token}"
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code != 200:
                    logger.error(f"AI service error: {response.status_code} - {response.text}")
                    raise APIServiceException(
                        message="AI service returned an error",
                        details={
                            "status_code": response.status_code,
                            "error": response.text
                        },
                        http_status_code=500
                    )
                
                result = response.json()
                return result.get("answer", "I apologize, but I couldn't generate a response.")
                
        except httpx.TimeoutException:
            logger.error("AI service request timed out")
            raise APIServiceException(
                message="AI service request timed out",
                http_status_code=504
            )
        except httpx.RequestError as e:
            logger.error(f"AI service request error: {e}")
            raise APIServiceException(
                message="Failed to connect to AI service",
                details={"error": str(e)},
                http_status_code=503
            )
    
    async def _get_ai_chat_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """Get chat history for a session."""
        try:
            cursor = self.ai_chat_history_collection.find(
                {"session_id": session_id}
            ).sort("timestamp", -1).limit(limit)
            
            messages = []
            async for msg in cursor:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Reverse to maintain chronological order (oldest first)
            messages.reverse()
            return messages
            
        except Exception as e:
            logger.error(f"Error getting AI chat history: {e}")
            raise APIServiceException(
                message="Failed to get AI chat history",
                details={"error": str(e)},
                http_status_code=500
            )
    
    async def _save_ai_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tenant_uid: Optional[str] = None
    ) -> None:
        """Save a message to AI chat history."""
        try:
            message = {
                "session_id": session_id,
                "role": role,
                "content": content,
                "tenant_uid": tenant_uid,
                "timestamp": datetime.utcnow()
            }
            
            await self.ai_chat_history_collection.insert_one(message)
            
        except Exception as e:
            logger.error(f"Error saving AI chat message: {e}")
            # Don't raise exception as this shouldn't break the flow
