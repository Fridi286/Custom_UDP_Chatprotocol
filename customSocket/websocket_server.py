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
        #peers-container {
            display: flex;
            gap: 10px;
            margin: 20px 0;
            flex-wrap: wrap;
        }
        .peer-item {
            display: inline-block;
            padding: 8px 12px;
            background: #e8f4f8;
            border: 1px solid #b3d9e6;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.2s;
            position: relative;
        }
        .peer-item:hover {
            background: #d0e8f0;
        }
        .peer-item.active {
            background: #4a90e2;
            color: white;
            border-color: #3a7bc8;
        }
        .peer-item.has-unread {
            font-weight: bold;
        }
        .peer-item.has-unread::after {
            content: '';
            position: absolute;
            top: 5px;
            right: 5px;
            width: 10px;
            height: 10px;
            background: #ff4444;
            border-radius: 50%;
            border: 2px solid white;
        }
        .peer-item.active.has-unread::after {
            display: none;
        }
        .unread-count {
            background: #ff4444;
            color: white;
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 0.8em;
            margin-left: 8px;
            font-weight: bold;
        }
        .peer-item.active .unread-count {
            display: none;
        }
        .peer-distance {
            font-size: 0.85em;
            color: #666;
            margin-left: 8px;
        }
        .peer-item.active .peer-distance {
            color: #e0e0e0;
        }
        #chat-container {
            display: flex;
            gap: 15px;
            margin: 20px 0;
        }
        .chat-section {
            flex: 1;
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 10px;
            display: none;
        }
        .chat-section.active {
            display: block;
        }
        .chat-header {
            font-weight: bold;
            padding: 8px;
            background: #f5f5f5;
            border-radius: 3px;
            margin-bottom: 10px;
        }
        .messages-area {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 10px;
            margin-bottom: 10px;
            background: white;
        }
        .msg {
            margin: 5px 0;
            padding: 8px;
            border-radius: 5px;
            max-width: 80%;
        }
        .msg.sent {
            background: #dcf8c6;
            margin-left: auto;
            text-align: right;
        }
        .msg.received {
            background: #f0f0f0;
        }
        .msg-header {
            font-size: 0.85em;
            color: #666;
            margin-bottom: 3px;
        }
        .msg-text {
            word-wrap: break-word;
        }
        .file {
            margin: 5px 0;
            padding: 8px;
            background: #e0f0ff;
            border-radius: 5px;
            border-left: 3px solid #4a90e2;
        }
        .file-path {
            font-size: 0.9em;
            color: #666;
            background: #f5f5f5;
            padding: 3px 6px;
            border-radius: 3px;
            margin-top: 5px;
            word-break: break-all;
        }
        input, button {
            margin: 5px;
            padding: 8px;
        }
        button {
            cursor: pointer;
            background: #4a90e2;
            color: white;
            border: none;
            border-radius: 3px;
        }
        button:hover {
            background: #3a7bc8;
        }
        .send-area {
            display: flex;
            gap: 5px;
            margin-top: 10px;
        }
        .send-area input {
            flex: 1;
        }
    </style>
</head>
<body>
    <h1>UDP Chat Interface</h1>
    <div id="status">Verbinde...</div>

    <h3>Peers (klicken zum Auswählen):</h3>
    <div id="peers-container"></div>

    <div id="chat-container"></div>

    <script>
        const port = window.location.port;
        const ws = new WebSocket(`ws://localhost:${port}/ws`);
        let currentPeer = null;
        const chatData = {};
        const unreadCounts = {};

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
                updatePeers(data.peers);
            }
            else if(data.type === 'message') {
                const peerKey = data.from;
                if(!chatData[peerKey]) {
                    createChatSection(peerKey);
                    chatData[peerKey] = [];
                }
                addMessage(peerKey, data.text, data.seq_num, 'received');

                if(currentPeer !== peerKey) {
                    unreadCounts[peerKey] = (unreadCounts[peerKey] || 0) + 1;
                    updatePeerUnreadIndicator(peerKey);
                }
            }
            else if(data.type === 'message_sent') {
                const peerKey = data.to;
                if(!chatData[peerKey]) {
                    createChatSection(peerKey);
                    chatData[peerKey] = [];
                }
                addMessage(peerKey, data.text, data.seq_num, 'sent');
            }
            else if(data.type === 'file_started') {
                const peerKey = data.from;
                if(!chatData[peerKey]) {
                    createChatSection(peerKey);
                    chatData[peerKey] = [];
                }
                addFileNotification(peerKey, data.filename, data.chunks, data.seq_num);

                if(currentPeer !== peerKey) {
                    unreadCounts[peerKey] = (unreadCounts[peerKey] || 0) + 1;
                    updatePeerUnreadIndicator(peerKey);
                }
            }
            else if(data.type === 'file_complete') {
                const peerKey = data.from;
                addFileComplete(peerKey, data.filename, data.file_path, data.seq_num);

                if(currentPeer !== peerKey) {
                    unreadCounts[peerKey] = (unreadCounts[peerKey] || 0) + 1;
                    updatePeerUnreadIndicator(peerKey);
                }
            }
            else if(data.type === 'success' || data.type === 'error') {
                console.log(data.message);
            }
            else if(data.type === 'file_sent') {
                const peerKey = data.to;
                if(!chatData[peerKey]) {
                    chatData[peerKey] = [];
                    createChatSection(peerKey);
                }
                addFileSent(peerKey, data.filename, data.chunks, data.seq_num);
            }
        };
        
        function addFileSent(peerKey, filename, chunks, seq_num) {
            if(!chatData[peerKey]) {
                chatData[peerKey] = [];
            }
        
            chatData[peerKey].push({type: 'file_sent', filename, chunks, seq_num});
        
            const messagesDiv = document.getElementById(`messages-${peerKey}`);
            if(!messagesDiv) return;
        
            const fileDiv = document.createElement('div');
            fileDiv.className = 'file';
            fileDiv.style.marginLeft = 'auto';
            fileDiv.style.maxWidth = '80%';
            fileDiv.style.background = '#d4edda';
            fileDiv.style.borderLeft = '3px solid #28a745';
            fileDiv.innerHTML = `📤 Datei gesendet: <b>${escapeHtml(filename)}</b> (${chunks} Chunks) <i>(seq: ${seq_num})</i>`;
            messagesDiv.appendChild(fileDiv);
            scrollMessages(peerKey);
        }
        
        function updatePeers(peers) {
            const container = document.getElementById('peers-container');
            if(peers.length === 0) {
                container.innerHTML = '<i>Keine Peers gefunden</i>';
                return;
            }

            container.innerHTML = '';
            peers.forEach(p => {
                const peerKey = `${p.ip}:${p.port}`;
                const item = document.createElement('div');
                item.className = 'peer-item';
                if(currentPeer === peerKey) {
                    item.classList.add('active');
                }

                const unreadCount = unreadCounts[peerKey] || 0;
                if(unreadCount > 0 && currentPeer !== peerKey) {
                    item.classList.add('has-unread');
                }

                const unreadBadge = unreadCount > 0 ? `<span class="unread-count">${unreadCount}</span>` : '';

                item.innerHTML = `${p.ip}:${p.port}${unreadBadge}<span class="peer-distance">Hop ${p.distance}</span>`;
                item.onclick = () => selectPeer(peerKey);

                container.appendChild(item);

                if(!chatData[peerKey]) {
                    createChatSection(peerKey);
                    chatData[peerKey] = [];
                }
            });
        }

        function selectPeer(peerKey) {
            currentPeer = peerKey;

            unreadCounts[peerKey] = 0;

            document.querySelectorAll('.peer-item').forEach(item => {
                item.classList.remove('active');
                item.classList.remove('has-unread');
                const badge = item.querySelector('.unread-count');
                if(badge) badge.remove();
            });
            event.target.closest('.peer-item').classList.add('active');

            document.querySelectorAll('.chat-section').forEach(section => {
                section.classList.remove('active');
            });
            document.getElementById(`chat-${peerKey}`).classList.add('active');

            scrollMessages(peerKey);
        }

        function updatePeerUnreadIndicator(peerKey) {
            const container = document.getElementById('peers-container');
            const items = container.querySelectorAll('.peer-item');

            items.forEach(item => {
                const itemText = item.textContent;
                if(itemText.startsWith(peerKey)) {
                    const unreadCount = unreadCounts[peerKey] || 0;
                    if(unreadCount > 0 && currentPeer !== peerKey) {
                        item.classList.add('has-unread');
                        const existingBadge = item.querySelector('.unread-count');
                        if(existingBadge) {
                            existingBadge.textContent = unreadCount;
                        }
                    }
                }
            });
        }

        function createChatSection(peerKey) {
            const container = document.getElementById('chat-container');
            const [ip, port] = peerKey.split(':');

            const section = document.createElement('div');
            section.className = 'chat-section';
            section.id = `chat-${peerKey}`;
            if(currentPeer === peerKey) {
                section.classList.add('active');
            }

            section.innerHTML = `
                <div class="chat-header">Chat mit ${peerKey}</div>
                <div class="messages-area" id="messages-${peerKey}"></div>
                <div class="send-area">
                    <input type="text" id="msg-input-${peerKey}" placeholder="Nachricht eingeben..." 
                           onkeypress="if(event.key==='Enter') sendMessage('${ip}', ${port})">
                    <button onclick="sendMessage('${ip}', ${port})">Senden</button>
                    <button onclick="sendFile('${ip}', ${port})">Datei senden</button>
                </div>
            `;

            container.appendChild(section);
        }

        function addMessage(peerKey, text, seq_num, type) {
            if(!chatData[peerKey]) {
                chatData[peerKey] = [];
            }

            chatData[peerKey].push({type: 'message', direction: type, text, seq_num});

            const messagesDiv = document.getElementById(`messages-${peerKey}`);
            if(!messagesDiv) return;

            const msgDiv = document.createElement('div');
            msgDiv.className = `msg ${type}`;

            const timeStr = new Date().toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'});
            msgDiv.innerHTML = `
                <div class="msg-header">${timeStr} • seq: ${seq_num}</div>
                <div class="msg-text">${escapeHtml(text)}</div>
            `;

            messagesDiv.appendChild(msgDiv);
            scrollMessages(peerKey);
        }

        function addFileNotification(peerKey, filename, chunks, seq_num) {
            if(!chatData[peerKey]) {
                chatData[peerKey] = [];
            }

            chatData[peerKey].push({type: 'file_started', filename, chunks, seq_num});

            const messagesDiv = document.getElementById(`messages-${peerKey}`);
            if(!messagesDiv) return;

            const fileDiv = document.createElement('div');
            fileDiv.className = 'file';
            fileDiv.innerHTML = `📥 Empfange Datei: <b>${escapeHtml(filename)}</b> (${chunks} Chunks) <i>(seq: ${seq_num})</i>`;
            messagesDiv.appendChild(fileDiv);
            scrollMessages(peerKey);
        }

        function addFileComplete(peerKey, filename, file_path, seq_num) {
            const messagesDiv = document.getElementById(`messages-${peerKey}`);
            if(!messagesDiv) return;

            const fileDiv = document.createElement('div');
            fileDiv.className = 'file';
            fileDiv.innerHTML = `
                ✅ Datei empfangen: <b>${escapeHtml(filename)}</b> <i>(seq: ${seq_num})</i>
                <div class="file-path">
                    📁 ${escapeHtml(file_path)}
                    <button onclick="copyToClipboard('${file_path.replace(/'/g, "\\'")}')">📋 Kopieren</button>
                </div>
            `;
            messagesDiv.appendChild(fileDiv);
            scrollMessages(peerKey);
        }

        function sendMessage(ip, port) {
            const peerKey = `${ip}:${port}`;
            const input = document.getElementById(`msg-input-${peerKey}`);
            const message = input.value.trim();

            if(!message) {
                alert('Bitte eine Nachricht eingeben!');
                return;
            }

            ws.send(JSON.stringify({
                action: 'send_text',
                dest_ip: ip,
                dest_port: parseInt(port),
                message: message
            }));

            input.value = '';
        }

        function sendFile(ip, port) {
            const filePath = prompt('Dateipfad eingeben:');
            if(!filePath) return;

            ws.send(JSON.stringify({
                action: 'send_file',
                dest_ip: ip,
                dest_port: parseInt(port),
                file_path: filePath
            }));
        }

        function scrollMessages(peerKey) {
            const messagesDiv = document.getElementById(`messages-${peerKey}`);
            if(messagesDiv) {
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                alert('Pfad kopiert!');
            });
        }

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

        # Benachrichtige alle Clients über gesendete Nachricht
        manager.broadcast_sync({
            "type": "message_sent",
            "to": f"{dest_ip}:{dest_port}",
            "text": message,
            "seq_num": seq_num
        })

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

    # Hole alle Routen aus der Routing-Tabelle
    routes = manager.my_socket.routing_table.get_all_routes()

    peers = []
    for route in routes:
        peers.append({
            "ip": str(ipaddress.IPv4Address(route.dest_ip)),
            "port": route.dest_port,
            "distance": route.distance
        })

    # Sortiere nach Distance (direkte Nachbarn zuerst)
    peers.sort(key=lambda x: x["distance"])

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

# In der notify-Funktion am Ende der Datei ergänzen:
def notify_file_sent(file_info):
    manager.broadcast_sync({
        "type": "file_sent",
        "to": f"{file_info['dest_ip']}:{file_info['dest_port']}",
        "filename": file_info['filename'],
        "chunks": file_info['chunks'],
        "seq_num": file_info['seq_num']
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
