# Custom_UDP_Chatprotocol

This repository contains a custom peer-to-peer chat protocol implemented as part of a university networking assignment.  
The project is intended for educational purposes and demonstrates how a reliable communication protocol can be built on top of UDP.

The application supports text messaging and file transfer between peers and provides a simple graphical user interface based on Tkinter.

---

## Project Context

This project was developed in the context of a university course on computer networks.  
It follows a given protocol specification and focuses on implementing core networking concepts such as:

- Communication over UDP
- Reliability mechanisms on the application layer
- Chunk-based file transfer
- Peer-to-peer communication without a central server

---

## Features

- **Peer-to-peer messaging**  
  Text messages are exchanged directly between peers using a custom message format.

- **File transfer**  
  Files are split into fixed-size chunks and transmitted over UDP.  
  The receiver reassembles the file once all chunks have been received.

- **Reliability layer over UDP**  
  Since UDP is unreliable, the protocol implements its own reliability mechanisms, including:
  - Sequence numbers
  - ACK and NO_ACK messages
  - Retransmission of missing data
  - Duplicate detection

- **Routing and forwarding**  
  Peers can forward packets for other peers using a distance-vector-based routing approach.

- **Graphical user interface**  
  A basic Tkinter-based UI is provided for sending messages and files and for interacting with the protocol.

---

## Protocol Overview

The protocol is based on UDP over IPv4 and uses a custom binary header followed by a variable-length payload.

Key characteristics include:

- Fixed-size protocol header (62 bytes)
- Big-endian encoding for all fields
- SHA-256 checksum for payload integrity
- Support for multiple message types, including:
  - MSG
  - FILE_INFO
  - FILE_CHUNK
  - ACK / NO_ACK
  - HELLO / GOODBYE
  - HEARTBEAT
  - ROUTING_UPDATE

Details about packet structure, message types, routing behavior, and reliability mechanisms are defined in the accompanying protocol specification document :contentReference[oaicite:1]{index=1}.

---

## Limitations

- Best-effort implementation intended for learning purposes
- No encryption or authentication
- No congestion control
- Limited scalability

---

## Credits

This project was implemented entirely by me as part of a university assignment.
