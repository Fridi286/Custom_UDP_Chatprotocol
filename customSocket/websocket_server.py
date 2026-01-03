# websocket_server.py
import asyncio
import ipaddress
import json
import threading
import sys
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

# WICHTIG: Windows-Kompatibilität
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.my_socket = None
        self.loop = None
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        with self._lock:
            self.active_connections.add(websocket)
        print(f"[WEBSOCKET] Client verbunden, Anzahl: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        with self._lock:
            self.active_connections.discard(websocket)
        print(f"[WEBSOCKET] Client getrennt, verbleibend: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        with self._lock:
            connections = list(self.active_connections)

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WEBSOCKET] Broadcast-Fehler: {e}")
                self.disconnect(connection)

    def broadcast_sync(self, message: dict):
        """Synchrone Version für Callbacks aus anderen Threads"""
        if not self.loop or self.loop.is_closed():
            print("[WEBSOCKET] Event Loop nicht verfügbar")
            return

        try:
            future = asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)
            future.result(timeout=1.0)
        except Exception as e:
            print(f"[WEBSOCKET] broadcast_sync Fehler: {e}")


manager = ConnectionManager()

# HTML Client
html = """
<!DOCTYPE html>
<html>
<head>
    <title>Custom UDP Chat</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #messages {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #ccc;
            padding: 10px;
            margin: 10px 0;
        }
        .msg { margin: 5px 0; padding: 5px; background: #f0f0f0; border-radius: 3px; }
        .file { margin: 5px 0; padding: 5px; background: #e0f0ff; border-radius: 3px; }
        input { margin: 5px; padding: 5px; }
        button { padding: 5px 15px; cursor: pointer; }
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
            console.log('WebSocket verbunden');
        };

        ws.onerror = (e) => {
            document.getElementById('status').innerHTML = '<b style="color:red">Verbindungsfehler</b>';
            console.error('WebSocket Fehler:', e);
        };

        ws.onclose = (e) => {
            document.getElementById('status').innerHTML = '<b style="color:orange">Getrennt</b>';
            console.log('WebSocket geschlossen:', e);
        };

        ws.onmessage = (e) => {
            const data = JSON.parse(e.data);
            console.log('Empfangen:', data);

            if(data.type === 'peers') {
                document.getElementById('peers').innerHTML =
                    '<h3>Peers:</h3>' + data.peers.map(p => `${p.ip}:${p.port}`).join('<br>');
            }
            else if(data.type === 'message') {
                const msgDiv = document.createElement('div');
                msgDiv.className = 'msg';
                msgDiv.innerHTML = `<b>${data.from}</b>: ${data.text} <i>(seq: ${data.seq_num})</i>`;
                document.getElementById('messages').appendChild(msgDiv);
                scrollMessages();
            }
            else if(data.type === 'file_started') {
                const fileDiv = document.createElement('div');
                fileDiv.className = 'file';
                fileDiv.innerHTML = `<b>${data.from}</b> sendet Datei: <b>${data.filename}</b> (${data.chunks} Chunks) <i>(seq: ${data.seq_num})</i>`;
                document.getElementById('messages').appendChild(fileDiv);
                scrollMessages();
            }
            else if(data.type === 'file_complete') {
                const fileDiv = document.createElement('div');
                fileDiv.className = 'file';
                fileDiv.innerHTML = `
                    <b>${data.from}</b> - Datei empfangen: <b>${data.filename}</b> <i>(seq: ${data.seq_num})</i><br>
                    <button onclick="copyToClipboard('${data.file_path}')">📋 Pfad kopieren</button>
                    <code style="font-size: 0.9em; color: #666;">${data.file_path}</code>
                `;
                document.getElementById('messages').appendChild(fileDiv);
                scrollMessages();
            }
            else if(data.type === 'success' || data.type === 'error') {
                alert(data.message);
            }
        };

        function scrollMessages() {
            const messagesDiv = document.getElementById('messages');
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                alert('Pfad in Zwischenablage kopiert!');
            });
        }

        function sendMessage() {
            const destIp = document.getElementById('destIp').value;
            const destPort = parseInt(document.getElementById('destPort').value);
            const message = document.getElementById('message').value;

            if(!destIp || !destPort || !message) {
                alert('Bitte alle Felder ausfüllen');
                return;
            }

            ws.send(JSON.stringify({
                action: 'send_text',
                dest_ip: destIp,
                dest_port: destPort,
                message: message
            }));
            document.getElementById('message').value = '';
        }

        function sendFile() {
            const destIp = document.getElementById('destIp').value;
            const destPort = parseInt(document.getElementById('destPort').value);
            const filePath = document.getElementById('filePath').value;

            if(!destIp || !destPort || !filePath) {
                alert('Bitte alle Felder ausfüllen');
                return;
            }

            ws.send(JSON.stringify({
                action: 'send_file',
                dest_ip: destIp,
                dest_port: destPort,
                file_path: filePath
            }));
        }

        // Peers alle 2 Sekunden abfragen
        setInterval(() => {
            if(ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({action: 'get_peers'}));
            }
        }, 2000);
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
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")

            if action == "send_text":
                await handle_send_text(message, websocket)
            elif action == "send_file":
                await handle_send_file(message, websocket)
            elif action == "get_peers":
                await handle_get_peers(websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WEBSOCKET ERROR] {e}")
        manager.disconnect(websocket)


async def handle_send_text(data: dict, websocket: WebSocket):
    try:
        dest_ip = data["dest_ip"]
        dest_port = data["dest_port"]
        message = data["message"]

        seq_num = manager.my_socket.get_seq_num()

        def send_task():
            from customSocket.send_handlers import send_msg_handler
            send_msg_handler.send_Text(
                manager.my_socket,
                seq_num,
                message,
                dest_ip,
                dest_port,
                manager.my_socket.my_ip_str,
                manager.my_socket.my_port
            )

        threading.Thread(target=send_task, daemon=True).start()
        await websocket.send_json({"type": "success", "message": "Nachricht wird gesendet..."})

    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})


async def handle_send_file(data: dict, websocket: WebSocket):
    try:
        dest_ip = data["dest_ip"]
        dest_port = data["dest_port"]
        file_path = data["file_path"]

        seq_num = manager.my_socket.get_seq_num()

        def send_task():
            from customSocket.send_handlers import send_file_handler
            send_file_handler.send_Data(
                manager.my_socket,
                seq_num,
                file_path,
                dest_ip,
                dest_port,
                manager.my_socket.my_ip_str,
                manager.my_socket.my_port
            )

        threading.Thread(target=send_task, daemon=True).start()
        await websocket.send_json({"type": "success", "message": "Datei wird gesendet..."})

    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})


async def handle_get_peers(websocket: WebSocket):
    if not manager.my_socket:
        await websocket.send_json({"type": "peers", "peers": []})
        return

    neighbors = manager.my_socket.neighbor_table.get_alive_neighbors()
    peers = [{"ip": str(ipaddress.IPv4Address(n.ip)), "port": n.port} for n in neighbors]

    await websocket.send_json({"type": "peers", "peers": peers})


def notify_message_received(msg):
    manager.broadcast_sync({
        "type": "message",
        "from": f"{str(ipaddress.IPv4Address(msg.header.source_ip))}:{msg.header.source_port}",
        "text": msg.payload.text,
        "seq_num": msg.header.sequence_number
    })


def notify_file_received(file_info):
    manager.broadcast_sync({
        "type": "file_started",
        "from": f"{str(ipaddress.IPv4Address(file_info.header.source_ip))}:{file_info.header.source_port}",
        "filename": file_info.payload.filename,
        "chunks": file_info.header.chunk_length,
        "seq_num": file_info.header.sequence_number
    })


def notify_file_complete(data):
    manager.broadcast_sync({
        "type": "file_complete",
        "from": f"{str(ipaddress.IPv4Address(data['src_ip']))}:{data['src_port']}",
        "filename": data['filename'],
        "file_path": data['file_path'],
        "seq_num": data['seq_num']
    })


def init_websocket_server(my_socket):
    """Startet den WebSocket-Server in separatem Thread"""
    manager.my_socket = my_socket
    port = my_socket.my_port + 1000

    def run_server():
        print(f"[WEBSOCKET] Starte Server-Thread...")

        # Event Loop für Windows erstellen
        if sys.platform == 'win32':
            loop = asyncio.new_event_loop()
        else:
            loop = asyncio.new_event_loop()

        asyncio.set_event_loop(loop)
        manager.loop = loop

        print(f"[WEBSOCKET] Event Loop erstellt: {loop}")

        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=port,
            log_level="warning",
            access_log=False
        )
        server = uvicorn.Server(config)

        print(f"[WEBSOCKET] Server startet auf http://0.0.0.0:{port}")

        try:
            loop.run_until_complete(server.serve())
        except Exception as e:
            print(f"[WEBSOCKET] Server-Fehler: {e}")

    thread = threading.Thread(target=run_server, daemon=True, name="WebSocket-Server")
    thread.start()

    # Warte kurz bis Server bereit ist
    import time
    time.sleep(1)

    print(f"[WEBSOCKET] Server sollte nun auf http://localhost:{port} erreichbar sein")
