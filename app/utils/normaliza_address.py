"""
Servicio de normalización de direcciones
"""

import re


# Diccionario: PATRÓN → ABREVIATURA ESTÁNDAR
STREET_ABBREVIATIONS = {
    # Carrera (cr) - formato corto
    "carrera": "cr",
    "cra": "cr",
    "cr": "cr",
    "kr": "cr",
    "kra": "cr",

    # Calle (cl) - formato corto
    "calle": "cl",
    "cll": "cl",
    "cl": "cl",

    # Diagonal (DIAG) - formato completo
    "diagonal": "DIAG",
    "diag": "DIAG",
    "dg": "DIAG",

    # Transversal (TV) - formato completo
    "transversal": "TV",
    "transv": "TV",
    "tv": "TV",

    # Avenida (AV) - formato completo
    "avenida": "AV",
    "av": "AV",
    "ave": "AV",

    # Circular (CIRC) - formato completo
    "circular": "CIRC",
    "circ": "CIRC",

    # Manzana (MZ) - formato completo
    "manzana": "MZ",
    "mz": "MZ",
    "man": "MZ",

    # Lote (LT) - formato completo
    "lote": "LT",
    "lt": "LT",

    # Kilometro (KM) - formato completo
    "kilometro": "KM",
    "kilómetro": "KM",
    "km": "KM",
}


class AddressService:
    """Servicio para normalización de direcciones"""

    @staticmethod
    def normalize(address: str) -> str:
        """
        Normaliza dirección a formato abreviado estándar.

        Args:
            address: Dirección a normalizar

        Returns:
            Dirección normalizada
        """
        if not address or not isinstance(address, str):
            return ""

        # Convertir a minúsculas para comparación
        normalized = address.lower()

        # 1. Eliminar símbolos #, comas y palabras "numero", "num", "no", "nro"
        normalized = re.sub(r'#', '', normalized)
        normalized = re.sub(r',', ' ', normalized)  # Reemplazar comas por espacio
        normalized = re.sub(r'\b(numero|num|nro)\b\.?\s*', '', normalized, flags=re.IGNORECASE)

        # 2. Limpiar rangos con guión PRIMERO (ej: "30-50" → "30", "70-41" → "70")
        normalized = re.sub(r'(\d+)-\d+', r'\1', normalized)

        # 3. Ordenar patrones por longitud descendente (evita reemplazos parciales)
        sorted_patterns = sorted(
            STREET_ABBREVIATIONS.keys(),
            key=len,
            reverse=True
        )

        # 4. Realizar reemplazos de nomenclatura
        for pattern in sorted_patterns:
            # Regex: palabra completa, opcionalmente con punto al final
            regex = r'\b' + re.escape(pattern) + r'\.?\b'

            normalized = re.sub(
                regex,
                STREET_ABBREVIATIONS[pattern],
                normalized,
                flags=re.IGNORECASE
            )

        # 5. Simplificar direcciones con doble nomenclatura
        # Patrón: "cl 45 12 cr 5" → "cl 45 5" (eliminar número intermedio y segunda nomenclatura)
        normalized = re.sub(r'\b(cl|cr)\s+(\w+)\s+\d+\s+(cr|cl)\s+(\w+)', r'\1 \2 \4', normalized)

        # Patrón más simple: "cl 88b cr 77" → "cl 88b 77" (solo eliminar segunda nomenclatura)
        normalized = re.sub(r'\b(cl|cr)\s+(\w+)\s+(cr|cl)\s+(\w+)', r'\1 \2 \4', normalized)

        # 6. Capturar solo los dos primeros números (vía principal y secundaria)
        # Patrón: "cr 53 106 89" → "cr 53 106" (eliminar números adicionales)
        match = re.match(r'(\b(?:cl|cr|DIAG|TV|AV|CIRC|MZ|LT|KM)\s+\w+\s+\w+)\b.*', normalized)
        if match:
            normalized = match.group(1)

        # 7. Limpiar espacios múltiples
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized


# Instancia del servicio
address_service = AddressService()
