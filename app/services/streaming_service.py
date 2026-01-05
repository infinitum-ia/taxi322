"""
Servicio de streaming para arquitectura sandwich.

Implementa el pipeline de 3 etapas:
1. STT (Speech-to-Text) - En Fase 1 simula transcripción desde texto
2. Agent (LangGraph) - Procesa con los 4 agentes existentes
3. TTS (Text-to-Speech) - En Fase 1 simula síntesis (passthrough)

Cada etapa es un generador asíncrono que:
- Consume eventos de la etapa anterior
- Genera sus propios eventos
- Pasa eventos upstream (passthrough pattern)
"""

from typing import AsyncIterator, Optional, Any
import asyncio
import logging
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.models.events import (
    VoiceAgentEvent,
    STTChunkEvent,
    STTOutputEvent,
    AgentChunkEvent,
    AgentEndEvent,
    ToolCallEvent,
    ToolResultEvent,
    AgentErrorEvent,
    TTSChunkEvent,
    TTSEndEvent,
    SystemMessageEvent,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Etapa 1: STT Stream (Speech-to-Text)
# ============================================================================

async def stt_stream(
    text_input: str,
) -> AsyncIterator[VoiceAgentEvent]:
    """
    Simula transcripción de voz a texto (Fase 1).

    En producción (Fase 2+), esto:
    - Recibiría chunks de audio del WebSocket
    - Los enviaría a AssemblyAI/Deepgram
    - Emitiría transcripciones parciales y finales

    En Fase 1:
    - Acepta texto directamente
    - Simula transcripción parcial (opcional, para demo)
    - Emite transcripción final
    """
    logger.info(f"STT: Procesando entrada de texto: {text_input[:50]}...")

    # Opcional: simular transcripción progresiva palabra por palabra
    # Esto da feedback visual en el cliente
    words = text_input.split()
    partial = ""

    for i, word in enumerate(words):
        partial += word + " "
        # Emitir chunks parciales cada 2-3 palabras
        if (i + 1) % 3 == 0 or i == len(words) - 1:
            yield STTChunkEvent.create(text=partial.strip())
            await asyncio.sleep(0.05)  # Simular latencia de red

    # Emitir transcripción final
    yield STTOutputEvent.create(text=text_input)
    logger.info("STT: Transcripción final emitida")


# ============================================================================
# Etapa 2: Agent Stream (LangGraph)
# ============================================================================

async def agent_stream(
    transcript: str,
    thread_id: str,
    user_id: str,
    client_id: str,
    graph: Any,
) -> AsyncIterator[VoiceAgentEvent]:
    """
    Procesa el mensaje con el graph de LangGraph en modo streaming.

    Esta es la integración clave con tu sistema existente:
    - Usa los 4 agentes existentes (RECEPCIONISTA, NAVEGANTE, OPERADOR, CONFIRMADOR)
    - Streaming token-por-token mediante stream_mode="messages"
    - Emite eventos de chunks, herramientas, y finalización

    Args:
        transcript: Texto transcrito del usuario
        thread_id: ID del thread para persistencia
        user_id: ID del usuario del sistema (para config de LangGraph)
        client_id: ID del cliente (número de teléfono)
        graph: Graph compilado de LangGraph

    Yields:
        AgentChunkEvent: Tokens de la respuesta
        ToolCallEvent: Llamadas a herramientas
        ToolResultEvent: Resultados de herramientas
        AgentEndEvent: Señal de finalización
        AgentErrorEvent: Errores durante procesamiento
    """
    logger.info(f"Agent: Procesando mensaje en thread {thread_id}, user_id: {user_id}, client_id: {client_id}")

    try:
        # Config with thread_id and user_id (like REST API does)
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
            },
        }

        # Include client_id in input_state (like REST API does)
        input_state = {
            "messages": [HumanMessage(content=transcript)],
            "client_id": client_id,
        }

        # Buffer para acumular el contenido completo del mensaje actual
        current_message_content = ""
        current_agent = None

        # CLAVE: stream_mode="messages" emite cada mensaje conforme se genera
        # Esto permite streaming token-por-token
        async for chunk in graph.astream(
            input_state,
            config=config,
            stream_mode="messages",
        ):
            # chunk es una tupla: (message, metadata)
            if isinstance(chunk, tuple) and len(chunk) == 2:
                message, metadata = chunk
            else:
                # Formato alternativo dependiendo de la versión de LangGraph
                message = chunk
                metadata = {}

            # Determinar agente actual desde metadata o estado
            if metadata and "langgraph_node" in metadata:
                current_agent = metadata["langgraph_node"]

            # Procesar AIMessage (respuestas del agente)
            if isinstance(message, AIMessage):
                # Contenido de texto
                if message.content:
                    # Emitir chunk por chunk
                    # En modo streaming, content puede venir completo o incremental
                    # dependiendo de la implementación del LLM
                    new_content = message.content

                    # Si es contenido nuevo (incremental)
                    if new_content != current_message_content:
                        # Calcular delta
                        if new_content.startswith(current_message_content):
                            delta = new_content[len(current_message_content):]
                        else:
                            delta = new_content

                        current_message_content = new_content

                        # Emitir chunk
                        if delta:
                            yield AgentChunkEvent.create(
                                text=delta,
                                agent=current_agent or "unknown"
                            )

                # Tool calls
                if hasattr(message, "tool_calls") and message.tool_calls:
                    for tool_call in message.tool_calls:
                        # Asegurar que tool_call_id siempre sea string (nunca None)
                        tool_call_id = tool_call.get("id") or ""
                        name = tool_call.get("name") or ""
                        args = tool_call.get("args") or {}

                        yield ToolCallEvent.create(
                            tool_call_id=tool_call_id,
                            name=name,
                            args=args,
                        )

            # Procesar ToolMessage (resultados de herramientas)
            elif isinstance(message, ToolMessage):
                # Asegurar que tool_call_id siempre sea string
                tool_call_id = message.tool_call_id or ""
                result = message.content or ""

                yield ToolResultEvent.create(
                    tool_call_id=tool_call_id,
                    result=result,
                )

        # Emitir señal de finalización
        yield AgentEndEvent.create(agent=current_agent or "unknown")
        logger.info("Agent: Procesamiento completado")

    except Exception as e:
        logger.error(f"Agent: Error durante procesamiento: {e}", exc_info=True)
        yield AgentErrorEvent.create(error=str(e))


# ============================================================================
# Etapa 3: TTS Stream (Text-to-Speech)
# ============================================================================

async def tts_stream(
    agent_events: AsyncIterator[VoiceAgentEvent],
) -> AsyncIterator[VoiceAgentEvent]:
    """
    Convierte texto a voz y pasa eventos upstream (Fase 1: passthrough).

    En producción (Fase 2+), esto:
    - Bufferizaría chunks de texto del agente
    - Los enviaría a Cartesia/ElevenLabs
    - Emitiría chunks de audio sintetizado

    En Fase 1:
    - Solo pasa los eventos del agente sin modificar (passthrough)
    - Opcionalmente emite eventos TTS simulados para testing

    Args:
        agent_events: Stream de eventos del agente

    Yields:
        Todos los eventos upstream (passthrough)
        TTSChunkEvent: Chunks de audio (simulados en Fase 1)
        TTSEndEvent: Señal de finalización
    """
    logger.info("TTS: Iniciando stream (modo passthrough Fase 1)")

    # Buffer para acumular texto antes de "sintetizar"
    text_buffer = ""
    has_content = False

    async for event in agent_events:
        # Passthrough: pasar evento upstream
        yield event

        # Acumular texto de chunks del agente
        if isinstance(event, AgentChunkEvent):
            text_buffer += event.text
            has_content = True

            # En producción, aquí se enviaría a Cartesia cuando:
            # - Buffer alcanza cierta longitud
            # - Se detecta fin de frase (. ? !)
            # - Se detecta pausa natural

        # Cuando el agente termina, emitir señal TTS end
        elif isinstance(event, AgentEndEvent):
            if has_content:
                # En Fase 1, solo logging
                logger.info(f"TTS: Texto acumulado ({len(text_buffer)} chars)")

                # Opcional: simular chunk de audio
                # yield TTSChunkEvent.create(
                #     audio="",  # Base64 vacío en Fase 1
                #     sample_rate=24000
                # )

                yield TTSEndEvent.create()
                has_content = False
                text_buffer = ""

    logger.info("TTS: Stream finalizado")


# ============================================================================
# Pipeline Completo
# ============================================================================

async def voice_pipeline(
    text_input: str,
    thread_id: str,
    user_id: str,
    client_id: Optional[str] = None,
    graph: Any = None,
) -> AsyncIterator[VoiceAgentEvent]:
    """
    Pipeline completo de 3 etapas que conecta STT → Agent → TTS.

    Este es el punto de entrada principal para procesar una entrada del usuario
    en la arquitectura sandwich.

    Flujo:
    1. Texto → STT Stream → eventos de transcripción
    2. Transcripción final → Agent Stream → eventos de respuesta
    3. Eventos de respuesta → TTS Stream → eventos de audio (Fase 1: passthrough)

    Args:
        text_input: Texto del usuario (en Fase 1, directo; en Fase 2+, transcripción)
        thread_id: ID único del thread de conversación
        user_id: ID del usuario del sistema (operador, bot, etc.)
        client_id: ID del cliente (número de teléfono, opcional, default a user_id)
        graph: Graph compilado de LangGraph

    Yields:
        VoiceAgentEvent: Todos los eventos del pipeline
    """
    # Fallback client_id to user_id if not provided
    if client_id is None:
        client_id = user_id

    logger.info(f"Pipeline: Iniciando para thread {thread_id}, user_id: {user_id}, client_id: {client_id}")

    try:
        # Emitir mensaje del sistema
        yield SystemMessageEvent.create(
            message=f"Procesando mensaje en thread {thread_id}",
            level="info"
        )

        # Etapa 1: STT
        async for stt_event in stt_stream(text_input):
            yield stt_event

            # Cuando tenemos transcripción final, procesarla con el agente
            if isinstance(stt_event, STTOutputEvent):
                # Etapa 2: Agent
                agent_events = agent_stream(
                    transcript=stt_event.text,
                    thread_id=thread_id,
                    user_id=user_id,
                    client_id=client_id,
                    graph=graph
                )

                # Etapa 3: TTS (envuelve eventos del agente)
                async for final_event in tts_stream(agent_events):
                    yield final_event

        logger.info("Pipeline: Completado exitosamente")

    except Exception as e:
        logger.error(f"Pipeline: Error crítico: {e}", exc_info=True)
        yield AgentErrorEvent.create(error=f"Error en pipeline: {str(e)}")


# ============================================================================
# Utilidades
# ============================================================================

async def merge_async_iters(*iterators: AsyncIterator) -> AsyncIterator:
    """
    Merge múltiples async iterators en uno solo (útil para TTS en Fase 2+).

    Permite procesar eventos de múltiples fuentes concurrentemente.
    """
    queue = asyncio.Queue()

    async def consume(iterator):
        async for item in iterator:
            await queue.put(item)

    async def producer():
        tasks = [asyncio.create_task(consume(it)) for it in iterators]
        await asyncio.gather(*tasks)
        await queue.put(None)  # Sentinel

    asyncio.create_task(producer())

    while True:
        item = await queue.get()
        if item is None:
            break
        yield item
