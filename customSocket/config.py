# config.py

CHUNK_SIZE = 1260
FRAME_SIZE = 128
TTL_DEFAULT = 64

MAX_RETRIES = 3                 # Wie oft wir bei keinem ACK oder NOACK eine Message neu senden
FRAME_WAIT_TIME = 1             # Beim reveiver Zeit die wir bei einem Frame warten auf ein ACK bis wir neu senden
WAIT_FOR_ACK_TIME = 20           # Zeit die wir bei MSG oder File_Info auf ein ACK warten

HEARTBEAT_TIMER = 3             # Wie oft wir heartbeats senden

MAX_BANDWIDTH_BYTES = 1_000_000   # 1 MByte pro Sekunde erlaubt
PACKET_SIZE_BYTES = 1500          # ungefähre Größe pro Paket

MAX_PPS = MAX_BANDWIDTH_BYTES // PACKET_SIZE_BYTES #ca


