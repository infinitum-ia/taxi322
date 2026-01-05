# Sistema de Solicitud de Taxis - API

API FastAPI profesional para sistema de despacho de taxis en Barranquilla y área metropolitana, construida con LangGraph y OpenAI GPT-4.

## Arquitectura

- **FastAPI**: Framework web moderno y rápido
- **LangGraph**: Framework de agentes con flujo secuencial especializado
- **OpenAI GPT-4**: LLM de OpenAI para procesamiento de lenguaje natural
- **Pydantic**: Validación de datos y configuración

### Flujo Secuencial de 4 Agentes

El sistema utiliza un flujo secuencial con 4 agentes especializados:

1. **Recepcionista** - Clasificación de intención del usuario
   - Detecta si es solicitud de taxi, taxi con carga, cancelación, queja o consulta
   - Normaliza métodos de pago mencionados (nequi, daviplata, etc.)

2. **Navegante** - Especialista en direcciones colombianas
   - Parsea direcciones con reglas específicas colombianas
   - Implementa la regla crítica: "B uno" → sufijo, "B doce" → letra + número
   - Valida zonas de cobertura (Barranquilla, Soledad, Puerto Colombia, Galapa)

3. **Operador** - Logística y detalles del servicio
   - Captura método de pago (Efectivo, Nequi, Daviplata, Datafono)
   - Identifica necesidades especiales del vehículo (baúl grande, aire, mascota)
   - Genera observación operativa para el conductor (tercera persona)

4. **Confirmador** - Validación final y despacho
   - Presenta resumen completo al usuario
   - Permite backtracking si el usuario quiere cambiar algo
   - Despacha el servicio al backend

### Backtracking Inteligente

El Confirmador puede regresar a agentes previos si el usuario quiere corregir información:
- Cambio de dirección → Vuelve a Navegante
- Cambio de pago o detalles → Vuelve a Operador

## Instalación

### Requisitos

- Python 3.12+
- uv (gestor de paquetes)

### Setup

1. **Navegar al directorio del proyecto**

```bash
cd customerTaxi
```

2. **Crear entorno virtual con uv**

```bash
uv venv
```

3. **Instalar dependencias**

```bash
uv pip install -r requirements.txt
```

4. **Configurar variables de entorno**

Copia el archivo de ejemplo y agrega tu API key de OpenAI:

```bash
cp .env.example .env
```

Edita `.env` y agrega tu `OPENAI_API_KEY`:

```env
OPENAI_API_KEY=tu_api_key_aqui
```

Puedes obtener tu API key en: https://platform.openai.com/api-keys

## Uso

### Arrancar el servidor

```bash
uv run uvicorn app.main:app --reload
```

La API estará disponible en:
- **Docs (Swagger)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **API**: http://localhost:8000/api/v1

### Endpoints Disponibles

#### Chat
- `POST /api/v1/chat` - Enviar mensaje al asistente
- `POST /api/v1/chat/continue` - Continuar conversación

#### Threads
- `GET /api/v1/threads/{thread_id}` - Obtener historial completo
- `GET /api/v1/threads/{thread_id}/state` - Obtener estado actual
- `DELETE /api/v1/threads/{thread_id}` - Eliminar thread

### Ejemplo de Uso

```bash
# Solicitar un taxi
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Necesito un taxi en Calle 72 # 43 - 25 en El Prado",
    "user_id": "user_123"
  }'
```

## Flujo de Conversación Típico

1. **Usuario**: "Necesito un taxi"
   - **Recepcionista**: Clasifica como SOLICITAR_TAXI → Transfiere a Navegante

2. **Navegante**: "¿A qué dirección necesitas el taxi?"
   - **Usuario**: "Calle 72 número 43 25 en El Prado"
   - **Navegante**: Parsea dirección, valida zona → Transfiere a Operador

3. **Operador**: "¿Cómo vas a pagar?"
   - **Usuario**: "Con Nequi"
   - **Operador**: Captura pago, genera observación → Transfiere a Confirmador

4. **Confirmador**: Presenta resumen completo
   ```
   📍 Dirección: Calle 72 #43-25, El Prado, Barranquilla
   🏙️ Zona: BARRANQUILLA
   💳 Pago: NEQUI
   📝 Observación: Pasajero solicita taxi.

   ¿Todo está correcto?
   ```
   - **Usuario**: "Sí"
   - **Confirmador**: Despacha servicio → FIN

## Estructura del Proyecto

```
customerTaxi/
├── app/
│   ├── main.py                    # FastAPI application
│   ├── models/
│   │   ├── taxi_state.py         # Extended state with taxi fields
│   │   ├── taxi_routing.py       # Transfer & backtrack tools
│   │   └── api.py                # API request/response models
│   ├── prompts/
│   │   └── taxi_prompts.py       # 4 specialized agent prompts
│   ├── agents/
│   │   ├── taxi/
│   │   │   └── graph.py          # Sequential graph with 4 agents
│   │   └── base.py               # Utilities
│   ├── tools/
│   │   ├── zone_tools.py         # Zone validation
│   │   ├── address_tools.py      # Colombian address parsing
│   │   └── dispatch_tools.py     # Backend dispatch
│   ├── services/
│   │   └── graph_service.py      # Graph orchestration
│   ├── api/                       # REST API endpoints
│   └── core/                      # Configuration & LLM
└── requirements.txt
```

## Reglas Críticas de Direcciones Colombianas

### Regla de Sufijos

La regla MÁS IMPORTANTE del sistema:

**"B uno"** (letra + número bajo) → **Sufijo**
```
"Calle 43 B uno" → via_tipo: Calle, via_numero: 43, sufijo_via: "1"
```

**"B doce"** (letra + número alto) → **Letra + Número separados**
```
"Carrera 50 B doce" → via_tipo: Carrera, via_numero: 50, letra_via: "B", numero: "12"
```

**"BIS", "SUR", "NORTE"** → **Sufijos especiales**
```
"Calle 72 BIS" → via_tipo: Calle, via_numero: 72, sufijo_via: "BIS"
```

### Zonas de Cobertura

✅ **Cobertura completa:**
- Barranquilla (todos los barrios)
- Soledad
- Puerto Colombia
- Galapa

❌ **Fuera de cobertura:**
- Cartagena, Santa Marta, y otras ciudades

## Configuración

### Variables de Entorno

**Requeridas:**
- `OPENAI_API_KEY` - API key de OpenAI

**Opcionales:**
- `LLM_MODEL=gpt-4o` - Modelo a usar (gpt-4o, gpt-4o-mini)
- `LLM_TEMPERATURE=1.0` - Temperatura del modelo
- `CHECKPOINTER_TYPE=memory` - Tipo de checkpointer (memory, postgres, redis)
- `DEBUG=True` - Modo debug

### Nuevas Variables (Futuras)

```env
# Validación de zonas
ZONE_VALIDATION_STRICT=true
ZONE_FUZZY_MATCH_THRESHOLD=0.8

# Backend de despacho (cuando se integre API real)
DISPATCH_API_URL=https://api.taxi-backend.com/dispatch
DISPATCH_API_KEY=your_key
```

## Desarrollo

### Ejecutar tests

```bash
uv run pytest
```

### Formatear código

```bash
uv run black app/ tests/
```

### Lint

```bash
uv run ruff check app/ tests/
```

## Licencia

MIT
