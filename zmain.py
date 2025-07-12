import socket

host = 'smtp.gmail.com'
port = 587
try:
    sock = socket.create_connection((host, port), timeout=10)
    print("Connection to smtp.gmail.com:587 successful")
    sock.close()
except Exception as e:
    print(f"Failed to connect to {host}:{port}: {str(e)}")