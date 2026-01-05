"""
Sistema de eventos para arquitectura sandwich de voice agents.

Este módulo define todos los tipos de eventos que fluyen a través del pipeline:
- STT (Speech-to-Text): Eventos de transcripción
- Agent: Eventos del agente LangGraph
- TTS (Text-to-Speech): Eventos de síntesis de voz

Cada evento tiene un timestamp y tipo específico para facilitar el debugging.
"""

from typing import Literal, Union, Any
from pydantic import BaseModel, Field
from datetime import datetime
import base64


class BaseEvent(BaseModel):
    """Evento base con timestamp automático"""
    type: str
    ts: int = Field(description="Unix timestamp en milisegundos")

    @classmethod
    def create(cls, **kwargs):
        """Factory method que agrega timestamp automáticamente"""
        return cls(ts=int(datetime.now().timestamp() * 1000), **kwargs)


# ============================================================================
# STT Events (Speech-to-Text)
# ============================================================================

class STTChunkEvent(BaseEvent):
    """Transcripción parcial del usuario (para mostrar feedback en tiempo real)"""
    type: Literal["stt_chunk"] = "stt_chunk"
    text: str = Field(description="Texto transcrito parcialmente")


class STTOutputEvent(BaseEvent):
    """Transcripción final del usuario (trigger para procesar con el agente)"""
    type: Literal["stt_output"] = "stt_output"
    text: str = Field(description="Texto transcrito completo")


STTEvent = Union[STTChunkEvent, STTOutputEvent]


# ============================================================================
# Agent Events (LangGraph)
# ============================================================================

class AgentChunkEvent(BaseEvent):
    """Token individual de la respuesta del agente (streaming)"""
    type: Literal["agent_chunk"] = "agent_chunk"
    text: str = Field(description="Fragmento de texto generado")
    agent: str = Field(default="", description="Agente actual (RECEPCIONISTA, NAVEGANTE, etc.)")


class AgentEndEvent(BaseEvent):
    """Señal de que el agente terminó de generar la respuesta"""
    type: Literal["agent_end"] = "agent_end"
    agent: str = Field(description="Agente que finalizó")


class ToolCallEvent(BaseEvent):
    """Llamada a una herramienta (ej: TransferToNavegante, validate_zone)"""
    type: Literal["tool_call"] = "tool_call"
    tool_call_id: str = Field(description="ID único de la llamada")
    name: str = Field(description="Nombre de la herramienta")
    args: dict = Field(description="Argumentos de la herramienta")


class ToolResultEvent(BaseEvent):
    """Resultado de la ejecución de una herramienta"""
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str = Field(description="ID de la llamada asociada")
    result: Any = Field(description="Resultado de la ejecución")


class AgentErrorEvent(BaseEvent):
    """Error durante el procesamiento del agente"""
    type: Literal["agent_error"] = "agent_error"
    error: str = Field(description="Mensaje de error")


AgentEvent = Union[
    AgentChunkEvent,
    AgentEndEvent,
    ToolCallEvent,
    ToolResultEvent,
    AgentErrorEvent
]


# ============================================================================
# TTS Events (Text-to-Speech)
# ============================================================================

class TTSChunkEvent(BaseEvent):
    """Chunk de audio sintetizado (base64 encoded)"""
    type: Literal["tts_chunk"] = "tts_chunk"
    audio: str = Field(description="Audio PCM en base64")
    sample_rate: int = Field(default=24000, description="Sample rate del audio")


class TTSEndEvent(BaseEvent):
    """Señal de que la síntesis de voz terminó"""
    type: Literal["tts_end"] = "tts_end"


TTSEvent = Union[TTSChunkEvent, TTSEndEvent]


# ============================================================================
# Union Type y Utilidades
# ============================================================================

VoiceAgentEvent = Union[STTEvent, AgentEvent, TTSEvent]


def event_to_dict(event: VoiceAgentEvent) -> dict:
    """
    Convierte un evento a diccionario JSON-serializable.

    Maneja casos especiales:
    - Convierte camelCase para compatibilidad con frontend
    - Excluye datos binarios cuando es apropiado
    """
    data = event.model_dump()

    # Convertir tool_call_id a camelCase para frontend JavaScript
    if "tool_call_id" in data:
        data["toolCallId"] = data.pop("tool_call_id")

    return data


# ============================================================================
# Eventos de Control (para simulación en Fase 1)
# ============================================================================

class UserInputEvent(BaseEvent):
    """
    Entrada de texto del usuario (simulando transcripción en Fase 1).
    En Fase 2+ contendrá audio bytes.
    """
    type: Literal["user_input"] = "user_input"
    text: str = Field(description="Texto del usuario")


class SystemMessageEvent(BaseEvent):
    """Mensajes del sistema (logs, estado, debugging)"""
    type: Literal["system_message"] = "system_message"
    message: str = Field(description="Mensaje del sistema")
    level: Literal["info", "warning", "error"] = Field(default="info")


# Agregar a union type
VoiceAgentEvent = Union[
    STTEvent,
    AgentEvent,
    TTSEvent,
    UserInputEvent,
    SystemMessageEvent
]
