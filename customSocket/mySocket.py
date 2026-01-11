# my_socket.py
import ipaddress
import queue
import signal
import sys
import threading
import time
from queue import SimpleQueue
from socket import socket, AF_INET, SOCK_DGRAM
from typing import Tuple

from _socket import SOL_SOCKET, SO_RCVBUF, SO_SNDBUF

from customSocket.helpers.ack_store import AckStore
from customSocket.helpers.file_store import FileStore
from customSocket.helpers.noack_store import NoAckStore
from customSocket.recv_handlers import personal_recv_handler
from customSocket.routing.neigbor_table import NextNeighborTable
from customSocket.routing.neighbor_monitor import NeighborMonitor
from customSocket.routing.routing_table import RoutingTable
from customSocket.routing.routing_table_monitor import RoutingTableMonitor
from customSocket.send_handlers import send_msg_handler, send_file_handler, send_ack_handler, send_no_ack_handler, \
    send_heartbeat_handler, \
    send_hello_handler, send_routing_update_handler, send_goodbye_handler
# In mySocket.py nach den Imports hinzufügen:
from customSocket.websocket_server import notify_file_complete, notify_file_sent, notify_message_received, \
    notify_file_received
from . import config


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

        # Puffer-Einstellungen (wie zuvor besprochen)
        try:
            self.sock.setsockopt(SOL_SOCKET, SO_RCVBUF, 8 * 1024 * 1024)
            self.sock.setsockopt(SOL_SOCKET, SO_SNDBUF, 4 * 1024 * 1024)
            print("[INFO] Socket Buffer: RCV 8MB, SND 4MB")
        except Exception as e:
            print(f"[WARN] Buffersize konnte nicht gesetzt werden: {e}")

        print(f"\n[INFO] Listening on {my_ip_str}:{my_port}\n")

        self.websocket_callback = None
        self.send_queue = SimpleQueue()

        # OPTIMIERUNG: 'all_incoming' entfernt. Wir dispatchen direkt.
        # self.all_incoming = queue.Queue(maxsize=20000)

        # ALT:
        # self.routing_incoming = queue.Queue(maxsize=10000)
        # self.my_incoming = queue.Queue(maxsize=10000)

        # NEU:
        self.routing_incoming = queue.SimpleQueue()
        self.my_incoming = queue.SimpleQueue()

        # storage for acks and noacks
        self.ack_store = AckStore()
        self.noack_store = NoAckStore()

        # storage for all files
        self.file_store = FileStore(
            on_frame_complete=self.send_ack_frame,
            on_frame_timeout=self.send_noack_frame,
            mySocket=self,
            on_file_complete=self.on_file_complete,
        )

        self.seq_counter = 1
        self.seq_lock = threading.Lock()
        self.takenSeqNum = set()

        self.routing_table = RoutingTable()
        self.neighbor_table = NextNeighborTable()

        self.handel_hello()

        # Threading Starts
        neighbor_monitor = NeighborMonitor(self.neighbor_table, self.routing_table, self.send_routing_update)
        neighbor_monitor.start()

        routing_monitor = RoutingTableMonitor(self.routing_table, self.send_routing_update)
        routing_monitor.start()

        threading.Thread(target=self.send_heartbeats, daemon=True).start()

        # Listener Thread starten
        threading.Thread(target=self.listen, daemon=True).start()

        # OPTIMIERUNG: 'handel_incoming' Thread entfernt
        # threading.Thread(target=self.handel_incoming, daemon=True).start()

        threading.Thread(target=self.handel_my_incoming, daemon=True).start()
        threading.Thread(target=self.handel_routing_incoming, daemon=True).start()

        for _ in range(2):
            threading.Thread(target=self.send_loop, daemon=True).start()

        threading.Thread(target=self.send_message, daemon=True).start()

        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

        from customSocket.websocket_server import init_websocket_server
        init_websocket_server(self)

        self.shutdown_event = threading.Event()

        # Callback-Funktion definieren
        def websocket_notify(event_type, data):
            if event_type == 'message':
                notify_message_received(data)
            elif event_type == 'file_info':
                notify_file_received(data)
            elif event_type == 'file_complete':
                notify_file_complete(data)
            elif event_type == 'file_sent':
                notify_file_sent(data)

        self.websocket_callback = websocket_notify

        while True:
            pass

# =====================================================================================================================
# Listening and Routing
# =====================================================================================================================

    def listen(self):
        """
        OPTIMIZED LISTEN:
        Liest vom Socket und entscheidet sofort anhand der Raw-Bytes,
        ob das Paket für uns ist oder geroutet werden muss.
        """
        # Lokale Referenzen für Speed im Loop
        sock_recv = self.sock.recvfrom
        my_in_put = self.my_incoming.put
        route_in_put = self.routing_incoming.put
        my_ip_bytes = self.my_ip_bytes
        packet_size = config.PACKET_SIZE_BYTES + 200  # Etwas Buffer

        print("[INFO] High-Performance Dispatch Listener started")

        while True:
            try:
                data, addr = sock_recv(packet_size)

                # Check Header: Type[0], Seq[1-5], DestIP[5-9]
                # Wenn Paket kaputt oder zu kurz -> ignorieren
                if len(data) < 9:
                    continue

                # Schneller Byte-Vergleich der Destination IP (Bytes 5 bis 9)
                dest_ip_slice = data[5:9]

                if dest_ip_slice == my_ip_bytes:
                    # Paket ist für mich -> direkt in my_incoming
                    my_in_put((data, addr))
                else:
                    # Paket ist für jemand anderen -> Routing
                    route_in_put((data, addr))

            except Exception as e:
                # Bei Socket-Shutdown oder Fehlern
                if self.shutdown_event.is_set():
                    break
                print(f"[ERROR] Listen Loop: {e}")

    # OPTIMIERUNG: Diese Funktion wird nicht mehr benötigt
    # def handel_incoming(self):
    #     pass

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
        # Header Parsing Optimierung: Wir vertrauen darauf, dass listen() vorsortiert hat

        while True:
            data, addr = queue_get()

            try:
                # Type ist das erste Byte
                msg_type = data[0]

                handler = self.HANDLERS.get(msg_type)
                if handler:
                    handler(self, data, self.send_routing_update)
                else:
                    print(f"Unknown Message Type for me: {msg_type}")
            except Exception as e:
                print(f"[ERROR] Handling packet: {e}")

    # ---------- Handels data which is not for you and needs routing ---
    def handel_routing_incoming(self):
        queue_get = self.routing_incoming.get
        while True:
            data = queue_get()
            dest_ip = int.from_bytes(data[5:9])
            dest_port = int.from_bytes(data[13: 15])
            self.send_queue.put((data, (str(ipaddress.IPv4Address(dest_ip)), dest_port)))



    # ---------- Handels ACK and NOACK of data sent to you -

    def send_ack_frame(self, seq_num, src_ip, src_port):
        send_ack_handler.send_ack(self, seq_num, src_ip, src_port, self.my_ip_str, self.my_port)

    def send_noack_frame(self, key, missing_chunks):
        seq_num, src_ip, src_port = key
        print(f"[NOACK] missing {missing_chunks}")
        send_no_ack_handler.send_no_ack(self, seq_num, src_ip, src_port, self.my_ip_str, self.my_port, missing_chunks)

    # --------- Handel routing/neigbor Updates ----------------------------------
    def send_routing_update(self):
        send_routing_update_handler.send_routing_update(self)

    # --------- Send heartbeats ----------------------------------
    def send_heartbeats(self):
        while True:
            #print(self.routing_table.export_for_update())
            neighbors = self.neighbor_table.get_alive_neighbors()
            seqNum = self.get_seq_num()
            send_routing_update_handler.send_routing_update(self)
            for entry in neighbors:
                send_heartbeat_handler.send_heartbeat(self, seqNum, entry.ip, entry.port, self.my_ip_str, self.my_port)
            #print(f"\n[SENT]Heartbeats to: {neighbors}\n")
            time.sleep(config.HEARTBEAT_TIMER)

# =====================================================================================================================
# Sending Hello and Goodbye
# =====================================================================================================================

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
            send_hello_handler.send_hello(self, self.get_seq_num(), dest_ip, int(dest_port), self.my_ip_str, self.my_port)
        return

    def _shutdown_handler(self, signum, frame):
        print("\n[INFO] Beende Anwendung...")
        neighbors = self.neighbor_table.get_alive_neighbors()
        for entry in neighbors:
            dest_ip = entry.ip
            dest_port = entry.port
            send_goodbye_handler.send_goodbye(self, self.get_seq_num(), dest_ip, dest_port, self.my_ip_str, self.my_port)
            pass

        print("[INFO] Anwendung beendet.")
        sys.exit(0)

# =====================================================================================================================
# Sending MSG and DATA
# =====================================================================================================================

    def send_message(self):

        while True:
            try:
                dest_ip = input("\nZiel-IP: ")
                dest_port = int(input("\nZiel-Port: "))
                msg = input("\nGib deine Nachricht ein (Wenn du eine Datei verschicken willst, gib \"Send Data\" ein): ")
                seqNum = self.get_seq_num()
                if msg.upper() == "SEND DATA":
                    threading.Thread(target=send_file_handler.send_Data, args=(self, seqNum, msg, dest_ip, dest_port, self.my_ip_str, self.my_port), daemon=True).start()
                else:
                    threading.Thread(target=send_msg_handler.send_Text, args=(self, seqNum, msg, dest_ip, dest_port, self.my_ip_str, self.my_port), daemon=True).start()
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
            ip, port = addr
            routing_info = self.routing_table.get_route(int(ipaddress.IPv4Address(ip)), port)
            if routing_info:
                addr = (str(ipaddress.IPv4Address(routing_info.next_hop_ip)), routing_info.next_hop_port)
            send(packet, addr)

    # =======================================================================================
    # Websocket Callback for on_file_complete
    # =================================================================================
    def on_file_complete(self, seq_num, src_ip, src_port, filename, file_path):
        """Wird aufgerufen wenn eine Datei vollständig empfangen wurde"""
        if self.websocket_callback:
            self.websocket_callback('file_complete', {
                'seq_num': seq_num,
                'src_ip': src_ip,
                'src_port': src_port,
                'filename': filename,
                'file_path': file_path
            })

    # ---------------- WEBSOCKET GOODBYE CALLBACK ----------
    def shutdown_gracefully(self):
        """Sendet Goodbye an alle Nachbarn und beendet den Socket ordnungsgemäß"""
        if self.shutdown_event.is_set():
            return  # Bereits im Shutdown-Prozess

        self.shutdown_event.set()

        print("\n[INFO] Sende Goodbye an alle Nachbarn...")
        neighbors = self.neighbor_table.get_alive_neighbors()

        for entry in neighbors:
            dest_ip = entry.ip
            dest_port = entry.port
            send_goodbye_handler.send_goodbye(
                self,
                self.get_seq_num(),
                dest_ip,
                dest_port,
                self.my_ip_str,
                self.my_port
            )
            print(f"[GOODBYE] Gesendet an {dest_ip}:{dest_port}")

        # Wartezeit damit Goodbye-Pakete gesendet werden
        time.sleep(1.5)

        # Socket schließen
        try:
            self.sock.close()
            print("[INFO] Socket geschlossen")
        except Exception as e:
            print(f"[ERROR] Beim Schließen: {e}")

        # Prozess hart beenden (funktioniert auch mit Threads)
        print("[INFO] Beende Anwendung...")
        import os
        os._exit(0)



# =====================================================================================================================
# Starter
# =====================================================================================================================
if __name__ == "__main__":
    host = sys.argv[1]
    port = int(sys.argv[2])
    MySocket(host, port)