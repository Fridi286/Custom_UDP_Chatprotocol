from customSocket import byteDecoder
from customSocket.helpers.models import NoAckMessage


def handle_ack(mySocket, data):
    mySocket.ack_store.add_ack(int.from_bytes(data[1: 5], "big"))

def handle_no_ack(mySocket, data):
    msg, succ = byteDecoder.decodePayload(data)
    if not succ:
        #TODO
        print("Wrong Checksum")
        return
    pld = msg.payload
    seq_num = pld.sequence_number
    chunks = pld.missing_chunks
    mySocket.noack_store.add_noack(seq_num, chunks)

def handle_hello(mySocket, data):
    #TODO
    print("handle_hello")

def handle_msg(mySocket, data):
    msg, succ = byteDecoder.decodePayload(data)
    if not succ:
        #TODO
        print("Wrong Checksum")
        return
    print(f"\n[RECV from {msg.header.source_ip}:{msg.header.source_port}] \n"
          f"{msg.payload.text}\n")
    #TODO send ACK
    print("handle_msg")

def handle_goodbye(mySocket, data):
    #TODO
    print("handle_goodbye")

def handle_file_chunk(mySocket, data):
    #TODO
    print("handle_file_chunk")

def handle_file_info(mySocket, data):
    #TODO
    print("handle_file_info")

def handle_heartbeat(mySocket, data):
    #TODO
    print("handle_heartbeat")

def handle_routing_update(mySocket, data):
    #TODO
    print("handle_routing_update")
