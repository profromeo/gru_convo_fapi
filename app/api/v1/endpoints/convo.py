
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.core.models.convo import (
    ConvoDefinition,
    ChatRequest,
    ChatResponse,
    ChatSession,
    ChatMessageRequest
)
from app.core.services.convo_service import ConvoService
from app.db.mongodb import get_database
from app.core.auth.dependencies import get_current_user
from app.core.models.users import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def get_convo_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> ConvoService:
    """Dependency to get convo service instance."""
    settings = get_settings()
    return ConvoService(settings, db)


@router.post("/convos", response_model=ConvoDefinition, status_code=status.HTTP_201_CREATED)
async def create_convo(
    convo: ConvoDefinition,
    service: ConvoService = Depends(get_convo_service),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new convo definition.
    
    Requires authentication.
    """
    try:
        # Set created_by from current user
        convo.created_by = current_user.user_id
        
        # Set tenant_uid from user context if not provided
        if not convo.tenant_uid:
            convo.tenant_uid = service._get_tenant_uid(None, current_user)
        
        result = await service.create_convo(convo)
        logger.info(f"User {current_user.email} created convo: {convo.id}")
        return result
    except Exception as e:
        logger.error(f"Error creating convo: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/convos", response_model=List[ConvoDefinition])
async def list_convos(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    tenant_uid: Optional[str] = Query(None, description="Filter by tenant/company ID"),
    service: ConvoService = Depends(get_convo_service),
    current_user: User = Depends(get_current_user)
):
    """
    List all convo definitions.
    
    Requires authentication.
    """
    try:
        convos = await service.list_convos(skip=skip, limit=limit, tenant_uid=tenant_uid)
        return convos
    except Exception as e:
        logger.error(f"Error listing convos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list convos"
        )


@router.get("/convos/{convo_id}", response_model=ConvoDefinition)
async def get_convo(
    convo_id: str,
    service: ConvoService = Depends(get_convo_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific convo by ID.
    
    Requires authentication.
    """
    try:
        convo = await service.get_convo(convo_id)
        if not convo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Convo '{convo_id}' not found"
            )
        return convo
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting convo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get convo"
        )


@router.put("/convos/{convo_id}", response_model=ConvoDefinition)
async def update_convo(
    convo_id: str,
    convo: ConvoDefinition,
    service: ConvoService = Depends(get_convo_service),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing convo.
    
    Requires authentication.
    """
    try:
        result = await service.update_convo(convo_id, convo)
        logger.info(f"User {current_user.email} updated convo: {convo_id}")
        return result
    except Exception as e:
        logger.error(f"Error updating convo: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/convos/{convo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_convo(
    convo_id: str,
    service: ConvoService = Depends(get_convo_service),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a convo.
    
    Requires authentication.
    """
    try:
        await service.delete_convo(convo_id)
        logger.info(f"User {current_user.email} deleted convo: {convo_id}")
        return None
    except Exception as e:
        logger.error(f"Error deleting convo: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Convo '{convo_id}' not found"
        )


# Chat Session Endpoints

@router.post("/chat/start", response_model=ChatResponse)
async def start_chat_session(
    request: ChatRequest,
    service: ConvoService = Depends(get_convo_service),
    current_user: User = Depends(get_current_user)
):
    """
    Start a new chat session with a convo.
    
    Requires authentication.
    """
    try:
        # Set user_id from current user if not provided
        if not request.user_id:
            request.user_id = current_user.user_id
        
        # Set tenant_uid from user context if not provided
        if not request.tenant_uid:
            request.tenant_uid = service._get_tenant_uid(None, current_user)
        
        response = await service.start_chat_session(request)
        logger.info(f"User {current_user.email} started chat session: {response.session_id}")
        return response
    except Exception as e:
        logger.error(f"Error starting chat session: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/chat/{session_id}/message", response_model=ChatResponse)
async def send_chat_message(
    session_id: str,
    message: Optional[str] = Query(None, description="User message to send"),
    media_url: Optional[str] = Query(None, description="Media URL (or object name)"),
    body: Optional[ChatMessageRequest] = None,
    service: ConvoService = Depends(get_convo_service),
    current_user: User = Depends(get_current_user)
):
    """
    Send a message to an existing chat session.
    
    Accepts message/media_url either via query params (legacy) or JSON body.
    Requires authentication.
    """
    try:
        # Extract from body if provided
        final_message = message
        final_media_url = media_url
        
        if body:
            if body.message:
                final_message = body.message
            if body.media_url:
                final_media_url = body.media_url
        
        # Validation
        if not final_message and not final_media_url:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'message' or 'media_url' must be provided"
            )

        # Allow empty message if media_url is present, but ensure string for service
        if final_message is None:
            final_message = ""

        response = await service.continue_chat_session(session_id, final_message, media_url=final_media_url)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending chat message: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/chat/{session_id}", response_model=ChatSession)
async def get_chat_session(
    session_id: str,
    service: ConvoService = Depends(get_convo_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a chat session.
    
    Requires authentication.
    """
    try:
        session = await service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat session '{session_id}' not found"
            )
        
        # Verify user has access to this session
        if session.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this chat session"
            )
        
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat session"
        )


# @router.delete("/chat/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def end_chat_session(
#     session_id: str,
#     service: ConvoService = Depends(get_convo_service),
#     current_user: User = Depends(get_current_user)
# ):
#     """
#     End a chat session.
    
#     Requires authentication.
#     """
#     try:
#         # Verify user has access to this session
#         session = await service.get_session(session_id)
#         if session and session.user_id != current_user.user_id:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="You don't have access to this chat session"
#             )
        
#         await service.end_session(session_id)
#         logger.info(f"User {current_user.email} ended chat session: {session_id}")
#         return None
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error ending chat session: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"Chat session '{session_id}' not found"
#         )

@router.post("/chat/{session_id}/end", status_code=status.HTTP_204_NO_CONTENT)
async def end_chat_session_end(
    session_id: str,
    service: ConvoService = Depends(get_convo_service),
    current_user: User = Depends(get_current_user)
):
    """
    End a chat session.
    
    Requires authentication.
    """
    try:
        # Verify user has access to this session
        session = await service.get_session(session_id)
        if session and session.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this chat session"
            )
        
        await service.end_session(session_id)
        logger.info(f"User {current_user.email} ended chat session: {session_id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending chat session: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session '{session_id}' not found"
        )
