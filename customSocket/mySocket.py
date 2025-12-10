# my_socket.py
import ipaddress
import queue
import sys
import threading
import time
from queue import Queue
from queue import SimpleQueue



from socket import socket, AF_INET, SOCK_DGRAM
from typing import Tuple

from customSocket.helpers.ack_store import AckStore
from customSocket.helpers.file_store import FileStore
from customSocket.helpers.noack_store import NoAckStore
from customSocket.recv_handlers import personal_recv_handler
from customSocket.routing.neigbor_table import NextNeighborTable
from customSocket.routing.neighbor_monitor import NeighborMonitor
from customSocket.routing.routing_table import RoutingTable
from customSocket.routing.routing_table_monitor import RoutingTableMonitor
from customSocket.send_handlers import msg_handler, file_handler, ack_handler, no_ack_handler, heartbeat_handler, \
    hello_handler, routing_update_handler
from . import byteDecoder, config


class MySocket:

    # ====================================================================================================
    # Constructor
    # ====================================================================================================

    def __init__(self, my_ip_str, my_port):
        self.my_ip_str = my_ip_str
        self.my_port = my_port

        self.my_ip_bytes = int(ipaddress.IPv4Address(my_ip_str)).to_bytes(4, "big")
        self.my_port_bytes = my_port.to_bytes(2, "big")

        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.bind((host, port))
        print(f"\n[INFO] Listening on {my_ip_str}:{my_port}\n")
        #self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)

        # self.send_queue = Queue() #OLD
        self.send_queue = SimpleQueue()

        # queues for all incomming msgs
        self.all_incoming = queue.Queue(maxsize=20000)
        self.routing_incoming = queue.Queue(maxsize=10000)
        self.my_incoming = queue.Queue(maxsize=10000)

        # storage for acks and noacks
        self.ack_store = AckStore()
        self.noack_store = NoAckStore()

        # storage for all files that the user receives
        self.file_store = FileStore(
            on_frame_complete=self.send_ack_frame,  #Callback function
            on_frame_timeout=self.send_noack_frame  #Callback function
        )

        # Sequence Number Producer
        self.seq_counter = 1
        self.seq_lock = threading.Lock()
        self.takenSeqNum = set()

        # Routing Logic
        self.routing_table = RoutingTable()
        self.neighbor_table = NextNeighborTable()

        # Hello Logic - After giving Hello IP/Ports Code, socket will run
        self.hello_list = self.handel_hello()

        # Garbage Collector and File Assembler

        # Neighbor Monitoring Thread starten
        neighbor_monitor = NeighborMonitor(
            self.neighbor_table,
            self.routing_table,
            on_routing_update=self.send_routing_update,  #Callback function
        )
        neighbor_monitor.start()

        # Routing Table Monitor starten (überwacht poisoned routes)
        routing_monitor = RoutingTableMonitor(
            self.routing_table,
            on_routing_update=self.send_routing_update  #Callback function
        )
        routing_monitor.start()

        # Heartbeat starten
        heartbeat = threading.Thread(target=self.send_heartbeats, daemon=True)
        heartbeat.start()

        # Listener Thread starten
        threading.Thread(target=self.listen, daemon=True).start()

        # Incoming Handler starten
        threading.Thread(target=self.handel_incoming, daemon=True).start()
        threading.Thread(target=self.handel_my_incoming, daemon=True).start()
        threading.Thread(target=self.handel_routing_incoming, daemon=True).start()

        # Send Loop Threads starten
        for _ in range(5):
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
            msgType = int.from_bytes(data[0:1], "big")
            self.HANDLERS[msgType](self, data, on_routing_update=self.send_routing_update)

    # ---------- Handels data which is not for you and needs routing ---
    def handel_routing_incoming(self):
        routing_update_handler.send_routing_update(self)
        #TODO Handel routing mechanics -- Depends on the existence of Routing Tables etc
        print("Routing")

    # ---------- Handels ACK and NOACK of data sent to you -

    def send_ack_frame(self, seq_num, src_ip, src_port):
        ack_handler.send_ack(self, seq_num, src_ip, src_port, self.my_ip_str, self.my_port)

    def send_noack_frame(self, key, missing_chunks):
        seq_num, src_ip, src_port = key
        print(f"[NOACK] missing {missing_chunks}")
        no_ack_handler.send_no_ack(self, seq_num, src_ip, src_port, self.my_ip_str, self.my_port, missing_chunks)

    # --------- Handel routing/neigbor Updates ----------------------------------
    def send_routing_update(self):
        routing_update_handler.send_routing_update(self)
        print("[SENT] Routing Update")

    # --------- Send heartbeats ----------------------------------
    def send_heartbeats(self):
        while True:
            neighbors = self.neighbor_table.get_alive_neighbors()
            seqNum = self.get_seq_num()
            for entry in neighbors:
                heartbeat_handler.send_heartbeat(self, seqNum, entry.ip, entry.port, self.my_ip_str, self.my_port)
            #print(f"\n[SENT]Heartbeats to: {neighbors}\n")
            time.sleep(config.HEARTBEAT_TIMER)

    # ====================================================================================================
    # Sending Hello and Goodbye
    # ====================================================================================================

    def handel_hello(self):
        neighbors = []
        entry: Tuple[str, int]
        print("\nBitte gib im folgenden jeweils die IP und den Port der Nachbar ein die du hinzufügen willst.\nEine leere Eingabe beendet das hinzufügen.\n")
        while True:
            entry_ip = input("\nGib die IP eines Nachbarns ein:")
            if not entry_ip: break
            entry_port = input("\nGib die den Port des Nachbarns ein:")
            if not entry_port: break
            neighbors.append((entry_ip, entry_port))

        for entry in neighbors:
            dest_ip, dest_port = entry
            hello_handler.send_hello(self, self.get_seq_num(), dest_ip, int(dest_port), self.my_ip_str, self.my_port)
        return

    # ====================================================================================================
    # Sending MSG and DATA
    # ====================================================================================================

    def send_message(self):

        while True:
            try:
                dest_ip = input("\nZiel-IP: ")
                dest_port = int(input("\nZiel-Port: "))
                msg = input("\nGib deine Nachricht ein (Wenn du eine Datei verschicken willst, gib \"Send Data\" ein): ")
                seqNum = self.get_seq_num()
                if msg.upper() == "SEND DATA":
                    threading.Thread(target=file_handler.send_Data, args=(self, seqNum, msg, dest_ip, dest_port, self.my_ip_str, self.my_port), daemon=True).start()
                else:
                    threading.Thread(target=msg_handler.send_Text, args=(self, seqNum, msg, dest_ip, dest_port, self.my_ip_str, self.my_port), daemon=True).start()
            except Exception as e:
                print(e)
            time.sleep(3)

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
            #print(self.send_queue.qsize())
            packet, addr = queue_get()
            send(packet, addr)

    # ====================================================================================================
    # Starter
    # ====================================================================================================
if __name__ == "__main__":
    host = sys.argv[1]
    port = int(sys.argv[2])
    MySocket(host, port)