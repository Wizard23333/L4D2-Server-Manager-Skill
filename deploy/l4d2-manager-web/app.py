#!/usr/bin/env python3
import base64
import html
import json
import os
import re
import struct
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOMS = {
    "room1": {
        "label": "Room 1",
        "service": "l4d2",
        "port": 27015,
        "script": Path("/opt/l4d2/start_l4d2.sh"),
    },
    "room2": {
        "label": "Room 2",
        "service": "l4d2_2",
        "port": 27016,
        "script": Path("/opt/l4d2/start_l4d2_2.sh"),
    },
}

MAPS_DIR = Path("/opt/l4d2/left4dead2/maps")
MISSIONS_DIR = Path("/opt/l4d2/left4dead2/missions")
ADDONS_DIR = Path("/opt/l4d2/left4dead2/addons")
DISABLED_ADDONS_DIR = Path("/opt/l4d2/left4dead2/addons_disabled")
JOBS_DIR = Path(os.environ.get("L4D2_WEB_JOBS_DIR", "/var/lib/l4d2-manager-web/jobs"))
PACKAGES_FILE = Path(os.environ.get("L4D2_WEB_PACKAGES_FILE", "/var/lib/l4d2-manager-web/packages.json"))
ADMIN_USER = os.environ.get("L4D2_WEB_USER", "admin")
ADMIN_PASSWORD = os.environ.get("L4D2_WEB_PASSWORD", "")
STEAM_WEB_API_KEY = os.environ.get("STEAM_WEB_API_KEY", "")
AUTH_REALM = "L4D2 Manager"
WORKSHOP_ID_RE = re.compile(r"^[0-9]{4,20}$")
ADDON_RE = re.compile(r"^[A-Za-z0-9_. -]{1,180}\.vpk$")
CATALOG_FORBIDDEN_CHARS = set('/\\<>[]{}$;|`')
JOBS = {}
JOBS_LOCK = threading.Lock()
EXCLUDED_CAMPAIGN_MAPS = {"c5m1_waterfront_sndscape"}
STEAM_DETAILS_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
STEAM_QUERY_URL = "https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/"
STEAM_BROWSE_URL = "https://steamcommunity.com/workshop/browse/"
STEAM_WORKSHOP_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id={id}"
GAMEMAPS_DETAILS_URL = "https://www.gamemaps.com/details/{id}"

KNOWN_CATALOG_ITEMS = [
    {
        "source": "workshop",
        "id": "2232584588",
        "title": "Run to the Hills (L4D2)",
        "kind": "map",
        "url": STEAM_WORKSHOP_URL.format(id="2232584588"),
        "size": "317.9 MB",
        "summary": "5-map campaign. Steam API currently returns a downloadable VPK.",
        "installable": True,
        "reason": "",
        "aliases": ["run to the hills", "runtothehills", "run hills"],
    },
    {
        "source": "gamemaps",
        "id": "2559",
        "title": "Run To The Hills",
        "kind": "map",
        "url": GAMEMAPS_DETAILS_URL.format(id="2559"),
        "size": "131.3 MB",
        "summary": "5-map GameMaps campaign package: runtothehills.vpk.",
        "installable": True,
        "reason": "",
        "aliases": ["run to the hills", "runtothehills", "run hills"],
    },
    {
        "source": "workshop",
        "id": "3583374422",
        "install_ids": ["3583374422", "3583375624", "3583381403", "3583382507"],
        "title": "广西灵山 V2.9 / Lingshan-Guangxi V2.9",
        "kind": "map",
        "url": STEAM_WORKSHOP_URL.format(id="3583374422"),
        "size": "4 packages",
        "summary": "Multi-part campaign package. Installs the main Workshop item plus Pack-2, Pack-3, and Pack-4.",
        "installable": True,
        "reason": "",
        "aliases": ["广西灵山", "灵山", "lingshan", "guangxi lingshan", "lingshan-guangxi"],
    },
    {
        "source": "gamemaps",
        "id": "34721",
        "title": "Lingshan-Guangxi / 广西灵山",
        "kind": "map",
        "url": GAMEMAPS_DETAILS_URL.format(id="34721"),
        "size": "",
        "summary": "GameMaps mirror. Steam Workshop is preferred for this multi-part campaign.",
        "installable": True,
        "reason": "",
        "aliases": ["广西灵山", "灵山", "lingshan", "guangxi lingshan", "lingshan-guangxi"],
    },
    {
        "source": "workshop",
        "id": "767999000",
        "install_ids": ["767999000", "170360252", "169801737", "1127584577"],
        "title": "Yama",
        "kind": "map",
        "url": STEAM_WORKSHOP_URL.format(id="767999000"),
        "size": "4 packages",
        "summary": "Multi-part campaign package: Yama part 1, part 2, part 3, and Yama Finale fix.",
        "installable": True,
        "reason": "",
        "aliases": ["yama", "l4d_yama", "yama japan"],
    },
    {
        "source": "workshop",
        "id": "2396847377",
        "title": "广州增城 （Zengcheng）Lv7.3",
        "kind": "map",
        "url": STEAM_WORKSHOP_URL.format(id="2396847377"),
        "size": "",
        "summary": "5-map Guangzhou Zengcheng campaign.",
        "installable": True,
        "reason": "",
        "aliases": ["广州增城", "增城", "zengcheng", "guangzhou zengcheng", "gzzc"],
    },
    {
        "source": "workshop",
        "id": "3526529688",
        "title": "地心引力 / The Gravitation",
        "kind": "map",
        "url": STEAM_WORKSHOP_URL.format(id="3526529688"),
        "size": "411.3 MB",
        "summary": "Campaign package. The author notes that servers only need to upload part 1.",
        "installable": True,
        "reason": "",
        "aliases": ["地心引力", "the gravitation", "gravitation", "dxyl"],
    },
    {
        "source": "workshop",
        "id": "2459037122",
        "title": "Glubtastic 4",
        "kind": "map",
        "url": STEAM_WORKSHOP_URL.format(id="2459037122"),
        "size": "",
        "summary": "Installed map package candidate.",
        "installable": True,
        "reason": "",
        "aliases": ["glubtastic", "glubtastic 4"],
    },
    {
        "source": "workshop",
        "id": "3366491323",
        "title": "Glubtastic 5",
        "kind": "map",
        "url": STEAM_WORKSHOP_URL.format(id="3366491323"),
        "size": "",
        "summary": "Installed map package candidate.",
        "installable": True,
        "reason": "",
        "aliases": ["glubtastic", "glubtastic 5"],
    },
]

OFFICIAL_CAMPAIGNS = [
    {
        "id": "official_dead_center",
        "title": "Dead Center",
        "source": "official",
        "maps": [
            {"name": "c1m1_hotel", "display_name": "Hotel", "chapter": 1},
            {"name": "c1m2_streets", "display_name": "Streets", "chapter": 2},
            {"name": "c1m3_mall", "display_name": "Mall", "chapter": 3},
            {"name": "c1m4_atrium", "display_name": "Atrium", "chapter": 4},
        ],
    },
    {
        "id": "official_dark_carnival",
        "title": "Dark Carnival",
        "source": "official",
        "maps": [
            {"name": "c2m1_highway", "display_name": "Highway", "chapter": 1},
            {"name": "c2m2_fairgrounds", "display_name": "Fairgrounds", "chapter": 2},
            {"name": "c2m3_coaster", "display_name": "Coaster", "chapter": 3},
            {"name": "c2m4_barns", "display_name": "Barns", "chapter": 4},
            {"name": "c2m5_concert", "display_name": "Concert", "chapter": 5},
        ],
    },
    {
        "id": "official_swamp_fever",
        "title": "Swamp Fever",
        "source": "official",
        "maps": [
            {"name": "c3m1_plankcountry", "display_name": "Plank Country", "chapter": 1},
            {"name": "c3m2_swamp", "display_name": "Swamp", "chapter": 2},
            {"name": "c3m3_shantytown", "display_name": "Shantytown", "chapter": 3},
            {"name": "c3m4_plantation", "display_name": "Plantation", "chapter": 4},
        ],
    },
    {
        "id": "official_hard_rain",
        "title": "Hard Rain",
        "source": "official",
        "maps": [
            {"name": "c4m1_milltown_a", "display_name": "Milltown", "chapter": 1},
            {"name": "c4m2_sugarmill_a", "display_name": "Sugar Mill", "chapter": 2},
            {"name": "c4m3_sugarmill_b", "display_name": "Mill Escape", "chapter": 3},
            {"name": "c4m4_milltown_b", "display_name": "Return to Town", "chapter": 4},
            {"name": "c4m5_milltown_escape", "display_name": "Town Escape", "chapter": 5},
        ],
    },
    {
        "id": "official_the_parish",
        "title": "The Parish",
        "source": "official",
        "maps": [
            {"name": "c5m1_waterfront", "display_name": "Waterfront", "chapter": 1},
            {"name": "c5m2_park", "display_name": "Park", "chapter": 2},
            {"name": "c5m3_cemetery", "display_name": "Cemetery", "chapter": 3},
            {"name": "c5m4_quarter", "display_name": "Quarter", "chapter": 4},
            {"name": "c5m5_bridge", "display_name": "Bridge", "chapter": 5},
        ],
    },
]


def run_cmd(args, timeout=8):
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": result.returncode == 0,
            "code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "code": -1, "stdout": "", "stderr": str(exc)}


def parse_systemctl_show(text):
    data = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key] = value
    return data


def default_map(script):
    try:
        text = script.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r"(?:^|\s)\+map\s+(\S+)", text)
    return match.group(1) if match else None


def list_maps():
    try:
        return sorted(path.stem for path in MAPS_DIR.glob("*.bsp"))
    except OSError:
        return []


def list_vpk_files():
    files = []
    for state, root in (("enabled", ADDONS_DIR), ("disabled", DISABLED_ADDONS_DIR)):
        try:
            paths = sorted(root.glob("*.vpk"))
        except OSError:
            paths = []
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            files.append({"path": path, "filename": path.name, "state": state, "size": stat.st_size})
    return files


def read_vpk_entries(vpk_path):
    entries = {}
    try:
        with open(vpk_path, "rb") as handle:
            header = handle.read(8)
            if len(header) != 8:
                return entries
            signature, version = struct.unpack("<II", header)
            if signature != 0x55AA1234:
                return entries
            tree_size_data = handle.read(4)
            if len(tree_size_data) != 4:
                return entries
            tree_size = struct.unpack("<I", tree_size_data)[0]
            if version == 2:
                handle.read(16)
            header_size = 12 if version == 1 else 28
            data_start = header_size + tree_size
            handle.seek(header_size)
            while True:
                extension = read_null_string(handle)
                if not extension:
                    break
                while True:
                    path = read_null_string(handle)
                    if not path:
                        break
                    while True:
                        filename = read_null_string(handle)
                        if not filename:
                            break
                        entry_data = handle.read(18)
                        if len(entry_data) != 18:
                            return entries
                        _crc, preload_bytes, archive_index, entry_offset, entry_size, _term = struct.unpack("<IHHIIH", entry_data)
                        preload = handle.read(preload_bytes)
                        path_name = "" if path in (" ", ".") else path
                        entry_name = f"{path_name}/{filename}.{extension}" if path_name else f"{filename}.{extension}"
                        entries[entry_name.replace("\\", "/").lower()] = {
                            "archive_index": archive_index,
                            "entry_offset": entry_offset,
                            "entry_size": entry_size,
                            "preload": preload,
                            "data_start": data_start,
                            "vpk_path": vpk_path,
                        }
    except OSError:
        return {}
    return entries


def read_null_string(handle):
    data = []
    while True:
        char = handle.read(1)
        if not char or char == b"\x00":
            break
        data.append(char)
    return b"".join(data).decode("utf-8", errors="ignore")


def read_vpk_entry(entry):
    if entry["archive_index"] != 0x7FFF:
        return None
    try:
        with open(entry["vpk_path"], "rb") as handle:
            handle.seek(entry["data_start"] + entry["entry_offset"])
            return entry["preload"] + handle.read(entry["entry_size"])
    except OSError:
        return None


def vpk_inventory():
    inventory = []
    for item in list_vpk_files():
        entries = read_vpk_entries(item["path"])
        maps = sorted(
            Path(name).stem.lower().replace(" ", "_")
            for name in entries
            if name.startswith("maps/") and name.endswith(".bsp")
        )
        missions = {
            Path(name).stem: entry
            for name, entry in entries.items()
            if name.startswith("missions/") and name.endswith(".txt")
        }
        content_text = "\n".join(entries.keys()).lower()
        is_map_package = bool(maps or missions) or "addoninfo.txt" in entries and (
            "addoncontent_campaign" in content_text or "addoncontent_map" in content_text
        )
        item.update({"maps": maps, "missions": missions, "is_map_package": is_map_package})
        inventory.append(item)
    return inventory


def available_maps():
    maps = set(list_maps())
    for item in vpk_inventory():
        if item["state"] == "enabled":
            maps.update(item["maps"])
            for entry in item["missions"].values():
                mission_data = read_vpk_entry(entry)
                if not mission_data:
                    continue
                try:
                    parsed = parse_keyvalues(mission_data.decode("utf-8", errors="replace"))
                except Exception:
                    continue
                mission = mission_root(parsed) or {}
                modes = dict_get_ci(mission, "modes") if isinstance(mission, dict) else {}
                coop = dict_get_ci(modes, "coop") if isinstance(modes, dict) else {}
                if not isinstance(coop, dict):
                    continue
                for chapter in coop.values():
                    map_name = dict_get_ci(chapter, "Map") if isinstance(chapter, dict) else None
                    if map_name:
                        maps.add(str(map_name).lower().replace(" ", "_"))
    return sorted(maps)


def strip_keyvalues_comments(text):
    cleaned = []
    for line in text.splitlines():
        in_quote = False
        escaped = False
        result = []
        index = 0
        while index < len(line):
            char = line[index]
            if char == "\\" and in_quote and not escaped:
                escaped = True
                result.append(char)
                index += 1
                continue
            if char == '"' and not escaped:
                in_quote = not in_quote
            escaped = False
            if not in_quote and line[index:index + 2] == "//":
                break
            result.append(char)
            index += 1
        cleaned.append("".join(result))
    return "\n".join(cleaned)


def keyvalues_tokens(text):
    pattern = re.compile(r'"([^"]*)"|([{}])')
    for match in pattern.finditer(strip_keyvalues_comments(text)):
        yield match.group(1) if match.group(1) is not None else match.group(2)


def parse_keyvalues(text):
    tokens = list(keyvalues_tokens(text))
    index = 0

    def parse_object():
        nonlocal index
        data = {}
        while index < len(tokens):
            token = tokens[index]
            index += 1
            if token == "}":
                break
            if token == "{":
                continue
            if index < len(tokens) and tokens[index] == "{":
                index += 1
                data[token] = parse_object()
            elif index < len(tokens):
                data[token] = tokens[index]
                index += 1
        return data

    parsed = {}
    while index < len(tokens):
        key = tokens[index]
        index += 1
        if index < len(tokens) and tokens[index] == "{":
            index += 1
            parsed[key] = parse_object()
        elif index < len(tokens):
            parsed[key] = tokens[index]
            index += 1
    return parsed


def campaign_id(title, fallback):
    value = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return value or fallback


def natural_map_key(value):
    parts = re.split(r"(\d+)", value)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def dict_get_ci(data, key):
    if not isinstance(data, dict):
        return None
    key_lower = key.lower()
    for item_key, value in data.items():
        if isinstance(item_key, str) and item_key.lower() == key_lower:
            return value
    return None


def mission_root(parsed):
    mission = dict_get_ci(parsed, "mission")
    if isinstance(mission, dict):
        return mission
    if not isinstance(parsed, dict):
        return None
    for value in parsed.values():
        if not isinstance(value, dict):
            continue
        modes = dict_get_ci(value, "modes")
        coop = dict_get_ci(modes, "coop") if isinstance(modes, dict) else None
        if isinstance(coop, dict):
            return value
    return None


def campaign_from_mission_text(text, fallback, installed_maps):
    try:
        parsed = parse_keyvalues(text)
    except Exception:
        return None
    mission = mission_root(parsed)
    if not isinstance(mission, dict):
        return None
    modes = dict_get_ci(mission, "modes")
    coop = dict_get_ci(modes, "coop") if isinstance(modes, dict) else None
    if not isinstance(coop, dict):
        return None
    title = dict_get_ci(mission, "DisplayTitle") or dict_get_ci(mission, "Name") or fallback
    installed_by_lower = {name.lower(): name for name in installed_maps}
    maps = []
    for chapter_key in sorted(coop, key=lambda value: int(value) if value.isdigit() else 9999):
        entry = coop[chapter_key]
        if not isinstance(entry, dict):
            continue
        map_name = dict_get_ci(entry, "Map")
        if not map_name:
            continue
        canonical_map_name = installed_by_lower.get(str(map_name).lower())
        if not canonical_map_name:
            continue
        display_name = str(dict_get_ci(entry, "DisplayName") or "").strip() or canonical_map_name
        maps.append(
            {
                "name": canonical_map_name,
                "display_name": display_name,
                "chapter": int(chapter_key) if chapter_key.isdigit() else len(maps) + 1,
            }
        )
    if not maps:
        return None
    return {
        "id": f"mission_{campaign_id(title, fallback)}",
        "title": title,
        "source": "mission",
        "maps": maps,
    }


def fallback_campaign_from_vpk(item):
    maps = sorted(set(item.get("maps", [])), key=natural_map_key)
    if len(maps) < 2:
        return None
    package = read_package_registry().get(item["filename"], {})
    title = package.get("title") or Path(item["filename"]).stem
    title = re.sub(r"^(map|mod)_\d+_", "", title).replace("_", " ").strip() or Path(item["filename"]).stem
    return {
        "id": f"vpk_{campaign_id(title, Path(item['filename']).stem)}",
        "title": title,
        "source": "vpk",
        "maps": [
            {"name": name, "display_name": name, "chapter": index + 1}
            for index, name in enumerate(maps)
        ],
    }


def parse_mission_campaigns(installed_maps):
    campaigns = []
    try:
        mission_files = sorted(MISSIONS_DIR.glob("*.txt"))
    except OSError:
        mission_files = []
    for mission_file in mission_files:
        try:
            campaign = campaign_from_mission_text(
                mission_file.read_text(encoding="utf-8", errors="replace"),
                mission_file.stem,
                installed_maps,
            )
        except OSError:
            continue
        if campaign:
            campaigns.append(campaign)
    for item in vpk_inventory():
        if item["state"] != "enabled":
            continue
        found_campaign = False
        for fallback, entry in item["missions"].items():
            data = read_vpk_entry(entry)
            if not data:
                continue
            campaign = campaign_from_mission_text(
                data.decode("utf-8", errors="replace"),
                fallback,
                installed_maps,
            )
            if campaign:
                campaign["source"] = "vpk"
                campaigns.append(campaign)
                found_campaign = True
        if not found_campaign:
            campaign = fallback_campaign_from_vpk(item)
            if campaign:
                campaigns.append(campaign)
    return campaigns


def build_campaigns():
    installed_maps = set(available_maps()) - EXCLUDED_CAMPAIGN_MAPS
    campaigns = []
    assigned = set()
    assigned_lower = set()
    for campaign in OFFICIAL_CAMPAIGNS:
        maps = [dict(item) for item in campaign["maps"] if item["name"] in installed_maps]
        if maps:
            copy = dict(campaign)
            copy["maps"] = maps
            campaigns.append(copy)
            assigned.update(item["name"] for item in maps)
            assigned_lower.update(item["name"].lower() for item in maps)
    for campaign in parse_mission_campaigns(installed_maps):
        maps = [item for item in campaign["maps"] if item["name"].lower() not in assigned_lower]
        if maps:
            copy = dict(campaign)
            copy["maps"] = maps
            campaigns.append(copy)
            assigned.update(item["name"] for item in maps)
            assigned_lower.update(item["name"].lower() for item in maps)
    other_maps = [
        {"name": name, "display_name": name, "chapter": index + 1}
        for index, name in enumerate(sorted(name for name in installed_maps - assigned if name.lower() not in assigned_lower))
    ]
    if other_maps:
        campaigns.append(
            {
                "id": "other",
                "title": "Other / 未分组地图",
                "source": "other",
                "maps": other_maps,
            }
        )
    return campaigns


def find_campaign_for_map(map_name, campaigns=None):
    campaigns = campaigns if campaigns is not None else build_campaigns()
    for campaign in campaigns:
        if any(item["name"] == map_name for item in campaign["maps"]):
            return campaign["id"]
    return None


def list_addons():
    addons = []
    inventory = vpk_inventory()
    packages = sync_package_registry(inventory)
    seen_packages = set()
    for item in inventory:
        try:
            modified_at = int(item["path"].stat().st_mtime)
        except OSError:
            modified_at = 0
        package = packages.get(item["filename"], {})
        if item["is_map_package"]:
            seen_packages.add(item["filename"])
        addons.append(
            {
                "filename": item["filename"],
                "state": item["state"],
                "size": item["size"],
                "modified_at": modified_at,
                "kind": "map" if item["is_map_package"] else "mod",
                "maps": item["maps"],
                "missions": sorted(item["missions"].keys()),
                "source": package.get("source", ""),
                "catalog_id": package.get("id", ""),
                "title": package.get("title", item["filename"]),
                "url": package.get("url", ""),
                "install_ids": package.get("install_ids", []),
                "package_status": package.get("status", "installed") if item["is_map_package"] else "",
                "reinstallable": bool(package.get("source") and package.get("id")) if item["is_map_package"] else False,
            }
        )
    for filename, package in packages.items():
        if filename in seen_packages or package.get("status") != "deleted":
            continue
        addons.append(
            {
                "filename": filename,
                "state": "deleted",
                "size": 0,
                "modified_at": package.get("deleted_at", 0),
                "kind": "map",
                "maps": package.get("maps", []),
                "missions": package.get("missions", []),
                "source": package.get("source", ""),
                "catalog_id": package.get("id", ""),
                "title": package.get("title", filename),
                "url": package.get("url", ""),
                "install_ids": package.get("install_ids", []),
                "package_status": "deleted",
                "reinstallable": bool(package.get("source") and package.get("id")),
            }
        )
    return addons


def room_status(room, campaigns=None):
    info = ROOMS[room]
    result = run_cmd(
        [
            "/usr/bin/systemctl",
            "show",
            info["service"],
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "NRestarts",
            "-p",
            "ExecMainStatus",
            "-p",
            "ExecMainStartTimestamp",
            "--no-pager",
        ]
    )
    fields = parse_systemctl_show(result["stdout"]) if result["ok"] else {}
    port_result = run_cmd(["/usr/bin/ss", "-H", "-lun", f"sport = :{info['port']}"])
    current_map = default_map(info["script"])
    return {
        "id": room,
        "label": info["label"],
        "service": info["service"],
        "port": info["port"],
        "active": fields.get("ActiveState", "unknown"),
        "sub_state": fields.get("SubState", "unknown"),
        "restarts": fields.get("NRestarts", "unknown"),
        "exit_status": fields.get("ExecMainStatus", "unknown"),
        "started_at": fields.get("ExecMainStartTimestamp", ""),
        "default_map": current_map,
        "default_campaign_id": find_campaign_for_map(current_map, campaigns),
        "port_listening": port_result["ok"] and bool(port_result["stdout"]),
    }


def snapshot():
    campaigns = build_campaigns()
    return {
        "generated_at": int(time.time()),
        "rooms": [room_status(room, campaigns) for room in ROOMS],
        "maps": available_maps(),
        "campaigns": campaigns,
        "addons": list_addons(),
        "jobs": list_jobs(),
    }


def restart_room(room):
    if room not in ROOMS:
        return {"ok": False, "message": "Unknown room"}
    service = ROOMS[room]["service"]
    result = run_cmd(["/usr/bin/sudo", "-n", "/usr/bin/systemctl", "restart", service], timeout=20)
    if result["ok"]:
        return {"ok": True, "message": f"Restarted {service}"}
    return {"ok": False, "message": result["stderr"] or result["stdout"] or "Restart failed"}


def set_default_map(room, map_name, restart=False):
    if room not in ROOMS:
        return {"ok": False, "message": "Unknown room"}
    if map_name not in available_maps():
        return {"ok": False, "message": "Map is not installed"}
    result = run_cmd(
        ["/usr/bin/sudo", "-n", "/usr/local/bin/l4d2-webctl", "set-default-map", room, map_name],
        timeout=10,
    )
    if not result["ok"]:
        return {"ok": False, "message": result["stderr"] or result["stdout"] or "Map update failed"}
    if restart:
        restart_result = restart_room(room)
        if not restart_result["ok"]:
            return {
                "ok": False,
                "message": f"Default map saved, but restart failed: {restart_result['message']}",
            }
        return {"ok": True, "message": f"Default map saved and {ROOMS[room]['service']} restarted"}
    return {"ok": True, "message": "Default map saved"}


def list_jobs():
    load_persisted_jobs()
    with JOBS_LOCK:
        return sorted(JOBS.values(), key=lambda job: job["created_at"], reverse=True)[:20]


def update_job(job_id, **fields):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job.update(fields)
        persist_job(job)


def ensure_jobs_dir():
    try:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def job_path(job_id):
    return JOBS_DIR / f"{job_id}.json"


def persist_job(job):
    ensure_jobs_dir()
    try:
        tmp = JOBS_DIR / f".{job['id']}.{uuid.uuid4().hex}.tmp"
        tmp.write_text(json.dumps(job, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(job_path(job["id"]))
    except OSError:
        pass


def read_job_file(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("id"):
        return None
    return data


def load_persisted_jobs():
    ensure_jobs_dir()
    try:
        paths = sorted(JOBS_DIR.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:50]
    except OSError:
        paths = []
    loaded = {}
    for path in paths:
        job = read_job_file(path)
        if job:
            loaded[job["id"]] = job
    with JOBS_LOCK:
        for job_id, job in loaded.items():
            JOBS.setdefault(job_id, job)


def recover_interrupted_jobs():
    load_persisted_jobs()
    with JOBS_LOCK:
        interrupted = [
            job for job in JOBS.values()
            if job.get("status") in {"queued", "running"}
        ]
    for job in interrupted:
        update_job(
            job["id"],
            status="interrupted",
            stage="interrupted",
            message="Install was interrupted while the Web service was offline. Re-run the install if it did not finish.",
            finished_at=int(time.time()),
        )


def read_package_registry():
    try:
        data = json.loads(PACKAGES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    packages = data.get("packages", {})
    return packages if isinstance(packages, dict) else {}


def write_package_registry(packages):
    try:
        PACKAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PACKAGES_FILE.with_name(f".{PACKAGES_FILE.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps({"packages": packages}, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(PACKAGES_FILE)
    except OSError:
        pass


def infer_package_source(filename):
    match = re.match(r"map_(\d{4,20})_", filename)
    if match:
        item_id = match.group(1)
        return {
            "source": "workshop",
            "id": item_id,
            "url": STEAM_WORKSHOP_URL.format(id=item_id),
            "install_ids": known_install_ids("workshop", "map", item_id) or [item_id],
        }
    match = re.match(r"map_gamemaps_(\d{1,12})_", filename)
    if match:
        item_id = match.group(1)
        return {
            "source": "gamemaps",
            "id": item_id,
            "url": GAMEMAPS_DETAILS_URL.format(id=item_id),
            "install_ids": [item_id],
        }
    for item in KNOWN_CATALOG_ITEMS:
        if item["kind"] != "map":
            continue
        title = normalize_catalog_query(item.get("title", ""))
        stem = normalize_catalog_query(Path(filename).stem)
        aliases = [normalize_catalog_query(alias) for alias in item.get("aliases", [])]
        if title and title in stem or any(alias and alias in stem for alias in aliases):
            return {
                "source": item["source"],
                "id": item["id"],
                "url": item["url"],
                "install_ids": item.get("install_ids") or [item["id"]],
            }
    return {"source": "", "id": "", "url": "", "install_ids": []}


def package_record_from_addon(addon, source_data=None):
    source_data = source_data or infer_package_source(addon["filename"])
    return {
        "filename": addon["filename"],
        "source": source_data.get("source", ""),
        "id": str(source_data.get("id", "")),
        "title": addon.get("title") or addon["filename"],
        "url": source_data.get("url", ""),
        "install_ids": [str(value) for value in source_data.get("install_ids", [])],
        "maps": addon.get("maps", []),
        "missions": sorted(addon.get("missions", {}).keys()) if isinstance(addon.get("missions"), dict) else addon.get("missions", []),
        "installed_at": int(time.time()),
        "status": "installed",
    }


def sync_package_registry(addons=None):
    packages = read_package_registry()
    addons = addons if addons is not None else vpk_inventory()
    changed = False
    for addon in addons:
        if not addon.get("is_map_package"):
            continue
        record = packages.get(addon["filename"]) or package_record_from_addon(addon)
        source_data = infer_package_source(addon["filename"])
        record.update({
            "filename": addon["filename"],
            "status": "installed",
            "maps": addon.get("maps", []),
            "missions": sorted(addon.get("missions", {}).keys()),
        })
        for key in ("source", "id", "url", "install_ids"):
            if not record.get(key) and source_data.get(key):
                record[key] = source_data[key]
        packages[addon["filename"]] = record
        changed = True
    if changed:
        write_package_registry(packages)
    return packages


def register_installed_package(filename, source, kind, item_id, title, url, install_ids):
    if kind != "map" or not ADDON_RE.match(filename):
        return
    addons = vpk_inventory()
    addon = next((item for item in addons if item["filename"] == filename), None)
    if not addon:
        return
    packages = sync_package_registry(addons)
    packages[filename] = package_record_from_addon(
        addon,
        {
            "source": source,
            "id": item_id,
            "url": url or (STEAM_WORKSHOP_URL.format(id=item_id) if source == "workshop" else GAMEMAPS_DETAILS_URL.format(id=item_id)),
            "install_ids": install_ids or [item_id],
        },
    )
    packages[filename]["title"] = title or packages[filename]["title"]
    write_package_registry(packages)


def http_json(url, data=None, timeout=12):
    body = None
    method = "GET"
    headers = {"User-Agent": "L4D2Manager/0.1"}
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def format_bytes(value):
    try:
        size = int(value)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return ""


def catalog_item(source, item_id, title, kind, url, size="", summary="", installable=True, reason="", install_ids=None):
    return {
        "source": source,
        "id": str(item_id),
        "title": title or str(item_id),
        "kind": kind,
        "url": url,
        "size": size,
        "summary": summary,
        "installable": bool(installable),
        "reason": reason,
        "install_ids": [str(value) for value in (install_ids or [])],
    }


def known_catalog_results(query, kind):
    normalized = normalize_catalog_query(query)
    results = []
    for item in KNOWN_CATALOG_ITEMS:
        if item["kind"] != kind:
            continue
        haystack = normalize_catalog_query(" ".join([item["title"], *item.get("aliases", [])]))
        aliases = [normalize_catalog_query(alias) for alias in item.get("aliases", [])]
        ids = {str(item["id"]), *[str(value) for value in item.get("install_ids", [])]}
        if normalized in ids or normalized in haystack or any(alias and alias in normalized for alias in aliases):
            results.append(catalog_item(
                item["source"],
                item["id"],
                item["title"],
                item["kind"],
                item["url"],
                item["size"],
                item["summary"],
                item["installable"],
                item["reason"],
                item.get("install_ids"),
            ))
    return results


def known_catalog_by_id(source, item_id, kind):
    for item in KNOWN_CATALOG_ITEMS:
        ids = {str(item["id"]), *[str(value) for value in item.get("install_ids", [])]}
        if item["kind"] == kind and item["source"] == source and str(item_id) in ids:
            return item
    return None


def enrich_catalog_result(item):
    known = known_catalog_by_id(item["source"], item["id"], item["kind"])
    if not known:
        return item
    enriched = dict(item)
    enriched["title"] = enriched.get("title") or known["title"]
    enriched["url"] = enriched.get("url") or known["url"]
    enriched["summary"] = known.get("summary") or enriched.get("summary", "")
    enriched["size"] = enriched.get("size") or known.get("size", "")
    enriched["install_ids"] = [str(value) for value in known.get("install_ids", [])]
    if known.get("reason"):
        enriched["reason"] = known["reason"]
    return enriched


def normalize_catalog_query(value):
    return re.sub(r"\s+", " ", value.casefold()).strip()


def catalog_query_error(query):
    if len(query) < 3:
        return "Search query must be at least 3 characters"
    if len(query) > 80:
        return "Search query must be 80 characters or fewer"
    if query[0].isspace():
        return "Search query must not start with whitespace"
    for char in query:
        if char in CATALOG_FORBIDDEN_CHARS or ord(char) < 32 or ord(char) == 127:
            return "Search query contains unsupported characters"
    return ""


def workshop_detail_result(workshop_id, kind):
    try:
        payload = http_json(STEAM_DETAILS_URL, {"itemcount": "1", "publishedfileids[0]": workshop_id})
        details = payload.get("response", {}).get("publishedfiledetails", [{}])[0]
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return catalog_item(
            "workshop",
            workshop_id,
            f"Workshop {workshop_id}",
            kind,
            STEAM_WORKSHOP_URL.format(id=workshop_id),
            "",
            "",
            False,
            f"Steam lookup failed: {exc}",
        )
    title = details.get("title") or f"Workshop {workshop_id}"
    installable = str(details.get("result")) == "1" and bool(details.get("file_url"))
    reason = "" if installable else f"Steam API returned result {details.get('result', 'unknown')} without file_url"
    return catalog_item(
        "workshop",
        workshop_id,
        title,
        kind,
        STEAM_WORKSHOP_URL.format(id=workshop_id),
        format_bytes(details.get("file_size")),
        (details.get("description") or "").replace("\r", " ").replace("\n", " ")[:220],
        installable,
        reason,
    )


def workshop_search_results(query, kind):
    results = []
    if WORKSHOP_ID_RE.match(query):
        results.append(workshop_detail_result(query, kind))
        return results
    # QueryFiles usually requires a Steam Web API key. Keep this best-effort,
    # and rely on the curated fallback for known campaigns when it is unavailable.
    params = {
        "query_type": "12",
        "cursor": "*",
        "numperpage": "5",
        "creator_appid": "550",
        "appid": "550",
        "search_text": query,
        "filetype": "0",
        "return_tags": "1",
        "return_short_description": "1",
    }
    if STEAM_WEB_API_KEY:
        params["key"] = STEAM_WEB_API_KEY
    try:
        url = f"{STEAM_QUERY_URL}?{urllib.parse.urlencode(params)}"
        payload = http_json(url, timeout=5)
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        pass
    else:
        for details in payload.get("response", {}).get("publishedfiledetails", [])[:5]:
            item_id = details.get("publishedfileid")
            if not item_id:
                continue
            results.append(catalog_item(
                "workshop",
                item_id,
                details.get("title") or f"Workshop {item_id}",
                kind,
                STEAM_WORKSHOP_URL.format(id=item_id),
                format_bytes(details.get("file_size")),
                details.get("short_description") or "",
                True,
                "",
            ))
    results.extend(workshop_public_search_results(query, kind))
    return results


def workshop_public_search_results(query, kind):
    params = {
        "appid": "550",
        "searchtext": query,
        "browsesort": "textsearch",
        "section": "readytouseitems",
        "actualsort": "textsearch",
        "p": "1",
    }
    try:
        url = f"{STEAM_BROWSE_URL}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=5) as response:
            html_text = response.read(768 * 1024).decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError):
        return []
    item_ids = []
    for match in re.finditer(r'(?:publishedfileid["\']?\s*[:=]\s*["\']?|[?&]id=)(\d{4,20})', html_text):
        item_id = match.group(1)
        if item_id not in item_ids:
            item_ids.append(item_id)
        if len(item_ids) >= 8:
            break
    results = []
    for item_id in item_ids:
        results.append(workshop_detail_result(item_id, kind))
    return results


def gamemaps_search_results(query, kind):
    if kind != "map":
        return []
    results = []
    if WORKSHOP_ID_RE.match(query):
        if len(query) > 8:
            return results
        results.append(catalog_item(
            "gamemaps",
            query,
            f"GameMaps {query}",
            "map",
            GAMEMAPS_DETAILS_URL.format(id=query),
            "",
            "GameMaps numeric details id.",
            True,
            "",
        ))
        return results
    results.extend([item for item in known_catalog_results(query, "map") if item["source"] == "gamemaps"])
    # Best-effort HTML search. GameMaps may block automated requests, so this
    # must never be the only way a known result can appear.
    try:
        search_url = "https://www.gamemaps.com/search?" + urllib.parse.urlencode({"q": query})
        request = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=5) as response:
            html_text = response.read(256 * 1024).decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError):
        return results
    for match in re.finditer(r'href=["\'](?:https://www\.gamemaps\.com)?/details/(\d+)["\'][^>]*>([^<]+)', html_text):
        item_id, raw_title = match.groups()
        title = re.sub(r"\s+", " ", raw_title).strip()
        if not title:
            continue
        item = catalog_item("gamemaps", item_id, title, "map", GAMEMAPS_DETAILS_URL.format(id=item_id), "", "", True, "")
        if all(existing["source"] != "gamemaps" or existing["id"] != item_id for existing in results):
            results.append(item)
        if len(results) >= 6:
            break
    return results


def search_catalog(query, kind):
    query = query.strip()
    if kind not in {"map", "mod"}:
        return {"ok": False, "message": "Kind must be map or mod"}
    error = catalog_query_error(query)
    if error and not WORKSHOP_ID_RE.match(query):
        return {"ok": False, "message": error}
    results = []
    known_results = known_catalog_results(query, kind)
    if known_results and not WORKSHOP_ID_RE.match(query) and not STEAM_WEB_API_KEY:
        return {"ok": True, "query": query, "kind": kind, "results": known_results[:10]}
    results.extend(workshop_search_results(query, kind))
    results.extend(gamemaps_search_results(query, kind))
    if not WORKSHOP_ID_RE.match(query):
        results.extend(known_results)
    deduped = []
    seen = set()
    for item in results:
        item = enrich_catalog_result(item)
        key = (item["source"], item["id"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return {"ok": True, "query": query, "kind": kind, "results": deduped[:10]}


def install_catalog_job(job_id, source, kind, item_id):
    install_catalog_bundle_job(job_id, source, kind, [item_id])


def install_command(source, kind, item_id):
    if source == "workshop":
        return ["/usr/bin/sudo", "-n", "/usr/local/bin/l4d2-webctl", "install-workshop", kind, item_id]
    if source == "gamemaps" and kind == "map":
        return ["/usr/bin/sudo", "-n", "/usr/local/bin/l4d2-webctl", "install-gamemaps-map", item_id]
    return None


def run_install_command(job_id, command, index, total_items, item_id):
    update_job(
        job_id,
        status="running",
        stage="starting",
        current_item=item_id,
        items_done=index - 1,
        items_total=total_items,
        progress=int(((index - 1) / total_items) * 100),
        downloaded_bytes=0,
        total_bytes=0,
        message=f"Installing item {index}/{total_items}: {item_id}",
    )
    lines = []
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        return {"ok": False, "message": str(exc)}

    try:
        assert process.stdout is not None
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            lines.append(line)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                update_job(job_id, message=line[-2000:])
                continue
            if event.get("event") == "progress":
                downloaded = int(event.get("downloaded") or 0)
                total = int(event.get("total") or 0)
                item_fraction = downloaded / total if total > 0 else 0
                update_job(
                    job_id,
                    stage=event.get("stage") or "downloading",
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                    progress=min(99, int(((index - 1 + item_fraction) / total_items) * 100)),
                    message=event.get("message") or f"Downloading item {index}/{total_items}",
                )
            elif event.get("event") == "stage":
                progress = int(((index - 1) / total_items) * 100)
                update_job(
                    job_id,
                    stage=event.get("stage") or "",
                    progress=progress,
                    message=event.get("message") or "",
                )
            elif event.get("event") == "message":
                update_job(job_id, message=event.get("message") or "")
        try:
            stderr = process.stderr.read() if process.stderr else ""
            code = process.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            process.kill()
            stderr = process.stderr.read() if process.stderr else ""
            return {"ok": False, "message": "Install command timed out\n" + stderr}
    except Exception as exc:
        process.kill()
        return {"ok": False, "message": str(exc)}

    messages = []
    installed_filename = ""
    for line in lines[-12:]:
        try:
            event = json.loads(line)
            if event.get("event") == "progress" and event.get("stage") != "downloaded":
                continue
            text = event.get("message")
            if text:
                messages.append(text)
                match = re.search(r"installed\s+([A-Za-z0-9_. -]+\.vpk)", text)
                if match:
                    installed_filename = match.group(1)
        except json.JSONDecodeError:
            messages.append(line)
            match = re.search(r"installed\s+([A-Za-z0-9_. -]+\.vpk)", line)
            if match:
                installed_filename = match.group(1)
    if stderr:
        messages.append(stderr.strip())
    return {"ok": code == 0, "message": "\n".join(part for part in messages if part) or "Install finished", "filename": installed_filename}


def install_catalog_bundle_job(job_id, source, kind, item_ids, title="", url="", catalog_id=""):
    total_items = len(item_ids)
    if total_items < 1:
        update_job(job_id, status="failed", message="No install items", finished_at=int(time.time()))
        return
    messages = []
    for index, current_id in enumerate(item_ids, 1):
        command = install_command(source, kind, current_id)
        if not command:
            update_job(job_id, status="failed", message="Unsupported install source or kind", finished_at=int(time.time()))
            return
        result = run_install_command(job_id, command, index, total_items, current_id)
        messages.append(result["message"])
        if not result["ok"]:
            update_job(
                job_id,
                status="failed",
                stage="failed",
                message=result["message"][-2000:],
                finished_at=int(time.time()),
            )
            return
        if result.get("filename"):
            item_url = (
                STEAM_WORKSHOP_URL.format(id=current_id)
                if source == "workshop"
                else GAMEMAPS_DETAILS_URL.format(id=current_id)
            )
            item_title = title or result["filename"]
            if title and total_items > 1:
                item_title = f"{title} ({index}/{total_items})"
            register_installed_package(
                result["filename"],
                source,
                kind,
                current_id,
                item_title,
                url if current_id == catalog_id else item_url,
                [current_id],
            )
            addon = next((item for item in vpk_inventory() if item["filename"] == result["filename"]), None)
            if kind == "map" and addon and addon.get("maps") and not addon.get("missions"):
                messages.append(f"{result['filename']} installed, but no mission file was found; maps may be grouped by package name.")
        update_job(
            job_id,
            items_done=index,
            progress=int((index / total_items) * 100),
            downloaded_bytes=0,
            total_bytes=0,
            message=f"Installed item {index}/{total_items}: {current_id}",
        )
    update_job(
        job_id,
        status="succeeded",
        stage="finished",
        progress=100,
        current_item="",
        message=("\n".join(messages) or "Install finished")[-2000:],
        finished_at=int(time.time()),
    )


def known_install_ids(source, kind, item_id):
    for item in KNOWN_CATALOG_ITEMS:
        if item["source"] == source and item["kind"] == kind and item["id"] == item_id:
            return [str(value) for value in item.get("install_ids", [])]
    return []


def create_catalog_install_job(source, kind, item_id, title="", url="", install_ids=None):
    if source not in {"workshop", "gamemaps"}:
        return {"ok": False, "message": "Source must be workshop or gamemaps"}
    if kind not in {"map", "mod"}:
        return {"ok": False, "message": "Kind must be map or mod"}
    if source == "gamemaps" and kind != "map":
        return {"ok": False, "message": "GameMaps installs are map-only"}
    if not WORKSHOP_ID_RE.match(item_id):
        return {"ok": False, "message": "Catalog id must be numeric"}
    item_ids = install_ids or known_install_ids(source, kind, item_id) or [item_id]
    if source != "workshop" and len(item_ids) > 1:
        return {"ok": False, "message": "Bundle installs are workshop-only"}
    if any(not WORKSHOP_ID_RE.match(value) for value in item_ids):
        return {"ok": False, "message": "Catalog install ids must be numeric"}
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "source": source,
        "kind": kind,
        "workshop_id": item_id if source == "workshop" else "",
        "catalog_id": item_id,
        "install_ids": item_ids,
        "title": title,
        "url": url,
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "downloaded_bytes": 0,
        "total_bytes": 0,
        "current_item": "",
        "items_done": 0,
        "items_total": len(item_ids),
        "message": "Queued",
        "created_at": int(time.time()),
        "finished_at": None,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
        persist_job(job)
    thread = threading.Thread(
        target=install_catalog_bundle_job,
        args=(job_id, source, kind, item_ids, title, url, item_id),
        daemon=True,
    )
    thread.start()
    return {"ok": True, "message": "Install queued", "job": job}


def create_install_job(kind, workshop_id):
    if not WORKSHOP_ID_RE.match(workshop_id):
        return {"ok": False, "message": "Workshop ID must be numeric"}
    return create_catalog_install_job(
        "workshop",
        kind,
        workshop_id,
        f"Workshop {workshop_id}",
        STEAM_WORKSHOP_URL.format(id=workshop_id),
    )


def set_addon_state(filename, state):
    if not ADDON_RE.match(filename) or "/" in filename or "\\" in filename:
        return {"ok": False, "message": "Invalid addon filename"}
    if state not in {"enabled", "disabled"}:
        return {"ok": False, "message": "Invalid addon state"}
    result = run_cmd(
        ["/usr/bin/sudo", "-n", "/usr/local/bin/l4d2-webctl", "set-addon-state", filename, state],
        timeout=20,
    )
    if result["ok"]:
        return {"ok": True, "message": result["stdout"] or f"{filename} {state}"}
    return {"ok": False, "message": result["stderr"] or result["stdout"] or "Addon update failed"}


def current_default_maps():
    return {value.lower() for value in (default_map(info["script"]) for info in ROOMS.values()) if value}


def package_by_filename(filename):
    for addon in list_addons():
        if addon["filename"] == filename and addon["kind"] == "map":
            return addon
    return None


def delete_map_package(filename, mode):
    if not ADDON_RE.match(filename) or "/" in filename or "\\" in filename:
        return {"ok": False, "message": "Invalid package filename"}
    if mode not in {"soft", "purge"}:
        return {"ok": False, "message": "Invalid delete mode"}
    package = package_by_filename(filename)
    if not package:
        return {"ok": False, "message": "Map package not found"}
    default_maps = current_default_maps()
    package_maps = {name.lower() for name in package.get("maps", [])}
    if default_maps & package_maps:
        return {"ok": False, "message": "Package contains a current default map; switch defaults before deleting it"}
    if package.get("state") != "deleted":
        result = run_cmd(
            ["/usr/bin/sudo", "-n", "/usr/local/bin/l4d2-webctl", "delete-map-package", filename, mode],
            timeout=120,
        )
        if not result["ok"]:
            return {"ok": False, "message": result["stderr"] or result["stdout"] or "Package delete failed"}
    packages = read_package_registry()
    if mode == "purge":
        packages.pop(filename, None)
    else:
        record = packages.get(filename) or {
            "filename": filename,
            "title": package.get("title", filename),
            "source": package.get("source", ""),
            "id": package.get("catalog_id", ""),
            "url": package.get("url", ""),
            "install_ids": package.get("install_ids", []),
            "maps": package.get("maps", []),
            "missions": package.get("missions", []),
        }
        record.update({"status": "deleted", "deleted_at": int(time.time())})
        packages[filename] = record
    write_package_registry(packages)
    return {"ok": True, "message": f"{filename} {mode} deleted"}


def reinstall_map_package(filename):
    if not ADDON_RE.match(filename) or "/" in filename or "\\" in filename:
        return {"ok": False, "message": "Invalid package filename"}
    package = package_by_filename(filename)
    if not package:
        return {"ok": False, "message": "Map package record not found"}
    source = package.get("source", "")
    item_id = package.get("catalog_id", "")
    install_ids = package.get("install_ids", [])
    if source not in {"workshop", "gamemaps"} or not WORKSHOP_ID_RE.match(item_id):
        return {"ok": False, "message": "Package does not have a reinstall source"}
    return create_catalog_install_job(
        source,
        "map",
        item_id,
        package.get("title", filename),
        package.get("url", ""),
        install_ids,
    )


def render_page():
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>L4D2 Server Manager</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #f7f7f4; color: #202322; }
    header { padding: 20px 24px 12px; border-bottom: 1px solid #d9ded8; background: #ffffff; }
    h1 { margin: 0; font-size: 22px; letter-spacing: 0; }
    main { max-width: 1180px; margin: 0 auto; padding: 24px; }
    .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
    .card { background: #fff; border: 1px solid #d9ded8; border-radius: 8px; padding: 16px; }
    .room-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .name { font-weight: 700; font-size: 18px; }
    .pill { border-radius: 999px; padding: 4px 9px; font-size: 12px; background: #e8ece8; color: #2c3b33; }
    .pill.ok { background: #dff1e5; color: #11602e; }
    dl { display: grid; grid-template-columns: 112px 1fr; gap: 8px 12px; margin: 16px 0; font-size: 14px; }
    dt { color: #68706a; }
    dd { margin: 0; overflow-wrap: anywhere; }
    button { height: 36px; border: 1px solid #b8c1ba; background: #25362d; color: #fff; border-radius: 7px; padding: 0 13px; cursor: pointer; white-space: nowrap; }
    button.secondary { background: #fff; color: #25362d; }
    button.danger { background: #733331; border-color: #733331; }
    button:disabled { opacity: .55; cursor: wait; }
    select { height: 36px; min-width: 150px; max-width: 100%; border: 1px solid #b8c1ba; border-radius: 7px; background: #fff; padding: 0 9px; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .primary-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; }
    .field { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    input { height: 34px; min-width: 180px; border: 1px solid #b8c1ba; border-radius: 7px; background: #fff; padding: 0 9px; }
    .toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; }
    .catalog-results { display: grid; gap: 10px; margin-top: 12px; }
    .catalog-item { border-top: 1px solid #e4e7e3; padding-top: 10px; display: grid; gap: 8px; }
    .catalog-head { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: space-between; }
    a { color: #1f5f46; }
    .maps { margin-top: 16px; }
    .maps-list { display: grid; gap: 10px; font-size: 13px; line-height: 1.8; }
    .maps-list details { border-top: 1px solid #e4e7e3; padding-top: 8px; }
    .maps-list details:first-child { border-top: 0; padding-top: 0; }
    .maps-list summary { cursor: pointer; font-weight: 650; }
    .chapter-list { columns: 2 220px; margin-top: 6px; }
    .stack { display: grid; gap: 16px; margin-top: 16px; }
    .split-panel { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(280px, .8fr); gap: 18px; align-items: start; margin-top: 14px; }
    .section-label { font-weight: 700; margin-bottom: 8px; }
    .rows { display: grid; gap: 8px; margin-top: 12px; }
    .row { display: grid; grid-template-columns: minmax(150px, 1fr) 88px 86px 130px; gap: 8px; align-items: center; font-size: 13px; }
    .package-row { grid-template-columns: minmax(260px, 1fr) 88px 86px minmax(180px, auto); padding: 8px 0; border-top: 1px solid #e4e7e3; }
    .package-row:first-child { border-top: 0; }
    .package-title { font-weight: 700; margin-bottom: 3px; }
    .package-actions { justify-content: flex-end; }
    .more-actions { position: relative; border: 0; padding: 0; }
    .more-actions summary { list-style: none; height: 34px; border: 1px solid #b8c1ba; border-radius: 7px; padding: 0 12px; display: inline-flex; align-items: center; background: #fff; color: #25362d; cursor: pointer; font-weight: 650; }
    .more-actions summary::-webkit-details-marker { display: none; }
    .menu-actions { position: absolute; right: 0; top: 40px; z-index: 10; min-width: 170px; display: grid; gap: 6px; padding: 8px; border: 1px solid #d9ded8; border-radius: 8px; background: #fff; box-shadow: 0 8px 24px rgba(0,0,0,.12); }
    .menu-actions button { width: 100%; }
    .job { padding: 8px 0; border-top: 1px solid #e4e7e3; font-size: 13px; }
    .progress-line { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 6px 0; }
    progress { width: min(360px, 100%); height: 14px; accent-color: #25362d; }
    .mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }
    .muted { color: #68706a; font-size: 13px; }
    #notice { min-height: 20px; }
    @media (max-width: 760px) {
      .split-panel { grid-template-columns: 1fr; }
      .package-row, .row { grid-template-columns: 1fr; }
      .package-actions { justify-content: flex-start; }
    }
  </style>
</head>
<body>
  <header><h1>L4D2 Server Manager</h1></header>
  <main>
    <div class="toolbar">
      <button id="refresh">Refresh</button>
      <span id="notice" class="muted"></span>
    </div>
    <section id="rooms" class="grid"></section>
    <section class="stack">
      <section class="card">
        <div class="room-head">
          <div class="name">Search & Install</div>
          <span class="pill">Workshop / GameMaps</span>
        </div>
        <div class="field" style="margin-top: 14px">
          <input id="catalog-query" autocomplete="off" placeholder="Run To The Hills">
          <select id="catalog-kind">
            <option value="map">Map</option>
            <option value="mod">Mod</option>
          </select>
          <button id="catalog-search">Search</button>
          <input id="workshop-id" inputmode="numeric" autocomplete="off" placeholder="Workshop ID">
          <button id="install-workshop">Install ID</button>
        </div>
        <div class="split-panel">
          <div>
            <div class="section-label">Search Results</div>
            <div id="catalog-results" class="catalog-results"></div>
          </div>
          <div>
            <div class="section-label">Install Jobs</div>
            <div id="jobs"></div>
          </div>
        </div>
      </section>
      <section class="card">
        <div class="room-head">
          <div class="name">Map Packages</div>
          <span id="map-package-count" class="pill"></span>
        </div>
        <div id="map-packages" class="rows"></div>
      </section>
      <section class="card">
        <div class="room-head">
          <div class="name">Mod Management</div>
          <span id="addon-count" class="pill"></span>
        </div>
        <div id="addons" class="rows"></div>
      </section>
    </section>
    <section class="maps card">
      <div class="room-head">
        <div class="name">Installed Maps</div>
        <span id="map-count" class="pill"></span>
      </div>
      <div id="maps" class="maps-list"></div>
    </section>
  </main>
  <script>
    const roomsEl = document.querySelector("#rooms");
    const mapsEl = document.querySelector("#maps");
    const mapCountEl = document.querySelector("#map-count");
    const mapPackageCountEl = document.querySelector("#map-package-count");
    const mapPackagesEl = document.querySelector("#map-packages");
    const addonCountEl = document.querySelector("#addon-count");
    const addonsEl = document.querySelector("#addons");
    const jobsEl = document.querySelector("#jobs");
    const catalogResultsEl = document.querySelector("#catalog-results");
    const noticeEl = document.querySelector("#notice");
    let currentState = null;
    let refreshTimer = null;

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }

    function roomCard(room) {
      const ok = room.active === "active" && room.port_listening;
      return `<article class="card">
        <div class="room-head">
          <div class="name">${room.label}</div>
          <span class="pill ${ok ? "ok" : ""}">${ok ? "Running" : room.active}</span>
        </div>
        <dl>
          <dt>Service</dt><dd>${room.service}</dd>
          <dt>Port</dt><dd>${room.port}/udp ${room.port_listening ? "listening" : "not listening"}</dd>
          <dt>Default map</dt><dd>${room.default_map || "unknown"}</dd>
          <dt>Restarts</dt><dd>${room.restarts}</dd>
          <dt>Started</dt><dd>${room.started_at || "unknown"}</dd>
          <dt>Exit status</dt><dd>${room.exit_status}</dd>
        </dl>
        <div class="primary-actions">
          <select data-campaign-select="${room.id}"></select>
          <select data-map-select="${room.id}"></select>
          <button data-save="${room.id}">Save</button>
          <details class="more-actions">
            <summary>More</summary>
            <div class="menu-actions">
              <button class="secondary" data-save-restart="${room.id}">Save & Restart</button>
              <button class="secondary" data-restart="${room.id}">Restart Room</button>
            </div>
          </details>
        </div>
      </article>`;
    }

    function renderAddons(addons) {
      const mods = addons.filter(addon => addon.kind !== "map");
      addonCountEl.textContent = `${mods.length} vpks`;
      if (!mods.length) {
        addonsEl.innerHTML = `<div class="muted">No VPK addons found.</div>`;
        return;
      }
      addonsEl.innerHTML = mods.map(addon => {
        const target = addon.state === "enabled" ? "disabled" : "enabled";
        const label = addon.state === "enabled" ? "Disable" : "Enable";
        const sizeMb = (addon.size / 1024 / 1024).toFixed(1);
        return `<div class="row">
          <div class="mono">${esc(addon.filename)}</div>
          <div>${addon.state}</div>
          <div>${sizeMb} MB</div>
          <button data-addon="${esc(addon.filename)}" data-addon-state="${target}">${label}</button>
        </div>`;
      }).join("");
    }

    function renderMapPackages(addons) {
      const packages = addons.filter(addon => addon.kind === "map");
      mapPackageCountEl.textContent = `${packages.length} vpks`;
      if (!packages.length) {
        mapPackagesEl.innerHTML = `<div class="muted">No map packages found.</div>`;
        return;
      }
      mapPackagesEl.innerHTML = packages.map(addon => {
        const target = addon.state === "enabled" ? "disabled" : "enabled";
        const label = addon.state === "enabled" ? "Disable" : "Enable";
        const sizeMb = (addon.size / 1024 / 1024).toFixed(1);
        const maps = addon.maps && addon.maps.length ? addon.maps.join(", ") : "mission only";
        const deleted = addon.state === "deleted";
        const openLink = addon.url ? `<a href="${esc(addon.url)}" target="_blank" rel="noreferrer">Open</a>` : "";
        const reinstall = addon.reinstallable ? `<button data-package-reinstall="${esc(addon.filename)}">Reinstall</button>` : "";
        const disable = deleted ? "" : `<button class="secondary" data-addon="${esc(addon.filename)}" data-addon-state="${target}">${label}</button>`;
        const softDelete = deleted ? "" : `<button class="secondary" data-package-delete="${esc(addon.filename)}" data-package-mode="soft">Soft Delete</button>`;
        const purgeDelete = `<button class="danger" data-package-delete="${esc(addon.filename)}" data-package-mode="purge">Purge Delete</button>`;
        const source = addon.source && addon.catalog_id ? `${addon.source} ${addon.catalog_id}` : "local package";
        const title = addon.title && addon.title !== addon.filename ? addon.title : addon.filename;
        const statusText = deleted ? "deleted" : addon.state;
        const sizeText = deleted ? "removed" : `${sizeMb} MB`;
        const moreActions = [disable, softDelete, purgeDelete].filter(Boolean).join("");
        const moreMenu = moreActions ? `<details class="more-actions">
          <summary>More</summary>
          <div class="menu-actions">${moreActions}</div>
        </details>` : "";
        return `<div class="row package-row">
          <div>
            <div class="package-title">${esc(title)}</div>
            <div class="muted mono">${esc(addon.filename)}</div>
            <div class="muted">${esc(maps)}</div>
            <div class="muted">${esc(source)}</div>
          </div>
          <div>${statusText}</div>
          <div>${sizeText}</div>
          <div class="actions package-actions">${openLink}${reinstall}${moreMenu}</div>
        </div>`;
      }).join("");
    }

    function renderJobs(jobs) {
      if (!jobs.length) {
        jobsEl.innerHTML = `<div class="muted">No install jobs yet.</div>`;
        return;
      }
      jobsEl.innerHTML = jobs.map(job => `<div class="job">
        <strong>${esc(job.status)}</strong>
        <span class="mono">${esc(job.source || "workshop")} ${esc(job.kind)} ${esc(job.catalog_id || job.workshop_id)}</span>
        ${job.title ? `<div>${esc(job.title)}</div>` : ""}
        ${job.install_ids && job.install_ids.length > 1 ? `<div class="muted mono">packages ${job.install_ids.map(esc).join(", ")}</div>` : ""}
        ${jobProgress(job)}
        <div class="muted">${esc(job.message)}</div>
      </div>`).join("");
    }

    function formatBytes(value) {
      const size = Number(value || 0);
      if (!size) return "";
      const units = ["B", "KB", "MB", "GB"];
      let current = size;
      let unit = 0;
      while (current >= 1024 && unit < units.length - 1) {
        current /= 1024;
        unit += 1;
      }
      return unit === 0 ? `${current} ${units[unit]}` : `${current.toFixed(1)} ${units[unit]}`;
    }

    function jobProgress(job) {
      const active = job.status === "queued" || job.status === "running";
      const progress = Number(job.progress || 0);
      const total = Number(job.total_bytes || 0);
      const downloaded = Number(job.downloaded_bytes || 0);
      const itemText = job.items_total > 1 ? `${job.items_done || 0}/${job.items_total}` : "";
      const bytes = total > 0 ? `${formatBytes(downloaded)} / ${formatBytes(total)}` : "";
      const label = [job.stage || "", itemText, bytes].filter(Boolean).join(" · ");
      if (job.stage === "extracting" && active) {
        return `<div class="progress-line"><progress></progress><span class="muted">${esc(label || "extracting")}</span></div>`;
      }
      return `<div class="progress-line"><progress max="100" value="${Math.max(0, Math.min(100, progress))}"></progress><span class="muted">${Math.round(progress)}%${label ? ` · ${esc(label)}` : ""}</span></div>`;
    }

    function renderCatalogResults(results) {
      if (!results.length) {
        catalogResultsEl.innerHTML = `<div class="muted">No matching maps or mods found. Steam or GameMaps search may be unavailable; try a Workshop ID if you know it.</div>`;
        return;
      }
      catalogResultsEl.innerHTML = results.map(item => {
        const disabled = item.installable ? "" : " disabled";
        const source = item.source === "gamemaps" ? "GameMaps" : "Workshop";
        const reason = item.reason ? `<div class="muted">${esc(item.reason)}</div>` : "";
        const size = item.size ? `<span class="pill">${esc(item.size)}</span>` : "";
        const packages = item.install_ids && item.install_ids.length > 1
          ? `<div class="muted mono">packages ${item.install_ids.map(esc).join(", ")}</div>`
          : "";
        return `<div class="catalog-item">
          <div class="catalog-head">
            <div><strong>${esc(item.title)}</strong> <span class="pill">${source}</span> ${size}</div>
            <div class="actions">
              <a href="${esc(item.url)}" target="_blank" rel="noreferrer">Open</a>
              <button data-catalog-install="${esc(item.id)}" data-catalog-source="${esc(item.source)}" data-catalog-kind="${esc(item.kind)}" data-catalog-title="${esc(item.title)}" data-catalog-url="${esc(item.url)}" data-catalog-install-ids="${esc((item.install_ids || []).join(","))}"${disabled}>Install</button>
            </div>
          </div>
          <div class="muted mono">${esc(item.kind)} ${esc(item.id)}</div>
          ${packages}
          ${item.summary ? `<div class="muted">${esc(item.summary)}</div>` : ""}
          ${reason}
        </div>`;
      }).join("");
    }

    function mapLabel(map) {
      return `${map.chapter}. ${map.display_name} (${map.name})`;
    }

    function selectedCampaignId(room, campaigns) {
      if (room.default_campaign_id) return room.default_campaign_id;
      return campaigns.length ? campaigns[0].id : "";
    }

    function campaignById(campaigns, campaignId) {
      return campaigns.find(campaign => campaign.id === campaignId) || campaigns[0];
    }

    function fillOneRoomSelects(room, campaigns) {
      const campaignSelect = document.querySelector(`[data-campaign-select="${room.id}"]`);
      const mapSelect = document.querySelector(`[data-map-select="${room.id}"]`);
      if (!campaignSelect || !mapSelect) return;
      const selectedCampaign = selectedCampaignId(room, campaigns);
      campaignSelect.innerHTML = campaigns.map(campaign => {
        const selected = campaign.id === selectedCampaign ? " selected" : "";
        return `<option value="${esc(campaign.id)}"${selected}>${esc(campaign.title)}</option>`;
      }).join("");
      fillChapterSelect(room.id, room.default_map, campaigns);
    }

    function fillChapterSelect(roomId, selectedMap, campaigns) {
      const campaignSelect = document.querySelector(`[data-campaign-select="${roomId}"]`);
      const mapSelect = document.querySelector(`[data-map-select="${roomId}"]`);
      if (!campaignSelect || !mapSelect) return;
      const campaign = campaignById(campaigns, campaignSelect.value);
      if (!campaign) {
        mapSelect.innerHTML = "";
        return;
      }
      mapSelect.innerHTML = campaign.maps.map(map => {
        const selected = selectedMap && map.name === selectedMap ? " selected" : "";
        return `<option value="${esc(map.name)}"${selected}>${esc(mapLabel(map))}</option>`;
      }).join("");
    }

    function fillMapSelects(data) {
      for (const room of data.rooms) {
        fillOneRoomSelects(room, data.campaigns || []);
      }
    }

    function renderCampaignMaps(campaigns) {
      if (!campaigns.length) {
        mapsEl.innerHTML = `<div class="muted">No maps found.</div>`;
        return;
      }
      mapsEl.innerHTML = campaigns.map(campaign => {
        const open = campaign.source !== "other" ? " open" : "";
        const chapters = campaign.maps.map(map =>
          `<div><span class="muted">${map.chapter}.</span> ${esc(map.display_name)} <span class="mono">${esc(map.name)}</span></div>`
        ).join("");
        return `<details${open}>
          <summary>${esc(campaign.title)} <span class="muted">${campaign.maps.length} maps</span></summary>
          <div class="chapter-list">${chapters}</div>
        </details>`;
      }).join("");
    }

    async function loadState() {
      noticeEl.textContent = "Loading...";
      const res = await fetch("/api/state");
      if (!res.ok) throw new Error("Failed to load state");
      const data = await res.json();
      currentState = data;
      roomsEl.innerHTML = data.rooms.map(roomCard).join("");
      fillMapSelects(data);
      renderCampaignMaps(data.campaigns || []);
      mapCountEl.textContent = `${data.maps.length} maps`;
      renderMapPackages(data.addons || []);
      renderAddons(data.addons || []);
      renderJobs(data.jobs || []);
      noticeEl.textContent = `Updated ${new Date(data.generated_at * 1000).toLocaleString()}`;
      scheduleNextRefresh(data.jobs || []);
    }

    function scheduleNextRefresh(jobs) {
      if (refreshTimer) clearTimeout(refreshTimer);
      const active = jobs.some(job => job.status === "queued" || job.status === "running");
      refreshTimer = setTimeout(() => loadState().catch(() => {}), active ? 2000 : 30000);
    }

    async function restartRoom(room) {
      noticeEl.textContent = "Restarting...";
      const res = await fetch("/api/restart", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({room})
      });
      const data = await res.json();
      noticeEl.textContent = data.message;
      await loadState();
    }

    async function saveMap(room, restart) {
      const select = document.querySelector(`[data-map-select="${room}"]`);
      if (!select) return;
      noticeEl.textContent = restart ? "Saving and restarting..." : "Saving...";
      const res = await fetch("/api/default-map", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({room, map: select.value, restart: restart ? "1" : "0"})
      });
      const data = await res.json();
      noticeEl.textContent = data.message;
      await loadState();
    }

    async function installWorkshop() {
      const workshopId = document.querySelector("#workshop-id").value.trim();
      const kind = document.querySelector("#catalog-kind").value;
      noticeEl.textContent = "Queueing install...";
      const res = await fetch("/api/workshop/install", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({kind, workshop_id: workshopId})
      });
      const data = await res.json();
      noticeEl.textContent = data.message;
      await loadState();
    }

    async function searchCatalog() {
      const query = document.querySelector("#catalog-query").value.trim();
      const kind = document.querySelector("#catalog-kind").value;
      noticeEl.textContent = "Searching...";
      const res = await fetch(`/api/catalog/search?${new URLSearchParams({query, kind})}`);
      const data = await res.json();
      if (!res.ok) {
        noticeEl.textContent = data.message || "Search failed";
        return;
      }
      renderCatalogResults(data.results || []);
      noticeEl.textContent = `${(data.results || []).length} result(s)`;
    }

    function runCatalogSearch(button) {
      if (button) button.disabled = true;
      return searchCatalog().finally(() => {
        if (button) button.disabled = false;
      });
    }

    async function installCatalog(source, kind, id, title, url, installIds) {
      noticeEl.textContent = "Queueing install...";
      const res = await fetch("/api/catalog/install", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({source, kind, id, title, url, install_ids: installIds || ""})
      });
      const data = await res.json();
      noticeEl.textContent = data.message;
      await loadState();
    }

    async function setAddonState(filename, state) {
      noticeEl.textContent = "Updating addon...";
      const res = await fetch("/api/addon/state", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({filename, state})
      });
      const data = await res.json();
      noticeEl.textContent = data.message;
      await loadState();
    }

    async function deleteMapPackage(filename, mode) {
      const prompt = mode === "purge"
        ? `Permanently delete ${filename}? This removes local files and the saved source record. Reinstalling later will require a fresh search.`
        : `Soft delete ${filename}? This removes local files but keeps the source link for reinstall.`;
      if (!confirm(prompt)) return;
      noticeEl.textContent = "Deleting package...";
      const res = await fetch("/api/map-package/delete", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({filename, mode})
      });
      const data = await res.json();
      noticeEl.textContent = data.message;
      await loadState();
    }

    async function reinstallMapPackage(filename) {
      noticeEl.textContent = "Queueing reinstall...";
      const res = await fetch("/api/map-package/reinstall", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({filename})
      });
      const data = await res.json();
      noticeEl.textContent = data.message;
      await loadState();
    }

    document.querySelector("#refresh").addEventListener("click", loadState);
    const catalogSearchButton = document.querySelector("#catalog-search");
    document.querySelector("#catalog-search").addEventListener("click", event => {
      runCatalogSearch(event.target);
    });
    document.querySelector("#catalog-query").addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        runCatalogSearch(catalogSearchButton);
      }
    });
    document.querySelector("#install-workshop").addEventListener("click", event => {
      event.target.disabled = true;
      installWorkshop().finally(() => event.target.disabled = false);
    });
    catalogResultsEl.addEventListener("click", event => {
      const id = event.target.dataset.catalogInstall;
      if (!id) return;
      event.target.disabled = true;
      installCatalog(
        event.target.dataset.catalogSource,
        event.target.dataset.catalogKind,
        id,
        event.target.dataset.catalogTitle || "",
        event.target.dataset.catalogUrl || "",
        event.target.dataset.catalogInstallIds || ""
      ).finally(() => event.target.disabled = false);
    });
    roomsEl.addEventListener("click", event => {
      const room = event.target.dataset.restart;
      const saveRoom = event.target.dataset.save;
      const saveRestartRoom = event.target.dataset.saveRestart;
      if (room) {
        event.target.disabled = true;
        restartRoom(room).finally(() => event.target.disabled = false);
      }
      if (saveRoom) {
        event.target.disabled = true;
        saveMap(saveRoom, false).finally(() => event.target.disabled = false);
      }
      if (saveRestartRoom) {
        event.target.disabled = true;
        saveMap(saveRestartRoom, true).finally(() => event.target.disabled = false);
      }
    });
    roomsEl.addEventListener("change", event => {
      const room = event.target.dataset.campaignSelect;
      if (!room) return;
      fillChapterSelect(room, null, (currentState && currentState.campaigns) || []);
    });
    addonsEl.addEventListener("click", event => {
      const filename = event.target.dataset.addon;
      const state = event.target.dataset.addonState;
      if (!filename || !state) return;
      event.target.disabled = true;
      setAddonState(filename, state).finally(() => event.target.disabled = false);
    });
    mapPackagesEl.addEventListener("click", event => {
      const filename = event.target.dataset.addon;
      const state = event.target.dataset.addonState;
      const deleteFilename = event.target.dataset.packageDelete;
      const deleteMode = event.target.dataset.packageMode;
      const reinstallFilename = event.target.dataset.packageReinstall;
      if (filename && state) {
        event.target.disabled = true;
        setAddonState(filename, state).finally(() => event.target.disabled = false);
      }
      if (deleteFilename && deleteMode) {
        event.target.disabled = true;
        deleteMapPackage(deleteFilename, deleteMode).finally(() => event.target.disabled = false);
      }
      if (reinstallFilename) {
        event.target.disabled = true;
        reinstallMapPackage(reinstallFilename).finally(() => event.target.disabled = false);
      }
    });
    loadState().catch(err => noticeEl.textContent = err.message);
  </script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "L4D2Manager/0.1"

    def authenticated(self):
        if not ADMIN_PASSWORD:
            return False
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header[6:]).decode("utf-8")
        except Exception:
            return False
        return decoded == f"{ADMIN_USER}:{ADMIN_PASSWORD}"

    def require_auth(self):
        payload = b"Authentication required for L4D2 Manager.\n"
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{AUTH_REALM}"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, status, body):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if not self.authenticated():
            self.require_auth()
            return
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            payload = render_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if parsed.path == "/api/state":
            self.send_json(200, snapshot())
            return
        if parsed.path == "/api/catalog/search":
            fields = parse_qs(parsed.query)
            query = fields.get("query", [""])[0]
            kind = fields.get("kind", ["map"])[0]
            result = search_catalog(query, kind)
            self.send_json(200 if result["ok"] else 400, result)
            return
        self.send_error(404)

    def do_POST(self):
        if not self.authenticated():
            self.require_auth()
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        fields = parse_qs(body)
        if self.path == "/api/restart":
            room = fields.get("room", [""])[0]
            result = restart_room(room)
            self.send_json(200 if result["ok"] else 400, result)
            return
        if self.path == "/api/default-map":
            room = fields.get("room", [""])[0]
            map_name = fields.get("map", [""])[0]
            restart = fields.get("restart", ["0"])[0] == "1"
            result = set_default_map(room, map_name, restart)
            self.send_json(200 if result["ok"] else 400, result)
            return
        if self.path == "/api/workshop/install":
            kind = fields.get("kind", [""])[0]
            workshop_id = fields.get("workshop_id", [""])[0]
            result = create_install_job(kind, workshop_id)
            self.send_json(200 if result["ok"] else 400, result)
            return
        if self.path == "/api/catalog/install":
            source = fields.get("source", [""])[0]
            kind = fields.get("kind", [""])[0]
            item_id = fields.get("id", [""])[0]
            title = fields.get("title", [""])[0][:180]
            url = fields.get("url", [""])[0][:300]
            install_ids = [value for value in fields.get("install_ids", [""])[0].split(",") if value]
            result = create_catalog_install_job(source, kind, item_id, title, url, install_ids)
            self.send_json(200 if result["ok"] else 400, result)
            return
        if self.path == "/api/addon/state":
            filename = fields.get("filename", [""])[0]
            state = fields.get("state", [""])[0]
            result = set_addon_state(filename, state)
            self.send_json(200 if result["ok"] else 400, result)
            return
        if self.path == "/api/map-package/delete":
            filename = fields.get("filename", [""])[0]
            mode = fields.get("mode", [""])[0]
            result = delete_map_package(filename, mode)
            self.send_json(200 if result["ok"] else 400, result)
            return
        if self.path == "/api/map-package/reinstall":
            filename = fields.get("filename", [""])[0]
            result = reinstall_map_package(filename)
            self.send_json(200 if result["ok"] else 400, result)
            return
        self.send_error(404)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


def main():
    host = os.environ.get("L4D2_WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("L4D2_WEB_PORT", "8080"))
    if not ADMIN_PASSWORD:
        raise SystemExit("L4D2_WEB_PASSWORD must be set")
    recover_interrupted_jobs()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Serving L4D2 manager on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
