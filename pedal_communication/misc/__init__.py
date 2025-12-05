import socket


class classproperty(property):
    def __get__(self, cls, owner):
        return classmethod(self.fget).__get__(None, owner)()


def recv_exact(socket: socket.socket, data_len: int) -> bytes:
    """
    Read exactly n bytes from a socket. Raises ConnectionError on EOF.
    This handles the fact that socket.recv(n) may return fewer bytes.
    """
    if data_len <= 0:
        return b""

    buf = b""
    while len(buf) < data_len:
        chunk = socket.recv(data_len - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed while reading")
        buf += chunk
    return buf
