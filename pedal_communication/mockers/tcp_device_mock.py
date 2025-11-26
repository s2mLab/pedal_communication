from ..devices.tcp_device import TcpDevice


class TcpDeviceMock(TcpDevice):
    def __init__(self, host: str, port: int, **kwargs):
        super().__init__(host=host, port=port, **kwargs)
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def connect(self) -> bool:
        # Do nothing for the mock
        self._is_connected = True
        return self._is_connected

    def disconnect(self) -> bool:
        self._is_connected = False
        return not self._is_connected

    def send(self, data: bytes) -> bool:
        # Do nothing for the mock
        return True

    def receive(self, num_bytes: int) -> bytes:
        # Return dummy data for the mock
        return bytes([0] * num_bytes)
