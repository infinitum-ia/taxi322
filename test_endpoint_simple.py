"""Script simple para probar el endpoint de chat con consulta de dirección."""

import requests
import json
from datetime import datetime

def test_chat_endpoint():
    """Prueba el endpoint con un cliente que tiene dirección registrada."""

    url = "http://localhost:8000/api/v1/chat"

    # Cliente con dirección registrada (ejemplo)
    payload = {
        "message": "Necesito un taxi",
        "thread_id": f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "user_id": "test_user",
        "client_id": "3022370040"  # Cliente de ejemplo
    }

    print("=" * 80)
    print("PRUEBA DE CONSULTA DE DIRECCIÓN")
    print("=" * 80)
    print(f"\nEnviando request...")
    print(f"Client ID: {payload['client_id']}")
    print(f"Thread ID: {payload['thread_id']}")
    print()

    try:
        response = requests.post(url, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()

            print("RESPUESTA DEL SERVIDOR:")
            print("-" * 80)
            print(f"Thread ID: {data.get('thread_id')}")
            print()
            print("Mensaje de Alice:")
            print(data.get('message', 'No message'))
            print()

            # Verificar si Alice consultó la dirección registrada
            message = data.get('message', '').lower()

            if 'registrada' in message or 'servicio antes' in message or 'veo que' in message:
                print("✅ ÉXITO: Alice consultó la dirección registrada!")
                print()
            elif 'desde' in message and ('dónde' in message or 'donde' in message):
                print("❌ PROBLEMA: Alice NO consultó la dirección registrada primero")
                print("   Está pidiendo la dirección directamente")
                print()
            else:
                print("⚠️  Respuesta inesperada - revisar manualmente")
                print()

        else:
            print(f"❌ Error HTTP {response.status_code}")
            print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"❌ Error en la conexión: {str(e)}")

    print("=" * 80)


if __name__ == "__main__":
    test_chat_endpoint()
