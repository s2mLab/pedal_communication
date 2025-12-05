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
    "sample_per_block": 10,     // Samples per block
    "channels": list<int>[],    // A list of the channel's code to activate
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
import json
import logging
import struct
from typing import Iterable, Tuple

import numpy as np

from .generic_communication_protocol import GenericRequestProtocol


_logger = logging.getLogger(__name__)


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

    # Data frame header (UDP): magic_code(2), version(2), sequence_id(4), sample_count(2), channel_count(2)
    data_header_format = "!H H I H H"
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
    pass


class UdpCommandProtocol(UdpRequestProtocol):
    def __init__(self, operational_code: UdpProtocolConstants.OperationalCode):
        self._operational_code = operational_code

    @property
    def serialized(self) -> bytes:
        command = {
            "udp_port": self._udp_port,
        }
        payload = json.dumps(command).encode("utf-8")

        header = struct.pack(
            UdpProtocolConstants.control_header_format,
            UdpProtocolConstants.control_magic_code,
            UdpProtocolConstants.control_version,
            UdpProtocolConstants.OperationalCode.SET_CONFIG.value,
            len(payload),
        )

        return header + payload


class UdpConfigurationProtocol(UdpRequestProtocol):
    class Channels(Enum):
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

    def __init__(
        self,
        channels: Channels | Iterable[Channels] = None,
        udp_port: int = None,
    ):
        """
        Prepare a configuration to the UDP device. If channels is None, all available channels are requested.
        """

        self._udp_port = udp_port

        if channels is None:
            channels = list(UdpConfigurationProtocol.Channels)
        elif isinstance(channels, UdpConfigurationProtocol.Channels):
            channels = [channels]
        self._channels = list(channels)

    @property
    def serialized(self) -> bytes:
        configuration = {
            "udp_port": self._udp_port,
            "channels": self._channels,
            "frequency": None,
            "sample_per_block": None,
        }
        payload = json.dumps(configuration).encode("utf-8")

        header = struct.pack(
            UdpProtocolConstants.control_header_format,
            UdpProtocolConstants.control_magic_code,
            UdpProtocolConstants.control_version,
            UdpProtocolConstants.OperationalCode.SET_CONFIG.value,
            len(payload),
        )

        return header + payload


class UdpResponseProtocol:
    @staticmethod
    def deserialize(data: bytes, previous_sequence_id: int = None) -> Tuple[np.ndarray | None, int]:
        if previous_sequence_id is None:
            previous_sequence_id = -1

        if len(data) < UdpProtocolConstants.data_header_len:
            _logger.warning("Short data packet")
            return None, previous_sequence_id

        # parse header
        data_hdr = data[: UdpProtocolConstants.data_header_len]
        (magic, ver, sequence_id, sample_count, channel_count) = struct.unpack(
            UdpProtocolConstants.data_header_format, data_hdr
        )
        if magic != UdpProtocolConstants.data_magic_code and ver != UdpProtocolConstants.data_version:
            _logger.warning("Bad data magic")
            return None, previous_sequence_id

        payload = data[UdpProtocolConstants.data_header_len :]
        expected_doubles = sample_count * channel_count
        if len(payload) < expected_doubles * 8:
            _logger.warning(f"Incomplete payload: got {len(payload)} expected {expected_doubles*8}")
            return None, previous_sequence_id

        if previous_sequence_id > sequence_id:
            _logger.warning(f"Out of order packet: got {sequence_id} expected > {previous_sequence_id}")
            return None, previous_sequence_id

        # unpack all doubles
        fmt = f"!{expected_doubles}d"
        values = struct.unpack(fmt, payload[: expected_doubles * 8])
        return np.array(values, dtype=np.float64).reshape((sample_count, channel_count)), sequence_id
