import threading
from typing import Dict, List


class NoAckStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._noacks: Dict[int, List[int]] = {}  # seq_num -> missing_chunks

    def add_noack(self, seq_num: int, missing_chunks: List[int]):
        # Führt neue fehlende Chunks mit bestehenden zusammen
        with self._lock:
            if seq_num not in self._noacks:
                print("added new to noack list")
                self._noacks[seq_num] = missing_chunks.copy()
            else:
                print("added to noack list")
                # Zusammenführen ohne Duplikate
                existing = set(self._noacks[seq_num])
                for c in missing_chunks:
                    existing.add(c)
                self._noacks[seq_num] = sorted(existing)

    def get_and_delete_missing(self, seq_num: int) -> List[int] | None:
        #print("Got ask of no ack list")
        # Gibt die fehlenden Chunks für seq_num zurück und löscht den Eintrag danach.
        with self._lock:
            return self._noacks.pop(seq_num, None)

    def remove_noack(self, seq_num: int):
        # Entfernt die gespeicherten Missing-Chunks für eine Sequenznummer
        with self._lock:
            self._noacks.pop(seq_num, None)

    def get_all(self) -> Dict[int, List[int]]:
        # Gibt eine Kopie aller NoAck-Einträge zurück
        with self._lock:
            return dict(self._noacks)