"""
The Protocol is based on TCP/UDP communication with the following structure:
- Control is any command sent from the client to the device that changes the device state or requests information.
- DataFrame is the continuous stream of data sent from the device to the client.

HEADER STRUCTURES:

--------------------------------
ControlHeader (fixed 8 bytes)
--------------------------------
uint16_t magic = 0xC0DE         // Magic number to identify control packets (2 bytes)
uint8_t  version = 1            // Current protocol version (1 byte)
uint8_t  operational_code       // Operation code (see UdpProtocolConstants.OperationalCode for description) (1 byte)
uint32_t payload_len            // length of the payload in bytes (4 bytes)
--------------------------------

--------------------------------
DataFrameHeader (fixed 24 bytes)
--------------------------------
uint16_t magic = 0xDA7A         // Magic number to identify data packets (2 bytes)
uint8_t  version = 1            // Current protocol version (1 byte)
uint32_t sequence_id            // Incremental sequence identifier (4 bytes)
uint32_t sample_count           // Number of sample blocks in the payload (4 bytes)
uint32_t channel_count          // Number of channels in the payload (4 bytes)
--------------------------------


PAYLOAD STRUCTURES:

--------------------------------
ControlPayload (variable length)
--------------------------------
Json-encoded command parameters (e.g., configuration settings)
UdpProtocolConstants.OperationalCode.SET_CONFIG:
{
    "udp_port": 6001            // UDP port for data streaming
    "frequency": 50.0,          // Sampling frequency in Hz
    "sample_window": 10,        // Samples per block
    "channels": <int>[],        // A list of the channel's code to activate
}
--------------------------------

--------------------------------
DataFramePayload (variable length)
--------------------------------
Repeated blocks of:
double time                     // 8 bytes
double channel_1                // 8 bytes
...
double channel_N                // 8 bytes (N = channel_count requested by client)
--------------------------------
"""

from enum import Enum
import struct

import numpy as np

from .generic_communication_protocol import GenericRequestProtocol
from ..data import DataType
from ..misc import classproperty


class UdpProtocolConstants:
    # Magic values to sign the beginning of packets
    control_magic_code = 0xC0DE
    data_magic_code = 0xDA7A

    # Version of the protocol
    control_version = 0x0001
    data_version = 0x0001

    # Control header (TCP): magic_code(2), version(2), operational code(2), payload_len(4)
    control_header_format = "!H H H I"
    control_header_len = struct.calcsize(control_header_format)

    # Data frame header (UDP): magic_code(2), version(2), flags(2), sequence_id(4), device_timestamp(8), sample_count(2), channel_count(2)
    data_header_format = "!H H H I d H H"
    data_header_len = struct.calcsize(data_header_format)

    # Operational codes for control messages
    class OperationalCode(Enum):
        SET_CONFIG = 0x0001
        START = 0x0002
        STOP = 0x0003
        GET_STATUS = 0x0004
        PING = 0x0005
        ACK = 0x0006
        ERR = 0x0007


class UdpRequestProtocol(GenericRequestProtocol):
    class Command(Enum):
        FX_LEFT = 0
        FY_LEFT = 1
        FZ_LEFT = 2
        MX_LEFT = 3
        MY_LEFT = 4
        MZ_LEFT = 5
        A6 = 6
        A7 = 7
        FX_RIGHT = 8
        FY_RIGHT = 9
        FZ_RIGHT = 10
        A11 = 11
        A12 = 12
        A13 = 13
        A14 = 14
        A15 = 15
        A16 = 16
        A17 = 17
        PEDAL_ANGLE = 18
        TIME = 19
        A20 = 20
        A21 = 21
        A22 = 22
        A23 = 23
        A24 = 24
        A25 = 25
        A26 = 26
        A27 = 27
        A28 = 28
        A29 = 29
        A30 = 30
        A31 = 31
        A32 = 32
        A33 = 33
        A34 = 34
        PEDALLING_SPEED = 35
        POWER_LEFT = 36
        POWER_RIGHT = 37
        POWER_TOTAL = 38
        A39 = 39
        A40 = 40
        A41 = 41
        A42 = 42
        A43 = 43
        A44 = 44

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
        self._commands_as_bytes = UdpRequestProtocol._command_to_bytes(self._commands)

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


class UdpResponseProtocol:
    @classproperty
    def header_length(cls) -> int:
        return UdpProtocolConstants.data_header_len

    @classproperty
    def data_shape(cls) -> tuple[int, int]:
        return (-1, 10)

    @staticmethod
    def get_data_length_from_header(header_data: bytes) -> int:
        if len(header_data) != UdpResponseProtocol.header_length:
            raise ValueError("Header data length does not match expected header length.")

        return struct.unpack("!i", header_data)[0] * 8  # each double is 8 bytes

    @staticmethod
    def deserialize(data: bytes) -> np.ndarray:
        data_length = len(data) // 8

        # Unpack double in network standard (Big endian)
        return np.reshape(struct.unpack(f"!{data_length}d", data), UdpResponseProtocol.data_shape).T
