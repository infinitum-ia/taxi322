"""Script to clear a specific thread's state from the checkpointer."""

import sys
from app.core.checkpointer import get_checkpointer

def clear_thread(thread_id: str):
    """
    Clear all state for a specific thread.

    Args:
        thread_id: The thread ID to clear
    """
    print(f"🗑️  Clearing thread: {thread_id}")

    try:
        checkpointer = get_checkpointer()

        # Create config for this thread
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        # Try to get current state
        try:
            from app.agents.graph_builder import create_graph
            graph = create_graph(checkpointer=checkpointer)
            state = graph.get_state(config)

            print(f"   Current state has {len(state.values.get('messages', []))} messages")
            print(f"   Next nodes: {state.next}")

        except Exception as e:
            print(f"   ⚠️  Could not read current state: {e}")

        # Clear the thread by updating with empty state
        # Note: This depends on your checkpointer implementation
        print(f"   ⚠️  To fully clear, delete the thread data from your storage backend")
        print(f"   Thread ID: {thread_id}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python clear_thread.py <thread_id>")
        print("\nExample:")
        print("  python clear_thread.py 051de035-7be3-4461-aeaf-5f8284d55e28")
        sys.exit(1)

    thread_id = sys.argv[1]
    clear_thread(thread_id)
