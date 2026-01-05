"""Routing tools for sequential taxi booking flow."""

from pydantic import BaseModel, Field
from typing import Literal


# ==================== FORWARD TRANSFER TOOLS ====================

class TransferToNavegante(BaseModel):
    """
    Transfer control from Recepcionista to Navegante (address specialist).

    This tool is called by the Recepcionista after classifying the user's
    intent as SOLICITAR_TAXI or SOLICITAR_TAXI_CARGA.

    The Navegante will take over to parse and validate the address.
    """

    summary: str = Field(
        description=(
            "Brief summary of what the user wants for the Navegante. "
            "Example: 'Usuario solicita taxi en Calle 72 a El Prado'"
        )
    )


class TransferToOperador(BaseModel):
    """
    Transfer control from Navegante to Operador (logistics specialist).

    This tool is called by the Navegante after successfully parsing
    and validating the address and zone.

    The Operador will take over to collect payment method and vehicle details.
    """

    summary: str = Field(
        description=(
            "Brief summary of the validated address for the Operador. "
            "Example: 'Dirección validada: Calle 72 #43-25, El Prado, Barranquilla'"
        )
    )


class TransferToConfirmador(BaseModel):
    """
    Transfer control from Operador to Confirmador (final confirmation).

    This tool is called by the Operador after collecting payment method,
    vehicle details, and generating the driver observation.

    The Confirmador will present a summary and get final user confirmation.
    """

    ready_for_confirmation: bool = Field(
        default=True,
        description="Indicates all details are ready for confirmation"
    )


# ==================== BACKTRACKING TOOLS ====================

class BacktrackToNavegante(BaseModel):
    """
    Backtrack from Confirmador to Navegante to fix address issues.

    This tool is ONLY available to the Confirmador agent and is used
    when the user wants to change or correct the address during final
    confirmation.

    Example: User says "No, la dirección es otra" during confirmation.
    """

    correction_request: str = Field(
        description=(
            "What the user wants to change about the address. "
            "Example: 'Usuario dice que la dirección está mal, quiere cambiarla'"
        )
    )


class BacktrackToOperador(BaseModel):
    """
    Backtrack from Confirmador to Operador to fix payment or vehicle details.

    This tool is ONLY available to the Confirmador agent and is used
    when the user wants to change payment method or vehicle requirements
    during final confirmation.

    Example: User says "Mejor pago en efectivo" during confirmation.
    """

    correction_request: str = Field(
        description=(
            "What the user wants to change. "
            "Example: 'Usuario quiere cambiar de NEQUI a EFECTIVO'"
        )
    )


# ==================== FINAL ACTION TOOLS ====================

class DispatchToBackend(BaseModel):
    """
    Final action: Dispatch the taxi request to the backend system.

    This tool is ONLY available to the Confirmador agent and is called
    after the user explicitly confirms all details are correct.

    This triggers the actual taxi dispatch and ENDS the conversation flow.

    Usage:
    - Only call after explicit user confirmation ("sí", "correcto", "ok")
    - This is the TERMINAL action - no further agent transfers after this
    """

    confirmed_by_user: bool = Field(
        default=True,
        description="User has explicitly confirmed the booking details"
    )

    urgent: bool = Field(
        default=False,
        description="Whether this is an urgent/priority request"
    )


class TransferToHuman(BaseModel):
    """
    Transfer the conversation to a human agent.

    This tool is available to the Confirmador agent and is called when:
    - Geocoding fails (no coordinates obtained)
    - Address cannot be validated or found
    - User explicitly requests to speak with a human
    - System cannot proceed with automatic dispatch

    This ENDS the automated conversation flow and marks the conversation
    for human agent intervention.

    Usage:
    - Explain to the user that they will be connected to a human agent
    - Provide a reason for the transfer
    - This is a TERMINAL action - no further automated agent processing
    """

    reason: str = Field(
        description=(
            "Reason for transferring to human agent. "
            "Example: 'No se pudieron obtener coordenadas de la dirección' or "
            "'Usuario solicitó hablar con un agente'"
        )
    )

    user_notified: bool = Field(
        default=True,
        description="User has been notified about the transfer to human agent"
    )


# ==================== HELPER MODELS ====================

class AgentTransition(BaseModel):
    """
    Metadata about agent transitions for debugging and logging.

    Not used as a tool - just for internal tracking.
    """

    from_agent: Literal["RECEPCIONISTA", "NAVEGANTE", "OPERADOR", "CONFIRMADOR"]
    to_agent: Literal["NAVEGANTE", "OPERADOR", "CONFIRMADOR", "END"]
    transition_type: Literal["forward", "backtrack"]
    reason: str


# ==================== EXPORT ====================

__all__ = [
    # Forward transfers
    "TransferToNavegante",
    "TransferToOperador",
    "TransferToConfirmador",

    # Backtracking
    "BacktrackToNavegante",
    "BacktrackToOperador",

    # Final actions
    "DispatchToBackend",
    "TransferToHuman",

    # Helper
    "AgentTransition",
]
