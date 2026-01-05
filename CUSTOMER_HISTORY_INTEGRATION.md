# Integración de Historial de Cliente

Este documento describe la implementación de la funcionalidad de consulta de historial de cliente en el sistema de taxi.

## Resumen

El sistema ahora puede:
1. Consultar servicios previos del cliente usando su número de teléfono (CLIENT_ID)
2. Recuperar la última dirección utilizada
3. Preguntar al cliente si quiere usar la dirección anterior o una nueva
4. Registrar nuevos servicios directamente en el backend

## Cambios Realizados

### 1. Nuevas Herramientas de Cliente (`app/tools/customer_tools.py`)

Se crearon 6 nuevas tools para interactuar con la API del cliente:

#### `consultar_servicios_cliente(client_id: str)`
- **Propósito**: Consulta servicios previos del cliente
- **Retorna**:
  - `has_previous_service`: Si el cliente ha usado el servicio antes
  - `last_address`: Última dirección utilizada
  - `data`: Lista completa de servicios previos
- **Uso**: El NAVEGANTE usa esta tool al inicio de la conversación

#### `consultar_cliente(client_id: str)`
- **Propósito**: Consulta información general del cliente
- **Retorna**: Datos del cliente (nombre, contacto, preferencias, etc.)

#### `consultar_servicio_detalle(service_id: str, client_id: str)`
- **Propósito**: Obtiene detalles completos de un servicio específico
- **Uso**: Para consultas sobre servicios anteriores

#### `cancelar_servicio_cliente(service_id: str)`
- **Propósito**: Cancela un servicio activo
- **Retorna**: Confirmación de cancelación

#### `consultar_coordenadas_gpt(client_id: str, ubicacion_actual: str)`
- **Propósito**: Convierte descripciones en lenguaje natural a coordenadas
- **Uso**: Para geocodificación de direcciones

#### `registrar_servicio(...)`
- **Propósito**: Registra un nuevo servicio en el backend
- **Parámetros**:
  - `client_id`: ID del cliente
  - `ubicacion_actual`: Dirección de recogida
  - `metodo_pago`: Método de pago
  - `observacion`: Observaciones para el conductor (opcional)

### 2. Actualización del State (`app/models/taxi_state.py`)

Se agregaron nuevos campos al `TaxiState`:

```python
# ==================== CUSTOMER INFORMATION ====================

client_id: Optional[str]  # Número de teléfono o ID del cliente

tiene_servicio_previo: bool  # Si el cliente ha usado el servicio antes

direccion_previa: Optional[str]  # Última dirección utilizada

usa_direccion_previa: Optional[bool]  # Si el cliente quiere usar la dirección anterior
```

### 3. Actualización del Agente NAVEGANTE

#### Herramientas Disponibles
El NAVEGANTE ahora tiene acceso a:
- `consultar_servicios_cliente` - Para consultar historial
- `consultar_cliente` - Para información del cliente
- `TransferToOperador` - Para avanzar al siguiente agente

#### Nuevo Flujo de Trabajo

**Paso 0: Verificación de Información Previa (SOLO LA PRIMERA VEZ)**

1. Si es la primera interacción (no hay `direccion_previa` en el state):
   - Usa `consultar_servicios_cliente(client_id)` automáticamente

2. Si tiene servicios previos (`has_previous_service = true`):
   - Pregunta: *"¡Hola! Veo que ya has usado nuestro servicio antes. ¿Quieres que te recojamos en [direccion_previa]?"*

   - **Si el usuario dice SÍ**:
     - Actualiza `usa_direccion_previa = true`
     - Confirma: *"Perfecto, entonces te recogemos en [direccion_previa]. ¿Correcto?"*
     - Continúa al paso 2

   - **Si el usuario dice NO**:
     - Actualiza `usa_direccion_previa = false`
     - Pregunta: *"Entiendo, ¿cuál es la nueva dirección?"*
     - Continúa al paso 1 (captura normal)

3. Si NO tiene servicios previos:
   - Continúa con el flujo normal (paso 1)

**Pasos 1-3**: Continúan igual que antes (captura de dirección, confirmación, transferencia)

### 4. Actualización de la API

#### Modelo `ChatRequest` (`app/models/api.py`)

Se agregó un campo opcional `client_id`:

```python
class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None
    user_id: str
    client_id: Optional[str] = None  # ← NUEVO
```

- Si `client_id` no se proporciona, se usa `user_id` como fallback
- El `client_id` se pasa automáticamente al state inicial

#### GraphService (`app/services/graph_service.py`)

El servicio ahora incluye `client_id` en el state inicial:

```python
input_state = {
    "messages": [HumanMessage(content=request.message)],
    "client_id": client_id,  # ← NUEVO
}
```

### 5. Configuración (`app/core/config.py`)

Se agregó la URL base de la API del cliente:

```python
# Customer API Configuration
CUSTOMER_API_BASE_URL: str = "https://s3xzbvdt-4021.use2.devtunnels.ms"
```

Puedes sobrescribir esto en el archivo `.env`:

```env
CUSTOMER_API_BASE_URL=https://tu-api-url.com
```

## Endpoints de la API del Cliente

La integración consume los siguientes endpoints:

| Endpoint | Método | Parámetros | Descripción |
|----------|--------|------------|-------------|
| `/api/consultar-servicio-clientId` | GET | `CLIENT_ID` | Lista de servicios del cliente |
| `/api/consultar-cliente` | GET | `CLIENT_ID` | Información del cliente |
| `/api/consultar-servicio-detalle` | GET | `ID_SERVICIO`, `CLIENT_ID` | Detalle de un servicio |
| `/api/cancelar-servicio` | POST | `ID_SERVICIO` | Cancela un servicio |
| `/api/consulta-coordenadas` | POST | `CLIENT_ID`, `UBICACION_ACTUAL` | Geocodificación |
| `/api/registrar-servicio` | POST | `CLIENT_ID`, `UBICACION_ACTUAL`, `METODO_PAGO`, `OBSERVACION` | Registro de servicio |

## Uso de la API

### Ejemplo 1: Cliente Nuevo (Sin Historial)

```json
POST /api/v1/chat/
{
  "message": "Necesito un taxi",
  "user_id": "user_123",
  "client_id": "3001234567"
}
```

**Respuesta del Asistente**:
```
"¡Con gusto! ¿Desde dónde necesitas el taxi?"
```

### Ejemplo 2: Cliente con Historial

```json
POST /api/v1/chat/
{
  "message": "Necesito un taxi",
  "user_id": "user_456",
  "client_id": "3022370040"
}
```

**Respuesta del Asistente** (si tiene dirección previa):
```
"¡Hola! Veo que ya has usado nuestro servicio antes.
¿Quieres que te recojamos en Calle 72 #43-25, El Prado?"
```

**Usuario responde "Sí"**:
```json
POST /api/v1/chat/
{
  "message": "Sí",
  "user_id": "user_456",
  "client_id": "3022370040",
  "thread_id": "abc123"  // Usar el thread_id de la respuesta anterior
}
```

**Respuesta**:
```
"Perfecto, entonces te recogemos en Calle 72 #43-25, El Prado.
¿Correcto?"
```

## Pruebas

### Script de Prueba

Ejecuta el script de prueba incluido:

```bash
uv run python test_customer_integration.py
```

Este script prueba:
1. ✅ Consulta de servicios previos
2. ✅ Consulta de información del cliente
3. ✅ Flujo completo con la API (requiere servidor corriendo)

### Prueba Manual con Cliente de Prueba

Cliente de prueba: `3022370040`

```bash
# 1. Inicia el servidor
uv run uvicorn app.main:app --reload

# 2. En otra terminal, ejecuta las pruebas
uv run python test_customer_integration.py
```

### Prueba con cURL

```bash
# Primera solicitud
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hola, necesito un taxi",
    "user_id": "test_user",
    "client_id": "3022370040"
  }'

# Captura el thread_id de la respuesta y continúa
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Sí, desde esa dirección",
    "user_id": "test_user",
    "client_id": "3022370040",
    "thread_id": "THREAD_ID_AQUI"
  }'
```

## Flujo Completo de Ejemplo

### Escenario: Cliente Recurrente

1. **Usuario llama**: Sistema recibe `client_id = "3022370040"`

2. **Usuario**: "Necesito un taxi"

3. **Sistema (RECEPCIONISTA)**: Clasifica intención → `SOLICITAR_TAXI`
   - Transfiere invisiblemente a NAVEGANTE

4. **Sistema (NAVEGANTE)**:
   - Consulta `consultar_servicios_cliente("3022370040")`
   - Encuentra servicio previo con dirección "Calle 72 #43-25, El Prado"
   - **Responde**: "¡Hola! Veo que ya has usado nuestro servicio antes. ¿Quieres que te recojamos en Calle 72 #43-25, El Prado?"

5. **Usuario**: "Sí"

6. **Sistema (NAVEGANTE)**:
   - Actualiza `usa_direccion_previa = true`
   - **Responde**: "Perfecto, entonces te recogemos en Calle 72 #43-25, El Prado. ¿Correcto?"

7. **Usuario**: "Sí, correcto"

8. **Sistema (NAVEGANTE)**:
   - **Responde**: "Perfecto. ¿Cómo prefieres pagar el viaje?"
   - Transfiere a OPERADOR

9. **Sistema (OPERADOR)**: Captura método de pago → CONFIRMADOR → Despacho

## Manejo de Errores

Las tools manejan errores gracefully:

- **Timeout**: Retorna `success: false` y continúa sin información previa
- **API Error**: Retorna mensaje de error pero permite continuar el flujo
- **Cliente no encontrado**: Trata como cliente nuevo (sin servicios previos)

Ejemplo de respuesta con error:

```python
{
    "success": False,
    "has_previous_service": False,
    "last_address": None,
    "message": "Timeout al consultar servicios - continuar sin información previa"
}
```

El agente puede continuar el flujo normalmente preguntando por la dirección.

## Consideraciones Importantes

### 1. Privacidad y Seguridad
- Los `client_id` deben ser validados antes de consultar servicios
- Considerar agregar autenticación/autorización en producción

### 2. Performance
- Las consultas a la API son asíncronas (no bloquean)
- Timeout configurado a 10 segundos para consultas de información
- 15 segundos para operaciones más pesadas (coordenadas, registro)

### 3. Voz vs. Texto
- El sistema está optimizado para llamadas de VOZ
- Las direcciones se repiten claramente para confirmación
- El usuario puede corregir en cualquier momento

### 4. Estado de Conversación
- La información del cliente se persiste durante toda la conversación
- El `thread_id` mantiene la continuidad entre mensajes
- El checkpointer guarda el estado entre reinicios del servidor

## Próximos Pasos

### Mejoras Sugeridas

1. **Cache de Información del Cliente**
   - Cachear consultas de cliente para reducir llamadas a la API
   - Usar Redis para cache distribuido

2. **Preferencias del Cliente**
   - Guardar método de pago preferido
   - Recordar necesidades especiales (A/C, mascota, etc.)

3. **Múltiples Direcciones**
   - Permitir al cliente elegir entre varias direcciones guardadas
   - Dirección de casa, trabajo, etc.

4. **Estadísticas de Uso**
   - Tracking de cuántos clientes usan direcciones previas
   - Métricas de satisfacción

5. **Integración Completa de Registro**
   - Usar `registrar_servicio` en lugar del mock `dispatch_to_backend`
   - Enviar todos los datos del servicio al backend real

## Archivos Modificados

```
✅ app/tools/customer_tools.py (NUEVO)
✅ app/tools/__init__.py (ACTUALIZADO)
✅ app/models/taxi_state.py (ACTUALIZADO)
✅ app/models/api.py (ACTUALIZADO)
✅ app/agents/taxi/graph.py (ACTUALIZADO)
✅ app/prompts/taxi_prompts.py (ACTUALIZADO)
✅ app/services/graph_service.py (ACTUALIZADO)
✅ app/core/config.py (ACTUALIZADO)
✅ test_customer_integration.py (NUEVO)
✅ CUSTOMER_HISTORY_INTEGRATION.md (NUEVO - este archivo)
```

## Soporte

Para preguntas o problemas:
1. Revisa los logs del servidor (`app.log`)
2. Ejecuta el script de prueba: `uv run python test_customer_integration.py`
3. Verifica que la API del cliente esté accesible
4. Revisa la documentación en `CLAUDE.md` para arquitectura general
