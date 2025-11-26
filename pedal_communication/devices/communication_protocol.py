from ..misc import classproperty


class CommunicationProtocol:
    version: str = "1.0.0"
    header_length: int = 8

    def __init__(self, message: str):
        self._message = message

    def __repr__(self) -> str:
        return f"CommunicationProtocol(version={self.version}, message={self._message})"

    def __str__(self) -> str:
        return f"Message: {self._message}"

    @property
    def message(self) -> str:
        return self._message

    @classproperty
    def version(cls) -> str:
        return "1.0.0"

    @property
    def serialized(self) -> str:
        header = self._prepare_header()
        body = self._prepare_body()

        header_length = len(header).to_bytes(4, byteorder="little")
        body_length = len(body).to_bytes(4, byteorder="little")

        return header_length + body_length + header.encode() + body.encode()

    @classproperty
    def header_length(cls) -> int:
        return 8

    @staticmethod
    def get_data_length_from_header(header_data: bytes) -> int:
        return sum(CommunicationProtocol._get_lengths_from_header(header_data))

    @staticmethod
    def _get_lengths_from_header(header_data: bytes) -> tuple[int, int]:
        if len(header_data) < 8:
            raise ValueError("Data too short to contain valid protocol information.")

        header_length = int.from_bytes(header_data[0:4], byteorder="little")
        body_length = int.from_bytes(header_data[4:8], byteorder="little")
        return header_length, body_length

    @staticmethod
    def deserialize(data: bytes) -> "CommunicationProtocol":
        header_length, body_length = CommunicationProtocol._get_lengths_from_header(data[0:8])

        expected_length = 8 + header_length + body_length
        if len(data) < expected_length:
            raise ValueError("Data length does not match expected lengths.")

        # Get the header data
        header_data = data[8 : 8 + header_length].decode()
        (version,) = CommunicationProtocol._extract_header(header_data)
        if version != CommunicationProtocol.version:
            raise ValueError(f"Unsupported protocol version: {version}")

        # Get the body data
        body_data = data[8 + header_length : expected_length].decode()
        (message,) = CommunicationProtocol._extract_body(body_data)

        return CommunicationProtocol(message=message)

    def _prepare_header(self) -> str:
        return f"PROTOCOL/{self.version}\n"

    def _prepare_body(self) -> str:
        return f"MESSAGE:{self._message}\n"

    @staticmethod
    def _extract_header(data: str) -> list[str]:
        version = CommunicationProtocol._extract_version_from_header(data)
        return [version]

    @staticmethod
    def _extract_version_from_header(header: str) -> str:
        return header.split("/")[1].split("\n")[0].strip()

    @staticmethod
    def _extract_body(data: str) -> list[str]:
        message_line = next((line for line in data.splitlines() if line.startswith("MESSAGE:")), None)
        if message_line is None:
            raise ValueError("MESSAGE field not found in body.")
        message = message_line.split(":", 1)[1]
        return [message]
