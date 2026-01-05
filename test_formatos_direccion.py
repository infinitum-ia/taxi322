"""
Script para probar diferentes formatos de dirección
"""

import asyncio
import httpx
import json
from app.core.config import settings


async def test_direccion(direccion: str, client_id: str = "3042124567"):
    """Prueba una dirección específica."""

    payload = {
        "CLIENT_ID": client_id,
        "UBICACION_NORMALIZADA": direccion
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{settings.CUSTOMER_API_BASE_URL}/api/consulta-coordenadas",
                json=payload
            )

            if response.status_code == 200:
                data = response.json()

                # Parsear LISTA_DIRECCIONES
                lista_direcciones = data.get("LISTA_DIRECCIONES", "[]")
                if isinstance(lista_direcciones, str):
                    lista_direcciones = json.loads(lista_direcciones)

                return {
                    "direccion": direccion,
                    "respuesta": data.get('RESPUESTA'),
                    "num_resultados": len(lista_direcciones) if isinstance(lista_direcciones, list) else 0,
                    "latitud": data.get('LATITUD'),
                    "longitud": data.get('LONGITUD'),
                    "zona": data.get('ZONA'),
                    "primer_resultado": lista_direcciones[0] if isinstance(lista_direcciones, list) and len(lista_direcciones) > 0 else None
                }
            else:
                return {
                    "direccion": direccion,
                    "error": f"HTTP {response.status_code}"
                }
    except Exception as e:
        return {
            "direccion": direccion,
            "error": str(e)
        }


async def test_multiples_formatos():
    """Prueba múltiples formatos de dirección."""

    print("="*80)
    print("PRUEBA DE MULTIPLES FORMATOS DE DIRECCION")
    print("="*80)

    # Diferentes formatos de la misma dirección
    formatos = [
        # Formato actual (normalizado)
        "cr 43b 112",

        # Con símbolo #
        "cr 43b #112",
        "cr 43b # 112",



        # Con guion (casa-placa)
        "cr 43b 112-1",
        "cr 43b #112-1",


        # Sin letra
        "cr 43 112",


        # Prueba con direcciones conocidas de Barranquilla

        "cl 72 43",
        "cr 50 12",
    ]

    print(f"\nProbando {len(formatos)} formatos diferentes...\n")

    resultados = []
    for formato in formatos:
        print(f"Probando: '{formato}'...", end=" ")
        resultado = await test_direccion(formato)
        resultados.append(resultado)

        if resultado.get('respuesta') == 'TRUE' or resultado.get('num_resultados', 0) > 0:
            print(f"[OK] EXITO! ({resultado.get('num_resultados', 0)} resultados)")
        else:
            print(f"[X] Sin resultados")

    print("\n" + "="*80)
    print("RESUMEN DE RESULTADOS")
    print("="*80)

    exitosos = [r for r in resultados if r.get('respuesta') == 'TRUE' or r.get('num_resultados', 0) > 0]

    if exitosos:
        print(f"\n[OK] FORMATOS EXITOSOS ({len(exitosos)}):")
        for r in exitosos:
            print(f"\n  Direccion: '{r['direccion']}'")
            print(f"    Resultados: {r.get('num_resultados', 0)}")
            print(f"    Zona: {r.get('zona')}")
            print(f"    Coordenadas: ({r.get('latitud')}, {r.get('longitud')})")
            if r.get('primer_resultado'):
                print(f"    Primer resultado: {json.dumps(r['primer_resultado'], indent=6, ensure_ascii=False)}")
    else:
        print(f"\n[X] NINGUN FORMATO FUNCIONO")
        print(f"\nRecomendacion: El servicio de geocodificacion podria:")
        print(f"  1. No tener datos de Barranquilla")
        print(f"  2. Requerir un formato especifico diferente")
        print(f"  3. Necesitar contexto adicional (ciudad, barrio)")

    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(test_multiples_formatos())
