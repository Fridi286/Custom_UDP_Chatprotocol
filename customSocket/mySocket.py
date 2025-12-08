# my_socket.py
import ipaddress
import os.path
import sys
import threading
import hashlib
from socket import socket, AF_INET, SOCK_DGRAM

# use package-relative imports so module works when executed as part of the package
from . import byteDecoder, byteEncoder
from .models import MsgMessage, Header, MsgPayload


class MySocket:

    # ====================================================================================================
    # Constructor
    # ====================================================================================================
    def __init__(self, host, port):
        self.host = host
        self.port = port

        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.bind((host, port))

        print(f"\nYour IP: {self.host}, Your Port: {self.port}")

        print(f"\n[INFO] Listening on {host}:{port}")

        self.takenSeqNum = {0}

        # Listener Thread starten
        listener_thread = threading.Thread(target=self.listen, daemon=True)
        listener_thread.start()

        # Sender Thread starten (pass the function, don't call it)
        send_thread = threading.Thread(target=self.send_message, daemon=True)
        send_thread.start()

        while True:
            pass

    # ====================================================================================================
    # Listening and Routing
    # ====================================================================================================

    def listen(self):

        while True:
            data, addr = self.sock.recvfrom(4096)
            msg = byteDecoder.decodePayload(data)

            print(f"\n[RECV from {addr}] \n{msg}")

    # ====================================================================================================
    # Sending MSG and DATA
    # ====================================================================================================

    def send_message(self):

        while True:
            try:
                dest_ip = input("Ziel-IP: ")
                dest_port = int(input("Ziel-Port: "))
                msg = input("Gib deine Nachricht ein (Wenn du eine Datei verschicken willst, gib \"Send Data\" ein): ")
                seqNum = self.get_seq_num()
                if msg.upper() == "SEND DATA":
                    threading.Thread(target=self.send_Data, args=(seqNum, dest_ip, dest_port), daemon=True).start()
                else:
                    threading.Thread(target=self.send_Text, args=(seqNum, msg, dest_ip, dest_port), daemon=True).start()
            except Exception as e:
                print(e)

    def get_seq_num(self) -> int:
        num = 1
        while True:
            if num in self.takenSeqNum:
                num += 1
            else:
                self.takenSeqNum.add(num)
                return num


    # ============================== Send Files ===============================

    def send_Data(self, seq_Num, dest_ip, dest_port):
        path = input("Gib den Dateipfad der zu verschickenden Datei an: ")
        if not os.path.exists(path):
            print("Pfad existiert nicht!")
            return
        elif not os.path.isfile(path):
            print("Es ist keine Datei!")
            return
        elif not os.access(path, os.R_OK):
            print("Keine Leserechte!")
            return
        else:
            print("Pfad ist gültig und lesbar.")

        # Here starts the real magic

        filename = os.path.basename(path)


        #with open(path, "rb") as f:
            #TODO


        print(path)

    def send_File(self, data, dest_ip, dest_port):
        #TODO
        return


    # ============================== Send Normal Text Message ===============================

    def send_Text(self,seq_num, msg, dest_ip, dest_port):
        # prepare payload bytes and checksum so Header validation succeeds
        payload_bytes = msg.encode('utf-8')
        payload_length = len(payload_bytes)
        checksum = hashlib.sha256(payload_bytes).digest()

        header = Header(
            type=5,
            sequence_number=seq_num,
            destination_ip=int(ipaddress.IPv4Address(dest_ip)),
            source_ip=int(ipaddress.IPv4Address(self.host)),
            destination_port=dest_port,
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

        self.sock.sendto(byteEncoder.encodePayload(data), (dest_ip, dest_port))

        print(f"\n[SENT to {dest_ip}:{dest_port}] {msg}")



    # ====================================================================================================
    # Starter
    # ====================================================================================================
if __name__ == "__main__":
    host = sys.argv[1]
    port = int(sys.argv[2])
    MySocket(host, port)