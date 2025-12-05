import logging
import socket
import struct
import time
import threading
from typing import Tuple

import numpy as np

from .generic_device import GenericDevice
from .udp_communication_protocol import (
    UdpResponseProtocol,
    UdpRequestProtocol,
    UdpCommandProtocol,
    UdpProtocolConstants,
    UdpConfigurationProtocol,
)
from ..misc import recv_exact

_logger = logging.getLogger("ClientExample")


def parse_control_header(data: bytes):
    return struct.unpack(UdpProtocolConstants.control_header_format, data)


class UdpPedalDevice(GenericDevice):
    def __init__(
        self, server_host: str = "localhost", control_port: int = 6000, data_port: int = 6001, *args, **kwargs
    ):

        super().__init__(*args, **kwargs)
        self._server_host = server_host
        self._control_port = control_port
        self._data_port = data_port

        self._control_socket: socket.socket = None
        self._data_socket: socket.socket = None

        self._data_last_received: np.ndarray = None
        self._data_stop_event = threading.Event()
        self._data_thread = threading.Thread(target=self._listen_udp_data, daemon=True)
        self._data_thread.start()

    @property
    def is_connected(self) -> bool:
        """
        Indicates whether the device is currently connected.
        """
        return self._control_socket is not None and self._data_socket is not None

    @property
    def host(self) -> str:
        return self._server_host

    @property
    def port(self) -> int:
        return self._control_port

    def connect(self) -> bool:
        _logger.debug(f"Attempting to connect to TCP device at {self._server_host}:{self._control_port}")
        if self.is_connected:
            _logger.debug("Already connected to TCP device.")
            return True  # Already connected

        # 1) Connect TCP control channel
        self._control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._control_socket.connect((self._server_host, self._control_port))
        except socket.error:
            _logger.error(f"Failed to connect to TCP device at {self._host}:{self._port}")
            self._control_socket = None

        # 2) Open UDP socket to receive data
        self._data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._data_socket.bind(("0.0.0.0", self._data_port))
        self._data_socket.settimeout(2.0)

        # 3) Send SET_CONFIG (tell server frequency, channels, which UDP port to stream to)
        is_success, _ = self.send(UdpConfigurationProtocol(udp_port=self._data_port))
        if not is_success:
            _logger.error("Failed to send configuration to UDP device.")
            self.disconnect()
            return False

        # 4) Request START streaming
        is_success, _ = self.send(UdpCommandProtocol(UdpProtocolConstants.OperationalCode.START))
        if not is_success:
            _logger.error("Failed to start streaming from UDP device.")
            self.disconnect()
            return False

        return True

    def disconnect(self) -> bool:
        _logger.debug(f"Disconnecting from {self._server_host}")
        self.send(UdpCommandProtocol(UdpProtocolConstants.OperationalCode.STOP))

        if self._control_socket is not None:
            _logger = logging.getLogger(__name__)
            self._control_socket.close()
            self._control_socket = None

        if self._data_socket is not None:
            self._data_socket.close()
            self._data_socket = None

        return not self.is_connected

    def dispose(self) -> None:
        """
        Terminate the current object and release all associated resources. Once disposed, the object cannot be used anymore.
        """
        self.disconnect()

        if self._data_thread.is_alive():
            self._data_stop_event.set()
            self._data_thread.join()

    def send(self, command: UdpRequestProtocol) -> Tuple[bool, bytes]:
        if not self.is_connected:
            return False

        try:
            self._control_socket.sendall(command.serialized)
        except socket.error:
            return False

        return self._parse_command_response()

    def _parse_command_response(self) -> Tuple[bool, bytes] | bool:
        # read response
        header = recv_exact(self._control_socket, UdpProtocolConstants.control_header_len)
        magic, version, operational_code, payload_len = struct.unpack(
            UdpProtocolConstants.control_header_format, header
        )
        # Sanity check
        if magic != UdpProtocolConstants.control_magic_code or version != UdpProtocolConstants.control_version:
            _logger.error(f"Unsupported control protocol version: {version}")
            return False

        # Get the payload (empty string if payload_len == 0)
        payload = recv_exact(self._control_socket, payload_len)
        _logger.info(f"SET_CONFIG response opcode={operational_code} payload={payload}")

        return operational_code == UdpProtocolConstants.OperationalCode.ACK.value, payload

    def _listen_udp_data(self) -> None:
        """
        Main loop that listens to UDP data packets from the device. It is designed to run in a separate thread, but to
        update the data in the main thread. This is currently NOT thread-safe and could be improved in the future.
        """

        previous_sequence_id = None
        try:
            while not self._data_stop_event.is_set():
                # Wait until connected
                if self._data_socket is None:
                    time.sleep(0.1)
                    continue

                data_packets, _ = self._data_socket.recvfrom(65536)
                data, previous_sequence_id = UdpResponseProtocol.deserialize(
                    data_packets, previous_sequence_id=previous_sequence_id
                )
                if data is not None:
                    self._data_last_received = data

        except:
            pass

        _logger.info("UDP data listener thread exiting")

    def get_last_data(self) -> np.ndarray | None:
        if not self.is_connected:
            return None
        return self._data_last_received
