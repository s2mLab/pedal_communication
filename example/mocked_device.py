import logging

from pedal_communication.mockers import UdpPedalDeviceMocker


def main():
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    mocker = UdpPedalDeviceMocker()

    try:
        mocker.run()
    except KeyboardInterrupt:
        pass
    finally:
        mocker.dispose()


if __name__ == "__main__":
    main()
