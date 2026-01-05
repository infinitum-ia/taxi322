"""API request and response models."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal, Any


class ChatRequest(BaseModel):
    """Request to send a message to the assistant."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "MESSAGE": "listo",
                "USER_ID": "3042124567",
                "CLIENT_ID": "3042124567",
                "THREAD_ID": "4223b121-31f9-47fc-9851-0435d4dda083"
            }
        }
    )

    message: str = Field(
        ...,
        alias="MESSAGE",
        description="User's message to send to the assistant",
        min_length=1
    )
    thread_id: Optional[str] = Field(
        None,
        alias="THREAD_ID",
        description="Thread ID for conversation continuity. If not provided, a new thread will be created."
    )
    user_id: str = Field(
        ...,
        alias="USER_ID",
        description="User identifier for this conversation",
        min_length=1
    )
    client_id: Optional[str] = Field(
        None,
        alias="CLIENT_ID",
        description="Client phone number or ID (defaults to user_id if not provided)"
    )


class ChatResponse(BaseModel):
    """Response from the assistant - compatible with integration system."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "THREAD_ID": "4223b121-31f9-47fc-9851-0435d4dda083",
                "RESPONSE": "He recibido todos tus datos, pero necesito verificar tu dirección con un asesor.",
                "IS_INTERRUPTED": "true",
                "FIN": "false"
            }
        }
    )

    thread_id: str = Field(
        ...,
        alias="THREAD_ID",
        serialization_alias="THREAD_ID",
        description="Thread ID for this conversation"
    )
    message: str = Field(
        ...,
        alias="RESPONSE",
        serialization_alias="RESPONSE",
        description="AI assistant's response text (ready for TTS)"
    )
    transfer_to_human: str = Field(
        "false",
        alias="IS_INTERRUPTED",
        serialization_alias="IS_INTERRUPTED",
        description="Whether the conversation should be transferred to a human agent (as string: 'true' or 'false')"
    )
    fin: str = Field(
        "false",
        alias="FIN",
        serialization_alias="FIN",
        description="Whether the conversation has ended after service registration (as string: 'true' or 'false')"
    )


class ChatContinueRequest(BaseModel):
    """Request to continue a conversation after an interrupt."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "thread_id": "abc123",
                "command": "approve"
            }
        }
    )

    thread_id: str = Field(
        ...,
        description="Thread ID to continue",
        min_length=1
    )
    command: Optional[Literal["approve", "reject"]] = Field(
        None,
        description="Command to approve or reject the pending action"
    )


class ThreadHistory(BaseModel):
    """Full conversation history for a thread."""

    thread_id: str = Field(..., description="Thread ID")
    messages: list[dict[str, Any]] = Field(..., description="All messages in the thread")
    dialog_state: list[str] = Field(..., description="Stack of active sub-assistants")


class ThreadState(BaseModel):
    """Current state of a thread."""

    thread_id: str = Field(..., description="Thread ID")
    messages: list[dict[str, Any]] = Field(..., description="Current messages")
    dialog_state: list[str] = Field(..., description="Stack of active sub-assistants")
    current_assistant: Optional[str] = Field(
        None,
        description="Name of the currently active assistant"
    )


class ThreadSummary(BaseModel):
    """Summary information about a thread."""

    thread_id: str = Field(..., description="Thread ID")
    user_id: str = Field(..., description="User ID who owns this thread")
    created_at: str = Field(..., description="Timestamp when thread was created")
    last_activity: str = Field(..., description="Timestamp of last activity")
    message_count: int = Field(..., description="Number of messages in the thread")
