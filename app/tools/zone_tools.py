"""Zone validation tools for taxi service coverage."""

from langchain_core.tools import tool
from typing import Literal, Optional
from difflib import SequenceMatcher


# ==================== ZONE COVERAGE DATABASE (MOCK) ====================

# In production, this would be replaced with a real geolocation service or database
ZONE_COVERAGE = {
    "BARRANQUILLA": {
        "barrios": [
            # Centro y alrededores
            "Centro", "Paseo Bolívar", "Barrio Abajo", "La Luz", "El Boliche",

            # Norte
            "El Prado", "Alto Prado", "Granadillo", "Altos del Prado",  "Villa Country",
            "Riomar", "Buenavista", "Villa Santos", "Los Nogales", "El Poblado",
            "Las Delicias", "Miramar", "La Campiña", "El Castillo",

            # Sur
            "San Roque", "Rebolo", "Las Nieves", "La Paz", "Simón Bolívar",
            "La Manga", "Las Américas", "Los Andes", "El Ferry",

            # Suroccidente
            "Boston", "Bellavista", "El Silencio", "La Victoria", "Chiquinquirá",
            "Los Trupillos", "Carrizal", "La Pradera",

            # Suroriente
            "Ciudadela 20 de Julio", "Las Malvinas", "Villa San Pedro",
            "Lipaya", "La Chinita", "Cuchilla de Villate",

            # Metropolitana
            "La Concepción", "Villa Carolina", "La Esmeralda", "San Isidro",
            "Santo Domingo", "El Valle", "Los Olivos", "Paraíso",
        ],
        "keywords": [
            "barranquilla", "atlántico", "b/quilla", "baq",
            "centro", "norte", "sur", "metropolitana", "riomar",
            "prado", "el prado", "alto prado"
        ],
        "capital": True,
    },
    "SOLEDAD": {
        "barrios": [
            "Centro", "Villa Katanga", "La Granja", "Manzanares",
            "Villa Estadio", "El Edén", "San Antonio", "Buena Esperanza",
            "Los Robles", "Las Américas", "El Carmen", "Colinas del Río",
            "San José", "Urbanización 20 de Julio", "Las Flores",
        ],
        "keywords": [
            "soledad", "municipio soledad", "soledad atlántico",
            "katanga", "villa katanga"
        ],
        "capital": False,
    },
    "PUERTO_COLOMBIA": {
        "barrios": [
            "Centro", "Salgar", "Miramar", "Puerto Velero",
            "Pradomar", "Sabanilla", "La Playa", "El Pueblo",
        ],
        "keywords": [
            "puerto colombia", "puerto", "salgar", "sabanilla",
            "pradomar", "puerto velero", "miramar"
        ],
        "capital": False,
    },
    "GALAPA": {
        "barrios": [
            "Centro", "Villa Rosa", "La Gloria", "San Pedro",
            "El Carmen", "Las Américas", "Urbano", "Rural",
        ],
        "keywords": [
            "galapa", "municipio galapa", "galapa atlántico"
        ],
        "capital": False,
    },
}

# Out of coverage cities (explicitly reject)
OUT_OF_COVERAGE_CITIES = {
    "CARTAGENA": ["cartagena", "ctg", "bolivar"],
    "SANTA_MARTA": ["santa marta", "santa", "marta", "samario"],
    "BOGOTA": ["bogotá", "bogota", "distrito capital"],
    "MEDELLIN": ["medellín", "medellin"],
    "CALI": ["cali", "valle"],
    "MONTERIA": ["montería", "monteria"],
    "SINCELEJO": ["sincelejo"],
    "VALLEDUPAR": ["valledupar"],
}


def normalize_text(text: str) -> str:
    """
    Normalize Colombian text for fuzzy matching.

    Args:
        text: Input text

    Returns:
        Normalized lowercase text without accents
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower().strip()

    # Remove common Colombian accent variations
    replacements = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "ñ": "n",  # Keep ñ for now as it's distinctive
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def fuzzy_match_score(text1: str, text2: str) -> float:
    """
    Calculate fuzzy match score between two strings.

    Args:
        text1: First string
        text2: Second string

    Returns:
        Similarity score between 0.0 and 1.0
    """
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    # Exact match bonus
    if norm1 == norm2:
        return 1.0

    # Substring match bonus
    if norm1 in norm2 or norm2 in norm1:
        return 0.9

    # Fuzzy matching using SequenceMatcher
    return SequenceMatcher(None, norm1, norm2).ratio()


# ==================== VALIDATION TOOLS ====================

@tool
def validate_zone(barrio: str, ciudad: Optional[str] = None) -> dict:
    """
    Validate if a location is within taxi service coverage.

    SIMPLIFIED: Only validates CITY (Barranquilla, Soledad, Puerto Colombia, Galapa).
    Does NOT validate specific neighborhoods - all neighborhoods in covered cities are accepted.

    Args:
        barrio: Neighborhood name (optional, not validated)
        ciudad: City name (REQUIRED for validation)

    Returns:
        Dictionary with validation result:
        {
            "zona": str,  # BARRANQUILLA, SOLEDAD, PUERTO_COLOMBIA, GALAPA, RECHAZADO, or None
            "confidence": float,  # 0.0 to 1.0
            "barrio_matched": str | None,  # Just returns barrio as-is
            "reason": str | None,  # Explanation if rejected or missing info
        }

    Examples:
        >>> validate_zone("El Prado", "Barranquilla")
        {"zona": "BARRANQUILLA", "confidence": 1.0, "barrio_matched": "El Prado", "reason": None}

        >>> validate_zone("Centro", "Soledad")
        {"zona": "SOLEDAD", "confidence": 1.0, "barrio_matched": "Centro", "reason": None}

        >>> validate_zone("Centro", "Cartagena")
        {"zona": "RECHAZADO", "confidence": 1.0, "reason": "Cartagena está fuera de cobertura..."}

        >>> validate_zone("Calle 90")
        {"zona": None, "confidence": 0.0, "reason": "Para validar la zona, necesito saber en qué ciudad estás..."}
    """
    # CRITICAL: If no ciudad provided, can't validate
    if not ciudad:
        return {
            "zona": None,
            "confidence": 0.0,
            "barrio_matched": barrio if barrio else None,
            "reason": "Para validar la zona, necesito saber en qué ciudad estás. ¿Es Barranquilla, Soledad, Puerto Colombia o Galapa?"
        }

    ciudad_norm = normalize_text(ciudad)

    # Step 1: Check if ciudad is OUT of coverage (reject)
    for out_city, keywords in OUT_OF_COVERAGE_CITIES.items():
        for keyword in keywords:
            if fuzzy_match_score(ciudad_norm, keyword) > 0.8:
                return {
                    "zona": "RECHAZADO",
                    "confidence": 1.0,
                    "barrio_matched": None,
                    "reason": f"{out_city.replace('_', ' ').title()} está fuera de cobertura. "
                              f"Solo atendemos Barranquilla, Soledad, Puerto Colombia y Galapa."
                }

    # Step 2: Check if ciudad is IN coverage (accept)
    for zone_name, zone_data in ZONE_COVERAGE.items():
        for keyword in zone_data["keywords"]:
            score = fuzzy_match_score(ciudad_norm, keyword)
            if score > 0.8:  # High confidence match
                return {
                    "zona": zone_name,
                    "confidence": round(score, 2),
                    "barrio_matched": barrio if barrio else None,
                    "reason": None,
                }

    # Step 3: Ciudad not recognized - ask for clarification
    return {
        "zona": None,
        "confidence": 0.0,
        "barrio_matched": barrio if barrio else None,
        "reason": f"No reconozco '{ciudad}'. ¿Es Barranquilla, Soledad, Puerto Colombia o Galapa?"
    }


@tool
def get_zone_info(zona: Literal["BARRANQUILLA", "SOLEDAD", "PUERTO_COLOMBIA", "GALAPA"]) -> dict:
    """
    Get detailed information about a service zone.

    Args:
        zona: Zone name

    Returns:
        Dictionary with zone information (barrios, keywords, etc.)
    """
    if zona not in ZONE_COVERAGE:
        return {"error": f"Zona '{zona}' no encontrada"}

    zone_data = ZONE_COVERAGE[zona]
    return {
        "zona": zona,
        "barrios": zone_data["barrios"],
        "total_barrios": len(zone_data["barrios"]),
        "es_capital": zone_data.get("capital", False),
    }


# ==================== EXPORT ====================

__all__ = [
    "validate_zone",
    "get_zone_info",
    "ZONE_COVERAGE",
]
