import os
import queue
import time
import threading
from pathlib import Path
from threading import Lock

from customSocket import config


class FileStore:

    def __init__(self, on_frame_complete, on_frame_timeout):
        """
        on_frame_complete(file_key)  ruft mySocket ACK-Funktion
        on_frame_timeout(file_key, missing_chunks)  ruft mySocket NO_ACK-Funktion
        """

        self.ack_queue = queue.SimpleQueue()
        self.noack_queue = queue.SimpleQueue()
        self.file_complete_queue = queue.SimpleQueue()

        self.files = {}
        self.lock = Lock()

        # Callbacks
        self.on_frame_complete = on_frame_complete
        self.on_frame_timeout = on_frame_timeout

        # Frame settings
        self.frame_size = config.FRAME_SIZE
        self.frame_wait_time = config.FRAME_WAIT_TIME

        threading.Thread(
            target=self.frame_timeout_watcher,
            daemon=True
        ).start()

        threading.Thread(
            target=self.ack_worker,
            daemon=True
        ).start()

        threading.Thread(
            target=self.noack_worker,
            daemon=True
        ).start()

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
                "created_at": time.monotonic(),
                "last_update": time.monotonic(),
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
        start = time.perf_counter()
        key = (seq_num, src_ip, src_port)

        frame_completed = False
        file_completed = False
        frame_id = chunk_id // self.frame_size

        with self.lock:
            file = self.files.get(key)
            if not file:
                return False

            if chunk_id in file["received"]:
                return False

            # Chunk speichern
            file["received"][chunk_id] = data
            file["last_update"] = time.monotonic()

            # Frame initialisieren
            frame = file["frames"].get(frame_id)
            if not frame:
                frame_start = frame_id * self.frame_size
                frame_end = min(frame_start + self.frame_size, file["total_chunks"])

                frame = {
                    "received_count": 0,
                    "expected": frame_end - frame_start,
                    "last_update": time.monotonic(),
                    "completed": False
                }
                file["frames"][frame_id] = frame

            # Frame updaten
            frame["received_count"] += 1
            frame["last_update"] = time.monotonic()

            if not frame["completed"] and frame["received_count"] == frame["expected"]:
                frame["completed"] = True
                frame_completed = True

            if len(file["received"]) == file["total_chunks"]:
                file_completed = True

        # Callbacks außerhalb des Locks
        if frame_completed:
            self.ack_queue.put(key)

        if file_completed:
            self.assemble_file(key)

        if chunk_id % 50 == 0:
            print(f"add_chunk: {time.perf_counter() - start:.6f}s")

        return True

    # ============================================================
    # frame_timeout_watcher
    # ============================================================

    def frame_timeout_watcher(self):
        while True:
            now = time.monotonic()
            expired = []

            with self.lock:
                for key, file in self.files.items():
                    for frame_id, frame in file["frames"].items():
                        if frame["completed"]:
                            continue
                        if now - frame["last_update"] >= self.frame_wait_time:
                            expired.append((key, frame_id))
                            frame["last_update"] = now

            for key, frame_id in expired:
                self.noack_queue.put((key, frame_id))

            time.sleep(0.01)

    # ============================================================
    # ack and no ack workers
    # ============================================================

    def ack_worker(self):
        while True:
            key = self.ack_queue.get()
            seq_num, src_ip, src_port = key
            self.on_frame_complete(seq_num, src_ip, src_port)

    def noack_worker(self):
        while True:
            key, frame_id = self.noack_queue.get()

            with self.lock:
                file = self.files.get(key)
                if not file:
                    continue

                frame = file["frames"].get(frame_id)
                if not frame:
                    continue

                frame_start = frame_id * self.frame_size
                frame_end = min(frame_start + self.frame_size, file["total_chunks"])

                received_count = frame["received_count"]
                expected_ids = range(frame_start, frame_end)

                missing = [
                    i for i in expected_ids
                    if i not in file["received"]
                ]

            self.on_frame_timeout(key, missing)


    # ============================================================
    # FILE COMPLETION
    # ============================================================
    def is_complete(self, seq_num, src_ip, src_port):
        key = (seq_num, src_ip, src_port)
        with self.lock:
            if key not in self.files:
                return False

            file = self.files[key]
            print(len(file["received"]), file["total_chunks"])
            return len(file["received"]) == file["total_chunks"]

    def assemble_file(self, key, output_folder="/Users/fridi/PycharmProjects/CustomNetworkRN/received_data/"):
        print(f"[INFO] Called assemble_file")

        if not os.path.exists(output_folder):
            print("Pfad existiert nicht!")
            return
        elif not os.path.isdir(output_folder):
            print("Pfad ist kein Ordner")
            return

        if key not in self.files:
            return None

        file = self.files[key]

        if len(file["received"]) != file["total_chunks"]:
            print(f"[ERROR] Can not assemble | Received {len(file["received"])} chunks , expected {file["total_chunks"]} chunks")
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


    def cleanup_stale_files(self):
        #TODO
        """
        Scannt periodisch den FileStore nach veralteten Dateien.
        Sollte in einem separaten Thread ausgeführt werden.
        """
        import time

        while True:
            time.sleep(15)  # Alle 3 Sekunden scannen

            current_time = time.time()
            stale_timeout = 60  # 5 Sekunden

            with self.lock:
                keys_to_process = []

                for key, file in self.files.items():
                    print(f"Current: {current_time} and last_update: {file["last_update"]}")
                    if current_time - file["last_update"] >= stale_timeout:
                        keys_to_process.append(key)

            # Verarbeitung außerhalb des Locks
            for key in keys_to_process:
                seq_num, src_ip, src_port = key

                if self.is_complete(seq_num, src_ip, src_port):
                    # File vollständig → assemblieren
                    output_path = self.assemble_file(seq_num, src_ip, src_port)
                    if output_path:
                        print(f"Stale file assembled: {output_path}")
                    self.remove_file(seq_num, src_ip, src_port)
                else:
                    # File unvollständig → löschen
                    self.remove_file(seq_num, src_ip, src_port)
                    print(f"Stale incomplete file removed: {key}")
