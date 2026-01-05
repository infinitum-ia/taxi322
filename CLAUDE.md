# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based taxi booking API built with **LangGraph** and **OpenAI GPT-4**. The system uses a **sequential 4-agent architecture** optimized for **VOICE CALLS** where specialized agents collaborate to guide users through the taxi booking process in Barranquilla, Colombia.

**CRITICAL: This is a VOICE-based system** - users are speaking on the phone, not typing. All prompts are designed for natural conversation, not text parsing.

## Common Commands

### Development Server
```bash
# Start the server (recommended - auto-reload on changes)
uv run uvicorn app.main:app --reload

# Alternative start method
uv run python -m app.main

# Server runs on http://localhost:8000
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

### Environment Setup
```bash
# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt

# Install dev dependencies (if exists)
uv pip install -r requirements-dev.txt

# Setup environment variables (copy and edit)
cp .env.example .env
```

### Testing & Code Quality
```bash
# Run tests
uv run pytest

# Format code
uv run black app/ tests/

# Lint code
uv run ruff check app/ tests/
```

## Architecture

### Sequential 4-Agent System

The system uses a **sequential conversation flow** with 4 specialized agents that appear as a single "Alice" assistant to the user:

```
User Message → Router → [RECEPCIONISTA → NAVEGANTE → OPERADOR → CONFIRMADOR] → Response
```

### Agent Flow

1. **RECEPCIONISTA** (Intent Classifier)
   - **Responsibility**: Classify user intent
   - **Intents**: `SOLICITAR_TAXI`, `SOLICITAR_TAXI_CARGA`, `CANCELAR`, `QUEJA`, `CONSULTA`, `OTRO`
   - **Transition**: If taxi request → asks for address → transfers to NAVEGANTE
   - **Tool**: `TransferToNavegante`

2. **NAVEGANTE** (Address Specialist)
   - **Responsibility**: Parse and validate Colombian addresses
   - **Process**:
     - Captures address from user
     - Parses Colombian address structure (Calle/Carrera + numbers)
     - Validates service coverage zone
     - Confirms with user
   - **Tools**: `validate_zone`, `parse_colombian_address`, `TransferToOperador`
   - **Transition**: When address complete and zone valid → asks for payment method

3. **OPERADOR** (Logistics Specialist)
   - **Responsibility**: Capture payment method, vehicle details, generate driver observation
   - **Process**:
     - Detects/asks payment method (EFECTIVO, NEQUI, DAVIPLATA, DATAFONO)
     - Detects special needs (A/C, pet, large trunk, etc.)
     - Generates operational note for driver (in third person)
   - **Tools**: `estimate_fare`, `TransferToConfirmador`
   - **Transition**: When payment and observation ready → transfers to CONFIRMADOR

4. **CONFIRMADOR** (Final Confirmation)
   - **Responsibility**: Confirm all details and dispatch
   - **Process**:
     - Presents complete summary with emojis
     - Asks explicit confirmation from user
     - Handles corrections or dispatches
   - **Tools**:
     - `BacktrackToNavegante` (correct address)
     - `BacktrackToOperador` (change payment)
     - `DispatchToBackend` (send order)
   - **Transition**:
     - User confirms → `DispatchToBackend` → END
     - User corrects → backtrack to appropriate agent

### State Management

**TaxiState** (`app/models/taxi_state.py`):
- `messages`: Full conversation history (managed by `add_messages` reducer)
- `agente_actual`: Current active agent (RECEPCIONISTA, NAVEGANTE, OPERADOR, CONFIRMADOR)
- `intencion`: Classified user intent
- `direccion_parseada`: Structured address (DireccionParseada model)
- `zona_validada`: Service coverage zone
- `metodo_pago`: Payment method
- `detalles_vehiculo`: Vehicle requirements list
- `observacion_final`: Driver operational note

The `agente_actual` field is critical for routing - the Router node uses it to determine which agent should handle the next message.

### Router Logic

The **Router Node** is the entry point for all messages:
1. Reads `agente_actual` from state
2. If `None` → routes to RECEPCIONISTA (new conversation)
3. If set → routes to that agent (continuing conversation)

Each agent updates `agente_actual` before ending to indicate which agent should handle the next user message.

### Checkpointing & Persistence

**Checkpointer** (`app/core/checkpointer.py`):
- Supports `memory`, `postgres`, or `redis` backends (configured via `CHECKPOINTER_TYPE` env var)
- Stores conversation state between requests
- Enables conversation persistence across server restarts (when using postgres/redis)
- Each conversation has a unique `thread_id`

### Message Cleaning

**Critical Pattern** (`app/agents/base.py` - `clean_messages_for_llm`):
- LangGraph can create orphaned `ToolMessage` objects that break LLM APIs
- The `clean_messages_for_llm` function removes ToolMessages without corresponding AIMessage tool_calls
- This prevents the error: "messages with role 'tool' must be a response to a preceeding message with 'tool_calls'"
- Called before every LLM invocation in each agent node

## Key Files

### API Layer
- `app/main.py` - FastAPI app initialization, CORS, health endpoints
- `app/api/v1/chat.py` - Chat endpoints (send message, continue, approve/reject)
- `app/api/v1/threads.py` - Thread management endpoints
- `app/api/deps.py` - Dependency injection (graph service)

### Core Services
- `app/services/graph_service.py` - Orchestrates graph invocations, handles responses
- `app/core/llm.py` - LLM factory (creates ChatOpenAI instances)
- `app/core/config.py` - Settings from environment variables
- `app/core/checkpointer.py` - Checkpointer factory

### Agents
- `app/agents/taxi/graph.py` - Main taxi booking graph with 4 agents
- `app/agents/base.py` - Message cleaning utilities

### Prompts
- `app/prompts/taxi_prompts.py` - Specialized prompts for each agent:
  - `RECEPCIONISTA_PROMPT`
  - `NAVEGANTE_PROMPT`
  - `OPERADOR_PROMPT`
  - `CONFIRMADOR_PROMPT`

### Tools
- `app/tools/zone_tools.py` - Zone validation (validate_zone, get_zone_info)
- `app/tools/address_tools.py` - Address parsing (parse_colombian_address, format_direccion)
- `app/tools/dispatch_tools.py` - Dispatch to backend (dispatch_to_backend, estimate_fare)

### Models
- `app/models/taxi_state.py` - TaxiState definition with custom reducers
- `app/models/taxi_routing.py` - Routing tool schemas (TransferToNavegante, etc.)
- `app/models/api.py` - API request/response models (ChatRequest, ChatResponse)

## Important Patterns

### Adding a New Tool

1. Define the tool function in appropriate `app/tools/*.py` file
2. Add `@tool` decorator with clear description
3. Import in `app/agents/taxi/graph.py`
4. Add to the appropriate agent's tools list in the agent node
5. Update the agent's prompt in `app/prompts/taxi_prompts.py` to mention the new tool

### Adding a New Agent

If you need to add a 5th agent to the flow:

1. Create prompt in `app/prompts/taxi_prompts.py`
2. Add agent name to `agente_actual` Literal in `app/models/taxi_state.py`
3. Create node function in `app/agents/taxi/graph.py`
4. Add node to graph builder
5. Update routing logic in `route_from_router`
6. Create transfer tool in `app/models/taxi_routing.py`

### Debugging Conversations

```python
# View full conversation state
GET /api/v1/threads/{thread_id}/state

# Check logs (app.log contains detailed debug info)
# GraphService logs all LLM invocations
# Each agent node logs when activated
# Message cleaning operations are logged
```

## Environment Variables

Required:
- `OPENAI_API_KEY` - OpenAI API key (get from https://platform.openai.com/api-keys)

Optional (with defaults):
- `LLM_MODEL=gpt-4o` - Model to use (gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo)
- `LLM_TEMPERATURE=1.0` - Temperature for LLM
- `LLM_MAX_TOKENS=4096` - Max tokens per response
- `CHECKPOINTER_TYPE=memory` - Checkpointer backend (memory, postgres, redis)
- `DEBUG=True` - Enable debug mode

## Common Issues

### "messages with role 'tool' must be a response to a preceeding message with 'tool_calls'"
- Caused by orphaned ToolMessages in conversation history
- The `clean_messages_for_llm` function should handle this automatically
- If you see this error, check that all agent nodes are calling `clean_messages_for_llm` before LLM invocation

### Agent Not Transitioning
- Check that the agent node is updating `agente_actual` in its return dict
- Verify that tool calls are being made correctly (e.g., `TransferToNavegante`)
- Check logs to see which agent the router is sending messages to

### State Not Persisting
- Check `CHECKPOINTER_TYPE` is set correctly in .env
- For postgres/redis, verify connection details in environment variables
- Ensure `thread_id` is being passed consistently across requests

### Colombian Address Parsing Issues
- Review the suffix rules in `NAVEGANTE_PROMPT` (app/prompts/taxi_prompts.py:103-121)
- Critical distinction: "B uno" → sufijo_via="1", "B doce" → letra_via="B", numero="12"
- Address format: `[Via tipo] [Número] [Letra] [Sufijo] # [Casa] - [Placa], [Barrio]`
- Example: "Calle 72 #43-25, El Prado"

## Design Principles

1. **Invisible Transitions**: Agents never mention "transferring" or "specialists" - the user only sees "Alice"
2. **Explicit Confirmation**: CONFIRMADOR never dispatches without user confirmation
3. **Backtracking Support**: Users can correct information at any stage
4. **Natural Language**: All prompts are in Spanish and conversational
5. **Operational Focus**: `observacion_final` is written in third person for driver consumption
