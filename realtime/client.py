import asyncio
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
            "turn_detection": None,
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

    async def _handle_item_done(self, event):
        """
        Handles completion of items, including tool calls.
        """
        item, delta = self.conversation.process_event(event)
        if item and item["status"] == "completed":
            self.dispatch("conversation.item.completed", {"item": item})
        if item and "tool" in item["formatted"]:
            await self._call_tool(item["formatted"]["tool"])

    async def _call_tool(self, tool):
        """
        Calls a tool with the provided arguments.
        """
        try:
            args = json.loads(tool["arguments"])
            tool_config = self.tools.get(tool["name"])
            if not tool_config:
                raise ValueError(f'Tool "{tool["name"]}" has not been added')

            result = await tool_config["handler"](args)
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

    async def connect(self):
        """
        Connects to the Realtime WebSocket API.
        """
        if self.is_connected():
            raise RuntimeError("Already connected, use disconnect() first.")
        await self.realtime.connect()
        self.update_session()
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

    def update_session(self, **kwargs):
        """
        Updates session configuration with the provided parameters.
        """
        self.session_config.update(kwargs)
        if self.realtime.is_connected():
            self.realtime.send("session.update", {"session": self.session_config})
        return True

    def send_user_message_content(self, content=None):
        """
        Sends a user message and generates a response.
        """
        content = content or []
        for c in content:
            if c["type"] == "input_audio" and isinstance(c["audio"], (bytes, bytearray)):
                c["audio"] = RealtimeUtils.array_buffer_to_base64(c["audio"])
        self.realtime.send("conversation.item.create", {
            "item": {
                "type": "message",
                "role": "user",
                "content": content,
            }
        })
        self.create_response()
        return True

    def create_response(self):
        """
        Forces a model response generation.
        """
        if not self.get_turn_detection_type() and self.input_audio_buffer:
            self.realtime.send("input_audio_buffer.commit")
            self.conversation.queue_input_audio(self.input_audio_buffer)
            self.input_audio_buffer = bytearray()
        self.realtime.send("response.create")
        return True

    def get_turn_detection_type(self):
        """
        Gets the active turn detection mode.
        """
        return self.session_config.get("turn_detection", {}).get("type", None)

    # Additional methods like `addTool`, `removeTool`, `waitForNextItem`, etc., can be implemented here
