import hashlib

from customSocket.helpers.models import AnyMessage, Header, NoAckPayload, MsgPayload, FileChunkPayload, FileInfoPayload, \
    RoutingUpdatePayload

# ============================ Helpers ==========================================

def encodeNoAck(payload: NoAckPayload) -> bytes:
    sequenceNumber = payload.sequence_number.to_bytes(4, "big")
    missingCount = len(payload.missing_chunks).to_bytes(2, "big")
    missingChunks = bytes(0)
    # payload.missing_chunks is a list of ints
    for i in payload.missing_chunks:
        missingChunks += i.to_bytes(4, "big")

    return sequenceNumber + missingCount + missingChunks

def encodeMsg(payload: MsgPayload) -> bytes:
    return payload.text.encode("utf-8", errors="ignore")

def encodeFileChunk(payload: FileChunkPayload) -> bytes:
    return payload.data

def encodeFileInfo(payload: FileInfoPayload) -> bytes:
    return payload.filename.encode("utf-8", errors="ignore")

def encodeRoutingUpdate(payload: RoutingUpdatePayload) -> bytes:

    data = len(payload.entries).to_bytes(2, "big")

    for entry in payload.entries:
        data += entry.dest_ip.to_bytes(4, "big")
        data += entry.dest_port.to_bytes(2, "big")
        data += entry.distance.to_bytes(1, "big")

    return data


# =========================================================================


def encodeAll(header: Header, payload) -> bytes:

    type = header.type.to_bytes(1, "big")
    seqNumber = header.sequence_number.to_bytes(4, "big")
    destIP = header.destination_ip.to_bytes(4, "big")
    srcIP = header.source_ip.to_bytes(4, "big")
    destPort = header.destination_port.to_bytes(2, "big")
    srcPort = header.source_port.to_bytes(2, "big")

    payloadLength = len(payload).to_bytes(4, "big")

    chunkID = header.chunk_id.to_bytes(4, "big")
    chunkLength = header.chunk_length.to_bytes(4, "big")
    ttl = header.ttl.to_bytes(1, "big")

    checksum = hashlib.sha256(payload).digest()

    return type+seqNumber+destIP+srcIP+destPort+srcPort+payloadLength+chunkID+chunkLength+ttl+checksum+payload


# ======================================================================
# This is the Methode use do encode a Message
# ======================================================================

def encodePayload(message: AnyMessage) -> bytes:

    msgType = message.header.type
    payload = bytes(0)

    match msgType:
        case 2:
            payload = encodeNoAck(message.payload)
        case 5:
            payload = encodeMsg(message.payload)
        case 6:
            payload = encodeFileChunk(message.payload)
        case 7:
            payload = encodeFileInfo(message.payload)
        case 9:
            payload = encodeRoutingUpdate(message.payload)

    return encodeAll(message.header, payload)
