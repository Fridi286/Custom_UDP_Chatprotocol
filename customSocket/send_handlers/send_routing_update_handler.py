import ipaddress

from customSocket import config, byteEncoder
from customSocket.helpers.models import RoutingUpdatePayload, RoutingUpdateEntry, RoutingUpdateMessage, Header


def send_routing_update(mySocket):
    """
    Sendet Routing Updates an alle lebenden Nachbarn.

    Implementiert:
    1. Split Horizon: Routen werden NICHT an den Next-Hop zurückgesendet
    2. Poison Reverse: Tote Nachbarn werden mit Distance 255 markiert
    """
    # Hole alle lebenden Nachbarn
    alive_neighbors = mySocket.neighbor_table.get_alive_neighbors()

    if not alive_neighbors:
        print("[INFO] No alive neighbors to send routing update to")
        return

    # Hole alle Routen aus der Routing-Tabelle
    # Format: [(dest_ip, dest_port, distance), ...]
    routing_entries = mySocket.routing_table.export_for_update()

    # Für jeden lebenden Nachbarn ein individuelles Update senden
    for neighbor in alive_neighbors:
        neighbor_ip = neighbor.ip
        neighbor_port = neighbor.port

        # Erstelle Liste der Einträge mit Split Horizon
        entries_for_neighbor = []

        for dest_ip, dest_port, distance in routing_entries:
            # Hole die vollständige Route aus der Routing-Tabelle
            route = mySocket.routing_table.get_route(dest_ip, dest_port)

            if route is None:
                continue

            # Split Horizon: Sende keine Route zurück zum Next-Hop
            # Wenn der Next-Hop dieses Nachbarn ist, überspringe diese Route komplett
            if route.next_hop_ip == neighbor_ip and route.next_hop_port == neighbor_port:
                continue  # Route wird NICHT gesendet (Split Horizon)

            is_dest_dead = False
            # Prüfe ob das Ziel ein toter Nachbar ist
            if mySocket.neighbor_table.is_neighbor(dest_ip, dest_port):
                is_dest_dead = not mySocket.neighbor_table.is_alive(dest_ip, dest_port)


            if is_dest_dead:
                # Poison Reverse: Tote Nachbarn mit Distance 255 markieren
                entries_for_neighbor.append(
                    RoutingUpdateEntry(
                        dest_ip=dest_ip,
                        dest_port=dest_port,
                        distance=255  # Poison für tote Nachbarn
                    )
                )
            else:
                # Normale Route senden
                entries_for_neighbor.append(
                    RoutingUpdateEntry(
                        dest_ip=dest_ip,
                        dest_port=dest_port,
                        distance=distance
                    )
                )

        # Wenn keine Einträge vorhanden sind, trotzdem ein leeres Update senden
        # (damit Nachbarn wissen, dass wir noch leben)

        # Erstelle die Payload
        payload = RoutingUpdatePayload(entries=entries_for_neighbor)

        # Hole neue Sequenznummer
        seq_num = mySocket.get_seq_num()

        # Erstelle die Nachricht
        update_msg = RoutingUpdateMessage(
            header=Header(
                type=9,  # ROUTING_UPDATE
                sequence_number=seq_num,
                destination_ip=neighbor_ip,
                source_ip=int(ipaddress.IPv4Address(mySocket.my_ip_str)),
                destination_port=neighbor_port,
                source_port=mySocket.my_port,
                payload_length=0,
                chunk_id=0,
                chunk_length=0,
                ttl=config.TTL_DEFAULT,
                checksum=bytes(32)
            ),
            payload=payload
        )

        # Encodiere und sende
        encoded_data = byteEncoder.encodePayload(update_msg)
        mySocket.send_queue.put((
            encoded_data,
            (str(ipaddress.IPv4Address(neighbor_ip)), neighbor_port)
        ))

        #print(f"[SENT] Routing Update to {ipaddress.IPv4Address(neighbor_ip)}:{neighbor_port} with {len(entries_for_neighbor)} entries")

    return



