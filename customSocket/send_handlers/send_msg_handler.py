import ipaddress
import time

from customSocket import byteEncoder, config
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

    encoded_data = (byteEncoder.encodePayload(data))

    for _ in range(config.MAX_RETRIES):
        if mySocket.ack_store.check_and_delete_ack(seq_num):
            print(f"\n[SENT to {dest_ip}:{dest_port}] {msg}\n")
            return True

        mySocket.send_queue.put((encoded_data, (dest_ip, dest_port)))

        last_event_time = time.time()
        while True:

            # --------------- ACK angekommen? ---------------
            if mySocket.ack_store.check_and_delete_ack(seq_num):
                print(f"\n[Succ SENT to {dest_ip}:{dest_port}] {msg}\n")
                return True
            # --------------- NoAck angekommen? --------------
            missing = mySocket.noack_store.get_and_delete_missing(seq_num)
            if missing:
                mySocket.send_queue.put((encoded_data, (dest_ip, dest_port)))
                last_event_time = time.time()  # Timer reset
                continue
            # --------------- Timeout prüfen ------------------------
            if time.time() - last_event_time >= config.WAIT_FOR_ACK_TIME:
                break

            time.sleep(0.01)

    return False