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

addons = state.get("addons", [])
campaigns = state.get("campaigns", [])
other_maps = set()
for campaign in campaigns:
    if campaign.get("id") == "other":
        other_maps.update(item["name"] for item in campaign.get("maps", []))

if any(addon["filename"].startswith("map_2459037122_") for addon in addons):
    glub4 = next((campaign for campaign in campaigns if campaign["title"] == "Glubtastic 4"), None)
    assert glub4, "Glubtastic 4 package is installed but not grouped as a campaign"
    glub4_maps = [item["name"] for item in glub4["maps"]]
    assert glub4_maps == [f"glubtastic4_{index}" for index in range(1, 8)], glub4_maps
    assert not set(glub4_maps) & other_maps, "Glubtastic 4 maps leaked into Other"
    print("glubtastic4_campaign", glub4_maps)

if any(addon["filename"].startswith("map_3366491323_") for addon in addons):
    glub5 = next((campaign for campaign in campaigns if campaign["title"] == "Glubtastic 5"), None)
    assert glub5, "Glubtastic 5 package is installed but not grouped as a campaign"
    glub5_maps = [item["name"] for item in glub5["maps"]]
    expected_glub5 = [f"glubtastic5_{index}" for index in range(1, 7)] + ["glubtastic5_bigtesco"]
    assert glub5_maps == expected_glub5, glub5_maps
    assert not set(glub5_maps) & other_maps, "Glubtastic 5 maps leaked into Other"
    print("glubtastic5_campaign", glub5_maps)

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

status, lingshan = request("/api/catalog/search?query=%E5%B9%BF%E8%A5%BF%E7%81%B5%E5%B1%B1&kind=map")
print("catalog_search_lingshan", status, [(item["source"], item["id"], item.get("install_ids", [])) for item in lingshan["results"]])
workshop_lingshan = next(item for item in lingshan["results"] if item["source"] == "workshop" and item["id"] == "3583374422")
assert workshop_lingshan["install_ids"] == ["3583374422", "3583375624", "3583381403", "3583382507"]

status, yama = request("/api/catalog/search?query=Yama&kind=map")
print("catalog_search_yama", status, [(item["source"], item["id"], item.get("install_ids", [])) for item in yama["results"]])
assert any(item["source"] == "workshop" and item["id"] == "767999000" for item in yama["results"])

status, zengcheng = request("/api/catalog/search?query=%E5%B9%BF%E5%B7%9E%E5%A2%9E%E5%9F%8E&kind=map")
print("catalog_search_zengcheng", status, [(item["source"], item["id"]) for item in zengcheng["results"]])
assert any(item["source"] == "workshop" and item["id"] == "2396847377" for item in zengcheng["results"])

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

status, invalid_delete = request(
    "/api/map-package/delete",
    {"filename": "../bad.vpk", "mode": "soft"},
    expect_error=True,
)
print("invalid_delete", status, invalid_delete["message"])

status, invalid_delete_mode = request(
    "/api/map-package/delete",
    {"filename": "missing.vpk", "mode": "explode"},
    expect_error=True,
)
print("invalid_delete_mode", status, invalid_delete_mode["message"])
