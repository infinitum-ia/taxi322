"""Extended state model for sequential taxi booking flow."""

from typing import Annotated, Optional, Literal, TypedDict
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


# ==================== TOKEN TRACKING ====================

class TokenTracking(TypedDict, total=False):
    """Token tracking data for billing and analytics."""

    start_time: Optional[float]  # Unix timestamp of first message
    total_input_tokens: int  # Cumulative prompt tokens
    total_output_tokens: int  # Cumulative completion tokens
    dispatch_executed: bool  # DispatchToBackend was called
    tracking_saved: bool  # Prevents duplicate file writes


class DireccionParseada(BaseModel):
    """
    Structured address model for Colombian locations.

    This model captures the specific structure of Colombian addresses
    with special handling for suffixes and lettering conventions.

    CRITICAL RULE - Suffix Distinction:
    - "B uno" (B followed by single digit word) → sufijo_via: "1"
    - "B doce" (B followed by number > 9) → letra_via: "B", numero: "12"

    Examples:
    - "Calle 43 B uno # 25 - 30"
      → via_tipo: "Calle", via_numero: "43", sufijo_via: "1", numero_casa: "25", placa_numero: "30"

    - "Carrera 50 B doce # 12 - 5"
      → via_tipo: "Carrera", via_numero: "50", letra_via: "B", numero: "12", numero_casa: "12", placa_numero: "5"

    - "Diagonal 72 BIS # 43 - 25"
      → via_tipo: "Diagonal", via_numero: "72", sufijo_via: "BIS", numero_casa: "43", placa_numero: "25"
    """

    via_tipo: Optional[Literal["Calle", "Carrera", "Diagonal", "Transversal", "Avenida"]] = Field(
        default=None,
        description="Type of street/avenue (Calle, Carrera, etc.)"
    )

    via_numero: Optional[str] = Field(
        default=None,
        description="Main street number (e.g., '43', '100')"
    )

    letra_via: Optional[str] = Field(
        default=None,
        description="Letter designation for street (A, B, C, etc.). Only used when number follows."
    )

    sufijo_via: Optional[str] = Field(
        default=None,
        description=(
            "Suffix for street (BIS, 1, 2, 3, etc.). "
            "CRITICAL: 'B uno' → sufijo_via='1', NOT letra_via='B'"
        )
    )

    numero: Optional[str] = Field(
        default=None,
        description=(
            "Cross street number. "
            "CRITICAL: 'B doce' → letra_via='B', numero='12' (separate fields)"
        )
    )

    letra_numero: Optional[str] = Field(
        default=None,
        description="Letter designation for cross street number"
    )

    numero_casa: Optional[str] = Field(
        default=None,
        description="House/building number (after # symbol)"
    )

    letra_casa: Optional[str] = Field(
        default=None,
        description="Letter designation for house number"
    )

    placa_numero: Optional[str] = Field(
        default=None,
        description="Plate number (after - symbol)"
    )

    barrio: Optional[str] = Field(
        default=None,
        description="Neighborhood name (e.g., 'El Prado', 'Centro', 'Riomar')"
    )

    ciudad: Optional[str] = Field(
        default=None,
        description="City name (Barranquilla, Soledad, Puerto Colombia, Galapa)"
    )

    referencias: Optional[str] = Field(
        default=None,
        description="Additional references (e.g., 'Frente al banco', 'Al lado del parque')"
    )

    validado: bool = Field(
        default=False,
        description="Whether this address has been validated by the user"
    )

    def to_formatted_string(self) -> str:
        """
        Convert to human-readable Colombian address format.

        Returns formatted string like:
        "Calle 43B #25-30, El Prado, Barranquilla"
        """
        parts = []

        # Main street part
        if self.via_tipo and self.via_numero:
            street = f"{self.via_tipo} {self.via_numero}"

            # Add letra_via if present (for "B doce" pattern)
            if self.letra_via:
                street += self.letra_via

            # Add sufijo_via if present (for "B uno" pattern or "BIS")
            if self.sufijo_via:
                street += self.sufijo_via

            # Add cross street number
            if self.numero:
                if self.letra_numero:
                    street += f" {self.letra_numero}{self.numero}"
                else:
                    street += f" #{self.numero}"

            parts.append(street)

        # House number part (#25-30)
        if self.numero_casa:
            house = f"#{self.numero_casa}"
            if self.letra_casa:
                house = f"#{self.numero_casa}{self.letra_casa}"
            if self.placa_numero:
                house += f"-{self.placa_numero}"
            parts.append(house)

        # Neighborhood
        if self.barrio:
            parts.append(self.barrio)

        # City
        if self.ciudad:
            parts.append(self.ciudad)

        # References
        if self.referencias:
            parts.append(f"({self.referencias})")

        return ", ".join(parts) if parts else "Dirección no especificada"

    def is_complete(self) -> bool:
        """
        Check if the address has minimum required information.

        Returns:
            True if address has at least via_tipo, via_numero, and barrio/ciudad
        """
        has_street = self.via_tipo and self.via_numero
        has_location = self.barrio or self.ciudad
        return bool(has_street and has_location)


class CustomerInfo(BaseModel):
    """
    Structured output model for customer information extraction from NAVEGANTE.

    This model is used to reliably extract customer name and confirmed address
    from the conversation.
    """

    nombre_cliente: str = Field(
        default="",
        description=(
            "Nombre completo del cliente mencionado en la conversación. "
            "Extrae el nombre cuando el usuario responde a la pregunta '¿A nombre de quién?'. "
            "Si no se mencionó ningún nombre, deja vacío."
        )
    )

    direccion_confirmada: str = Field(
        default="",
        description=(
            "Dirección completa confirmada por el usuario. "
            "Extrae la dirección EXACTA que el asistente le repitió al usuario para confirmar. "
            "Ejemplo: 'Calle 72 número 43-25, El Prado'"
        )
    )


class VehicleDetails(BaseModel):
    """
    Structured output model for vehicle details extraction from OPERADOR.

    This model is used for structured output from the LLM to ensure
    reliable extraction of payment method and vehicle characteristics.
    """

    metodo_pago: Literal["EFECTIVO", "NEQUI", "DAVIPLATA", "DATAFONO"] = Field(
        description="Método de pago del cliente"
    )

    caracteristicas: list[str] = Field(
        default_factory=list,
        description=(
            "Lista de características del vehículo solicitadas. "
            "Valores válidos: parrilla, carga, baul grande, corporativo, "
            "camioneta chery, camioneta turbo doble cabina, estaca, zapatico, "
            "portabicicleta, amplio"
        )
    )

    observacion: str = Field(
        default="",
        description=(
            "Observación operacional para el conductor en tercera persona. "
            "Incluye detalles importantes como destino, mascota, silla de bebé, etc."
        )
    )


def update_detalles_vehiculo(left: list[str] | None, right: list[str] | None) -> list[str]:
    """
    Reducer for detalles_vehiculo field.

    Accumulates vehicle detail requirements (append-only).

    Args:
        left: Current list of vehicle details
        right: New vehicle details to add

    Returns:
        Combined list with deduplication
    """
    if right is None:
        return left or []

    current = left or []

    # Add new items that aren't already present (deduplication)
    for item in right:
        if item not in current:
            current.append(item)

    return current


class TaxiState(TypedDict, total=False):
    """
    Extended state for sequential taxi booking workflow.

    This state tracks the complete journey through 4 specialized agents:
    1. Recepcionista - Intent classification
    2. Navegante - Address parsing and zone validation
    3. Operador - Payment and vehicle details
    4. Confirmador - Final confirmation and dispatch

    The state accumulates information as the user progresses through the flow,
    with support for backtracking if corrections are needed.
    """

    # ==================== CORE MESSAGING ====================

    messages: Annotated[list[AnyMessage], add_messages]

    # ==================== CUSTOMER INFORMATION ====================

    client_id: Optional[str]  # Phone number or customer ID

    nombre_cliente: Optional[str]  # Customer name

    tiene_servicio_previo: bool  # Whether customer has previous services

    direccion_previa: Optional[str]  # Last address used by customer

    usa_direccion_previa: Optional[bool]  # Whether customer wants to use previous address

    cliente_consultado: bool  # CACHE FLAG: Whether backend was already consulted for customer info

    # ==================== ACTIVE SERVICE INFORMATION ====================
    # Información del servicio activo del cliente (si existe)

    tiene_servicio_activo: bool  # Flag que indica si el cliente tiene un servicio activo (NOSERVICIOS != "TRUE")

    id_servicio_activo: Optional[str]  # ID del servicio activo (ej: "17148220") extraído de ID_SERVICIO

    direccion_servicio_activo: Optional[str]  # Dirección del servicio activo (DIRECCION_CLIENTE o UBICACION_ACTUAL)

    servicios_activos_multiples: bool  # Flag cuando MASDEUNO="TRUE" - Cliente tiene múltiples servicios activos

    # ==================== SERVICE DETAIL (consulted on demand) ====================
    # Estos campos se llenan SOLO cuando el usuario pregunta por el servicio

    nombre_conductor: Optional[str]  # Nombre del conductor asignado (de /consultar-servicio-detalle)

    placa_vehiculo: Optional[str]  # Placa del vehículo asignado (de /consultar-servicio-detalle)

    estado_servicio: Optional[str]  # Estado del servicio: EN_RUTA, ASIGNADO, etc. (de /consultar-servicio-detalle)

    servicio_detalle_consultado: bool  # CACHE FLAG: Previene consultas duplicadas del detalle

    # ==================== TAXI-SPECIFIC FIELDS ====================

    intencion: Optional[Literal[
        "SOLICITAR_TAXI",
        "SOLICITAR_TAXI_CARGA",  # For moving/cargo services
        "CANCELAR",
        "QUEJA",
        "CONSULTA",
        "OTRO"
    ]]

    direccion_parseada: Optional[DireccionParseada]

    zona_validada: Optional[Literal[
        "BARRANQUILLA",
        "SOLEDAD",
        "PUERTO_COLOMBIA",
        "GALAPA",
        "RECHAZADO"  # Out of service coverage
    ]]

    # NOTA IMPORTANTE - FLUJO DE CAPTURA Y ENVÍO:
    # 1. Durante la conversación:
    #    - metodo_pago: Se captura el método de pago (EFECTIVO, NEQUI, DAVIPLATA, DATAFONO)
    #    - detalles_vehiculo: Se capturan TODAS las características del vehículo (parrilla, carga, baul grande, etc.)
    #
    # 2. Al hacer dispatch al backend:
    #    - Se combinan metodo_pago + detalles_vehiculo en un solo string usando combine_tipo_vehiculo_params()
    #    - Este string combinado se envía como tipo_vehiculo al backend
    #    - Ejemplo: metodo_pago="NEQUI" + detalles_vehiculo=["parrilla", "carga"] → tipo_vehiculo="nequi, parrilla, carga"

    tipo_vehiculo: Optional[Literal[
        "amplio",
        "baul grande",
        "corporativo",
        "datafono",
        "camioneta chery",
        "carga",
        "portabicicleta",
        "parrilla",
        "camioneta turbo doble cabina",
        "estaca",
        "zapatico",
        "nequi",
        "daviplata"
    ]]  # DEPRECATED: Este campo ya no se usa directamente, se genera dinámicamente al hacer dispatch

    detalles_vehiculo: Annotated[list[str], update_detalles_vehiculo]  # Lista de características del vehículo

    metodo_pago: Optional[Literal["EFECTIVO", "NEQUI", "DAVIPLATA", "DATAFONO"]]  # Método de pago del cliente

    observacion_final: Optional[str]

    # ==================== GEOCODING (INTERNAL USE) ====================
    # These coordinates are NOT shown to the user, only sent to backend on dispatch

    latitud: Optional[float]  # Latitude coordinate for pickup location

    longitud: Optional[float]  # Longitude coordinate for pickup location

    coordenadas_consultadas: bool  # CACHE FLAG: Whether geocoding API was already consulted (prevents duplicate calls)

    # ==================== FLOW CONTROL ====================
    # CRITICAL: No default value - this allows the router to detect new conversations

    agente_actual: Optional[Literal[
        "RECEPCIONISTA",
        "NAVEGANTE",
        "OPERADOR",
        "CONFIRMADOR",
        "END"
    ]]

    # ==================== HUMAN TRANSFER ====================
    # Set to True when the conversation needs to be transferred to a human agent

    transfer_to_human: bool  # Flag indicating conversation should be transferred to human
    transfer_reason: Optional[str]  # Reason for the transfer (e.g., "No coordinates obtained")

    # ==================== BACKTRACKING SUPPORT ====================

    requires_correction: bool

    correction_target: Optional[Literal["NAVEGANTE", "OPERADOR"]]

    # ==================== DEBUGGING & METADATA ====================

    debug_info: dict

    # ==================== TOKEN TRACKING ====================

    token_tracking: Optional[TokenTracking]


# ==================== HELPER FUNCTIONS ====================

def get_completion_status(state: TaxiState) -> dict:
    """
    Get the current completion status of the booking.

    Args:
        state: Current taxi state

    Returns:
        Dict with completion status of each stage
    """
    return {
        "intencion_clasificada": state.get("intencion") is not None,
        "direccion_completa": (
            state.get("direccion_parseada") is not None
            and state.get("direccion_parseada").is_complete()
        ),
        "zona_validada": state.get("zona_validada") is not None,
        "detalles_capturados": (
            state.get("metodo_pago") is not None
            and state.get("observacion_final") is not None
        ),
        "listo_para_confirmar": all([
            state.get("intencion") in ["SOLICITAR_TAXI", "SOLICITAR_TAXI_CARGA"],
            state.get("direccion_parseada") is not None,
            state.get("zona_validada") not in [None, "RECHAZADO"],
            state.get("metodo_pago") is not None,
            state.get("observacion_final") is not None,
        ])
    }


def should_backtrack(state: TaxiState) -> bool:
    """
    Check if the state indicates a backtracking request.

    Args:
        state: Current taxi state

    Returns:
        True if requires_correction is set and has a valid correction_target
    """
    return (
        state.get("requires_correction", False)
        and state.get("correction_target") is not None
    )


def combine_tipo_vehiculo_params(state: TaxiState) -> str:
    """
    Combina el método de pago y las características del vehículo en un solo string
    para enviar al backend como tipo_vehiculo.

    El backend acepta tipo_vehiculo como un campo único, por lo que esta función
    combina todos los parámetros capturados durante la conversación.

    Args:
        state: Current taxi state

    Returns:
        String combinado con todos los parámetros (ej: "nequi, parrilla, carga")

    Examples:
        - metodo_pago="NEQUI", detalles_vehiculo=["parrilla", "carga"]
          → "nequi, parrilla, carga"
        - metodo_pago="EFECTIVO", detalles_vehiculo=["baul grande"]
          → "baul grande"
        - metodo_pago="DAVIPLATA", detalles_vehiculo=[]
          → "daviplata"
    """
    params = []

    # Agregar método de pago si no es efectivo (efectivo es default)
    metodo_pago = state.get("metodo_pago")
    if metodo_pago and metodo_pago != "EFECTIVO":
        params.append(metodo_pago.lower())

    # Agregar todas las características del vehículo
    detalles_vehiculo = state.get("detalles_vehiculo", [])
    if detalles_vehiculo:
        params.extend(detalles_vehiculo)

    # Si solo es efectivo sin características especiales, usar "amplio" como default
    if not params:
        return "amplio"

    # Combinar todos los parámetros con comas
    return ", ".join(params)


def get_summary(state: TaxiState) -> str:
    """
    Get a human-readable summary of the current booking state.

    Args:
        state: Current taxi state

    Returns:
        Formatted summary string
    """
    parts = []

    if state.get("intencion"):
        parts.append(f"Intención: {state.get('intencion')}")

    if state.get("direccion_parseada"):
        parts.append(f"Dirección: {state.get('direccion_parseada').to_formatted_string()}")

    if state.get("zona_validada"):
        parts.append(f"Zona: {state.get('zona_validada')}")

    if state.get("metodo_pago"):
        parts.append(f"Pago: {state.get('metodo_pago')}")

    if state.get("detalles_vehiculo"):
        parts.append(f"Detalles: {', '.join(state.get('detalles_vehiculo'))}")

    if state.get("observacion_final"):
        parts.append(f"Observación: {state.get('observacion_final')}")

    return "\n".join(parts) if parts else "Estado vacío"
