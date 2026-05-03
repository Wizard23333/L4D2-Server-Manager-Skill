import socket
import struct

SERVERDATA_RESPONSE_VALUE = 0
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_AUTH = 3

def rcon_command(ip, port, password, command):
    def create_packet(request_id, packet_type, body):
        return struct.pack('<ii', request_id, packet_type) + body.encode('ascii') + b'\x00\x00'

    def read_exact(sock, size):
        chunks = []
        remaining = size
        while remaining > 0:
            chunk = sock.recv(remaining)
            if not chunk:
                raise ConnectionError("RCON connection closed while reading a packet")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b''.join(chunks)

    def read_packet(sock):
        packet_size = struct.unpack('<i', read_exact(sock, 4))[0]
        if packet_size < 10:
            raise ValueError(f"Invalid RCON packet size: {packet_size}")

        payload = read_exact(sock, packet_size)
        request_id, packet_type = struct.unpack('<ii', payload[:8])
        body = payload[8:-2]
        return request_id, packet_type, body

    def send_packet(sock, request_id, packet_type, body):
        packet = create_packet(request_id, packet_type, body)
        sock.sendall(struct.pack('<i', len(packet)) + packet)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5.0)
        s.connect((ip, port))

        auth_id = 1
        command_id = 2
        terminator_id = 3
        terminator = "END_OF_RCON"

        send_packet(s, auth_id, SERVERDATA_AUTH, password)

        while True:
            response_id, packet_type, _body = read_packet(s)
            if response_id == -1:
                raise PermissionError("RCON authentication failed")
            if response_id == auth_id and packet_type == SERVERDATA_EXECCOMMAND:
                break

        send_packet(s, command_id, SERVERDATA_EXECCOMMAND, command)
        send_packet(s, terminator_id, SERVERDATA_EXECCOMMAND, f"echo {terminator}")

        response_parts = []
        while True:
            try:
                response_id, packet_type, body = read_packet(s)
            except socket.timeout:
                break

            if response_id == command_id and packet_type == SERVERDATA_RESPONSE_VALUE:
                response_parts.append(body)
            elif response_id == terminator_id and terminator.encode('ascii') in body:
                break

        return b''.join(response_parts).decode('ascii', errors='ignore')

if __name__ == "__main__":
    import sys
    import os
    cmd = sys.argv[1] if len(sys.argv) > 1 else "maps *"
    # 从环境变量获取密码，或者使用占位符
    rcon_pass = os.getenv("RCON_PASSWORD", "YOUR_RCON_PASSWORD_HERE")
    print(rcon_command("127.0.0.1", 27015, rcon_pass, cmd))
