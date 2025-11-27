import time
import logging

from pedal_communication import TcpDevice, Data


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger = logging.getLogger(__name__)

    device = TcpDevice(host="localhost", port=6000)
    while not device.connect():
        time.sleep(1)

    all_data = Data()
    cmp = 0
    while cmp < 100:
        if cmp % 10 == 0:
            logger.info(f"Collecting data... {cmp}/100")

        next_data = device.get_next_data()
        if next_data is None:
            continue
        all_data.add_data(next_data)
        cmp += 1
    device.disconnect()

    all_data.show(Data.Type.FGx, show_now=True)


if __name__ == "__main__":
    main()
