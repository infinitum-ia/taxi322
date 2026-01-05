"""
WebSocket endpoint for real-time streaming conversations.

Este endpoint implementa la arquitectura sandwich para voice agents:
- Acepta texto del usuario (Fase 1) o audio (Fase 2+)
- Procesa mediante pipeline de 3 etapas (STT → Agent → TTS)
- Emite eventos en tiempo real al cliente
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import uuid
import logging
import json
from typing import Dict, Set

from app.services.streaming_service import voice_pipeline
from app.models.events import event_to_dict, UserInputEvent, SystemMessageEvent
from app.services.graph_service import GraphService
from app.api.deps import get_graph_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


# Gestión de conexiones activas
class ConnectionManager:
    """Administra conexiones WebSocket activas"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, connection_id: str):
        """Acepta nueva conexión WebSocket"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        logger.info(f"WebSocket conectado: {connection_id}")

    def disconnect(self, connection_id: str):
        """Desconecta y limpia conexión"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info(f"WebSocket desconectado: {connection_id}")

    async def send_event(self, connection_id: str, event_dict: dict):
        """Envía evento a un cliente específico"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            await websocket.send_json(event_dict)


# Instancia global del manager
manager = ConnectionManager()


@router.websocket("/chat")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    graph_service: GraphService = Depends(get_graph_service)
):
    """
    WebSocket endpoint para conversaciones en streaming.

    Protocolo de comunicación:

    Cliente → Servidor (envía):
    {
        "type": "user_input",
        "text": "Hola, necesito un taxi",
        "thread_id": "uuid" (opcional, se crea si no existe),
        "client_id": "3022370040" (opcional, número de teléfono del cliente)
    }

    Servidor → Cliente (recibe múltiples eventos):
    {
        "type": "stt_chunk",
        "text": "Hola, necesito",
        "ts": 1234567890
    }
    {
        "type": "stt_output",
        "text": "Hola, necesito un taxi",
        "ts": 1234567891
    }
    {
        "type": "agent_chunk",
        "text": "Hola",
        "agent": "RECEPCIONISTA",
        "ts": 1234567892
    }
    {
        "type": "agent_chunk",
        "text": "! Claro",
        "agent": "RECEPCIONISTA",
        "ts": 1234567893
    }
    ...
    {
        "type": "agent_end",
        "agent": "RECEPCIONISTA",
        "ts": 1234567900
    }

    Args:
        websocket: Conexión WebSocket
        graph_service: Servicio del graph (inyectado)
    """
    # Generar ID único para esta conexión
    connection_id = str(uuid.uuid4())

    try:
        # Aceptar conexión
        await manager.connect(websocket, connection_id)

        # Enviar mensaje de bienvenida
        welcome_event = SystemMessageEvent.create(
            message="Conexión establecida. Envía un mensaje para comenzar.",
            level="info"
        )
        await manager.send_event(connection_id, event_to_dict(welcome_event))

        # Thread ID de la conversación (puede persistir a través de mensajes)
        thread_id = None

        # Loop principal: escuchar mensajes del cliente
        while True:
            # Recibir mensaje JSON del cliente
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError as e:
                error_event = SystemMessageEvent.create(
                    message=f"Error: JSON inválido - {str(e)}",
                    level="error"
                )
                await manager.send_event(connection_id, event_to_dict(error_event))
                continue

            # Validar estructura del mensaje
            if not isinstance(data, dict) or "type" not in data:
                error_event = SystemMessageEvent.create(
                    message="Error: Mensaje debe ser un objeto JSON con campo 'type'",
                    level="error"
                )
                await manager.send_event(connection_id, event_to_dict(error_event))
                continue

            # Procesar según tipo de mensaje
            message_type = data.get("type")

            if message_type == "user_input":
                # Extraer datos del mensaje
                text = data.get("text", "")
                thread_id = data.get("thread_id") or thread_id or str(uuid.uuid4())
                user_id = data.get("user_id", "websocket_user")  # Extract user_id with default
                client_id = data.get("client_id") or user_id  # Fallback to user_id if not provided

                if not text:
                    error_event = SystemMessageEvent.create(
                        message="Error: Campo 'text' es requerido",
                        level="error"
                    )
                    await manager.send_event(connection_id, event_to_dict(error_event))
                    continue

                logger.info(f"WebSocket [{connection_id}]: Procesando mensaje en thread {thread_id}, user_id: {user_id}, client_id: {client_id}")

                # Confirmar recepción
                ack_event = SystemMessageEvent.create(
                    message=f"Procesando mensaje en thread {thread_id}...",
                    level="info"
                )
                await manager.send_event(connection_id, event_to_dict(ack_event))

                try:
                    # Ejecutar pipeline de 3 etapas
                    async for event in voice_pipeline(
                        text_input=text,
                        thread_id=thread_id,
                        user_id=user_id,
                        client_id=client_id,
                        graph=graph_service.graph
                    ):
                        # Convertir evento a dict y enviar
                        event_dict = event_to_dict(event)
                        await manager.send_event(connection_id, event_dict)

                    # Enviar evento de finalización exitosa
                    complete_event = SystemMessageEvent.create(
                        message="Mensaje procesado exitosamente",
                        level="info"
                    )
                    await manager.send_event(connection_id, event_to_dict(complete_event))

                except Exception as e:
                    logger.error(f"WebSocket [{connection_id}]: Error en pipeline: {e}", exc_info=True)
                    error_event = SystemMessageEvent.create(
                        message=f"Error procesando mensaje: {str(e)}",
                        level="error"
                    )
                    await manager.send_event(connection_id, event_to_dict(error_event))

            elif message_type == "ping":
                # Responder a keepalive ping
                pong_event = SystemMessageEvent.create(
                    message="pong",
                    level="info"
                )
                await manager.send_event(connection_id, event_to_dict(pong_event))

            else:
                # Tipo de mensaje no reconocido
                error_event = SystemMessageEvent.create(
                    message=f"Tipo de mensaje no reconocido: {message_type}",
                    level="warning"
                )
                await manager.send_event(connection_id, event_to_dict(error_event))

    except WebSocketDisconnect:
        # Cliente se desconectó
        logger.info(f"WebSocket [{connection_id}]: Cliente desconectado")
        manager.disconnect(connection_id)

    except Exception as e:
        # Error inesperado
        logger.error(f"WebSocket [{connection_id}]: Error inesperado: {e}", exc_info=True)
        manager.disconnect(connection_id)
        # Intentar notificar al cliente antes de cerrar
        try:
            error_event = SystemMessageEvent.create(
                message=f"Error del servidor: {str(e)}",
                level="error"
            )
            await manager.send_event(connection_id, event_to_dict(error_event))
        except:
            pass  # Si falla, el cliente ya se desconectó


@router.get("/health")
async def websocket_health():
    """
    Health check para el servicio de WebSocket.

    Returns:
        Status del servicio y número de conexiones activas
    """
    return {
        "status": "healthy",
        "active_connections": len(manager.active_connections),
        "service": "websocket_streaming"
    }
