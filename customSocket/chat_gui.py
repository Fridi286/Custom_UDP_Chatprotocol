import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import queue
import ipaddress


class ChatGUI:
    def __init__(self, my_socket):
        self.my_socket = my_socket
        self.root = tk.Tk()
        self.root.title(f"Chat - {my_socket.my_ip_str}:{my_socket.my_port}")
        self.root.geometry("1000x700")

        # Queue für eingehende Nachrichten
        self.incoming_msg_queue = queue.Queue()

        self._create_widgets()

        # Routing-Update Hook registrieren
        self._start_routing_monitor()

        # Nachrichten-Monitor starten
        self._start_message_monitor()

    def _create_widgets(self):
        # Hauptcontainer
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Linke Seite: Routing-Tabelle
        left_frame = ttk.LabelFrame(main_frame, text="Erreichbare Hosts", padding="5")
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))

        # Treeview für Routing-Tabelle
        self.routing_tree = ttk.Treeview(left_frame, columns=("IP", "Port", "Hops"), show="headings", height=15)
        self.routing_tree.heading("IP", text="IP-Adresse")
        self.routing_tree.heading("Port", text="Port")
        self.routing_tree.heading("Hops", text="Hops")
        self.routing_tree.column("IP", width=120)
        self.routing_tree.column("Port", width=60)
        self.routing_tree.column("Hops", width=50)

        scrollbar_routing = ttk.Scrollbar(left_frame, orient="vertical", command=self.routing_tree.yview)
        self.routing_tree.configure(yscrollcommand=scrollbar_routing.set)

        self.routing_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_routing.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Doppelklick auf Route übernimmt IP/Port
        self.routing_tree.bind("<Double-1>", self._on_route_select)

        # Rechte Seite: Chat
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Empfangene Nachrichten
        msg_frame = ttk.LabelFrame(right_frame, text="Empfangene Nachrichten", padding="5")
        msg_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))

        self.msg_display = scrolledtext.ScrolledText(msg_frame, width=60, height=15, state='disabled')
        self.msg_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Senden
        send_frame = ttk.LabelFrame(right_frame, text="Nachricht senden", padding="5")
        send_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))

        ttk.Label(send_frame, text="Ziel-IP:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.dest_ip_entry = ttk.Entry(send_frame, width=20)
        self.dest_ip_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)

        ttk.Label(send_frame, text="Ziel-Port:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.dest_port_entry = ttk.Entry(send_frame, width=20)
        self.dest_port_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)

        ttk.Label(send_frame, text="Nachricht:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.msg_entry = ttk.Entry(send_frame, width=20)
        self.msg_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2)

        button_frame = ttk.Frame(send_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=5)

        ttk.Button(button_frame, text="Text senden", command=self._send_text).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Datei senden", command=self._send_file).pack(side=tk.LEFT, padx=2)

        # Grid-Gewichte
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=3)
        left_frame.rowconfigure(0, weight=1)
        left_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        msg_frame.rowconfigure(0, weight=1)
        msg_frame.columnconfigure(0, weight=1)

    def _update_routing_table(self):
        """Aktualisiert die Routing-Tabelle Anzeige"""
        # Alte Einträge löschen
        for item in self.routing_tree.get_children():
            self.routing_tree.delete(item)

        # Neue Einträge hinzufügen
        routes = self.my_socket.routing_table.export_for_update()
        for route in routes:
            dest_ip_int, dest_port, hops = route
            ip_str = str(ipaddress.IPv4Address(dest_ip_int))
            # Eigene IP nicht anzeigen
            if ip_str == self.my_socket.my_ip_str and dest_port == self.my_socket.my_port:
                continue
            self.routing_tree.insert("", tk.END, values=(ip_str, dest_port, hops))

    def _on_route_select(self, event):
        """Übernimmt ausgewählte Route in die Eingabefelder"""
        selection = self.routing_tree.selection()
        if selection:
            item = self.routing_tree.item(selection[0])
            ip, port, _ = item['values']
            self.dest_ip_entry.delete(0, tk.END)
            self.dest_ip_entry.insert(0, ip)
            self.dest_port_entry.delete(0, tk.END)
            self.dest_port_entry.insert(0, port)

    def _start_routing_monitor(self):
        """Überwacht Routing-Updates"""

        def monitor():
            while True:
                self.root.after(0, self._update_routing_table)
                threading.Event().wait(2)  # Alle 2 Sekunden aktualisieren

        threading.Thread(target=monitor, daemon=True).start()

    def _start_message_monitor(self):
        """Überwacht eingehende Nachrichten"""

        def check_messages():
            try:
                while True:
                    msg = self.incoming_msg_queue.get_nowait()
                    self._display_message(msg)
            except queue.Empty:
                pass
            finally:
                self.root.after(100, check_messages)

        self.root.after(100, check_messages)

    def _display_message(self, msg):
        """Zeigt eine Nachricht an"""
        self.msg_display.configure(state='normal')
        self.msg_display.insert(tk.END, msg + "\n")
        self.msg_display.see(tk.END)
        self.msg_display.configure(state='disabled')

    def add_incoming_message(self, sender_ip, sender_port, message):
        """Wird von außen aufgerufen, um eine Nachricht hinzuzufügen"""
        formatted_msg = f"[{sender_ip}:{sender_port}] {message}"
        self.incoming_msg_queue.put(formatted_msg)

    def _send_text(self):
        dest_ip = self.dest_ip_entry.get()
        dest_port = self.dest_port_entry.get()
        msg = self.msg_entry.get()

        if not dest_ip or not dest_port or not msg:
            messagebox.showwarning("Warnung", "Bitte alle Felder ausfüllen!")
            return

        try:
            from customSocket.send_handlers import send_msg_handler
            seq_num = self.my_socket.get_seq_num()
            threading.Thread(
                target=send_msg_handler.send_Text,
                args=(self.my_socket, seq_num, msg, dest_ip, int(dest_port),
                      self.my_socket.my_ip_str, self.my_socket.my_port),
                daemon=True
            ).start()
            self.msg_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Senden: {e}")

    def _send_file(self):
        dest_ip = self.dest_ip_entry.get()
        dest_port = self.dest_port_entry.get()

        if not dest_ip or not dest_port:
            messagebox.showwarning("Warnung", "Bitte Ziel-IP und Port eingeben!")
            return

        file_path = filedialog.askopenfilename()
        if file_path:
            try:
                from customSocket.send_handlers import send_file_handler
                seq_num = self.my_socket.get_seq_num()
                threading.Thread(
                    target=send_file_handler.send_Data,
                    args=(self.my_socket, seq_num, file_path, dest_ip, int(dest_port),
                          self.my_socket.my_ip_str, self.my_socket.my_port),
                    daemon=True
                ).start()
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Senden: {e}")

    def run(self):
        self.root.mainloop()
