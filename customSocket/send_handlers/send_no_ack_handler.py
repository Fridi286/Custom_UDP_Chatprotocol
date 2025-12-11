import ipaddress

from customSocket import config, byteEncoder
from customSocket.helpers.models import Header, NoAckMessage, NoAckPayload


def send_no_ack(
        mySocket,
        seq_num,
        dest_ip,
        dest_port,
        src_ip,
        src_port,
        missing
):
    data = NoAckMessage(
        header=Header(
            type=2,
            sequence_number=seq_num,
            destination_ip=int(ipaddress.IPv4Address(dest_ip)),
            source_ip=int(ipaddress.IPv4Address(src_ip)),
            destination_port=dest_port,
            source_port=src_port,
            payload_length=0,
            chunk_id=0,
            chunk_length=0,
            ttl=config.TTL_DEFAULT,
            checksum=bytes(32),
        ),
        payload=NoAckPayload(
            sequence_number=seq_num,
            missing_chunks=missing
        )
    )
    encoded_data = byteEncoder.encodePayload(data)
    mySocket.send_queue.put((encoded_data, (str(ipaddress.IPv4Address(dest_ip)), dest_port)))
    print(f"Sent NoACK for {seq_num}")
    return