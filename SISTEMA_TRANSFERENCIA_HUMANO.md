# Sistema de Transferencia a Agente Humano

## Resumen

Se ha implementado un sistema completo para transferir conversaciones a un agente humano cuando:
1. **No se obtienen coordenadas GPS de la dirección** (caso principal)
2. El usuario solicita explícitamente hablar con un agente humano
3. El sistema no puede proceder con el despacho automático

---

## Componentes Implementados

### 1. Herramienta de Transferencia (`app/models/taxi_routing.py:128-158`)

```python
class TransferToHuman(BaseModel):
    """Transfer the conversation to a human agent."""

    reason: str = Field(
        description="Reason for transferring to human agent"
    )
    user_notified: bool = Field(
        default=True,
        description="User has been notified about the transfer"
    )
```

**Uso:** Disponible para el agente CONFIRMADOR cuando necesita transferir a humano.

---

### 2. Campos de Estado (`app/models/taxi_state.py:364-368`)

```python
# HUMAN TRANSFER
transfer_to_human: bool  # Flag indicating conversation should be transferred to human
transfer_reason: Optional[str]  # Reason for the transfer
```

**Propósito:** Almacenar el estado de transferencia en la conversación.

---

### 3. Lógica del CONFIRMADOR (`app/agents/taxi/graph.py`)

#### Detección de Coordenadas Faltantes:
```python
# Check if coordinates are missing
tiene_coordenadas = state.get("latitud") is not None and state.get("longitud") is not None
logger.info(f"  → Coordenadas presentes: {tiene_coordenadas}")
```

#### Herramientas Disponibles:
```python
tools = [BacktrackToNavegante, BacktrackToOperador, DispatchToBackend, TransferToHuman]
```

#### Manejo de Transferencia:
```python
elif tool_name == "TransferToHuman":
    # Transfer to human agent
    transfer_to_human = True
    transfer_reason = tool_args.get("reason", "Usuario requiere asistencia humana")
    agente_actual = "END"
    logger.info(f"  → 🙋 TRANSFERENCIA A HUMANO: {transfer_reason}")
```

---

### 4. Prompt del CONFIRMADOR (`app/prompts/taxi_prompts.py:513-518`)

```
IMPORTANTE - VERIFICACIÓN DE COORDENADAS:
ANTES de solicitar confirmación al usuario, verifica si hay coordenadas GPS (latitud/longitud) en el sistema.
Si NO hay coordenadas GPS:
→ Explica al usuario: "He recibido todos tus datos, pero necesito verificar tu dirección con un asesor.
   En un momento te contactará una persona para confirmar tu ubicación exacta."
→ USA TransferToHuman con razón: "No se pudieron obtener coordenadas GPS de la dirección"
→ NO procedas con el despacho automático
```

**Comportamiento:** El agente detecta automáticamente cuando faltan coordenadas y transfiere a humano.

---

### 5. API Response (`app/models/api.py:58-65`)

```python
class ChatResponse(BaseModel):
    # ... campos existentes ...

    transfer_to_human: bool = Field(
        False,
        description="Whether the conversation should be transferred to a human agent"
    )
    transfer_reason: Optional[str] = Field(
        None,
        description="Reason for transferring to human agent (if transfer_to_human is True)"
    )
```

**Respuesta de ejemplo con transferencia:**
```json
{
  "thread_id": "abc123",
  "message": "He recibido todos tus datos, pero necesito verificar tu dirección con un asesor...",
  "is_interrupted": false,
  "interrupt_info": null,
  "transfer_to_human": true,
  "transfer_reason": "No se pudieron obtener coordenadas GPS de la dirección"
}
```

---

### 6. GraphService (`app/services/graph_service.py:167-172`)

```python
# CHECK FOR HUMAN TRANSFER
transfer_to_human = result.get("transfer_to_human", False)
transfer_reason = result.get("transfer_reason")

if transfer_to_human:
    logger.info(f"🙋 TRANSFERENCIA A HUMANO SOLICITADA: {transfer_reason}")
```

**Logging:** Se registra en los logs cuando se solicita una transferencia.

---

## Flujo Completo

### Escenario: Dirección Sin Coordenadas GPS

```
1. Usuario: "Necesito un taxi"
2. RECEPCIONISTA → NAVEGANTE → OPERADOR → CONFIRMADOR

3. OPERADOR intenta obtener coordenadas:
   - Normaliza dirección: "cr 43b 112"
   - Llama a API de geocodificación
   - API devuelve: LATITUD=NULL, LONGITUD=NULL
   - Coordenadas NO se guardan en el estado

4. CONFIRMADOR detecta:
   - tiene_coordenadas = False
   - Verifica en el prompt que debe transferir a humano

5. CONFIRMADOR responde al usuario:
   "He recibido todos tus datos, pero necesito verificar tu dirección
    con un asesor. En un momento te contactará una persona para confirmar
    tu ubicación exacta."

6. CONFIRMADOR usa herramienta:
   TransferToHuman(
       reason="No se pudieron obtener coordenadas GPS de la dirección",
       user_notified=True
   )

7. Estado actualizado:
   - transfer_to_human = True
   - transfer_reason = "No se pudieron obtener coordenadas GPS de la dirección"
   - agente_actual = "END"

8. API devuelve ChatResponse:
   {
     "transfer_to_human": true,
     "transfer_reason": "No se pudieron obtener coordenadas GPS de la dirección",
     "message": "He recibido todos tus datos..."
   }

9. Sistema cliente (frontend/call center):
   - Detecta transfer_to_human = true
   - Redirige la conversación a un agente humano
   - Muestra transfer_reason al agente humano
```

---

## Integración con Sistema Cliente

### Backend debe verificar en cada respuesta:

```python
response = await chat_api.invoke_chat(request)

if response.transfer_to_human:
    # Transferir a agente humano
    reason = response.transfer_reason
    thread_id = response.thread_id

    # Obtener contexto completo de la conversación
    state = await chat_api.get_thread_state(thread_id)

    # Redirigir a cola de agentes humanos con contexto:
    # - Dirección proporcionada
    # - Método de pago
    # - Detalles del vehículo
    # - Razón de transferencia

    await transfer_to_human_queue(
        thread_id=thread_id,
        reason=reason,
        context=state
    )
```

---

## Casos de Uso

### 1. **Geocodificación Fallida** (Implementado)
- Dirección no encontrada en el servicio de mapas
- Coordenadas devueltas como NULL
- → **Transferencia automática a humano**

### 2. **Usuario Solicita Agente** (Preparado)
Usuario: "Quiero hablar con una persona"
→ CONFIRMADOR usa `TransferToHuman(reason="Usuario solicitó hablar con un agente")`

### 3. **Dirección Ambigua** (Futuro)
- Servicio devuelve múltiples resultados
- Usuario no puede confirmar cuál es correcto
- → **Transferencia a humano para clarificar**

---

## Logs de Ejemplo

```
2025-12-30 10:15:23 - app.agents.taxi.graph - INFO - ✅ CONFIRMADOR: Confirmación final
2025-12-30 10:15:23 - app.agents.taxi.graph - INFO -   → Coordenadas presentes: False
2025-12-30 10:15:25 - app.agents.taxi.graph - INFO -   → 🙋 TRANSFERENCIA A HUMANO: No se pudieron obtener coordenadas GPS de la dirección
2025-12-30 10:15:25 - app.services.graph_service - INFO - 🙋 TRANSFERENCIA A HUMANO SOLICITADA: No se pudieron obtener coordenadas GPS de la dirección
```

---

## Testing

### Prueba Manual:

1. Iniciar conversación con dirección que NO tiene coordenadas
2. Completar flujo hasta CONFIRMADOR
3. Verificar que la API devuelve `transfer_to_human: true`
4. Confirmar que el mensaje al usuario es apropiado

### Ejemplo de Prueba:

```bash
# 1. Iniciar conversación
POST /api/v1/chat
{
  "message": "Necesito un taxi",
  "user_id": "test_user",
  "client_id": "3042124567"
}

# 2. Continuar hasta dirección
POST /api/v1/chat
{
  "message": "cr 43b 999999",  # Dirección inexistente
  "thread_id": "..."
}

# 3. Completar flujo (método de pago, etc.)

# 4. En CONFIRMADOR, verificar respuesta:
{
  "transfer_to_human": true,
  "transfer_reason": "No se pudieron obtener coordenadas GPS de la dirección",
  "message": "He recibido todos tus datos, pero necesito verificar..."
}
```

---

## Conclusión

El sistema está completamente implementado y listo para:
- Detectar automáticamente cuando faltan coordenadas GPS
- Transferir conversaciones a agentes humanos
- Proveer contexto completo al sistema cliente para la transferencia
- Mantener logging detallado de todas las transferencias

**Siguiente paso:** Integrar en el sistema cliente (frontend/call center) para manejar la transferencia cuando `transfer_to_human: true`.
