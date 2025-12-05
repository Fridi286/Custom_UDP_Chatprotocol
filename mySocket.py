# my_socket.py
import sys
import threading
from socket import socket, AF_INET, SOCK_DGRAM



class MySocket:

    def __init__(self, host, port):
        self.host = host
        self.port = port

        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.bind((host, port))

        print(f"\n[INFO] Listening on {host}:{port}")

        # Listener Thread starten
        listener_thread = threading.Thread(target=self.listen, daemon=True)
        listener_thread.start()

        # Sender Thread starten
        send_thread = threading.Thread(target=self.send_message(), daemon=True)
        send_thread.start()

        while True:
            pass

    def listen(self):

        while True:
            data, addr = self.sock.recvfrom(4096)
            msg = data.decode("utf-8")

            print(f"\n[RECV from {addr}] {msg}")

    def send_message(self):

        while True:
            try:
                print(f"\nDeine IP: {self.host}, dein Port: {self.port}")
                ip = input("Ziel-IP: ")
                port = int(input("Ziel-Port: "))
                msg = input("Nachricht: ")

                self.sock.sendto(msg.encode("utf-8"), (ip, port))
                print(f"\n[SENT to {ip}:{port}] {msg}")
            except Exception as e:
                print(e)


if __name__ == "__main__":
    host = sys.argv[1]
    port = int(sys.argv[2])
    MySocket(host, port)