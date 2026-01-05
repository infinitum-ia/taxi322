"""Test script to verify API integration compatibility."""

import json
from app.models.api import ChatRequest, ChatResponse


def test_chat_request():
    """Test ChatRequest with uppercase field names."""
    # Test with uppercase (API format)
    request_data = {
        "MESSAGE": "Necesito un taxi",
        "USER_ID": "3042124567",
        "CLIENT_ID": "3042124567",
        "THREAD_ID": "4223b121-31f9-47fc-9851-0435d4dda083"
    }

    request = ChatRequest(**request_data)
    print("✓ ChatRequest created successfully")
    print(f"  message: {request.message}")
    print(f"  user_id: {request.user_id}")
    print(f"  client_id: {request.client_id}")
    print(f"  thread_id: {request.thread_id}")
    print()


def test_chat_response():
    """Test ChatResponse serialization with uppercase field names."""
    # Create response
    response = ChatResponse(
        thread_id="4223b121-31f9-47fc-9851-0435d4dda083",
        message="¿Desde dónde necesitas el taxi?",
        transfer_to_human="false",
        transfer_reason=None
    )

    print("✓ ChatResponse created successfully")

    # Serialize with aliases (this is what FastAPI will do)
    json_output = response.model_dump(by_alias=True)
    print("✓ Serialized with aliases (by_alias=True):")
    print(f"  {json.dumps(json_output, indent=2, ensure_ascii=False)}")
    print()

    # Verify field names are uppercase
    assert "THREAD_ID" in json_output, "THREAD_ID not found in output"
    assert "MESSAGE" in json_output, "MESSAGE not found in output"
    assert "TRANSFER_TO_HUMAN" in json_output, "TRANSFER_TO_HUMAN not found in output"
    assert "TRANSFER_REASON" in json_output, "TRANSFER_REASON not found in output"

    # Verify removed fields are not present
    assert "is_interrupted" not in json_output, "is_interrupted should not be in output"
    assert "interrupt_info" not in json_output, "interrupt_info should not be in output"

    # Verify transfer_to_human is a string
    assert isinstance(json_output["TRANSFER_TO_HUMAN"], str), "TRANSFER_TO_HUMAN should be string"
    assert json_output["TRANSFER_TO_HUMAN"] in ["true", "false"], "TRANSFER_TO_HUMAN should be 'true' or 'false'"

    print("✓ All assertions passed!")
    print()


def test_transfer_to_human_case():
    """Test ChatResponse with transfer_to_human=true."""
    response = ChatResponse(
        thread_id="abc123",
        message="Te voy a transferir con un asesor.",
        transfer_to_human="true",
        transfer_reason="No se pudieron obtener coordenadas GPS de la dirección"
    )

    json_output = response.model_dump(by_alias=True)
    print("✓ Transfer to human case:")
    print(f"  {json.dumps(json_output, indent=2, ensure_ascii=False)}")
    print()

    assert json_output["TRANSFER_TO_HUMAN"] == "true"
    assert json_output["TRANSFER_REASON"] == "No se pudieron obtener coordenadas GPS de la dirección"
    print("✓ Transfer case assertions passed!")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("Testing API Integration Compatibility")
    print("=" * 60)
    print()

    test_chat_request()
    test_chat_response()
    test_transfer_to_human_case()

    print("=" * 60)
    print("✓ ALL TESTS PASSED!")
    print("=" * 60)
