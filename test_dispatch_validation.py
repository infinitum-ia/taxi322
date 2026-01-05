"""
Test de validación del registro de servicio en backend
Cliente: 3042124567
"""

import asyncio
import httpx
import time


async def test_service_registration():
    """Simula una conversación completa y valida que el servicio se registre."""

    base_url = "http://localhost:8000"
    client_id = "3042124567"

    print("=" * 80)
    print("PRUEBA DE REGISTRO DE SERVICIO EN BACKEND")
    print(f"Cliente ID: {client_id}")
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

        await asyncio.sleep(1.5)

        # Mensaje 2: Usuario da dirección
        print("\n[USUARIO] Desde la Calle 72 número 43 guion 25 en El Prado")

        response2 = await client.post(
            f"{base_url}/api/v1/chat/",
            json={
                "message": "Desde la Calle 72 número 43 guion 25 en El Prado",
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

        await asyncio.sleep(1.5)

        # Mensaje 3: Confirmar dirección
        print("\n[USUARIO] Sí, esa dirección está bien")

        response3 = await client.post(
            f"{base_url}/api/v1/chat/",
            json={
                "message": "Sí, esa dirección está bien",
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

        await asyncio.sleep(1.5)

        # Mensaje 4: Método de pago
        print("\n[USUARIO] Voy a pagar en efectivo")

        response4 = await client.post(
            f"{base_url}/api/v1/chat/",
            json={
                "message": "Voy a pagar en efectivo",
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

        await asyncio.sleep(1.5)

        # Mensaje 5: Necesidades especiales (si pregunta)
        print("\n[USUARIO] No, todo bien así")

        response5 = await client.post(
            f"{base_url}/api/v1/chat/",
            json={
                "message": "No, todo bien así",
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

        await asyncio.sleep(1.5)

        # Mensaje 6: CONFIRMACIÓN FINAL
        print("\n[USUARIO] Sí, confirmo todo")

        response6 = await client.post(
            f"{base_url}/api/v1/chat/",
            json={
                "message": "Sí, confirmo todo",
                "user_id": f"test_{client_id}",
                "client_id": client_id,
                "thread_id": thread_id
            }
        )

        if response6.status_code == 200:
            data6 = response6.json()
            print(f"[ALICE] {data6['message']}")

            print("\n" + "=" * 80)
            print("[OK] CONVERSACION COMPLETADA")
            print("=" * 80)

            print("\n[INFO] VERIFICA LOS LOGS DEL SERVIDOR")
            print("Deberias ver:")
            print("  [OK] SERVICIO REGISTRADO EXITOSAMENTE EN EL BACKEND")
            print("  [ID] ID de servicio: [ID del backend]")
            print("  [DIR] Direccion: Calle 72 #43-25, El Prado")
            print("  [CAR] Tipo vehiculo: [tipo detectado]")
            print("=" * 80)

        else:
            print(f"[ERROR] {response6.status_code}: {response6.text}")
            return


if __name__ == "__main__":
    print("\nIniciando test de registro de servicio...")
    print("Asegurate de que el servidor este corriendo en http://localhost:8000\n")

    asyncio.run(test_service_registration())
