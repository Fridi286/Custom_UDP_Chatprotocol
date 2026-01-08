import threading
import time

class NeighborMonitor(threading.Thread):

    def __init__(self, neighbor_table, routing_table, on_routing_update):
        """
        :param neighbor_table: deine NextNeighborTable Instanz
        :param routing_table: deine RoutingTable Instanz
        :param on_routing_update: callback, wird ausgeführt wenn ein Routing-Update gesendet werden soll
        """
        super().__init__(daemon=True)
        self.neighbor_table = neighbor_table
        self.routing_table = routing_table
        self.on_routing_update = on_routing_update
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            changed = False

            for (ip, port), entry in list(self.neighbor_table.neighbors.items()):
                died_now = self.neighbor_table.mark_dead_if_timeout(ip, port)

                if died_now:
                    print(f"[NEIGHBOR DEAD] {ip}:{port}")

                    # Poison alle Routen über diesen Nachbarn (statt löschen!)
                    if self.routing_table.poison_routes_via(ip, port):
                        changed = True

            if changed:
                self.on_routing_update()

            time.sleep(1)
