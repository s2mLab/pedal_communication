from enum import Enum
import time
import threading
import queue
from typing import Iterable

import numpy as np

from ..devices.generic_device import GenericDevice
from ..misc import classproperty


class DataType(Enum):
    """
    For the left pedal:
    X Axis points forward if the pedal is vertically oriented with the cable pointing downwards.
    Y Axis points to the left side of the pedal, perpendicular to the chain ring.
    Z Axis points upward in line with the long axis of the pedal.

    For the right pedal:
    Same as left, but Y Axis points to the right side of the pedal and Z Axis points downward.

    Angles are given in radians.

    Speed are positive when pedaling forward.

    The AX values are unknown for now.
    """

    FX_LEFT = 0
    FY_LEFT = 1
    FZ_LEFT = 2
    MX_LEFT = 3
    MY_LEFT = 4
    MZ_LEFT = 5
    A6 = 6
    A7 = 7
    FX_RIGHT = 8
    FY_RIGHT = 9
    FZ_RIGHT = 10
    A11 = 11
    A12 = 12
    A13 = 13
    A14 = 14
    A15 = 15
    A16 = 16
    A17 = 17
    PEDAL_ANGLE = 18
    TIME = 19
    A20 = 20
    A21 = 21
    A22 = 22
    A23 = 23
    A24 = 24
    A25 = 25
    A26 = 26
    A27 = 27
    A28 = 28
    A29 = 29
    A30 = 30
    A31 = 31
    A32 = 32
    A33 = 33
    A34 = 34
    PEDALLING_SPEED = 35
    POWER_LEFT = 36
    POWER_RIGHT = 37
    POWER_TOTAL = 38
    A39 = 39
    A40 = 40
    A41 = 41
    A42 = 42
    A43 = 43
    A44 = 44


class Data:
    def __init__(self, data: np.ndarray | None = None):
        if data is None:
            data = np.empty((0, self.columns_count + 1))
        else:
            if data.shape[1] != self.columns_count + 1:
                raise ValueError(f"Data must have {self.columns_count + 1} columns.")
        self._data = data
        if len(self._data.shape) == 1:
            self._data = self._data[None, :]

    def add_data(self, new_data: np.ndarray) -> None:
        self._data = np.concatenate((self._data, new_data), axis=0)

    @property
    def timestamp(self) -> np.ndarray:
        return self._data[:, 0]

    @classproperty
    def columns_count(cls) -> int:
        return 42

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

            data = self._device.get_last_data()
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
        curves = [plot.plot(pen=colors[idx]) for idx, i in enumerate(data_indices)]

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
