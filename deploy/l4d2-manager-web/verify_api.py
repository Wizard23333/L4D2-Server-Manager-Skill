#!/usr/bin/env python3
import base64
import http.cookiejar
import json
import urllib.parse
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

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
login_body = urllib.parse.urlencode(
    {"username": env["L4D2_WEB_USER"], "password": env["L4D2_WEB_PASSWORD"]}
).encode("utf-8")
login_request = urllib.request.Request(
    "http://127.0.0.1:8080/api/login",
    data=login_body,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
with opener.open(login_request, timeout=5) as response:
    if response.status != 200:
        raise SystemExit(f"session login failed: {response.status}")
session_request = urllib.request.Request("http://127.0.0.1:8080/api/state")
with opener.open(session_request, timeout=5) as response:
    session_data = json.loads(response.read().decode("utf-8"))
if "rooms" not in session_data:
    raise SystemExit("session state response missing rooms")

system = data.get("system", {})
required_sections = ["cpu", "memory", "swap", "disk", "uptime", "processes"]
missing = [name for name in required_sections if name not in system]
if missing:
    raise SystemExit(f"Missing system sections: {', '.join(missing)}")

for section_name in ["memory", "swap"]:
    section = system[section_name]
    for field_name in ["total", "used", "percent"]:
        if section.get(field_name) is not None and not isinstance(section[field_name], (int, float)):
            raise SystemExit(f"Invalid system.{section_name}.{field_name}")

if not isinstance(system["disk"], list) or not system["disk"]:
    raise SystemExit("system.disk must be a non-empty list")
if not isinstance(system["processes"], list) or not system["processes"]:
    raise SystemExit("system.processes must be a non-empty list")

print(
    json.dumps(
        {
            "rooms": data["rooms"],
            "system": {
                "cpu": system["cpu"],
                "memory": system["memory"],
                "swap": system["swap"],
                "disk": [
                    {
                        "label": item.get("label"),
                        "path": item.get("path"),
                        "percent": item.get("percent"),
                    }
                    for item in system["disk"]
                ],
                "processes": [
                    {
                        "service": item.get("service"),
                        "active": item.get("active"),
                        "memory_current": item.get("memory_current"),
                    }
                    for item in system["processes"]
                ],
            },
            "map_count": len(data["maps"]),
            "first_maps": data["maps"][:10],
        },
        ensure_ascii=False,
        indent=2,
    )
)
