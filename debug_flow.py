"""
Script de diagnóstico para depurar el flujo de direcciones.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_flow_with_debug():
    """Prueba el flujo con debugging detallado."""

    print("\n" + "="*80)
    print("DIAGNÓSTICO: Flujo de Confirmación de Dirección")
    print("="*80 + "\n")

    thread_id = None

    # Paso 1: Enviar dirección desde el inicio
    print("📝 PASO 1: Dar dirección directamente")
    print("-"*80)

    payload1 = {
        "message": "es para la calle sesenta y nueve b numero ventinueve a cincuenta",
        "user_id": "debug_user"
    }

    print(f"📤 REQUEST:")
    print(f"   URL: {BASE_URL}/api/v1/chat/")
    print(f"   Payload: {json.dumps(payload1, indent=2, ensure_ascii=False)}")

    response1 = requests.post(f"{BASE_URL}/api/v1/chat/", json=payload1)
    data1 = response1.json()

    print(f"\n📥 RESPONSE:")
    print(f"   Status: {response1.status_code}")
    print(f"   Thread ID: {data1.get('thread_id')}")
    print(f"   Message: {data1.get('message')}")
    print(f"   Is Interrupted: {data1.get('is_interrupted')}")

    thread_id = data1.get('thread_id')

    # Verificar el estado después del primer mensaje
    print(f"\n🔍 Verificando estado del thread...")
    state_response = requests.get(f"{BASE_URL}/api/v1/threads/{thread_id}/state")
    if state_response.status_code == 200:
        state_data = state_response.json()
        agente_actual = state_data.get('values', {}).get('agente_actual')
        print(f"   agente_actual en estado: {agente_actual}")

    print("\n" + "="*80 + "\n")

    # Paso 2: Confirmar dirección
    print("📝 PASO 2: Confirmar dirección")
    print("-"*80)

    payload2 = {
        "message": "si, es correcta",
        "user_id": "debug_user",
        "thread_id": thread_id  # ← Usar el mismo thread_id
    }

    print(f"📤 REQUEST:")
    print(f"   URL: {BASE_URL}/api/v1/chat/")
    print(f"   Payload: {json.dumps(payload2, indent=2, ensure_ascii=False)}")

    response2 = requests.post(f"{BASE_URL}/api/v1/chat/", json=payload2)
    data2 = response2.json()

    print(f"\n📥 RESPONSE:")
    print(f"   Status: {response2.status_code}")
    print(f"   Thread ID: {data2.get('thread_id')}")
    print(f"   Message: {data2.get('message')}")
    print(f"   Is Interrupted: {data2.get('is_interrupted')}")

    # Verificar el estado después del segundo mensaje
    print(f"\n🔍 Verificando estado del thread...")
    state_response2 = requests.get(f"{BASE_URL}/api/v1/threads/{thread_id}/state")
    if state_response2.status_code == 200:
        state_data2 = state_response2.json()
        agente_actual2 = state_data2.get('values', {}).get('agente_actual')
        print(f"   agente_actual en estado: {agente_actual2}")

    print("\n" + "="*80 + "\n")

    # Análisis
    print("📊 ANÁLISIS:")
    print("-"*80)

    message2 = data2.get('message', '').lower()

    if "puedo ayudarte" in message2:
        print("❌ PROBLEMA DETECTADO:")
        print("   El sistema perdió el contexto y volvió al inicio")
        print("\n🔍 POSIBLES CAUSAS:")
        print("   1. agente_actual no se guardó correctamente después del primer mensaje")
        print("   2. El router está leyendo agente_actual = None")
        print("   3. El RECEPCIONISTA está recibiendo 'sí, es correcta' sin contexto")
        print("\n💡 SOLUCIÓN:")
        print("   Revisar que el estado se persista correctamente entre mensajes")
    elif "pago" in message2 or "cómo prefieres" in message2:
        print("✅ FLUJO CORRECTO:")
        print("   El sistema avanzó al NAVEGANTE y luego al OPERADOR")
        print("   Preguntó por el método de pago como se esperaba")
    elif not message2 or message2.strip() == "":
        print("❌ PROBLEMA DETECTADO:")
        print("   Mensaje vacío - el LLM no generó respuesta de texto")
        print("\n🔍 POSIBLE CAUSA:")
        print("   El LLM hizo un tool_call pero sin contenido de mensaje")
    else:
        print("⚠️  RESPUESTA INESPERADA:")
        print(f"   Mensaje: {data2.get('message')}")

    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    try:
        # Verificar que el servidor esté corriendo
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        print("[OK] Servidor esta corriendo")

        test_flow_with_debug()

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] El servidor no esta corriendo o no responde")
        print(f"   {str(e)}")
        print("\n   Por favor ejecuta: uv run uvicorn app.main:app --reload")
