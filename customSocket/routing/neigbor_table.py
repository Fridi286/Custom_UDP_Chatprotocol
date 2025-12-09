from dataclasses import dataclass
import time
from typing import Dict, Tuple, Optional

from pydantic import BaseModel

from customSocket import config

HEARTBEAT_TIMER = config.HEARTBEAT_TIMER  # laut Spezifikation

class NeighborEntry (BaseModel):
    ip: int
    port: int
    last_heard: float
    alive: bool = True


class NextNeighborTable:

    def __init__(self):
        # Key = (ip, port)
        self.neighbors: Dict[Tuple[int, int], NeighborEntry] = {}

    def update_neighbor(self, ip: int, port: int):
        """
        Wird bei jedem HEARTBEAT, HELLO oder jedem Paket des Nachbarn aufgerufen.
        """
        now = time.time()
        key = (ip, port)

        if key not in self.neighbors:
            # Neuer Nachbar
            self.neighbors[key] = NeighborEntry(ip=ip, port=port, last_heard=now, alive=True)
        else:
            entry = self.neighbors[key]
            entry.last_heard = now
            entry.alive = True

    def mark_dead_if_timeout(self, ip: int, port: int) -> bool:
        """
        Prüft, ob dieser Nachbar tot ist (heartbeat * 2 + 1).
        Gibt True zurück wenn er neu als tot markiert wurde.
        """
        key = (ip, port)
        if key not in self.neighbors:
            return False

        entry = self.neighbors[key]
        now = time.time()

        timeout_limit = HEARTBEAT_TIMER * 2 + 1
        if now - entry.last_heard > timeout_limit:
            if entry.alive:  # Übergang alive → dead
                entry.alive = False
                return True

        return False

    def get_alive_neighbors(self):
        return [n for n in self.neighbors.values() if n.alive]

    def is_alive(self, ip: int, port: int) -> bool:
        entry = self.neighbors.get((ip, port))
        return entry.alive if entry else False
