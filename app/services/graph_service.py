"""Graph service for invoking the conversation graph."""

import logging
from typing import Optional
import uuid
from langchain_core.messages import HumanMessage

from app.agents.taxi.graph import create_taxi_graph
from app.core.checkpointer import get_checkpointer
from app.models.api import ChatRequest, ChatResponse, ChatContinueRequest

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class GraphService:
    """Service for managing graph invocations and conversation state."""

    def __init__(self):
        """Initialize the graph service with a checkpointer."""
        self.checkpointer = get_checkpointer()
        self.graph = create_taxi_graph(checkpointer=self.checkpointer)

    async def invoke_chat(self, request: ChatRequest) -> ChatResponse:
        """
        Invoke the graph with a user message.

        Args:
            request: Chat request with message, thread_id, and user_id

        Returns:
            ChatResponse with thread_id, messages, and interrupt info
        """
        # Generate thread_id if not provided
        thread_id = request.thread_id or str(uuid.uuid4())

        # Enhanced logging for debugging thread persistence
        if request.thread_id:
            logger.info(f"📨 INVOKE CHAT - Thread: {thread_id} (PROVIDED by client)")
        else:
            logger.info(f"📨 INVOKE CHAT - Thread: {thread_id} (NEW - generated)")

        logger.debug(f"   User message: {request.message[:100]}...")

        # Create config with thread_id and user_id
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": request.user_id,
            }
        }

        # Determine client_id (use provided client_id or fallback to user_id)
        client_id = request.client_id or request.user_id

        # Create input state with user message and client_id
        input_state = {
            "messages": [HumanMessage(content=request.message)],
            "client_id": client_id,
        }

        # Invoke the graph
        try:
            logger.debug("   Invoking graph...")
            result = await self.graph.ainvoke(input_state, config)
            logger.debug(f"   ✓ Graph completed - {len(result.get('messages', []))} messages in result")

            # Check if interrupted
            state = self.graph.get_state(config)
            is_interrupted = len(state.next) > 0

            # Log current state for debugging
            agente_actual = state.values.get("agente_actual")
            logger.debug(f"   📊 Current agente_actual: {agente_actual}")
            logger.debug(f"   📊 Next nodes: {state.next}")

            interrupt_info = None
            if is_interrupted:
                # Get information about the interruption
                next_node = state.next[0] if state.next else None

                # Find the last AIMessage with tool_calls (search backwards)
                messages = state.values.get("messages", [])
                ai_message_with_tools = None
                for msg in reversed(messages):
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        ai_message_with_tools = msg
                        break

                if ai_message_with_tools and ai_message_with_tools.tool_calls:
                    tool_call = ai_message_with_tools.tool_calls[0]
                    interrupt_info = {
                        "node": next_node,
                        "tool": tool_call.get("name"),
                        "args": tool_call.get("args"),
                        "message": f"Do you want to proceed with {tool_call.get('name')}?"
                    }

            # Extract only the LAST AI message content
            # This is sent directly to TTS (text-to-speech) system
            new_messages = result.get("messages", [])

            logger.debug(f"   📦 Found {len(new_messages)} messages in result")

            # Find the last AI message with content
            ai_response = ""
            last_ai_with_tool_calls = None
            last_ai_with_tool_calls_index = -1

            for i, msg in enumerate(new_messages):
                msg_type = getattr(msg, "type", "unknown")
                msg_content = getattr(msg, "content", "")
                logger.debug(f"   [{i}] Type: {msg_type}, Content: {str(msg_content)[:50]}...")

                if msg_type == "ai":
                    # Check if this AI message has tool_calls
                    has_tool_calls = hasattr(msg, "tool_calls") and msg.tool_calls

                    if has_tool_calls:
                        # Store the last AI message with tool_calls (even if no content)
                        last_ai_with_tool_calls = msg
                        last_ai_with_tool_calls_index = i
                        logger.debug(f"   🔧 Found AI message with tool_calls at [{i}]")

                    if msg_content and msg_content.strip():
                        # Keep updating to get the LAST ai message with content
                        ai_response = msg_content
                        logger.debug(f"   ✅ Updated AI response from message [{i}]")

            # CRITICAL FIX: If the LAST AI message has tool_calls (indicating a transfer),
            # we should generate a response based on the tool_call, EVEN IF there are
            # previous AI messages with content. This prevents returning stale responses.
            is_placeholder = ai_response.strip() in ["...", ".", "--", "—", ""]
            has_recent_tool_call = last_ai_with_tool_calls is not None

            # Check if the last AI message with tool_calls is more recent than the last AI message with content
            # by checking if it's the last or second-to-last message (allowing for one HumanMessage after it)
            is_tool_call_recent = has_recent_tool_call and last_ai_with_tool_calls_index >= len(new_messages) - 2

            if has_recent_tool_call and (is_placeholder or is_tool_call_recent):
                logger.warning("   ⚠️  AI message has tool_calls but no content - generating appropriate response")

                # Get the first tool call
                tool_call = last_ai_with_tool_calls.tool_calls[0]
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})

                logger.debug(f"   🔧 Tool: {tool_name}, Args: {tool_args}")

                # Generate appropriate message based on tool
                if tool_name == "TransferToNavegante":
                    # The RECEPCIONISTA detected a taxi request
                    # Generate a friendly message asking for the address
                    ai_response = "¡Con gusto! ¿Desde dónde necesitas el taxi?"
                    logger.info(f"   ✅ Generated TransferToNavegante response: {ai_response}")
                elif tool_name == "TransferToOperador":
                    ai_response = "Perfecto. ¿Cómo vas a pagar el servicio?"
                    logger.info(f"   ✅ Generated TransferToOperador response: {ai_response}")
                elif tool_name == "TransferToConfirmador":
                    # Short confirmation - CONFIRMADOR will present the summary when user is ready
                    ai_response = "Perfecto."
                    logger.info(f"   ✅ Generated TransferToConfirmador response: {ai_response}")
                elif tool_name == "TransferToHuman":
                    # Generate appropriate transfer message based on reason
                    reason = tool_args.get("reason", "").lower()
                    if "coordenadas" in reason or "dirección" in reason or "gps" in reason:
                        ai_response = "He recibido todos tus datos. Un asesor te contactará en un momento para confirmar tu ubicación exacta y completar tu pedido. ¡Gracias por tu paciencia!"
                    elif "backend" in reason or "técnico" in reason:
                        ai_response = "Disculpa, tengo problemas técnicos en este momento. Un asesor te contactará enseguida para ayudarte con tu pedido."
                    elif "múltiples" in reason or "servicios" in reason:
                        ai_response = "Veo que tienes más de un servicio activo. Un asesor te contactará para ayudarte con esto."
                    else:
                        ai_response = "Un asesor te contactará en un momento para ayudarte. Gracias por tu comprensión."
                    logger.info(f"   ✅ Generated TransferToHuman response: {ai_response}")
                elif tool_name == "DispatchToBackend":
                    # Service confirmed and being dispatched - farewell message
                    ai_response = "¡Listo! Tu taxi está en camino. Llegará en aproximadamente 10 minutos. ¡Buen viaje!"
                    logger.info(f"   ✅ Generated DispatchToBackend response: {ai_response}")
                else:
                    # Fallback for other tools (BacktrackToNavegante, BacktrackToOperador, etc.)
                    ai_response = ""  # Empty - will be filled by next agent or fallback
                    logger.warning(f"   ⚠️  Unknown tool {tool_name}, no message generated")

            # If still no valid AI response found, use fallback
            if not ai_response or not ai_response.strip():
                ai_response = "Lo siento, ¿podrías repetir eso? No entendí bien tu mensaje."
                logger.warning("   ⚠️  No valid AI response found, using fallback message")

            logger.debug(f"   🎯 Final AI response: {ai_response[:100]}...")

            # ====== CHECK FOR HUMAN TRANSFER ======
            transfer_to_human = result.get("transfer_to_human", False)
            transfer_reason = result.get("transfer_reason")

            if transfer_to_human:
                logger.info(f"🙋 TRANSFERENCIA A HUMANO SOLICITADA: {transfer_reason}")

                # Use the message from the agent (which is already contextual)
                # Only use fallback if ai_response is empty
                if not ai_response or not ai_response.strip():
                    # Fallback message based on transfer_reason
                    if "coordenadas" in transfer_reason.lower() or "dirección" in transfer_reason.lower():
                        ai_response = "He recibido todos tus datos, pero necesito verificar tu dirección con un asesor. En un momento te contactará una persona para confirmar tu ubicación exacta."
                    elif "solicito hablar" in transfer_reason.lower() or "asesor" in transfer_reason.lower():
                        ai_response = "Por supuesto, te conecto con un asesor. Un momento por favor."
                    elif "backend" in transfer_reason.lower():
                        ai_response = "Disculpa, estoy teniendo problemas técnicos. Voy a conectarte con un asesor que te ayudará."
                    elif "multiples servicios" in transfer_reason.lower():
                        ai_response = "Veo que tienes más de un servicio activo. Voy a conectarte con un asesor que te ayudará con esto."
                    else:
                        ai_response = "Déjame conectarte con un asesor que podrá ayudarte mejor. Un momento por favor."

                    logger.info(f"   ✅ Usando mensaje de transferencia fallback: {ai_response[:50]}...")
                else:
                    logger.info(f"   ✅ Usando mensaje de transferencia del agente: {ai_response[:50]}...")

            # ====== CHECK FOR CONVERSATION END ======
            # Conversation ends when service has been dispatched (registered) OR transferred to human
            token_tracking = result.get("token_tracking", {})
            dispatch_executed = token_tracking.get("dispatch_executed", False)

            # End conversation if dispatch was executed OR transfer to human was requested
            fin = "true" if (dispatch_executed or transfer_to_human) else "false"

            if dispatch_executed:
                logger.info(f"✅ CONVERSACIÓN FINALIZADA - Servicio registrado")
            elif transfer_to_human:
                logger.info(f"✅ CONVERSACIÓN FINALIZADA - Transferido a humano")

            # ====== CHECK FOR SESSION END ======
            self._check_and_save_session_end(
                thread_id=thread_id,
                user_message=request.message,
                state=result
            )

            return ChatResponse(
                thread_id=thread_id,
                message=ai_response,
                transfer_to_human="true" if transfer_to_human else "false",
                fin=fin,
            )

        except Exception as e:
            # Handle errors gracefully
            logger.error(f"❌ ERROR IN INVOKE_CHAT: {str(e)}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Thread: {thread_id}")

            # Log full exception details for debugging
            import traceback
            logger.error(f"   Traceback:\n{traceback.format_exc()}")

            return ChatResponse(
                thread_id=thread_id,
                message=f"Lo siento, ocurrió un error: {str(e)}",
                transfer_to_human="false",
                fin="false",
            )

    async def continue_chat(self, request: ChatContinueRequest) -> ChatResponse:
        """
        Continue a conversation after an interrupt.

        Args:
            request: Continue request with thread_id and optional command

        Returns:
            ChatResponse with continued conversation
        """
        logger.info(f"▶️  CONTINUE CHAT - Thread: {request.thread_id}")

        config = {
            "configurable": {
                "thread_id": request.thread_id,
            }
        }

        try:
            logger.debug("   Continuing from interrupt...")
            # Continue from interrupt (None means "proceed with pending action")
            result = await self.graph.ainvoke(None, config)
            logger.debug(f"   ✓ Continue completed - {len(result.get('messages', []))} messages in result")

            # Check if still interrupted
            state = self.graph.get_state(config)
            is_interrupted = len(state.next) > 0

            interrupt_info = None
            if is_interrupted:
                next_node = state.next[0] if state.next else None

                # Find the last AIMessage with tool_calls (search backwards)
                messages = state.values.get("messages", [])
                ai_message_with_tools = None
                for msg in reversed(messages):
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        ai_message_with_tools = msg
                        break

                if ai_message_with_tools and ai_message_with_tools.tool_calls:
                    tool_call = ai_message_with_tools.tool_calls[0]
                    interrupt_info = {
                        "node": next_node,
                        "tool": tool_call.get("name"),
                        "args": tool_call.get("args"),
                        "message": f"Do you want to proceed with {tool_call.get('name')}?"
                    }

            # Extract only the LAST AI message content
            # This is sent directly to TTS (text-to-speech) system
            new_messages = result.get("messages", [])

            # Find the last AI message with content
            ai_response = ""
            last_ai_with_tool_calls = None
            last_ai_with_tool_calls_index = -1

            for i, msg in enumerate(new_messages):
                msg_type = getattr(msg, "type", "unknown")
                msg_content = getattr(msg, "content", "")

                if msg_type == "ai":
                    # Check if this AI message has tool_calls
                    has_tool_calls = hasattr(msg, "tool_calls") and msg.tool_calls

                    if has_tool_calls:
                        # Store the last AI message with tool_calls (even if no content)
                        last_ai_with_tool_calls = msg
                        last_ai_with_tool_calls_index = i

                    if msg_content and msg_content.strip():
                        # Keep updating to get the LAST ai message with content
                        ai_response = msg_content

            # CRITICAL FIX: If the LAST AI message has tool_calls (indicating a transfer),
            # we should generate a response based on the tool_call, EVEN IF there are
            # previous AI messages with content. This prevents returning stale responses.
            is_placeholder = ai_response.strip() in ["...", ".", "--", "—", ""]
            has_recent_tool_call = last_ai_with_tool_calls is not None

            # Check if the last AI message with tool_calls is more recent than the last AI message with content
            # by checking if it's the last or second-to-last message (allowing for one HumanMessage after it)
            is_tool_call_recent = has_recent_tool_call and last_ai_with_tool_calls_index >= len(new_messages) - 2

            if has_recent_tool_call and (is_placeholder or is_tool_call_recent):
                logger.warning("   ⚠️  AI message has tool_calls but no content - generating appropriate response")

                # Get the first tool call
                tool_call = last_ai_with_tool_calls.tool_calls[0]
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})

                logger.debug(f"   🔧 Tool: {tool_name}, Args: {tool_args}")

                # Generate appropriate message based on tool
                if tool_name == "TransferToNavegante":
                    ai_response = "¡Con gusto! ¿Desde dónde necesitas el taxi?"
                    logger.info(f"   ✅ Generated TransferToNavegante response: {ai_response}")
                elif tool_name == "TransferToOperador":
                    ai_response = "Perfecto. ¿Cómo vas a pagar el servicio?"
                    logger.info(f"   ✅ Generated TransferToOperador response: {ai_response}")
                elif tool_name == "TransferToConfirmador":
                    ai_response = "Entendido. Déjame confirmar los detalles del servicio..."
                    logger.info(f"   ✅ Generated TransferToConfirmador response: {ai_response}")
                else:
                    ai_response = "Entendido, un momento por favor..."
                    logger.warning(f"   ⚠️  Unknown tool {tool_name}, using generic response")

            # If still no valid AI response found, use fallback
            if not ai_response or not ai_response.strip():
                ai_response = "Lo siento, ¿podrías repetir eso? No entendí bien tu mensaje."
                logger.warning("   ⚠️  No valid AI response found, using fallback message")

            logger.debug(f"   Returning AI response: {ai_response[:100]}...")

            # Check for human transfer in continue_chat as well
            transfer_to_human = result.get("transfer_to_human", False)
            transfer_reason = result.get("transfer_reason")

            if transfer_to_human:
                logger.info(f"🙋 TRANSFERENCIA A HUMANO SOLICITADA: {transfer_reason}")

                # Use the message from the agent (which is already contextual)
                # Only use fallback if ai_response is empty
                if not ai_response or not ai_response.strip():
                    # Fallback message based on transfer_reason
                    if "coordenadas" in transfer_reason.lower() or "dirección" in transfer_reason.lower():
                        ai_response = "He recibido todos tus datos, pero necesito verificar tu dirección con un asesor. En un momento te contactará una persona para confirmar tu ubicación exacta."
                    elif "solicito hablar" in transfer_reason.lower() or "asesor" in transfer_reason.lower():
                        ai_response = "Por supuesto, te conecto con un asesor. Un momento por favor."
                    elif "backend" in transfer_reason.lower():
                        ai_response = "Disculpa, estoy teniendo problemas técnicos. Voy a conectarte con un asesor que te ayudará."
                    elif "multiples servicios" in transfer_reason.lower():
                        ai_response = "Veo que tienes más de un servicio activo. Voy a conectarte con un asesor que te ayudará con esto."
                    else:
                        ai_response = "Déjame conectarte con un asesor que podrá ayudarte mejor. Un momento por favor."

                    logger.info(f"   ✅ Usando mensaje de transferencia fallback: {ai_response[:50]}...")
                else:
                    logger.info(f"   ✅ Usando mensaje de transferencia del agente: {ai_response[:50]}...")

            # Check for conversation end
            token_tracking = result.get("token_tracking", {})
            dispatch_executed = token_tracking.get("dispatch_executed", False)
            fin = "true" if dispatch_executed else "false"

            if dispatch_executed:
                logger.info(f"✅ CONVERSACIÓN FINALIZADA - Servicio registrado")

            return ChatResponse(
                thread_id=request.thread_id,
                message=ai_response,
                transfer_to_human="true" if transfer_to_human else "false",
                fin=fin,
            )

        except Exception as e:
            logger.error(f"❌ ERROR IN CONTINUE_CHAT: {str(e)}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Thread: {request.thread_id}")

            # Log full exception details for debugging
            import traceback
            logger.error(f"   Traceback:\n{traceback.format_exc()}")

            return ChatResponse(
                thread_id=request.thread_id,
                message=f"Error al continuar la conversación: {str(e)}",
                transfer_to_human="false",
                fin="false",
            )

    def _check_and_save_session_end(
        self,
        thread_id: str,
        user_message: str,
        state: dict
    ):
        """
        Check if session has ended and save token tracking to file.

        Session ends when:
        1. DispatchToBackend was executed (service confirmed)
        2. User sends farewell message (goodbye)

        Args:
            thread_id: Conversation thread identifier
            user_message: Latest user message
            state: Current conversation state
        """
        from app.services.token_tracker import TokenTracker
        import time

        tracking = state.get("token_tracking")
        if not tracking:
            logger.debug("No token tracking data - skipping")
            return

        # Prevent duplicate saves
        if tracking.get("tracking_saved", False):
            logger.debug("Token tracking already saved - skipping")
            return

        # Check end criteria
        dispatch_executed = tracking.get("dispatch_executed", False)
        is_farewell = TokenTracker.is_farewell_message(user_message)

        logger.debug(
            f"Session end check - "
            f"dispatch={dispatch_executed}, farewell={is_farewell}"
        )

        if dispatch_executed and is_farewell:
            # Calculate duration
            start_time = tracking.get("start_time")
            if start_time:
                duration = time.time() - start_time
            else:
                duration = 0.0

            # Get client_id
            client_id = state.get("client_id", "unknown")

            # Save to file
            TokenTracker.write_session_to_file(
                client_id=client_id,
                duration=duration,
                input_tokens=tracking.get("total_input_tokens", 0),
                output_tokens=tracking.get("total_output_tokens", 0)
            )

            # Mark as saved to prevent duplicates
            tracking["tracking_saved"] = True

            logger.info(
                f"✅ Session completed - "
                f"Client: {client_id}, "
                f"Duration: {duration:.2f}s, "
                f"Tokens: {tracking['total_input_tokens']}+{tracking['total_output_tokens']}"
            )

    def get_thread_state(self, thread_id: str):
        """
        Get the current state of a thread.

        Args:
            thread_id: Thread ID to get state for

        Returns:
            Current state of the thread
        """
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        try:
            state = self.graph.get_state(config)
            return {
                "thread_id": thread_id,
                "messages": state.values.get("messages", []),
                "dialog_state": state.values.get("dialog_state", []),
                "next": state.next,
            }
        except Exception as e:
            return {
                "error": str(e),
                "thread_id": thread_id,
            }
