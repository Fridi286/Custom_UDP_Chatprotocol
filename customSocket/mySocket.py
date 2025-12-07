# my_socket.py
import ipaddress
import sys
import threading
import hashlib
from socket import socket, AF_INET, SOCK_DGRAM

# use package-relative imports so module works when executed as part of the package
from . import byteDecoder, byteEncoder
from .models import MsgMessage, Header, MsgPayload


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

        # Sender Thread starten (pass the function, don't call it)
        send_thread = threading.Thread(target=self.send_message, daemon=True)
        send_thread.start()

        while True:
            pass

    def listen(self):

        while True:
            data, addr = self.sock.recvfrom(4096)
            msg = byteDecoder.decodePayload(data)

            print(f"\n[RECV from {addr}] \n{msg}")

    def send_message(self):

        while True:
            try:
                print(f"\nDeine IP: {self.host}, dein Port: {self.port}")
                ip = input("Ziel-IP: ")
                port = int(input("Ziel-Port: "))
                msg = input("Nachricht: ")

                # prepare payload bytes and checksum so Header validation succeeds
                payload_bytes = msg.encode('utf-8')
                payload_length = len(payload_bytes)
                checksum = hashlib.sha256(payload_bytes).digest()

                header = Header(
                    type=5,
                    sequence_number=1,
                    destination_ip=int(ipaddress.IPv4Address(ip)),
                    source_ip=int(ipaddress.IPv4Address(self.host)),
                    destination_port=port,
                    source_port=self.port,
                    payload_length=payload_length,
                    chunk_id=0,
                    chunk_length=0,
                    ttl=10,
                    checksum=checksum,
                )
                data = MsgMessage(
                    header=header,
                    payload=MsgPayload(
                        text=msg
                    )
                )

                self.sock.sendto(byteEncoder.encodePayload(data), (ip, port))
                print(f"\n[SENT to {ip}:{port}] {msg}")
            except Exception as e:
                print(e)


if __name__ == "__main__":
    host = sys.argv[1]
    port = int(sys.argv[2])
    MySocket(host, port)