"""Script de debug para verificar estructura de tokens en LangChain."""

import logging
from app.core.llm import get_llm
from langchain_core.messages import HumanMessage

# Configurar logging para ver todos los detalles
logging.basicConfig(level=logging.DEBUG)

# Crear LLM
llm = get_llm()

# Hacer una invocación simple
print("\n" + "="*80)
print("TESTING LLM TOKEN TRACKING")
print("="*80 + "\n")

messages = [HumanMessage(content="Di hola en español")]
result = llm.invoke(messages)

print(f"\n[TOKEN DEBUG] Result type: {type(result)}")
print(f"[TOKEN DEBUG] Result class: {result.__class__.__name__}")
print(f"\n[TOKEN DEBUG] Available attributes:")
for attr in dir(result):
    if not attr.startswith('_'):
        print(f"  - {attr}")

# Check usage_metadata
if hasattr(result, 'usage_metadata'):
    print(f"\n[FOUND] usage_metadata:")
    print(f"   {result.usage_metadata}")
    if result.usage_metadata:
        print(f"\n   Type: {type(result.usage_metadata)}")
        if hasattr(result.usage_metadata, '__dict__'):
            print(f"   Dict: {result.usage_metadata.__dict__}")

# Check response_metadata
if hasattr(result, 'response_metadata'):
    print(f"\n[FOUND] response_metadata:")
    print(f"   {result.response_metadata}")
    if 'token_usage' in result.response_metadata:
        print(f"\n   token_usage: {result.response_metadata['token_usage']}")

# Full result
print(f"\n[RESULT] Full result:")
print(f"   Content: {result.content}")
print(f"   ID: {result.id if hasattr(result, 'id') else 'N/A'}")

print("\n" + "="*80)
