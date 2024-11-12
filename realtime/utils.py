import base64
import random
from typing import Union
import numpy as np


class RealtimeUtils:
    """
    Basic utilities for the RealtimeAPI
    """

    @staticmethod
    def float_to_16_bit_pcm(float32_array: np.ndarray) -> memoryview:
        """
        Converts Float32Array of amplitude data to ArrayBuffer in Int16Array format
        """
        int16_array = np.clip(float32_array, -1, 1) * (2**15 - 1)
        int16_array = int16_array.astype(np.int16)
        return memoryview(int16_array)

    @staticmethod
    def base64_to_array_buffer(base64_string: str) -> memoryview:
        """
        Converts a base64 string to an ArrayBuffer
        """
        binary_data = base64.b64decode(base64_string)
        return memoryview(binary_data)

    @staticmethod
    def array_buffer_to_base64(array_buffer: Union[bytes, memoryview, np.ndarray]) -> str:
        """
        Converts an ArrayBuffer, Int16Array, or Float32Array to a base64 string
        """
        if isinstance(array_buffer, np.ndarray) and array_buffer.dtype == np.float32:
            array_buffer = RealtimeUtils.float_to_16_bit_pcm(array_buffer).tobytes()
        elif isinstance(array_buffer, np.ndarray) and array_buffer.dtype == np.int16:
            array_buffer = array_buffer.tobytes()
        elif isinstance(array_buffer, memoryview):
            array_buffer = array_buffer.tobytes()

        binary_data = base64.b64encode(array_buffer).decode('ascii')
        return binary_data

    @staticmethod
    def merge_int16_arrays(left: Union[bytes, np.ndarray], right: Union[bytes, np.ndarray]) -> np.ndarray:
        """
        Merge two Int16Arrays from Int16Arrays or ArrayBuffers
        """
        if isinstance(left, bytes):
            left = np.frombuffer(left, dtype=np.int16)
        if isinstance(right, bytes):
            right = np.frombuffer(right, dtype=np.int16)

        if not isinstance(left, np.ndarray) or left.dtype != np.int16:
            raise ValueError("Left item must be Int16Array (numpy array with dtype=int16)")
        if not isinstance(right, np.ndarray) or right.dtype != np.int16:
            raise ValueError("Right item must be Int16Array (numpy array with dtype=int16)")

        return np.concatenate((left, right))

    @staticmethod
    def generate_id(prefix: str, length: int = 21) -> str:
        """
        Generates an ID to send with events and messages
        """
        chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        random_str = ''.join(random.choice(chars) for _ in range(length - len(prefix)))
        return f"{prefix}{random_str}"
