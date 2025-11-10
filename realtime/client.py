import json
import asyncio
import base64
from loguru import logger

from .event_handler import RealtimeEventHandler
from .api import RealtimeAPI
from .conversation import RealtimeConversation
from .utils import RealtimeUtils


class RealtimeClient(RealtimeEventHandler):
    """
    RealtimeClient Class for handling real-time conversations with API and WebSocket integration.
    """

    def __init__(self, url=None, api_key=None, dangerously_allow_api_key_in_browser=False, debug=False):
        super().__init__()
        self.default_session_config = {
            "modalities": ["text", "audio"],
            "instructions": "",
            "voice": "verse",
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": None,
            "turn_detection": {},
            "tools": [],
            "tool_choice": "auto",
            "temperature": 0.8,
            "max_response_output_tokens": 4096,
        }
        self.session_config = {}
        self.transcription_models = [{"model": "whisper-1"}]
        self.default_server_vad_config = {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 200,
        }
        self.realtime = RealtimeAPI(url=url, api_key=api_key, debug=debug)
        self.conversation = RealtimeConversation()
        self._reset_config()
        self._add_api_event_handlers()

    def _reset_config(self):
        """
        Resets sessionConfig and conversationConfig to defaults.
        """
        self.session_created = False
        self.tools = {}
        self.session_config = self.default_session_config.copy()
        self.input_audio_buffer = bytearray()
        return True

    def _add_api_event_handlers(self):
        """
        Sets up event handlers for API and conversation control flow.
        """
        # Event logging handlers
        self.realtime.on("client.*", self._log_event("client"))
        self.realtime.on("server.*", self._log_event("server"))

        # Session created handler
        self.realtime.on("server.session.created", self._on_session_created)

        # Conversation event handlers
        self.realtime.on("server.conversation.item.created", self._handle_item_created)
        self.realtime.on("server.conversation.item.truncated", self._handle_item_updated)
        self.realtime.on("server.conversation.item.deleted", self._handle_item_updated)
        self.realtime.on("server.conversation.item.input_audio_transcription.completed", self._handle_item_updated)
        self.realtime.on("server.response.audio_transcript.delta", self._handle_item_updated)
        self.realtime.on("server.response.audio.delta", self._handle_item_updated)
        self.realtime.on("server.response.text.delta", self._handle_item_updated)
        self.realtime.on("server.response.function_call_arguments.delta", self._handle_item_updated)
        self.realtime.on("server.response.output_item.done", self._handle_item_done)

        # Added missing event handlers for speech start and end
        self.realtime.on("server.input_audio_buffer.speech_started", self._handle_speech_started)
        self.realtime.on("server.input_audio_buffer.speech_stopped", self._handle_speech_stopped)

        return True

    def _log_event(self, source):
        """
        Logs events from client or server.
        """
        def handler(event):
            self.dispatch("realtime.event", {
                "time": asyncio.get_event_loop().time(),
                "source": source,
                "event": event,
            })
        return handler

    def _on_session_created(self, event):
        """
        Marks the session as created.
        """
        self.session_created = True

    def _handle_item_created(self, event):
        """
        Handles item creation events.
        """
        item, delta = self.conversation.process_event(event)
        self.dispatch("conversation.item.appended", {"item": item})
        if item and item["status"] == "completed":
            self.dispatch("conversation.item.completed", {"item": item})

    def _handle_item_updated(self, event, *args):
        """
        Handles updates to items in the conversation.
        """
        item, delta = self.conversation.process_event(event, *args)
        self.dispatch("conversation.updated", {"item": item, "delta": delta})

    def _handle_item_done(self, event):
        """
        Handles completion of items, including tool calls.
        """
        item, delta = self.conversation.process_event(event)
        if item and item["status"] == "completed":
            self.dispatch("conversation.item.completed", {"item": item})
        if item and "tool" in item["formatted"]:
            self._call_tool(item["formatted"]["tool"])

    def _call_tool(self, tool):
        """
        Calls a tool with the provided arguments.
        """
        try:
            args = json.loads(tool["arguments"])
            tool_config = self.tools.get(tool["name"])
            if not tool_config:
                raise ValueError(f'Tool "{tool["name"]}" has not been added')

            result = tool_config["handler"](args)
            self.realtime.send("conversation.item.create", {
                "item": {
                    "type": "function_call_output",
                    "call_id": tool["call_id"],
                    "output": json.dumps(result),
                }
            })
        except Exception as e:
            self.realtime.send("conversation.item.create", {
                "item": {
                    "type": "function_call_output",
                    "call_id": tool["call_id"],
                    "output": json.dumps({"error": str(e)}),
                }
            })

    # Added missing event handlers

    def _handle_speech_started(self, event):
        """
        Handles speech started events.
        """
        item, delta = self.conversation.process_event(event)
        self.dispatch('conversation.interrupted', {})

    def _handle_speech_stopped(self, event):
        """
        Handles speech stopped events.
        """
        item, delta = self.conversation.process_event(event, self.input_audio_buffer)

    # Existing methods continue...

    async def connect(self):
        """
        Connects to the Realtime WebSocket API.
        """
        if self.is_connected():
            raise RuntimeError("Already connected, use disconnect() first.")
        await self.realtime.connect()
        await self.update_session()

        return True

    async def disconnect(self):
        """
        Disconnects from the API and clears conversation history.
        """
        self.session_created = False
        if self.is_connected():
            await self.realtime.disconnect()
        self.conversation.clear()

    def is_connected(self) -> bool:
        """
        Checks whether the realtime WebSocket connection is active.
        """
        return self.realtime.is_connected()
        
    async def wait_for_session_created(self):
        """
        Waits for the 'session.created' event to be triggered.
        """
        if not self.is_connected():
            raise RuntimeError("Not connected. Please use the connect() method first.")
        
        while not self.session_created:
            await asyncio.sleep(0.1)
        return True

    async def update_session(self, **kwargs):
        """
        Updates session configuration with the provided parameters.
        """
        self.session_config.update(kwargs)
        if self.realtime.is_connected():
            await self.realtime.send("session.update", {"session": self.session_config})
        return True

    async def send_user_message_content(self, content=None):
        """
        Sends a user message and generates a response.
        """
        content = content or []
        for c in content:
            if c["type"] == "input_audio" and isinstance(c["audio"], (bytes, bytearray)):
                c["audio"] = RealtimeUtils.array_buffer_to_base64(c["audio"])

        await self.realtime.send("conversation.item.create", {
            "item": {
                "type": "message",
                "role": "user",
                "content": content,
            }
        })
        await self.create_response()
        return True

    async def create_response(self):
        """
        Forces a model response generation.
        """
        if not self.get_turn_detection_type() and self.input_audio_buffer:
            await self.realtime.send("input_audio_buffer.commit")
            self.conversation.queue_input_audio(self.input_audio_buffer)
            self.input_audio_buffer = bytearray()
        await self.realtime.send("response.create")
        return True

    def get_turn_detection_type(self):
        """
        Gets the active turn detection mode.
        """
        return self.session_config.get("turn_detection", {}).get("type", None)
        
    def add_tool(self, definition, handler):
        if not definition.get('name'):
            raise Exception('Missing tool name in definition')
        name = definition.get('name')
        if name in self.tools:
            raise Exception(f'Tool "{name}" already added. Please use .remove_tool("{name}") before trying to add again.')
        if not callable(handler):
            raise Exception(f'Tool "{name}" handler must be a function')
        self.tools[name] = {'definition': definition, 'handler': handler}
        t = []
        for k, v in self.tools.items():
            t.append(v)
        self.update_session({"tools": t})
        return self.tools[name]

    def remove_tool(self, name):
        if name not in self.tools:
            raise Exception(f'Tool "{name}" does not exist, cannot be removed.')
        del self.tools[name]
        return True
        
    def delete_item(self, item_id):
        asyncio.create_task(self.realtime.send('conversation.item.delete', {'item_id': item_id}))
        return True
        
    async def append_input_audio(self, array_buffer):
        if len(array_buffer) > 0:
            await self.realtime.send('input_audio_buffer.append', {
                'audio': base64.b64encode(array_buffer).decode('utf-8')
            })
            self.input_audio_buffer += array_buffer
        return True

    # Added missing functions below

    def reset(self):
        """
        Resets the client instance: disconnects and clears active config.
        """
        asyncio.create_task(self.disconnect())
        self.clear_event_handlers()
        self.realtime.clear_event_handlers()
        self._reset_config()
        self._add_api_event_handlers()
        return True

    def cancel_response(self, item_id=None, sample_count=0):
        """
        Cancels the ongoing server generation and truncates ongoing generation, if applicable.
        """
        if not item_id:
            asyncio.create_task(self.realtime.send('response.cancel'))
            return {'item': None}
        else:
            item = self.conversation.get_item(item_id)
            if not item:
                raise Exception(f'Could not find item "{item_id}"')
            if item['type'] != 'message':
                raise Exception('Can only cancel_response messages with type "message"')
            elif item['role'] != 'assistant':
                raise Exception('Can only cancel_response messages with role "assistant"')
            asyncio.create_task(self.realtime.send('response.cancel'))
            audio_index = next((i for i, c in enumerate(item['content']) if c['type'] == 'audio'), -1)
            if audio_index == -1:
                raise Exception('Could not find audio on item to cancel')
            asyncio.create_task(self.realtime.send('conversation.item.truncate', {
                'item_id': item_id,
                'content_index': audio_index,
                'audio_end_ms': int((sample_count / self.conversation.default_frequency) * 1000)
            }))
            return {'item': item}

    async def wait_for_next_item(self):
        """
        Utility for waiting for the next 'conversation.item.appended' event.
        """
        event = await self.wait_for_next('conversation.item.appended')
        item = event.get('item') if event else None
        return {'item': item}

    async def wait_for_next_completed_item(self):
        """
        Utility for waiting for the next 'conversation.item.completed' event.
        """
        event = await self.wait_for_next('conversation.item.completed')
        item = event.get('item') if event else None
        return {'item': item}
