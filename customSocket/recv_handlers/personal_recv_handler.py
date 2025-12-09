from customSocket import byteDecoder
from customSocket.helpers.models import NoAckMessage
from customSocket.send_handlers import ack_handler


# =========================================================
#
# =========================================================
def handle_ack(mySocket, data):
    mySocket.ack_store.add_ack(int.from_bytes(data[1: 5], "big"))
    print(f"\nRec Ack for Seq: {data[1: 5]}")

# =========================================================
#
# =========================================================
def handle_no_ack(mySocket, data):
    msg, succ = byteDecoder.decodePayload(data)
    if not succ:
        print("Received NoAck with Wrong Checksum")
        return
    pld = msg.payload
    seq_num = pld.sequence_number
    chunks = pld.missing_chunks
    mySocket.noack_store.add_noack(seq_num, chunks)
    print(f"\nRec NOACK for Seq: {seq_num}, missing chunk: {chunks}\n")

# =========================================================
#
# =========================================================
def handle_hello(mySocket, data):
    #TODO
    print("handle_hello")

# =========================================================
# Handling received MSGs
# =========================================================

def handle_msg(mySocket, data):
    msg, succ = byteDecoder.decodePayload(data)
    if not succ:
        print("Received Message with Wrong Checksum")
        return
    ack_handler.send_ack(mySocket, msg.header.sequence_number, msg.header.source_ip, msg.header.source_port, mySocket.my_ip, mySocket.my_port)
    print(f"\n[RECV from {msg.header.source_ip}:{msg.header.source_port}] \n"
          f"{msg.payload.text}\n")
# =========================================================
#
# =========================================================


def handle_goodbye(mySocket, data):
    #TODO
    print("handle_goodbye")

# =========================================================
#
# =========================================================


def handle_file_chunk(mySocket, data):
    file_chunk, succ = byteDecoder.decodePayload(data)
    if not succ: return False
    succ = mySocket.file_store.add_chunk(
        file_chunk.header.sequence_number,
        file_chunk.header.source_ip,
        file_chunk.header.source_port,
        file_chunk.header.chunk_id,
        file_chunk.payload.data
    )
    print(f"Got: {file_chunk.header.chunk_id}")
    print("handle_file_chunk")
    return succ

# =========================================================
#
# =========================================================


def handle_file_info(mySocket, data):
    file_info, succ = byteDecoder.decodePayload(data)
    if not succ: return False
    succ = mySocket.file_store.register_file_info(
        file_info.header.sequence_number,
        file_info.header.source_ip,
        file_info.header.source_port,
        file_info.payload.filename,
        file_info.header.chunk_length
    )
    print(f"Got File Info {file_info.header.sequence_number} with total of {file_info.header.chunk_length} chunks")
    print("handle_file_info")
    return succ

# =========================================================
#
# =========================================================


def handle_heartbeat(mySocket, data):
    #TODO
    print("handle_heartbeat")

# =========================================================
#
# =========================================================


def handle_routing_update(mySocket, data):
    #TODO
    print("handle_routing_update")
