# websocket_server.py
import asyncio
import ipaddress
import json
import threading
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.my_socket = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.copy():
            try:
                await connection.send_json(message)
            except:
                self.active_connections.discard(connection)

    def broadcast_sync(self, message: dict):
        """Synchrone Version für Callbacks aus anderen Threads"""
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.broadcast(message))
            loop.close()
        except:
            pass


manager = ConnectionManager()

# HTML Client für Testzwecke
html = """
<!DOCTYPE html>
<html>
<head>
    <title>Custom UDP Chat</title>
    <style>
        #messages { 
            max-height: 400px; 
            overflow-y: auto; 
            border: 1px solid #ccc; 
            padding: 10px; 
            margin: 10px 0;
        }
        .msg { margin: 5px 0; padding: 5px; background: #f0f0f0; }
        .file { margin: 5px 0; padding: 5px; background: #e0f0ff; }
    </style>
</head>
<body>
    <h1>UDP Chat Interface</h1>
    <div id="status">Verbinde...</div>
    <div id="peers"></div>

    <h3>Nachricht senden</h3>
    <input id="destIp" placeholder="Ziel-IP"/>
    <input id="destPort" placeholder="Ziel-Port" type="number"/>
    <input id="message" placeholder="Nachricht"/>
    <button onclick="sendMessage()">Text senden</button>

    <h3>Datei senden</h3>
    <input id="filePath" placeholder="Dateipfad"/>
    <button onclick="sendFile()">Datei senden</button>

    <h3>Empfangene Nachrichten</h3>
    <div id="messages"></div>

    <script>
        const port = window.location.port;
        const ws = new WebSocket(`ws://localhost:${port}/ws`);

        ws.onopen = () => {
            document.getElementById('status').innerHTML = '<b style="color:green">Verbunden</b>';
        };

        ws.onerror = () => {
            document.getElementById('status').innerHTML = '<b style="color:red">Verbindungsfehler</b>';
        };

        ws.onmessage = (e) => {
            const data = JSON.parse(e.data);

            if(data.type === 'peers') {
                document.getElementById('peers').innerHTML =
                    '<h3>Peers:</h3>' + data.peers.map(p => `${p.ip}:${p.port}`).join('<br>');
            } 
            else if(data.type === 'message') {
                const msgDiv = document.createElement('div');
                msgDiv.className = 'msg';
                msgDiv.innerHTML = `<b>${data.from}</b>: ${data.text} <i>(seq: ${data.seq_num})</i>`;
                document.getElementById('messages').appendChild(msgDiv);
                document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
            }
            else if(data.type === 'file_started') {
                const fileDiv = document.createElement('div');
                fileDiv.className = 'file';
                fileDiv.innerHTML = `<b>${data.from}</b> sendet Datei: <b>${data.filename}</b> (${data.chunks} Chunks) <i>(seq: ${data.seq_num})</i>`;
                document.getElementById('messages').appendChild(fileDiv);
                document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
            }
            else if(data.type === 'success' || data.type === 'error') {
                alert(data.message);
            }
        };

        function sendMessage() {
            ws.send(JSON.stringify({
                action: 'send_text',
                dest_ip: document.getElementById('destIp').value,
                dest_port: parseInt(document.getElementById('destPort').value),
                message: document.getElementById('message').value
            }));
            document.getElementById('message').value = '';
        }

        function sendFile() {
            ws.send(JSON.stringify({
                action: 'send_file',
                dest_ip: document.getElementById('destIp').value,
                dest_port: parseInt(document.getElementById('destPort').value),
                file_path: document.getElementById('filePath').value
            }));
        }

        setInterval(() => ws.send(JSON.stringify({action: 'get_peers'})), 2000);
    </script>
</body>
</html>
"""


@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "send_text":
                await handle_send_text(data, websocket)
            elif action == "send_file":
                await handle_send_file(data, websocket)
            elif action == "get_peers":
                await handle_get_peers(websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def handle_send_text(data: dict, websocket: WebSocket):
    """Text-Nachricht über UDP-Socket senden"""
    if not manager.my_socket:
        await websocket.send_json({"type": "error", "message": "Socket nicht initialisiert"})
        return

    dest_ip = data.get("dest_ip")
    dest_port = data.get("dest_port")
    message = data.get("message")

    seq_num = manager.my_socket.get_seq_num()

    # In separatem Thread ausführen
    def send():
        from customSocket.send_handlers import send_msg_handler
        send_msg_handler.send_Text(
            manager.my_socket, seq_num, message,
            dest_ip, dest_port,
            manager.my_socket.my_ip_str, manager.my_socket.my_port
        )

    threading.Thread(target=send, daemon=True).start()
    await websocket.send_json({"type": "success", "message": "Nachricht wird gesendet"})


async def handle_send_file(data: dict, websocket: WebSocket):
    """Datei über UDP-Socket senden"""
    if not manager.my_socket:
        await websocket.send_json({"type": "error", "message": "Socket nicht initialisiert"})
        return

    dest_ip = data.get("dest_ip")
    dest_port = data.get("dest_port")
    file_path = data.get("file_path")

    seq_num = manager.my_socket.get_seq_num()

    def send():
        from customSocket.send_handlers import send_file_handler
        send_file_handler.send_Data(
            manager.my_socket, seq_num, file_path,
            dest_ip, dest_port,
            manager.my_socket.my_ip_str, manager.my_socket.my_port
        )

    threading.Thread(target=send, daemon=True).start()
    await websocket.send_json({"type": "success", "message": "Datei wird gesendet"})


async def handle_get_peers(websocket: WebSocket):
    """Liste der erreichbaren Peers senden"""
    if not manager.my_socket:
        await websocket.send_json({"type": "peers", "peers": []})
        return

    neighbors = manager.my_socket.neighbor_table.get_alive_neighbors()
    peers = [{"ip": str(ipaddress.IPv4Address(n.ip)), "port": n.port} for n in neighbors]

    await websocket.send_json({"type": "peers", "peers": peers})


def notify_message_received(msg):
    """Callback für empfangene Textnachrichten"""
    manager.broadcast_sync({
        "type": "message",
        "from": f"{str(ipaddress.IPv4Address(msg.header.source_ip))}:{msg.header.source_port}",
        "text": msg.payload.text,
        "seq_num": msg.header.sequence_number
    })


def notify_file_received(file_info):
    """Callback für empfangene Datei-Infos"""
    manager.broadcast_sync({
        "type": "file_started",
        "from": f"{str(ipaddress.IPv4Address(file_info.header.source_ip))}:{file_info.header.source_port}",
        "filename": file_info.payload.filename,
        "chunks": file_info.header.chunk_length,
        "seq_num": file_info.header.sequence_number
    })


def init_websocket_server(my_socket):
    """Startet den WebSocket-Server in separatem Thread"""
    manager.my_socket = my_socket

    def run_server():
        uvicorn.run(app, host="0.0.0.0", port=my_socket.my_port+1000, log_level="warning")

    threading.Thread(target=run_server, daemon=True).start()
    print(f"[WEBSOCKET] Server gestartet auf http://localhost:{my_socket.my_port+1000}")
