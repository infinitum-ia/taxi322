"""Sequential taxi booking graph with 4 specialized agents."""

import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.models.taxi_state import TaxiState
from app.core.llm import get_llm
from app.agents.base import clean_messages_for_llm
from app.prompts.taxi_prompts import (
    RECEPCIONISTA_PROMPT,
    NAVEGANTE_PROMPT,
    OPERADOR_PROMPT,
    CONFIRMADOR_PROMPT,
)
from app.models.taxi_routing import (
    TransferToNavegante,
    TransferToOperador,
    TransferToConfirmador,
    BacktrackToNavegante,
    BacktrackToOperador,
    DispatchToBackend,
    TransferToHuman,
)
from app.tools.zone_tools import validate_zone, get_zone_info
from app.tools.address_tools import (
    parse_colombian_address,
    format_direccion,
    validate_address_completeness,
    normalize_direccion_for_geocoding,
)
from app.tools.dispatch_tools import dispatch_to_backend, cancel_service, check_service_status, estimate_fare
from app.tools.customer_tools import (
    obtener_direccion_cliente,
    consultar_cliente,
    registrar_servicio,
    consultar_coordenadas_gpt_impl,
)

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ==================== HELPER FUNCTIONS ====================

async def dispatch_servicio_completo(state: TaxiState) -> dict:
    """
    Helper function to dispatch complete service to backend.

    This function should be called when DispatchToBackend is triggered
    by the Confirmador after user confirmation.

    It sends all collected information including:
    - Client ID
    - Customer name
    - Complete address (formatted)
    - Coordinates (lat/lng) - automatically obtained
    - Zone
    - Vehicle type (includes payment method and characteristics)
    - Driver observation
    - Additional fields (to be added in the future)

    Args:
        state: Current TaxiState with all collected information

    Returns:
        Dictionary with dispatch result
    """
    import asyncio

    client_id = state.get("client_id")
    nombre_cliente = state.get("nombre_cliente")
    direccion_parseada = state.get("direccion_parseada")
    zona_validada = state.get("zona_validada")
    tipo_vehiculo = state.get("tipo_vehiculo")
    observacion_final = state.get("observacion_final")
    latitud = state.get("latitud")
    longitud = state.get("longitud")

    # Format complete address
    if hasattr(direccion_parseada, 'to_formatted_string'):
        ubicacion_actual = direccion_parseada.to_formatted_string()
    elif hasattr(direccion_parseada, 'model_dump'):
        from app.tools.address_tools import format_direccion
        ubicacion_actual = format_direccion(**direccion_parseada.model_dump())
    else:
        ubicacion_actual = str(direccion_parseada)

    logger.info("📤 Despachando servicio al backend...")
    logger.info(f"   Cliente: {client_id}")
    logger.info(f"   Nombre: {nombre_cliente}")
    logger.info(f"   Dirección: {ubicacion_actual}")
    logger.info(f"   Coordenadas: ({latitud}, {longitud})")
    logger.info(f"   Zona: {zona_validada}")
    logger.info(f"   Tipo de vehículo: {tipo_vehiculo}")
    logger.info(f"   Observación: {observacion_final}")

    # Call backend registration
    from app.tools.customer_tools import registrar_servicio_impl
    from app.models.taxi_state import combine_tipo_vehiculo_params

    # Combinar método de pago + características del vehículo en un solo string para el backend
    tipo_vehiculo_combinado = combine_tipo_vehiculo_params(state)

    logger.info(f"   Tipo de vehículo combinado: {tipo_vehiculo_combinado}")

    try:
        result = await registrar_servicio_impl(
            client_id=client_id,
            ubicacion_actual=ubicacion_actual,
            tipo_vehiculo=tipo_vehiculo_combinado,  # Enviar parámetros combinados
            observacion=observacion_final,
            latitud=latitud,
            longitud=longitud,
            zona=zona_validada,
            nombre_cliente=nombre_cliente
        )

        if result.get("success"):
            logger.info(f"✅ Servicio registrado exitosamente: {result.get('service_id')}")
        else:
            logger.error(f"❌ Error registrando servicio: {result.get('message')}")

        return result

    except Exception as e:
        logger.error(f"❌ Error en dispatch: {str(e)}")
        return {
            "success": False,
            "message": f"Error al despachar servicio: {str(e)}"
        }


# ==================== ROUTER NODE ====================

def router_node(state: TaxiState) -> dict:
    """
    Router node that determines which agent should handle the next message.

    This is the entry point for all messages. It checks the current agent
    state to determine where to route.
    """
    agente_actual = state.get("agente_actual")

    logger.info(f"🔀 ROUTER: agente_actual = {agente_actual}")

    # No need to return messages, just pass through
    # The routing logic will be in route_from_router
    return {}


def route_from_router(state: TaxiState) -> str:
    """
    Determine which agent should handle the message based on current state.

    - If no agente_actual → Go to recepcionista (new conversation)
    - If agente_actual is set → Go to that agent (continue conversation)
    """
    agente_actual = state.get("agente_actual")

    if not agente_actual:
        logger.info("  → Routing to recepcionista (new conversation)")
        return "recepcionista"

    # Continue with the current agent
    logger.info(f"  → Routing to {agente_actual.lower()} (continuing)")

    # Map agente_actual to node name
    agent_map = {
        "RECEPCIONISTA": "recepcionista",
        "NAVEGANTE": "navegante",
        "OPERADOR": "operador",
        "CONFIRMADOR": "confirmador",
    }

    return agent_map.get(agente_actual, "recepcionista")


# ==================== AGENT NODE FUNCTIONS ====================

async def recepcionista_node(state: TaxiState) -> dict:
    """Recepcionista: Intent classification and initial data extraction."""
    logger.info(" RECEPCIONISTA: Clasificando intención")

    # CRITICAL: Check if we need to lookup customer address FIRST
    # This happens BEFORE invoking the LLM to ensure the information is available
    direccion_previa = state.get("direccion_previa")
    client_id = state.get("client_id")
    cliente_consultado = state.get("cliente_consultado", False)

    logger.info(f"  → DEBUG: direccion_previa = {direccion_previa}, client_id = {client_id}, cliente_consultado = {cliente_consultado}")

    # CACHE OPTIMIZATION: Only consult backend ONCE per thread
    # If we haven't checked for previous address yet and we have a client_id
    # direccion_previa can be None, False, or empty string - check all cases
    if not cliente_consultado and client_id:
        logger.info("  → Consultando dirección del cliente ANTES de invocar LLM...")

        try:
            # Import and invoke the tool directly
            from app.tools.customer_tools import obtener_direccion_cliente_completa

            # Call the helper function directly (async)
            result_data = await obtener_direccion_cliente_completa(client_id)

            logger.info(f"  → Resultado de consulta: {result_data}")

            # NUEVO: Verificar si backend está caído
            if result_data.get("backend_down"):
                logger.error("Backend de 322 caído al consultar cliente - Transferencia requerida")

                # Informar al usuario
                from langchain_core.messages import AIMessage
                user_msg = AIMessage(
                    content="Disculpa, estoy teniendo problemas para acceder al sistema. Voy a conectarte con un asesor que te ayudará."
                )

                return {
                    "messages": [user_msg],
                    "agente_actual": "END",
                    "transfer_to_human": True,
                    "transfer_reason": "Backend no disponible para consultar información del cliente",
                    "cliente_consultado": True,  # Marcar como consultado para evitar reintentos
                    "token_tracking": state.get("token_tracking")
                }


            # Update state with the results
            state["direccion_previa"] = result_data.get("last_address") or ""
            state["tiene_servicio_previo"] = result_data.get("has_previous_service", False)
            state["cliente_consultado"] = True  # CACHE: Mark as consulted to prevent future queries

            # NUEVO: Extraer información de servicios activos
            state["tiene_servicio_activo"] = result_data.get("tiene_servicio_activo", False)
            state["id_servicio_activo"] = result_data.get("id_servicio_activo")
            state["direccion_servicio_activo"] = result_data.get("direccion_servicio_activo")
            state["servicios_activos_multiples"] = result_data.get("servicios_activos_multiples", False)
            state["servicio_detalle_consultado"] = False

            # NUEVO: CASO: Múltiples servicios activos - Transferir a humano inmediatamente
            if result_data.get("servicios_activos_multiples"):
                logger.warning("Cliente con múltiples servicios activos - Transferencia a humano requerida")

                # Agregar mensaje del sistema informando al LLM
                from langchain_core.messages import SystemMessage
                transfer_msg = SystemMessage(
                    content="""[ALERTA DEL SISTEMA]
El cliente tiene MÚLTIPLES SERVICIOS ACTIVOS.

ACCIÓN REQUERIDA:
- Informa al usuario: "Veo que tienes más de un servicio activo. Voy a conectarte con un asesor que te ayudará con esto."
- USA la herramienta TransferToHuman con razón: "Cliente con múltiples servicios activos"
- NO intentes manejar la solicitud tú mismo

Este caso requiere intervención humana."""
                )
                state["messages"].append(transfer_msg)


            # Add a system message to inform the LLM about the lookup result
            from langchain_core.messages import SystemMessage

            # Decidir qué mensaje del sistema enviar basándose en la situación
            if result_data.get("tiene_servicio_activo"):
                # Cliente tiene servicio ACTIVO
                direccion_activa = result_data.get("direccion_servicio_activo", "dirección no especificada")
                tiene_multiples = result_data.get("servicios_activos_multiples", False)

                lookup_msg = SystemMessage(
                    content=f"""[INFORMACIÓN DEL SISTEMA - INVISIBLE PARA EL USUARIO]
Has consultado y encontraste que el cliente TIENE UN SERVICIO ACTIVO:

SERVICIO ACTIVO:
- ID del servicio: {result_data.get("id_servicio_activo")}
- Dirección de recogida: {direccion_activa}
- {"⚠️ Tiene MÚLTIPLES servicios activos" if tiene_multiples else "Solo un servicio activo"}

IMPORTANTE PARA CONSULTAS:
- Si pregunta por su taxi, ya tienes la información básica (ID y dirección)
- Si pregunta info detallada (conductor, placa), usa la herramienta consultar_detalle_servicio_activo
- NUNCA digas "voy a consultar" - responde directamente con la información

IMPORTANTE PARA CANCELACIONES:
- Si quiere cancelar, PRIMERO confirma: "¿Quieres cancelar el taxi para {direccion_activa}?"
- Solo después de confirmación explícita, usa cancelar_servicio_activo
- NUNCA canceles sin confirmar

SERVICIOS PREVIOS:
- Tiene servicios previos: {result_data.get("has_previous_service")}
- Última dirección usada: {result_data.get("last_address")}

NUNCA menciones que "consultaste el sistema" - actúa naturalmente."""
                )
            elif result_data.get("has_previous_service"):
                # Cliente SIN servicio activo pero con historial
                lookup_msg = SystemMessage(
                    content=f"""[INFORMACIÓN DEL SISTEMA - INVISIBLE PARA EL USUARIO]
Cliente consultado:
- NO tiene servicios activos actualmente
- Tiene servicios previos
- Última dirección: {result_data.get("last_address")}

IMPORTANTE - Diferencia entre PREGUNTAR y SOLICITAR:
- Si PREGUNTA "¿Dónde está mi taxi?" → Responde: "No tienes servicios activos. ¿Necesitas solicitar uno?"
- Si SOLICITA "Necesito un taxi" → NO menciones servicios activos. Pregunta directo: "¿De dónde saldrías?" o "¿Quieres que te recojamos en {result_data.get("last_address")}?"

NUNCA menciones que consultaste el sistema."""
                )
            else:
                # Cliente nuevo
                lookup_msg = SystemMessage(
                    content="""[INFORMACIÓN DEL SISTEMA - INVISIBLE PARA EL USUARIO]
Cliente nuevo sin servicios previos ni servicios activos.

IMPORTANTE - Diferencia entre PREGUNTAR y SOLICITAR:
- Si PREGUNTA "¿Dónde está mi taxi?" → Responde: "No tienes servicios activos. ¿Necesitas solicitar uno?"
- Si SOLICITA "Necesito un taxi" → NO menciones servicios activos. Pregunta directo y cotidiano: "¿De dónde saldrías?" o "¿Cuál es tu dirección de recogida?"

Sé cotidiano pero profesional."""
                )

            # Add the system message to state messages
            if "messages" not in state:
                state["messages"] = []
            state["messages"].append(lookup_msg)

            logger.info(f"  → State actualizado: direccion_previa = {state.get('direccion_previa')}, cliente_consultado = True")

        except Exception as e:
            logger.error(f"  ⚠️ Error consultando dirección del cliente: {str(e)}")
            # Continue without previous address info
            state["direccion_previa"] = ""
            state["tiene_servicio_previo"] = False

    from app.tools.dispatch_tools import consultar_detalle_servicio_activo, cancelar_servicio_activo

    llm = get_llm()
    tools = [
        TransferToNavegante,
        consultar_detalle_servicio_activo,
        cancelar_servicio_activo,
        TransferToHuman,  # NUEVO: Agregar herramienta de transferencia a humano
    ]
    runnable = RECEPCIONISTA_PROMPT | llm.bind_tools(tools)

    # Clean messages before invoking LLM to prevent orphaned ToolMessage errors
    cleaned_state = state.copy()
    if "messages" in cleaned_state:
        cleaned_state["messages"] = clean_messages_for_llm(cleaned_state["messages"])

    result = runnable.invoke(cleaned_state)

    # ====== TOKEN TRACKING ======
    from app.agents.taxi.token_interceptor import intercept_llm_call
    state = intercept_llm_call(result, state)

    # Check if the recepcionista wants to transfer to navegante
    agente_actual = "RECEPCIONISTA"

    # Method 1: Explicit tool call
    if hasattr(result, "tool_calls") and result.tool_calls:
        tool_name = result.tool_calls[0]["name"]
        if tool_name == "TransferToNavegante":
            agente_actual = "NAVEGANTE"
            logger.info("  → agente_actual actualizado a NAVEGANTE (tool call)")

        # NUEVO: Manejo de consulta de detalle del servicio
        elif tool_name == "consultar_detalle_servicio_activo":
            logger.info("  → Consultando detalle del servicio activo...")

            tool_config = {"configurable": {"state": state}}

            try:
                # Ejecutar la tool de forma async
                detalle_info = await consultar_detalle_servicio_activo.ainvoke({}, config=tool_config)

                # Marcar que ya consultamos el detalle (cache)
                state["servicio_detalle_consultado"] = True

                logger.info(f"  ✅ Detalle del servicio obtenido: {detalle_info}")

                # Agregar el resultado como ToolMessage para que el LLM lo vea
                from langchain_core.messages import ToolMessage
                tool_msg = ToolMessage(
                    content=detalle_info,
                    tool_call_id=result.tool_calls[0]["id"]
                )

                # Reinvocar el LLM con la información obtenida
                cleaned_state_with_tool = cleaned_state.copy()
                cleaned_state_with_tool["messages"] = cleaned_state.get("messages", []) + [result, tool_msg]

                # El LLM generará la respuesta final con la información del servicio
                final_result = runnable.invoke(cleaned_state_with_tool)
                result = final_result

                # El agente permanece en RECEPCIONISTA
                agente_actual = "RECEPCIONISTA"

            except Exception as e:
                logger.error(f"  ❌ Error consultando detalle de servicio: {str(e)}")
                agente_actual = "RECEPCIONISTA"

        # NUEVO: Manejo de cancelación de servicio
        elif tool_name == "cancelar_servicio_activo":
            logger.info("  → Cancelando servicio activo...")

            tool_config = {"configurable": {"state": state}}

            try:
                # Ejecutar la tool de forma async
                cancelacion_result = await cancelar_servicio_activo.ainvoke({}, config=tool_config)

                # Limpiar información de servicio activo en state
                state["tiene_servicio_activo"] = False
                state["id_servicio_activo"] = None
                state["direccion_servicio_activo"] = None

                logger.info(f"  ✅ Servicio cancelado exitosamente: {cancelacion_result}")

                # Agregar el resultado como ToolMessage
                from langchain_core.messages import ToolMessage
                tool_msg = ToolMessage(
                    content=cancelacion_result,
                    tool_call_id=result.tool_calls[0]["id"]
                )

                # Reinvocar el LLM para generar confirmación final
                cleaned_state_with_tool = cleaned_state.copy()
                cleaned_state_with_tool["messages"] = cleaned_state.get("messages", []) + [result, tool_msg]

                final_result = runnable.invoke(cleaned_state_with_tool)
                result = final_result

                agente_actual = "RECEPCIONISTA"

            except Exception as e:
                logger.error(f"  ❌ Error cancelando servicio: {str(e)}")
                agente_actual = "RECEPCIONISTA"

        # NUEVO: Manejo de TransferToHuman
        elif tool_name == "TransferToHuman":
            tool_args = result.tool_calls[0].get("args", {})
            logger.warning(f"⚠️  TRANSFERENCIA A HUMANO: {tool_args.get('reason', 'Sin razón especificada')}")
            return {
                "messages": [result],
                "agente_actual": "END",
                "transfer_to_human": True,
                "transfer_reason": tool_args.get("reason", "Usuario requiere asistencia humana"),
                "token_tracking": state.get("token_tracking")
            }

    # Method 2: Detect if asking for address (fallback if LLM doesn't use tool)
    elif hasattr(result, "content") and result.content:
        content_lower = result.content.lower()
        # If asking for location/address, transfer to Navegante
        if any(keyword in content_lower for keyword in [
            "dónde", "donde", "dirección", "direccion",
            "ubicación", "ubicacion", "lugar", "salir"
        ]):
            agente_actual = "NAVEGANTE"
            logger.info("  → agente_actual actualizado a NAVEGANTE (detección automática)")

    # NUEVO: Detectar señal de transferencia a humano en los mensajes ToolMessage
    # Esto ocurre cuando consultar_detalle_servicio_activo o cancelar_servicio_activo retornan la señal
    if "messages" in state:
        for msg in reversed(state["messages"][-5:]):  # Revisar últimos 5 mensajes
            if hasattr(msg, "content") and isinstance(msg.content, str):
                if msg.content.startswith("TRANSFER_TO_HUMAN|"):
                    reason = msg.content.split("|", 1)[1]
                    logger.warning(f"⚠️  Transferencia detectada desde tool: {reason}")

                    # Informar al usuario antes de transferir
                    from langchain_core.messages import AIMessage
                    user_msg = AIMessage(
                        content="Disculpa, necesito conectarte con un asesor para ayudarte con esto. Un momento por favor."
                    )

                    return {
                        "messages": [user_msg],
                        "agente_actual": "END",
                        "transfer_to_human": True,
                        "transfer_reason": reason,
                        "token_tracking": state.get("token_tracking")
                    }

    updates = {
        "messages": [result],
        "agente_actual": agente_actual,
        "token_tracking": state.get("token_tracking")
    }

    # Preserve the address lookup results if they were set
    if "direccion_previa" in state:
        updates["direccion_previa"] = state.get("direccion_previa")
    if "tiene_servicio_previo" in state:
        updates["tiene_servicio_previo"] = state.get("tiene_servicio_previo")
    if "cliente_consultado" in state:
        updates["cliente_consultado"] = state.get("cliente_consultado")

    # NUEVO: Preservar información de servicios activos
    if "tiene_servicio_activo" in state:
        updates["tiene_servicio_activo"] = state.get("tiene_servicio_activo")
    if "id_servicio_activo" in state:
        updates["id_servicio_activo"] = state.get("id_servicio_activo")
    if "direccion_servicio_activo" in state:
        updates["direccion_servicio_activo"] = state.get("direccion_servicio_activo")
    if "servicios_activos_multiples" in state:
        updates["servicios_activos_multiples"] = state.get("servicios_activos_multiples")
    if "servicio_detalle_consultado" in state:
        updates["servicio_detalle_consultado"] = state.get("servicio_detalle_consultado")

    return updates


async def navegante_node(state: TaxiState) -> dict:
    """Navegante: Conversational address capture (voice optimized)."""
    logger.info("🗺️ NAVEGANTE: Capturando dirección por voz")

    # CRITICAL: Check if we need to lookup customer address FIRST
    # This happens BEFORE invoking the LLM to ensure the information is available
    direccion_previa = state.get("direccion_previa")
    client_id = state.get("client_id")
    cliente_consultado = state.get("cliente_consultado", False)

    logger.info(f"  → DEBUG: direccion_previa = {direccion_previa}, client_id = {client_id}, cliente_consultado = {cliente_consultado}")

    # CACHE OPTIMIZATION: Only consult backend ONCE per thread
    # If we haven't checked for previous address yet and we have a client_id
    # direccion_previa can be None, False, or empty string - check all cases
    if not cliente_consultado and client_id:
        logger.info("  → Consultando dirección del cliente ANTES de invocar LLM...")

        try:
            # Import and invoke the tool directly
            from app.tools.customer_tools import obtener_direccion_cliente_completa

            # Call the helper function directly (async)
            result_data = await obtener_direccion_cliente_completa(client_id)

            logger.info(f"  → Resultado de consulta: {result_data}")

            # Update state with the results
            state["direccion_previa"] = result_data.get("last_address") or ""
            state["tiene_servicio_previo"] = result_data.get("has_previous_service", False)
            state["cliente_consultado"] = True  # CACHE: Mark as consulted to prevent future queries

            # Add a system message to inform the LLM about the lookup result
            from langchain_core.messages import SystemMessage

            if result_data.get("last_address"):
                lookup_msg = SystemMessage(
                    content=f"""[INFORMACIÓN DEL SISTEMA - INVISIBLE PARA EL USUARIO]
Has consultado la dirección del cliente y encontraste:
- Dirección registrada: {result_data.get("last_address")}
- Tiene servicios previos: {result_data.get("has_previous_service")}

AHORA debes:
1. Preguntarle al usuario si quiere usar esta dirección
2. Si dice SÍ → confirmar y avanzar
3. Si dice NO → pedir nueva dirección

NUNCA menciones que consultaste el sistema - actúa naturalmente."""
                )
            else:
                lookup_msg = SystemMessage(
                    content="""[INFORMACIÓN DEL SISTEMA - INVISIBLE PARA EL USUARIO]
Has consultado la dirección del cliente pero NO tiene dirección registrada.

AHORA debes:
1. Pedir la dirección normalmente
2. Continuar con el flujo estándar

NUNCA menciones que consultaste el sistema - actúa naturalmente."""
                )

            # Add the system message to state messages
            if "messages" not in state:
                state["messages"] = []
            state["messages"].append(lookup_msg)

            logger.info(f"  → State actualizado: direccion_previa = {state.get('direccion_previa')}, cliente_consultado = True")

        except Exception as e:
            logger.error(f"  ⚠️ Error consultando dirección del cliente: {str(e)}")
            # Continue without previous address info
            state["direccion_previa"] = ""
            state["tiene_servicio_previo"] = False
            state["cliente_consultado"] = True  # CACHE: Mark as consulted even if error to prevent retry

    llm = get_llm()
    # Include customer lookup tools along with transfer tool
    tools = [
        TransferToOperador,
        obtener_direccion_cliente,  # Tool principal para obtener dirección del cliente
    ]
    runnable = NAVEGANTE_PROMPT | llm.bind_tools(tools)

    # Clean messages before invoking LLM to prevent orphaned ToolMessage errors
    cleaned_state = state.copy()
    if "messages" in cleaned_state:
        cleaned_state["messages"] = clean_messages_for_llm(cleaned_state["messages"])

    result = runnable.invoke(cleaned_state)

    # ====== TOKEN TRACKING ======
    from app.agents.taxi.token_interceptor import intercept_llm_call
    state = intercept_llm_call(result, state)

    # Check if navegante wants to transfer to operador
    agente_actual = "NAVEGANTE"
    updates = {
        "messages": [result],
        "agente_actual": agente_actual,
        "token_tracking": state.get("token_tracking")
    }

    # Preserve the address lookup results if they were set
    if "direccion_previa" in state:
        updates["direccion_previa"] = state.get("direccion_previa")
    if "tiene_servicio_previo" in state:
        updates["tiene_servicio_previo"] = state.get("tiene_servicio_previo")
    if "cliente_consultado" in state:
        updates["cliente_consultado"] = state.get("cliente_consultado")

    # Method 1: Explicit tool call to TransferToOperador
    if hasattr(result, "tool_calls") and result.tool_calls:
        tool_name = result.tool_calls[0]["name"]
        if tool_name == "TransferToOperador":
            # Mark that the next message should go to Operador
            updates["agente_actual"] = "OPERADOR"
            logger.info("  → agente_actual actualizado a OPERADOR (tool call)")

    # Method 2: Automatic transfer detection (fallback)
    # If the LLM asks about payment method but forgot to use TransferToOperador
    elif hasattr(result, "content") and result.content:
        content_lower = result.content.lower()
        payment_keywords = [
            "cómo prefieres pagar", "como prefieres pagar",
            "método de pago", "metodo de pago",
            "forma de pago", "pagar el viaje",
            "efectivo, nequi", "nequi, daviplata"
        ]
        if any(keyword in content_lower for keyword in payment_keywords):
            updates["agente_actual"] = "OPERADOR"
            logger.warning("  ⚠️  NAVEGANTE preguntó por pago pero NO usó TransferToOperador - transferencia automática activada")

    # ==================== AUTO-PARSE ADDRESS AND NAME BEFORE TRANSFER ====================
    # If transferring to OPERADOR, extract and parse address and name from conversation
    if updates.get("agente_actual") == "OPERADOR":
        # ==================== EXTRACT CUSTOMER INFO WITH STRUCTURED OUTPUT ====================
        logger.info("  → Extrayendo dirección y nombre del cliente usando Structured Output...")

        from app.models.taxi_state import CustomerInfo
        from langchain_core.prompts import ChatPromptTemplate

        # Create extraction prompt
        customer_extraction_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """Eres un extractor de información. Analiza la conversación y extrae:

1. **nombre_cliente**: El nombre completo del cliente
   - Busca cuando el asistente pregunta "¿A nombre de quién?" o similar
   - El usuario responde con su nombre (puede ser solo nombre o nombre completo)
   - También puede aparecer cuando el asistente dice "Gracias [nombre]" o "Perfecto [nombre]"
   - Si no se menciona ningún nombre, deja vacío

2. **direccion_confirmada**: La dirección que el asistente confirmó con el usuario
   - Busca frases como "¿la dirección es [dirección]?" o "Entiendo, ¿la dirección es [dirección]?"
   - Extrae SOLO la dirección confirmada, no otras direcciones mencionadas
   - Ejemplo: "Calle 72 número 43-25, El Prado"
   - Si no hay dirección confirmada, deja vacío

IMPORTANTE: Solo extrae información que REALMENTE aparezca en la conversación.
"""
            ),
            ("placeholder", "{messages}"),
        ])

        # Configure LLM with structured output
        customer_extraction_llm = get_llm().with_structured_output(CustomerInfo)
        customer_extraction_chain = customer_extraction_prompt | customer_extraction_llm

        # Clean messages for extraction
        cleaned_state_customer = state.copy()
        if "messages" in cleaned_state_customer:
            cleaned_state_customer["messages"] = clean_messages_for_llm(cleaned_state_customer["messages"])

        try:
            # Extract customer info
            customer_info: CustomerInfo = customer_extraction_chain.invoke(cleaned_state_customer)

            logger.info(f"  ✅ Customer Info extraída exitosamente:")
            logger.info(f"     nombre_cliente: {customer_info.nombre_cliente}")
            logger.info(f"     direccion_confirmada: {customer_info.direccion_confirmada}")

            # Update state with extracted name
            if customer_info.nombre_cliente:
                updates["nombre_cliente"] = customer_info.nombre_cliente
            else:
                logger.warning("  ⚠️  No se encontró nombre del cliente en la conversación")

            # Parse the confirmed address if found
            if customer_info.direccion_confirmada:
                direccion_texto = customer_info.direccion_confirmada
                logger.info(f"  → Parseando dirección confirmada: {direccion_texto}")

                try:
                    # Import the underlying function, not the LangChain tool
                    from app.tools.address_tools import parse_colombian_address

                    # Call the underlying function directly
                    if hasattr(parse_colombian_address, 'func'):
                        parsed_result = parse_colombian_address.func(texto=direccion_texto)
                    else:
                        parsed_result = parse_colombian_address(texto=direccion_texto)

                    # Convert to DireccionParseada model
                    from app.models.taxi_state import DireccionParseada
                    direccion_parseada = DireccionParseada(**parsed_result)

                    updates["direccion_parseada"] = direccion_parseada
                    logger.info(f"  ✅ Dirección parseada exitosamente: {direccion_parseada.to_formatted_string()}")

                except Exception as e:
                    logger.error(f"  ⚠️  Error parseando dirección: {str(e)}")
                    import traceback
                    logger.error(f"  ⚠️  Traceback: {traceback.format_exc()}")
            else:
                logger.warning("  ⚠️  No se encontró dirección confirmada en la conversación")

        except Exception as e:
            logger.error(f"  ❌ Error en structured output de customer info: {str(e)}")
            import traceback
            logger.error(f"  Traceback: {traceback.format_exc()}")
            logger.warning("  ⚠️  Continuando sin información del cliente")

    return updates


def operador_node(state: TaxiState) -> dict:
    """Operador: Payment method, vehicle details, and driver observation."""
    logger.info("🚗 OPERADOR: Capturando detalles logísticos")

    # ==================== GEOCODING: Obtain coordinates BEFORE LLM invocation ====================
    # This happens automatically and is INVISIBLE to the user
    # Coordinates are stored in state for backend dispatch

    direccion_parseada = state.get("direccion_parseada")
    client_id = state.get("client_id")
    coordenadas_consultadas = state.get("coordenadas_consultadas", False)

    # DEBUG: Log state values to diagnose geocoding issues
    logger.info(f"  → DEBUG: direccion_parseada = {direccion_parseada}")
    logger.info(f"  → DEBUG: client_id = {client_id}")
    logger.info(f"  → DEBUG: latitud actual = {state.get('latitud')}")
    logger.info(f"  → DEBUG: coordenadas_consultadas = {coordenadas_consultadas}")

    # CACHE OPTIMIZATION: Only geocode ONCE per conversation
    # Only geocode if we have an address and haven't consulted yet
    if direccion_parseada and client_id and not coordenadas_consultadas:
        logger.info("  → Obteniendo coordenadas de la dirección (invisible para el usuario)...")

        try:
            # Convert DireccionParseada to dict if it's a Pydantic model
            if hasattr(direccion_parseada, 'model_dump'):
                direccion_dict = direccion_parseada.model_dump()
            elif hasattr(direccion_parseada, 'dict'):
                direccion_dict = direccion_parseada.dict()
            else:
                direccion_dict = direccion_parseada

            # FIX: Si numero_casa es None pero barrio contiene números, intenta extraerlos
            if not direccion_dict.get("numero_casa") and direccion_dict.get("barrio"):
                import re
                barrio_text = direccion_dict.get("barrio", "")
                # Pattern: "número 112-1" o "numero 112-1" o solo "112-1"
                match = re.search(r'(?:número|numero)?\s*(\d+)(?:\s*-\s*(\d+))?', barrio_text, re.IGNORECASE)
                if match:
                    direccion_dict["numero_casa"] = match.group(1)
                    if match.group(2):
                        direccion_dict["placa_numero"] = match.group(2)
                    # Clear barrio since it was a misparsed house number
                    direccion_dict["barrio"] = None
                    logger.info(f"  → FIX: Extraído numero_casa={match.group(1)}, placa_numero={match.group(2)} desde barrio")

            # Normalize address for geocoding API
            direccion_normalizada = normalize_direccion_for_geocoding(direccion_dict)
            logger.info(f"  → Dirección normalizada: {direccion_normalizada}")

            # Call geocoding API
            import asyncio

            try:
                # Try to get existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, create a task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        coordenadas_result = pool.submit(
                            lambda: asyncio.run(consultar_coordenadas_gpt_impl(client_id, direccion_normalizada))
                        ).result()
                else:
                    coordenadas_result = loop.run_until_complete(
                        consultar_coordenadas_gpt_impl(client_id, direccion_normalizada)
                    )
            except RuntimeError:
                # No event loop, create a new one
                coordenadas_result = asyncio.run(
                    consultar_coordenadas_gpt_impl(client_id, direccion_normalizada)
                )

            if coordenadas_result.get("success"):
                # Extract coordinates from response
                data = coordenadas_result.get("data", {})

                # Try multiple field name variations (lowercase and UPPERCASE)
                latitud = (data.get("latitud") or data.get("lat") or
                          data.get("LATITUD") or data.get("LAT"))
                longitud = (data.get("longitud") or data.get("lng") or data.get("lon") or
                           data.get("LONGITUD") or data.get("LNG") or data.get("LON"))

                # Check if LISTA_DIRECCIONES has results
                lista_direcciones = data.get("LISTA_DIRECCIONES", "[]")
                if isinstance(lista_direcciones, str):
                    import json
                    try:
                        lista_direcciones = json.loads(lista_direcciones)
                    except:
                        lista_direcciones = []

                # If we have a list with results, use the first one
                if isinstance(lista_direcciones, list) and len(lista_direcciones) > 0:
                    primera_direccion = lista_direcciones[0]
                    logger.info(f"  → LISTA_DIRECCIONES tiene {len(lista_direcciones)} resultado(s), usando el primero")
                    logger.info(f"  → Primera dirección: {primera_direccion}")

                    # Extract coordinates from first result
                    latitud = (primera_direccion.get("latitud") or primera_direccion.get("lat") or
                              primera_direccion.get("LATITUD") or primera_direccion.get("LAT") or latitud)
                    longitud = (primera_direccion.get("longitud") or primera_direccion.get("lng") or
                               primera_direccion.get("LONGITUD") or primera_direccion.get("LNG") or longitud)

                # Filter out NULL strings
                if latitud in ["NULL", "null", None, ""]:
                    latitud = None
                if longitud in ["NULL", "null", None, ""]:
                    longitud = None

                if latitud and longitud:
                    # Store in state (NOT shown to user)
                    state["latitud"] = float(latitud)
                    state["longitud"] = float(longitud)
                    state["coordenadas_consultadas"] = True  # ✅ CACHE: Mark as consulted
                    logger.info(f"  ✅ Coordenadas obtenidas: lat={latitud}, lng={longitud}")
                else:
                    logger.warning(f"  ⚠️  Respuesta no contiene coordenadas válidas")
                    logger.warning(f"  ⚠️  LATITUD={latitud}, LONGITUD={longitud}")
                    logger.warning(f"  ⚠️  LISTA_DIRECCIONES tiene {len(lista_direcciones) if isinstance(lista_direcciones, list) else 0} resultados")
                    state["coordenadas_consultadas"] = True  # ✅ CACHE: Mark as consulted even if failed
            else:
                logger.warning(f"  ⚠️  Error obteniendo coordenadas: {coordenadas_result.get('message')}")
                state["coordenadas_consultadas"] = True  # ✅ CACHE: Mark as consulted even if error

        except Exception as e:
            logger.error(f"  ⚠️  Error en geocodificación: {str(e)}")
            import traceback
            logger.error(f"  ⚠️  Traceback completo:\n{traceback.format_exc()}")
            state["coordenadas_consultadas"] = True  # ✅ CACHE: Mark as consulted even if exception
            # Continue without coordinates - dispatch will handle this gracefully

    # ==================== LLM INVOCATION ====================

    llm = get_llm()
    tools = [TransferToConfirmador, estimate_fare]
    runnable = OPERADOR_PROMPT | llm.bind_tools(tools)

    # Clean messages before invoking LLM to prevent orphaned ToolMessage errors
    cleaned_state = state.copy()
    if "messages" in cleaned_state:
        cleaned_state["messages"] = clean_messages_for_llm(cleaned_state["messages"])

    result = runnable.invoke(cleaned_state)

    # ====== TOKEN TRACKING ======
    from app.agents.taxi.token_interceptor import intercept_llm_call
    state = intercept_llm_call(result, state)

    # Check if operador wants to transfer to confirmador
    agente_actual = "OPERADOR"
    if hasattr(result, "tool_calls") and result.tool_calls:
        tool_name = result.tool_calls[0]["name"]
        if tool_name == "TransferToConfirmador":
            # Mark that the next message should go to Confirmador
            agente_actual = "CONFIRMADOR"
            logger.info("  → agente_actual actualizado a CONFIRMADOR")

    # Prepare updates
    updates = {
        "messages": [result],
        "agente_actual": agente_actual,
        "token_tracking": state.get("token_tracking")
    }

    # Include coordinates if they were obtained
    if "latitud" in state and state.get("latitud"):
        updates["latitud"] = state.get("latitud")
        updates["longitud"] = state.get("longitud")

    # Preserve geocoding cache flag
    if "coordenadas_consultadas" in state:
        updates["coordenadas_consultadas"] = state.get("coordenadas_consultadas")

    # ==================== EXTRACT VEHICLE DETAILS WITH STRUCTURED OUTPUT ====================
    if agente_actual == "CONFIRMADOR":
        logger.info("  → Extrayendo detalles del vehículo usando Structured Output...")

        # Use a second LLM call with structured output to extract vehicle details
        from app.models.taxi_state import VehicleDetails
        from langchain_core.prompts import ChatPromptTemplate

        # Create extraction prompt
        extraction_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """Eres un extractor de información. Analiza la conversación y extrae:

1. **metodo_pago**: El método de pago mencionado por el usuario
   - Valores válidos: EFECTIVO, NEQUI, DAVIPLATA, DATAFONO
   - Si el usuario dice "tarjeta", es DATAFONO
   - Si no menciona nada, usa EFECTIVO como default

2. **caracteristicas**: TODAS las características del vehículo mencionadas (puede ser una lista)
   - Ejemplos: ["parrilla"], ["parrilla", "carga"], ["camioneta turbo doble cabina"]
   - Valores válidos: parrilla, carga, baul grande, corporativo, camioneta chery,
     camioneta turbo doble cabina, estaca, zapatico, portabicicleta, amplio
   - Si el usuario dice "camión turbo" o "turbo", usa "camioneta turbo doble cabina"
   - Si dice "mudanza" o "trasteo", agrega "carga"
   - Si dice "maletas" o "equipaje", agrega "baul grande"
   - Si no menciona características especiales, deja la lista vacía

3. **observacion**: Nota para el conductor en tercera persona sobre detalles importantes
   - Ejemplo: "Cliente va al aeropuerto", "Lleva mascota", "Requiere silla de bebé"
   - Si no hay información adicional, usa cadena vacía

IMPORTANTE: Solo extrae lo que el usuario REALMENTE mencionó en la conversación.
"""
            ),
            ("placeholder", "{messages}"),
        ])

        # Configure LLM with structured output
        extraction_llm = get_llm().with_structured_output(VehicleDetails)
        extraction_chain = extraction_prompt | extraction_llm

        # Clean messages for extraction
        cleaned_state = state.copy()
        if "messages" in cleaned_state:
            cleaned_state["messages"] = clean_messages_for_llm(cleaned_state["messages"])

        try:
            # Extract vehicle details
            vehicle_details: VehicleDetails = extraction_chain.invoke(cleaned_state)

            logger.info(f"  ✅ Structured Output extraído exitosamente:")
            logger.info(f"     metodo_pago: {vehicle_details.metodo_pago}")
            logger.info(f"     caracteristicas: {vehicle_details.caracteristicas}")
            logger.info(f"     observacion: {vehicle_details.observacion}")

            # Update state with extracted data
            updates["metodo_pago"] = vehicle_details.metodo_pago
            updates["detalles_vehiculo"] = vehicle_details.caracteristicas
            updates["observacion_final"] = vehicle_details.observacion

            # Generar vista previa de tipo_vehiculo combinado (solo para logging)
            from app.models.taxi_state import combine_tipo_vehiculo_params
            preview_state = state.copy()
            preview_state["metodo_pago"] = vehicle_details.metodo_pago
            preview_state["detalles_vehiculo"] = vehicle_details.caracteristicas
            tipo_vehiculo_preview = combine_tipo_vehiculo_params(preview_state)
            logger.info(f"  📋 tipo_vehiculo combinado: {tipo_vehiculo_preview}")

        except Exception as e:
            logger.error(f"  ❌ Error en structured output: {str(e)}")
            import traceback
            logger.error(f"  Traceback: {traceback.format_exc()}")

            # Fallback to defaults
            updates["metodo_pago"] = "EFECTIVO"
            updates["detalles_vehiculo"] = []
            updates["observacion_final"] = ""
            logger.warning("  ⚠️  Usando valores por defecto debido al error")

    return updates


async def confirmador_node(state: TaxiState) -> dict:
    """Confirmador: Final confirmation and dispatch."""
    logger.info("✅ CONFIRMADOR: Confirmación final")

    # Check if coordinates are missing (handle None, empty strings, 0, etc.)
    latitud = state.get("latitud")
    longitud = state.get("longitud")

    # Coordinates are valid only if they are numbers (not None, not empty, not 0)
    tiene_coordenadas = (
        latitud is not None and
        latitud != '' and
        latitud != 0 and
        longitud is not None and
        longitud != '' and
        longitud != 0
    )

    logger.info(f"  → DEBUG: latitud={latitud}, longitud={longitud}")
    logger.info(f"  → Coordenadas válidas: {tiene_coordenadas}")

    # Prepare state with explicit system message about coordinates
    from langchain_core.messages import SystemMessage

    llm = get_llm()
    # Include TransferToHuman tool for cases where coordinates are missing
    tools = [BacktrackToNavegante, BacktrackToOperador, DispatchToBackend, TransferToHuman]
    runnable = CONFIRMADOR_PROMPT | llm.bind_tools(tools)

    # Clean messages before invoking LLM to prevent orphaned ToolMessage errors
    cleaned_state = state.copy()
    if "messages" in cleaned_state:
        cleaned_state["messages"] = clean_messages_for_llm(cleaned_state["messages"])

    # Add system message about coordinates availability
    if not tiene_coordenadas:
        coord_warning = SystemMessage(
            content="[ALERTA DEL SISTEMA - INVISIBLE PARA EL USUARIO]\n"
                   "NO SE OBTUVIERON COORDENADAS GPS de la dirección.\n"
                   "Latitud y Longitud están vacías o son NULL.\n\n"
                   "ACCIÓN REQUERIDA:\n"
                   "USA INMEDIATAMENTE TransferToHuman con la razón: 'No se pudieron obtener coordenadas GPS de la dirección'\n"
                   "NO generes ningún mensaje de texto - SOLO usa el tool.\n"
                   "NO uses DispatchToBackend - la transferencia a humano es OBLIGATORIA."
        )
        cleaned_state["messages"] = list(cleaned_state.get("messages", [])) + [coord_warning]
        logger.warning("  ⚠️  COORDENADAS FALTANTES - Mensaje de sistema agregado para CONFIRMADOR")

    result = runnable.invoke(cleaned_state)

    # ====== TOKEN TRACKING ======
    from app.agents.taxi.token_interceptor import intercept_llm_call
    state = intercept_llm_call(result, state)

    # Check for backtracking, dispatch, or human transfer
    agente_actual = "CONFIRMADOR"
    transfer_to_human = state.get("transfer_to_human", False)
    transfer_reason = state.get("transfer_reason")

    if hasattr(result, "tool_calls") and result.tool_calls:
        tool_name = result.tool_calls[0]["name"]
        tool_args = result.tool_calls[0].get("args", {})

        if tool_name == "BacktrackToNavegante":
            agente_actual = "NAVEGANTE"
            logger.info("  → agente_actual actualizado a NAVEGANTE (backtrack)")
        elif tool_name == "BacktrackToOperador":
            agente_actual = "OPERADOR"
            logger.info("  → agente_actual actualizado a OPERADOR (backtrack)")
        elif tool_name == "TransferToHuman":
            # Transfer to human agent
            transfer_to_human = True
            transfer_reason = tool_args.get("reason", "Usuario requiere asistencia humana")
            agente_actual = "END"
            logger.info(f"  → 🙋 TRANSFERENCIA A HUMANO: {transfer_reason}")
        elif tool_name == "DispatchToBackend":
            # Keep as CONFIRMADOR - will end after this
            logger.info("  → Servicio despachado - iniciando registro en backend")

            # ====== MARK DISPATCH EXECUTED ======
            if state.get("token_tracking"):
                state["token_tracking"]["dispatch_executed"] = True
                logger.debug(" Dispatch executed - tracking marked")

            # ====== CALL BACKEND REGISTRATION ======
            try:
                dispatch_result = await dispatch_servicio_completo(state)
                if dispatch_result.get("success"):
                    logger.info("✅ SERVICIO REGISTRADO EXITOSAMENTE EN EL BACKEND")
                    logger.info(f"   📋 ID de servicio: {dispatch_result.get('service_id', 'N/A')}")

                    # Get address from state for logging
                    direccion_parseada = state.get("direccion_parseada")
                    if direccion_parseada:
                        if hasattr(direccion_parseada, 'to_formatted_string'):
                            direccion_str = direccion_parseada.to_formatted_string()
                        else:
                            direccion_str = str(direccion_parseada)
                        logger.info(f"   📍 Dirección: {direccion_str}")

                    tipo_vehiculo = state.get("tipo_vehiculo")
                    if tipo_vehiculo:
                        logger.info(f"   🚗 Tipo vehículo: {tipo_vehiculo}")
                else:
                    # NUEVO: Verificar si backend esta caido
                    if dispatch_result.get("backend_down"):
                        # Backend caido durante registro
                        logger.error("Backend de 322 caido al registrar servicio - Transferencia requerida")
                    
                        # Crear mensaje para el usuario
                        from langchain_core.messages import AIMessage
                        user_msg = AIMessage(
                            content="He recibido todos tus datos, pero tengo problemas para procesar tu solicitud. Voy a conectarte con un asesor que completara tu pedido."
                        )
                    
                        return {
                            "messages": [user_msg],
                            "agente_actual": "END",
                            "transfer_to_human": True,
                            "transfer_reason": "Backend no disponible para registrar servicio",
                            "token_tracking": state.get("token_tracking")
                        }
                    else:
                        # Otro error - solo logear
                        logger.error(f"❌ Error al registrar servicio: {dispatch_result.get('message')}")
            except Exception as e:
                logger.error(f"❌ Excepción al registrar servicio: {str(e)}")

    return {
        "messages": [result],
        "agente_actual": agente_actual,
        "transfer_to_human": transfer_to_human,
        "transfer_reason": transfer_reason,
        "token_tracking": state.get("token_tracking")
    }


# ==================== ROUTING FUNCTIONS ====================

def route_from_recepcionista(state: TaxiState) -> Literal[END]:
    """
    Route from Recepcionista - always goes to END.

    The recepcionista updates agente_actual to indicate which agent
    should handle the next message.
    """
    messages = state.get("messages", [])
    if not messages:
        return END

    last_msg = messages[-1]

    # Check for TransferToNavegante tool call
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        tool_name = last_msg.tool_calls[0]["name"]
        if tool_name == "TransferToNavegante":
            logger.info("  → Marcado para Navegante (próximo mensaje)")
            # The recepcionista_node already set agente_actual to handle this
            # We just go to END and wait for user's next message
            return END

    # Otherwise end (for CONSULTA, QUEJA, etc.)
    logger.info("  → Finalizando (intención no requiere flujo de booking)")
    return END


def route_from_navegante(state: TaxiState) -> Literal[END]:
    """Route from Navegante - always goes to END."""
    logger.info("  → Finalizando (esperando respuesta del usuario)")
    return END


def route_from_operador(state: TaxiState) -> Literal[END]:
    """Route from Operador - always goes to END."""
    logger.info("  → Finalizando (esperando respuesta del usuario)")
    return END


def route_from_confirmador(state: TaxiState) -> Literal[END]:
    """Route from Confirmador - always goes to END."""
    logger.info("  → Finalizando (esperando respuesta del usuario)")
    return END


# ==================== GRAPH CONSTRUCTION ====================

def create_taxi_graph(checkpointer=None):
    """
    Create the sequential taxi booking graph.

    Flow: Recepcionista → Navegante → Operador → Confirmador
    With backtracking from Confirmador to previous agents.

    Args:
        checkpointer: Optional checkpointer for conversation persistence
                     If None, uses MemorySaver

    Returns:
        Compiled StateGraph ready for use
    """
    logger.info("🏗️ Construyendo grafo secuencial de taxi")

    # Use provided checkpointer or default to MemorySaver
    if checkpointer is None:
        checkpointer = MemorySaver()

    # Build the graph
    builder = StateGraph(TaxiState)

    # ==================== ADD NODES ====================

    # Add router as the entry point
    builder.add_node("router", router_node)

    # Add agent nodes
    builder.add_node("recepcionista", recepcionista_node)
    builder.add_node("navegante", navegante_node)
    builder.add_node("operador", operador_node)
    builder.add_node("confirmador", confirmador_node)

    # ==================== SET ENTRY POINT ====================

    # Router is the entry point - it determines which agent to route to
    builder.set_entry_point("router")

    # ==================== ADD CONDITIONAL EDGES ====================

    # Router decides which agent to activate
    builder.add_conditional_edges(
        "router",
        route_from_router,
        {
            "recepcionista": "recepcionista",
            "navegante": "navegante",
            "operador": "operador",
            "confirmador": "confirmador",
        },
    )

    # Recepcionista routes to Navegante or END
    # All agents always go to END after responding
    # The router will decide which agent handles the next message based on agente_actual
    builder.add_conditional_edges(
        "recepcionista",
        route_from_recepcionista,
        {END: END},
    )

    builder.add_conditional_edges(
        "navegante",
        route_from_navegante,
        {END: END},
    )

    builder.add_conditional_edges(
        "operador",
        route_from_operador,
        {END: END},
    )

    builder.add_conditional_edges(
        "confirmador",
        route_from_confirmador,
        {END: END},
    )

    # ==================== COMPILE GRAPH ====================

    graph = builder.compile(
        checkpointer=checkpointer,
        # No interrupts - confirmation handled through conversation
    )

    logger.info("✅ Grafo secuencial de taxi compilado exitosamente")

    return graph


# ==================== EXPORT ====================

# Create default graph instance
default_taxi_graph = create_taxi_graph()
