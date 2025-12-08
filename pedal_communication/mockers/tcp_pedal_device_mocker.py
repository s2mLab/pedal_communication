import logging
import socket
import struct
import time

import numpy as np

from .pedal_device_mocker import PedalDeviceMocker
from ..data.data import Data
from ..devices.tpc_communication_protocol import TcpRequestProtocol
from ..misc import recv_exact


_logger = logging.getLogger(__name__)


class TcpPedalDeviceMocker(PedalDeviceMocker):
    # A simple mock device that simulates basic behavior.
    def __init__(self, port: int = 6000):
        self._is_socket_initialized = False

        self._port = port
        self._socket: socket.socket = None
        self._connection: socket.socket = None
        self._is_running = False

        self._starting_device_clock = time.time()
        self._frequency = 50  # Hz
        self._time_vector_template = np.arange(0, 10 * 1 / self._frequency, 1 / self._frequency)

        self._request_protocol_cache = TcpRequestProtocol(request_type=TcpRequestProtocol.RequestType.NORMAL)

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    def run(self):
        """
        Start the mock device server.
        """
        self._start_listening()

    def dispose(self):
        """
        Dispose the mock device server. After disposing, the server cannot be restarted.
        """
        self._stop_listening()
        self._socket = None
        self._is_running = False

    def _listen_command(self) -> bool:
        if not self.is_connected:
            return False

        # Wait synchronously for client commands
        try:
            int_size = struct.calcsize("!i")
            commands_length = recv_exact(self._connection, int_size)
            if not commands_length:
                raise Exception("Client disconnected.")
            commands_length = struct.unpack("!i", commands_length)[0]

            commands_data = recv_exact(self._connection, commands_length)
            if not commands_data:
                raise Exception("Client disconnected.")

            commands = struct.unpack(f"!{commands_length}b", commands_data)
            commands = [list(commands[i : i + 2]) for i in range(0, len(commands), 2)]
            if commands != self._request_protocol_cache._commands:
                _logger.info(f"Unexpected commands received")
                return False

            return True

        except:
            self._stop_listening()
            return False

    def _serve_data(self):
        if not self.is_connected:
            return

        # Create a time vector based on elapsed time
        time_increments = 1 / self._frequency * len(self._time_vector_template)
        time_elapsed = time.time() - self._starting_device_clock
        ratio = time_elapsed // (1 / self._frequency * len(self._time_vector_template))
        time_vector = self._time_vector_template + ratio * time_increments

        # Simulate some random data (time_vector length x N channels)
        data = np.concatenate((time_vector[:, None], np.random.rand(len(time_vector), Data.columns_count)), axis=1)
        data_bytes = b""
        for row in data.T:
            for value in row:
                data_bytes += struct.pack("!d", value)

        data_length = struct.pack("!i", data.shape[0] * data.shape[1])
        try:
            self._connection.sendall(data_length + data_bytes)
        except BrokenPipeError:
            _logger.info("Client disconnected.")
            self._stop_listening()

    def _start_listening(self):
        self._is_running = True
        while self._is_running:
            try:
                if not self.is_connected:
                    if not self._is_socket_initialized:
                        _logger.info(f"DeviceMock listening on port {self._port}")
                        self._is_socket_initialized = True
                        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self._socket.bind(("localhost", self._port))
                        self._socket.listen(1)
                        self._socket.settimeout(0.1)
                    try:
                        self._connection, addr = self._socket.accept()
                    except socket.timeout:
                        continue
                    except:
                        _logger.exception("Error accepting connection")
                        continue
                    _logger.info(f"Connection from {addr} has been established!")

                has_command = self._listen_command()
                if not has_command:
                    continue
                self._serve_data()
            except KeyboardInterrupt:
                raise KeyboardInterrupt()
            except:
                _logger.exception("Error in DeviceMocker:")
                self._stop_listening()

    def _stop_listening(self):
        if self._connection is not None:
            self._connection.close()
            _logger.info("Connection closed.")
        self._connection = None

        if self._socket is not None:
            self._socket.close()
            _logger.info("DeviceMock stopped listening.")

        self._is_socket_initialized = False
