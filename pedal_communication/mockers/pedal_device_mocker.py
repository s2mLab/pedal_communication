from abc import ABC, abstractmethod


class PedalDeviceMocker(ABC):
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Indicates whether a client is currently connected or not
        """

    @abstractmethod
    def run(self):
        """
        Start the mock device server.
        """

    @abstractmethod
    def dispose(self):
        """
        Dispose the mock device server. After disposing, the server cannot be restarted.
        """
