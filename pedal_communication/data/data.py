from enum import Enum
import time
import threading
import queue
from typing import Iterable

import numpy as np

from ..devices.generic_device import GenericDevice


class DataType(Enum):
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


class Data:
    def __init__(self, data: np.ndarray | None = None):
        if data is None:
            data = np.empty((0, self.columns_count + 1))
        else:
            if data.shape[1] != self.columns_count + 1:
                raise ValueError(f"Data must have {self.columns_count + 1} columns.")
        self._data = data

    def add_data(self, new_data: np.ndarray) -> None:
        self._data = np.concatenate((self._data, new_data), axis=0)

    @property
    def timestamp(self) -> np.ndarray:
        return self._data[:, 0]

    @property
    @staticmethod
    def columns_count(self) -> int:
        return 14

    def __getitem__(self, time_indices: int | slice | tuple | list) -> "Data":
        return Data(data=self._data[time_indices, :])

    @property
    def values(self) -> np.ndarray:
        return self._data[:, 1:]

    def clear(self) -> None:
        self._data = np.empty((0, self.columns_count + 1))

    def show(self, data_type: DataType, show_now: bool) -> None:
        from matplotlib import pyplot as plt

        plt.plot(self.timestamp, self.values[:, data_type.value], label=data_type.name)
        if show_now:
            plt.show()


class DataCollector(threading.Thread):
    def __init__(self, device: GenericDevice):
        super().__init__(daemon=True)
        self._queue = queue.Queue()
        self._device = device
        self._data = Data()
        self._is_running = False

    @property
    def data(self) -> Data:
        return self._data

    def start(self) -> None:
        self._is_running = True
        if not self.is_alive():
            super().start()
        self._data.clear()

    def stop(self) -> None:
        self._is_running = False

    def run(self) -> None:
        condition = threading.Condition()
        while self.is_alive():
            with condition:
                while not self._is_running:
                    condition.wait()

            data = self._device.get_next_data()
            if data is not None:
                self._data.add_data(data)
                self._queue.put(True)

            time.sleep(0.001)  # avoid burning CPU

        self._device.disconnect()

    def show_live(self, data_type: DataType | Iterable[DataType], window_len: int = 300) -> None:
        import pyqtgraph as pg
        from pyqtgraph.Qt import QtWidgets, QtCore

        if not isinstance(data_type, Iterable):
            data_type = [data_type]

        data_indices = [dt.value for dt in data_type]
        colors = ["r", "g", "b", "c", "m", "y", "w"]

        def update():
            # read all items currently available
            while not self._queue.empty():
                # Empty the queue
                _ = self._queue.get()

            starting_index = len(self._data.timestamp) - window_len if len(self._data.timestamp) > window_len else 0
            data = self._data[starting_index:]

            for curve, data_index in zip(curves, data_indices):
                curve.setData(data.timestamp, data.values[:, data_index])
            plot.setXRange(data.timestamp[0], data.timestamp[-1])

        app = QtWidgets.QApplication([])
        win = pg.GraphicsLayoutWidget(show=True, title="Data Live Plot")
        plot = win.addPlot()
        curves = [plot.plot(pen=colors[i]) for _, i in enumerate(data_indices)]

        timer = QtCore.QTimer()
        timer.timeout.connect(update)
        timer.start(50)

        # Start the thread
        was_started_from_here = False
        if not self.is_alive():
            was_started_from_here = True
            self.start()
        # Make sure the thread is running
        while not self._is_running:
            time.sleep(0.1)

        app.exec()
        if was_started_from_here:
            self.stop()
