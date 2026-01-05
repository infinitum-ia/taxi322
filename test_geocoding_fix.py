"""
Script para probar la corrección de geocodificación.
Simula el flujo completo de normalización y geocodificación.
"""

import asyncio
from app.tools.address_tools import normalize_direccion_for_geocoding
from app.tools.customer_tools import consultar_coordenadas_gpt_impl


def test_normalization_fix():
    """Prueba la corrección de normalización de direcciones."""
    print("\n" + "="*80)
    print("TEST 1: Normalización de dirección con número en barrio")
    print("="*80)

    # Simular dirección parseada incorrectamente (como viene actualmente del sistema)
    direccion_parseada_incorrecta = {
        "via_tipo": "Carrera",
        "via_numero": "43",
        "letra_via": "B",
        "sufijo_via": None,
        "numero": None,
        "letra_numero": None,
        "numero_casa": None,  # ← Debería tener 112
        "letra_casa": None,
        "placa_numero": None,
        "barrio": "número 112-1",  # ← Aquí está el problema
        "ciudad": None,
        "referencias": None,
        "validado": False
    }

    print(f"\n>> Direccion parseada (INCORRECTA):")
    print(f"   via_tipo={direccion_parseada_incorrecta['via_tipo']}")
    print(f"   via_numero={direccion_parseada_incorrecta['via_numero']}")
    print(f"   letra_via={direccion_parseada_incorrecta['letra_via']}")
    print(f"   numero_casa={direccion_parseada_incorrecta['numero_casa']} <- Vacio (MALO)")
    print(f"   barrio={direccion_parseada_incorrecta['barrio']} <- Contiene el numero (MALO)")

    # Aplicar el FIX del código
    import re
    direccion_dict = direccion_parseada_incorrecta.copy()

    if not direccion_dict.get("numero_casa") and direccion_dict.get("barrio"):
        barrio_text = direccion_dict.get("barrio", "")
        match = re.search(r'(?:numero)?\s*(\d+)(?:\s*-\s*(\d+))?', barrio_text, re.IGNORECASE)
        if match:
            direccion_dict["numero_casa"] = match.group(1)
            if match.group(2):
                direccion_dict["placa_numero"] = match.group(2)
            direccion_dict["barrio"] = None
            print(f"\n>> FIX APLICADO:")
            print(f"   numero_casa={direccion_dict['numero_casa']} (extraido del barrio)")
            print(f"   placa_numero={direccion_dict['placa_numero']} (extraido del barrio)")
            print(f"   barrio={direccion_dict['barrio']} (limpiado)")

    # Normalizar dirección
    direccion_normalizada = normalize_direccion_for_geocoding(direccion_dict)
    print(f"\n>> Direccion normalizada para API:")
    print(f"   {direccion_normalizada}")

    expected = "cr 43b 112"
    if direccion_normalizada == expected:
        print(f"\n>> SUCCESS: La normalizacion es correcta! (esperado: '{expected}')")
    else:
        print(f"\n>> FAIL: La normalizacion es incorrecta")
        print(f"   Esperado: '{expected}'")
        print(f"   Obtenido: '{direccion_normalizada}'")

    return direccion_normalizada


async def test_geocoding_api(direccion_normalizada: str):
    """Prueba la llamada a la API de geocodificación."""
    print("\n" + "="*80)
    print("TEST 2: Llamada a la API de geocodificación")
    print("="*80)

    client_id = "3042124567"  # ID de prueba del log

    print(f"\n>> Llamando API de geocodificacion...")
    print(f"   CLIENT_ID: {client_id}")
    print(f"   UBICACION_NORMALIZADA: {direccion_normalizada}")

    result = await consultar_coordenadas_gpt_impl(client_id, direccion_normalizada)

    print(f"\n>> Resultado de la API:")
    print(f"   success: {result.get('success')}")

    if result.get("success"):
        data = result.get("data", {})

        # Verificar campos en mayúsculas
        print(f"\n>> Campos de respuesta:")
        print(f"   RESPUESTA: {data.get('RESPUESTA')}")
        print(f"   LISTA_DIRECCIONES: {data.get('LISTA_DIRECCIONES')}")
        print(f"   LATITUD: {data.get('LATITUD')}")
        print(f"   LONGITUD: {data.get('LONGITUD')}")
        print(f"   ZONA: {data.get('ZONA')}")

        # Parsear LISTA_DIRECCIONES
        lista_direcciones = data.get("LISTA_DIRECCIONES", "[]")
        if isinstance(lista_direcciones, str):
            import json
            try:
                lista_direcciones = json.loads(lista_direcciones)
                print(f"\n>> LISTA_DIRECCIONES parseada: {len(lista_direcciones)} resultados")
                if len(lista_direcciones) > 0:
                    print(f"   Primera direccion: {lista_direcciones[0]}")
            except Exception as e:
                print(f"\n>> Error parseando LISTA_DIRECCIONES: {e}")

        # Verificar coordenadas
        latitud = (data.get("latitud") or data.get("lat") or
                  data.get("LATITUD") or data.get("LAT"))
        longitud = (data.get("longitud") or data.get("lng") or
                   data.get("LONGITUD") or data.get("LNG"))

        # Filter NULL strings
        if latitud in ["NULL", "null", None, ""]:
            latitud = None
        if longitud in ["NULL", "null", None, ""]:
            longitud = None

        print(f"\n>> Coordenadas extraidas:")
        print(f"   Latitud: {latitud}")
        print(f"   Longitud: {longitud}")

        if latitud and longitud:
            print(f"\n>> SUCCESS: Coordenadas obtenidas correctamente!")
        else:
            print(f"\n>> WARNING: No se obtuvieron coordenadas validas")
            if isinstance(lista_direcciones, list) and len(lista_direcciones) > 0:
                print(f"   Pero LISTA_DIRECCIONES tiene {len(lista_direcciones)} resultado(s)")
                print(f"   Esto podria indicar que las coordenadas estan en LISTA_DIRECCIONES[0]")
    else:
        print(f"\n>> ERROR: {result.get('message')}")


async def main():
    """Ejecutar todas las pruebas."""
    print("\n" + "="*80)
    print("PRUEBA DE CORRECCIÓN DE GEOCODIFICACIÓN")
    print("="*80)

    # Test 1: Normalización
    direccion_normalizada = test_normalization_fix()

    # Test 2: API de geocodificación
    await test_geocoding_api(direccion_normalizada)

    print("\n" + "="*80)
    print("PRUEBAS COMPLETADAS")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
