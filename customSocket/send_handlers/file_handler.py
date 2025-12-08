import ipaddress
import math
import os
import time

from customSocket import byteEncoder, config
from customSocket.helpers.models import AnyMessage, FileInfoMessage, Header, FileInfoPayload, FileChunkMessage, FileChunkPayload


# ====================================================================================================
# send_Data ist the Method called by the socket
# ====================================================================================================
def send_Data(
        mySocket,
        seq_num,
        msg,
        dest_ip,
        dest_port,
        src_ip,
        src_port,
        send_queue
):
    path = input("Gib den Dateipfad der zu verschickenden Datei an: ")
    if not os.path.exists(path):
        print("Pfad existiert nicht!")
        return
    elif not os.path.isfile(path):
        print("Es ist keine Datei!")
        return
    elif not os.access(path, os.R_OK):
        print("Keine Leserechte!")
        return
    else:
        print("Pfad ist gültig und lesbar.")

    # Here starts the real magic

    filename = os.path.basename(path)

    size = os.path.getsize(path)

    # ==========Important Variables=============
    ttl = config.TTL_DEFAULT
    CHUNK_SIZE = config.CHUNK_SIZE
    FRAME_SIZE = config.FRAME_SIZE
    # ==========================================

    # Calculate Num of Chunks
    chunk_length = math.ceil(size / CHUNK_SIZE) + 1


    with open(path, "rb") as f:
        frame: list[AnyMessage] = []
        frame.append(
            FileInfoMessage(
                header=Header(
                    type=7,
                    sequence_number=seq_num,
                    destination_ip=int(ipaddress.IPv4Address(dest_ip)),
                    source_ip=int(ipaddress.IPv4Address(src_ip)),
                    destination_port=dest_port,
                    source_port=src_port,
                    payload_length=0,           #gets calculated in encoder
                    chunk_id=0,                 #FileInfo gets chunk_id = 0
                    chunk_length=chunk_length,
                    ttl=ttl,
                    checksum=bytes(32),          #gets calculated in encoder
                ),
                payload=FileInfoPayload(
                    filename=filename
                )
            )
        )
        # ---------- DATA CHUNKS ----------
        for chunk_id in range(1, chunk_length):

            succ = False

            chunk_bytes = f.read(CHUNK_SIZE)

            frame.append(
                createFileChunk(
                    chunk_bytes,
                    seq_num,
                    dest_ip, src_ip,
                    dest_port, src_port,
                    chunk_id,
                    chunk_length,
                    ttl
                )
            )

            # Send Full Frame
            if len(frame) == FRAME_SIZE:
                succ = send_frame(mySocket, frame, seq_num)
                frame = []

        # Send Rest Frame
        if frame:
            succ = send_frame(mySocket, seq_num)

    print(path)



# ====================================================================================================
# This Method handels the sending / resending / Ack and No_Ack Handling of one Frame
# ====================================================================================================


def send_frame(mySocket, frame, seq_num) -> bool:
    tries = 0
    delivered = False

    while not delivered:
        send_all_chunks(mySocket, frame)
        time.sleep(config.FRAME_WAIT_TIME)
        delivered = check_ACK(mySocket, seq_num)


    return True

# ------------- Helpers for send_frame -------------

def send_all_chunks(mySocket, frame):
    for chunk in frame:
        mySocket.send_queue.put((byteEncoder.encodePayload(chunk), (chunk.header.destination_ip, chunk.header.destination_port)))

def check_ACK(mySocket, seq_num):
    if mySocket.ack_store.has_ack(seq_num):
        return True
    return False




# ====================================================================================================
# Helpers Methods
# ====================================================================================================

def createFileChunk(payload, seq_num, dest_ip, src_ip, dest_port, src_port, chunk_id, chunk_length, ttl) -> FileChunkMessage:
    return FileChunkMessage(
        header=Header(
            type=6,
            sequence_number=seq_num,
            destination_ip=int(ipaddress.IPv4Address(dest_ip)),
            source_ip=int(ipaddress.IPv4Address(src_ip)),
            destination_port=dest_port,
            source_port=src_port,
            payload_length=0,  # gets calculated in encoder
            chunk_id=chunk_id,  # FileInfo gets chunk_id = 0
            chunk_length=chunk_length,
            ttl=ttl,
            checksum=bytes(32),  # gets calculated in encoder
        ),
        payload=FileChunkPayload(
            data=payload
        )
    )