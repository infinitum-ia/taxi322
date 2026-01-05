"""Thread management endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.services.graph_service import GraphService
from app.api.deps import get_graph_service


router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("/{thread_id}")
async def get_thread_history(
    thread_id: str,
    graph_service: GraphService = Depends(get_graph_service)
):
    """
    Get the conversation history for a thread.

    Args:
        thread_id: Thread ID to retrieve
        graph_service: Graph service (injected)

    Returns:
        Thread history with all messages and state
    """
    try:
        state = graph_service.get_thread_state(thread_id)

        if "error" in state:
            raise HTTPException(status_code=404, detail=state["error"])

        return state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{thread_id}/state")
async def get_thread_state(
    thread_id: str,
    graph_service: GraphService = Depends(get_graph_service)
):
    """
    Get the current state of a thread.

    Args:
        thread_id: Thread ID
        graph_service: Graph service (injected)

    Returns:
        Current thread state
    """
    try:
        state = graph_service.get_thread_state(thread_id)

        if "error" in state:
            raise HTTPException(status_code=404, detail=state["error"])

        return {
            "thread_id": thread_id,
            "dialog_state": state.get("dialog_state", []),
            "current_assistant": state.get("dialog_state", [])[-1] if state.get("dialog_state") else "primary_assistant",
            "is_waiting": len(state.get("next", [])) > 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{thread_id}")
async def delete_thread(
    thread_id: str,
    graph_service: GraphService = Depends(get_graph_service)
):
    """
    Delete a thread and its checkpoint data.

    Note: This functionality depends on the checkpointer implementation.
    MemorySaver doesn't support deletion, but persistent checkpointers do.

    Args:
        thread_id: Thread ID to delete
        graph_service: Graph service (injected)

    Returns:
        Success message
    """
    # TODO: Implement deletion when using persistent checkpointer
    return {
        "message": "Thread deletion not yet implemented with current checkpointer",
        "thread_id": thread_id,
        "note": "Use persistent checkpointer (Redis/Postgres) for this feature"
    }
