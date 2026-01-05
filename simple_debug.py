"""
Script de diagnostico simple sin emojis para evitar errores de encoding.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_thread_persistence():
    """Prueba si el thread_id persiste entre requests."""

    print("\n" + "="*80)
    print("DIAGNOSTICO: Persistencia de thread_id")
    print("="*80 + "\n")

    # PASO 1: Enviar primer mensaje
    print("PASO 1: Enviar direccion")
    print("-"*80)

    payload1 = {
        "message": "es para la calle sesenta y nueve b numero ventinueve a cincuenta",
        "user_id": "debug_user"
    }

    print("REQUEST:")
    print(f"  URL: {BASE_URL}/api/v1/chat/")
    print(f"  Payload: {json.dumps(payload1, indent=2, ensure_ascii=False)}")

    response1 = requests.post(f"{BASE_URL}/api/v1/chat/", json=payload1)
    data1 = response1.json()

    print("\nRESPONSE:")
    print(f"  Status: {response1.status_code}")
    print(f"  Thread ID: {data1.get('thread_id')}")
    print(f"  Message: {data1.get('message')}")

    thread_id = data1.get('thread_id')

    # Verificar estado
    print("\nVerificando estado del thread...")
    state_response = requests.get(f"{BASE_URL}/api/v1/threads/{thread_id}/state")
    if state_response.status_code == 200:
        state_data = state_response.json()
        agente_actual = state_data.get('values', {}).get('agente_actual')
        print(f"  agente_actual: {agente_actual}")

    print("\n" + "="*80 + "\n")

    # PASO 2: Confirmar con el MISMO thread_id
    print("PASO 2: Confirmar direccion (usando MISMO thread_id)")
    print("-"*80)

    payload2 = {
        "message": "si, es correcta",
        "user_id": "debug_user",
        "thread_id": thread_id  # <-- CRITICO: usar el mismo thread_id
    }

    print("REQUEST:")
    print(f"  URL: {BASE_URL}/api/v1/chat/")
    print(f"  Payload: {json.dumps(payload2, indent=2, ensure_ascii=False)}")

    response2 = requests.post(f"{BASE_URL}/api/v1/chat/", json=payload2)
    data2 = response2.json()

    print("\nRESPONSE:")
    print(f"  Status: {response2.status_code}")
    print(f"  Thread ID: {data2.get('thread_id')}")
    print(f"  Message: {data2.get('message')}")

    # Verificar estado nuevamente
    print("\nVerificando estado del thread...")
    state_response2 = requests.get(f"{BASE_URL}/api/v1/threads/{thread_id}/state")
    if state_response2.status_code == 200:
        state_data2 = state_response2.json()
        agente_actual2 = state_data2.get('values', {}).get('agente_actual')
        print(f"  agente_actual: {agente_actual2}")

    print("\n" + "="*80 + "\n")

    # ANALISIS
    print("ANALISIS:")
    print("-"*80)

    message2 = data2.get('message', '').lower()

    if "puedo ayudarte" in message2:
        print("PROBLEMA: El sistema perdio el contexto")
        print("  La respuesta volvio al inicio como nueva conversacion")
        print("\nPOSIBLES CAUSAS:")
        print("  1. thread_id NO se envio en el segundo request")
        print("  2. agente_actual se reseteo a None")
        print("  3. El checkpointer no guardo el estado")
    elif "pago" in message2 or "como prefieres" in message2:
        print("EXITO: El sistema avanzo correctamente")
        print("  Pregunto por metodo de pago como se esperaba")
    elif not message2 or message2.strip() == "":
        print("PROBLEMA: Mensaje vacio")
        print("  El LLM no genero texto")
    else:
        print("RESPUESTA INESPERADA:")
        print(f"  Mensaje: {data2.get('message')}")

    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    try:
        # Verificar servidor
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        print("Servidor esta corriendo\n")

        test_thread_persistence()

    except requests.exceptions.RequestException as e:
        print(f"ERROR: El servidor no esta corriendo")
        print(f"  {str(e)}")
        print("\n  Por favor ejecuta: uv run uvicorn app.main:app --reload")
