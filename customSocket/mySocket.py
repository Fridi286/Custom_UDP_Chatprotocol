# my_socket.py
import ipaddress
import queue
import sys
import threading
import time
from queue import Queue
from queue import SimpleQueue
from fastqueue import Queue as FastQueue



from socket import socket, AF_INET, SOCK_DGRAM

from customSocket.helpers.ack_store import AckStore
from customSocket.helpers.noack_store import NoAckStore
from customSocket.recv_handlers import personal_recv_handler
from customSocket.send_handlers import msg_handler, file_handler
# use package-relative imports so module works when executed as part of the package
from . import byteDecoder, config


class MySocket:

    # ====================================================================================================
    # Constructor
    # ====================================================================================================

    def __init__(self, my_ip, my_port):
        self.my_ip = my_ip
        self.my_port = my_port

        self.my_ip_bytes = int(ipaddress.IPv4Address(my_ip)).to_bytes(4, "big")
        self.my_port_bytes = my_port.to_bytes(2, "big")

        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.bind((host, port))
        print(f"\n[INFO] Listening on {my_ip}:{my_port}")
        #self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)

        # self.send_queue = Queue() #OLD
        self.send_queue = SimpleQueue()

        self.all_incoming = queue.Queue(maxsize=20000)
        self.routing_incoming = queue.Queue(maxsize=10000)
        self.my_incoming = queue.Queue(maxsize=10000)

        self.ack_store = AckStore()
        self.noack_store = NoAckStore()

        self.seq_counter = 1
        self.seq_lock = threading.Lock()
        self.takenSeqNum = set()

        # Listener Thread starten
        threading.Thread(target=self.listen, daemon=True).start()

        # Incoming Handler starten
        threading.Thread(target=self.handel_incoming, daemon=True).start()
        threading.Thread(target=self.handel_my_incoming, daemon=True).start()
        threading.Thread(target=self.handel_routing_incoming, daemon=True).start()

        # Send Loop Threads starten
        for _ in range(1):
            threading.Thread(target=self.send_loop, daemon=True).start()

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
                data, addr = self.sock.recvfrom(8096)
                self.all_incoming.put(data)
            except Exception as e:
                print(e)


    # -------- Handels all incoming data and structures --------------
    def handel_incoming(self):
        queue_get = self.all_incoming.get
        while True:
            data = queue_get()
            if data[5: 9] == self.my_ip_bytes and data[13: 15] == self.my_port_bytes:
                self.my_incoming.put(data)
            else:
                self.routing_incoming.put(data)

    # ---------- Handels data that is adressed to you ------------------
    HANDLERS = {
        1: personal_recv_handler.handle_ack,
        2: personal_recv_handler.handle_no_ack,
        3: personal_recv_handler.handle_hello,
        4: personal_recv_handler.handle_goodbye,
        5: personal_recv_handler.handle_msg,
        6: personal_recv_handler.handle_file_chunk,
        7: personal_recv_handler.handle_file_info,
        8: personal_recv_handler.handle_heartbeat,
        9: personal_recv_handler.handle_routing_update,
    }
    def handel_my_incoming(self):
        queue_get = self.my_incoming.get
        while True:
            data = queue_get()
            msgType = data[0:1]
            self.HANDLERS[msgType](self, data)

    # ---------- Handels data which is not for you and needs routing ---
    def handel_routing_incoming(self):
        #TODO Handel routing mechanics -- Depends on the existence of Routing Tables etc
        print("Routing")



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
                    threading.Thread(target=file_handler.send_Data, args=(self, seqNum, msg, dest_ip, dest_port, self.my_ip, self.my_port), daemon=True).start()
                else:
                    threading.Thread(target=msg_handler.send_Text, args=(self, seqNum, msg, dest_ip, dest_port, self.my_ip, self.my_port), daemon=True).start()
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
        send = self.sock.sendto
        queue_get = self.send_queue.get

        while True:
            packet, addr = queue_get()
            send(packet, addr)

    # ====================================================================================================
    # Starter
    # ====================================================================================================
if __name__ == "__main__":
    host = sys.argv[1]
    port = int(sys.argv[2])
    MySocket(host, port)