import os
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
        print(f"[RECV] Chunk - SEQ_NUM: {seq_num} - CHUNKID: {chunk_id}")
        key = (seq_num, src_ip, src_port)

        with self.lock:
            file = self.files.get(key)
            if not file:
                print(f"[ERROR] No existing File for: Chunk - SEQ_NUM: {seq_num} - CHUNKID: {chunk_id}")
                return False

            # Duplikat?
            if chunk_id in file["received"]:
                print(f"[INFO] Already received - Skipping: Chunk - SEQ_NUM: {seq_num} - CHUNKID: {chunk_id}")
                return False

            # Chunk speichern
            file["received"][chunk_id] = data
            file["last_update"] = time.time()
            print(f"[INFO] Chunk added to File: Chunk - SEQ_NUM: {seq_num} - CHUNKID: {chunk_id}")

            # Zugehörigen Frame bestimmen
            frame_id = chunk_id // self.frame_size

            # Frame-Struktur anlegen, falls noch nicht da
            if frame_id not in file["frames"]:
                file["frames"][frame_id] = {
                    "received": set(),
                    "timer": None,
                }

            frame = file["frames"][frame_id]
            frame["received"].add(chunk_id)
            print(f"[INFO] ChunkID: {chunk_id} added to Frame: {frame_id}")

            # Falls es einen laufenden Timer für diesen Frame gibt, stoppen
            print(f"[INFO] Chunk received, cur Time: {frame["timer"]}")
            if frame["timer"]:
                frame["timer"].cancel()
                frame["timer"] = None

            # Frame-Grenzen berechnen
            frame_start = frame_id * self.frame_size
            frame_end = min(frame_start + self.frame_size, file["total_chunks"])
            expected_chunks = frame_end - frame_start

            print(f"[INFO] Frame received: {len(frame["received"])} chunks | Expected: {expected_chunks}")

            # Ist der Frame vollständig?
            if len(frame["received"]) == expected_chunks:
                print(f"[INFO] Frame completed")
                # ACK für kompletten Frame senden
                print(f"[INFO] Give call to send ACK for Seq_Num: {seq_num} to {src_ip}/{src_port}")
                seq_num, src_ip, src_port = key
                threading.Thread(
                    target=self.on_frame_complete,
                    args=(seq_num, src_ip, src_port),
                    daemon=True
                ).start()
                # Datei ggf. komplett?
                if len(file["received"]) == file["total_chunks"]:
                    print(f"[INFO] File completed -> Assembling")
                    print(f"Assembled file in: {self.assemble_file(seq_num, src_ip, src_port)}")

            else:
                print(f"[INFO] Frame not completed restarting timer, cur Time: {frame["timer"]}")
                # Frame noch nicht vollständig → neuen Timer starten
                frame["timer"] = threading.Timer(
                    self.frame_wait_time,
                    self._frame_timeout,
                    args=(key, frame_id)
                )
                frame["timer"].start()
                print(f"[INFO] Timer resetted, cur Time: {frame["timer"]}")

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

            # Prüfe, ob dieser Timer noch aktiv ist
            # (könnte bereits durch neuen Chunk ersetzt worden sein)
            current_timer = threading.current_thread()
            if frame["timer"] != current_timer and frame["timer"] is not None:
                return  # Timer wurde bereits durch neuen ersetzt

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
            print(len(file["received"]), file["total_chunks"])
            return len(file["received"]) == file["total_chunks"]

    def assemble_file(self, seq_num, src_ip, src_port, output_folder="/Users/fridi/PycharmProjects/CustomNetworkRN/received_data/"):
        print(f"[INFO] Called assemble_file")

        key = (seq_num, src_ip, src_port)
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
