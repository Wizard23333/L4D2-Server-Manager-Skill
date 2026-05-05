#!/usr/bin/env python3
import base64
import json
import urllib.error
import urllib.parse
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


def request(path, data=None, expect_error=False):
    body = None if data is None else urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:8080{path}",
        data=body,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
        if not expect_error:
            raise
        return exc.code, payload


status, state = request("/api/state")
print("state", status, len(state["rooms"]), len(state["maps"]), len(state["addons"]), len(state["jobs"]))

status, invalid_install = request(
    "/api/workshop/install",
    {"kind": "map", "workshop_id": "../bad"},
    expect_error=True,
)
print("invalid_install", status, invalid_install["message"])

status, search = request("/api/catalog/search?query=Run%20To%20The%20Hills&kind=map")
print("catalog_search", status, [(item["source"], item["id"]) for item in search["results"]])
assert any(item["source"] == "workshop" and item["id"] == "2232584588" for item in search["results"])
assert any(item["source"] == "gamemaps" and item["id"] == "2559" for item in search["results"])

status, invalid_search = request(
    "/api/catalog/search?query=..%2Fbad&kind=map",
    expect_error=True,
)
print("invalid_search", status, invalid_search["message"])

status, invalid_catalog_install = request(
    "/api/catalog/install",
    {"source": "gamemaps", "kind": "mod", "id": "2559"},
    expect_error=True,
)
print("invalid_catalog_install", status, invalid_catalog_install["message"])

status, invalid_addon = request(
    "/api/addon/state",
    {"filename": "../bad.vpk", "state": "disabled"},
    expect_error=True,
)
print("invalid_addon", status, invalid_addon["message"])
