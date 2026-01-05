"""Backend dispatch tools for taxi requests."""

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from typing import Optional
import uuid
from datetime import datetime, timedelta
import random


# ==================== MOCK DISPATCH SIMULATION ====================

@tool
def dispatch_to_backend(config: RunnableConfig) -> str:
    """
    Dispatch taxi request to backend system.

    This is the FINAL action in the booking flow. It sends the complete
    taxi request to the backend dispatch system and returns a confirmation.

    In production, this would:
    1. Call the real taxi dispatch API
    2. Assign a driver from the fleet
    3. Send notifications to driver and customer
    4. Return tracking information

    For now, it returns a mock confirmation for testing.

    Args:
        config: Runtime configuration (contains state context)

    Returns:
        Confirmation message with service ID and ETA

    Example:
        "✅ Taxi solicitado exitosamente!
         ID de servicio: TXI-abc123
         Tiempo estimado de llegada: 8 minutos
         El conductor te contactará pronto."
    """
    # Generate mock service ID
    service_id = f"TXI-{uuid.uuid4().hex[:8]}"

    # Generate mock ETA (5-15 minutes)
    eta_minutes = random.randint(5, 15)
    eta_time = datetime.now() + timedelta(minutes=eta_minutes)

    # Mock driver info
    drivers = [
        {"nombre": "Carlos Pérez", "placa": "ABC-123", "modelo": "Toyota Corolla 2020"},
        {"nombre": "Ana Martínez", "placa": "DEF-456", "modelo": "Chevrolet Spark 2021"},
        {"nombre": "Luis Rodríguez", "placa": "GHI-789", "modelo": "Mazda 3 2019"},
        {"nombre": "María González", "placa": "JKL-012", "modelo": "Hyundai Accent 2022"},
    ]
    driver = random.choice(drivers)

    # Format confirmation message
    confirmation = f"""✅ ¡Taxi solicitado exitosamente!

🆔 ID de servicio: {service_id}
⏱️ Tiempo estimado de llegada: {eta_minutes} minutos (aprox. {eta_time.strftime("%H:%M")})

🚗 Conductor asignado:
   Nombre: {driver["nombre"]}
   Vehículo: {driver["modelo"]}
   Placa: {driver["placa"]}

📞 El conductor te contactará pronto.
💬 Puedes rastrear tu servicio en tiempo real desde la app.

¡Gracias por usar nuestro servicio!"""

    return confirmation


@tool
def cancel_service(service_id: str, reason: Optional[str] = None) -> str:
    """
    Cancel an existing taxi service.

    This tool would be used if the user wants to cancel a previously
    dispatched service.

    Args:
        service_id: Service ID to cancel (format: TXI-xxxxxxxx)
        reason: Optional cancellation reason

    Returns:
        Cancellation confirmation message
    """
    # In production, this would call the backend API to cancel the service
    # For now, return mock confirmation

    if not service_id.startswith("TXI-"):
        return "❌ ID de servicio inválido. El formato debe ser TXI-xxxxxxxx"

    message = f"""✅ Servicio cancelado exitosamente

🆔 ID: {service_id}
📅 Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M")}
"""

    if reason:
        message += f"📝 Motivo: {reason}\n"

    message += "\n💰 No se realizará ningún cobro."

    return message


@tool
def check_service_status(service_id: str) -> dict:
    """
    Check the status of a taxi service.

    Args:
        service_id: Service ID to check (format: TXI-xxxxxxxx)

    Returns:
        Dictionary with service status information
    """
    # In production, this would query the backend for real-time status
    # For now, return mock status

    if not service_id.startswith("TXI-"):
        return {"error": "ID de servicio inválido"}

    # Mock statuses
    statuses = [
        {
            "status": "BUSCANDO_CONDUCTOR",
            "message": "Buscando conductor disponible...",
            "progress": 25
        },
        {
            "status": "CONDUCTOR_ASIGNADO",
            "message": "Conductor asignado, en camino",
            "progress": 50
        },
        {
            "status": "EN_RUTA",
            "message": "Conductor a 3 minutos de tu ubicación",
            "progress": 75
        },
        {
            "status": "EN_SERVICIO",
            "message": "Servicio en curso",
            "progress": 90
        },
    ]

    status_info = random.choice(statuses)

    return {
        "service_id": service_id,
        "status": status_info["status"],
        "message": status_info["message"],
        "progress_percentage": status_info["progress"],
        "timestamp": datetime.now().isoformat(),
    }


@tool
def estimate_fare(
    origen_zona: str,
    destino_zona: str,
    metodo_pago: str = "EFECTIVO"
) -> dict:
    """
    Estimate fare for a taxi trip.

    Args:
        origen_zona: Origin zone (BARRANQUILLA, SOLEDAD, etc.)
        destino_zona: Destination zone
        metodo_pago: Payment method

    Returns:
        Dictionary with fare estimate
    """
    # Mock fare calculation based on zones
    base_fares = {
        ("BARRANQUILLA", "BARRANQUILLA"): {"min": 8000, "max": 15000},
        ("BARRANQUILLA", "SOLEDAD"): {"min": 15000, "max": 25000},
        ("BARRANQUILLA", "PUERTO_COLOMBIA"): {"min": 20000, "max": 35000},
        ("BARRANQUILLA", "GALAPA"): {"min": 18000, "max": 30000},
        ("SOLEDAD", "SOLEDAD"): {"min": 6000, "max": 12000},
        # Add more combinations as needed
    }

    route_key = (origen_zona, destino_zona)
    fare_range = base_fares.get(route_key, {"min": 10000, "max": 20000})

    # Calculate estimate (average of range)
    estimated_fare = (fare_range["min"] + fare_range["max"]) // 2

    # Add surcharge for non-cash payment
    if metodo_pago != "EFECTIVO":
        surcharge = int(estimated_fare * 0.05)  # 5% surcharge
        estimated_fare += surcharge
    else:
        surcharge = 0

    return {
        "origen": origen_zona,
        "destino": destino_zona,
        "metodo_pago": metodo_pago,
        "tarifa_base": fare_range["min"],
        "tarifa_maxima": fare_range["max"],
        "tarifa_estimada": estimated_fare,
        "recargo_pago": surcharge,
        "moneda": "COP",
        "nota": "Tarifa sujeta a tráfico y condiciones reales del viaje"
    }


# ==================== SERVICE QUERY & CANCELLATION TOOLS ====================

@tool
async def consultar_detalle_servicio_activo(config: RunnableConfig) -> str:
    """
    Consulta información detallada del servicio activo (conductor, placa, estado).

    Esta herramienta obtiene el nombre del conductor, placa del vehículo,
    y estado actual del servicio cuando el usuario pregunta información específica.

    Ejemplo de uso:
    Usuario: "¿Quién es el conductor?"
    → Usa esta herramienta
    → Responde: "Tu conductor es Carlos Pérez, placa ABC-123."

    Args:
        config: Runtime configuration (contains state context with service_id)

    Returns:
        Información detallada del servicio en formato conversacional
    """
    # Extraer state del config
    state = config.get("configurable", {}).get("state", {})

    id_servicio = state.get("id_servicio_activo")
    client_id = state.get("client_id")

    if not id_servicio:
        return "No se encontró información de servicio activo."

    # Consultar detalle del servicio
    from app.tools.customer_tools import consultar_servicio_detalle_impl

    result = await consultar_servicio_detalle_impl(id_servicio, client_id)

    # NUEVO: Detectar errores y backend caído
    if not result.get("success"):
        if result.get("backend_down"):
            # Backend caído - señal de transferencia
            return "TRANSFER_TO_HUMAN|Backend no disponible para consultar detalles del servicio"
        else:
            # Error HTTP u otro error - también transferir
            return "TRANSFER_TO_HUMAN|No se pudo obtener información del servicio"

    # Servicio encontrado exitosamente
    data = result.get("data", {})

    nombre_driver = data.get("NOMBRE_DRIVER", "N/A")
    placa_movil = data.get("PLACA_MOVIL", "N/A")
    estado_servicio = data.get("ESTADO_SERVICIO", "N/A")

    if nombre_driver == "NULL" or estado_servicio == "SERVICIO_NO_EXISTE":
        return "Lo siento, parece que ese servicio ya fue completado o cancelado. ¿Necesitas solicitar un nuevo taxi?"

    # Mapear estados técnicos a lenguaje natural
    estado_map = {
        "ASIGNADO": "asignado y en camino",
        "EN_RUTA": "en camino a tu ubicación",
        "LLEGADO": "ha llegado a tu ubicación",
        "EN_SERVICIO": "en curso",
        "COMPLETADO": "completado",
        "CANCELADO": "cancelado"
    }

    estado_natural = estado_map.get(estado_servicio, estado_servicio)

    return f"Tu conductor es {nombre_driver}, placa {placa_movil}. El servicio está {estado_natural}."


@tool
async def cancelar_servicio_activo(config: RunnableConfig) -> str:
    """
    Cancela el servicio activo del cliente.

    IMPORTANTE: Esta herramienta solo debe usarse después de confirmación explícita.
    Según la decisión del usuario, SIEMPRE debe confirmar antes de cancelar.

    Flujo correcto:
    1. Usuario: "Quiero cancelar"
    2. Alice: "Entiendo que quieres cancelar el taxi para [dirección]. ¿Es correcto?"
    3. Usuario: "Sí"
    4. → USA esta herramienta
    5. Alice: "Listo, he cancelado tu servicio."

    Args:
        config: Runtime configuration (contains state context with service_id)

    Returns:
        Confirmación de cancelación
    """
    # Extraer state del config
    state = config.get("configurable", {}).get("state", {})

    id_servicio = state.get("id_servicio_activo")

    if not id_servicio:
        return "No hay ningún servicio activo para cancelar."

    # Cancelar servicio
    from app.tools.customer_tools import cancelar_servicio_cliente_impl

    result = await cancelar_servicio_cliente_impl(id_servicio)

    # NUEVO: Detectar backend caído
    if not result.get("success"):
        if result.get("backend_down"):
            # Backend caído - señal de transferencia
            return "TRANSFER_TO_HUMAN|Backend no disponible para cancelar el servicio"
        else:
            # Otro error - mensaje normal
            return f"Lo siento, no pude cancelar el servicio. {result.get('message', 'Por favor intenta comunicarte con nosotros más tarde.')}"

    # Servicio cancelado exitosamente
    return f"Listo, he cancelado tu servicio. No se realizará ningún cobro."


# ==================== BACKEND INTEGRATION (PLACEHOLDER) ====================

class TaxiBackendAPI:
    """
    Placeholder class for future real backend integration.

    In production, this would:
    - Connect to the actual dispatch system API
    - Handle authentication and authorization
    - Send real-time updates via websockets
    - Integrate with payment gateways
    - Track driver GPS locations
    - etc.
    """

    def __init__(self, api_url: str, api_key: str):
        """
        Initialize backend API client.

        Args:
            api_url: Base URL for the dispatch API
            api_key: API authentication key
        """
        self.api_url = api_url
        self.api_key = api_key

    def dispatch_service(self, service_data: dict) -> dict:
        """
        Dispatch a new taxi service.

        Args:
            service_data: Complete service information

        Returns:
            Response from backend with service_id and ETA
        """
        # TODO: Implement real API call
        # Example:
        # response = requests.post(
        #     f"{self.api_url}/dispatch",
        #     headers={"Authorization": f"Bearer {self.api_key}"},
        #     json=service_data
        # )
        # return response.json()
        raise NotImplementedError("Real backend integration pending")

    def cancel_service(self, service_id: str) -> dict:
        """Cancel a service."""
        raise NotImplementedError("Real backend integration pending")

    def get_service_status(self, service_id: str) -> dict:
        """Get service status."""
        raise NotImplementedError("Real backend integration pending")


# ==================== EXPORT ====================

__all__ = [
    "dispatch_to_backend",
    "cancel_service",
    "check_service_status",
    "estimate_fare",
    "TaxiBackendAPI",
]
