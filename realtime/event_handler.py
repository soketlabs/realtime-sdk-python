import asyncio
from typing import Callable, Any, Dict, List, Optional
from loguru import logger

class RealtimeEventHandler:
    """
    Inherited class for RealtimeAPI and RealtimeClient
    Adds basic event handling
    """

    def __init__(self):
        """
        Create a new RealtimeEventHandler instance
        """
        self.event_handlers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self.next_event_handlers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    def clear_event_handlers(self) -> bool:
        """
        Clears all event handlers
        """
        self.event_handlers.clear()
        self.next_event_handlers.clear()
        return True

    def on(self, event_name: str, callback: Callable[[Dict[str, Any]], None]) -> Callable[[Dict[str, Any]], None]:
        """
        Listen to specific events
        """
        self.event_handlers.setdefault(event_name, []).append(callback)
        return callback

    def on_next(self, event_name: str, callback: Callable[[Dict[str, Any]], None]) -> Callable[[Dict[str, Any]], None]:
        """
        Listen for the next event of a specified type
        """
        self.next_event_handlers.setdefault(event_name, []).append(callback)
        return callback

    def off(self, event_name: str, callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> bool:
        """
        Turns off event listening for specific events
        """
        if event_name in self.event_handlers:
            if callback:
                handlers = self.event_handlers[event_name]
                if callback not in handlers:
                    raise ValueError(f'Could not turn off specified event listener for "{event_name}": not found as a listener')
                handlers.remove(callback)
            else:
                del self.event_handlers[event_name]
        return True

    def off_next(self, event_name: str, callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> bool:
        """
        Turns off event listening for the next event of a specific type
        """
        if event_name in self.next_event_handlers:
            if callback:
                next_handlers = self.next_event_handlers[event_name]
                if callback not in next_handlers:
                    raise ValueError(f'Could not turn off specified next event listener for "{event_name}": not found as a listener')
                next_handlers.remove(callback)
            else:
                del self.next_event_handlers[event_name]
        return True

    async def wait_for_next(self, event_name: str, timeout: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Waits for the next event of a specific type and returns the payload
        """
        t0 = asyncio.get_event_loop().time()
        next_event = None

        def handler(event: Dict[str, Any]):
            nonlocal next_event
            next_event = event

        self.on_next(event_name, handler)

        while next_event is None:
            if timeout:
                t1 = asyncio.get_event_loop().time()
                if (t1 - t0) * 1000 > timeout:
                    return None
            await asyncio.sleep(0.001)

        return next_event

    def dispatch(self, event_name: str, event: Dict[str, Any]) -> bool:
        """
        Executes all events in the order they were added
        """
        logger.info("reahced1")
        handlers = list(self.event_handlers.get(event_name, []))
        logger.info("reahced2")
        for handler in handlers:
            handler(event)

        next_handlers = list(self.next_event_handlers.get(event_name, []))
        logger.info("reahced3")
        for next_handler in next_handlers:
            next_handler(event)

        self.next_event_handlers.pop(event_name, None)
        return True
