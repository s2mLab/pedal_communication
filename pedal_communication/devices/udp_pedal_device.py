import json
import logging
import socket
import struct
import time

import numpy as np

from .generic_device import GenericDevice
from .udp_communication_protocol import UdpResponseProtocol, UdpRequestProtocol, UdpProtocolConstants
from ..misc import recv_exact

_logger = logging.getLogger("ClientExample")


def build_control_header(operational_code: int, payload_len: int, version: int = 1) -> bytes:
    return struct.pack(
        UdpProtocolConstants.control_header_format,
        UdpProtocolConstants.control_magic_code,
        UdpProtocolConstants.control_version,
        operational_code,
        payload_len,
    )


def parse_control_header(data: bytes):
    return struct.unpack(UdpProtocolConstants.control_header_format, data)


def run_example(server_host="127.0.0.1", control_port=6000, local_udp_port=6001):

    # 3) Send SET_CONFIG (tell server frequency, channels, which UDP port to stream to)
    cfg = {"frequency": 50, "sample_window": 0.2, "channels": 15, "udp_port": local_udp_port}
    payload = json.dumps(cfg).encode("utf-8")
    hdr = build_control_header(OPCODE["SET_CONFIG"], len(payload))
    ctrl.sendall(hdr + payload)

    # read response
    hdr = recv_exact(ctrl, CTRL_HEADER_LEN)
    magic, version, opcode, payload_len = parse_control_header(hdr)
    resp = recv_exact(ctrl, payload_len) if payload_len else b""
    logger.info(f"SET_CONFIG response opcode={opcode} payload={resp}")

    # 4) START streaming
    hdr = build_control_header(OPCODE["START"], 0)
    ctrl.sendall(hdr)
    hdr = recv_exact(ctrl, CTRL_HEADER_LEN)
    _, _, opcode, payload_len = parse_control_header(hdr)
    resp = recv_exact(ctrl, payload_len) if payload_len else b""
    logger.info(f"START response opcode={opcode} payload={resp}")

    # 5) Receive some UDP frames and parse
    last_seq = None
    try:
        while True:
            pkt, addr = udp_sock.recvfrom(65536)
            if len(pkt) < DATA_HEADER_LEN:
                logger.warning("Short packet")
                continue
            # parse header
            data_hdr = pkt[:DATA_HEADER_LEN]
            (magic, ver, flags, seq, ts, sample_count, channel_count) = struct.unpack(DATA_HEADER_FMT, data_hdr)
            if magic != 0xDA7A:
                logger.warning("Bad data magic")
                continue

            payload = pkt[DATA_HEADER_LEN:]
            expected_doubles = sample_count * channel_count
            if len(payload) < expected_doubles * 8:
                logger.warning(f"Incomplete payload: got {len(payload)} expected {expected_doubles*8}")
                continue

            # unpack all doubles
            fmt = f"!{expected_doubles}d"
            values = struct.unpack(fmt, payload[: expected_doubles * 8])
            arr = np.array(values, dtype=np.float64).reshape((sample_count, channel_count))

            # detect gap
            if last_seq is not None and seq != ((last_seq + 1) & 0xFFFFFFFF):
                logger.warning(f"Gap detected: last={last_seq} got={seq}")
            last_seq = seq

            # Example use: print first sample time and first channel values
            t0 = arr[0, 0]
            logger.info(f"Frame seq={seq} ts={ts:.6f} sample_count={sample_count} channels={channel_count} t0={t0:.6f}")

            # client logic: process arr ...
    except KeyboardInterrupt:
        logger.info("Stopping client")
    finally:
        # tell server to stop gracefully
        hdr = build_control_header(OPCODE["STOP"], 0)
        ctrl.sendall(hdr)
        ctrl.close()
        udp_sock.close()


class UdpPedalDevice(GenericDevice):
    def __init__(
        self, server_host: str = "localhost", control_port: int = 6000, data_port: int = 6001, *args, **kwargs
    ):

        super().__init__(*args, **kwargs)
        self._server_host = server_host
        self._control_port = control_port
        self._data_port = data_port

        # self._request = UdpRequestProtocol()
        # self._socket: socket.socket | None = None

        # self._previous_last_timestamp: float | None = None

    @property
    def is_connected(self) -> bool:
        """
        Indicates whether the device is currently connected.
        """
        return self._socket is not None

    @property
    def host(self) -> str:
        return self._server_host

    @property
    def port(self) -> int:
        return self._control_port

    def connect(self) -> bool:
        _logger.debug(f"Attempting to connect to TCP device at {self._server_host}:{self._control_port}")
        if self._socket is not None:
            _logger.debug("Already connected to TCP device.")
            return True  # Already connected

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._socket.connect((self._host, self._port))
        except socket.error:
            logger.error(f"Failed to connect to TCP device at {self._host}:{self._port}")
            self._socket = None

        # 1) Connect TCP control channel
        ctrl = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ctrl.connect((server_host, control_port))

        # 2) Open UDP socket to receive data
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind(("0.0.0.0", local_udp_port))
        udp_sock.settimeout(2.0)

        return self._socket is not None

    def disconnect(self) -> bool:
        if self._socket is not None:
            logger = logging.getLogger(__name__)
            logger.debug(f"Disconnecting from TCP device at {self._host}:{self._port}")
            self._socket.close()
            self._socket = None

        return self._socket is None

    def send(self, data: TcpRequestProtocol) -> bool:
        if self._socket is None:
            return False

        try:
            self._socket.sendall(data.serialized)
            return True
        except socket.error:
            return False

    def get_next_data(self) -> np.ndarray | None:
        if self._socket is None:
            return None

        # First, we need to send the formating of the data
        self.send(data=self._request)

        try:
            logger = logging.getLogger(__name__)
            logger.debug(f"Receiving data from TCP device at {self._host}:{self._port}")
            header_length = TcpResponseProtocol.header_length
            header = recv_exact(self._socket, header_length)
            if not header:
                return None
            data_length = TcpResponseProtocol.get_data_length_from_header(header)
            data = recv_exact(self._socket, data_length)
            if not data:
                return None

            output = TcpResponseProtocol.deserialize(data)
            first_timestamp = output[0, 0]
            last_timestamp = output[-1, 0]

            if self._previous_last_timestamp is not None and first_timestamp < self._previous_last_timestamp:
                return None
            self._previous_last_timestamp = last_timestamp

            return output

        except socket.error:
            return None
