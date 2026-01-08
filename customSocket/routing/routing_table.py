from dataclasses import dataclass
from typing import Dict, Tuple, Optional

from pydantic import BaseModel


class RoutingEntry(BaseModel):
    dest_ip: int
    dest_port: int
    next_hop_ip: int
    next_hop_port: int
    distance: int


class RoutingTable:
    def __init__(self):
        # Key = (dest_ip, dest_port)
        self.table: Dict[Tuple[int, int], RoutingEntry] = {}

    # returns fastest route
    def get_route(self, dest_ip: int, dest_port: int) -> Optional[RoutingEntry]:
        return self.table.get((dest_ip, dest_port))

    # updates own routing table, returns True if updated -> False when nothing changed
    def update_route(self, dest_ip: int, dest_port: int,
                     next_hop_ip: int, next_hop_port: int, distance: int) -> bool:
        key = (dest_ip, dest_port)
        existing = self.table.get(key)

        # Distance auf 255 begrenzen (256 -> 255)
        if distance > 255:
            distance = 255

        # Szenario A: Neue Route
        if existing is None:
            if distance < 255:  # Nur erreichbare Routen hinzufügen
                self.table[key] = RoutingEntry(
                    dest_ip=dest_ip,
                    dest_port=dest_port,
                    next_hop_ip=next_hop_ip,
                    next_hop_port=next_hop_port,
                    distance=distance
                )
                return True
            return False

        # Szenario C: Update vom gleichen Hop (WICHTIG: vor Szenario B!)
        if existing.next_hop_ip == next_hop_ip and existing.next_hop_port == next_hop_port:
            if existing.distance != distance:
                self.table[key] = RoutingEntry(
                    dest_ip=dest_ip,
                    dest_port=dest_port,
                    next_hop_ip=next_hop_ip,
                    next_hop_port=next_hop_port,
                    distance=distance  # Auch 255 wird gespeichert (Route Poisoning)
                )
                return True
            return False

        # Szenario B: Kürzere Route über anderen Hop
        if distance < existing.distance:
            self.table[key] = RoutingEntry(
                dest_ip=dest_ip,
                dest_port=dest_port,
                next_hop_ip=next_hop_ip,
                next_hop_port=next_hop_port,
                distance=distance
            )
            return True

        # Szenario D: Ignorieren
        return False

    def delete_routes_via(self, hop_ip: int, hop_port: int) -> bool:
        # Entfernt ALLE Routen, die über diesen Nachbarn laufen.
        to_delete = [key for key, entry in self.table.items()
                     if entry.next_hop_ip == hop_ip and entry.next_hop_port == hop_port]

        changed = len(to_delete) > 0
        for key in to_delete:
            del self.table[key]

        return changed

    def export_for_update(self):
        """
        Gibt eine Liste zurück für das RoutingUpdatePayload:
        [(dest_ip, dest_port, distance), ...]
        """
        return [
            (entry.dest_ip, entry.dest_port, entry.distance)
            for entry in self.table.values()
        ]

    def get_all_routes(self):
        """
        Gibt alle Routen als Liste von RoutingEntry zurück
        """
        return list(self.table.values())

    def poison_routes_via(self, hop_ip: int, hop_port: int) -> bool:
        """
        Setzt alle Routen über einen Nachbarn auf Distance 255 (Route Poisoning).
        Gibt True zurück wenn sich etwas geändert hat.
        """
        changed = False

        for key, entry in list(self.table.items()):
            if entry.next_hop_ip == hop_ip and entry.next_hop_port == hop_port:
                # Nur ändern wenn nicht schon poisoned
                if entry.distance != 255:
                    self.table[key] = RoutingEntry(
                        dest_ip=entry.dest_ip,
                        dest_port=entry.dest_port,
                        next_hop_ip=entry.next_hop_ip,
                        next_hop_port=entry.next_hop_port,
                        distance=255
                    )
                    changed = True
                    print(f"[POISON] Route to {entry.dest_ip}:{entry.dest_port} via {hop_ip}:{hop_port}")

        return changed