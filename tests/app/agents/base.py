"""Base utilities for LangGraph agents."""

import logging
from langchain_core.messages import ToolMessage, AIMessage

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def clean_messages_for_llm(messages: list) -> list:
    """
    Clean messages before sending to LLM API.

    Handles two types of orphaned messages:
    1. ToolMessages without corresponding AIMessage tool_calls
    2. AIMessages with tool_calls that have no ToolMessage responses

    This prevents API errors like: "messages with role 'tool' must be a response
    to a preceeding message with 'tool_calls'."

    Args:
        messages: List of messages to clean

    Returns:
        Cleaned list of messages safe for LLM API
    """
    if not messages:
        return messages

    logger.debug(f"🧹 CLEANING MESSAGES - Total messages: {len(messages)}")

    # Log all messages before cleaning
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        content_preview = str(getattr(msg, 'content', ''))[:50]
        logger.debug(f"  [{i}] {msg_type}: {content_preview}...")

        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            logger.debug(f"      → tool_calls: {msg.tool_calls}")
        elif isinstance(msg, ToolMessage) and hasattr(msg, 'tool_call_id'):
            logger.debug(f"      → tool_call_id: {msg.tool_call_id}")

    # First pass: collect all tool_call_ids from ToolMessages (responses)
    tool_response_ids = set()
    for msg in messages:
        if isinstance(msg, ToolMessage) and hasattr(msg, 'tool_call_id'):
            tool_response_ids.add(msg.tool_call_id)

    # Second pass: clean AIMessages and collect valid tool_call_ids
    cleaned = []
    removed_tool_calls_count = 0
    orphaned_tool_messages = 0

    for msg in messages:
        if isinstance(msg, AIMessage):
            # Check if this AIMessage has tool_calls
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                # Filter out tool_calls that don't have responses
                valid_tool_calls = [
                    tc for tc in msg.tool_calls
                    if isinstance(tc, dict) and tc.get('id') in tool_response_ids
                ]

                removed = len(msg.tool_calls) - len(valid_tool_calls)
                if removed > 0:
                    removed_tool_calls_count += removed
                    orphaned_ids = [
                        tc.get('id', 'NO_ID') for tc in msg.tool_calls
                        if isinstance(tc, dict) and tc.get('id') not in tool_response_ids
                    ]
                    logger.warning(f"  ⚠️  REMOVED {removed} orphaned tool_call(s) from AIMessage: {orphaned_ids}")

                    # Create new AIMessage without orphaned tool_calls
                    if valid_tool_calls:
                        # Keep AIMessage but with filtered tool_calls
                        msg = AIMessage(
                            content=msg.content,
                            tool_calls=valid_tool_calls,
                            id=msg.id if hasattr(msg, 'id') else None,
                            name=msg.name if hasattr(msg, 'name') else None,
                        )
                    else:
                        # Remove tool_calls entirely if none are valid
                        msg = AIMessage(
                            content=msg.content,
                            id=msg.id if hasattr(msg, 'id') else None,
                            name=msg.name if hasattr(msg, 'name') else None,
                        )

            cleaned.append(msg)

        elif isinstance(msg, ToolMessage):
            # Only keep ToolMessages that have a valid tool_call_id
            # (even though we know they exist because we collected them above,
            # this is for consistency)
            if hasattr(msg, 'tool_call_id'):
                cleaned.append(msg)
                logger.debug(f"  ✓ Kept ToolMessage with tool_call_id: {msg.tool_call_id}")
            else:
                orphaned_tool_messages += 1
                logger.warning(f"  ⚠️  REMOVED ToolMessage without tool_call_id")
        else:
            # Keep all other message types (HumanMessage, SystemMessage, etc.)
            cleaned.append(msg)

    logger.debug(
       # f"🧹 CLEANING COMPLETE - Kept: {len(cleaned)}, "
        #f"Removed tool_calls: {removed_tool_calls_count}, "
        f"Removed ToolMessages: {orphaned_tool_messages}"
    )
    return cleaned
