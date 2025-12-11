import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import threading


class ChatGUI:
    def __init__(self, socket_instance):
        self.socket = socket_instance
        self.window = tk.Tk()
        self.window.title(f"Chat - {self.socket.my_ip_str}:{self.socket.my_port}")
        self.window.geometry("600x500")

        # Ziel-IP
        tk.Label(self.window, text="Ziel-IP:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ip_entry = tk.Entry(self.window, width=30)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5)

        # Ziel-Port
        tk.Label(self.window, text="Ziel-Port:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.port_entry = tk.Entry(self.window, width=30)
        self.port_entry.grid(row=1, column=1, padx=5, pady=5)

        # Nachrichtenfeld
        tk.Label(self.window, text="Nachricht:").grid(row=2, column=0, padx=5, pady=5, sticky="nw")
        self.msg_text = scrolledtext.ScrolledText(self.window, height=15, width=60)
        self.msg_text.grid(row=2, column=1, padx=5, pady=5)

        # Buttons
        button_frame = tk.Frame(self.window)
        button_frame.grid(row=3, column=1, pady=10)

        tk.Button(button_frame, text="Text senden", command=self.send_text, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Datei senden", command=self.send_file, width=15).pack(side=tk.LEFT, padx=5)

        # Status-Label
        self.status_label = tk.Label(self.window, text="Bereit", fg="green")
        self.status_label.grid(row=4, column=0, columnspan=2, pady=5)

    def send_text(self):
        try:
            dest_ip = self.ip_entry.get().strip()
            dest_port = int(self.port_entry.get().strip())
            msg = self.msg_text.get("1.0", tk.END).strip()

            if not dest_ip or not dest_port or not msg:
                messagebox.showwarning("Warnung", "Bitte alle Felder ausfüllen!")
                return

            seqNum = self.socket.get_seq_num()
            from customSocket.send_handlers import send_msg_handler

            threading.Thread(
                target=send_msg_handler.send_Text,
                args=(self.socket, seqNum, msg, dest_ip, dest_port, self.socket.my_ip_str, self.socket.my_port),
                daemon=True
            ).start()

            self.status_label.config(text=f"Nachricht gesendet an {dest_ip}:{dest_port}", fg="green")
            self.msg_text.delete("1.0", tk.END)

        except ValueError:
            messagebox.showerror("Fehler", "Port muss eine Zahl sein!")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def send_file(self):
        try:
            dest_ip = self.ip_entry.get().strip()
            dest_port = int(self.port_entry.get().strip())

            if not dest_ip or not dest_port:
                messagebox.showwarning("Warnung", "Bitte IP und Port eingeben!")
                return

            # Datei auswählen
            file_path = filedialog.askopenfilename(
                title="Datei zum Senden auswählen",
                filetypes=[("Alle Dateien", "*.*")]
            )

            print(file_path)

            if not file_path:
                return  # Benutzer hat abgebrochen

            seqNum = self.socket.get_seq_num()
            from customSocket.send_handlers import send_file_handler

            threading.Thread(
                target=send_file_handler.send_Data,
                args=(self.socket, seqNum, file_path, dest_ip, dest_port, self.socket.my_ip_str, self.socket.my_port),
                daemon=True
            ).start()

            self.status_label.config(text=f"Datei '{file_path.split('/')[-1]}' wird gesendet an {dest_ip}:{dest_port}",
                                     fg="blue")

        except ValueError:
            messagebox.showerror("Fehler", "Port muss eine Zahl sein!")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def run(self):
        self.window.mainloop()
