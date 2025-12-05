from pedal_communication.mockers import UdpPedalDeviceMocker


def main():
    mocker = UdpPedalDeviceMocker()

    while True:
        # Restart the mocker indefinitely if it disconnects
        mocker.run()


if __name__ == "__main__":
    main()
