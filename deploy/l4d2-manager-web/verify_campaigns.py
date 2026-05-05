#!/usr/bin/env python3
import base64
import json
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
request = urllib.request.Request(
    "http://127.0.0.1:8080/api/state",
    headers={"Authorization": f"Basic {token}"},
)
with urllib.request.urlopen(request, timeout=10) as response:
    data = json.loads(response.read().decode("utf-8"))

campaigns = data["campaigns"]
by_title = {campaign["title"]: campaign for campaign in campaigns}
all_campaign_maps = {
    item["name"]
    for campaign in campaigns
    for item in campaign["maps"]
}

gravitation = next(
    campaign for campaign in campaigns if any(item["name"] == "dxyl1" for item in campaign["maps"])
)
gravitation_maps = [item["name"] for item in gravitation["maps"]]
assert gravitation_maps == ["dxyl1", "dxyl2", "dxyl3", "dxyl4", "dxyl4_f"], gravitation_maps

dead_center = by_title["Dead Center"]
assert dead_center["maps"][0]["name"] == "c1m1_hotel", dead_center
assert "c5m1_waterfront_sndscape" not in all_campaign_maps

other = next(campaign for campaign in campaigns if campaign["id"] == "other")
other_maps = {item["name"] for item in other["maps"]}
assert {"test_box2", "zoo_jukebox", "styleguide_urban_01"} <= other_maps

tianti = next(
    campaign for campaign in campaigns if any(item["name"] == "hls_05" for item in campaign["maps"])
)
tianti_maps = [item["name"] for item in tianti["maps"]]
assert "hls_05" in tianti_maps, tianti

addons = {addon["filename"]: addon for addon in data["addons"]}
assert addons["gzzc7.3.vpk"]["kind"] == "map", addons["gzzc7.3.vpk"]
assert addons["tianti.vpk"]["kind"] == "map", addons["tianti.vpk"]
assert addons["left4bots2.vpk"]["kind"] == "mod", addons["left4bots2.vpk"]

room1 = next(room for room in data["rooms"] if room["id"] == "room1")
assert room1["default_map"] == "dxyl1", room1
assert room1["default_campaign_id"] == gravitation["id"], room1

print(
    json.dumps(
        {
            "campaign_count": len(campaigns),
            "gravitation_title": gravitation["title"],
            "gravitation_maps": gravitation_maps,
            "dead_center_maps": [item["name"] for item in dead_center["maps"]],
            "other_count": len(other["maps"]),
            "tianti_title": tianti["title"],
            "tianti_maps": tianti_maps,
            "map_packages": sorted(name for name, addon in addons.items() if addon["kind"] == "map"),
            "mods": sorted(name for name, addon in addons.items() if addon["kind"] == "mod"),
            "room1_default_campaign_id": room1["default_campaign_id"],
        },
        ensure_ascii=False,
        indent=2,
    )
)
