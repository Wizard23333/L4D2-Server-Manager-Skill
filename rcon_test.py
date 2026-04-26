import socket
import struct

def rcon_command(ip, port, password, command):
    def create_packet(id, type, body):
        return struct.pack('<ii', id, type) + body.encode('ascii') + b'\x00\x00'

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5.0)
            s.connect((ip, port))
            
            # Auth
            auth_packet = create_packet(1, 3, password)
            s.sendall(struct.pack('<i', len(auth_packet)) + auth_packet)
            # Read auth response and potentially the empty response that follows
            s.recv(4096)
            
            # Command
            cmd_packet = create_packet(2, 2, command)
            s.sendall(struct.pack('<i', len(cmd_packet)) + cmd_packet)
            
            # Add a second command to force a response if the first one doesn't
            term_packet = create_packet(3, 2, "echo END_OF_RCON")
            s.sendall(struct.pack('<i', len(term_packet)) + term_packet)
            
            data = b""
            while True:
                try:
                    chunk = s.recv(4096)
                    if not chunk: break
                    data += chunk
                    if b"END_OF_RCON" in data:
                        break
                except socket.timeout:
                    break
            return data.decode('ascii', errors='ignore')

if __name__ == "__main__":
    import sys
    import os
    cmd = sys.argv[1] if len(sys.argv) > 1 else "maps *"
    # 从环境变量获取密码，或者使用占位符
    rcon_pass = os.getenv("RCON_PASSWORD", "YOUR_RCON_PASSWORD_HERE")
    print(rcon_command("127.0.0.1", 27015, rcon_pass, cmd))
