import socket

from .generic_device import GenericDevice
from .communication_protocol import CommunicationProtocol


class TcpDevice(GenericDevice):
    def __init__(self, host: str, port: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._host = host
        self._port = port

        self._socket: socket.socket | None = None

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
        if self._socket is not None:
            return True  # Already connected

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._socket.connect((self._host, self._port))
        except socket.error:
            self._socket = None

        return self._socket is not None

    def disconnect(self) -> bool:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

        return self._socket is None

    def send(self, data: CommunicationProtocol) -> bool:
        if self._socket is None:
            return False

        try:
            self._socket.sendall(data.serialized)
            return True
        except socket.error:
            return False

    def get_next_data(self) -> CommunicationProtocol | None:
        if self._socket is None:
            return None

        try:
            header_length = CommunicationProtocol.header_length
            data = self._socket.recv(header_length)
            data_length = CommunicationProtocol.get_data_length_from_header(data)
            data += self._socket.recv(data_length)

            return CommunicationProtocol.deserialize(data)
        except socket.error:
            return None
