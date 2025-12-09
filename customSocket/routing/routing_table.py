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
        # Szenario: Eintrag für IP/PORT existiert nicht
        if existing is None:
            self.table[key] = RoutingEntry(dest_ip, dest_port, next_hop_ip, next_hop_port, distance)
            return True

        # Szenario: Es gibt eine kürzere Distanz zu existierendem IP/PORT, über anderen HOP
        if distance < existing.distance:
            self.table[key] = RoutingEntry(dest_ip, dest_port, next_hop_ip, next_hop_port, distance)
            return True

        # Szenario: Es gibt eine kürzere Distanz zu existierendem IP/PORT, bei gleichem HOP
        if existing.next_hop_ip == next_hop_ip and existing.next_hop_port == next_hop_port:
            if existing.distance != distance:
                existing.distance = distance
                return True

        # Szenario: ignorieren
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
