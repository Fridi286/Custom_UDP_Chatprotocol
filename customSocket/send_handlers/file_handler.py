import ipaddress
import math
import os
import time
from typing import List

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
        src_port
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

    # ==========Important Variables==========================
    ttl = config.TTL_DEFAULT
    CHUNK_SIZE = config.CHUNK_SIZE
    FRAME_SIZE = config.FRAME_SIZE
    # =======================================================

    # Calculate Num of Chunks
    chunk_length = math.ceil(size / CHUNK_SIZE)

    # =======================================================
    # Sending File_Info, waiting for before data transfer
    # =======================================================

    if not send_check_file_info(mySocket, seq_num, dest_ip, src_ip, dest_port, src_port, chunk_length, ttl, filename):
        return False

    # =======================================================
    # Iteratign through all bytes of data creating frames and sending
    # =======================================================

    with open(path, "rb") as f:
        frame: list[AnyMessage] = []
        # ---------- DATA CHUNKS ----------
        for chunk_id in range(0, chunk_length):

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
            if len(frame) == FRAME_SIZE + 1:
                if not send_frame(mySocket, frame, seq_num):
                    return False
                frame = []

        # Send Rest Frame
        if frame:
            if not send_frame(mySocket, frame, seq_num):
                return False

    print("transfer finished")

    return True

# ======================================Down here are "private methods"=================================================


# ======================================================================================================================
# Sending File_Info, waiting for before data transfer
# ======================================================================================================================

def send_check_file_info(mySocket, seq_num, dest_ip, src_ip, dest_port, src_port, chunk_length, ttl, filename) -> bool:

    file_info = FileInfoMessage(
        header=Header(
            type=7,
            sequence_number=seq_num,
            destination_ip=int(ipaddress.IPv4Address(dest_ip)),
            source_ip=int(ipaddress.IPv4Address(src_ip)),
            destination_port=dest_port,
            source_port=src_port,
            payload_length=0,  # gets calculated in encoder
            chunk_id=0,  # FileInfo gets chunk_id = 0
            chunk_length=chunk_length,
            ttl=ttl,
            checksum=bytes(32),  # gets calculated in encoder
        ),
        payload=FileInfoPayload(
            filename=filename
        )
    )

    for _ in range(config.MAX_RETRIES):
        if mySocket.ack_store.check_and_delete_ack(seq_num):
            print(f"\n[FILE_INFO WAS SENT TO: {dest_ip}:{dest_port}]\n")
            return True

        mySocket.send_queue.put((byteEncoder.encodePayload(file_info), (dest_ip, dest_port)))

        last_event_time = time.time()
        while True:

            # --------------- ACK angekommen? ---------------
            if mySocket.ack_store.check_and_delete_ack(seq_num):
                print(f"\n[FILE_INFO WAS SENT TO: {dest_ip}:{dest_port}]\n")
                return True
            # --------------- NoAck angekommen? --------------
            missing = mySocket.noack_store.get_and_delete_missing(seq_num)
            if missing:
                mySocket.send_queue.put((byteEncoder.encodePayload(file_info), (dest_ip, dest_port)))
                last_event_time = time.time()  # Timer reset
                continue
            # --------------- Timeout prüfen ------------------------
            if time.time() - last_event_time >= config.WAIT_FOR_ACK_TIME:
                break

            time.sleep(0.01)

    print(f"\n[FILE_INFO COULD NOT BE SENT TO: {dest_ip}:{dest_port}]\n")

    return False

# ====================================================================================================
# This Method handels the sending / resending / Ack and No_Ack Handling of one Frame
# ====================================================================================================

def send_frame(mySocket, frame, seq_num) -> bool:
    for _ in range(config.MAX_RETRIES):
        # 1. ACK schon da?
        if mySocket.ack_store.check_and_delete_ack(seq_num):
            return True

        # 2. Erstmal alle Chunks senden
        send_all_chunks(mySocket, frame)

        # 3. Reset des Timers
        last_event_time = time.time()
        while True:

            # --------------- ACK angekommen? ---------------
            if mySocket.ack_store.check_and_delete_ack(seq_num):
                return True
            # --------------- NoAck angekommen? --------------
            missing = mySocket.noack_store.get_and_delete_missing(seq_num)
            if missing:
                send_missing_chunks(mySocket, frame, missing)
                last_event_time = time.time()  # Timer reset
                continue
            # --------------- Timeout prüfen ------------------------
            if time.time() - last_event_time >= 5:
                break

            time.sleep(0.01)
    # reached max retries return False transfer failed
    return False

# ------------- Helpers for send_frame -------------

def send_all_chunks(mySocket, frame):
    for chunk in frame:
        dest_ip_str = str(ipaddress.IPv4Address(chunk.header.destination_ip))
        #print(f"Sent: {chunk.header.chunk_id}")
        mySocket.send_queue.put((byteEncoder.encodePayload(chunk), (dest_ip_str, chunk.header.destination_port)))


def send_missing_chunks(mySocket, frame, missing):
    for missing_chunk in missing:
        for chunk in frame:
            if chunk.header.chunk_id == missing_chunk:
                #print(f"Re-Sent: {chunk.header.chunk_id}")
                dest_ip_str = str(ipaddress.IPv4Address(chunk.header.destination_ip))
                mySocket.send_queue.put((byteEncoder.encodePayload(chunk), (dest_ip_str, chunk.header.destination_port)))


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