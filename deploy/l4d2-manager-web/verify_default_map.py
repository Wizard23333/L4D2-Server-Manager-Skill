#!/usr/bin/env python3
import base64
import json
import urllib.parse
import urllib.error
import urllib.request


env = {}
with open("/etc/l4d2-manager-web.env", encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if line and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value

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
try:
    with urllib.request.urlopen(request, timeout=10) as response:
        print(response.status)
        print(json.dumps(json.loads(response.read().decode("utf-8")), ensure_ascii=False))
except urllib.error.HTTPError as exc:
    print(exc.code)
    print(exc.read().decode("utf-8", errors="replace"))
    raise SystemExit(1)
