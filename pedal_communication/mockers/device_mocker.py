import socket
import time
import select

from ..devices.communication_protocol import CommunicationProtocol


class DeviceMocker:
    # A simple mock device that simulates basic behavior.
    def __init__(self, port: int = 1234):
        self._port = port
        self._socket: socket.socket = None
        self._connection: socket.socket = None
        self._is_running = False

    def run(self):
        """
        Start the mock device server.
        """
        self._start_listening()

    def _serve_data(self):
        if self._connection is None:
            return

        # Check if client sent data
        ready_to_read, _, _ = select.select([self._connection], [], [], 0)
        if ready_to_read:
            try:
                header_length = CommunicationProtocol.header_length
                data = self._connection.recv(header_length)
                if not data:
                    print("Client disconnected.")
                    self._stop_listening()
                    return

                data_length = CommunicationProtocol.get_data_length_from_header(data)
                data += self._connection.recv(data_length)
                data = CommunicationProtocol.deserialize(data)

                if data.message == "STOP":
                    print("Received STOP command from client.")
                    self._stop_listening()
                    return
            except ConnectionResetError:
                print("Client disconnected.")
                self._stop_listening()
                return

        # Simulate sending some data
        try:
            self._connection.sendall(CommunicationProtocol(message="Mocked device data\n").serialized)
        except BrokenPipeError:
            print("Client disconnected.")
            self._stop_listening()

    def _start_listening(self):
        try:
            print(f"DeviceMock listening on port {self._port}")

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.bind(("localhost", self._port))
            self._socket.listen(1)
            self._connection, addr = self._socket.accept()
            print(f"Connection from {addr} has been established!")

            self._is_running = True
            while self._is_running:
                self._serve_data()
                time.sleep(0.2)

        except KeyboardInterrupt:
            print("Shutting down DeviceMocker.")
        finally:
            self._stop_listening()

    def _stop_listening(self):
        self._is_running = False

        if self._connection:
            self._connection.close()
            print("Connection closed.")
        self._connection = None

        if self._socket:
            self._socket.close()
            print("DeviceMock stopped listening.")
        self._socket = None
