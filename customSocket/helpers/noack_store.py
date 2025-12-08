import threading
from typing import List, Dict


class NoAckStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._noacks: Dict[int, List[int]] = {}

    def add_noack(self, seq_num: int, missing_chunks: List[int]):
        with self._lock:
            self._noacks[seq_num] = missing_chunks

    def get_missing(self, seq_num: int) -> List[int] | None:
        with self._lock:
            return self._noacks.get(seq_num)

    def remove_noack(self, seq_num: int):
        with self._lock:
            self._noacks.pop(seq_num, None)

    def get_all(self) -> dict[int, list[int]]:
        with self._lock:
            return dict(self._noacks)