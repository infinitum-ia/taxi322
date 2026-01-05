"""
Script de prueba para verificar la consulta automática de dirección previa.

Este script simula dos escenarios:
1. Cliente nuevo sin dirección previa
2. Cliente recurrente con dirección previa

Uso:
    uv run python test_address_lookup.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.models.api import ChatRequest
from app.services.graph_service import GraphService


async def test_new_customer():
    """Prueba con cliente nuevo sin dirección previa."""
    print("\n" + "="*80)
    print("TEST 1: CLIENTE NUEVO (sin dirección previa)")
    print("="*80 + "\n")

    # Usar un client_id que probablemente no existe en la base de datos
    graph_service = GraphService()

    request = ChatRequest(
        message="Necesito un taxi",
        user_id="9999999999",  # Cliente que no existe
        client_id="9999999999"
    )

    print(f"📤 Usuario: {request.message}")
    print(f"📞 Client ID: {request.client_id}\n")

    response = graph_service.invoke_chat(request)

    print(f"🤖 Alice: {response.message}\n")
    print(f"Thread ID: {response.thread_id}")
    print(f"Interrupted: {response.is_interrupted}")

    # Verificación esperada
    print("\n✅ RESULTADO ESPERADO:")
    print("   Alice debería preguntar: '¡Con gusto! ¿Desde dónde necesitas el taxi?'")
    print("   (Sin mencionar dirección previa porque el cliente es nuevo)")

    return response


async def test_returning_customer():
    """Prueba con cliente recurrente que tiene dirección previa."""
    print("\n" + "="*80)
    print("TEST 2: CLIENTE RECURRENTE (con dirección previa)")
    print("="*80 + "\n")

    # Usar un client_id que probablemente existe en la base de datos
    # NOTA: Reemplaza este número con un client_id real de tu base de datos
    graph_service = GraphService()

    request = ChatRequest(
        message="Necesito un taxi",
        user_id="3022370040",  # Cliente que existe (ajustar según tu BD)
        client_id="3022370040"
    )

    print(f"📤 Usuario: {request.message}")
    print(f"📞 Client ID: {request.client_id}\n")

    response = graph_service.invoke_chat(request)

    print(f"🤖 Alice: {response.message}\n")
    print(f"Thread ID: {response.thread_id}")
    print(f"Interrupted: {response.is_interrupted}")

    # Verificación esperada
    print("\n✅ RESULTADO ESPERADO:")
    print("   Alice debería preguntar: '¡Hola! Veo que ya has usado nuestro servicio antes.'")
    print("   '¿Quieres que te recojamos en [dirección registrada]?'")

    return response


async def test_conversation_flow():
    """Prueba el flujo completo de conversación."""
    print("\n" + "="*80)
    print("TEST 3: FLUJO COMPLETO DE CONVERSACIÓN")
    print("="*80 + "\n")

    graph_service = GraphService()

    # Primera interacción
    print("--- Turno 1: Usuario solicita taxi ---")
    request1 = ChatRequest(
        message="Hola, necesito un taxi",
        user_id="test_user_123",
        client_id="test_user_123"
    )

    print(f"📤 Usuario: {request1.message}")
    response1 = graph_service.invoke_chat(request1)
    print(f"🤖 Alice: {response1.message}\n")

    # Segunda interacción (continuando la conversación)
    print("--- Turno 2: Usuario da una dirección ---")
    request2 = ChatRequest(
        message="Calle 72 número 43-25, El Prado",
        user_id="test_user_123",
        client_id="test_user_123",
        thread_id=response1.thread_id  # Continuar la misma conversación
    )

    print(f"📤 Usuario: {request2.message}")
    response2 = graph_service.invoke_chat(request2)
    print(f"🤖 Alice: {response2.message}\n")

    print(f"Thread ID: {response2.thread_id}")

    print("\n✅ RESULTADO ESPERADO:")
    print("   Turno 1: Alice pregunta por la dirección")
    print("   Turno 2: Alice repite la dirección y pide confirmación")


async def main():
    """Ejecuta todas las pruebas."""
    print("\n🚀 INICIANDO PRUEBAS DE CONSULTA DE DIRECCIÓN PREVIA\n")

    try:
        # Test 1: Cliente nuevo
        await test_new_customer()

        # Esperar un poco entre tests
        await asyncio.sleep(2)

        # Test 2: Cliente recurrente
        # IMPORTANTE: Ajusta el client_id con uno real de tu base de datos
        print("\n⚠️  NOTA: Para el Test 2, asegúrate de usar un client_id real")
        print("   que exista en tu base de datos con servicios previos.\n")

        await test_returning_customer()

        # Esperar un poco entre tests
        await asyncio.sleep(2)

        # Test 3: Flujo completo
        await test_conversation_flow()

        print("\n" + "="*80)
        print("✅ TODAS LAS PRUEBAS COMPLETADAS")
        print("="*80 + "\n")

        print("📊 INSTRUCCIONES PARA VERIFICAR:")
        print("   1. Revisa que el Test 1 NO mencione direcciones previas")
        print("   2. Revisa que el Test 2 SÍ mencione la dirección previa del cliente")
        print("   3. Revisa que el flujo completo funcione correctamente")
        print("   4. Revisa los logs en app.log para ver la consulta de dirección\n")

    except Exception as e:
        print(f"\n❌ ERROR EN LAS PRUEBAS: {str(e)}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
