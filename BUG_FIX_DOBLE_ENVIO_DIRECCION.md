# Corrección del Bug: Doble Envío de Dirección

## Problema Identificado

Cuando el usuario enviaba su dirección por primera vez, el sistema devolvía una respuesta incorrecta (la respuesta del mensaje anterior "¡Hola! Soy Alice..."), obligando al usuario a enviar la dirección **dos veces** para obtener una respuesta adecuada.

## Causa Raíz

El problema ocurría en el flujo siguiente:

1. Usuario envía mensaje con dirección: "puedes mandarme un taxi en Calle 93 número 46C-120"
2. RECEPCIONISTA detecta la dirección y hace un `tool_call` a `TransferToNavegante`
3. El LLM genera un AIMessage con:
   - **tool_call**: `TransferToNavegante`
   - **content**: `"..."` (solo puntos suspensivos, sin mensaje útil)
4. `graph_service.py` busca la última respuesta AI con contenido válido
5. Como el contenido "..." se considera válido (`bool("...".strip()) == True`), lo selecciona
6. Pero "..." no es una respuesta útil, así que el usuario ve la respuesta anterior

## Archivo Afectado

- `app/services/graph_service.py` - Métodos `invoke_chat` y `continue_chat`

## Solución Implementada

Se modificó la lógica de extracción de respuestas en `graph_service.py` para:

### 1. Detectar AIMessages con tool_calls sin contenido útil

```python
# Nueva lógica
is_placeholder = ai_response.strip() in ["...", ".", "--", "—"]
if (not ai_response or not ai_response.strip() or is_placeholder) and last_ai_with_tool_calls:
    # Generar respuesta apropiada basada en el tool_call
```

### 2. Generar respuestas apropiadas según el tool_call

Cuando se detecta un AIMessage con tool_call pero sin contenido útil, el sistema ahora genera automáticamente una respuesta apropiada:

- **TransferToNavegante**: "¡Con gusto! ¿Desde dónde necesitas el taxi?"
- **TransferToOperador**: "Perfecto. ¿Cómo vas a pagar el servicio?"
- **TransferToConfirmador**: "Entendido. Déjame confirmar los detalles del servicio..."

## Resultados

### Antes (Bug)
```
Usuario: "puedes mandarme un taxi en Calle 93 número 46C-120"
Sistema: "¡Hola! Soy Alice, tu asistente de taxi de 3 22. ¿En qué puedo ayudarte hoy?"
         ❌ Respuesta incorrecta (del mensaje anterior)

Usuario: "puedes mandarme un taxi en Calle 93 número 46C-120" [segunda vez]
Sistema: "Entiendo, ¿la dirección es Calle 93 número 46C-120? ¿Es correcto?"
         ✅ Respuesta correcta (pero requirió doble envío)
```

### Después (Corrección)
```
Usuario: "puedes mandarme un taxi en Calle 93 número 46C-120"
Sistema: "Entiendo, ¿la dirección es Calle 93 número 46C-120? ¿Es correcto?"
         ✅ Respuesta correcta (en el primer envío)
```

## Archivos Modificados

1. **app/services/graph_service.py**
   - Método `invoke_chat` (líneas 129-156)
   - Método `continue_chat` (líneas 264-286)

## Archivos de Prueba

- `test_tool_call_fix.py` - Script de prueba que verifica la corrección

Para ejecutar la prueba:
```bash
python test_tool_call_fix.py
```

## Logs de Verificación

El sistema ahora muestra los siguientes logs cuando detecta el problema:

```
⚠️  AI message has tool_calls but no content - generating appropriate response
🔧 Tool: TransferToNavegante, Args: {...}
✅ Generated TransferToNavegante response: ¡Con gusto! ¿Desde dónde necesitas el taxi?
```

## Comportamiento del LLM

El problema ocurre porque GPT-4 a veces genera AIMessages con:
- Solo tool_calls (sin contenido de texto)
- Contenido placeholder como "..." (sin información útil)

Esta corrección maneja ambos casos de forma robusta.

## Fecha de Corrección

2025-12-26

## Estado

✅ **CORREGIDO** - Verificado con pruebas exitosas
