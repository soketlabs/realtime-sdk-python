import asyncio
import json
from websockets import connect
from websockets.exceptions import ConnectionClosed
from typing import Optional, Dict, Any, Union
from .event_handler import RealtimeEventHandler
from .utils import RealtimeUtils


class RealtimeAPI(RealtimeEventHandler):
    """
    RealtimeAPI class for connecting and interacting with a WebSocket server.
    """

    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None, debug: bool = False):
        """
        Create a new RealtimeAPI instance
        """
        super().__init__()
        self.default_url = "wss://api.soket.ai/s2s"
        self.url = url or self.default_url
        self.api_key = api_key
        self.debug = debug
        self.connection_created = False
        self.ws = None

    def is_connected(self) -> bool:
        """
        Checks whether the WebSocket is connected.
        """
        return self.ws is not None and self.connection_created

    def log(self, *args):
        """
        Logs WebSocket activities if debug mode is enabled.
        """
        if self.debug:
            timestamp = asyncio.get_event_loop().time()
            log_messages = [f"[WebSocket/{timestamp}]"]
            for arg in args:
                if isinstance(arg, (dict, list)):
                    log_messages.append(json.dumps(arg, indent=2))
                else:
                    log_messages.append(str(arg))
            print(" ".join(log_messages))

    async def connect(self, model: str = "gpt-4o-realtime-preview-2024-10-01"):
        """
        Connects to the Realtime API WebSocket Server.
        """
        if self.is_connected():
            raise RuntimeError("Already connected")

        try:
            self.ws = await connect(
            f"{self.url}?model={model}",
            extra_headers={
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
        )
            self.log(f"Connected to {self.url}")
            self.connection_created = True
            asyncio.create_task(self.listen())
            return True

        except websockets.exceptions.ConnectionClosed:
            self.connection_created = False 
        except Exception as e:
            self.log(f"Failed to connect: {e}")
            raise RuntimeError(f"Could not connect to {self.url}") from e

    async def disconnect(self):
        """
        Disconnects from the Realtime API server.
        """
        if self.ws:
            await self.ws.close()
            self.ws = None
            self.connection_created = False
            self.log("Disconnected from the server")

    async def listen(self):
        """
        Listens for incoming WebSocket messages.
        """
        try:
            async for message in self.ws:
                data = json.loads(message)
                self.receive(data["type"], data)
        except ConnectionClosed as e:
            self.log(f"WebSocket closed: {e}")
            await self.disconnect()

    def receive(self, event_name: str, event: Dict[str, Any]):
        """
        Handles received WebSocket events.
        """
        self.log("Received:", event_name, event)
        self.dispatch(f"server.{event_name}", event)
        self.dispatch("server.*", event)

    def send(self, event_name: str, data: Optional[Dict[str, Any]] = None):
        """
        Sends an event to the WebSocket server.
        """
        if not self.is_connected():
            raise RuntimeError("RealtimeAPI is not connected")

        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        event = {
            "event_id": RealtimeUtils.generate_id("evt_"),
            "type": event_name,
            **data,
        }
        self.dispatch(f"client.{event_name}", event)
        self.dispatch("client.*", event)
        self.log("Sent:", event_name, event)
        asyncio.create_task(self.ws.send(json.dumps(event)))
