import numpy as np
from .utils import RealtimeUtils


class RealtimeConversation:
    """
    RealtimeConversation holds conversation history and performs event validation for RealtimeAPI.
    """

    def __init__(self):
        self.default_frequency = 24000  # 24,000 Hz
        self.clear()

    def clear(self) -> bool:
        """
        Clears the conversation history and resets to default.
        """
        self.item_lookup = {}
        self.items = []
        self.response_lookup = {}
        self.responses = []
        self.queued_speech_items = {}
        self.queued_transcript_items = {}
        self.queued_input_audio = None
        return True

    def queue_input_audio(self, input_audio: np.ndarray) -> np.ndarray:
        """
        Queue input audio for manual speech event.
        """
        self.queued_input_audio = input_audio
        return input_audio

    def get_item(self, item_id: str) -> dict:
        """
        Retrieves an item by its ID.
        """
        return self.item_lookup.get(item_id, None)

    def get_items(self) -> list:
        """
        Retrieves all items in the conversation.
        """
        return list(self.items)

    def process_event(self, event: dict, *args):
        """
        Process an event from the WebSocket server and compose items.
        """
        if "event_id" not in event:
            raise ValueError(f"Missing 'event_id' on event: {event}")
        if "type" not in event:
            raise ValueError(f"Missing 'type' on event: {event}")

        event_processor = self.EventProcessors.get(event["type"])
        if not event_processor:
            raise ValueError(f"Missing event processor for '{event['type']}'")

        return event_processor(event, *args)

    def _truncate_audio(self, audio, audio_end_ms):
        """
        Helper method to truncate audio based on duration in milliseconds.
        """
        end_index = int((audio_end_ms * self.default_frequency) / 1000)
        return audio[:end_index]

    EventProcessors = {
        "conversation.item.created": lambda self, event: self._process_item_created(event),
        "conversation.item.truncated": lambda self, event: self._process_item_truncated(event),
        "conversation.item.deleted": lambda self, event: self._process_item_deleted(event),
        "conversation.item.input_audio_transcription.completed": lambda self, event: self._process_audio_transcription_completed(event),
        "input_audio_buffer.speech_started": lambda self, event: self._process_speech_started(event),
        "input_audio_buffer.speech_stopped": lambda self, event, input_audio: self._process_speech_stopped(event, input_audio),
        "response.created": lambda self, event: self._process_response_created(event),
        "response.output_item.added": lambda self, event: self._process_output_item_added(event),
        "response.output_item.done": lambda self, event: self._process_output_item_done(event),
        "response.content_part.added": lambda self, event: self._process_content_part_added(event),
        "response.audio_transcript.delta": lambda self, event: self._process_audio_transcript_delta(event),
        "response.audio.delta": lambda self, event: self._process_audio_delta(event),
        "response.text.delta": lambda self, event: self._process_text_delta(event),
        "response.function_call_arguments.delta": lambda self, event: self._process_function_call_arguments_delta(event),
    }

    def _process_item_created(self, event):
        # Similar logic as the JavaScript `conversation.item.created` event
        pass

    def _process_item_truncated(self, event):
        # Process truncation logic
        pass

    def _process_item_deleted(self, event):
        # Process deletion logic
        pass

    def _process_audio_transcription_completed(self, event):
        # Handle completed audio transcription
        pass

    def _process_speech_started(self, event):
        # Handle speech started event
        pass

    def _process_speech_stopped(self, event, input_audio):
        # Handle speech stopped event
        pass

    def _process_response_created(self, event):
        # Handle response creation
        pass

    def _process_output_item_added(self, event):
        # Handle output item addition
        pass

    def _process_output_item_done(self, event):
        # Handle marking output items as done
        pass

    def _process_content_part_added(self, event):
        # Add content part to response
        pass

    def _process_audio_transcript_delta(self, event):
        # Process audio transcript delta updates
        pass

    def _process_audio_delta(self, event):
        # Process audio delta updates
        pass

    def _process_text_delta(self, event):
        # Process text delta updates
        pass

    def _process_function_call_arguments_delta(self, event):
        # Process function call arguments delta updates
        pass
