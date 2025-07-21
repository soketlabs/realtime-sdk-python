import asyncio
import pyaudio
import base64
from loguru import logger
from realtime.client import RealtimeClient
import os
# import dotenv
from connect import ConversationHandler, AudioManager, audio_recorder

from dotenv import load_dotenv
# import os
load_dotenv()

# Initialize the OpenAI client

client = RealtimeClient(
        url="wss://api.soket.ai/v1/realtime",
        api_key=os.getenv("TENSOR_STUDIO_API_KEY"),  # Ensure your API key is set
        debug=True  # Set to True to enable debugging logs
    )
# Initialize the conversation handler and audio manager
audio_manager = AudioManager()
conversation_handler = ConversationHandler(audio_manager)

# Register the event handlers
client.on("conversation.updated", conversation_handler.on_conversation_updated)
client.on("conversation.item.completed", conversation_handler.on_conversation_item_completed)
client.on("error", conversation_handler.on_error)
client.on("conversation.interrupted", conversation_handler.on_conversation_interrupted)


async def main():
    recorder_task = None
    try:
        await client.connect()
        await client.update_session(
            instructions = '''
        You are Soket bot, a helpful assistant. Please respond clearly and concisely.
                ''',
                turn_detection = {
                    "type": "server_vad",
                    "threshold": 0.2,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 1000,
                }
        )
        logger.info("Connected to Realtime API.")
        message_content = [
                {
                    "type": "input_text",
                    "text": "तुम्हारा नाम क्या है?"
                }
            ]
        await client.send_user_message_content(content=message_content)
        logger.info("Message sent.")

        # Start audio recorder as a coroutine
        recorder_task = asyncio.create_task(audio_recorder(client))

        # Keep the connection alive to process events
        await asyncio.Event().wait()

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise e

    finally:
        # Disconnect from the API
        await client.disconnect()
        logger.info("Disconnected from Realtime API.")

        # Stop and clean up AudioManager
        await audio_manager.shutdown()

        # Cancel recorder_task if it's still running
        if recorder_task and not recorder_task.done():
            recorder_task.cancel()
            try:
                await recorder_task
            except asyncio.CancelledError:
                logger.info("Recorder task cancelled.")

if __name__ == "__main__":
    asyncio.run(main())



