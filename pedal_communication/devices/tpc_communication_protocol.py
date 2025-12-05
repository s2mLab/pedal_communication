from enum import Enum
import struct

import numpy as np

from .generic_communication_protocol import GenericRequestProtocol
from ..misc import classproperty


class TcpRequestProtocol(GenericRequestProtocol):
    class RequestType(Enum):
        NORMAL = 0
        FAST = 1

    class Command(Enum):
        FGx = [0, 0]
        FGy = [0, 1]
        FGz = [0, 2]
        FDx = [0, 3]
        FDy = [0, 4]
        FDz = [0, 5]
        MGx = [2, 0]
        MGy = [2, 1]
        MGz = [2, 2]
        MDx = [2, 3]
        MDy = [2, 4]
        MDz = [2, 5]
        TG = [4, 0]
        TD = [4, 1]
        AG = [6, 0]
        AD = [6, 1]

    def __init__(self, request_type: RequestType | None = None, command: list[Command] | None = None):
        if command is not None and request_type is not None:
            raise ValueError("Specify either command or request_type, not both.")
        if command is None:
            if request_type == self.RequestType.NORMAL:
                self._commands = [[i, j] for i in range(43) for j in range(10)]
            elif request_type == self.RequestType.FAST:
                self._commands = [[i, j] for i in range(43) for j in range(10)]
            else:
                raise ValueError("Unsupported request type.")
        else:
            self._commands = [cmd.value for cmd in command]

        if not self._commands:
            raise ValueError("Command cannot be empty.")

        # Make sure the self._command is a rectangular list
        row_lengths = {len(row) for row in self._commands}
        if len(row_lengths) != 1:
            raise ValueError("Command must be a rectangular list.")

        # Parse the data into bytes
        self._commands_lengths = struct.pack("!i", len(self._commands) * len(self._commands[0]))
        self._commands_as_bytes = TcpRequestProtocol._command_to_bytes(self._commands)

    @staticmethod
    def _command_to_bytes(commands: list[list[int]]) -> bytes:
        commands_as_bytes = b""
        for commands_row in commands:
            for command in commands_row:
                # we chose unsigned char 8 (range from 0 to 511) so each x or y coordinates can be store on 1 byte
                commands_as_bytes += struct.pack("!B", command)
        return commands_as_bytes

    @property
    def serialized(self) -> bytes:
        return self._commands_lengths + self._commands_as_bytes


class TcpResponseProtocol:
    @classproperty
    def header_length(cls) -> int:
        return 4

    @classproperty
    def data_shape(cls) -> tuple[int, int]:
        return (-1, 10)

    @staticmethod
    def get_data_length_from_header(header_data: bytes) -> int:
        if len(header_data) != TcpResponseProtocol.header_length:
            raise ValueError("Header data length does not match expected header length.")

        return struct.unpack("!i", header_data)[0] * 8  # each double is 8 bytes

    @staticmethod
    def deserialize(data: bytes) -> np.ndarray:
        data_length = len(data) // 8

        # Unpack double in network standard (Big endian)
        return np.reshape(struct.unpack(f"!{data_length}d", data), TcpResponseProtocol.data_shape).T
