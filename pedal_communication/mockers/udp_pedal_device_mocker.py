import socket
import struct
import threading
import time
import json
import logging
from typing import Tuple, List
import numpy as np


from ..devices.udp_communication_protocol import UdpProtocolConstants
from ..misc import recv_exact


# Declare some helpers
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger("DeviceMock")


class UdpPedalDeviceMocker:
    """
    See the UDP communication protocol specification for details:
    """

    def __init__(self, port: int = 6000):
        self._control_port = port
        self._control_socket: socket.socket = None
        self._client_control_connexion: socket.socket = None
        self._client_addr: Tuple[str, int] = None

        # UDP target (set by client in SET_CONFIG or START)
        self._udp_target = None  # (ip, port)

        # Server state
        self._is_server_running = False

        # Streaming state
        self._is_streaming = False
        self._stream_thread: threading.Thread = None
        self._stop_event = threading.Event()
        self._starting_device_clock = time.time()

        # Data constraints
        self._frequency = 50  # Hz
        self._sample_per_block = 10  # frames per block packet
        self._max_channel_count = 44
        self._time_vector_template = np.arange(0, self._sample_per_block * 1 / self._frequency, 1 / self._frequency)

        # Data parameters (configurable)
        self._channels_to_serve: List[int] = []  # includes time channel at index 0
        self._sequence_id = 0

        # Simulate the fact that the Mocker is connected to a real device and gets blocks of data itself
        self._data_simulator_current_data = np.ndarray(shape=(0, self._max_channel_count), dtype=np.float64)
        self._data_simulator_stop_event = threading.Event()
        self._data_simulator_thread = threading.Thread(target=self._simulate_data)
        self._data_simulator_thread.start()

    def run(self):
        """
        Start the mock device server.
        """
        self._is_server_running = True

        # Connect the control socket and handle client connections
        self._control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._control_socket.bind(("0.0.0.0", self._control_port))
        self._control_socket.listen(1)
        _logger.info(f"Control listening on port {self._control_port}")

        self._handle_control_connection()

    def dispose(self):
        """
        Dispose the mock device server.
        """

        self._stop_streaming()

        if self._control_socket is not None:
            self._control_socket.close()
        self._control_socket = None
        self._is_server_running = False

    def _stop_listening(self):
        logger = logging.getLogger(__name__)
        self._is_running = False

        if self._connection:
            self._connection.close()
            logger.info("Connection closed.")
        self._connection = None

        if self._socket:
            self._socket.close()
            logger.info("DeviceMock stopped listening.")
        self._socket = None

    def _handle_control_connection(self):
        """Main loop for handling control messages from the connected client"""
        while self._is_server_running:  # TODO Check if disconnected, it still waits for new connections
            # read control header
            try:
                header = recv_exact(self._control_socket, UdpProtocolConstants.control_header_len)
            except ConnectionError:
                _logger.info("Client disconnected.")
                continue

            magic, version, operational_code, payload_len = struct.unpack(
                UdpProtocolConstants.control_header_format, header
            )

            # Sanity check
            if magic != UdpProtocolConstants.control_magic_code or version != UdpProtocolConstants.control_version:
                _logger.error(f"Unsupported control protocol version: {version}")
                raise ConnectionError("Unsupported control protocol version")

            # Get the payload (empty string if payload_len == 0)
            payload = recv_exact(self._control_socket, payload_len)

            # dispatch based on opcode
            if operational_code == UdpProtocolConstants.OperationalCode.SET_CONFIG.value:
                # expect JSON payload with fields decribed in UdpCommunicationProtocol for OperationalCode.SET_CONFIG
                config = json.loads(payload.decode("utf-8"))
                self._frequency = int(config.get("frequency", self._frequency))
                self._sample_per_block = float(config.get("sample_window", self._sample_per_block))
                self._channels_to_serve = config.get("channels", [])
                udp_port = int(config.get("udp_port"))

                client_ip = self._client_addr[0]  # use the TCP peer IP
                self._udp_target = (client_ip, udp_port)
                _logger.info(
                    f"SET_CONFIG: freq={self._frequency}Hz window={self._sample_per_block}s channels={self._channels_to_serve} -> UDP {self._udp_target}"
                )
                self._send_control_response(
                    self._control_socket, operational_code=UdpProtocolConstants.OperationalCode.ACK.value, payload=b"OK"
                )

            elif operational_code == UdpProtocolConstants.OperationalCode.START.value:
                if not self._udp_target:
                    self._send_control_response(
                        self._control_socket,
                        operational_code=UdpProtocolConstants.OperationalCode.ERR.value,
                        payload=b"missing_udp_target",
                    )
                    continue
                self._start_streaming()
                self._send_control_response(
                    self._control_socket,
                    operational_code=UdpProtocolConstants.OperationalCode.ACK.value,
                    payload=b"STREAMING_STARTED",
                )

            elif operational_code == UdpProtocolConstants.OperationalCode.STOP.value:
                self._stop_streaming()
                self._send_control_response(
                    self._control_socket,
                    operational_code=UdpProtocolConstants.OperationalCode.ACK.value,
                    payload=b"STREAMING_STOPPED",
                )

            elif operational_code == UdpProtocolConstants.OperationalCode.GET_STATUS.value:
                status = {
                    "is_streaming": self._is_streaming,
                    "frequency": self._frequency,
                    "sample_per_block": self._sample_per_block,
                    "channels": self._channels_to_serve,
                    "sequence_id": self._sequence_id,
                }
                payload_b = json.dumps(status).encode("utf-8")
                self._send_control_response(
                    self._control_socket,
                    operational_code=UdpProtocolConstants.OperationalCode.ACK.value,
                    payload=payload_b,
                )

            elif operational_code == UdpProtocolConstants.OperationalCode.PING.value:
                self._send_control_response(
                    self._control_socket,
                    operational_code=UdpProtocolConstants.OperationalCode.ACK.value,
                    payload=b"PONG",
                )

            else:
                _logger.warning(f"Unknown control opcode {operational_code}")
                self._send_control_response(
                    self._control_socket,
                    operational_code=UdpProtocolConstants.OperationalCode.ERR.value,
                    payload=b"unknown_opcode",
                )

    def _send_control_response(self, conn: socket.socket, operational_code: int, payload: bytes):
        header = struct.pack(
            UdpProtocolConstants.control_header_format,
            UdpProtocolConstants.control_magic_code,
            UdpProtocolConstants.control_version,
            operational_code,
            len(payload),
        )
        conn.sendall(header + payload)

    def _start_streaming(self):
        if self._is_streaming or not self._is_server_running:
            return

        self._is_streaming = True
        self._stop_event.clear()

        self._stream_thread = threading.Thread(target=self._stream_data_loop, daemon=True)
        self._stream_thread.start()
        _logger.info("Streaming thread started")

    def _stop_streaming(self):
        if not self._is_streaming or not self._is_server_running:
            return

        self._stop_event.set()
        if self._stream_thread:
            self._stream_thread.join(timeout=1.0)

        self._is_streaming = False
        _logger.info("Streaming stopped")

    def _stream_data_loop(self):
        """
        Stream frames to UDP target at self.frequency.
        Each frame contains sample_count = int(sample_window * frequency) samples.
        """
        if not self._udp_target:
            _logger.error("No UDP target configured; aborting stream")
            self._is_streaming = False
            return

        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        next_serve_data_time = time.time()
        last_frame_timestamp = -1
        while not self._stop_event.is_set():
            # Fetch the current data (this should be thread-safe)
            data = np.copy(self._data_simulator_current_data)

            # If no new data, wait are recorded, wait a bit
            if last_frame_timestamp == data[-1, 0]:
                # This should be based on a OnNewData event to make sure data are served as soon as available
                now = time.time()
                time.sleep(min(0.001, next_serve_data_time - now))
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
                len(self._channels_to_serve),
            )

            # pack data row-major by sample: sample0[ch0..chN], sample1[ch0..chN], ...
            # total doubles = sample_count * channel_count
            payload = b"".join(struct.pack("!d", float(x)) for x in data_blocks.flatten(order="C"))

            # full packet
            packet = header + payload

            try:
                udp_sock.sendto(packet, self._udp_target)
            except Exception as e:
                _logger.exception(f"Failed to send UDP packet to {self._udp_target}: {e}")
                break

            # schedule next frame
            last_frame_timestamp = data[-1, 0]
            next_serve_data_time += self._sample_per_block / self._frequency  # TODO Check this

        udp_sock.close()

    def _simulate_data(self):
        """
        This method simulates the threads of the real device that generates data blocks that can be served to clients.
        """
        next_frame_time = time.time()
        while not self._data_simulator_stop_event.is_set():
            now = time.time()
            if now < next_frame_time:
                time.sleep(min(0.001, next_frame_time - now))
                continue

            # Create a time vector based on elapsed time
            time_increments = 1 / self._frequency * len(self._time_vector_template)
            time_elapsed = time.time() - self._starting_device_clock
            ratio = time_elapsed // (1 / self._frequency * len(self._time_vector_template))
            time_vector = self._time_vector_template + ratio * time_increments

            # Simulate some random data (time_vector length x n channels)
            data = np.concatenate(
                (time_vector[:, None], np.random.rand(len(time_vector), self._max_channel_count - 1)), axis=1
            )
            self._data_simulator_current_data = np.concatenate((time_vector[:, None], data), axis=1)

            # schedule next frame
            next_frame_time += 1 / self._frequency
