"""Colombian address parsing tools with suffix rules."""

from langchain_core.tools import tool
import re
from typing import Optional, Dict
from app.models.taxi_state import DireccionParseada
from app.utils.normaliza_address import address_service


# ==================== COLOMBIAN NUMBER WORDS ====================

# Low numbers (1-10) - when these appear after a letter, they're SUFFIXES
NUMEROS_BAJOS = {
    "uno": "1", "dos": "2", "tres": "3", "cuatro": "4", "cinco": "5",
    "seis": "6", "siete": "7", "ocho": "8", "nueve": "9", "diez": "10"
}

# Higher numbers (11+) - when these appear after a letter, they're SEPARATE numero field
NUMEROS_ALTOS = {
    "once": "11", "doce": "12", "trece": "13", "catorce": "14", "quince": "15",
    "dieciséis": "16", "dieciSeis": "16", "dieciseis": "16",
    "diecisiete": "17", "dieciocho": "18", "diecinueve": "19",
    "veinte": "20", "veintiuno": "21", "veintidos": "22", "veintitres": "23",
    "treinta": "30", "cuarenta": "40", "cincuenta": "50",
    "sesenta": "60", "setenta": "70", "ochenta": "80", "noventa": "90"
}

ALL_NUMBER_WORDS = {**NUMEROS_BAJOS, **NUMEROS_ALTOS}


def word_to_number(word: str) -> Optional[str]:
    """Convert Spanish number word to digit string."""
    word_lower = word.lower().strip()
    return ALL_NUMBER_WORDS.get(word_lower)


# ==================== PARSING FUNCTIONS ====================

def parse_suffix_or_letter_numero(via_part: str) -> Dict[str, Optional[str]]:
    """
    Parse the CRITICAL distinction between suffix and letra+numero.

    RULE:
    - "B uno" (letra + número bajo) → sufijo_via: "1"
    - "B doce" (letra + número alto) → letra_via: "B", numero: "12"
    - "BIS", "SUR", "NORTE" → sufijo_via: "BIS" / "SUR" / "NORTE"

    Args:
        via_part: Part after the main via number (e.g., "B uno", "B doce", "BIS")

    Returns:
        Dict with letra_via, sufijo_via, and/or numero fields
    """
    result = {
        "letra_via": None,
        "sufijo_via": None,
        "numero": None,
        "letra_numero": None
    }

    if not via_part:
        return result

    via_part = via_part.strip()

    # Special suffixes (BIS, SUR, NORTE, ESTE, OESTE)
    special_suffixes = ["BIS", "SUR", "NORTE", "ESTE", "OESTE"]
    for suffix in special_suffixes:
        if suffix in via_part.upper():
            result["sufijo_via"] = suffix
            # Remove the suffix and continue parsing
            via_part = re.sub(suffix, "", via_part, flags=re.IGNORECASE).strip()
            break

    # Pattern: Letter followed by number or number word
    # Examples: "B uno", "B 12", "B doce", "A 1", "C5"
    match = re.match(r"([A-Z])\s*(.+)", via_part, re.IGNORECASE)
    if match:
        letra = match.group(1).upper()
        numero_part = match.group(2).strip()

        # Try to parse the number part
        # Check if it's a word
        numero_value = word_to_number(numero_part)
        if not numero_value:
            # Try to extract digit
            digit_match = re.search(r"(\d+)", numero_part)
            if digit_match:
                numero_value = digit_match.group(1)

        if numero_value:
            numero_int = int(numero_value)

            # CRITICAL RULE: <= 10 → letra + sufijo, > 10 → letra + numero
            if numero_int <= 10:
                # "B uno" or "C5" pattern → LETRA + SUFFIX
                # Example: "26C5" → letra_via="C", sufijo_via="5"
                result["letra_via"] = letra
                result["sufijo_via"] = numero_value
            else:
                # "B doce" pattern → LETRA + NUMERO
                result["letra_via"] = letra
                result["numero"] = numero_value
        else:
            # Can't parse number, assume it's just a letter with no number
            result["letra_via"] = letra

    # Pattern: Just a single letter (no number after)
    elif re.match(r"^[A-Z]$", via_part, re.IGNORECASE):
        result["letra_via"] = via_part.upper()

    # Pattern: Just a number with no letter
    elif re.match(r"^\d+$", via_part):
        # This could be either numero or sufijo - need more context
        numero_int = int(via_part)
        if numero_int <= 10:
            result["sufijo_via"] = via_part
        else:
            result["numero"] = via_part

    # Pattern: Number followed by letter AND suffix (e.g., "42B1", "26C5", "77B1")
    # This is the MOST CRITICAL pattern for Colombian addresses
    # Example: "Calle 90 42B1" → numero="42", letra_numero="B", sufijo_numero="1"
    # Example: "Carrera 26C5" → letra_via="C", sufijo_via="5" (when part of via number)
    elif re.match(r"^(\d+)([A-Z])(\d+)\b", via_part, re.IGNORECASE):
        match = re.match(r"^(\d+)([A-Z])(\d+)\b", via_part, re.IGNORECASE)
        numero_value = match.group(1)
        letra_value = match.group(2).upper()
        sufijo_value = match.group(3)

        sufijo_int = int(sufijo_value)

        # CRITICAL RULE: If suffix is <= 10, treat as numero + letra + sufijo
        # Example: "42B1" → numero="42", letra_numero="B", sufijo_numero="1"
        if sufijo_int <= 10:
            result["numero"] = numero_value
            result["letra_numero"] = letra_value
            # Store suffix in a special field (we'll need to add this to the model)
            # For now, we'll concatenate it with letra_numero for compatibility
            # TODO: Add sufijo_numero field to DireccionParseada model
            result["letra_numero"] = f"{letra_value}{sufijo_value}"
        else:
            # If suffix is > 10, it might be a different pattern
            # For now, treat as numero + letra
            result["numero"] = numero_value
            result["letra_numero"] = letra_value

    # Pattern: Number followed by letter (e.g., "43B", "12A", "43B en Barranquilla")
    # This represents a cross street number with letter
    # Example: "Calle 90 43B" → numero="43", letra_numero="B"
    # Uses \b (word boundary) instead of $ to handle text after the letter
    elif re.match(r"^(\d+)([A-Z])\b", via_part, re.IGNORECASE):
        match = re.match(r"^(\d+)([A-Z])\b", via_part, re.IGNORECASE)
        numero_value = match.group(1)
        letra_value = match.group(2).upper()

        # Always treat "number + letter" as cross street (numero + letra_numero)
        result["numero"] = numero_value
        result["letra_numero"] = letra_value

    return result


@tool
def parse_colombian_address(texto: str) -> dict:
    """
    Parse Colombian address text into structured DireccionParseada format.

    This function implements the CRITICAL Colombian address parsing rules,
    especially the suffix distinction:
    - "B uno" → sufijo_via: "1"
    - "B doce" → letra_via: "B", numero: "12"

    Supported formats:
    - "Calle 43 B uno # 25 - 30"
    - "Carrera 50 B doce # 12 - 5, El Prado"
    - "Diagonal 72 BIS # 43 - 25"
    - "Transversal 42 # 50 - 20, Barrio Abajo, Barranquilla"

    Args:
        texto: Raw address text from user

    Returns:
        Dictionary representation of DireccionParseada with parsed components

    Examples:
        >>> parse_colombian_address("Calle 43 B uno # 25 - 30")
        {
            "via_tipo": "Calle",
            "via_numero": "43",
            "sufijo_via": "1",
            "numero_casa": "25",
            "placa_numero": "30",
            ...
        }

        >>> parse_colombian_address("Carrera 50 B doce # 12 - 5")
        {
            "via_tipo": "Carrera",
            "via_numero": "50",
            "letra_via": "B",
            "numero": "12",
            "numero_casa": "12",
            "placa_numero": "5",
            ...
        }
    """
    # Initialize result
    result = {
        "via_tipo": None,
        "via_numero": None,
        "letra_via": None,
        "sufijo_via": None,
        "numero": None,
        "letra_numero": None,
        "numero_casa": None,
        "letra_casa": None,
        "placa_numero": None,
        "barrio": None,
        "ciudad": None,
        "referencias": None,
        "validado": False,
    }

    if not texto or not texto.strip():
        return result

    texto = texto.strip()

    # CRITICAL FIX: Remove "número", "num", "nro" BEFORE parsing
    # This prevents "número" from being parsed as letra_via="N"
    # Example: "Calle 90 número 42" → "Calle 90 42"
    # IMPORTANT: DO NOT remove # here - we need it to split via/casa parts!
    texto = re.sub(r'\b(n[uú]mero?|num|nro|no\.?)\b\.?\s*', ' ', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s+', ' ', texto).strip()  # Normalize spaces

    # Step 1: Extract ciudad (usually at the end after comma)
    ciudad_match = re.search(r",\s*(barranquilla|soledad|puerto\s*colombia|galapa)", texto, re.IGNORECASE)
    if ciudad_match:
        result["ciudad"] = ciudad_match.group(1).strip().title()
        # Remove ciudad from text
        texto = texto[:ciudad_match.start()].strip()

    # Step 2: Extract barrio (usually after comma, before ciudad)
    # Pattern: ", [Barrio Name]"
    barrio_match = re.search(r",\s*([^,]+?)(?:,|$)", texto)
    if barrio_match:
        potential_barrio = barrio_match.group(1).strip()
        # Check it's not just a number or house number
        if not re.match(r"^\d+$", potential_barrio):
            result["barrio"] = potential_barrio
            # Remove barrio from text
            texto = texto[:barrio_match.start()].strip()

    # Step 3: Extract referencias (text in parentheses)
    ref_match = re.search(r"\(([^)]+)\)", texto)
    if ref_match:
        result["referencias"] = ref_match.group(1).strip()
        # Remove referencias from text
        texto = re.sub(r"\([^)]+\)", "", texto).strip()

    # Step 4: Parse main address structure
    # Pattern: [Via tipo] [Numero] [Letra/Sufijo opcional] # [Casa] - [Placa]

    # Extract via tipo (Calle, Carrera, Diagonal, Transversal, Avenida)
    via_tipos = ["Calle", "Carrera", "Diagonal", "Transversal", "Avenida"]
    via_match = None
    for via_tipo in via_tipos:
        match = re.search(rf"\b({via_tipo})\b", texto, re.IGNORECASE)
        if match:
            result["via_tipo"] = match.group(1).capitalize()
            via_match = match
            break

    if not via_match:
        # Try abbreviations: Cl, Cr, Dg, Tv, Av
        abbr_match = re.search(r"\b(Cl|Cr|Dg|Tv|Av|Kr)\.?\s*", texto, re.IGNORECASE)
        if abbr_match:
            abbr = abbr_match.group(1).upper()
            abbr_map = {"CL": "Calle", "CR": "Carrera", "KR": "Carrera",
                        "DG": "Diagonal", "TV": "Transversal", "AV": "Avenida"}
            result["via_tipo"] = abbr_map.get(abbr, "Calle")
            via_match = abbr_match

    if via_match:
        # Extract everything after via tipo up to # symbol
        after_via = texto[via_match.end():].strip()

        # Split by # to separate via part from casa part
        parts = after_via.split("#")
        via_part = parts[0].strip()

        # Parse via number (first number after via tipo)
        via_num_match = re.match(r"(\d+)", via_part)
        if via_num_match:
            result["via_numero"] = via_num_match.group(1)
            via_part = via_part[via_num_match.end():].strip()

            # Parse suffix or letra+numero
            suffix_result = parse_suffix_or_letter_numero(via_part)
            result.update(suffix_result)

        # Parse house number and placa (after #)
        if len(parts) > 1:
            casa_part = parts[1].strip()

            # IMPROVED: Parse casa_part similar to via_part for complex patterns
            # Supports: "42 E1", "49 C", "51 B - 120", "42B1-61", etc.

            # First, extract the main number
            casa_num_match = re.match(r"(\d+)", casa_part)
            if casa_num_match:
                # This is used as either numero_casa OR numero (cross street)
                # depending on whether we already have a numero from via_part
                main_num = casa_num_match.group(1)
                remaining = casa_part[casa_num_match.end():].strip()

                # Parse the remaining part for letter/suffix patterns
                casa_suffix_result = parse_suffix_or_letter_numero(remaining)

                # Determine if this is numero (cross street) or numero_casa (house number)
                # If we DON'T have numero yet, this is the cross street
                # If we DO have numero, this is the house number
                if not result.get("numero"):
                    # This is the cross street (e.g., "Calle 90 # 42B1", "Calle 95 # 49 C")
                    result["numero"] = main_num

                    # Apply letter from suffix result
                    if casa_suffix_result.get("letra_via"):
                        result["letra_numero"] = casa_suffix_result["letra_via"]
                    if casa_suffix_result.get("letra_numero"):
                        result["letra_numero"] = casa_suffix_result["letra_numero"]

                    # Check for placa - could be from suffix_result or from regex
                    placa = None
                    if casa_suffix_result.get("numero"):
                        # The suffix parser found a numero after the letter (e.g., "C - 30")
                        placa = casa_suffix_result["numero"]
                    else:
                        # Try regex match for placa
                        placa_match = re.search(r"-\s*(\d+)", remaining)
                        if placa_match:
                            placa = placa_match.group(1)

                    if placa:
                        result["placa_numero"] = placa
                else:
                    # We already have numero, so this is numero_casa
                    result["numero_casa"] = main_num

                    # Apply letter from suffix result
                    if casa_suffix_result.get("letra_via"):
                        result["letra_casa"] = casa_suffix_result["letra_via"]

                    # Check for placa
                    placa = None
                    if casa_suffix_result.get("numero"):
                        placa = casa_suffix_result["numero"]
                    else:
                        placa_match = re.search(r"-\s*(\d+)", remaining)
                        if placa_match:
                            placa = placa_match.group(1)

                    if placa:
                        result["placa_numero"] = placa

    return result


@tool
def format_direccion(
    via_tipo: Optional[str] = None,
    via_numero: Optional[str] = None,
    letra_via: Optional[str] = None,
    sufijo_via: Optional[str] = None,
    numero: Optional[str] = None,
    letra_numero: Optional[str] = None,
    numero_casa: Optional[str] = None,
    letra_casa: Optional[str] = None,
    placa_numero: Optional[str] = None,
    barrio: Optional[str] = None,
    ciudad: Optional[str] = None,
) -> str:
    """
    Format Colombian address components into a readable string.

    Args:
        via_tipo: Type of street (Calle, Carrera, etc.)
        via_numero: Main street number
        letra_via: Letter for street (only if numero > 10)
        sufijo_via: Suffix (only for "B uno" pattern or BIS)
        numero: Cross street number (only if > 10)
        letra_numero: Letter for cross street number
        numero_casa: House number
        letra_casa: Letter for house number
        placa_numero: Plate number
        barrio: Neighborhood
        ciudad: City

    Returns:
        Formatted address string

    Example:
        >>> format_direccion(via_tipo="Calle", via_numero="43", sufijo_via="1",
        ...                  numero_casa="25", placa_numero="30", barrio="El Prado")
        "Calle 43-1 #25-30, El Prado"
    """
    parts = []

    # Main street part
    if via_tipo and via_numero:
        street = f"{via_tipo} {via_numero}"

        # Add letra_via if present (for "B doce" pattern)
        if letra_via:
            street += letra_via

        # Add sufijo_via if present (for "B uno" pattern or "BIS")
        if sufijo_via:
            street += f"-{sufijo_via}"

        # Add cross street number
        if numero:
            if letra_numero:
                street += f" #{numero}{letra_numero}"  # Format: "90 #43B" not "90 B43"
            else:
                street += f" #{numero}"

        parts.append(street)

    # House number part
    if numero_casa:
        house = f"#{numero_casa}"
        if letra_casa:
            house = f"#{numero_casa}{letra_casa}"
        if placa_numero:
            house += f"-{placa_numero}"
        parts.append(house)

    # Neighborhood
    if barrio:
        parts.append(barrio)

    # City
    if ciudad:
        parts.append(ciudad)

    return ", ".join(parts) if parts else "Dirección no especificada"


# ==================== VALIDATION ====================

@tool
def validate_address_completeness(direccion_dict: dict) -> dict:
    """
    Validate if an address has all required components.

    Args:
        direccion_dict: Dictionary with address components

    Returns:
        Dictionary with validation result and missing fields
    """
    required_fields = ["via_tipo", "via_numero", "numero_casa"]
    recommended_fields = ["barrio", "placa_numero"]

    missing_required = [f for f in required_fields if not direccion_dict.get(f)]
    missing_recommended = [f for f in recommended_fields if not direccion_dict.get(f)]

    is_complete = len(missing_required) == 0
    is_optimal = is_complete and len(missing_recommended) == 0

    return {
        "is_complete": is_complete,
        "is_optimal": is_optimal,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "message": (
            "Dirección completa" if is_complete
            else f"Faltan campos requeridos: {', '.join(missing_required)}"
        )
    }


# ==================== NORMALIZATION FOR GEOCODING ====================

def normalize_direccion_for_geocoding(direccion_dict: dict) -> str:
    """
    Convert DireccionParseada to normalized format for geocoding API.

    This function formats the address and then normalizes it using AddressService,
    which converts it to the short format expected by the geocoding endpoint:
    - "Calle" → "cl"
    - "Carrera" → "cr"
    - Only keeps first 2 components (main street + cross street)

    Args:
        direccion_dict: Dictionary with DireccionParseada components

    Returns:
        Normalized address string (e.g., "cl 72 43")

    Example:
        >>> normalize_direccion_for_geocoding({
        ...     "via_tipo": "Calle",
        ...     "via_numero": "72",
        ...     "numero_casa": "43",
        ...     "placa_numero": "25",
        ...     "barrio": "El Prado"
        ... })
        "cl 72 43"
    """
    # First, format the complete address
    # format_direccion is a LangChain tool, so we need to use .func to call the underlying function
    format_func = format_direccion.func if hasattr(format_direccion, 'func') else format_direccion

    direccion_completa = format_func(
        via_tipo=direccion_dict.get("via_tipo"),
        via_numero=direccion_dict.get("via_numero"),
        letra_via=direccion_dict.get("letra_via"),
        sufijo_via=direccion_dict.get("sufijo_via"),
        numero=direccion_dict.get("numero"),
        letra_numero=direccion_dict.get("letra_numero"),
        numero_casa=direccion_dict.get("numero_casa"),
        letra_casa=direccion_dict.get("letra_casa"),
        placa_numero=direccion_dict.get("placa_numero"),
        barrio=direccion_dict.get("barrio"),
        ciudad=direccion_dict.get("ciudad"),
    )

    # Then normalize using AddressService (converts to "cr 53 106" format)
    direccion_normalizada = address_service.normalize(direccion_completa)

    return direccion_normalizada


# ==================== EXPORT ====================

__all__ = [
    "parse_colombian_address",
    "format_direccion",
    "validate_address_completeness",
    "parse_suffix_or_letter_numero",
    "normalize_direccion_for_geocoding",
]
