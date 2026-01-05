# Guía de Streaming - Arquitectura Sandwich (Fase 1)

## Descripción General

Esta implementación agrega **streaming en tiempo real** al sistema de taxi mediante una **arquitectura sandwich** de 3 etapas:

```
📱 Cliente ←→ WebSocket ←→ [STT → Agent → TTS] ←→ Graph
```

### Fase 1: Streaming de Texto (Implementación Actual)

En esta fase inicial:
- ✅ **WebSocket bidireccional**: Comunicación en tiempo real
- ✅ **Pipeline asíncrono de 3 etapas**: STT (simulado) → Agent (real) → TTS (passthrough)
- ✅ **Eventos tipados**: Sistema completo de eventos para observabilidad
- ✅ **Streaming token-por-token**: Respuestas incrementales del agente
- ⏳ **Audio real**: Se implementará en Fase 2 (integración con AssemblyAI/Cartesia)

---

## Arquitectura Técnica

### Flujo de Datos

```
1️⃣ Usuario envía texto → WebSocket
2️⃣ STT Stream (simulado)
   └─> Emite: stt_chunk, stt_output
3️⃣ Agent Stream (4 agentes: RECEPCIONISTA → NAVEGANTE → OPERADOR → CONFIRMADOR)
   └─> Emite: agent_chunk, tool_call, tool_result, agent_end
4️⃣ TTS Stream (passthrough en Fase 1)
   └─> Pasa eventos upstream
5️⃣ Eventos → WebSocket → Cliente (visualización en tiempo real)
```

### Archivos Nuevos

```
app/
├── models/
│   └── events.py                    # Sistema de eventos tipados
├── services/
│   └── streaming_service.py        # Pipeline de 3 etapas (STT → Agent → TTS)
└── api/
    └── v1/
        └── websocket.py             # Endpoint WebSocket

test_websocket_client.html          # Cliente de prueba interactivo
```

### Archivos Modificados

```
app/
└── main.py                         # Registra router WebSocket
```

---

## Inicio Rápido

### 1. Instalar Dependencias

El proyecto ya tiene todas las dependencias necesarias. Si necesitas reinstalar:

```bash
uv pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno

Asegúrate de tener tu `.env` configurado:

```bash
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=1.0
CHECKPOINTER_TYPE=memory  # o postgres/redis
DEBUG=True
```

### 3. Iniciar el Servidor

```bash
uv run uvicorn app.main:app --reload
```

El servidor estará disponible en:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **WebSocket**: ws://localhost:8000/api/v1/ws/chat

### 4. Abrir Cliente de Prueba

Abre en tu navegador:

```
test_websocket_client.html
```

O visita directamente el archivo en tu explorador de archivos.

### 5. Probar el Streaming

1. **Conectar**: Click en "Conectar" en el panel derecho
2. **Enviar mensaje**: Escribe en el input, por ejemplo:
   ```
   Hola, necesito un taxi a la Calle 72 #43-25 en El Prado
   ```
3. **Observar eventos**: Panel derecho muestra eventos en tiempo real
4. **Ver respuesta streaming**: Panel izquierdo muestra la respuesta construyéndose token por token

---

## Protocolo WebSocket

### Mensaje del Cliente → Servidor

```json
{
  "type": "user_input",
  "text": "Necesito un taxi",
  "thread_id": "uuid-opcional"
}
```

**Campos:**
- `type`: Siempre `"user_input"` en Fase 1
- `text`: Mensaje del usuario (en Fase 2+, será audio base64)
- `thread_id`: (Opcional) ID del thread para continuar conversación

### Eventos del Servidor → Cliente

El servidor emite múltiples eventos por cada mensaje:

#### 1. Eventos STT (Speech-to-Text)

**stt_chunk** - Transcripción parcial (simula feedback en tiempo real)
```json
{
  "type": "stt_chunk",
  "text": "Necesito un",
  "ts": 1234567890
}
```

**stt_output** - Transcripción final (trigger para el agente)
```json
{
  "type": "stt_output",
  "text": "Necesito un taxi",
  "ts": 1234567891
}
```

#### 2. Eventos del Agente

**agent_chunk** - Token de la respuesta (streaming)
```json
{
  "type": "agent_chunk",
  "text": "¡Hola",
  "agent": "RECEPCIONISTA",
  "ts": 1234567892
}
```

**tool_call** - Llamada a herramienta
```json
{
  "type": "tool_call",
  "toolCallId": "call_abc123",
  "name": "TransferToNavegante",
  "args": {},
  "ts": 1234567893
}
```

**tool_result** - Resultado de herramienta
```json
{
  "type": "tool_result",
  "toolCallId": "call_abc123",
  "result": "Transfer successful",
  "ts": 1234567894
}
```

**agent_end** - Agente terminó
```json
{
  "type": "agent_end",
  "agent": "RECEPCIONISTA",
  "ts": 1234567895
}
```

**agent_error** - Error durante procesamiento
```json
{
  "type": "agent_error",
  "error": "Error message",
  "ts": 1234567896
}
```

#### 3. Eventos del Sistema

**system_message** - Mensajes del sistema (logs, estado)
```json
{
  "type": "system_message",
  "message": "Procesando mensaje en thread abc123",
  "level": "info",  // "info" | "warning" | "error"
  "ts": 1234567897
}
```

#### 4. Eventos TTS (Fase 2+)

**tts_chunk** - Chunk de audio sintetizado
```json
{
  "type": "tts_chunk",
  "audio": "base64-encoded-audio",
  "sample_rate": 24000,
  "ts": 1234567898
}
```

**tts_end** - Síntesis finalizada
```json
{
  "type": "tts_end",
  "ts": 1234567899
}
```

---

## Casos de Uso

### Ejemplo 1: Solicitar Taxi

**Usuario:**
```
Necesito un taxi a la Calle 72 #43-25, El Prado
```

**Eventos esperados:**
1. `stt_chunk` → "Necesito un"
2. `stt_chunk` → "Necesito un taxi a"
3. `stt_output` → "Necesito un taxi a la Calle 72 #43-25, El Prado"
4. `agent_chunk` → "¡Hola"
5. `agent_chunk` → "! Perfecto"
6. `agent_chunk` → ", te ayudo"
7. ... (más chunks)
8. `tool_call` → `TransferToNavegante`
9. `agent_end` → "RECEPCIONISTA"
10. (Usuario responde y continúa el flujo con NAVEGANTE, OPERADOR, CONFIRMADOR)

### Ejemplo 2: Conversación Completa

```
Usuario: "Hola"
  → RECEPCIONISTA: "¡Hola! ¿En qué puedo ayudarte?"

Usuario: "Necesito un taxi"
  → RECEPCIONISTA: "Perfecto, ¿a qué dirección te diriges?"
  → tool_call: TransferToNavegante

Usuario: "Calle 72 #43-25"
  → NAVEGANTE: "Entendido, Calle 72 #43-25. ¿En qué barrio?"

Usuario: "El Prado"
  → NAVEGANTE: valida zona, confirma
  → tool_call: TransferToOperador

Usuario: "En efectivo"
  → OPERADOR: "Perfecto, efectivo. ¿Alguna preferencia especial?"

Usuario: "No"
  → OPERADOR: genera observación
  → tool_call: TransferToConfirmador

Usuario: "Sí, confirmo"
  → CONFIRMADOR: muestra resumen
  → tool_call: DispatchToBackend
```

---

## Testing y Debugging

### 1. Verificar Conexión WebSocket

```bash
# En el navegador, consola JavaScript:
ws = new WebSocket('ws://localhost:8000/api/v1/ws/chat')
ws.onopen = () => console.log('Conectado')
ws.onmessage = (e) => console.log(JSON.parse(e.data))
```

### 2. Enviar Mensaje de Prueba

```javascript
ws.send(JSON.stringify({
  type: 'user_input',
  text: 'Hola',
  thread_id: 'test-123'
}))
```

### 3. Monitorear Logs del Servidor

Los logs incluyen:
- `🔀 ROUTER`: Decisiones de routing
- `🎯 RECEPCIONISTA`: Procesamiento de intención
- `🗺️ NAVEGANTE`: Validación de dirección
- `⚙️ OPERADOR`: Captura de detalles
- `✅ CONFIRMADOR`: Confirmación final

```bash
tail -f app.log
```

### 4. Health Check del WebSocket

```bash
curl http://localhost:8000/api/v1/ws/health
```

Respuesta esperada:
```json
{
  "status": "healthy",
  "active_connections": 0,
  "service": "websocket_streaming"
}
```

---

## Roadmap - Fases Siguientes

### Fase 2: Integración Audio Real (STT + TTS)

**Objetivos:**
- [ ] Integrar AssemblyAI para Speech-to-Text real
- [ ] Integrar Cartesia/ElevenLabs para Text-to-Speech
- [ ] Modificar cliente para capturar/reproducir audio
- [ ] Implementar buffer inteligente para TTS (frases completas)

**Cambios necesarios:**
- `streaming_service.py`:
  - `stt_stream()`: Conectar con AssemblyAI WebSocket
  - `tts_stream()`: Bufferizar y enviar a Cartesia
- `websocket.py`:
  - Aceptar audio bytes en lugar de texto
- Cliente HTML:
  - Captura de micrófono (MediaRecorder API)
  - Reproducción de audio (Web Audio API)

### Fase 3: Optimizaciones de Producción

**Objetivos:**
- [ ] Rate limiting por usuario
- [ ] Reconexión automática en cliente
- [ ] Compresión de audio (Opus codec)
- [ ] Detección de actividad de voz (VAD)
- [ ] Métricas y monitoreo (latencia, throughput)
- [ ] Load balancing para múltiples conexiones

### Fase 4: Features Avanzadas

**Objetivos:**
- [ ] Interrupción del agente (barge-in)
- [ ] Múltiples idiomas
- [ ] Voces personalizadas
- [ ] Transcripción en tiempo real en pantalla
- [ ] Guardar grabaciones de audio

---

## Troubleshooting

### Error: "Connection refused" al conectar WebSocket

**Causa:** El servidor no está corriendo o está en otro puerto.

**Solución:**
```bash
# Verificar que el servidor esté corriendo
curl http://localhost:8000/health

# Iniciar servidor si no está corriendo
uv run uvicorn app.main:app --reload
```

### Error: "messages with role 'tool' must be a response to..."

**Causa:** ToolMessages huérfanos en el historial (ya manejado por `clean_messages_for_llm`).

**Solución:** Este error NO debería ocurrir en la implementación actual. Si ocurre, revisar logs y reportar.

### WebSocket se desconecta inmediatamente

**Causa:** Error durante el procesamiento del pipeline.

**Solución:**
1. Verificar logs del servidor: `tail -f app.log`
2. Revisar eventos con nivel "error" en el cliente
3. Verificar que `OPENAI_API_KEY` esté configurada

### No se ven eventos de streaming

**Causa:** El graph no está emitiendo eventos correctamente.

**Solución:**
1. Verificar que `stream_mode="messages"` esté configurado en `streaming_service.py:91`
2. Revisar logs para ver si el pipeline se ejecuta
3. Probar con un mensaje simple: "Hola"

### Eventos llegan pero el chat no se actualiza

**Causa:** Error en el JavaScript del cliente.

**Solución:**
1. Abrir consola del navegador (F12)
2. Verificar errores de JavaScript
3. Refrescar la página y volver a conectar

---

## Mejores Prácticas

### 1. Gestión de Thread IDs

```javascript
// Mantener thread_id en localStorage para persistencia
let threadId = localStorage.getItem('taxi_thread_id') || generateUUID();
localStorage.setItem('taxi_thread_id', threadId);

// Limpiar thread al finalizar conversación
function resetConversation() {
  localStorage.removeItem('taxi_thread_id');
  threadId = generateUUID();
}
```

### 2. Manejo de Reconexión

```javascript
let reconnectAttempts = 0;
const MAX_RECONNECTS = 5;

ws.onclose = () => {
  if (reconnectAttempts < MAX_RECONNECTS) {
    setTimeout(() => {
      reconnectAttempts++;
      connect();
    }, 1000 * reconnectAttempts);
  }
};

ws.onopen = () => {
  reconnectAttempts = 0;
};
```

### 3. Buffer de Mensajes del Asistente

```javascript
// Actualizar solo cuando hay cambios significativos
const MIN_CHARS_TO_UPDATE = 3;
let lastUpdate = "";

function updateAssistantMessage(text) {
  if (text.length - lastUpdate.length >= MIN_CHARS_TO_UPDATE) {
    // Actualizar DOM
    lastUpdate = text;
  }
}
```

---

## Diferencias con API HTTP (Endpoint `/chat`)

| Aspecto | HTTP `/chat` | WebSocket `/ws/chat` |
|---------|--------------|----------------------|
| **Conexión** | Request-Response | Persistente, bidireccional |
| **Latencia** | Espera respuesta completa | Streaming progresivo |
| **Experiencia** | Usuario espera | Feedback instantáneo |
| **Uso de red** | 1 request, 1 response | 1 conexión, N eventos |
| **Estado** | Stateless (via thread_id) | Stateful en conexión |
| **Escalabilidad** | Alta (stateless) | Media (conexiones persistentes) |
| **Caso de uso** | APIs, integraciones | UIs en tiempo real, voz |

**Recomendación:**
- **HTTP**: Para integraciones con otros servicios, webhooks, batch processing
- **WebSocket**: Para interfaces de usuario interactivas, especialmente voz

---

## Recursos Adicionales

### Documentación
- [LangChain Voice Agent Docs](https://docs.langchain.com/oss/javascript/langchain/voice-agent)
- [LangGraph Streaming](https://langchain-ai.github.io/langgraph/concepts/streaming/)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)

### Ejemplos de Referencia
- [Voice Sandwich Demo (GitHub)](https://github.com/langchain-ai/voice-sandwich-demo)

### Próximos Pasos
1. Probar el cliente HTML con diferentes mensajes
2. Observar los eventos en tiempo real
3. Experimentar con el flujo completo de booking
4. Prepararse para Fase 2 (audio real)

---

## Soporte

Si encuentras problemas:
1. Revisa esta guía y la sección de Troubleshooting
2. Consulta los logs: `app.log`
3. Verifica el estado del servidor: `curl http://localhost:8000/health`
4. Revisa la consola del navegador (F12)

**Happy Streaming! 🚀**
