# my_socket.py
import sys
import threading
from queue import Queue
from socket import socket, AF_INET, SOCK_DGRAM

from customSocket.helpers.ack_store import AckStore
from customSocket.helpers.noack_store import NoAckStore
from customSocket.send_handlers import msg_handler, file_handler
# use package-relative imports so module works when executed as part of the package
from . import byteDecoder


class MySocket:

    # ====================================================================================================
    # Constructor
    # ====================================================================================================

    def __init__(self, my_ip, my_port):
        self.my_ip = my_ip
        self.my_port = my_port

        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.bind((host, port))

        self.send_queue = Queue()

        self.ack_store = AckStore()
        self.noack_store = NoAckStore()

        print(f"\nYour IP: {self.my_ip}, Your Port: {self.my_port}")

        print(f"\n[INFO] Listening on {my_ip}:{my_port}")

        self.seq_counter = 1
        self.seq_lock = threading.Lock()
        self.takenSeqNum = set()

        # Listener Thread starten
        listener_thread = threading.Thread(target=self.listen, daemon=True)
        listener_thread.start()

        # Sending Queue starten
        sender_thread = threading.Thread(target=self.send_loop, daemon=True)
        sender_thread.start()

        # Sender Thread starten
        send_thread = threading.Thread(target=self.send_message, daemon=True)
        send_thread.start()

        while True:
            pass

    # ====================================================================================================
    # Listening and Routing
    # ====================================================================================================

    def listen(self):

        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
                msg = byteDecoder.decodePayload(data)

                print(f"\n[RECV from {addr}] \n{msg}")
            except Exception as e:
                print(e)

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
                    threading.Thread(target=file_handler.send_Data, args=(seqNum, msg, dest_ip, dest_port, self.my_ip, self.my_port, self.send_queue), daemon=True).start()
                else:
                    threading.Thread(target=msg_handler.send_Text, args=(seqNum, msg, dest_ip, dest_port, self.my_ip, self.my_port, self.send_queue), daemon=True).start()
            except Exception as e:
                print(e)

    # ----------- Set Sequence Number ------------
    def get_seq_num(self):
        with self.seq_lock:
            num = self.seq_counter
            self.seq_counter += 1
            self.takenSeqNum.add(num)
            return num

    # ----------- Sending Loop waits for items in the queue, continouisly checks if the queue has data to send
    def send_loop(self):
        while True:
            try:
                packet, addr = self.send_queue.get()
                self.sock.sendto(packet, addr)
            except Exception as e:
                print("[SEND ERROR]", e)

    # ====================================================================================================
    # Starter
    # ====================================================================================================
if __name__ == "__main__":
    host = sys.argv[1]
    port = int(sys.argv[2])
    MySocket(host, port)