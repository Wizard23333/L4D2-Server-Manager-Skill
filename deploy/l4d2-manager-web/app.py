#!/usr/bin/env python3
import base64
import cgi
import hashlib
import hmac
import html
from http import cookies
import json
import os
import re
import secrets
import shutil
import struct
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
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
STATE_DIR = Path(os.environ.get("L4D2_WEB_STATE_DIR", "/var/lib/l4d2-manager-web"))
JOBS_DIR = Path(os.environ.get("L4D2_WEB_JOBS_DIR", str(STATE_DIR / "jobs")))
UPLOADS_DIR = Path(os.environ.get("L4D2_WEB_UPLOADS_DIR", str(STATE_DIR / "uploads")))
EXPORTS_DIR = Path(os.environ.get("L4D2_WEB_EXPORTS_DIR", str(STATE_DIR / "exports")))
PACKAGES_FILE = Path(os.environ.get("L4D2_WEB_PACKAGES_FILE", str(STATE_DIR / "packages.json")))
MAX_UPLOAD_BYTES = int(os.environ.get("L4D2_WEB_MAX_UPLOAD_BYTES", str(2 * 1024 * 1024 * 1024)))
EXPORT_RETENTION_SECONDS = int(os.environ.get("L4D2_WEB_EXPORT_RETENTION_SECONDS", str(24 * 60 * 60)))
EXPORT_MIN_FREE_BYTES = int(os.environ.get("L4D2_WEB_EXPORT_MIN_FREE_BYTES", str(1024 * 1024 * 1024)))
EXPORT_MIN_MEMORY_BYTES = int(os.environ.get("L4D2_WEB_EXPORT_MIN_MEMORY_BYTES", str(256 * 1024 * 1024)))
ADMIN_USER = os.environ.get("L4D2_WEB_USER", "admin")
ADMIN_PASSWORD = os.environ.get("L4D2_WEB_PASSWORD", "")
SESSION_SECRET = os.environ.get("L4D2_WEB_SESSION_SECRET", "")
SESSION_TTL_SECONDS = int(os.environ.get("L4D2_WEB_SESSION_TTL_SECONDS", str(12 * 60 * 60)))
SESSION_COOKIE_SECURE = os.environ.get("L4D2_WEB_COOKIE_SECURE", "0") == "1"
STEAM_WEB_API_KEY = os.environ.get("STEAM_WEB_API_KEY", "")
AUTH_REALM = "L4D2 Manager"
WORKSHOP_ID_RE = re.compile(r"^[0-9]{4,20}$")
ADDON_RE = re.compile(r"^[A-Za-z0-9_. -]{1,180}\.vpk$")
JOB_ID_RE = re.compile(r"^[a-f0-9]{12}$")
STAGED_UPLOAD_RE = re.compile(r"^upload_[a-f0-9]{12}_[a-f0-9]{12}\.(vpk|zip)$")
CATALOG_FORBIDDEN_CHARS = set('/\\<>[]{}$;|`')
MANIFEST_FORMAT = "l4d2-manager-web-manifest"
MAX_MANIFEST_BYTES = 1024 * 1024
JOBS = {}
JOB_PROCESSES = {}
SESSIONS = {}
JOBS_LOCK = threading.Lock()
PROCESSES_LOCK = threading.Lock()
SESSIONS_LOCK = threading.Lock()
EXCLUDED_CAMPAIGN_MAPS = {"c5m1_waterfront_sndscape"}
SYSTEM_SERVICES = [
    {"id": "room1", "label": "Room 1", "service": "l4d2"},
    {"id": "room2", "label": "Room 2", "service": "l4d2_2"},
    {"id": "web", "label": "Web Panel", "service": "l4d2-manager-web"},
]
DISK_TARGETS = [
    {"id": "root", "label": "Root", "path": Path("/")},
    {"id": "l4d2", "label": "L4D2", "path": Path("/opt/l4d2")},
    {"id": "web_state", "label": "Web State", "path": STATE_DIR},
]
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
    seen_records = set()
    for item in inventory:
        try:
            modified_at = int(item["path"].stat().st_mtime)
        except OSError:
            modified_at = 0
        package = packages.get(item["filename"], {})
        seen_records.add(item["filename"])
        if item["is_map_package"]:
            kind = "map"
        else:
            kind = package.get("kind") or "mod"
        addons.append(
            {
                "filename": item["filename"],
                "state": item["state"],
                "size": item["size"],
                "modified_at": modified_at,
                "kind": kind,
                "maps": item["maps"],
                "missions": sorted(item["missions"].keys()),
                "source": package.get("source", ""),
                "catalog_id": package.get("id", ""),
                "title": package.get("title", item["filename"]),
                "url": package.get("url", ""),
                "install_ids": package.get("install_ids", []),
                "package_status": package.get("status", "installed"),
                "reinstallable": bool(package.get("source") == "workshop" and package.get("id")),
            }
        )
    for filename, package in packages.items():
        if filename in seen_records or package.get("status") not in {"deleted", "remote", "not_installed"}:
            continue
        kind = package.get("kind") or "map"
        state = "remote" if package.get("status") in {"remote", "not_installed"} else "deleted"
        addons.append(
            {
                "filename": filename,
                "state": state,
                "size": 0,
                "modified_at": package.get("deleted_at") or package.get("imported_at", 0),
                "kind": kind,
                "maps": package.get("maps", []),
                "missions": package.get("missions", []),
                "source": package.get("source", ""),
                "catalog_id": package.get("id", ""),
                "title": package.get("title", filename),
                "url": package.get("url", ""),
                "install_ids": package.get("install_ids", []),
                "package_status": package.get("status", state),
                "reinstallable": bool(package.get("source") == "workshop" and package.get("id")),
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


def parse_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def percent(used, total):
    if not total:
        return None
    return round((used / total) * 100, 1)


def read_meminfo():
    values = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) >= 2:
                    values[parts[0].rstrip(":")] = int(parts[1]) * 1024
    except (OSError, ValueError):
        return values
    return values


def memory_snapshot(meminfo):
    total = meminfo.get("MemTotal", 0)
    available = meminfo.get("MemAvailable", 0)
    used = max(0, total - available) if total else 0
    return {
        "total": total,
        "used": used,
        "available": available,
        "percent": percent(used, total),
    }


def swap_snapshot(meminfo):
    total = meminfo.get("SwapTotal", 0)
    free = meminfo.get("SwapFree", 0)
    used = max(0, total - free) if total else 0
    return {
        "total": total,
        "used": used,
        "free": free,
        "percent": percent(used, total),
    }


def read_cpu_times():
    try:
        with open("/proc/stat", encoding="utf-8") as handle:
            first = handle.readline().split()
    except OSError:
        return None
    if not first or first[0] != "cpu":
        return None
    try:
        values = [int(value) for value in first[1:]]
    except ValueError:
        return None
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return total, idle


def cpu_percent_sample():
    first = read_cpu_times()
    if not first:
        return None
    time.sleep(1)
    second = read_cpu_times()
    if not second:
        return None
    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]
    if total_delta <= 0:
        return None
    return round(max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100)), 1)


def cpu_snapshot():
    try:
        load_avg = os.getloadavg()
    except OSError:
        load_avg = (None, None, None)
    return {
        "cores": os.cpu_count() or 0,
        "percent": cpu_percent_sample(),
        "load_average": [round(value, 2) if value is not None else None for value in load_avg],
    }


def disk_snapshot():
    disks = []
    for target in DISK_TARGETS:
        path = target["path"]
        try:
            usage = shutil.disk_usage(path)
            total = usage.total
            free = usage.free
            used = usage.used
            disks.append(
                {
                    "id": target["id"],
                    "label": target["label"],
                    "path": str(path),
                    "total": total,
                    "used": used,
                    "free": free,
                    "percent": percent(used, total),
                }
            )
        except OSError:
            disks.append(
                {
                    "id": target["id"],
                    "label": target["label"],
                    "path": str(path),
                    "total": None,
                    "used": None,
                    "free": None,
                    "percent": None,
                }
            )
    return disks


def uptime_snapshot():
    try:
        uptime_seconds = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
    except (OSError, IndexError, ValueError):
        return {"seconds": None, "display": "unknown"}
    total = int(uptime_seconds)
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return {"seconds": total, "display": " ".join(parts)}


def system_service_snapshot():
    services = []
    for item in SYSTEM_SERVICES:
        result = run_cmd(
            [
                "/usr/bin/systemctl",
                "show",
                item["service"],
                "-p",
                "ActiveState",
                "-p",
                "SubState",
                "-p",
                "MemoryCurrent",
                "-p",
                "CPUUsageNSec",
                "--no-pager",
            ],
            timeout=5,
        )
        fields = parse_systemctl_show(result["stdout"]) if result["ok"] else {}
        services.append(
            {
                "id": item["id"],
                "label": item["label"],
                "service": item["service"],
                "active": fields.get("ActiveState", "unknown"),
                "sub_state": fields.get("SubState", "unknown"),
                "memory_current": parse_int(fields.get("MemoryCurrent")),
                "cpu_usage_nsec": parse_int(fields.get("CPUUsageNSec")),
            }
        )
    return services


def system_snapshot():
    meminfo = read_meminfo()
    return {
        "cpu": cpu_snapshot(),
        "memory": memory_snapshot(meminfo),
        "swap": swap_snapshot(meminfo),
        "disk": disk_snapshot(),
        "uptime": uptime_snapshot(),
        "processes": system_service_snapshot(),
    }


def snapshot():
    campaigns = build_campaigns()
    return {
        "generated_at": int(time.time()),
        "system": system_snapshot(),
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


def job_status(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return job.get("status") if job else ""


def register_job_process(job_id, process):
    with PROCESSES_LOCK:
        JOB_PROCESSES[job_id] = process


def unregister_job_process(job_id, process=None):
    with PROCESSES_LOCK:
        if process is None or JOB_PROCESSES.get(job_id) is process:
            JOB_PROCESSES.pop(job_id, None)


def current_job_process(job_id):
    with PROCESSES_LOCK:
        return JOB_PROCESSES.get(job_id)


def get_job(job_id):
    load_persisted_jobs()
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return dict(job) if job else None


def log_event(event, **fields):
    payload = {"event": event, "timestamp": int(time.time())}
    payload.update(fields)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


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
        cleanup_job_temp(job["id"])
        cleanup_staged_upload(job.get("staged_filename", ""))


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
            "kind": "map",
            "source": "workshop",
            "id": item_id,
            "url": STEAM_WORKSHOP_URL.format(id=item_id),
            "install_ids": known_install_ids("workshop", "map", item_id) or [item_id],
        }
    match = re.match(r"mod_(\d{4,20})_", filename)
    if match:
        item_id = match.group(1)
        return {
            "kind": "mod",
            "source": "workshop",
            "id": item_id,
            "url": STEAM_WORKSHOP_URL.format(id=item_id),
            "install_ids": [item_id],
        }
    match = re.match(r"map_gamemaps_(\d{1,12})_", filename)
    if match:
        item_id = match.group(1)
        return {
            "kind": "map",
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
                "kind": item["kind"],
                "source": item["source"],
                "id": item["id"],
                "url": item["url"],
                "install_ids": item.get("install_ids") or [item["id"]],
            }
    return {"kind": "", "source": "", "id": "", "url": "", "install_ids": []}


def package_record_from_addon(addon, source_data=None):
    source_data = source_data or infer_package_source(addon["filename"])
    return {
        "filename": addon["filename"],
        "kind": source_data.get("kind") or ("map" if addon.get("is_map_package") else "mod"),
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
        record = packages.get(addon["filename"]) or package_record_from_addon(addon)
        source_data = infer_package_source(addon["filename"])
        kind = record.get("kind") or source_data.get("kind") or ("map" if addon.get("is_map_package") else "mod")
        record.update({
            "filename": addon["filename"],
            "kind": kind,
            "status": "installed",
            "maps": addon.get("maps", []),
            "missions": sorted(addon.get("missions", {}).keys()),
        })
        for key in ("source", "id", "url", "install_ids", "kind"):
            if not record.get(key) and source_data.get(key):
                record[key] = source_data[key]
        packages[addon["filename"]] = record
        changed = True
    if changed:
        write_package_registry(packages)
    return packages


def register_installed_package(filename, source, kind, item_id, title, url, install_ids):
    if kind not in {"map", "mod"} or not ADDON_RE.match(filename):
        return
    addons = vpk_inventory()
    addon = next((item for item in addons if item["filename"] == filename), None)
    if not addon:
        return
    packages = sync_package_registry(addons)
    packages[filename] = package_record_from_addon(
        addon,
        {
            "kind": kind,
            "source": source,
            "id": item_id,
            "url": url
            or (STEAM_WORKSHOP_URL.format(id=item_id) if source == "workshop" and item_id else "")
            or (GAMEMAPS_DETAILS_URL.format(id=item_id) if source == "gamemaps" and item_id else ""),
            "install_ids": install_ids or ([item_id] if item_id else []),
        },
    )
    packages[filename]["title"] = title or packages[filename]["title"]
    packages[filename]["kind"] = kind
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
    if job_status(job_id) == "cancelled":
        return {"ok": False, "cancelled": True, "message": "Install cancelled"}
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
        env = os.environ.copy()
        env["L4D2_WEB_JOB_ID"] = job_id
        env["L4D2_WEB_CURRENT_ITEM"] = item_id
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        register_job_process(job_id, process)
    except Exception as exc:
        return {"ok": False, "message": str(exc)}

    try:
        assert process.stdout is not None
        for line in process.stdout:
            if job_status(job_id) == "cancelled":
                process.terminate()
                return {"ok": False, "cancelled": True, "message": "Install cancelled"}
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
    finally:
        unregister_job_process(job_id, process)

    if job_status(job_id) == "cancelled":
        return {"ok": False, "cancelled": True, "message": "Install cancelled"}

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


def cleanup_job_temp(job_id):
    if not JOB_ID_RE.match(job_id):
        return
    run_cmd(
        ["/usr/bin/sudo", "-n", "/usr/local/bin/l4d2-webctl", "cleanup-job-temp", job_id],
        timeout=20,
    )


def cleanup_staged_upload(staged_filename):
    if not STAGED_UPLOAD_RE.match(staged_filename or ""):
        return
    try:
        (UPLOADS_DIR / staged_filename).unlink()
    except OSError:
        pass


def cancel_job(job_id):
    if not JOB_ID_RE.match(job_id):
        return {"ok": False, "message": "Invalid job id"}
    load_persisted_jobs()
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return {"ok": False, "message": "Job not found"}
        if job.get("status") not in {"queued", "running"}:
            return {"ok": False, "message": "Only queued or running jobs can be cancelled"}
        job.update(
            {
                "status": "cancelled",
                "stage": "cancelled",
                "message": "Cancel requested. Temporary download files will be cleaned up; already installed earlier package parts are kept.",
                "finished_at": int(time.time()),
            }
        )
        persist_job(job)
    process = current_job_process(job_id)
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    cleanup_job_temp(job_id)
    return {"ok": True, "message": "Install job cancelled"}


def install_catalog_bundle_job(job_id, source, kind, item_ids, title="", url="", catalog_id=""):
    try:
        total_items = len(item_ids)
        if total_items < 1:
            update_job(job_id, status="failed", message="No install items", finished_at=int(time.time()))
            return
        messages = []
        for index, current_id in enumerate(item_ids, 1):
            if job_status(job_id) == "cancelled":
                cleanup_job_temp(job_id)
                return
            command = install_command(source, kind, current_id)
            if not command:
                update_job(job_id, status="failed", message="Unsupported install source or kind", finished_at=int(time.time()))
                return
            result = run_install_command(job_id, command, index, total_items, current_id)
            messages.append(result["message"])
            if result.get("cancelled") or job_status(job_id) == "cancelled":
                cleanup_job_temp(job_id)
                update_job(
                    job_id,
                    status="cancelled",
                    stage="cancelled",
                    message="Install cancelled. Already installed earlier package parts were kept.",
                    finished_at=int(time.time()),
                )
                return
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
    finally:
        cleanup_job_temp(job_id)


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


def registry_record_by_filename(filename):
    if not ADDON_RE.match(filename) or "/" in filename or "\\" in filename:
        return None
    for addon in list_addons():
        if addon["filename"] == filename:
            return addon
    return None


def manifest_item_from_record(record):
    item_id = str(record.get("catalog_id") or "")
    install_ids = [str(value) for value in (record.get("install_ids") or [])]
    if not install_ids:
        install_ids = [item_id] if item_id else []
    return {
        "kind": record.get("kind") or "map",
        "source": "workshop",
        "id": item_id,
        "install_ids": install_ids,
        "title": record.get("title") or record.get("filename", ""),
        "url": STEAM_WORKSHOP_URL.format(id=item_id),
        "filename": record.get("filename", ""),
        "state": record.get("state", ""),
        "maps": record.get("maps", []),
        "missions": record.get("missions", []),
    }


def create_manifest(filenames):
    unique = []
    for filename in filenames:
        if filename not in unique:
            unique.append(filename)
    if not unique:
        return {"ok": False, "message": "No addons selected"}
    items = []
    skipped = []
    for filename in unique:
        if not ADDON_RE.match(filename) or "/" in filename or "\\" in filename:
            return {"ok": False, "message": "Invalid addon filename"}
        record = registry_record_by_filename(filename)
        if not record:
            skipped.append({"filename": filename, "reason": "record not found"})
            continue
        kind = record.get("kind")
        source = record.get("source")
        item_id = str(record.get("catalog_id") or "")
        if kind not in {"map", "mod"}:
            skipped.append({"filename": filename, "reason": "unsupported kind"})
            continue
        if source != "workshop" or not WORKSHOP_ID_RE.match(item_id):
            skipped.append({"filename": filename, "reason": "only Workshop items can be exported as JSON manifest"})
            continue
        item = manifest_item_from_record(record)
        if any(not WORKSHOP_ID_RE.match(value) for value in item["install_ids"]):
            skipped.append({"filename": filename, "reason": "invalid Workshop install id"})
            continue
        items.append(item)
    manifest = {
        "format": MANIFEST_FORMAT,
        "version": 1,
        "created_at": int(time.time()),
        "items": items,
        "skipped": skipped,
    }
    return {"ok": True, "message": f"Exported {len(items)} item(s), skipped {len(skipped)}", "manifest": manifest}


def safe_manifest_text(value, limit=180):
    text = str(value or "").strip()
    return text[:limit]


def validate_manifest_item(item):
    if not isinstance(item, dict):
        return None, "item must be an object"
    kind = safe_manifest_text(item.get("kind"), 12)
    if kind not in {"map", "mod"}:
        return None, "kind must be map or mod"
    source = safe_manifest_text(item.get("source"), 20)
    if source != "workshop":
        return None, "only Workshop items are supported"
    item_id = safe_manifest_text(item.get("id"), 24)
    if not WORKSHOP_ID_RE.match(item_id):
        return None, "Workshop id must be numeric"
    filename = Path(safe_manifest_text(item.get("filename"), 180)).name
    if not filename:
        filename = f"{kind}_{item_id}_{safe_manifest_text(item.get('title'), 60) or 'workshop_item'}.vpk"
        filename = re.sub(r"[^A-Za-z0-9_. -]+", "_", filename)
    if not ADDON_RE.match(filename):
        return None, "invalid filename"
    install_ids = [str(value).strip() for value in item.get("install_ids") or [] if str(value).strip()]
    if not install_ids:
        install_ids = [item_id]
    if any(not WORKSHOP_ID_RE.match(value) for value in install_ids):
        return None, "install_ids must be numeric"
    if kind == "mod" and item_id not in install_ids:
        install_ids = [item_id]
    maps = [safe_manifest_text(value, 80) for value in item.get("maps") or [] if safe_manifest_text(value, 80)]
    missions = [safe_manifest_text(value, 80) for value in item.get("missions") or [] if safe_manifest_text(value, 80)]
    record = {
        "filename": filename,
        "kind": kind,
        "source": "workshop",
        "id": item_id,
        "title": safe_manifest_text(item.get("title"), 180) or filename,
        "url": STEAM_WORKSHOP_URL.format(id=item_id),
        "install_ids": install_ids,
        "maps": maps,
        "missions": missions,
        "status": "remote",
        "imported_at": int(time.time()),
    }
    return record, ""


def import_manifest_data(manifest):
    if not isinstance(manifest, dict):
        return {"ok": False, "message": "Manifest must be a JSON object"}
    if manifest.get("format") != MANIFEST_FORMAT or manifest.get("version") != 1:
        return {"ok": False, "message": "Unsupported manifest format or version"}
    items = manifest.get("items")
    if not isinstance(items, list):
        return {"ok": False, "message": "Manifest items must be a list"}
    if len(items) > 200:
        return {"ok": False, "message": "Manifest contains too many items"}
    packages = read_package_registry()
    imported = {"map": 0, "mod": 0}
    skipped = []
    for item in items:
        record, reason = validate_manifest_item(item)
        if not record:
            skipped.append({"filename": str(item.get("filename", "")) if isinstance(item, dict) else "", "reason": reason})
            continue
        filename = record["filename"]
        existing_file = addon_file_path(filename)
        existing_record = packages.get(filename, {})
        if existing_file or existing_record.get("status") == "installed":
            record["status"] = "installed"
            record["installed_at"] = existing_record.get("installed_at", int(time.time()))
        packages[filename] = {**existing_record, **record}
        imported[record["kind"]] += 1
    write_package_registry(packages)
    return {
        "ok": True,
        "message": f"Imported {imported['map']} map(s), {imported['mod']} mod(s); skipped {len(skipped)}",
        "imported": imported,
        "skipped": skipped,
    }


def install_manifest_records(filenames):
    unique = []
    for filename in filenames:
        if filename not in unique:
            unique.append(filename)
    if not unique:
        return {"ok": False, "message": "No manifest records selected"}
    packages = read_package_registry()
    jobs = []
    for filename in unique:
        if not ADDON_RE.match(filename) or "/" in filename or "\\" in filename:
            return {"ok": False, "message": "Invalid addon filename"}
        record = packages.get(filename)
        if not record:
            return {"ok": False, "message": f"Manifest record not found: {filename}"}
        if record.get("source") != "workshop" or not WORKSHOP_ID_RE.match(str(record.get("id", ""))):
            return {"ok": False, "message": f"Record is not installable: {filename}"}
        kind = record.get("kind")
        if kind not in {"map", "mod"}:
            return {"ok": False, "message": f"Unsupported record kind: {filename}"}
        install_ids = [str(value) for value in record.get("install_ids", [])] or [str(record["id"])]
        if any(not WORKSHOP_ID_RE.match(value) for value in install_ids):
            return {"ok": False, "message": f"Invalid install ids: {filename}"}
        result = create_catalog_install_job(
            "workshop",
            kind,
            str(record["id"]),
            record.get("title", filename),
            record.get("url", ""),
            install_ids,
        )
        if not result["ok"]:
            return result
        jobs.append(result["job"])
    return {"ok": True, "message": f"Queued {len(jobs)} install job(s)", "jobs": jobs}


def remove_manifest_record(filename):
    if not ADDON_RE.match(filename) or "/" in filename or "\\" in filename:
        return {"ok": False, "message": "Invalid addon filename"}
    if addon_file_path(filename):
        return {"ok": False, "message": "Addon file exists; remove or disable the file instead of deleting only the record"}
    packages = read_package_registry()
    record = packages.get(filename)
    if not record:
        return {"ok": False, "message": "Record not found"}
    if record.get("status") not in {"remote", "not_installed", "deleted"}:
        return {"ok": False, "message": "Only remote/deleted records can be removed"}
    packages.pop(filename, None)
    write_package_registry(packages)
    return {"ok": True, "message": f"Removed record {filename}"}


def addon_file_path(filename):
    if not ADDON_RE.match(filename) or "/" in filename or "\\" in filename:
        return None
    for root in (ADDONS_DIR, DISABLED_ADDONS_DIR):
        path = root / filename
        if path.is_file():
            return path
    return None


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def assert_vpk_signature(path):
    try:
        with open(path, "rb") as handle:
            return handle.read(4) == b"\x34\x12\xaa\x55"
    except OSError:
        return False


def collect_export_packages(filenames):
    unique = []
    for filename in filenames:
        if filename not in unique:
            unique.append(filename)
    if not unique:
        return {"ok": False, "message": "No packages selected"}
    packages = read_package_registry()
    manifest_packages = []
    registry_subset = {}
    export_paths = []
    for filename in unique:
        if not ADDON_RE.match(filename) or "/" in filename or "\\" in filename:
            return {"ok": False, "message": "Invalid package filename"}
        package = package_by_filename(filename)
        if not package or package.get("kind") != "map" or package.get("state") == "deleted":
            return {"ok": False, "message": f"Map package is not installed: {filename}"}
        path = addon_file_path(filename)
        if not path:
            return {"ok": False, "message": f"VPK file not found: {filename}"}
        manifest_packages.append(
            {
                "filename": filename,
                "state": package.get("state", ""),
                "source": package.get("source", ""),
                "id": package.get("catalog_id", ""),
                "url": package.get("url", ""),
                "install_ids": package.get("install_ids", []),
                "maps": package.get("maps", []),
                "missions": package.get("missions", []),
                "size": path.stat().st_size,
                "sha256": "",
            }
        )
        registry_subset[filename] = packages.get(filename) or {
            "filename": filename,
            "title": package.get("title", filename),
            "source": package.get("source", ""),
            "id": package.get("catalog_id", ""),
            "url": package.get("url", ""),
            "install_ids": package.get("install_ids", []),
            "maps": package.get("maps", []),
            "missions": package.get("missions", []),
            "status": "installed",
        }
        export_paths.append((filename, path))
    return {
        "ok": True,
        "manifest_packages": manifest_packages,
        "registry_subset": registry_subset,
        "export_paths": export_paths,
    }


def mem_available_bytes():
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except (OSError, IndexError, ValueError):
        return None
    return None


def active_export_filenames():
    load_persisted_jobs()
    with JOBS_LOCK:
        return {
            job.get("export_filename", "")
            for job in JOBS.values()
            if job.get("type") == "export" and job.get("status") in {"queued", "running", "succeeded"}
        }


def prune_old_exports():
    try:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        paths = list(EXPORTS_DIR.glob("l4d2-map-packages-*.zip"))
    except OSError:
        return
    cutoff = time.time() - EXPORT_RETENTION_SECONDS
    protected = active_export_filenames()
    for path in paths:
        try:
            if path.name in protected and path.stat().st_mtime >= cutoff:
                continue
            if path.stat().st_mtime < cutoff:
                size = path.stat().st_size
                path.unlink()
                log_event("export_pruned", filename=path.name, bytes=size)
        except OSError as exc:
            log_event("export_prune_failed", filename=path.name, message=str(exc))


def check_export_capacity(required_bytes):
    try:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        free_bytes = shutil.disk_usage(EXPORTS_DIR).free
    except OSError as exc:
        return {"ok": False, "message": f"Cannot inspect export directory: {exc}"}
    required_free = max(EXPORT_MIN_FREE_BYTES, required_bytes + 256 * 1024 * 1024)
    if free_bytes < required_free:
        return {
            "ok": False,
            "message": (
                "Not enough disk space for export: "
                f"free {free_bytes // (1024 * 1024)} MB, "
                f"need {required_free // (1024 * 1024)} MB"
            ),
        }
    available_memory = mem_available_bytes()
    if available_memory is not None and available_memory < EXPORT_MIN_MEMORY_BYTES:
        return {
            "ok": False,
            "message": (
                "Not enough available memory for export: "
                f"available {available_memory // (1024 * 1024)} MB, "
                f"need {EXPORT_MIN_MEMORY_BYTES // (1024 * 1024)} MB"
            ),
        }
    return {"ok": True}


def export_map_packages(filenames):
    collected = collect_export_packages(filenames)
    if not collected["ok"]:
        return collected
    try:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        export_name = f"l4d2-map-packages-{uuid.uuid4().hex[:12]}.zip"
        export_path = EXPORTS_DIR / export_name
        for item, (_, path) in zip(collected["manifest_packages"], collected["export_paths"]):
            item["sha256"] = sha256_file(path)
        manifest = {
            "format": "l4d2-manager-web-export",
            "version": 1,
            "created_at": int(time.time()),
            "packages": collected["manifest_packages"],
        }
        with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr("packages.json", json.dumps({"packages": collected["registry_subset"]}, ensure_ascii=False, indent=2))
            for filename, path in collected["export_paths"]:
                archive.write(path, f"addons/{filename}")
        return {"ok": True, "path": export_path, "filename": export_name}
    except OSError as exc:
        return {"ok": False, "message": str(exc)}


def send_zip_file(handler, path, download_name):
    try:
        size = path.stat().st_size
        handler.send_response(200)
        handler.send_header("Content-Type", "application/zip")
        handler.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        handler.send_header("Content-Length", str(size))
        handler.end_headers()
        with open(path, "rb") as handle:
            shutil.copyfileobj(handle, handler.wfile)
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def stream_zip_file(handler, path, download_name, job_id=""):
    size = path.stat().st_size
    start = time.time()
    log_event("export_download_start", job_id=job_id, filename=download_name, bytes=size)
    handler.send_response(200)
    handler.send_header("Content-Type", "application/zip")
    handler.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
    handler.send_header("Content-Length", str(size))
    handler.end_headers()
    with open(path, "rb") as handle:
        shutil.copyfileobj(handle, handler.wfile)
    log_event(
        "export_download_finished",
        job_id=job_id,
        filename=download_name,
        bytes=size,
        duration_ms=int((time.time() - start) * 1000),
    )


def create_export_job(filenames):
    collected = collect_export_packages(filenames)
    if not collected["ok"]:
        return collected
    total_bytes = sum(path.stat().st_size for _, path in collected["export_paths"])
    prune_old_exports()
    capacity = check_export_capacity(total_bytes)
    if not capacity["ok"]:
        log_event("export_rejected", bytes=total_bytes, message=capacity["message"])
        return capacity
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "type": "export",
        "source": "local",
        "kind": "map",
        "catalog_id": "",
        "install_ids": [],
        "title": f"Export {len(collected['export_paths'])} map package(s)",
        "url": "",
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "downloaded_bytes": 0,
        "total_bytes": total_bytes,
        "current_item": "",
        "items_done": 0,
        "items_total": len(collected["export_paths"]),
        "message": "Export queued",
        "created_at": int(time.time()),
        "finished_at": None,
        "download_url": "",
        "export_filename": "",
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
        persist_job(job)
    thread = threading.Thread(target=run_export_job, args=(job_id, collected), daemon=True)
    thread.start()
    return {"ok": True, "message": "Export queued", "job": job}


def run_export_job(job_id, collected):
    start = time.time()
    export_name = f"l4d2-map-packages-{job_id}.zip"
    export_path = EXPORTS_DIR / export_name
    total_bytes = sum(path.stat().st_size for _, path in collected["export_paths"])
    log_event("export_started", job_id=job_id, filename=export_name, bytes=total_bytes)
    try:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        capacity = check_export_capacity(total_bytes)
        if not capacity["ok"]:
            raise RuntimeError(capacity["message"])
        manifest_packages = collected["manifest_packages"]
        export_paths = collected["export_paths"]
        total_items = max(1, len(export_paths))
        for index, (manifest_item, (filename, path)) in enumerate(zip(manifest_packages, export_paths), 1):
            update_job(
                job_id,
                status="running",
                stage="hashing",
                current_item=filename,
                items_done=index - 1,
                progress=int(((index - 1) / total_items) * 45),
                message=f"Hashing {filename}",
            )
            log_event("export_hashing", job_id=job_id, stage="hashing", filename=filename, bytes=path.stat().st_size)
            manifest_item["sha256"] = sha256_file(path)
        manifest = {
            "format": "l4d2-manager-web-export",
            "version": 1,
            "created_at": int(time.time()),
            "packages": manifest_packages,
        }
        update_job(job_id, stage="packing", progress=50, message="Writing export ZIP")
        log_event("export_packing", job_id=job_id, stage="packing", filename=export_name)
        with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr("packages.json", json.dumps({"packages": collected["registry_subset"]}, ensure_ascii=False, indent=2))
            for index, (filename, path) in enumerate(export_paths, 1):
                update_job(
                    job_id,
                    stage="packing",
                    current_item=filename,
                    items_done=index - 1,
                    progress=50 + int(((index - 1) / total_items) * 45),
                    message=f"Packing {filename}",
                )
                archive.write(path, f"addons/{filename}")
        size = export_path.stat().st_size
        update_job(
            job_id,
            status="succeeded",
            stage="ready",
            progress=100,
            current_item="",
            items_done=len(export_paths),
            message=f"Export ready: {export_name}",
            download_url=f"/api/export/download?job_id={job_id}",
            export_filename=export_name,
            finished_at=int(time.time()),
        )
        log_event("export_finished", job_id=job_id, stage="ready", filename=export_name, bytes=size, duration_ms=int((time.time() - start) * 1000))
    except Exception as exc:
        update_job(job_id, status="failed", stage="failed", message=str(exc)[-2000:], finished_at=int(time.time()))
        log_event("export_failed", job_id=job_id, stage="failed", filename=export_name, message=str(exc), duration_ms=int((time.time() - start) * 1000))


def export_download_for_job(job_id):
    if not JOB_ID_RE.match(job_id):
        return {"ok": False, "message": "Invalid job id"}
    job = get_job(job_id)
    if not job:
        return {"ok": False, "message": "Export job not found"}
    if job.get("type") != "export" or job.get("status") != "succeeded" or job.get("stage") != "ready":
        return {"ok": False, "message": "Export is not ready"}
    filename = job.get("export_filename", "")
    if not re.match(r"^l4d2-map-packages-[a-f0-9]{12}\.zip$", filename):
        return {"ok": False, "message": "Invalid export filename"}
    path = (EXPORTS_DIR / filename).resolve()
    try:
        exports_root = EXPORTS_DIR.resolve()
    except OSError:
        return {"ok": False, "message": "Export directory is missing"}
    if exports_root not in path.parents or not path.is_file():
        return {"ok": False, "message": "Export file is missing"}
    return {"ok": True, "path": path, "filename": filename, "job_id": job_id}


def safe_upload_final_name(filename, suffix):
    name = Path(filename or "").name
    if suffix == ".vpk":
        candidate = re.sub(r"[^A-Za-z0-9_. -]+", "_", name)
        if not candidate.lower().endswith(".vpk"):
            candidate = f"{Path(candidate).stem or 'uploaded'}.vpk"
        return candidate if ADDON_RE.match(candidate) else f"uploaded_{uuid.uuid4().hex[:8]}.vpk"
    return f"upload_{uuid.uuid4().hex[:12]}.zip"


def create_transfer_job(kind, upload_type, staged_filename, final_filename="", metadata=None):
    if upload_type not in {"vpk", "zip"}:
        return {"ok": False, "message": "Invalid upload type"}
    if upload_type == "vpk" and kind not in {"map", "mod"}:
        return {"ok": False, "message": "Kind must be map or mod"}
    if not STAGED_UPLOAD_RE.match(staged_filename):
        return {"ok": False, "message": "Invalid staged upload filename"}
    if final_filename and not ADDON_RE.match(final_filename):
        return {"ok": False, "message": "Invalid final filename"}
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "source": "upload",
        "kind": kind or "map",
        "catalog_id": "",
        "install_ids": [],
        "title": final_filename or staged_filename,
        "url": "",
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "downloaded_bytes": 0,
        "total_bytes": 0,
        "current_item": staged_filename,
        "items_done": 0,
        "items_total": 1,
        "message": "Upload received; import queued",
        "created_at": int(time.time()),
        "finished_at": None,
        "upload_type": upload_type,
        "staged_filename": staged_filename,
        "final_filename": final_filename,
        "metadata": metadata or {},
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
        persist_job(job)
    thread = threading.Thread(target=run_transfer_job, args=(job_id,), daemon=True)
    thread.start()
    return {"ok": True, "message": "Import queued", "job": job}


def run_job_command(job_id, command, env_extra=None):
    update_job(job_id, status="running", stage="importing", progress=5, message="Import started")
    lines = []
    try:
        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        register_job_process(job_id, process)
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    try:
        assert process.stdout is not None
        for line in process.stdout:
            if job_status(job_id) == "cancelled":
                process.terminate()
                return {"ok": False, "cancelled": True, "message": "Import cancelled"}
            line = line.strip()
            if not line:
                continue
            lines.append(line)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                update_job(job_id, message=line[-2000:])
                continue
            if event.get("event") == "stage":
                update_job(job_id, stage=event.get("stage") or "", message=event.get("message") or "", progress=50)
            elif event.get("event") == "message":
                update_job(job_id, message=event.get("message") or "")
        stderr = process.stderr.read() if process.stderr else ""
        code = process.wait(timeout=1800)
    except Exception as exc:
        process.kill()
        return {"ok": False, "message": str(exc)}
    finally:
        unregister_job_process(job_id, process)
    if job_status(job_id) == "cancelled":
        return {"ok": False, "cancelled": True, "message": "Import cancelled"}
    message = "\n".join(lines[-8:])
    if stderr:
        message = (message + "\n" + stderr.strip()).strip()
    return {"ok": code == 0, "message": message or "Import finished"}


def merge_imported_packages_from_zip(staged_path):
    try:
        with zipfile.ZipFile(staged_path) as archive:
            package_data = json.loads(archive.read("packages.json").decode("utf-8"))
    except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile):
        return
    incoming = package_data.get("packages", {}) if isinstance(package_data, dict) else {}
    if not isinstance(incoming, dict):
        return
    packages = read_package_registry()
    for filename, record in incoming.items():
        if ADDON_RE.match(filename) and isinstance(record, dict):
            record = dict(record)
            record.update({"filename": filename, "status": "installed", "installed_at": int(time.time())})
            packages[filename] = record
    write_package_registry(packages)


def run_transfer_job(job_id):
    with JOBS_LOCK:
        job = dict(JOBS.get(job_id) or {})
    staged_filename = job.get("staged_filename", "")
    staged_path = UPLOADS_DIR / staged_filename
    try:
        if job_status(job_id) == "cancelled":
            return
        if not staged_path.is_file():
            update_job(job_id, status="failed", stage="failed", message="Staged upload is missing", finished_at=int(time.time()))
            return
        if job.get("upload_type") == "vpk":
            command = [
                "/usr/bin/sudo",
                "-n",
                "/usr/local/bin/l4d2-webctl",
                "import-vpk",
                job.get("kind", "map"),
                staged_filename,
                job.get("final_filename", ""),
            ]
        else:
            command = ["/usr/bin/sudo", "-n", "/usr/local/bin/l4d2-webctl", "import-export-zip", staged_filename]
        result = run_job_command(job_id, command, {"L4D2_WEB_JOB_ID": job_id})
        if result.get("cancelled"):
            update_job(job_id, status="cancelled", stage="cancelled", message="Import cancelled", finished_at=int(time.time()))
            return
        if not result["ok"]:
            update_job(job_id, status="failed", stage="failed", message=result["message"][-2000:], finished_at=int(time.time()))
            return
        if job.get("upload_type") == "vpk":
            register_installed_package(
                job.get("final_filename", ""),
                "upload",
                job.get("kind", "map"),
                "",
                Path(job.get("final_filename", "")).stem,
                "",
                [],
            )
        else:
            merge_imported_packages_from_zip(staged_path)
        update_job(
            job_id,
            status="succeeded",
            stage="finished",
            progress=100,
            message=result["message"][-2000:] or "Import finished",
            finished_at=int(time.time()),
        )
    finally:
        cleanup_staged_upload(staged_filename)


def create_upload_job(kind, field):
    original = Path(field.filename or "").name
    suffix = Path(original).suffix.lower()
    if suffix not in {".vpk", ".zip"}:
        return {"ok": False, "message": "Upload must be a .vpk or an exported .zip"}
    upload_type = suffix.lstrip(".")
    final_filename = safe_upload_final_name(original, suffix) if upload_type == "vpk" else ""
    if final_filename and addon_file_path(final_filename):
        return {"ok": False, "message": f"Target already exists: {final_filename}"}
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    staged_filename = f"upload_{uuid.uuid4().hex[:12]}_{uuid.uuid4().hex[:12]}{suffix}"
    staged_path = UPLOADS_DIR / staged_filename
    size = 0
    try:
        with open(staged_path, "wb") as handle:
            while True:
                chunk = field.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    handle.close()
                    staged_path.unlink(missing_ok=True)
                    return {"ok": False, "message": "Upload is too large"}
                handle.write(chunk)
    except OSError as exc:
        return {"ok": False, "message": str(exc)}
    if upload_type == "vpk" and not assert_vpk_signature(staged_path):
        staged_path.unlink(missing_ok=True)
        return {"ok": False, "message": "Uploaded file is not a VPK"}
    if upload_type == "zip":
        validation = validate_export_zip(staged_path)
        if not validation["ok"]:
            staged_path.unlink(missing_ok=True)
            return validation
    return create_transfer_job(kind, upload_type, staged_filename, final_filename)


def validate_export_zip(path):
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if "manifest.json" not in names or "packages.json" not in names:
                return {"ok": False, "message": "ZIP must be an L4D2 manager export"}
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if manifest.get("format") != "l4d2-manager-web-export":
                return {"ok": False, "message": "Unsupported export manifest"}
            addon_names = [name for name in names if name.startswith("addons/")]
            if not addon_names:
                return {"ok": False, "message": "Export ZIP does not contain VPK files"}
            for name in names:
                normalized = name.replace("\\", "/")
                if normalized.startswith("/") or ".." in Path(normalized).parts:
                    return {"ok": False, "message": "ZIP contains unsafe paths"}
                if normalized.endswith("/"):
                    continue
                if normalized not in {"manifest.json", "packages.json"} and not normalized.startswith("addons/"):
                    return {"ok": False, "message": "ZIP contains unsupported files"}
                if normalized.startswith("addons/") and not ADDON_RE.match(Path(normalized).name):
                    return {"ok": False, "message": "ZIP contains invalid VPK filename"}
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        return {"ok": False, "message": f"Invalid export ZIP: {exc}"}
    return {"ok": True, "message": "ZIP is valid"}


def handle_upload_request(handler):
    content_length = int(handler.headers.get("Content-Length", "0") or 0)
    if content_length <= 0:
        handler.send_json(400, {"ok": False, "message": "Upload body is empty"})
        return
    if content_length > MAX_UPLOAD_BYTES + 1024 * 1024:
        handler.send_json(400, {"ok": False, "message": "Upload is too large"})
        return
    content_type = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        handler.send_json(400, {"ok": False, "message": "Upload must use multipart/form-data"})
        return
    form = cgi.FieldStorage(
        fp=handler.rfile,
        headers=handler.headers,
        environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": str(content_length),
        },
    )
    file_field = form["file"] if "file" in form else None
    if isinstance(file_field, list):
        file_field = file_field[0] if file_field else None
    if file_field is None or not getattr(file_field, "filename", ""):
        handler.send_json(400, {"ok": False, "message": "Missing upload file"})
        return
    kind = form.getfirst("kind", "map")
    result = create_upload_job(kind, file_field)
    handler.send_json(200 if result["ok"] else 400, result)


def handle_manifest_import_request(handler):
    content_length = int(handler.headers.get("Content-Length", "0") or 0)
    if content_length <= 0:
        handler.send_json(400, {"ok": False, "message": "Manifest upload body is empty"})
        return
    if content_length > MAX_MANIFEST_BYTES + 1024 * 64:
        handler.send_json(400, {"ok": False, "message": "Manifest upload is too large"})
        return
    content_type = handler.headers.get("Content-Type", "")
    try:
        if "multipart/form-data" in content_type:
            form = cgi.FieldStorage(
                fp=handler.rfile,
                headers=handler.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                    "CONTENT_LENGTH": str(content_length),
                },
            )
            file_field = form["file"] if "file" in form else None
            if isinstance(file_field, list):
                file_field = file_field[0] if file_field else None
            if file_field is None or not getattr(file_field, "filename", ""):
                handler.send_json(400, {"ok": False, "message": "Missing manifest file"})
                return
            if Path(file_field.filename).suffix.lower() != ".json":
                handler.send_json(400, {"ok": False, "message": "Manifest must be a .json file"})
                return
            payload = file_field.file.read(MAX_MANIFEST_BYTES + 1)
        else:
            payload = handler.rfile.read(content_length)
        if len(payload) > MAX_MANIFEST_BYTES:
            handler.send_json(400, {"ok": False, "message": "Manifest upload is too large"})
            return
        manifest = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        handler.send_json(400, {"ok": False, "message": f"Invalid manifest JSON: {exc}"})
        return
    result = import_manifest_data(manifest)
    handler.send_json(200 if result["ok"] else 400, result)


def check_credentials(username, password):
    return hmac.compare_digest(str(username or ""), ADMIN_USER) and hmac.compare_digest(str(password or ""), ADMIN_PASSWORD)


def prune_sessions():
    now = time.time()
    with SESSIONS_LOCK:
        expired = [token for token, data in SESSIONS.items() if data.get("expires_at", 0) <= now]
        for token in expired:
            SESSIONS.pop(token, None)


def create_session(username):
    prune_sessions()
    token = secrets.token_urlsafe(32)
    with SESSIONS_LOCK:
        SESSIONS[token] = {
            "username": username,
            "created_at": int(time.time()),
            "expires_at": time.time() + SESSION_TTL_SECONDS,
        }
    return token


def session_from_cookie(header):
    if not header:
        return None
    jar = cookies.SimpleCookie()
    try:
        jar.load(header)
    except cookies.CookieError:
        return None
    morsel = jar.get("l4d2web_session")
    if not morsel:
        return None
    token = morsel.value
    prune_sessions()
    with SESSIONS_LOCK:
        data = SESSIONS.get(token)
        if not data:
            return None
        if data.get("expires_at", 0) <= time.time():
            SESSIONS.pop(token, None)
            return None
        return token


def destroy_session(token):
    if not token:
        return
    with SESSIONS_LOCK:
        SESSIONS.pop(token, None)


def session_cookie_header(token, max_age=SESSION_TTL_SECONDS):
    parts = [
        f"l4d2web_session={token}",
        "Path=/",
        "HttpOnly",
        "SameSite=Lax",
        f"Max-Age={max_age}",
    ]
    if SESSION_COOKIE_SECURE:
        parts.append("Secure")
    return "; ".join(parts)


def render_login_page(message=""):
    safe_message = html.escape(message or "")
    message_html = f'<div id="message" class="message">{safe_message}</div>' if safe_message else '<div id="message" class="message"></div>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>L4D2 Manager Login</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f7f7f4; color: #202322; }}
    main {{ width: min(390px, calc(100vw - 32px)); background: #fff; border: 1px solid #d9ded8; border-radius: 8px; padding: 24px; }}
    h1 {{ margin: 0 0 6px; font-size: 22px; letter-spacing: 0; }}
    p {{ margin: 0 0 20px; color: #68706a; }}
    label {{ display: grid; gap: 6px; margin-top: 14px; font-weight: 650; }}
    input {{ height: 38px; border: 1px solid #b8c1ba; border-radius: 7px; padding: 0 10px; font: inherit; }}
    button {{ margin-top: 18px; width: 100%; height: 40px; border: 1px solid #25362d; border-radius: 7px; background: #25362d; color: #fff; font: inherit; cursor: pointer; }}
    button:disabled {{ opacity: .6; cursor: wait; }}
    .message {{ min-height: 20px; margin-top: 14px; color: #9c3b37; }}
  </style>
</head>
<body>
  <main>
    <h1>L4D2 Server Manager</h1>
    <p>Sign in to manage rooms, maps, mods, and server health.</p>
    <form id="login-form">
      <label>Username <input id="username" name="username" autocomplete="username" required autofocus></label>
      <label>Password <input id="password" name="password" type="password" autocomplete="current-password" required></label>
      <button id="submit" type="submit">Sign In</button>
    </form>
    {message_html}
  </main>
  <script>
    const params = new URLSearchParams(location.search);
    const messageEl = document.querySelector("#message");
    if (params.get("expired") === "1") {{
      messageEl.textContent = "Your session expired. Sign in again.";
    }}
    document.querySelector("#login-form").addEventListener("submit", async event => {{
      event.preventDefault();
      const button = document.querySelector("#submit");
      button.disabled = true;
      messageEl.textContent = "Signing in...";
      const body = new URLSearchParams({{
        username: document.querySelector("#username").value,
        password: document.querySelector("#password").value
      }});
      try {{
        const res = await fetch("/api/login", {{
          method: "POST",
          headers: {{"Content-Type": "application/x-www-form-urlencoded"}},
          body
        }});
        const data = await res.json();
        if (!res.ok) {{
          messageEl.textContent = data.message || "Sign in failed";
          return;
        }}
        location.href = "/";
      }} catch (err) {{
        messageEl.textContent = err.message || "Sign in failed";
      }} finally {{
        button.disabled = false;
      }}
    }});
  </script>
</body>
</html>"""


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
    header { padding: 18px 24px 12px; border-bottom: 1px solid #d9ded8; background: #ffffff; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    h1 { margin: 0; font-size: 22px; letter-spacing: 0; }
    main { max-width: 1180px; margin: 0 auto; padding: 24px; }
    .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
    .card { background: #fff; border: 1px solid #d9ded8; border-radius: 8px; padding: 16px; }
    .room-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin: 0 0 12px; }
    .section-desc { margin: 4px 0 0; color: #68706a; font-size: 13px; line-height: 1.5; }
    .name { font-weight: 700; font-size: 18px; }
    .pill { border-radius: 999px; padding: 4px 9px; font-size: 12px; background: #e8ece8; color: #2c3b33; }
    .pill.ok { background: #dff1e5; color: #11602e; }
    .pill.warn { background: #fff0c9; color: #6d4d00; }
    .pill.danger { background: #f4d7d5; color: #733331; }
    dl { display: grid; grid-template-columns: 112px 1fr; gap: 8px 12px; margin: 16px 0; font-size: 14px; }
    dt { color: #68706a; }
    dd { margin: 0; overflow-wrap: anywhere; }
    button { height: 36px; border: 1px solid #b8c1ba; background: #25362d; color: #fff; border-radius: 7px; padding: 0 13px; cursor: pointer; white-space: nowrap; font-weight: 650; }
    button.secondary { background: #fff; color: #25362d; }
    button.danger { background: #733331; border-color: #733331; }
    button:disabled { opacity: .55; cursor: wait; }
    select { height: 36px; min-width: 150px; max-width: 100%; border: 1px solid #b8c1ba; border-radius: 7px; background: #fff; padding: 0 9px; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .primary-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; }
    .field { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    input { height: 34px; min-width: 180px; border: 1px solid #b8c1ba; border-radius: 7px; background: #fff; padding: 0 9px; }
    input[type="checkbox"] { height: auto; min-width: 0; padding: 0; }
    input[type="file"] { padding: 5px 9px; }
    .toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; }
    .overview-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }
    .overview-item { background: #fff; border: 1px solid #d9ded8; border-radius: 8px; padding: 12px; display: grid; gap: 4px; }
    .overview-label { color: #68706a; font-size: 12px; }
    .overview-value { font-size: 22px; font-weight: 750; }
    .tool-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-top: 14px; }
    .tool-panel { border: 1px solid #e4e7e3; border-radius: 8px; padding: 12px; display: grid; gap: 10px; align-content: start; }
    .tool-title { font-weight: 700; }
    .decision-list { display: grid; gap: 6px; margin: 12px 0 0; padding: 10px 12px; border: 1px solid #e4e7e3; border-radius: 8px; background: #fbfcfa; font-size: 13px; }
    .decision-list strong { color: #25362d; }
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
    .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 12px; }
    .filter-button { background: #fff; color: #25362d; }
    .filter-button.active { background: #25362d; color: #fff; }
    .rows { display: grid; gap: 8px; margin-top: 12px; }
    .row { display: grid; grid-template-columns: minmax(150px, 1fr) 88px 86px 130px; gap: 8px; align-items: center; font-size: 13px; }
    .package-row { grid-template-columns: minmax(260px, 1fr) 86px 82px 82px minmax(110px, 1fr) minmax(160px, auto); padding: 10px 0; border-top: 1px solid #e4e7e3; }
    .package-row:first-child { border-top: 0; }
    .package-title { font-weight: 700; margin-bottom: 3px; }
    .package-source { overflow-wrap: anywhere; }
    .package-actions { justify-content: flex-end; }
    .more-actions { position: relative; border: 0; padding: 0; }
    .more-actions summary { list-style: none; height: 34px; border: 1px solid #b8c1ba; border-radius: 7px; padding: 0 12px; display: inline-flex; align-items: center; background: #fff; color: #25362d; cursor: pointer; font-weight: 650; }
    .more-actions summary::-webkit-details-marker { display: none; }
    .menu-actions { position: absolute; right: 0; top: 40px; z-index: 10; min-width: 170px; display: grid; gap: 6px; padding: 8px; border: 1px solid #d9ded8; border-radius: 8px; background: #fff; box-shadow: 0 8px 24px rgba(0,0,0,.12); }
    .menu-actions button { width: 100%; }
    .job-list { display: grid; gap: 10px; margin-top: 12px; }
    .job { padding: 10px; border: 1px solid #e4e7e3; border-radius: 8px; font-size: 13px; display: grid; gap: 8px; }
    .job-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
    .job-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; }
    .job-field { display: grid; gap: 3px; }
    .job-label { color: #68706a; font-size: 12px; }
    .history-box { margin-top: 12px; border-top: 1px solid #e4e7e3; padding-top: 10px; }
    .history-box summary { cursor: pointer; font-weight: 700; }
    .progress-line { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 6px 0; }
    progress { width: min(360px, 100%); height: 14px; accent-color: #25362d; }
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 14px; }
    .metric { border: 1px solid #e4e7e3; border-radius: 7px; padding: 10px; display: grid; gap: 6px; min-width: 0; }
    .metric.warn { border-color: #d7a844; background: #fff9ea; }
    .metric.danger { border-color: #b85c57; background: #fff0ef; }
    .metric-label { color: #68706a; font-size: 12px; }
    .metric-value { font-weight: 700; overflow-wrap: anywhere; }
    .bar { height: 8px; border-radius: 999px; background: #e8ece8; overflow: hidden; }
    .bar span { display: block; height: 100%; background: #25362d; width: 0; }
    .metric.warn .bar span { background: #b8841c; }
    .metric.danger .bar span { background: #9c3b37; }
    .process-grid { display: grid; gap: 8px; margin-top: 12px; }
    .process-row { display: grid; grid-template-columns: minmax(120px, 1fr) 88px minmax(80px, auto) minmax(80px, auto); gap: 8px; align-items: center; font-size: 13px; }
    .mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }
    .muted { color: #68706a; font-size: 13px; }
    .empty-state { border: 1px dashed #cbd3cc; border-radius: 8px; padding: 14px; color: #68706a; font-size: 13px; background: #fbfcfa; }
    #notice { min-height: 20px; }
    @media (max-width: 760px) {
      .split-panel { grid-template-columns: 1fr; }
      .package-row, .row, .process-row { grid-template-columns: 1fr; }
      .package-actions { justify-content: flex-start; }
      .section-heading { display: grid; }
    }
  </style>
</head>
<body>
  <header>
    <h1>L4D2 Server Manager</h1>
    <button id="logout" class="secondary">Logout</button>
  </header>
  <main>
    <div class="toolbar">
      <button id="refresh">Refresh</button>
      <span id="notice" class="muted"></span>
    </div>
    <section id="overview" class="overview-grid"></section>
    <section id="system" class="card"></section>
    <section class="stack">
      <section>
        <div class="section-heading">
          <div>
            <div class="name">房间管理</div>
            <p class="section-desc">保存默认地图不会影响当前玩家；重启类操作会断开当前房间连接。</p>
          </div>
        </div>
        <section id="rooms" class="grid"></section>
      </section>
    </section>
    <section class="stack">
      <section class="card">
        <div class="section-heading">
          <div>
            <div class="name">搜索地图/Mod</div>
            <p class="section-desc">按名称搜索 Workshop / GameMaps 候选；如果已经知道 Workshop ID，可以用右侧直装。</p>
          </div>
          <span class="pill">Workshop / GameMaps</span>
        </div>
        <div class="tool-grid">
          <div class="tool-panel">
            <div>
              <div class="tool-title">按名称搜索</div>
              <p class="section-desc">适合搜索三方地图、Mod 名称或关键词。</p>
            </div>
            <div class="field">
              <input id="catalog-query" autocomplete="off" placeholder="Run To The Hills">
              <select id="catalog-kind">
                <option value="map">Map</option>
                <option value="mod">Mod</option>
              </select>
              <button id="catalog-search">Search</button>
            </div>
          </div>
          <div class="tool-panel">
            <div>
              <div class="tool-title">直接安装 Workshop ID</div>
              <p class="section-desc">适合已确认 ID 的地图或 Mod，不经过搜索结果选择。</p>
            </div>
            <div class="field">
              <input id="workshop-id" inputmode="numeric" autocomplete="off" placeholder="Workshop ID">
              <select id="workshop-kind">
                <option value="map">Map</option>
                <option value="mod">Mod</option>
              </select>
              <button id="install-workshop">Install</button>
            </div>
          </div>
        </div>
        <div style="margin-top: 16px">
          <div class="section-label">搜索结果</div>
          <div id="catalog-results" class="catalog-results"></div>
        </div>
      </section>
      <section class="card">
        <div class="section-heading">
          <div>
            <div class="name">安装任务</div>
            <p class="section-desc">默认只显示运行中、失败或中断的任务；成功任务折叠在历史记录里。</p>
          </div>
          <span id="job-count" class="pill"></span>
        </div>
        <div class="filters" id="job-filters">
          <button class="filter-button active" data-job-filter="current">当前</button>
          <button class="filter-button" data-job-filter="problem">失败/中断</button>
          <button class="filter-button" data-job-filter="history">成功历史</button>
          <button class="filter-button" data-job-filter="all">全部</button>
        </div>
        <div id="jobs" class="job-list"></div>
      </section>
      <section class="card">
        <div class="section-heading">
          <div>
            <div class="name">地图包管理</div>
            <p class="section-desc">管理已安装或已记录来源的地图包；删除本地文件会保留来源记录，彻底删除会移除记录。</p>
          </div>
          <div class="actions">
            <span id="map-package-count" class="pill"></span>
          </div>
        </div>
        <div class="filters">
          <input id="package-filter-text" autocomplete="off" placeholder="筛选名称或文件名">
          <select id="package-filter-status">
            <option value="all">全部状态</option>
            <option value="enabled">Enabled</option>
            <option value="disabled">Disabled</option>
            <option value="remote">Remote</option>
            <option value="deleted">Deleted</option>
          </select>
          <select id="package-filter-source">
            <option value="all">全部来源</option>
            <option value="workshop">Workshop</option>
            <option value="gamemaps">GameMaps</option>
            <option value="local">Local</option>
          </select>
          <select id="package-filter-record">
            <option value="all">全部记录</option>
            <option value="with">有来源记录</option>
            <option value="without">无来源记录</option>
          </select>
        </div>
        <div id="map-packages" class="rows"></div>
      </section>
      <section class="card">
        <div class="section-heading">
          <div>
            <div class="name">迁移</div>
            <p class="section-desc">默认用 Manifest 迁移来源记录；不行再用 ZIP；只有单文件时才用 VPK。</p>
          </div>
          <span class="pill">推荐 Manifest / 备选 ZIP / 手工 VPK</span>
        </div>
        <div class="decision-list">
          <div><strong>跨服务器迁移：</strong>优先 Manifest，不传输大文件。</div>
          <div><strong>目标服务器无法在线拉取：</strong>用完整 ZIP 兜底。</div>
          <div><strong>手头只有单个文件：</strong>用 VPK 手工导入。</div>
        </div>
        <div class="tool-grid">
          <div class="tool-panel">
            <div>
              <div class="tool-title">推荐方案：Manifest 迁移</div>
              <p class="section-desc">只迁移来源记录和可重装信息，不传输 .vpk 文件本体；适合公网、跨机房和低带宽场景。目标服务器需要能访问对应来源，来源记录也必须有效。</p>
            </div>
            <div class="field">
              <button id="manifest-export">导出来源记录</button>
              <input id="manifest-file" type="file" accept=".json,application/json">
              <button id="manifest-import" class="secondary">导入来源记录</button>
            </div>
          </div>
          <div class="tool-panel">
            <div>
              <div class="tool-title">备选方案：完整 ZIP 迁移</div>
              <p class="section-desc">迁移 .vpk 文件本体和元数据；适合来源失效、目标服务器无法在线拉取或少量应急包。体积较大，受服务器出网带宽影响，不适合大量地图长期批量迁移。</p>
            </div>
            <div class="field">
              <button id="export-selected" class="secondary">导出选中地图包 ZIP</button>
            </div>
            <form id="zip-upload-form" class="field">
              <input id="zip-upload-file" name="file" type="file" accept=".zip">
              <button id="zip-upload-submit" class="secondary" type="submit">导入迁移 ZIP</button>
            </form>
          </div>
          <div class="tool-panel">
            <div>
              <div class="tool-title">手工导入本地文件</div>
              <p class="section-desc">适合已经拿到单个 .vpk 文件时手动补包，不作为主迁移策略。</p>
            </div>
            <form id="vpk-upload-form" class="field">
              <input id="vpk-upload-file" name="file" type="file" accept=".vpk">
              <select id="vpk-upload-kind" name="kind">
                <option value="map">Map package</option>
                <option value="mod">Mod</option>
              </select>
              <button id="vpk-upload-submit" type="submit">导入 VPK</button>
            </form>
          </div>
        </div>
      </section>
      <section class="card">
        <div class="section-heading">
          <div>
            <div class="name">Mod 管理</div>
            <p class="section-desc">启用或禁用非地图 VPK；远端记录可在需要时重新安装。</p>
          </div>
          <span id="addon-count" class="pill"></span>
        </div>
        <div id="addons" class="rows"></div>
      </section>
    </section>
    <section class="maps card">
      <div class="section-heading">
        <div>
          <div class="name">已安装地图</div>
          <p class="section-desc">按战役分组展示当前可选择的章节地图，Other 中是未识别战役的地图。</p>
        </div>
        <span id="map-count" class="pill"></span>
      </div>
      <div id="maps" class="maps-list"></div>
    </section>
  </main>
  <script>
    const overviewEl = document.querySelector("#overview");
    const systemEl = document.querySelector("#system");
    const roomsEl = document.querySelector("#rooms");
    const mapsEl = document.querySelector("#maps");
    const mapCountEl = document.querySelector("#map-count");
    const mapPackageCountEl = document.querySelector("#map-package-count");
    const mapPackagesEl = document.querySelector("#map-packages");
    const addonCountEl = document.querySelector("#addon-count");
    const addonsEl = document.querySelector("#addons");
    const jobsEl = document.querySelector("#jobs");
    const jobCountEl = document.querySelector("#job-count");
    const catalogResultsEl = document.querySelector("#catalog-results");
    const noticeEl = document.querySelector("#notice");
    const exportSelectedButton = document.querySelector("#export-selected");
    const manifestExportButton = document.querySelector("#manifest-export");
    const manifestImportButton = document.querySelector("#manifest-import");
    const zipUploadForm = document.querySelector("#zip-upload-form");
    const vpkUploadForm = document.querySelector("#vpk-upload-form");
    let currentState = null;
    let refreshTimer = null;
    let jobFilter = "current";
    let packageFilters = {text: "", status: "all", source: "all", record: "all"};

    async function apiFetch(input, init = {}) {
      const res = await fetch(input, {credentials: "same-origin", ...init});
      if (res.status === 401) {
        location.href = "/login?expired=1";
        throw new Error("Session expired");
      }
      return res;
    }

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }

    function renderOverview(data) {
      const rooms = data.rooms || [];
      const addons = data.addons || [];
      const jobs = data.jobs || [];
      const onlineRooms = rooms.filter(room => room.active === "active" && room.port_listening).length;
      const runningJobs = jobs.filter(job => job.status === "queued" || job.status === "running").length;
      const problemJobs = jobs.filter(job => job.status === "failed" || job.status === "interrupted").length;
      const mapPackages = addons.filter(addon => addon.kind === "map").length;
      const disabledMods = addons.filter(addon => addon.kind !== "map" && addon.state === "disabled").length;
      const items = [
        ["在线房间", `${onlineRooms}/${rooms.length}`],
        ["运行中任务", runningJobs],
        ["失败/中断任务", problemJobs],
        ["地图包", mapPackages],
        ["禁用 Mod", disabledMods],
      ];
      overviewEl.innerHTML = items.map(([label, value]) => `<div class="overview-item">
        <div class="overview-label">${esc(label)}</div>
        <div class="overview-value">${esc(value)}</div>
      </div>`).join("");
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
            <summary>危险操作</summary>
            <div class="menu-actions">
              <div class="muted">会重启房间，当前玩家可能断开。</div>
              <button class="danger" data-save-restart="${room.id}">Save & Restart</button>
              <button class="danger" data-restart="${room.id}">Restart Room</button>
            </div>
          </details>
        </div>
      </article>`;
    }

    function renderAddons(addons) {
      const mods = addons.filter(addon => addon.kind !== "map");
      addonCountEl.textContent = `${mods.length} vpks`;
      if (!mods.length) {
        addonsEl.innerHTML = `<div class="empty-state">当前没有可管理的非地图 VPK。上传或安装 Mod 后会出现在这里。</div>`;
        return;
      }
      addonsEl.innerHTML = mods.map(addon => {
        const remote = addon.state === "remote";
        const target = addon.state === "enabled" ? "disabled" : "enabled";
        const label = addon.state === "enabled" ? "Disable" : "Enable";
        const sizeMb = (addon.size / 1024 / 1024).toFixed(1);
        const openLink = addon.url ? `<a href="${esc(addon.url)}" target="_blank" rel="noreferrer">Open</a>` : "";
        const install = remote && addon.reinstallable ? `<button data-manifest-install="${esc(addon.filename)}">按来源重新安装</button>` : "";
        const remove = remote ? `<button class="secondary" data-manifest-remove="${esc(addon.filename)}">删除来源记录</button>` : "";
        const stateButton = remote ? "" : `<button data-addon="${esc(addon.filename)}" data-addon-state="${target}">${label}</button>`;
        const sizeText = remote ? "not downloaded" : `${sizeMb} MB`;
        return `<div class="row">
          <label class="actions" style="gap: 6px">
            <input type="checkbox" data-manifest-select="${esc(addon.filename)}">
            <span class="mono">${esc(addon.filename)}</span>
          </label>
          <div>${addon.state}</div>
          <div>${sizeText}</div>
          <div class="actions">${openLink}${install}${remove}${stateButton}</div>
        </div>`;
      }).join("");
    }

    function renderMapPackages(addons) {
      const packages = addons.filter(addon => addon.kind === "map");
      const filtered = packages.filter(packageMatchesFilters);
      mapPackageCountEl.textContent = `${filtered.length}/${packages.length} vpks`;
      if (!packages.length) {
        mapPackagesEl.innerHTML = `<div class="empty-state">当前没有地图包。可以先搜索 Workshop 地图，导入来源记录，或手工导入 VPK。</div>`;
        return;
      }
      if (!filtered.length) {
        mapPackagesEl.innerHTML = `<div class="empty-state">没有符合筛选条件的地图包。可以清空名称、状态或来源筛选。</div>`;
        return;
      }
      mapPackagesEl.innerHTML = filtered.map(addon => {
        const target = addon.state === "enabled" ? "disabled" : "enabled";
        const label = addon.state === "enabled" ? "Disable" : "Enable";
        const sizeMb = (addon.size / 1024 / 1024).toFixed(1);
        const mapCount = addon.maps && addon.maps.length ? addon.maps.length : 0;
        const maps = mapCount ? addon.maps.join(", ") : "mission only";
        const deleted = addon.state === "deleted";
        const remote = addon.state === "remote";
        const openLink = addon.url ? `<a href="${esc(addon.url)}" target="_blank" rel="noreferrer">Open</a>` : "";
        const exportLink = deleted || remote ? "" : `<button class="secondary" data-package-export="${esc(addon.filename)}">Export ZIP</button>`;
        const reinstall = !remote && addon.reinstallable ? `<button data-package-reinstall="${esc(addon.filename)}">Reinstall</button>` : "";
        const installRemote = remote && addon.reinstallable ? `<button data-manifest-install="${esc(addon.filename)}">按来源重新安装</button>` : "";
        const removeRemote = remote ? `<button class="secondary" data-manifest-remove="${esc(addon.filename)}">删除来源记录</button>` : "";
        const disable = deleted ? "" : `<button class="secondary" data-addon="${esc(addon.filename)}" data-addon-state="${target}">${label}</button>`;
        const softDelete = deleted ? "" : `<button class="danger" data-package-delete="${esc(addon.filename)}" data-package-mode="soft">删除本地文件</button>`;
        const purgeDelete = `<button class="danger" data-package-delete="${esc(addon.filename)}" data-package-mode="purge">彻底删除</button>`;
        const source = addon.source && addon.catalog_id ? `${addon.source} ${addon.catalog_id}` : "local package";
        const title = addon.title && addon.title !== addon.filename ? addon.title : addon.filename;
        const statusText = remote ? "remote" : (deleted ? "deleted" : addon.state);
        const sizeText = remote ? "not downloaded" : (deleted ? "removed" : `${sizeMb} MB`);
        const moreActions = remote ? "" : [disable, softDelete, purgeDelete].filter(Boolean).join("");
        const checkbox = deleted || remote
          ? `<input type="checkbox" data-manifest-select="${esc(addon.filename)}">`
          : `<input type="checkbox" data-package-select="${esc(addon.filename)}" data-manifest-select="${esc(addon.filename)}">`;
        const moreMenu = moreActions ? `<details class="more-actions">
          <summary>More</summary>
          <div class="menu-actions">${moreActions}</div>
        </details>` : "";
        return `<div class="row package-row">
          <div>
            <label class="actions" style="gap: 6px">
              ${checkbox}
              <span class="package-title">${esc(title)}</span>
            </label>
            <div class="muted mono">${esc(addon.filename)}</div>
            <div class="muted mono">${esc(maps)}</div>
          </div>
          <div>${statusText}</div>
          <div>${mapCount || "-"}</div>
          <div>${sizeText}</div>
          <div class="muted package-source">${esc(source)}</div>
          <div class="actions package-actions">${openLink}${exportLink}${installRemote}${removeRemote}${reinstall}${moreMenu}</div>
        </div>`;
      }).join("");
    }

    function packageMatchesFilters(addon) {
      const text = packageFilters.text.toLowerCase();
      const source = addon.source || "local";
      const hasRecord = Boolean(addon.source && addon.catalog_id);
      if (text) {
        const haystack = [addon.title, addon.filename, addon.catalog_id, (addon.maps || []).join(" ")].join(" ").toLowerCase();
        if (!haystack.includes(text)) return false;
      }
      if (packageFilters.status !== "all" && addon.state !== packageFilters.status) return false;
      if (packageFilters.source !== "all" && source !== packageFilters.source) return false;
      if (packageFilters.record === "with" && !hasRecord) return false;
      if (packageFilters.record === "without" && hasRecord) return false;
      return true;
    }

    function renderJobs(jobs) {
      const currentJobs = jobs.filter(job => ["queued", "running", "failed", "interrupted"].includes(job.status));
      const problemJobs = jobs.filter(job => ["failed", "interrupted"].includes(job.status));
      const historyJobs = jobs.filter(job => job.status === "succeeded");
      const filtered = jobFilter === "current" ? currentJobs
        : jobFilter === "problem" ? problemJobs
        : jobFilter === "history" ? historyJobs.slice(0, 5)
        : jobs;
      jobCountEl.textContent = `${currentJobs.length} current / ${problemJobs.length} problem`;
      document.querySelectorAll("[data-job-filter]").forEach(button => {
        button.classList.toggle("active", button.dataset.jobFilter === jobFilter);
      });
      if (!jobs.length) {
        jobsEl.innerHTML = `<div class="empty-state">当前没有安装、导出或导入任务。</div>`;
        return;
      }
      const emptyCopy = jobFilter === "current"
        ? "当前没有运行中、失败或中断任务。成功任务已折叠到历史记录。"
        : jobFilter === "problem"
          ? "当前没有失败或中断任务。"
          : jobFilter === "history"
            ? "还没有成功任务历史。"
            : "没有符合条件的任务。";
      const body = filtered.length ? filtered.map(jobCard).join("") : `<div class="empty-state">${emptyCopy}</div>`;
      const history = jobFilter === "current" && historyJobs.length
        ? `<details class="history-box">
            <summary>History · 最近 ${Math.min(5, historyJobs.length)} 条成功任务</summary>
            <div class="job-list">${historyJobs.slice(0, 5).map(jobCard).join("")}</div>
          </details>`
        : "";
      jobsEl.innerHTML = body + history;
    }

    function jobCard(job) {
      const type = job.type || job.source || "workshop";
      const target = job.title || job.catalog_id || job.workshop_id || job.export_filename || "unknown";
      const idText = job.catalog_id || job.workshop_id || job.export_filename || job.id || "";
      const canCancel = job.status === "queued" || job.status === "running";
      const download = job.type === "export" && job.status === "succeeded" && job.download_url
        ? `<a href="${esc(job.download_url)}">Download</a>`
        : "";
      const statusClass = job.status === "succeeded" ? "ok"
        : ["failed", "interrupted"].includes(job.status) ? "danger"
        : ["queued", "running"].includes(job.status) ? "warn"
        : "";
      const packages = job.install_ids && job.install_ids.length > 1
        ? `<div class="muted mono">packages ${job.install_ids.map(esc).join(", ")}</div>`
        : "";
      return `<div class="job">
        <div class="job-head">
          <strong>${esc(target)}</strong>
          <div class="actions">
            <span class="pill ${statusClass}">${esc(job.status)}</span>
            ${canCancel ? `<button class="secondary" data-job-cancel="${esc(job.id)}">Cancel</button>` : ""}
            ${download}
          </div>
        </div>
        <div class="job-grid">
          <div class="job-field"><span class="job-label">任务类型</span><span>${esc(type)} ${esc(job.kind || "")}</span></div>
          <div class="job-field"><span class="job-label">目标</span><span class="mono">${esc(idText)}</span></div>
          <div class="job-field"><span class="job-label">阶段</span><span>${esc(job.stage || "done")}</span></div>
        </div>
        ${packages}
        ${jobProgress(job)}
        <div class="muted">${esc(job.message || "")}</div>
      </div>`;
    }

    function formatBytes(value) {
      const size = Number(value || 0);
      if (!size) return "0 B";
      const units = ["B", "KB", "MB", "GB"];
      let current = size;
      let unit = 0;
      while (current >= 1024 && unit < units.length - 1) {
        current /= 1024;
        unit += 1;
      }
      return unit === 0 ? `${current} ${units[unit]}` : `${current.toFixed(1)} ${units[unit]}`;
    }

    function formatPercent(value) {
      if (value === null || value === undefined || value === "") return "unknown";
      const number = Number(value);
      return Number.isFinite(number) ? `${number.toFixed(1)}%` : "unknown";
    }

    function riskClass(percent, warn, danger) {
      if (percent === null || percent === undefined || percent === "") return "";
      const value = Number(percent);
      if (!Number.isFinite(value)) return "";
      if (value >= danger) return "danger";
      if (value >= warn) return "warn";
      return "";
    }

    function metricCard(label, value, detail, percent, warn = 80, danger = 92) {
      const hasPercent = percent !== null && percent !== undefined && percent !== "" && Number.isFinite(Number(percent));
      const bounded = hasPercent ? Math.max(0, Math.min(100, Number(percent))) : 0;
      const cls = riskClass(percent, warn, danger);
      return `<div class="metric ${cls}">
        <div class="metric-label">${esc(label)}</div>
        <div class="metric-value">${esc(value)}</div>
        ${detail ? `<div class="muted">${esc(detail)}</div>` : ""}
        ${hasPercent ? `<div class="bar"><span style="width:${bounded}%"></span></div>` : ""}
      </div>`;
    }

    function renderSystem(system) {
      if (!system) {
        systemEl.innerHTML = `<div class="muted">System metrics unavailable.</div>`;
        return;
      }
      const cpu = system.cpu || {};
      const memory = system.memory || {};
      const swap = system.swap || {};
      const uptime = system.uptime || {};
      const load = Array.isArray(cpu.load_average) ? cpu.load_average.filter(value => value !== null).join(", ") : "unknown";
      const metrics = [
        metricCard("CPU", formatPercent(cpu.percent), `${cpu.cores || 0} cores · load ${load}`, cpu.percent, 75, 90),
        metricCard(
          "Memory",
          `${formatBytes(memory.used)} / ${formatBytes(memory.total)}`,
          `${formatBytes(memory.available)} available`,
          memory.percent,
          75,
          90
        ),
        metricCard(
          "Swap",
          `${formatBytes(swap.used)} / ${formatBytes(swap.total)}`,
          `${formatBytes(swap.free)} free`,
          swap.percent,
          40,
          75
        ),
        metricCard("Uptime", uptime.display || "unknown", "", null),
      ];
      const disks = (system.disk || []).map(disk =>
        metricCard(
          `Disk ${disk.label || disk.path}`,
          `${formatBytes(disk.used)} / ${formatBytes(disk.total)}`,
          `${formatBytes(disk.free)} free · ${disk.path}`,
          disk.percent,
          80,
          92
        )
      ).join("");
      const processes = (system.processes || []).map(proc => {
        const active = proc.active === "active";
        return `<div class="process-row">
          <div><strong>${esc(proc.label || proc.service)}</strong><div class="muted mono">${esc(proc.service)}</div></div>
          <span class="pill ${active ? "ok" : ""}">${esc(proc.active || "unknown")}</span>
          <div>${formatBytes(proc.memory_current)}</div>
          <div class="muted">${proc.cpu_usage_nsec !== null && proc.cpu_usage_nsec !== undefined ? `${Math.round(proc.cpu_usage_nsec / 1000000000)}s CPU` : "CPU unknown"}</div>
        </div>`;
      }).join("");
      systemEl.innerHTML = `<div class="room-head">
        <div class="name">Server Performance</div>
        <span class="pill">live</span>
      </div>
      <div class="metric-grid">${metrics.join("")}${disks}</div>
      <div class="process-grid">${processes}</div>`;
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
        catalogResultsEl.innerHTML = `<div class="empty-state">没有找到匹配结果。可以换一个关键词，或在右侧直接输入 Workshop ID 安装。</div>`;
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
      const res = await apiFetch("/api/state");
      if (!res.ok) throw new Error("Failed to load state");
      const data = await res.json();
      currentState = data;
      renderOverview(data);
      renderSystem(data.system);
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
      const res = await apiFetch("/api/restart", {
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
      const res = await apiFetch("/api/default-map", {
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
      const kind = document.querySelector("#workshop-kind").value;
      noticeEl.textContent = "Queueing install...";
      const res = await apiFetch("/api/workshop/install", {
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
      const res = await apiFetch(`/api/catalog/search?${new URLSearchParams({query, kind})}`);
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
      const res = await apiFetch("/api/catalog/install", {
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
      const res = await apiFetch("/api/addon/state", {
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
        ? `彻底删除 ${filename}？这会删除本地文件和来源记录，之后需要重新搜索或重新导入才能安装回来。`
        : `删除本地文件 ${filename}？这会移除本地 VPK 和提取文件，但保留来源记录，之后可以用 Reinstall 安装回来。`;
      if (!confirm(prompt)) return;
      noticeEl.textContent = "Deleting package...";
      const res = await apiFetch("/api/map-package/delete", {
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
      const res = await apiFetch("/api/map-package/reinstall", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({filename})
      });
      const data = await res.json();
      noticeEl.textContent = data.message;
      await loadState();
    }

    async function cancelJob(jobId) {
      noticeEl.textContent = "Cancelling job...";
      const res = await apiFetch("/api/job/cancel", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({job_id: jobId})
      });
      const data = await res.json();
      noticeEl.textContent = data.message;
      await loadState();
    }

    async function exportPackages(selected) {
      noticeEl.textContent = "Queueing export...";
      const body = new URLSearchParams();
      selected.forEach(filename => body.append("filename", filename));
      const res = await apiFetch("/api/map-package/export-job", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body
      });
      const data = await res.json();
      noticeEl.textContent = data.message || (res.ok ? "Export queued" : "Export failed");
      if (res.ok) await loadState();
    }

    async function exportSelectedPackages() {
      const selected = [...document.querySelectorAll("[data-package-select]:checked")].map(input => input.dataset.packageSelect);
      if (!selected.length) {
        noticeEl.textContent = "Select at least one map package.";
        return;
      }
      await exportPackages(selected);
    }

    function selectedManifestRecords() {
      return [...new Set([...document.querySelectorAll("[data-manifest-select]:checked")].map(input => input.dataset.manifestSelect))];
    }

    async function exportManifestSelected() {
      const selected = selectedManifestRecords();
      if (!selected.length) {
        noticeEl.textContent = "请先选择至少一个地图或 Mod 来源记录。";
        return;
      }
      noticeEl.textContent = "正在准备来源记录...";
      const body = new URLSearchParams();
      selected.forEach(filename => body.append("filename", filename));
      const res = await apiFetch("/api/manifest/export", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body
      });
      if (!res.ok) {
        const data = await res.json();
        noticeEl.textContent = data.message || "来源记录导出失败";
        return;
      }
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="([^"]+)"/);
      const filename = match ? match[1] : "l4d2-manager-manifest.json";
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      noticeEl.textContent = "来源记录已导出。";
    }

    async function importManifest() {
      const file = document.querySelector("#manifest-file").files[0];
      if (!file) {
        noticeEl.textContent = "请先选择来源记录 .json 文件。";
        return;
      }
      const form = new FormData();
      form.append("file", file);
      noticeEl.textContent = "正在导入来源记录...";
      const res = await apiFetch("/api/manifest/import", {method: "POST", body: form});
      const data = await res.json();
      noticeEl.textContent = data.message || (res.ok ? "来源记录已导入" : "来源记录导入失败");
      if (res.ok) {
        document.querySelector("#manifest-file").value = "";
        await loadState();
      }
    }

    async function installManifestRecord(filename) {
      noticeEl.textContent = "正在按来源创建重新安装任务...";
      const res = await apiFetch("/api/manifest/install", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({filename})
      });
      const data = await res.json();
      noticeEl.textContent = data.message;
      await loadState();
    }

    async function removeManifestRecord(filename) {
      if (!confirm(`删除 ${filename} 的来源记录？这不会删除本地 VPK 文件，但之后需要重新搜索或重新导入来源记录。`)) return;
      noticeEl.textContent = "正在删除来源记录...";
      const res = await apiFetch("/api/manifest/remove-record", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({filename})
      });
      const data = await res.json();
      noticeEl.textContent = data.message;
      await loadState();
    }

    async function uploadZipImport(event) {
      event.preventDefault();
      const file = document.querySelector("#zip-upload-file").files[0];
      if (!file) {
        noticeEl.textContent = "请先选择迁移 ZIP 文件。";
        return;
      }
      const form = new FormData();
      form.append("file", file);
      form.append("kind", "map");
      noticeEl.textContent = "正在导入迁移 ZIP...";
      const res = await apiFetch("/api/upload", {method: "POST", body: form});
      const data = await res.json();
      noticeEl.textContent = data.message;
      if (res.ok) {
        document.querySelector("#zip-upload-file").value = "";
        await loadState();
      }
    }

    async function uploadVpkImport(event) {
      event.preventDefault();
      const file = document.querySelector("#vpk-upload-file").files[0];
      if (!file) {
        noticeEl.textContent = "请先选择单个 .vpk 文件。";
        return;
      }
      const form = new FormData();
      form.append("file", file);
      form.append("kind", document.querySelector("#vpk-upload-kind").value);
      noticeEl.textContent = "正在导入 VPK...";
      const res = await apiFetch("/api/upload", {method: "POST", body: form});
      const data = await res.json();
      noticeEl.textContent = data.message;
      if (res.ok) {
        document.querySelector("#vpk-upload-file").value = "";
        await loadState();
      }
    }

    async function logout() {
      try {
        await apiFetch("/api/logout", {method: "POST"});
      } finally {
        location.href = "/login";
      }
    }

    document.querySelector("#logout").addEventListener("click", logout);
    document.querySelector("#refresh").addEventListener("click", loadState);
    document.querySelector("#job-filters").addEventListener("click", event => {
      const selected = event.target.dataset.jobFilter;
      if (!selected) return;
      jobFilter = selected;
      renderJobs((currentState && currentState.jobs) || []);
    });
    document.querySelector("#package-filter-text").addEventListener("input", event => {
      packageFilters.text = event.target.value.trim();
      renderMapPackages((currentState && currentState.addons) || []);
    });
    document.querySelector("#package-filter-status").addEventListener("change", event => {
      packageFilters.status = event.target.value;
      renderMapPackages((currentState && currentState.addons) || []);
    });
    document.querySelector("#package-filter-source").addEventListener("change", event => {
      packageFilters.source = event.target.value;
      renderMapPackages((currentState && currentState.addons) || []);
    });
    document.querySelector("#package-filter-record").addEventListener("change", event => {
      packageFilters.record = event.target.value;
      renderMapPackages((currentState && currentState.addons) || []);
    });
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
    jobsEl.addEventListener("click", event => {
      const jobId = event.target.dataset.jobCancel;
      if (!jobId) return;
      event.target.disabled = true;
      cancelJob(jobId).finally(() => event.target.disabled = false);
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
      const manifestInstall = event.target.dataset.manifestInstall;
      const manifestRemove = event.target.dataset.manifestRemove;
      if (filename && state) {
        event.target.disabled = true;
        setAddonState(filename, state).finally(() => event.target.disabled = false);
      }
      if (manifestInstall) {
        event.target.disabled = true;
        installManifestRecord(manifestInstall).finally(() => event.target.disabled = false);
      }
      if (manifestRemove) {
        event.target.disabled = true;
        removeManifestRecord(manifestRemove).finally(() => event.target.disabled = false);
      }
    });
    mapPackagesEl.addEventListener("click", event => {
      const filename = event.target.dataset.addon;
      const state = event.target.dataset.addonState;
      const deleteFilename = event.target.dataset.packageDelete;
      const deleteMode = event.target.dataset.packageMode;
      const reinstallFilename = event.target.dataset.packageReinstall;
      const exportFilename = event.target.dataset.packageExport;
      const manifestInstall = event.target.dataset.manifestInstall;
      const manifestRemove = event.target.dataset.manifestRemove;
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
      if (exportFilename) {
        event.target.disabled = true;
        exportPackages([exportFilename]).finally(() => event.target.disabled = false);
      }
      if (manifestInstall) {
        event.target.disabled = true;
        installManifestRecord(manifestInstall).finally(() => event.target.disabled = false);
      }
      if (manifestRemove) {
        event.target.disabled = true;
        removeManifestRecord(manifestRemove).finally(() => event.target.disabled = false);
      }
    });
    exportSelectedButton.addEventListener("click", event => {
      event.target.disabled = true;
      exportSelectedPackages().finally(() => event.target.disabled = false);
    });
    manifestExportButton.addEventListener("click", event => {
      event.target.disabled = true;
      exportManifestSelected().finally(() => event.target.disabled = false);
    });
    manifestImportButton.addEventListener("click", event => {
      event.target.disabled = true;
      importManifest().finally(() => event.target.disabled = false);
    });
    zipUploadForm.addEventListener("submit", event => {
      const button = document.querySelector("#zip-upload-submit");
      button.disabled = true;
      uploadZipImport(event).finally(() => button.disabled = false);
    });
    vpkUploadForm.addEventListener("submit", event => {
      const button = document.querySelector("#vpk-upload-submit");
      button.disabled = true;
      uploadVpkImport(event).finally(() => button.disabled = false);
    });
    loadState().catch(err => noticeEl.textContent = err.message);
  </script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "L4D2Manager/0.1"

    def basic_authenticated(self):
        if not ADMIN_PASSWORD:
            return False
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header[6:]).decode("utf-8")
        except Exception:
            return False
        username, separator, password = decoded.partition(":")
        return bool(separator) and check_credentials(username, password)

    def session_token(self):
        return session_from_cookie(self.headers.get("Cookie", ""))

    def authenticated(self):
        return self.basic_authenticated() or bool(self.session_token())

    def require_auth(self):
        payload = json.dumps({"ok": False, "message": "Authentication required"}).encode("utf-8")
        self.send_response(401)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_html(self, status, body, headers=None):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, status, body, headers=None):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def send_json_download(self, filename, body):
        payload = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/login":
            if self.authenticated():
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_html(200, render_login_page())
            return
        if not self.authenticated():
            if parsed.path == "/" or parsed.path == "/index.html":
                self.send_html(200, render_login_page())
            else:
                self.require_auth()
            return
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
        if parsed.path == "/api/map-package/export":
            fields = parse_qs(parsed.query)
            filename = fields.get("filename", [""])[0]
            result = export_map_packages([filename])
            if not result["ok"]:
                self.send_json(400, result)
                return
            send_zip_file(self, result["path"], result["filename"])
            return
        if parsed.path == "/api/export/download":
            fields = parse_qs(parsed.query)
            job_id = fields.get("job_id", [""])[0]
            result = export_download_for_job(job_id)
            if not result["ok"]:
                self.send_json(400, result)
                return
            stream_zip_file(self, result["path"], result["filename"], result["job_id"])
            return
        self.send_error(404)

    def do_POST(self):
        if self.path == "/api/login":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            fields = parse_qs(body)
            username = fields.get("username", [""])[0]
            password = fields.get("password", [""])[0]
            if not check_credentials(username, password):
                self.send_json(401, {"ok": False, "message": "Invalid username or password"})
                return
            token = create_session(username)
            self.send_json(
                200,
                {"ok": True, "message": "Signed in"},
                {"Set-Cookie": session_cookie_header(token)},
            )
            return
        if self.path == "/api/logout":
            destroy_session(self.session_token())
            self.send_json(
                200,
                {"ok": True, "message": "Signed out"},
                {"Set-Cookie": session_cookie_header("", max_age=0)},
            )
            return
        if not self.authenticated():
            self.require_auth()
            return
        if self.path == "/api/upload":
            handle_upload_request(self)
            return
        if self.path == "/api/manifest/import":
            handle_manifest_import_request(self)
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
        if self.path == "/api/job/cancel":
            job_id = fields.get("job_id", [""])[0]
            result = cancel_job(job_id)
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
        if self.path == "/api/map-package/export-job":
            filenames = fields.get("filename", [])
            if len(filenames) == 1 and "," in filenames[0]:
                filenames = [value for value in filenames[0].split(",") if value]
            result = create_export_job(filenames)
            self.send_json(200 if result["ok"] else 400, result)
            return
        if self.path == "/api/map-package/export-bulk":
            filenames = fields.get("filename", [])
            if len(filenames) == 1 and "," in filenames[0]:
                filenames = [value for value in filenames[0].split(",") if value]
            result = export_map_packages(filenames)
            if not result["ok"]:
                self.send_json(400, result)
                return
            send_zip_file(self, result["path"], result["filename"])
            return
        if self.path == "/api/manifest/export":
            filenames = fields.get("filename", [])
            if len(filenames) == 1 and "," in filenames[0]:
                filenames = [value for value in filenames[0].split(",") if value]
            result = create_manifest(filenames)
            if not result["ok"]:
                self.send_json(400, result)
                return
            self.send_json_download(f"l4d2-manager-manifest-{int(time.time())}.json", result["manifest"])
            return
        if self.path == "/api/manifest/install":
            filenames = fields.get("filename", [])
            if len(filenames) == 1 and "," in filenames[0]:
                filenames = [value for value in filenames[0].split(",") if value]
            result = install_manifest_records(filenames)
            self.send_json(200 if result["ok"] else 400, result)
            return
        if self.path == "/api/manifest/remove-record":
            filename = fields.get("filename", [""])[0]
            result = remove_manifest_record(filename)
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
