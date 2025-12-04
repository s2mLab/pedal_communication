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
    data_collector.show_live([DataType.A0, DataType.A1])
    # FGx = 0 Force vers l'avant lorsque la pédale a le fil par en bas

    # data_collector.show_live(DataType.FGy)
    # FGy = 1 Force sortant du pédalier vers la gauche

    # data_collector.show_live(DataType.FGz)
    # FGz = 2

    # data_collector.show_live(DataType.FDx)
    # FDx = 3 Moment x

    # data_collector.show_live(DataType.FDy)
    # FDy = 4 Moment y

    # data_collector.show_live(DataType.FDz)
    # FDz = 5 Moment z

    # data_collector.show_live(DataType.MGx)
    # MGx = 6  ?

    # data_collector.show_live(DataType.A19)

    # data_collector.show_live(DataType.MGy)
    # MGy = 7 # Angle ?

    # data_collector.show_live(DataType.A8)
    # MGz = 8  Fx droit

    # data_collector.show_live(DataType.A9)
    # MDx = 9  # Fy droit

    # data_collector.show_live(DataType.A10)
    # MDy = 10  Fz droit

    # data_collector.show_live(DataType.A11)
    # MDz = 11

    # data_collector.show_live(DataType.A12)
    # TG = 12

    # data_collector.show_live(DataType.A13)
    # TD = 13  Moment z positif en sens anti horaire (vers l'intérieur)

    # data_collector.show_live(DataType.A18)
    # 18 ange du pédalier en radiant

    # data_collector.show_live(DataType.A35)
    # 35 vitesse du pédalier positif vers l'avant

    # data_collector.show_live(DataType.A37)
    # 37  puissance pedale droite

    data_collector.show_live(DataType.A38)
    # 38 puissance

    # data_collector.show_live(DataType.A41)
    # 41  ?

    # ...or just start collecting data in the background
    # data_collector.start()
    # do_something(data_collector)
    # data_collector.stop()


if __name__ == "__main__":
    main()
