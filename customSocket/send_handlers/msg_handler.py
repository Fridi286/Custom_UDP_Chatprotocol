import ipaddress

from customSocket import byteEncoder
from customSocket.helpers.models import Header, MsgMessage, MsgPayload


def send_Text(
        mySocket,
        seq_num,
        msg,
        dest_ip,
        dest_port,
        src_ip,
        src_port
):
    # prepare payload bytes and checksum so Header validation succeeds
    payload_bytes = msg.encode('utf-8')
    payload_length = len(payload_bytes)
    checksum = bytes(32) # Placeholder
    ttl = 64

    header = Header(
        type=5,
        sequence_number=seq_num,
        destination_ip=int(ipaddress.IPv4Address(dest_ip)),
        source_ip=int(ipaddress.IPv4Address(src_ip)),
        destination_port=dest_port,
        source_port=src_port,
        payload_length=payload_length,
        chunk_id=0,
        chunk_length=0,
        ttl=ttl,
        checksum=checksum,
    )
    data = MsgMessage(
        header=header,
        payload=MsgPayload(
            text=msg
        )
    )

    mySocket.send_queue.put((byteEncoder.encodePayload(data), (dest_ip, dest_port)))
    print(f"\n[SENT to {dest_ip}:{dest_port}] {msg}")
    return