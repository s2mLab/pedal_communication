from pedal_communication import TcpDevice, CommunicationProtocol


def main():
    device = TcpDevice(host="localhost", port=1234)
    device.connect()
    device.send(CommunicationProtocol(message="coucou"))
    for _ in range(50):
        data = device.get_next_data()
        print(data)
    device.disconnect()


if __name__ == "__main__":
    main()
