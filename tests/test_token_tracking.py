"""Test para el sistema de tracking de tokens por sesión."""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch
from app.services.token_tracker import TokenTracker, TOKEN_FILE
from app.agents.taxi.token_interceptor import intercept_llm_call


# Path para el archivo de tracking (usa el mismo que el servicio)
TOKEN_USAGE_FILE = TOKEN_FILE


@pytest.fixture(autouse=True)
def cleanup_token_file():
    """Limpia el archivo de tokens antes y después de cada test."""
    if TOKEN_USAGE_FILE.exists():
        TOKEN_USAGE_FILE.unlink()
    yield
    if TOKEN_USAGE_FILE.exists():
        TOKEN_USAGE_FILE.unlink()


def test_extract_tokens_from_llm_response():
    """Test que verifica la extracción de tokens de una respuesta LLM."""
    # Mock de AIMessage con response_metadata
    mock_result = Mock()
    mock_result.usage_metadata = None  # Disable usage_metadata
    mock_result.response_metadata = {
        "token_usage": {
            "prompt_tokens": 150,
            "completion_tokens": 45
        }
    }

    tokens = TokenTracker.extract_tokens_from_llm_response(mock_result)

    assert tokens["input"] == 150
    assert tokens["output"] == 45


def test_extract_tokens_no_metadata():
    """Test cuando el resultado no tiene metadata."""
    mock_result = Mock()
    mock_result.usage_metadata = None  # Disable usage_metadata
    mock_result.response_metadata = {}

    tokens = TokenTracker.extract_tokens_from_llm_response(mock_result)

    assert tokens["input"] == 0
    assert tokens["output"] == 0


def test_is_farewell_message():
    """Test de detección de mensajes de despedida."""
    assert TokenTracker.is_farewell_message("Gracias") is True
    assert TokenTracker.is_farewell_message("Muchas gracias") is True
    assert TokenTracker.is_farewell_message("Adiós") is True
    assert TokenTracker.is_farewell_message("adios") is True
    assert TokenTracker.is_farewell_message("Chao") is True
    assert TokenTracker.is_farewell_message("Hasta luego") is True
    assert TokenTracker.is_farewell_message("Bye") is True

    assert TokenTracker.is_farewell_message("Hola") is False
    assert TokenTracker.is_farewell_message("Necesito un taxi") is False
    assert TokenTracker.is_farewell_message("") is False


def test_write_session_to_file():
    """Test de escritura del archivo de tokens."""
    TokenTracker.write_session_to_file(
        client_id="3001234567",
        duration=45.67,
        input_tokens=850,
        output_tokens=320
    )

    assert TOKEN_USAGE_FILE.exists()

    with open(TOKEN_USAGE_FILE, "r", encoding="utf-8") as f:
        line = f.read().strip()

    parts = line.split("|")
    assert len(parts) == 4

    client_id, duration, input_tokens, output_tokens = parts

    assert client_id.strip() == "3001234567"
    assert float(duration.strip()) == 45.67
    assert int(input_tokens.strip()) == 850
    assert int(output_tokens.strip()) == 320


def test_intercept_llm_call_initializes_tracking():
    """Test que intercept_llm_call inicializa el tracking en la primera llamada."""
    # Mock de AIMessage
    mock_result = Mock()
    mock_result.usage_metadata = None  # Disable usage_metadata
    mock_result.response_metadata = {
        "token_usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50
        }
    }

    state = {}

    updated_state = intercept_llm_call(mock_result, state)

    assert "token_tracking" in updated_state
    assert "start_time" in updated_state["token_tracking"]
    assert updated_state["token_tracking"]["total_input_tokens"] == 100
    assert updated_state["token_tracking"]["total_output_tokens"] == 50
    assert updated_state["token_tracking"]["dispatch_executed"] is False
    assert updated_state["token_tracking"]["tracking_saved"] is False


def test_intercept_llm_call_accumulates_tokens():
    """Test que intercept_llm_call acumula tokens en llamadas subsiguientes."""
    # Primera llamada
    mock_result1 = Mock()
    mock_result1.usage_metadata = None  # Disable usage_metadata
    mock_result1.response_metadata = {
        "token_usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50
        }
    }

    state = {}
    state = intercept_llm_call(mock_result1, state)

    assert state["token_tracking"]["total_input_tokens"] == 100
    assert state["token_tracking"]["total_output_tokens"] == 50

    # Segunda llamada
    mock_result2 = Mock()
    mock_result2.usage_metadata = None  # Disable usage_metadata
    mock_result2.response_metadata = {
        "token_usage": {
            "prompt_tokens": 120,
            "completion_tokens": 35
        }
    }

    state = intercept_llm_call(mock_result2, state)

    assert state["token_tracking"]["total_input_tokens"] == 220  # 100 + 120
    assert state["token_tracking"]["total_output_tokens"] == 85  # 50 + 35


def test_write_multiple_sessions():
    """Test que verifica la escritura de múltiples sesiones en el archivo."""
    # Sesión 1
    TokenTracker.write_session_to_file(
        client_id="3001234567",
        duration=45.67,
        input_tokens=850,
        output_tokens=320
    )

    # Sesión 2
    TokenTracker.write_session_to_file(
        client_id="3009876543",
        duration=52.34,
        input_tokens=920,
        output_tokens=405
    )

    assert TOKEN_USAGE_FILE.exists()

    with open(TOKEN_USAGE_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 2

    # Validar primera línea
    parts1 = lines[0].strip().split("|")
    assert parts1[0].strip() == "3001234567"
    assert float(parts1[1].strip()) == 45.67
    assert int(parts1[2].strip()) == 850
    assert int(parts1[3].strip()) == 320

    # Validar segunda línea
    parts2 = lines[1].strip().split("|")
    assert parts2[0].strip() == "3009876543"
    assert float(parts2[1].strip()) == 52.34
    assert int(parts2[2].strip()) == 920
    assert int(parts2[3].strip()) == 405


def test_token_tracking_end_to_end():
    """
    Test end-to-end que simula el flujo completo de tracking de tokens.

    Este test simula:
    1. Múltiples invocaciones LLM (acumulando tokens)
    2. Ejecución de DispatchToBackend
    3. Mensaje de despedida
    4. Escritura del archivo
    """
    import time

    # Simular estado inicial
    state = {}

    # Simular 3 invocaciones LLM
    for i in range(3):
        mock_result = Mock()
        mock_result.usage_metadata = None  # Disable usage_metadata
        mock_result.response_metadata = {
            "token_usage": {
                "prompt_tokens": 100 + (i * 10),
                "completion_tokens": 50 + (i * 5)
            }
        }
        state = intercept_llm_call(mock_result, state)

    # Verificar acumulación
    assert state["token_tracking"]["total_input_tokens"] == 100 + 110 + 120  # 330
    assert state["token_tracking"]["total_output_tokens"] == 50 + 55 + 60  # 165

    # Simular ejecución de DispatchToBackend
    state["token_tracking"]["dispatch_executed"] = True

    # Simular mensaje de despedida y escritura del archivo
    client_id = "3001234567"
    state["client_id"] = client_id

    # Calcular duración
    start_time = state["token_tracking"]["start_time"]
    time.sleep(0.1)  # Simular paso del tiempo
    duration = time.time() - start_time

    # Escribir al archivo
    TokenTracker.write_session_to_file(
        client_id=client_id,
        duration=duration,
        input_tokens=state["token_tracking"]["total_input_tokens"],
        output_tokens=state["token_tracking"]["total_output_tokens"]
    )

    # Validar archivo
    assert TOKEN_USAGE_FILE.exists()

    with open(TOKEN_USAGE_FILE, "r", encoding="utf-8") as f:
        line = f.read().strip()

    parts = line.split("|")
    assert len(parts) == 4
    assert parts[0].strip() == "3001234567"
    assert float(parts[1].strip()) > 0
    assert int(parts[2].strip()) == 330
    assert int(parts[3].strip()) == 165


def test_token_tracking_file_format():
    """Test que valida el formato exacto del archivo."""
    TokenTracker.write_session_to_file(
        client_id="3001234567",
        duration=45.67,
        input_tokens=850,
        output_tokens=320
    )

    with open(TOKEN_USAGE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Verificar formato con pipes
    assert "|" in content
    assert content.count("|") == 3

    # Verificar que los espacios alrededor de pipes están presentes
    assert " | " in content

    # Verificar que termina con newline
    assert content.endswith("\n")


# Tests de token tracking completados exitosamente
