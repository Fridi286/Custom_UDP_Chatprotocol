from enum import IntEnum
from pydantic import BaseModel, Field
from typing import Optional, List, Union



# ENUM:Message Types

class MessageType(IntEnum):
    ACK = 1
    NO_ACK = 2
    HELLO = 3
    GOODBYE = 4
    MSG = 5
    FILE_CHUNK = 6
    FILE_INFO = 7
    HEARTBEAT = 8
    ROUTING_UPDATE = 9


# HEADER MODEL

class Header(BaseModel):
    type: int

    sequence_number: int = Field(ge=0, le=2**32 - 1)

    destination_ip: int = Field(ge=0, le=2**32 - 1)
    source_ip: int = Field(ge=0, le=2**32 - 1)

    destination_port: int = Field(ge=0, le=65535)
    source_port: int = Field(ge=0, le=65535)

    payload_length: int = Field(ge=0, le=2**32 - 1)

    chunk_id: int = Field(ge=0, le=2**32 - 1)
    chunk_length: int = Field(ge=0, le=2**32 - 1)

    ttl: int = Field(ge=0, le=255)

    checksum: bytes = Field(min_length=32, max_length=32)


# BASE MESSAGE (Header + Payload)

class BaseMessage(BaseModel):
    header: Header


# PAYLOAD MODELS (pro Nachrichtentyp)

# --- Typ 0x01 ACK ---
class AckPayload(BaseModel):
    """kein Payload -> leeres Modell"""
    pass


# --- Typ 0x02 NO_ACK ---
class NoAckPayload(BaseModel):
    # 0–3: Sequence Number des betroffenen Pakets
    sequence_number: int = Field(ge=0, le=2**32 - 1)

    # Liste der fehlenden Chunk-IDs
    # 4–5: len(missing)  (uint16)
    # ab 6: pro Eintrag 4 Byte
    missing_chunks: List[int] = Field(max_length=256)


# --- Typ 0x03 HELLO ---
class HelloPayload(BaseModel):
    pass


# --- Typ 0x04 GOODBYE ---
class GoodbyePayload(BaseModel):
    pass


# --- Typ 0x05 MSG ---
class MsgPayload(BaseModel):
    text: str  # UTF-8 string


# --- Typ 0x06 FILE_CHUNK ---
class FileChunkPayload(BaseModel):
    data: bytes  # Chunk-Rohdaten


# --- Typ 0x07 FILE_INFO ---
class FileInfoPayload(BaseModel):
    filename: str   # UTF-8 string


# --- Typ 0x08 HEARTBEAT ---
class HeartbeatPayload(BaseModel):
    pass


# --- Typ 0x09 ROUTING_UPDATE ---
class RoutingUpdateEntry(BaseModel):
    dest_ip: int
    dest_port: int
    distance: int

class RoutingUpdatePayload(BaseModel):
    entries: List[RoutingUpdateEntry]


# ======================================================
# MESSAGE MODELS pro Typ (Header + jeweiliger Payload)
# ======================================================

class AckMessage(BaseMessage):
    payload: AckPayload = AckPayload()


class NoAckMessage(BaseMessage):
    payload: NoAckPayload


class HelloMessage(BaseMessage):
    payload: HelloPayload = HelloPayload()


class GoodbyeMessage(BaseMessage):
    payload: GoodbyePayload = GoodbyePayload()


class MsgMessage(BaseMessage):
    payload: MsgPayload


class FileChunkMessage(BaseMessage):
    payload: FileChunkPayload


class FileInfoMessage(BaseMessage):
    payload: FileInfoPayload


class HeartbeatMessage(BaseMessage):
    payload: HeartbeatPayload = HeartbeatPayload()


class RoutingUpdateMessage(BaseMessage):
    payload: RoutingUpdatePayload


AnyMessage = Union[
    AckMessage,
    NoAckMessage,
    HelloMessage,
    GoodbyeMessage,
    MsgMessage,
    FileChunkMessage,
    FileInfoMessage,
    HeartbeatMessage,
    RoutingUpdateMessage,
]
