import asyncio
import pyaudio
import base64
from loguru import logger
from realtime.client import RealtimeClient  # Ensure you have the RealtimeClient implementation

# Async playback logic
async def audio_player(audio_queue):
    """
    Async function to retrieve PCM16 audio data from the queue, decode it, and play it in real time.
    """
    # Audio settings
    FORMAT = pyaudio.paInt16  # PCM16 format
    CHANNELS = 1  # Mono audio
    RATE = 22050  # Sample rate in Hz (adjust based on your stream)
    CHUNK = 512  # Buffer size

    # Initialize PyAudio
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)

    print("Audio playback started.")
    try:
        while True:
            # Get audio data from the queue
            audio_data = await audio_queue.get()
            if audio_data is None:  # Stop signal
                break
            logger.info(len(audio_data))
            stream.write(audio_data)  # Write audio data to the output stream
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        print("Audio playback stopped.")

# Define the event handlers
def on_conversation_updated(event, audio_queue):
    # logger.info(event)
    item = event.get("item")
    delta = event.get("delta")
    if delta.get("audio", None) is not None:
        audio = delta["audio"]
        try:
            # Put decoded audio data in the queue
            logger.info(len(audio))
            audio_queue.put_nowait(audio)
        except Exception as e:
            logger.error(f"Failed to decode audio data: {e}")
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

    audio_queue = asyncio.Queue()

    # Register the event handlers
    client.on("conversation.updated", lambda event: on_conversation_updated(event, audio_queue))
    client.on("conversation.item.completed", on_conversation_item_completed)

    try:
        # Start audio playback as a coroutine
        playback_task = asyncio.create_task(audio_player(audio_queue))

        # Connect to the Realtime API
        await client.connect()
        logger.info("Connected to Realtime API.")

        # Wait for the session to be created
        #await client.wait_for_session_created()
        logger.info("Session created successfully.")

        # Example: Send a user message
        message_content = [
            {
                "type": "input_text",
                "text": "तुम्हारा नाम क्या है?"
            }
        ]
        await client.send_user_message_content(content=message_content)
        logger.info("Message sent.")

        # Keep the connection alive to process events
        await asyncio.Event().wait()

    except Exception as e:
        raise e

    finally:
        # Disconnect from the API
        await client.disconnect()
        print("Disconnected from Realtime API.")
        await audio_queue.put(None)  # Send stop signal to audio player
        await playback_task  # Wait for playback task to complete

# Run the asyncio event loop
if __name__ == "__main__":
    asyncio.run(main())
