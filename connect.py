import asyncio
from realtime.client import RealtimeClient  # Ensure you have the RealtimeClient implementation

# Define the event handlers
def on_conversation_updated(event):
    item = event.get("item")
    delta = event.get("delta")
    if item and item["type"] == "function_call":
        print("Function call in progress...")
        if delta and "arguments" in delta:
            print(f"Arguments are being populated: {delta['arguments']}")

def on_conversation_item_completed(event):
    item = event.get("item")
    if item and item["type"] == "function_call":
        print("Function call completed. Execute custom code here.")

async def main():
    # Initialize RealtimeClient with necessary parameters
    client = RealtimeClient(
        url="wss://api.soket.ai/s2s",
        api_key="your-api-key-here",  # Replace with your actual API key
        debug=True  # Set to True to enable debugging logs
    )


    # Register the event handlers
    client.on("conversation.updated", on_conversation_updated)
    client.on("conversation.item.completed", on_conversation_item_completed)

    try:
        # Connect to the Realtime API
        await client.connect()
        print("Connected to Realtime API.")

        # Wait for the session to be created
        #await client.wait_for_session_created()
        print("Session created successfully.")

        # Example: Send a user message
        message_content = [
            {
                "type": "input_text",
                "text": "Hello, how can I help you?"
            }
        ]
        await client.send_user_message_content(content=message_content)
        print("Message sent.")

        # Keep the connection alive to process events
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        # Disconnect from the API
        await client.disconnect()
        print("Disconnected from Realtime API.")

# Run the asyncio event loop
asyncio.run(main())
