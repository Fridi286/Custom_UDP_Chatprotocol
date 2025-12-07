from typing import List

from annotated_types.test_cases import cases

from customSocket.models import Header, AckMessage, HelloMessage, GoodbyeMessage, HeartbeatMessage, NoAckMessage, \
    NoAckPayload


def parseHeader(h) -> Header:
    type = h[0: 1]
    seqNumber = h[1: 5]
    destIP = h [5: 9]
    srcIP = h [9: 13]
    destPort = h [13: 15]
    srcPort = h [15: 17]
    payloadLength = h [17: 21]
    chunkID = h [21: 25]
    chunkLength = h [25: 29]
    ttl = h [29:30]
    checksum = h [30: 62]

    header = Header(
        type= int.from_bytes(type, "big"),
        sequence_number= int.from_bytes(seqNumber, "big"),

        destination_ip= int.from_bytes(destIP, "big"),
        source_ip= int.from_bytes(srcIP, "big"),

        destination_port= int.from_bytes(destPort, "big"),
        source_port= int.from_bytes(srcPort, "big"),

        payload_length= int.from_bytes(payloadLength, "big"),

        chunk_id= int.from_bytes(chunkID, "big"),
        chunk_length= int.from_bytes(chunkLength, "big"),

        ttl= int.from_bytes(ttl, "big"),

        checksum=checksum,
    )

    return header

def parseNoAck(payload) -> NoAckPayload:

    seqNumber = int.from_bytes(payload [0 : 4], "big")
    missingCountInt = int.from_bytes(payload [4 : 6], "big")
    missingChunks = []

    for i in range(missingCountInt):
        byte_index = 6 + i*4
        missingChunks.append(
            int.from_bytes(payload [byte_index : byte_index+4], "big")
        )

    return NoAckPayload(
        sequence_number=seqNumber,
        missing_chunks=missingChunks
    )


def parseMsg():
    return #TODO
def parseFileChunk():
    return #TODO
def parseFileInfo():
    return #TODO
def parseRoutingUpdate():
    return #TODO

def parsePayload(udpPayload):
    header = parseHeader(udpPayload[0: 61])

    payload = udpPayload [61 : 61 + header.payload_length]


    match header.type:
        case 1:
            return AckMessage(
                header=header
            )

        case 2:
            return NoAckMessage(
                header=header,
                payload=parseNoAck(payload)
            )

        case 3:
            return HelloMessage(
                header=header
            )

        case 4:
            return GoodbyeMessage(
                header=header
            )
        case 5:
            return parseMsg()

        case 6:
            return parseFileChunk()

        case 7:
            return parseFileInfo()

        case 8:
            return HeartbeatMessage(
                header=header
            )

        case 9:
            return parseRoutingUpdate()

    raise ValueError("Unknown message type")

