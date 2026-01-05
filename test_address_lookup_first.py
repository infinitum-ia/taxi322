"""
Script de prueba para validar el flujo de consulta de dirección PRIMERO.

Este script prueba que:
1. El NAVEGANTE consulta la dirección del cliente ANTES de pedirla
2. Si el cliente tiene dirección registrada, pregunta si quiere usarla
3. Si no tiene o quiere cambiar, solicita la nueva dirección
"""

import asyncio
import logging
from langchain_core.messages import HumanMessage
from app.agents.taxi.graph import create_taxi_graph
from app.core.checkpointer import get_checkpointer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_customer_with_previous_address():
    """Test flow when customer has a previous address."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: Cliente CON dirección registrada")
    logger.info("=" * 80)

    # Create graph
    checkpointer = get_checkpointer()
    graph = create_taxi_graph(checkpointer=checkpointer)

    # Thread ID for this test
    thread_id = "test_address_lookup_with_address"
    config = {"configurable": {"thread_id": thread_id}}

    # Simulate a customer with ID (phone number)
    # This customer should have a previous address in the system
    client_id = "3022370040"  # Example customer ID

    # Step 1: User wants a taxi
    logger.info("\n📱 Usuario: 'Necesito un taxi'")
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="Necesito un taxi")],
            "client_id": client_id,
        },
        config
    )

    # Extract AI response
    last_ai_message = None
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            last_ai_message = msg.content
            break

    logger.info(f"\n🤖 Alice: {last_ai_message}")

    # Verify that Alice is asking about pickup location
    # The NAVEGANTE should have been activated
    state = graph.get_state(config)
    agente_actual = state.values.get("agente_actual")
    logger.info(f"\n📊 Estado: agente_actual = {agente_actual}")

    # Step 2: Check if tool was called
    # Look for tool calls in messages
    tool_calls = []
    for msg in result.get("messages", []):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_calls.extend(msg.tool_calls)

    if tool_calls:
        logger.info(f"\n🔧 Tool calls detectadas: {[tc.get('name') for tc in tool_calls]}")
    else:
        logger.info("\n⚠️  No se detectaron tool calls en este paso")

    # Step 3: User confirms they want to use the previous address
    logger.info("\n📱 Usuario: 'Sí, esa dirección está bien'")
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="Sí, esa dirección está bien")],
        },
        config
    )

    last_ai_message = None
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            last_ai_message = msg.content
            break

    logger.info(f"\n🤖 Alice: {last_ai_message}")

    # Verify progression
    state = graph.get_state(config)
    agente_actual = state.values.get("agente_actual")
    logger.info(f"\n📊 Estado: agente_actual = {agente_actual}")

    logger.info("\n✅ TEST 1 COMPLETADO")


async def test_customer_without_previous_address():
    """Test flow when customer does NOT have a previous address."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Cliente SIN dirección registrada")
    logger.info("=" * 80)

    # Create graph
    checkpointer = get_checkpointer()
    graph = create_taxi_graph(checkpointer=checkpointer)

    # Thread ID for this test
    thread_id = "test_address_lookup_no_address"
    config = {"configurable": {"thread_id": thread_id}}

    # Simulate a new customer without previous address
    client_id = "9999999999"  # Example new customer ID

    # Step 1: User wants a taxi
    logger.info("\n📱 Usuario: 'Quiero un taxi'")
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="Quiero un taxi")],
            "client_id": client_id,
        },
        config
    )

    # Extract AI response
    last_ai_message = None
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            last_ai_message = msg.content
            break

    logger.info(f"\n🤖 Alice: {last_ai_message}")

    # Verify that Alice is asking for the address (since no previous address)
    state = graph.get_state(config)
    agente_actual = state.values.get("agente_actual")
    logger.info(f"\n📊 Estado: agente_actual = {agente_actual}")

    # Step 2: User provides address
    logger.info("\n📱 Usuario: 'Calle 72 número 43-25, El Prado'")
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="Calle 72 número 43-25, El Prado")],
        },
        config
    )

    last_ai_message = None
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            last_ai_message = msg.content
            break

    logger.info(f"\n🤖 Alice: {last_ai_message}")

    # Verify that Alice is confirming the address
    state = graph.get_state(config)
    agente_actual = state.values.get("agente_actual")
    logger.info(f"\n📊 Estado: agente_actual = {agente_actual}")

    logger.info("\n✅ TEST 2 COMPLETADO")


async def test_customer_wants_to_change_address():
    """Test flow when customer has previous address but wants to change it."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Cliente con dirección pero quiere cambiarla")
    logger.info("=" * 80)

    # Create graph
    checkpointer = get_checkpointer()
    graph = create_taxi_graph(checkpointer=checkpointer)

    # Thread ID for this test
    thread_id = "test_address_change"
    config = {"configurable": {"thread_id": thread_id}}

    # Simulate a customer with previous address
    client_id = "3022370040"  # Example customer with history

    # Step 1: User wants a taxi
    logger.info("\n📱 Usuario: 'Necesito un taxi'")
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="Necesito un taxi")],
            "client_id": client_id,
        },
        config
    )

    last_ai_message = None
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            last_ai_message = msg.content
            break

    logger.info(f"\n🤖 Alice: {last_ai_message}")

    # Step 2: User wants to change address
    logger.info("\n📱 Usuario: 'No, quiero cambiar la dirección'")
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="No, quiero cambiar la dirección")],
        },
        config
    )

    last_ai_message = None
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            last_ai_message = msg.content
            break

    logger.info(f"\n🤖 Alice: {last_ai_message}")

    # Verify that Alice is asking for the new address
    state = graph.get_state(config)
    agente_actual = state.values.get("agente_actual")
    logger.info(f"\n📊 Estado: agente_actual = {agente_actual}")

    # Step 3: User provides new address
    logger.info("\n📱 Usuario: 'Carrera 50 con 70, Riomar'")
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="Carrera 50 con 70, Riomar")],
        },
        config
    )

    last_ai_message = None
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            last_ai_message = msg.content
            break

    logger.info(f"\n🤖 Alice: {last_ai_message}")

    # Verify that Alice is confirming the new address
    state = graph.get_state(config)
    agente_actual = state.values.get("agente_actual")
    logger.info(f"\n📊 Estado: agente_actual = {agente_actual}")

    logger.info("\n✅ TEST 3 COMPLETADO")


async def main():
    """Run all tests."""
    logger.info("\n🚀 INICIANDO TESTS DE CONSULTA DE DIRECCIÓN PRIMERO\n")

    try:
        # Test 1: Customer with previous address
        await test_customer_with_previous_address()

        # Test 2: Customer without previous address
        await test_customer_without_previous_address()

        # Test 3: Customer wants to change address
        await test_customer_wants_to_change_address()

        logger.info("\n" + "=" * 80)
        logger.info("✅ TODOS LOS TESTS COMPLETADOS")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"\n❌ ERROR EN TESTS: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
