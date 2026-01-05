"""
Test completo del flujo conversacional de taxi.

Este script prueba todo el flujo desde el saludo inicial hasta la confirmación final.
MODIFICADO: Continúa el flujo completo incluso cuando hay fallos, reportando todos los errores al final.

Uso:
    python test_taxi_flow.py
"""

import requests
import json
import time
from typing import Optional, List, Tuple

# Configuración
BASE_URL = "http://localhost:8000"
USER_ID = "test_user_123"

# Lista para almacenar todos los resultados de los tests
test_results: List[Tuple[str, bool, str]] = []


def print_separator():
    """Imprime una línea separadora."""
    print("\n" + "=" * 80 + "\n")


def send_message(message: str, thread_id: Optional[str] = None) -> dict:
    """
    Envía un mensaje al API y retorna la respuesta.

    Args:
        message: Mensaje del usuario
        thread_id: ID del thread (opcional para el primer mensaje)

    Returns:
        Diccionario con la respuesta del API
    """
    url = f"{BASE_URL}/api/v1/chat/"

    payload = {
        "message": message,
        "user_id": USER_ID,
    }

    if thread_id:
        payload["thread_id"] = thread_id

    print(f"👤 USUARIO: {message}")

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        print(f"🤖 ALICE: {data.get('message', 'Sin respuesta')}")

        if data.get("is_interrupted"):
            print(f"⚠️  INTERRUPT: {data.get('interrupt_info')}")

        return data

    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"   Response: {e.response.text}")
        return {}


def record_test(step_name: str, passed: bool, details: str = ""):
    """
    Registra el resultado de un paso del test.

    Args:
        step_name: Nombre del paso
        passed: Si pasó o falló
        details: Detalles adicionales del error
    """
    test_results.append((step_name, passed, details))
    if passed:
        print(f"✅ {step_name} COMPLETADO")
    else:
        print(f"❌ {step_name} FALLÓ: {details}")


def test_complete_flow():
    """
    Prueba el flujo completo de solicitud de taxi.

    Flujo:
    1. Saludo inicial
    2. Solicitud de taxi
    3. Proporcionar dirección
    4. Confirmar dirección
    5. Método de pago
    6. Confirmación final
    7. Despacho

    NOTA: Este test continúa aunque haya fallos, reportando todos al final.
    """
    print_separator()
    print("🧪 INICIANDO TEST DEL FLUJO COMPLETO DE TAXI")
    print_separator()

    thread_id = None

    # ==================== PASO 1: SALUDO INICIAL ====================
    print("📝 PASO 1: Saludo inicial")
    print("-" * 80)

    try:
        response = send_message("Hola, buenos días")
        thread_id = response.get("thread_id")

        if not thread_id:
            record_test("PASO 1", False, "No se recibió thread_id")
        elif "Alice" not in response.get("message", ""):
            record_test("PASO 1", False, "Alice no se presentó")
        else:
            record_test("PASO 1", True)
    except Exception as e:
        record_test("PASO 1", False, f"Error inesperado: {str(e)}")

    time.sleep(1)
    print_separator()

    # ==================== PASO 2: SOLICITUD DE TAXI ====================
    print("📝 PASO 2: Solicitar taxi")
    print("-" * 80)

    try:
        response = send_message("Necesito un taxi", thread_id)
        message = response.get("message", "").lower()

        if "dirección" not in message and "dónde" not in message:
            record_test("PASO 2", False, "Alice no preguntó por la dirección")
        else:
            record_test("PASO 2", True)
    except Exception as e:
        record_test("PASO 2", False, f"Error inesperado: {str(e)}")

    time.sleep(1)
    print_separator()

    # ==================== PASO 3: PROPORCIONAR DIRECCIÓN ====================
    print("📝 PASO 3: Proporcionar dirección")
    print("-" * 80)

    try:
        response = send_message("Calle setenta y dos número cuarenta y tres venticinco en El Prado", thread_id)
        message = response.get("message", "")

        # Debe repetir la dirección con los números correctos
        if "72" in message or "setenta y dos" in message.lower():
            record_test("PASO 3", True, "Dirección capturada")
        else:
            record_test("PASO 3", False, f"Alice no repitió la dirección. Respuesta: {message}")
    except Exception as e:
        record_test("PASO 3", False, f"Error inesperado: {str(e)}")

    time.sleep(1)
    print_separator()

    # ==================== PASO 4: CONFIRMAR DIRECCIÓN ====================
    print("📝 PASO 4: Confirmar dirección")
    print("-" * 80)

    try:
        response = send_message("Sí, es correcta", thread_id)
        message = response.get("message", "").lower()

        # Debería preguntar por método de pago o avanzar
        if any(word in message for word in ["pago", "efectivo", "nequi", "confirmo", "cómo prefieres"]):
            record_test("PASO 4", True, "Avanzó al siguiente paso")
        elif not message or message.strip() == "":
            record_test("PASO 4", False, "Mensaje vacío - posible problema de continuidad")
        else:
            record_test("PASO 4", False, f"No avanzó correctamente. Respuesta: {message}")
    except Exception as e:
        record_test("PASO 4", False, f"Error inesperado: {str(e)}")

    time.sleep(1)
    print_separator()

    # ==================== PASO 5: MÉTODO DE PAGO ====================
    print("📝 PASO 5: Método de pago")
    print("-" * 80)

    try:
        # Si preguntó por pago, responder
        if "pago" in message:
            response = send_message("Efectivo", thread_id)
            message = response.get("message", "").lower()

        # Debería mostrar confirmación final o preguntar por detalles adicionales
        if any(word in message for word in ["confirmo", "correcto", "servicio", "detalles", "necesitas"]):
            record_test("PASO 5", True)
        else:
            record_test("PASO 5", False, f"No llegó a confirmación. Respuesta: {message}")
    except Exception as e:
        record_test("PASO 5", False, f"Error inesperado: {str(e)}")

    time.sleep(1)
    print_separator()

    # ==================== PASO 6: CONFIRMAR TODO ====================
    print("📝 PASO 6: Confirmar servicio")
    print("-" * 80)

    try:
        # Si no está en confirmación aún, avanzar
        if "confirmo" not in message and "necesitas" not in message:
            response = send_message("No, nada más", thread_id)
            message = response.get("message", "").lower()

        # Ahora debería estar en confirmación final
        if "confirmo" in message or "correcto" in message or "servicio" in message:
            response = send_message("Sí, todo correcto", thread_id)
            message = response.get("message", "").lower()

        # Debería indicar que el taxi fue solicitado
        if any(word in message for word in ["solicitado", "camino", "listo", "enviado"]):
            record_test("PASO 6", True, "Servicio confirmado y despachado")
        else:
            record_test("PASO 6", False, f"No se confirmó el despacho. Respuesta: {message}")
    except Exception as e:
        record_test("PASO 6", False, f"Error inesperado: {str(e)}")

    print_separator()

    # ==================== RESUMEN ====================
    print("📊 RESUMEN DEL TEST")
    print_separator()
    print(f"Thread ID utilizado: {thread_id}\n")

    passed_count = sum(1 for _, passed, _ in test_results if passed)
    total_count = len(test_results)

    print(f"Resultados: {passed_count}/{total_count} pasos completados exitosamente\n")

    for step_name, passed, details in test_results:
        status = "✅" if passed else "❌"
        print(f"{status} {step_name}")
        if not passed and details:
            print(f"   └─ {details}")

    print_separator()

    if passed_count == total_count:
        print("🎉 TEST COMPLETADO EXITOSAMENTE - TODOS LOS PASOS PASARON")
        print_separator()
        return True
    else:
        print(f"⚠️  TEST COMPLETADO CON ERRORES - {total_count - passed_count} paso(s) fallaron")
        print_separator()
        return False


def test_direction_correction():
    """
    Prueba el flujo de corrección de dirección.
    """
    test_results.clear()
    print_separator()
    print("🧪 PRUEBA DE CORRECCIÓN DE DIRECCIÓN")
    print_separator()

    thread_id = None

    try:
        # Inicio rápido
        response = send_message("Hola, necesito un taxi", None)
        thread_id = response.get("thread_id")
        time.sleep(0.5)
        print_separator()

        # Dar dirección
        response = send_message("Calle 50 número 20 30", thread_id)
        time.sleep(0.5)
        print_separator()

        # Corregir dirección
        response = send_message("No, es Calle 51 número 20 30", thread_id)

        message = response.get("message", "")
        if "51" in message:
            record_test("CORRECCIÓN DE DIRECCIÓN", True)
        else:
            record_test("CORRECCIÓN DE DIRECCIÓN", False, "Alice no capturó la corrección")

    except Exception as e:
        record_test("CORRECCIÓN DE DIRECCIÓN", False, f"Error inesperado: {str(e)}")

    print_separator()
    return all(passed for _, passed, _ in test_results)


def test_state_persistence():
    """
    Verifica que el estado persista entre mensajes.
    """
    test_results.clear()
    print_separator()
    print("🧪 PRUEBA DE PERSISTENCIA DE ESTADO")
    print_separator()

    try:
        # Primer mensaje
        response1 = send_message("Hola", None)
        thread_id = response1.get("thread_id")
        time.sleep(0.5)
        print_separator()

        # Segundo mensaje - debería recordar el contexto
        response2 = send_message("Necesito un taxi", thread_id)

        # No debería volver a presentarse
        if "Soy Alice" in response2.get("message", ""):
            record_test("PERSISTENCIA DE ESTADO", False, "Alice se volvió a presentar (no hay persistencia)")
        else:
            record_test("PERSISTENCIA DE ESTADO", True)

    except Exception as e:
        record_test("PERSISTENCIA DE ESTADO", False, f"Error inesperado: {str(e)}")

    print_separator()
    return all(passed for _, passed, _ in test_results)


if __name__ == "__main__":
    print("\n" + "🚕" * 40)
    print("TEST SUITE - SISTEMA DE TAXI 3 22")
    print("🚕" * 40 + "\n")

    try:
        # Verificar que el servidor esté corriendo
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        print("✅ Servidor está corriendo\n")

    except requests.exceptions.RequestException:
        print("❌ ERROR: El servidor no está corriendo")
        print("   Por favor ejecuta: uv run uvicorn app.main:app --reload")
        exit(1)

    # Ejecutar tests (todos, sin interrumpir)
    all_passed = True

    try:
        # Test 1: Flujo completo
        test_results.clear()
        result1 = test_complete_flow()
        all_passed = all_passed and result1
        time.sleep(2)

        # Test 2: Corrección de dirección
        result2 = test_direction_correction()
        all_passed = all_passed and result2
        time.sleep(2)

        # Test 3: Persistencia
        result3 = test_state_persistence()
        all_passed = all_passed and result3

        # Resumen final
        print("\n" + "=" * 80)
        print("RESUMEN FINAL DE TODOS LOS TESTS")
        print("=" * 80 + "\n")

        print(f"Test 1 - Flujo Completo: {'✅ PASÓ' if result1 else '❌ FALLÓ'}")
        print(f"Test 2 - Corrección de Dirección: {'✅ PASÓ' if result2 else '❌ FALLÓ'}")
        print(f"Test 3 - Persistencia de Estado: {'✅ PASÓ' if result3 else '❌ FALLÓ'}")

        print("\n" + "=" * 80 + "\n")

        if all_passed:
            print("🎉" * 40)
            print("TODOS LOS TESTS PASARON EXITOSAMENTE")
            print("🎉" * 40 + "\n")
            exit(0)
        else:
            print("⚠️ " * 40)
            print("ALGUNOS TESTS FALLARON - REVISAR RESULTADOS ARRIBA")
            print("⚠️ " * 40 + "\n")
            exit(1)

    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO INESPERADO: {str(e)}\n")
        import traceback
        traceback.print_exc()
        exit(1)
