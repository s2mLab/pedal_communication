import logging
import socket

import numpy as np

from .generic_device import GenericDevice
from .communication_protocol import AnswerProtocol, RequestProtocol


class TcpPedalDevice(GenericDevice):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6000,
        request_type: RequestProtocol.RequestType = RequestProtocol.RequestType.NORMAL,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._host = host
        self._port = port

        self._request = RequestProtocol(request_type=request_type)
        self._socket: socket.socket | None = None

        self._previous_last_timestamp: float | None = None

    @property
    def is_connected(self) -> bool:
        """
        Indicates whether the device is currently connected.
        """

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    def connect(self) -> bool:
        logger = logging.getLogger(__name__)

        logger.debug(f"Attempting to connect to TCP device at {self._host}:{self._port}")
        if self._socket is not None:
            logger.debug("Already connected to TCP device.")
            return True  # Already connected

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._socket.connect((self._host, self._port))
        except socket.error:
            logger.error(f"Failed to connect to TCP device at {self._host}:{self._port}")
            self._socket = None

        return self._socket is not None

    def disconnect(self) -> bool:
        if self._socket is not None:
            logger = logging.getLogger(__name__)
            logger.debug(f"Disconnecting from TCP device at {self._host}:{self._port}")
            self._socket.close()
            self._socket = None

        return self._socket is None

    def send(self, data: RequestProtocol) -> bool:
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
            header_length = AnswerProtocol.header_length
            header = self._socket.recv(header_length)
            if not header:
                return None
            data_length = AnswerProtocol.get_data_length_from_header(header)
            data = self._socket.recv(data_length)
            if not data:
                return None

            output = AnswerProtocol.deserialize(data)
            first_timestamp = output[0, 0]
            last_timestamp = output[-1, 0]

            if self._previous_last_timestamp is not None and first_timestamp < self._previous_last_timestamp:
                return None
            self._previous_last_timestamp = last_timestamp

            return output

        except socket.error:
            return None
