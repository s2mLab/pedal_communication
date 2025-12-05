from abc import ABC, abstractmethod


class GenericRequestProtocol(ABC):
    @property
    @abstractmethod
    def serialized(self) -> bytes:
        """
        Get the serialized byte representation of the request.

        Returns:
            bytes: The serialized request.
        """
