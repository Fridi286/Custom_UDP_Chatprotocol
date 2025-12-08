import threading


class AckStore:

    def __init__(self):
        self._lock = threading.Lock()
        self._acks: set[int] = set()

    def add_ack(self, seq_num: int):
        with self._lock:
            self._acks.add(seq_num)

    def has_ack(self, seq_num: int) -> bool:
        with self._lock:
            return seq_num in self._acks

    def remove_ack(self, seq_num: int):
        with self._lock:
            self._acks.discard(seq_num)

    def get_all(self) -> set[int]:
        with self._lock:
            return set(self._acks)