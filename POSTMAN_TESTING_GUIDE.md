# Guía de Testing en Postman

## PROBLEMA IDENTIFICADO

Cuando pruebas en Postman y confirmas la dirección, el sistema responde "¿en qué puedo ayudarte hoy?" en lugar de avanzar al siguiente paso.

**CAUSA RAÍZ**: El `thread_id` NO se está pasando correctamente entre requests.

## SOLUCIÓN: Cómo Probar Correctamente en Postman

### Request 1: Dar la dirección

**URL**: `POST http://localhost:8000/api/v1/chat/`

**Body (JSON)**:
```json
{
  "message": "es para la calle 72 número 43 25",
  "user_id": "test_user"
}
```

**RESPUESTA ESPERADA**:
```json
{
  "thread_id": "abc-123-def-456",  ← COPIA ESTE VALOR
  "message": "Entiendo, ¿la dirección es Calle 72 número 43-25? ¿Es correcto?",
  "is_interrupted": false,
  "interrupt_info": null
}
```

### Request 2: Confirmar la dirección

**⚠️ CRÍTICO**: Debes incluir el `thread_id` que recibiste en la respuesta anterior.

**URL**: `POST http://localhost:8000/api/v1/chat/`

**Body (JSON)**:
```json
{
  "message": "sí, es correcta",
  "user_id": "test_user",
  "thread_id": "abc-123-def-456"  ← MISMO thread_id del Response 1
}
```

**RESPUESTA ESPERADA**:
```json
{
  "thread_id": "abc-123-def-456",  ← MISMO thread_id
  "message": "Perfecto. ¿Cómo prefieres pagar el viaje?",
  "is_interrupted": false,
  "interrupt_info": null
}
```

## ¿QUÉ PASA SI NO ENVÍAS EL thread_id?

Si NO incluyes el `thread_id` en el segundo request:
- El sistema crea un NUEVO thread (nueva conversación)
- `agente_actual` será `None` (nueva sesión)
- El router enviará el mensaje al RECEPCIONISTA
- RECEPCIONISTA recibe "sí, es correcta" SIN CONTEXTO
- Responde: "¿En qué puedo ayudarte hoy?"

## Verificar el Estado del Thread

Puedes verificar el estado actual con:

**URL**: `GET http://localhost:8000/api/v1/threads/{thread_id}/state`

**Ejemplo**:
```
GET http://localhost:8000/api/v1/threads/abc-123-def-456/state
```

**Respuesta**:
```json
{
  "thread_id": "abc-123-def-456",
  "values": {
    "agente_actual": "NAVEGANTE",  ← Debe estar en NAVEGANTE después de dar dirección
    "messages": [...]
  },
  "next": []
}
```

## Script de Prueba Automático

Para evitar errores manuales, ejecuta:

```bash
python simple_debug.py
```

Este script:
1. Envía el primer mensaje
2. Captura el thread_id automáticamente
3. Usa el MISMO thread_id en el segundo mensaje
4. Verifica el estado entre requests
5. Analiza si el flujo fue correcto

## Cómo Configurar Postman para Facilitar las Pruebas

### Opción 1: Variables de Entorno

1. Crea una variable de entorno llamada `thread_id`
2. En el Request 1, agrega un "Test":
   ```javascript
   pm.environment.set("thread_id", pm.response.json().thread_id);
   ```
3. En el Request 2, usa la variable:
   ```json
   {
     "message": "sí, es correcta",
     "user_id": "test_user",
     "thread_id": "{{thread_id}}"
   }
   ```

### Opción 2: Copiar Manualmente

1. Ejecuta Request 1
2. Copia el `thread_id` de la respuesta
3. Pégalo en el body del Request 2

## Checklist de Debugging

- [ ] El Request 1 devuelve un `thread_id`
- [ ] El Request 2 incluye el MISMO `thread_id` en el body
- [ ] Los dos requests tienen el MISMO `user_id`
- [ ] El servidor está corriendo (`GET /health` retorna 200)
- [ ] El `agente_actual` cambia entre requests (verificar con `/threads/{id}/state`)
