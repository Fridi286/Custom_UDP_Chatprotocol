import threading
import time
from typing import Dict, Tuple

from customSocket import config


class RoutingTableMonitor(threading.Thread):
    """
    Überwacht die Routing-Tabelle auf poisoned routes (Distance = 255).

    Gemäß Spezifikation:
    - Erkennt Einträge mit Distance 255
    - Triggert ein Routing Update (damit andere Nodes informiert werden)
    - Löscht den Eintrag nach heartbeat_timer × 3 Sekunden
    """

    def __init__(self, routing_table, on_routing_update):
        """
        :param routing_table: RoutingTable Instanz
        :param on_routing_update: Callback-Funktion, die ein Routing Update triggert
        """
        super().__init__(daemon=True)
        self.routing_table = routing_table
        self.on_routing_update = on_routing_update
        self.running = True

        # Speichert poisoned routes: Key = (dest_ip, dest_port), Value = Timestamp when poisoned
        self.poisoned_routes: Dict[Tuple[int, int], float] = {}

        # Zeit bis zum Löschen: heartbeat_timer × 3 (gemäß Spezifikation)
        self.poison_timeout = config.HEARTBEAT_TIMER * 3

    def stop(self):
        """Stoppt den Monitor-Thread"""
        self.running = False

    def run(self):
        """Haupt-Loop des Monitors"""
        while self.running:
            changed = False
            now = time.time()

            # 1. Prüfe die Routing-Tabelle auf neue poisoned routes
            for (dest_ip, dest_port), entry in list(self.routing_table.table.items()):
                key = (dest_ip, dest_port)

                if entry.distance == 255:
                    # Route ist poisoned
                    if key not in self.poisoned_routes:
                        # Neu poisoned → merken und Update triggern
                        self.poisoned_routes[key] = now
                        changed = True
                        print(f"[POISON] Route to {dest_ip}:{dest_port} poisoned (Distance=255)")

            # 2. Prüfe ob poisoned routes gelöscht werden können
            to_delete = []
            for key, poison_time in list(self.poisoned_routes.items()):
                if now - poison_time >= self.poison_timeout:
                    # Timeout erreicht → Route löschen
                    dest_ip, dest_port = key

                    if key in self.routing_table.table:
                        del self.routing_table.table[key]
                        print(f"[POISON] Deleted poisoned route to {dest_ip}:{dest_port} after {self.poison_timeout}s")
                        changed = True

                    to_delete.append(key)

            # 3. Entferne gelöschte Routes aus dem Tracking
            for key in to_delete:
                del self.poisoned_routes[key]

            # 4. Wenn sich etwas geändert hat → Routing Update triggern
            if changed:
                print("[ROUTING] Table changed due to poison, triggering update")
                self.on_routing_update()

            # Scan alle 1 Sekunde
            time.sleep(1)

