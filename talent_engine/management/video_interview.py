# WebRTC Signaling Server
import logging
import uuid
import io
import json
import asyncio
import websockets
import threading

logger = logging.getLogger('job_applications')
connected_clients = {}

async def signaling_server(websocket, path):
    client_id = str(uuid.uuid4())
    connected_clients[client_id] = websocket
    try:
        async for message in websocket:
            data = json.loads(message)
            session_id = data.get('session_id')
            recipient_id = data.get('recipient_id')
            if recipient_id in connected_clients:
                await connected_clients[recipient_id].send(json.dumps(data))
            logger.info(f"Signaling message for session {session_id} from {client_id}")
    except Exception as e:
        logger.error(f"Signaling error: {e}")
    finally:
        del connected_clients[client_id]

def start_signaling_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = websockets.serve(signaling_server, "0.0.0.0", 8765)
    loop.run_until_complete(server)
    loop.run_forever()

# Start signaling server in a separate thread
threading.Thread(target=start_signaling_server, daemon=True).start()