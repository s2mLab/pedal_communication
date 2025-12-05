import time
import logging

from pedal_communication import PedalDevice, DataType, DataCollector


def do_something(data_collector: DataCollector):
    """
    This is just a showcase of how to use the DataCollector and get the data from it
    In this case we wait for 10 seconds, printing the number of collected data points every second
    """
    logger = logging.getLogger("do_something")
    logger.info("Start doing something with the data collector...")
    for _ in range(10):
        time.sleep(1)
        logger.info(f"Collected {len(data_collector.data.timestamp)} data points.")
    logger.info(f"Collected data timestamps: {data_collector.data.timestamp}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Connect to the device. If no real devices are available, one can run the script `mocked_device.py` to create a
    # local TCP mock device that simulates a real pedal device.
    device = PedalDevice()
    while not device.connect():
        time.sleep(0.1)

    data_collector = DataCollector(device)

    # Either start a live plot...
    data_collector.show_live(DataType.POWER_TOTAL)  # Single value plot
    data_collector.show_live([DataType.FX_LEFT, DataType.FX_RIGHT])  # Multiple values plot

    # ...or just start collecting data in the background
    # data_collector.start()
    # do_something(data_collector)
    # data_collector.stop()


if __name__ == "__main__":
    main()
