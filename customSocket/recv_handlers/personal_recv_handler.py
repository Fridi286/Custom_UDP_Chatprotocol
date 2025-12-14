import ipaddress
import time

from customSocket import byteDecoder
from customSocket.helpers.models import NoAckMessage
from customSocket.send_handlers import send_ack_handler, send_heartbeat_handler


# =========================================================
#
# =========================================================
def handle_ack(mySocket, data, on_routing_update=None):
    mySocket.ack_store.add_ack(int.from_bytes(data[1: 5], "big"))
# =========================================================
#
# =========================================================
def handle_no_ack(mySocket, data, on_routing_update=None):
    msg, succ = byteDecoder.decodePayload(data)
    if not succ:
        print("Received NoAck with Wrong Checksum")
        return
    pld = msg.payload
    seq_num = pld.sequence_number
    chunks = pld.missing_chunks
    mySocket.noack_store.add_noack(seq_num, chunks)

# =========================================================
# Handling received HELLO
# =========================================================
def handle_hello(mySocket, data, on_routing_update):
    src_ip = int.from_bytes(data[9: 13], "big")
    src_port = int.from_bytes(data[15: 17], "big")

    # Füge Nachbarn zur Neighbor-Tabelle hinzu oder aktualisiere ihn
    mySocket.neighbor_table.update_neighbor(src_ip, src_port, mySocket)

    # Erstelle eine direkte Route zum Nachbarn (Distance = 1)
    mySocket.routing_table.update_route(
        dest_ip=src_ip,
        dest_port=src_port,
        next_hop_ip=src_ip,
        next_hop_port=src_port,
        distance=1
    )

    send_heartbeat_handler.send_heartbeat(mySocket, mySocket.get_seq_num(), src_ip, src_port, mySocket.my_ip_str, mySocket.my_port)

    # Triggere Routing Update an alle Nachbarn
    on_routing_update()
    print(f"[HELLO] Received from {src_ip}:{src_port}")

# =========================================================
# Handling received MSGs
# =========================================================

def handle_msg(mySocket, data, on_routing_update=None):
    msg, succ = byteDecoder.decodePayload(data)
    if not succ:
        print("Received Message with Wrong Checksum")
        return
    send_ack_handler.send_ack(mySocket, msg.header.sequence_number, msg.header.source_ip, msg.header.source_port, mySocket.my_ip_str, mySocket.my_port)
    print(f"\n[RECV from {msg.header.source_ip}:{msg.header.source_port}] \n"
          f"{msg.payload.text}\n")

    # NEU: Nachricht an GUI weitergeben
    if hasattr(mySocket, 'gui') and mySocket.gui:
        mySocket.gui.add_incoming_message(str(ipaddress.IPv4Address(msg.header.source_ip)), msg.header.source_port, msg.payload.text)
# Handling received GOODBYE
# =========================================================


def handle_goodbye(mySocket, data, on_routing_update):
    src_ip = int(ipaddress.IPv4Address(int.from_bytes(data[9: 13])))
    src_port = int(ipaddress.IPv4Address(int.from_bytes(data[15: 17])))
    mySocket.neighbor_table.kill_neighbor(src_ip, src_port)
    on_routing_update()
    print("handle_goodbye")

# =========================================================
#
# =========================================================


def handle_file_chunk(mySocket, data, on_routing_update=None):
    file_chunk, succ = byteDecoder.decodePayload(data)
    if not succ: return False
    chunk_id = file_chunk.header.chunk_id
    seq_num = file_chunk.header.sequence_number
    succ = mySocket.file_store.add_chunk(
        seq_num,
        file_chunk.header.source_ip,
        file_chunk.header.source_port,
        chunk_id,
        file_chunk.payload.data
    )


    mySocket.neighbor_table.update_neighbor(file_chunk.header.source_ip, file_chunk.header.source_port, mySocket)
    return succ

# =========================================================
#
# =========================================================


def handle_file_info(mySocket, data, on_routing_update=None):
    file_info, succ = byteDecoder.decodePayload(data)
    if not succ: return False
    succ = mySocket.file_store.register_file_info(
        file_info.header.sequence_number,
        file_info.header.source_ip,
        file_info.header.source_port,
        file_info.payload.filename,
        file_info.header.chunk_length
    )
    # Download-Fenster erstellen
    if hasattr(mySocket, 'gui') and mySocket.gui:
        src_ip = str(ipaddress.IPv4Address(file_info.header.source_ip))
        src_port = file_info.header.source_port

        download_window = mySocket.gui.create_download_window(
            src_ip, src_port, file_info.payload.filename, file_info.header.chunk_length
        )

        if not hasattr(mySocket.file_store, 'download_windows'):
            mySocket.file_store.download_windows = {}

        mySocket.file_store.download_windows[file_info.header.sequence_number] = download_window

    print(f"[RECV] File Info {file_info.header.sequence_number} with total of {file_info.header.chunk_length} chunks")
    return succ

# =========================================================
# Handling received HEARTBEAT
# =========================================================


def handle_heartbeat(mySocket, data, on_routing_update=None):
    src_ip = int.from_bytes(data[9: 13], "big")
    src_port = int.from_bytes(data[15: 17], "big")
    mySocket.neighbor_table.update_neighbor(src_ip, src_port, mySocket)
    #print(f"[HEARTBEAT] Received from {src_ip}:{src_port}")

# =========================================================
# Handling received ROUTING_UPDATE
# =========================================================


def handle_routing_update(mySocket, data, on_routing_update):
    routing_update, succ = byteDecoder.decodePayload(data)
    if not succ: return False
    print(routing_update.payload)
    next_hop_ip = routing_update.header.source_ip
    next_hop_port = routing_update.header.source_port
    entries = routing_update.payload.entries
    changed = False
    for entry in entries:
        #if entry.dest_ip == int(ipaddress.IPv4Address(mySocket.my_ip_str)) and entry.dest_port == mySocket.my_port:
        #    continue
        if mySocket.routing_table.update_route(
                dest_ip=entry.dest_ip,
                dest_port=entry.dest_port,
                next_hop_ip=next_hop_ip,
                next_hop_port=next_hop_port,
                distance=entry.distance + 1
        ):
            changed = True

    if changed: on_routing_update()

    return True