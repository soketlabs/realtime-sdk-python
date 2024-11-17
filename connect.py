import asyncio
import pyaudio
import base64
from loguru import logger
from realtime.client import RealtimeClient  # Ensure you have the RealtimeClient implementation

class AudioManager:
    """
    Manages audio playback, allowing it to start and stop based on events.
    """
    def __init__(self):
        self.audio_queue = asyncio.Queue()
        self.playback_task = None
        self.audio = pyaudio.PyAudio()
        self.stream = None

    async def start_playback(self):
        """
        Starts the audio playback task if it's not already running.
        """
        if self.playback_task is None or self.playback_task.done():
            self.playback_task = asyncio.create_task(self.audio_player())
            logger.info("Audio playback task started.")

    async def stop_playback(self):
        """
        Stops the audio playback task by sending a stop signal and waiting for the task to finish.
        """
        if self.playback_task and not self.playback_task.done():
            await self.audio_queue.put(None)  # Send stop signal
            await self.playback_task
            self.playback_task = None
            logger.info("Audio playback task stopped.")

    async def audio_player(self):
        """
        Async function to retrieve PCM16 audio data from the queue and play it in real time.
        """
        # Audio settings
        FORMAT = pyaudio.paInt16  # PCM16 format
        CHANNELS = 1  # Mono audio
        RATE = 8000  # Sample rate in Hz (adjust based on your stream)
        CHUNK = 512  # Buffer size

        # Initialize PyAudio stream
        self.stream = self.audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)
        logger.info("Audio playback started.")

        try:
            while True:
                # Get audio data from the queue
                audio_data = await self.audio_queue.get()
                if audio_data is None:  # Stop signal
                    break
                # Use asyncio.to_thread to prevent blocking the event loop
                await asyncio.to_thread(self.stream.write, audio_data)
        except Exception as e:
            logger.error(f"Error during audio playback: {e}")
        finally:
            self.stream.stop_stream()
            self.stream.close()
            logger.info("Audio playback stopped.")

    async def enqueue_audio(self, audio_data):
        """
        Enqueue audio data for playback and ensure the playback task is running.
        """
        try:
            await self.audio_queue.put(audio_data)
            await self.start_playback()
        except Exception as e:
            logger.error(f"Failed to enqueue audio data: {e}")

    async def clear_audio_queue(self):
        """
        Clears all pending audio data from the queue.
        """
        try:
            while not self.audio_queue.empty():
                self.audio_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        logger.info("Audio queue cleared.")

    async def shutdown(self):
        """
        Clean up resources by stopping playback and terminating PyAudio.
        """
        await self.stop_playback()
        self.audio.terminate()
        logger.info("AudioManager shutdown complete.")

# Define the event handlers within AudioManager or pass the AudioManager instance to external handlers
class ConversationHandler:
    """
    Handles conversation events and interacts with AudioManager accordingly.
    """
    def __init__(self, audio_manager: AudioManager):
        self.audio_manager = audio_manager

    def on_conversation_updated(self, event):
        asyncio.create_task(self.handle_conversation_updated(event))

    def on_conversation_item_completed(self, event):
        item = event.get("item")
        if item and item["type"] == "function_call":
            print("Function call completed. Execute custom code here.")

    def on_error(self, event):
        logger.debug(event)

    def on_conversation_interrupted(self, event):
        asyncio.create_task(self.handle_conversation_interrupted(event))

    async def handle_conversation_updated(self, event):
        """
        Handles the 'conversation.updated' event by enqueuing audio data for playback.
        """
        item = event.get("item")
        delta = event.get("delta")
        if delta.get("audio", None) is not None:
            audio = delta["audio"]
            try:
                await self.audio_manager.enqueue_audio(audio)
            except Exception as e:
                logger.error(f"Failed to handle conversation updated event: {e}")
        if item and item["type"] == "function_call":
            print("Function call in progress...")
            if delta and "arguments" in delta:
                print(f"Arguments are being populated: {delta['arguments']}")

    async def handle_conversation_interrupted(self, event):
        """
        Handles the 'conversation.interrupted' event by stopping playback and clearing the audio queue.
        """
        print("Conversation interruption event")
        try:
            # **First, clear the audio queue to remove all pending audio data**
            await self.audio_manager.clear_audio_queue()
            # **Then, send the stop signal to terminate playback immediately**
            await self.audio_manager.stop_playback()
        except Exception as e:
            logger.error(f"Failed to handle conversation interrupted event: {e}")

async def audio_recorder(client):
    """
    Async function to record audio from the microphone and append it to the client.
    """
    # Audio settings
    FORMAT = pyaudio.paInt16  # PCM16 format
    CHANNELS = 1  # Mono audio
    RATE = 8000  # Sample rate in Hz
    CHUNK = 1024  # Buffer size

    # Initialize PyAudio
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    logger.info("Recording audio...")
    try:
        while True:
            # Use asyncio.to_thread to prevent blocking the event loop
            data = await asyncio.to_thread(stream.read, CHUNK, exception_on_overflow=False)
            # Append audio data to the client
            await client.append_input_audio(data)
            await asyncio.sleep(0)  # Yield control to the event loop
    except asyncio.CancelledError:
        logger.info("Audio recording stopped.")
    except Exception as e:
        logger.error(f"Error during audio recording: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        logger.info("Audio recorder terminated.")

async def main():
    # Initialize AudioManager
    audio_manager = AudioManager()

    # Initialize ConversationHandler with AudioManager
    conversation_handler = ConversationHandler(audio_manager)

    # Initialize RealtimeClient with necessary parameters
    client = RealtimeClient(
        url="wss://api.soket.ai/s2s",
        api_key="your-api-key-here",  # Replace with your actual API key
        debug=True  # Set to True to enable debugging logs
    )

    # Register the event handlers
    client.on("conversation.updated", conversation_handler.on_conversation_updated)
    client.on("conversation.item.completed", conversation_handler.on_conversation_item_completed)
    client.on("error", conversation_handler.on_error)
    client.on("conversation.interrupted", conversation_handler.on_conversation_interrupted)

    try:
        # Connect to the Realtime API
        await client.connect()
        await client.update_session(
            instructions = '''
                You are Arjun a loan service representative speaking to Tarun. The purpose of the conversation is to remind them about their overdue loan payment in the early delinquency stage and encourage timely payment to avoid penalties.

                    Loan Info:
                    1. Amount Due: 35000
                    2. Due Date: 1st November 2024
                    3. Payment link sent to the registered mobile number

                    Follow these instructions:
                    1. Only respond in Hindi.
                    2. Keep responses brief and direct; avoid long answers.
                    3. Address the customer by their name, confirm their identity, and inform them you are calling from Bajaj Finserv.
                    4. Politely inform them about their overdue amount and the original due date.
                    5. Explain the benefits of timely payment (e.g., avoiding penalties, maintaining credit score).
                    6. If needed, guide them on how to make the payment during the call.
                    7. If the customer denies engagement, always be polite and thank them for their time. Do not over-persuade.
                    8. Limit the conversation to three rounds and end by thanking them for their time.
                    9. If the user denies to pay the amount, just remind them that they will incur higher interest and late payment changes. If they are still not convinced, tell the that we can remove the late payment charges till date in good faith.

                    Conversation Structure:
                    1. Greet the customer and confirm their identity.
                    2. Politely inform them about the overdue payment details and due date.
                    3. Explain the benefits of timely payment and guide them through the payment process if required.
                    4. If they agree to pay, thank them and confirm the payment date.
                    5. If they are not interested, remain polite, do not insist further, and end with gratitude.

                    Key Benefits to Highlight:
                    1. Avoid late fees and penalties.
                    2. Maintain a healthy credit score.
                    3. Better eligibility for future loans.
                '''
        )
        logger.info("Connected to Realtime API.")

        # Wait for the session to be created
        # await client.wait_for_session_created()
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
        if not recorder_task.done():
            recorder_task.cancel()
            try:
                await recorder_task
            except asyncio.CancelledError:
                logger.info("Recorder task cancelled.")

# Run the asyncio event loop
if __name__ == "__main__":
    asyncio.run(main())
