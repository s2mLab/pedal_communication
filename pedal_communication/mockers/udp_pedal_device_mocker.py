import json
import logging
import socket
import struct
import threading
import time
from typing import Tuple, List

import numpy as np

from .pedal_device_mocker import PedalDeviceMocker
from ..data.data import Data
from ..devices.udp_communication_protocol import UdpProtocolConstants, UdpConfigurationProtocol
from ..misc import recv_exact

_logger = logging.getLogger("DeviceMock")


class UdpPedalDeviceMocker(PedalDeviceMocker):
    """
    See the UDP communication protocol specification for details:
    """

    def __init__(self, control_port: int = 6000, data_port: int = 5999):
        # Server state
        self._are_sockets_initialized = False
        self._is_server_running = False

        # Communication sockets
        self._control_port = control_port
        self._control_socket: socket.socket = None
        self._control_connection: socket.socket = None
        self._control_addr: Tuple[str, int] = None

        self._data_port = data_port
        self._data_socket: socket.socket = None
        self._data_addr: Tuple[str, int] = None

        # Streaming state
        self._stream_thread: threading.Thread = None
        self._stop_event: threading.Event = None
        self._starting_device_clock = time.time()

        # Data constraints
        self._frequency = 50  # Hz
        self._sample_per_block = 10  # frames per block packet
        self._max_channel_count = Data.columns_count
        self._time_vector_template = np.arange(0, self._sample_per_block * 1 / self._frequency, 1 / self._frequency)

        # Data parameters (configurable)
        # Channels to serve + 1 so that time channel at index 0 is included
        self._channels_to_serve: List[int] = [val.value + 1 for val in list(UdpConfigurationProtocol.Channels)]
        self._sequence_id = 0

        # Simulate the fact that the Mocker is connected to a real device and gets blocks of data itself
        self._data_simulator_current_data = np.ndarray(shape=(0, self._max_channel_count), dtype=np.float64)
        self._data_simulator_stop_event = threading.Event()
        self._data_simulator_thread = threading.Thread(target=self._simulate_data)
        self._data_simulator_thread.start()

    @property
    def is_connected(self) -> bool:
        """
        Indicates whether the mock device server is currently running.
        """
        return self._is_server_running and self._control_connection is not None and self._data_addr is not None

    def run(self):
        """
        Start the mock device server.
        """
        self._is_server_running = True
        self._handle_control_connection()

    def dispose(self):
        """
        Dispose the mock device server.
        """

        self._stop_listening()

        self._control_socket = None
        self._data_socket = None

        # Stop data simulator
        self._data_simulator_stop_event.set()
        if self._data_simulator_thread:
            self._data_simulator_thread.join(timeout=1.0)

        self._is_server_running = False

    def _start_listening(self) -> bool:
        try:
            if not self._are_sockets_initialized:
                _logger.info(f"Control listening on ports control:{self._control_port} and data:{self._data_port}")
                self._control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._control_socket.bind(("0.0.0.0", self._control_port))
                self._control_socket.settimeout(0.1)
                self._control_socket.listen(1)

                self._data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._data_socket.settimeout(0.1)
                self._data_socket.bind(("0.0.0.0", self._data_port))
                self._are_sockets_initialized = True

            if not self._control_connection:
                self._control_connection, self._control_addr = self._control_socket.accept()

            if self._control_connection:
                _, self._data_addr = self._data_socket.recvfrom(65536)

        except socket.timeout:
            return False
        except:
            _logger.exception("Error accepting connection")
            return False

        _logger.info(f"Client connected from {self._control_addr}")
        return self.is_connected

    def _stop_listening(self):
        logger = logging.getLogger(__name__)
        self._stop_streaming()

        if self._control_connection:
            self._control_connection.close()
            logger.info("Connection closed.")
        self._control_connection = None
        self._control_addr = None

        if self._control_socket is not None:
            self._control_socket.close()

        if self._data_socket is not None:
            self._data_socket.close()
            logger.info("DeviceMock stopped listening.")
        self._data_addr = None

        self._are_sockets_initialized = False

    def _handle_control_connection(self):
        """Main loop for handling control messages from the connected client"""
        while self._is_server_running:
            try:
                if not self.is_connected:
                    if not self._start_listening():
                        continue

                # read control header
                header = recv_exact(self._control_connection, UdpProtocolConstants.control_header_len)
                magic, version, operational_code, payload_len = struct.unpack(
                    UdpProtocolConstants.control_header_format, header
                )

                # Sanity check
                if magic != UdpProtocolConstants.control_magic_code or version != UdpProtocolConstants.control_version:
                    _logger.error(f"Unsupported control protocol version: {version}")
                    raise ConnectionError("Unsupported control protocol version")

                # Get the payload (empty string if payload_len == 0)
                payload = recv_exact(self._control_connection, payload_len)

                # dispatch based on opcode
                if operational_code == UdpProtocolConstants.OperationalCode.SET_CONFIG.value:
                    # expect JSON payload with fields decribed in UdpCommunicationProtocol for OperationalCode.SET_CONFIG
                    config: dict = json.loads(payload.decode("utf-8"))
                    value = config.get("frequency")
                    if value is not None:
                        self._frequency = int(value)
                    value = config.get("sample_per_block")
                    if value is not None:
                        self._sample_per_block = int(value)
                    value = config.get("channels")
                    if value is not None:
                        self._channels_to_serve = [
                            int(val) + 1 for val in value
                        ]  # +1 to include time channel at index 0

                    _logger.info(
                        f"SET_CONFIG: freq={self._frequency}Hz window={self._sample_per_block}s channels={self._channels_to_serve}"
                    )
                    self._send_control_response(
                        self._control_connection,
                        operational_code=UdpProtocolConstants.OperationalCode.ACK.value,
                        payload=b"OK",
                    )

                elif operational_code == UdpProtocolConstants.OperationalCode.START.value:
                    self._start_streaming()
                    self._send_control_response(
                        self._control_connection,
                        operational_code=UdpProtocolConstants.OperationalCode.ACK.value,
                        payload=b"STREAMING_STARTED",
                    )

                elif operational_code == UdpProtocolConstants.OperationalCode.STOP.value:
                    self._stop_streaming()
                    self._send_control_response(
                        self._control_connection,
                        operational_code=UdpProtocolConstants.OperationalCode.ACK.value,
                        payload=b"STREAMING_STOPPED",
                    )

                elif operational_code == UdpProtocolConstants.OperationalCode.GET_STATUS.value:
                    status = {
                        "is_streaming": self.is_streaming,
                        "frequency": self._frequency,
                        "sample_per_block": self._sample_per_block,
                        "channels": self._channels_to_serve,
                        "sequence_id": self._sequence_id,
                    }
                    payload_b = json.dumps(status).encode("utf-8")
                    self._send_control_response(
                        self._control_connection,
                        operational_code=UdpProtocolConstants.OperationalCode.ACK.value,
                        payload=payload_b,
                    )

                elif operational_code == UdpProtocolConstants.OperationalCode.PING.value:
                    self._send_control_response(
                        self._control_connection,
                        operational_code=UdpProtocolConstants.OperationalCode.ACK.value,
                        payload=b"PONG",
                    )

                else:
                    _logger.warning(f"Unknown control opcode {operational_code}")
                    self._send_control_response(
                        self._control_connection,
                        operational_code=UdpProtocolConstants.OperationalCode.ERR.value,
                        payload=b"unknown_opcode",
                    )

            except Exception as e:
                _logger.error(f"Error in DeviceMocker, resetting connection: {e}")
                self._stop_listening()

    def _send_control_response(self, conn: socket.socket, operational_code: int, payload: bytes):
        header = struct.pack(
            UdpProtocolConstants.control_header_format,
            UdpProtocolConstants.control_magic_code,
            UdpProtocolConstants.control_version,
            operational_code,
            len(payload),
        )
        conn.sendall(header + payload)

    @property
    def is_streaming(self):
        return self._stop_event is not None and not self._stop_event.is_set()

    def _start_streaming(self):
        if self.is_streaming:
            return

        if self._stop_event is None:
            self._stop_event = threading.Event()
        self._stop_event.clear()

        self._stream_thread = threading.Thread(target=self._stream_data_loop, daemon=True)
        self._stream_thread.start()
        _logger.info("Streaming thread started")

    def _stop_streaming(self):
        if not self.is_streaming:
            return

        if self._stop_event is not None:
            self._stop_event.set()
        if self._stream_thread:
            self._stream_thread.join(timeout=1.0)

        _logger.info("Streaming stopped")

    def _stream_data_loop(self):
        """
        Stream frames to UDP target at self.frequency.
        Each frame contains sample_count = int(sample_per_block * frequency) samples.
        """
        if self._control_addr is None:
            _logger.error("No client connected; aborting stream")
            return

        last_frame_timestamp = -1
        while not self._stop_event.is_set():
            try:
                # Fetch the current data (this should be thread-safe)
                data = np.copy(self._data_simulator_current_data)

                # If no new data were recorded, wait a bit
                if last_frame_timestamp == data[-1, 0]:
                    # This could be based on a OnNewData event to make sure data are served as soon as available
                    time.sleep(0.001)
                    continue

                # Prepare the packet to send
                self._sequence_id = (self._sequence_id + 1) & 0xFFFFFFFF

                # Prepare the time vector and data matrix for this block
                time_vector = data[:, 0]
                data_matrix = data[:, self._channels_to_serve]
                data_blocks = np.concatenate((time_vector[:, None], data_matrix), axis=1)

                # pack header
                header = struct.pack(
                    UdpProtocolConstants.data_header_format,
                    UdpProtocolConstants.data_magic_code,
                    UdpProtocolConstants.data_version,
                    self._sequence_id,
                    self._sample_per_block,
                    len(self._channels_to_serve) + 1,  # +1 for time channel
                )

                # pack data row-major by sample: sample0[ch0..chN], sample1[ch0..chN], ...
                # total doubles = sample_count * channel_count
                payload = b"".join(struct.pack("!d", float(x)) for x in data_blocks.flatten(order="C"))

                # full packet
                packet = header + payload

                if self._data_addr is not None:
                    self._data_socket.sendto(packet, self._data_addr)

                # schedule next frame
                last_frame_timestamp = data[-1, 0]

            except Exception as e:
                _logger.exception(f"Failed to send UDP packet to {self._data_addr}: {e}")

    def _simulate_data(self):
        """
        This method simulates the threads of the real device that generates data blocks that can be served to clients.
        """
        next_frame_time = time.time()
        while not self._data_simulator_stop_event.is_set():
            now = time.time()
            if now < next_frame_time:
                time.sleep(min(1 / self._frequency * self._sample_per_block, next_frame_time - now))
                continue

            # Create a time vector based on elapsed time
            time_increments = 1 / self._frequency * len(self._time_vector_template)
            time_elapsed = time.time() - self._starting_device_clock
            ratio = time_elapsed // (1 / self._frequency * len(self._time_vector_template))
            time_vector = self._time_vector_template + ratio * time_increments

            # Simulate some random data (time_vector length x n channels)
            self._data_simulator_current_data = np.concatenate(
                (time_vector[:, None], np.random.rand(len(time_vector), self._max_channel_count)), axis=1
            )

            # schedule next frame
            next_frame_time += 1 / self._frequency * self._sample_per_block
