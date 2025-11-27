from enum import Enum

import numpy as np
from matplotlib import pyplot as plt


class Data:
    class Type(Enum):
        FGx = 0
        FGy = 1
        FGz = 2
        FDx = 3
        FDy = 4
        FDz = 5
        MGx = 6
        MGy = 7
        MGz = 8
        MDx = 9
        MDy = 10
        MDz = 11
        TG = 12
        TD = 13
        AG = 14
        AD = 15

    def __init__(self, data: np.ndarray | None = None):
        if data is None:
            data = np.empty((0, 15))
        else:
            if data.shape[1] != 15:
                raise ValueError("Data must have 15 columns.")
        self._data = data

    def add_data(self, new_data: np.ndarray) -> None:
        self._data = np.concatenate((self._data, new_data), axis=0)

    @property
    def timestamp(self) -> np.ndarray:
        return self._data[:, 0]

    @property
    def data(self) -> np.ndarray:
        return self._data[:, 1:]

    def show(self, data_type: Type, show_now: bool) -> None:
        plt.plot(self.timestamp, self.data[:, data_type.value], label=data_type.name)
        if show_now:
            plt.show()
