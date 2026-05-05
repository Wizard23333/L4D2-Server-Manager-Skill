#!/usr/bin/env python3
import base64
import json
import subprocess
import urllib.parse
import urllib.request


env = {}
with open("/etc/l4d2-manager-web.env", encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if line and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value


def start_time():
    return subprocess.check_output(
        ["/usr/bin/systemctl", "show", "l4d2", "-p", "ExecMainStartTimestamp", "--value"],
        text=True,
    ).strip()


token = base64.b64encode(
    f"{env['L4D2_WEB_USER']}:{env['L4D2_WEB_PASSWORD']}".encode("utf-8")
).decode("ascii")
body = urllib.parse.urlencode(
    {"room": "room1", "map": "dxyl1", "restart": "0"}
).encode("utf-8")
request = urllib.request.Request(
    "http://127.0.0.1:8080/api/default-map",
    data=body,
    headers={
        "Authorization": f"Basic {token}",
        "Content-Type": "application/x-www-form-urlencoded",
    },
)

before = start_time()
with urllib.request.urlopen(request, timeout=10) as response:
    payload = json.loads(response.read().decode("utf-8"))
after = start_time()

print(json.dumps({"status": response.status, "payload": payload, "before": before, "after": after}))
if before != after:
    raise SystemExit("Room 1 restarted unexpectedly")
