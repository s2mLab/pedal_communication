from pedal_communication.mockers import DeviceMocker


def main():
    mocker = DeviceMocker()

    for i in range(3):
        mocker.run()


if __name__ == "__main__":
    main()
