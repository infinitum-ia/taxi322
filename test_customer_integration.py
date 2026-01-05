"""
Script de prueba para verificar la integración con la API de cliente.

Este script prueba:
1. Consulta de servicios previos del cliente
2. Flujo completo de solicitud de taxi con información previa
3. Cliente usando dirección anterior vs. dirección nueva
"""

import asyncio
import httpx
from app.tools.customer_tools import (
    obtener_direccion_cliente_completa,
    consultar_servicios_cliente_impl,
    consultar_cliente_impl
)


async def test_customer_lookup():
    """Prueba la consulta de información del cliente."""
    print("=" * 80)
    print("TEST 1: Consultar servicios previos del cliente")
    print("=" * 80)

    client_id = "3022370040"
    print(f"\n[PHONE] Consultando servicios para cliente: {client_id}")

    # Test consultar_servicios_cliente implementation
    result = await consultar_servicios_cliente_impl(client_id)

    print(f"\n[OK] Resultado de consulta:")
    print(f"   - Success: {result['success']}")
    print(f"   - Has previous service: {result['has_previous_service']}")
    print(f"   - Last address: {result['last_address']}")
    print(f"   - Message: {result['message']}")

    if result['data']:
        data = result['data']
        if isinstance(data, list):
            print(f"\n[LIST] Servicios encontrados: {len(data)}")
            if len(data) > 0:
                print(f"   Ultimo servicio: {data[0]}")
        elif isinstance(data, dict):
            print(f"\n[LIST] Datos del servicio: {data}")

    return result


async def test_direccion_completa():
    """Prueba la función completa que obtiene dirección de servicios O perfil."""
    print("\n" + "=" * 80)
    print("TEST 1B: Obtener dirección completa del cliente")
    print("=" * 80)

    client_id = "3022370040"
    print(f"\n[SEARCH] Buscando dirección del cliente: {client_id}")
    print("   (Consulta servicios previos Y perfil del cliente)")

    result = await obtener_direccion_cliente_completa(client_id)

    print(f"\n[OK] Resultado:")
    print(f"   - Success: {result['success']}")
    print(f"   - Has previous service: {result['has_previous_service']}")
    print(f"   - Last address: {result['last_address']}")
    print(f"   - Message: {result['message']}")

    if result['data']:
        print(f"\n[INFO] Datos adicionales disponibles")

    return result


async def test_customer_info():
    """Prueba la consulta de información general del cliente."""
    print("\n" + "=" * 80)
    print("TEST 2: Consultar información del cliente")
    print("=" * 80)

    client_id = "3022370040"
    print(f"\n[PHONE] Consultando información del cliente: {client_id}")

    result = await consultar_cliente_impl(client_id)

    print(f"\n[OK] Resultado:")
    print(f"   - Success: {result['success']}")
    print(f"   - Message: {result['message']}")

    if result['data']:
        print(f"   - Data: {result['data']}")

    return result


async def test_chat_api_with_customer():
    """Prueba el endpoint de chat con client_id."""
    print("\n" + "=" * 80)
    print("TEST 3: Prueba de Chat API con client_id")
    print("=" * 80)

    base_url = "http://localhost:8000"
    client_id = "3022370040"

    print(f"\n[ROCKET] Enviando mensaje al API con client_id: {client_id}")
    print(f"   URL: {base_url}/api/v1/chat/")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Primera solicitud - Usuario pide un taxi
        request_data = {
            "message": "Hola, necesito un taxi",
            "user_id": f"test_user_{client_id}",
            "client_id": client_id
        }

        print(f"\n[SEND] Request 1:")
        print(f"   Message: {request_data['message']}")
        print(f"   Client ID: {request_data['client_id']}")

        try:
            response = await client.post(
                f"{base_url}/api/v1/chat/",
                json=request_data
            )

            if response.status_code == 200:
                data = response.json()
                print(f"\n[OK] Response 1:")
                print(f"   Thread ID: {data['thread_id']}")
                print(f"   Message: {data['message']}")
                print(f"   Interrupted: {data['is_interrupted']}")

                thread_id = data['thread_id']

                # Segunda solicitud - Usuario responde sobre la dirección
                print("\n" + "-" * 80)
                print("[SEND] Request 2 - Usuario responde sobre dirección previa")

                request_data_2 = {
                    "message": "Sí, desde esa dirección",
                    "user_id": f"test_user_{client_id}",
                    "client_id": client_id,
                    "thread_id": thread_id
                }

                response_2 = await client.post(
                    f"{base_url}/api/v1/chat/",
                    json=request_data_2
                )

                if response_2.status_code == 200:
                    data_2 = response_2.json()
                    print(f"\n[OK] Response 2:")
                    print(f"   Message: {data_2['message']}")
                    print(f"   Interrupted: {data_2['is_interrupted']}")
                else:
                    print(f"\n[ERROR] Error en Request 2: {response_2.status_code}")
                    print(f"   {response_2.text}")

            else:
                print(f"\n[ERROR] Error: {response.status_code}")
                print(f"   {response.text}")

        except httpx.ConnectError:
            print(f"\n[ERROR] Error de conexión - ¿Está el servidor corriendo en {base_url}?")
            print("   Ejecuta: uv run uvicorn app.main:app --reload")
        except Exception as e:
            print(f"\n[ERROR] Error inesperado: {str(e)}")


async def main():
    """Ejecuta todas las pruebas."""
    print("\n" + "=" * 80)
    print("PRUEBAS DE INTEGRACION DE CLIENTE")
    print("=" * 80)

    # Test 1: Consultar servicios previos
    await test_customer_lookup()

    # Test 1B: Obtener dirección completa (PRINCIPAL)
    await test_direccion_completa()

    # Test 2: Consultar información del cliente
    await test_customer_info()

    # Test 3: Prueba completa con el API
    # Nota: Requiere que el servidor esté corriendo
    print("\n" + "=" * 80)
    print("[WARNING] NOTA: Test 3 requiere que el servidor esté corriendo")
    print("   Si quieres probarlo, asegúrate de ejecutar:")
    print("   uv run uvicorn app.main:app --reload")
    print("=" * 80)

    try:
        await test_chat_api_with_customer()
    except Exception as e:
        print(f"\n[WARNING] Test 3 omitido: {str(e)}")

    print("\n" + "=" * 80)
    print("[OK] PRUEBAS COMPLETADAS")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
