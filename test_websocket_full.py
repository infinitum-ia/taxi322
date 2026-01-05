"""
Test completo del flujo de booking con WebSocket.
Envía múltiples mensajes para probar el flujo completo.
"""

import asyncio
import websockets
import json


async def test_full_flow():
    """Test del flujo completo de booking."""
    uri = "ws://localhost:8000/api/v1/ws/chat"

    print("=" * 70)
    print("Test Completo de Flujo de Booking - WebSocket Streaming")
    print("=" * 70)
    print()

    messages = [
        "Necesito un taxi a la Calle 72 #43-25, El Prado",
        "En efectivo",
        "Si, confirmo"
    ]

    try:
        async with websockets.connect(uri) as websocket:
            print("[OK] Conectado al WebSocket\n")

            # Recibir mensaje de bienvenida
            await websocket.recv()

            thread_id = "test-full-flow"

            for idx, user_message in enumerate(messages, 1):
                print(f"\n{'='*70}")
                print(f"MENSAJE #{idx}: {user_message}")
                print('='*70)

                # Enviar mensaje
                await websocket.send(json.dumps({
                    "type": "user_input",
                    "text": user_message,
                    "thread_id": thread_id
                }))

                # Recibir respuesta completa
                assistant_response = ""
                tools_called = []

                while True:
                    try:
                        response = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=10.0
                        )

                        event = json.loads(response)
                        event_type = event.get("type")

                        if event_type == "agent_chunk":
                            text = event.get("text", "")
                            assistant_response += text
                            print(text, end='', flush=True)

                        elif event_type == "tool_call":
                            name = event.get("name", "")
                            tools_called.append(name)
                            print(f"\n[Tool] {name}")

                        elif event_type == "agent_end":
                            print()
                            break

                        elif event_type == "agent_error":
                            error = event.get("error", "")
                            print(f"\n[ERROR] {error}")
                            return

                    except asyncio.TimeoutError:
                        print("\n[Timeout] Sin mas eventos")
                        break

                print(f"\nHerramientas llamadas: {tools_called if tools_called else 'Ninguna'}")

            print("\n" + "=" * 70)
            print("[OK] Flujo completo probado exitosamente!")
            print("=" * 70)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_full_flow())
