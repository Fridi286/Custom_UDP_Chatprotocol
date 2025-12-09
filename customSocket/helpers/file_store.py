import time
import threading
from pathlib import Path
from threading import Lock

from customSocket import config


class FileStore:

    def __init__(self, on_frame_complete=None, on_frame_timeout=None):
        """
        on_frame_complete(file_key, frame_id)  ruft mySocket ACK-Funktion
        on_frame_timeout(file_key, frame_id, missing_chunks)  ruft mySocket NO_ACK-Funktion
        """

        self.files = {}
        self.lock = Lock()

        # Callbacks
        self.on_frame_complete = on_frame_complete
        self.on_frame_timeout = on_frame_timeout

        # Frame settings
        self.frame_size = config.FRAME_SIZE
        self.frame_wait_time = config.FRAME_WAIT_TIME

    # ============================================================
    # FILE INFO
    # ============================================================
    def register_file_info(self, seq_num, src_ip, src_port, filename, total_chunks):

        key = (seq_num, src_ip, src_port)

        with self.lock:
            if key in self.files:
                return False

            total_frames = (total_chunks + self.frame_size - 1) // self.frame_size

            self.files[key] = {
                "filename": filename,
                "total_chunks": total_chunks,
                "total_frames": total_frames,
                "received": {},     # chunk_id → bytes
                "frames": {},       # frame_id → {"received": set(), "timer": None}
                "created_at": time.time(),
                "last_update": time.time(),
            }

        threading.Thread(
            target=self.on_frame_complete,
            args=(key),
            daemon=True
        ).start()

        return True

    # ============================================================
    # ADD CHUNK (MIT FRAME LOGIK)
    # ============================================================
    def add_chunk(self, seq_num, src_ip, src_port, chunk_id, data):

        key = (seq_num, src_ip, src_port)

        with self.lock:
            if key not in self.files:
                return False

            file = self.files[key]

            # Duplicate?
            if chunk_id in file["received"]:
                return False

            # Store chunk bytes
            file["received"][chunk_id] = data
            file["last_update"] = time.time()

            # Frame bestimmen
            frame_id = chunk_id // self.frame_size

            # Falls Frame noch nicht existiert → anlegen
            if frame_id not in file["frames"]:
                file["frames"][frame_id] = {
                    "received": set(),
                    "timer": None,
                }

            frame = file["frames"][frame_id]
            frame["received"].add(chunk_id)

            # Frame Grenzen bestimmen
            frame_start = frame_id * self.frame_size
            frame_end = min(frame_start + self.frame_size, file["total_chunks"])
            expected_chunks = frame_end - frame_start

            # Prüfen: Frame vollständig? - sofort ACK
            if len(frame["received"]) == expected_chunks:
                # Falls Timer läuft - abbrechen
                if frame["timer"]:
                    frame["timer"].cancel()
                    frame["timer"] = None

                if self.on_frame_complete:
                    # Callback on_frame_complete
                    threading.Thread(
                        target=self.on_frame_complete,
                        args=key,
                        daemon=True
                    ).start()

            else:
                # Frame unvollständig - Timer starten
                if not frame["timer"]:
                    frame["timer"] = threading.Timer(
                        self.frame_wait_time,
                        self._frame_timeout,
                        args=(key, frame_id)
                    )
                    frame["timer"].start()

        return True

    # ============================================================
    # INTERNAL: FRAME TIMEOUT - NO_ACK
    # ============================================================
    def _frame_timeout(self, file_key, frame_id):

        with self.lock:
            file = self.files.get(file_key)
            if not file:
                return

            frame = file["frames"].get(frame_id)
            if not frame:
                return

            # Frame-Größe berechnen
            frame_start = frame_id * self.frame_size
            frame_end = min(frame_start + self.frame_size, file["total_chunks"])
            expected = set(range(frame_start, frame_end))

            missing = list(expected - frame["received"])

            # Kein Timer mehr
            frame["timer"] = None

        # NO_ACK Callback aufrufen
        if self.on_frame_timeout:
            threading.Thread(
                target=self.on_frame_timeout,
                args=(file_key, missing),
                daemon=True
            ).start()

    # ============================================================
    # FILE COMPLETION
    # ============================================================
    def is_complete(self, seq_num, src_ip, src_port):
        key = (seq_num, src_ip, src_port)

        with self.lock:
            if key not in self.files:
                return False

            file = self.files[key]
            return len(file["received"]) == file["total_chunks"]

    def assemble_file(self, seq_num, src_ip, src_port, output_folder="received_files"):

        key = (seq_num, src_ip, src_port)

        with self.lock:
            if key not in self.files:
                return None

            file = self.files[key]

            if len(file["received"]) != file["total_chunks"]:
                return None

            # Output-Pfad vorbereiten
            Path(output_folder).mkdir(parents=True, exist_ok=True)
            output_path = Path(output_folder) / file["filename"]

            # Chunks sortiert zusammenbauen
            chunks = [file["received"][i] for i in range(file["total_chunks"])]
            data = b"".join(chunks)

        with open(output_path, "wb") as f:
            f.write(data)

        return str(output_path)

    def remove_file(self, seq_num, src_ip, src_port):
        key = (seq_num, src_ip, src_port)

        with self.lock:
            if key in self.files:
                del self.files[key]
                return True

        return False