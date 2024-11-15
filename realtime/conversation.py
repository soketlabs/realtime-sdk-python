import numpy as np
import copy
import base64

from .utils import RealtimeUtils
from loguru import logger

class RealtimeConversation:
    """
    RealtimeConversation holds conversation history and performs event validation for RealtimeAPI.
    """

    def __init__(self):
        self.default_frequency = 24000  # 24,000 Hz
        self.EventProcessors = {
        "conversation.item.created": self._process_item_created,
        "conversation.item.truncated": self._process_item_truncated,
        "conversation.item.deleted": self._process_item_deleted,
        "conversation.item.input_audio_transcription.completed": self._process_audio_transcription_completed,
        "input_audio_buffer.speech_started": self._process_speech_started,
        "input_audio_buffer.speech_stopped": self._process_speech_stopped,
        "response.created": self._process_response_created,
        "response.output_item.added": self._process_output_item_added,
        "response.output_item.done": self._process_output_item_done,
        "response.content_part.added": self._process_content_part_added,
        "response.audio_transcript.delta": self._process_audio_transcript_delta,
        "response.audio.delta": self._process_audio_delta,
        "response.text.delta": self._process_text_delta,
        "response.function_call_arguments.delta": self._process_function_call_arguments_delta,
    }
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

    def _process_item_created(self, event):
        logger.info(event)
        item = event['item']
        new_item = copy.deepcopy(item)
        if new_item['id'] not in self.item_lookup:
            self.item_lookup[new_item['id']] = new_item
            self.items.append(new_item)

        new_item['formatted'] = {
            'audio': np.array([], dtype=np.int16),
            'text': '',
            'transcript': ''
        }

        # If we have a speech item, can populate audio
        if new_item['id'] in self.queued_speech_items:
            new_item['formatted']['audio'] = self.queued_speech_items[new_item['id']]['audio']
            del self.queued_speech_items[new_item['id']]  # free up some memory

        # Populate formatted text if it comes out on creation
        if new_item.get('content'):
            text_content = [c for c in new_item['content'] if c['type'] in ['text', 'input_text']]
            for content in text_content:
                new_item['formatted']['text'] += content['text']

        # If we have a transcript item, can pre-populate transcript
        if new_item['id'] in self.queued_transcript_items:
            new_item['formatted']['transcript'] = self.queued_transcript_items[new_item['id']]['transcript']
            del self.queued_transcript_items[new_item['id']]

        if new_item['type'] == 'message':
            if new_item['role'] == 'user':
                new_item['status'] = 'completed'
                if self.queued_input_audio is not None:
                    new_item['formatted']['audio'] = self.queued_input_audio
                    self.queued_input_audio = None
            else:
                new_item['status'] = 'in_progress'
        elif new_item['type'] == 'function_call':
            new_item['formatted']['tool'] = {
                'type': 'function',
                'name': new_item['name'],
                'call_id': new_item['call_id'],
                'arguments': '',
            }
            new_item['status'] = 'in_progress'
        elif new_item['type'] == 'function_call_output':
            new_item['status'] = 'completed'
            new_item['formatted']['output'] = new_item['output']

        logger.debug(new_item)

        return new_item, None

    def _process_item_truncated(self, event):
        item_id = event['item_id']
        audio_end_ms = event['audio_end_ms']
        item = self.item_lookup.get(item_id)
        if not item:
            raise ValueError(f'item.truncated: Item "{item_id}" not found')
        end_index = int((audio_end_ms * self.default_frequency) / 1000)
        item['formatted']['transcript'] = ''
        item['formatted']['audio'] = item['formatted']['audio'][:end_index]
        return item, None

    def _process_item_deleted(self, event):
        item_id = event['item_id']
        item = self.item_lookup.get(item_id)
        if not item:
            raise ValueError(f'item.deleted: Item "{item_id}" not found')
        del self.item_lookup[item['id']]
        if item in self.items:
            self.items.remove(item)
        return item, None

    def _process_audio_transcription_completed(self, event):
        item_id = event['item_id']
        content_index = event['content_index']
        transcript = event['transcript']
        item = self.item_lookup.get(item_id)
        formatted_transcript = transcript or ' '
        if not item:
            # We can receive transcripts in VAD mode before item.created
            # This happens specifically when audio is empty
            self.queued_transcript_items[item_id] = {'transcript': formatted_transcript}
            return item, None
        else:
            item['content'][content_index]['transcript'] = transcript
            item['formatted']['transcript'] = formatted_transcript
            return item, {'transcript': transcript}

    def _process_speech_started(self, event):
        item_id = event['item_id']
        audio_start_ms = event['audio_start_ms']
        self.queued_speech_items[item_id] = {'audio_start_ms': audio_start_ms}
        return None, None

    def _process_speech_stopped(self, event, input_audio_buffer):
        item_id = event['item_id']
        audio_end_ms = event['audio_end_ms']
        if item_id not in self.queued_speech_items:
            self.queued_speech_items[item_id] = {'audio_start_ms': audio_end_ms}
        speech = self.queued_speech_items[item_id]
        speech['audio_end_ms'] = audio_end_ms
        if input_audio_buffer is not None:
            start_index = int((speech['audio_start_ms'] * self.default_frequency) / 1000)
            end_index = int((speech['audio_end_ms'] * self.default_frequency) / 1000)
            speech['audio'] = input_audio_buffer[start_index:end_index]
        return None, None

    def _process_response_created(self, event):
        response = event['response']
        if response['id'] not in self.response_lookup:
            self.response_lookup[response['id']] = response
            self.responses.append(response)
        return None, None

    def _process_output_item_added(self, event):
        response_id = event['response_id']
        item = event['item']
        response = self.response_lookup.get(response_id)
        if not response:
            raise ValueError(f'response.output_item.added: Response "{response_id}" not found')
        response['output'].append(item['id'])
        return None, None

    def _process_output_item_done(self, event):
        item = event['item']
        if not item:
            raise ValueError('response.output_item.done: Missing "item"')
        found_item = self.item_lookup.get(item['id'])
        if not found_item:
            raise ValueError(f'response.output_item.done: Item "{item["id"]}" not found')
        found_item['status'] = item['status']
        return found_item, None

    def _process_content_part_added(self, event):
        item_id = event['item_id']
        part = event['part']
        item = self.item_lookup.get(item_id)
        if not item:
            raise ValueError(f'response.content_part.added: Item "{item_id}" not found')
        item['content'].append(part)
        return item, None

    def _process_audio_transcript_delta(self, event):
        item_id = event['item_id']
        content_index = event['content_index']
        delta = event['delta']
        item = self.item_lookup.get(item_id)
        if not item:
            raise ValueError(f'response.audio_transcript.delta: Item "{item_id}" not found')
        item['content'][content_index]['transcript'] += delta
        item['formatted']['transcript'] += delta
        return  item, {'transcript': delta}

    def _process_audio_delta(self, event):
        item_id = event['item_id']
        content_index = event['content_index']
        delta = event['delta']
        item = self.item_lookup.get(item_id)
        if not item:
            raise ValueError(f'response.audio.delta: Item "{item_id}" not found')
        # Decode base64 string to bytes
        delta_bytes = base64.b64decode(delta)
        append_values = np.frombuffer(delta_bytes, dtype=np.int16)
        item['formatted']['audio'] = np.concatenate((item['formatted']['audio'], append_values))
        return item, {'audio': append_values}

    def _process_text_delta(self, event):
        item_id = event['item_id']
        content_index = event['content_index']
        delta = event['delta']
        item = self.item_lookup.get(item_id)
        if not item:
            raise ValueError(f'response.text.delta: Item "{item_id}" not found')
        item['content'][content_index]['text'] += delta
        item['formatted']['text'] += delta
        return item, {'text': delta}

    def _process_function_call_arguments_delta(self, event):
        item_id = event['item_id']
        delta = event['delta']
        item = self.item_lookup.get(item_id)
        if not item:
            raise ValueError(f'response.function_call_arguments.delta: Item "{item_id}" not found')
        item['arguments'] += delta
        item['formatted']['tool']['arguments'] += delta
        return item,  {'arguments': delta}