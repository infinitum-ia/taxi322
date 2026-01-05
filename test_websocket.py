"""
Script de prueba para WebSocket streaming.
Conecta al servidor, envía un mensaje y muestra los eventos recibidos.
"""

import asyncio
import websockets
import json
import sys


async def test_websocket():
    """Test WebSocket connection and streaming."""
    uri = "ws://localhost:8000/api/v1/ws/chat"

    print("Conectando al servidor WebSocket...")
    print(f"URI: {uri}\n")

    try:
        async with websockets.connect(uri) as websocket:
            print("[OK] Conectado exitosamente!\n")

            # Esperar mensaje de bienvenida
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            print(f"[Servidor] {welcome_data.get('message', '')}\n")

            # Enviar mensaje de prueba
            test_message = {
                "type": "user_input",
                "text": "Hola, necesito un taxi",
                "thread_id": "test-123"
            }

            print(f"Enviando mensaje: {test_message['text']}")
            print("-" * 60)
            await websocket.send(json.dumps(test_message))

            # Recibir y mostrar eventos
            event_count = 0
            assistant_message = ""

            while True:
                try:
                    # Timeout de 5 segundos para cada evento
                    response = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=5.0
                    )

                    event = json.loads(response)
                    event_count += 1
                    event_type = event.get("type", "unknown")

                    # Mostrar evento según tipo
                    if event_type == "stt_chunk":
                        print(f"[STT Chunk] {event.get('text', '')}")

                    elif event_type == "stt_output":
                        print(f"[STT Final] {event.get('text', '')}")
                        print()

                    elif event_type == "agent_chunk":
                        text = event.get('text', '')
                        agent = event.get('agent', '')
                        assistant_message += text
                        print(f"[{agent}] {text}", end='', flush=True)

                    elif event_type == "agent_end":
                        agent = event.get('agent', '')
                        print(f"\n[{agent}] Finalizado")
                        print()
                        # Si terminó el agente, salir después de 1 segundo
                        await asyncio.sleep(1)
                        break

                    elif event_type == "tool_call":
                        name = event.get('name', '')
                        print(f"\n[Tool Call] {name}")

                    elif event_type == "tool_result":
                        result = event.get('result', '')
                        print(f"[Tool Result] {result}")

                    elif event_type == "system_message":
                        level = event.get('level', 'info')
                        message = event.get('message', '')
                        if level == 'error':
                            print(f"[ERROR] {message}")
                        elif level == 'info':
                            print(f"[Info] {message}")

                    elif event_type == "agent_error":
                        error = event.get('error', '')
                        print(f"[ERROR] {error}")
                        break

                except asyncio.TimeoutError:
                    print("\n[Timeout] No se recibieron más eventos en 5 segundos")
                    break

            print("-" * 60)
            print(f"\nResumen:")
            print(f"  Eventos recibidos: {event_count}")
            print(f"  Mensaje del asistente: {assistant_message}")
            print("\n[OK] Prueba completada exitosamente!")

    except websockets.exceptions.WebSocketException as e:
        print(f"[ERROR] Error de WebSocket: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("Test de WebSocket Streaming - Taxi Voice Agent")
    print("=" * 60)
    print()

    asyncio.run(test_websocket())
