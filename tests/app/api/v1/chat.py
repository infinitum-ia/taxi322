"""Chat endpoints for the taxi customer support API."""

from fastapi import APIRouter, Depends, HTTPException

from app.models.api import ChatRequest, ChatResponse, ChatContinueRequest
from app.services.graph_service import GraphService
from app.api.deps import get_graph_service


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse, response_model_by_alias=True)
async def chat(
    request: ChatRequest,
    graph_service: GraphService = Depends(get_graph_service)
) -> ChatResponse:
    """
    Send a message to the assistant.

    Creates a new thread if thread_id is not provided.
    Returns the assistant's response and thread_id.
    If an interrupt occurs, returns interrupt information.

    Args:
        request: Chat request with message and user_id
        graph_service: Graph service (injected)

    Returns:
        ChatResponse with messages and interrupt info
    """
    try:
        response = await graph_service.invoke_chat(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/continue", response_model=ChatResponse, response_model_by_alias=True)
async def continue_chat(
    request: ChatContinueRequest,
    graph_service: GraphService = Depends(get_graph_service)
) -> ChatResponse:
    """
    Continue a conversation after an interrupt.

    This endpoint is used to resume execution after the user
    has reviewed and approved a pending action (e.g., booking a trip).

    Args:
        request: Continue request with thread_id
        graph_service: Graph service (injected)

    Returns:
        ChatResponse with continued conversation
    """
    try:
        response = await graph_service.continue_chat(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{thread_id}/interrupt/approve", response_model=ChatResponse, response_model_by_alias=True)
async def approve_action(
    thread_id: str,
    graph_service: GraphService = Depends(get_graph_service)
) -> ChatResponse:
    """
    Approve a pending sensitive action and continue.

    Shorthand for calling /chat/continue with approve command.

    Args:
        thread_id: Thread ID to continue
        graph_service: Graph service (injected)

    Returns:
        ChatResponse with continued conversation
    """
    try:
        request = ChatContinueRequest(thread_id=thread_id, command="approve")
        response = await graph_service.continue_chat(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{thread_id}/interrupt/reject", response_model=ChatResponse, response_model_by_alias=True)
async def reject_action(
    thread_id: str,
    graph_service: GraphService = Depends(get_graph_service)
) -> ChatResponse:
    """
    Reject a pending sensitive action.

    Currently, rejection is handled by simply not proceeding.
    The user can send a new message to clarify their intent.

    Args:
        thread_id: Thread ID
        graph_service: Graph service (injected)

    Returns:
        ChatResponse indicating rejection
    """
    try:
        return ChatResponse(
            thread_id=thread_id,
            message="Acción cancelada. ¿En qué más puedo ayudarte?",
            transfer_to_human="false",
            fin="false"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
