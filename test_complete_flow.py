"""
Test completo del flujo end-to-end con cliente 3022370040
"""

import asyncio
import httpx
import time


async def test_complete_conversation():
    """Simula una conversación completa con el cliente."""

    base_url = "http://localhost:8000"
    client_id = "3022370040"

    print("=" * 80)
    print("PRUEBA DE FLUJO COMPLETO - Cliente con Direccion Registrada")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=60.0) as client:

        # Mensaje 1: Usuario pide un taxi
        print("\n[USUARIO] Hola, necesito un taxi")

        response1 = await client.post(
            f"{base_url}/api/v1/chat/",
            json={
                "message": "Hola, necesito un taxi",
                "user_id": f"test_{client_id}",
                "client_id": client_id
            }
        )

        if response1.status_code == 200:
            data1 = response1.json()
            thread_id = data1["thread_id"]
            print(f"[ALICE] {data1['message']}")
            print(f"\n   (Thread ID: {thread_id})")
        else:
            print(f"[ERROR] {response1.status_code}: {response1.text}")
            return

        # Pequeña espera para simular conversación real
        await asyncio.sleep(1)

        # Mensaje 2: Usuario responde (darle tiempo al agente para consultar)
        print("\n[USUARIO] Si, desde mi direccion")

        response2 = await client.post(
            f"{base_url}/api/v1/chat/",
            json={
                "message": "Si, desde mi direccion",
                "user_id": f"test_{client_id}",
                "client_id": client_id,
                "thread_id": thread_id
            }
        )

        if response2.status_code == 200:
            data2 = response2.json()
            print(f"[ALICE] {data2['message']}")
        else:
            print(f"[ERROR] {response2.status_code}: {response2.text}")
            return

        await asyncio.sleep(1)

        # Mensaje 3: Continuar la conversación
        print("\n[USUARIO] Si, desde esa direccion esta bien")

        response3 = await client.post(
            f"{base_url}/api/v1/chat/",
            json={
                "message": "Si, desde esa direccion esta bien",
                "user_id": f"test_{client_id}",
                "client_id": client_id,
                "thread_id": thread_id
            }
        )

        if response3.status_code == 200:
            data3 = response3.json()
            print(f"[ALICE] {data3['message']}")
        else:
            print(f"[ERROR] {response3.status_code}: {response3.text}")
            return

        await asyncio.sleep(1)

        # Mensaje 4: Continuar con método de pago
        print("\n[USUARIO] En efectivo")

        response4 = await client.post(
            f"{base_url}/api/v1/chat/",
            json={
                "message": "En efectivo",
                "user_id": f"test_{client_id}",
                "client_id": client_id,
                "thread_id": thread_id
            }
        )

        if response4.status_code == 200:
            data4 = response4.json()
            print(f"[ALICE] {data4['message']}")
        else:
            print(f"[ERROR] {response4.status_code}: {response4.text}")
            return

        await asyncio.sleep(1)

        # Mensaje 5: Responder sobre necesidades especiales
        print("\n[USUARIO] No, nada mas")

        response5 = await client.post(
            f"{base_url}/api/v1/chat/",
            json={
                "message": "No, nada mas",
                "user_id": f"test_{client_id}",
                "client_id": client_id,
                "thread_id": thread_id
            }
        )

        if response5.status_code == 200:
            data5 = response5.json()
            print(f"[ALICE] {data5['message']}")
        else:
            print(f"[ERROR] {response5.status_code}: {response5.text}")
            return

        await asyncio.sleep(1)

        # Mensaje 6: Confirmar el servicio
        print("\n[USUARIO] Si, confirmo")

        response6 = await client.post(
            f"{base_url}/api/v1/chat/",
            json={
                "message": "Si, confirmo",
                "user_id": f"test_{client_id}",
                "client_id": client_id,
                "thread_id": thread_id
            }
        )

        if response6.status_code == 200:
            data6 = response6.json()
            print(f"[ALICE] {data6['message']}")
        else:
            print(f"[ERROR] {response6.status_code}: {response6.text}")
            return

        print("\n" + "=" * 80)
        print("[OK] CONVERSACION COMPLETA")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_complete_conversation())
