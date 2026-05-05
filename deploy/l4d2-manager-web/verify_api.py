#!/usr/bin/env python3
import base64
import json
import urllib.request


env = {}
with open("/etc/l4d2-manager-web.env", encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value

token = base64.b64encode(
    f"{env['L4D2_WEB_USER']}:{env['L4D2_WEB_PASSWORD']}".encode("utf-8")
).decode("ascii")
request = urllib.request.Request(
    "http://127.0.0.1:8080/api/state",
    headers={"Authorization": f"Basic {token}"},
)
with urllib.request.urlopen(request, timeout=5) as response:
    data = json.loads(response.read().decode("utf-8"))

print(
    json.dumps(
        {
            "rooms": data["rooms"],
            "map_count": len(data["maps"]),
            "first_maps": data["maps"][:10],
        },
        ensure_ascii=False,
        indent=2,
    )
)
