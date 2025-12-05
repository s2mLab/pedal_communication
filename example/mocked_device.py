from pedal_communication.mockers import TcpPedalDeviceMocker


def main():
    mocker = TcpPedalDeviceMocker()

    while True:
        # Restart the mocker indefinitely if it disconnects
        mocker.run()


if __name__ == "__main__":
    main()
