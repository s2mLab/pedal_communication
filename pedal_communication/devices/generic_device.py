from abc import ABC, abstractmethod

import numpy as np

from .generic_communication_protocol import GenericRequestProtocol


class GenericDevice(ABC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Indicates whether the device is currently connected.
        """

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the device.

        Returns:
            bool: True if the connection was successful, False otherwise.
        """

    @abstractmethod
    def disconnect(self) -> bool:
        """
        Close the connection to the device.

        Returns:
            bool: True if the disconnection was successful, False otherwise.
        """

    @abstractmethod
    def send(self, message: GenericRequestProtocol) -> bool:
        """
        Send message to the device.

        Parameters:
            message: The message to send.

        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """

    @abstractmethod
    def get_last_data(self) -> np.ndarray | None:
        """
        Receive data from the device.

        Parameters:
            num_bytes (int): Number of bytes to receive.

        Returns:
            AnswerProtocol | None: The data received from the device, or None if no data was received.
        """
