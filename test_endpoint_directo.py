"""
Script para probar directamente el endpoint de geocodificación
"""

import asyncio
import httpx
import json
from app.core.config import settings


async def test_endpoint_directo():
    """Prueba directa al endpoint de coordenadas."""

    # Dirección a probar
    direccion = "cr 43b 112"
    client_id = "3042124567"

    print("="*80)
    print("PRUEBA DIRECTA AL ENDPOINT DE GEOCODIFICACION")
    print("="*80)
    print(f"\nEndpoint: {settings.CUSTOMER_API_BASE_URL}/api/consulta-coordenadas")
    print(f"Direccion: {direccion}")
    print(f"Client ID: {client_id}")

    payload = {
        "CLIENT_ID": client_id,
        "UBICACION_NORMALIZADA": direccion
    }

    print(f"\nPayload enviado:")
    print(json.dumps(payload, indent=2))

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            print(f"\nHaciendo peticion POST...")
            response = await client.post(
                f"{settings.CUSTOMER_API_BASE_URL}/api/consulta-coordenadas",
                json=payload
            )

            print(f"\n>> Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                print(f"\n>> RESPUESTA COMPLETA:")
                print(json.dumps(data, indent=2, ensure_ascii=False))

                print(f"\n>> ANALISIS DE LA RESPUESTA:")
                print(f"   RESPUESTA: {data.get('RESPUESTA')}")
                print(f"   MASDEUNA: {data.get('MASDEUNA')}")
                print(f"   COMPRENCION: {data.get('COMPRENCION')}")
                print(f"   ZONA: {data.get('ZONA')}")
                print(f"   LATITUD: {data.get('LATITUD')}")
                print(f"   LONGITUD: {data.get('LONGITUD')}")
                print(f"   MUNICIPIO: {data.get('MUNICIPIO')}")
                print(f"   DIRECCION_MENSAJES: {data.get('DIRECCION_MENSAJES')}")

                # Parsear LISTA_DIRECCIONES
                lista_direcciones = data.get("LISTA_DIRECCIONES", "[]")
                print(f"\n>> LISTA_DIRECCIONES (raw): {lista_direcciones}")
                print(f"   Tipo: {type(lista_direcciones)}")

                if isinstance(lista_direcciones, str):
                    try:
                        lista_parseada = json.loads(lista_direcciones)
                        print(f"\n>> LISTA_DIRECCIONES (parseada):")
                        print(f"   Numero de resultados: {len(lista_parseada)}")

                        if len(lista_parseada) > 0:
                            print(f"\n   PRIMER RESULTADO:")
                            print(json.dumps(lista_parseada[0], indent=4, ensure_ascii=False))

                            if len(lista_parseada) > 1:
                                print(f"\n   TOTAL DE RESULTADOS: {len(lista_parseada)}")
                                print(f"   (Mostrando solo el primero)")
                        else:
                            print(f"   >> Lista vacia - no se encontraron direcciones")
                    except Exception as e:
                        print(f"   >> Error parseando JSON: {e}")
                elif isinstance(lista_direcciones, list):
                    print(f"   >> Ya es una lista con {len(lista_direcciones)} elementos")
                    if len(lista_direcciones) > 0:
                        print(json.dumps(lista_direcciones[0], indent=4, ensure_ascii=False))

            else:
                print(f"\n>> ERROR: HTTP {response.status_code}")
                print(f">> Response text: {response.text}")

    except Exception as e:
        print(f"\n>> EXCEPCION: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(test_endpoint_directo())
