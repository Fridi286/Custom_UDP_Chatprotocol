import ipaddress

from customSocket import config, byteEncoder
from customSocket.helpers.models import AckMessage, Header, HelloMessage, GoodbyeMessage


def send_goodbye(
        mySocket,
        seq_num,
        dest_ip,
        dest_port,
        src_ip,
        src_port
):
    data = GoodbyeMessage(
        header=Header(
            type=4,
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
        )
    )
    encoded_data = byteEncoder.encodePayload(data)
    mySocket.sock.sendto(encoded_data, (str(ipaddress.IPv4Address(dest_ip)), dest_port))
    print(f"Sent Goodbye to {dest_ip}:{dest_port}")
    return