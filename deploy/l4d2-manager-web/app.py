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
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs


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
ADMIN_USER = os.environ.get("L4D2_WEB_USER", "admin")
ADMIN_PASSWORD = os.environ.get("L4D2_WEB_PASSWORD", "")
AUTH_REALM = "L4D2 Manager"
WORKSHOP_ID_RE = re.compile(r"^[0-9]{4,20}$")
ADDON_RE = re.compile(r"^[A-Za-z0-9_. -]{1,180}\.vpk$")
JOBS = {}
JOBS_LOCK = threading.Lock()
EXCLUDED_CAMPAIGN_MAPS = {"c5m1_waterfront_sndscape"}

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
                mission = parsed.get("mission", {})
                modes = mission.get("modes") if isinstance(mission, dict) else {}
                coop = modes.get("coop") if isinstance(modes, dict) else {}
                if not isinstance(coop, dict):
                    continue
                for chapter in coop.values():
                    if isinstance(chapter, dict) and chapter.get("Map"):
                        maps.add(chapter["Map"])
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


def campaign_from_mission_text(text, fallback, installed_maps):
    try:
        parsed = parse_keyvalues(text)
    except Exception:
        return None
    mission = parsed.get("mission")
    if not isinstance(mission, dict):
        return None
    modes = mission.get("modes")
    coop = modes.get("coop") if isinstance(modes, dict) else None
    if not isinstance(coop, dict):
        return None
    title = mission.get("DisplayTitle") or mission.get("Name") or fallback
    maps = []
    for chapter_key in sorted(coop, key=lambda value: int(value) if value.isdigit() else 9999):
        entry = coop[chapter_key]
        if not isinstance(entry, dict):
            continue
        map_name = entry.get("Map")
        if map_name not in installed_maps:
            continue
        maps.append(
            {
                "name": map_name,
                "display_name": entry.get("DisplayName") or map_name,
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
    return campaigns


def build_campaigns():
    installed_maps = set(available_maps()) - EXCLUDED_CAMPAIGN_MAPS
    campaigns = []
    assigned = set()
    for campaign in OFFICIAL_CAMPAIGNS:
        maps = [dict(item) for item in campaign["maps"] if item["name"] in installed_maps]
        if maps:
            copy = dict(campaign)
            copy["maps"] = maps
            campaigns.append(copy)
            assigned.update(item["name"] for item in maps)
    for campaign in parse_mission_campaigns(installed_maps):
        maps = [item for item in campaign["maps"] if item["name"] not in assigned]
        if maps:
            copy = dict(campaign)
            copy["maps"] = maps
            campaigns.append(copy)
            assigned.update(item["name"] for item in maps)
    other_maps = [
        {"name": name, "display_name": name, "chapter": index + 1}
        for index, name in enumerate(sorted(installed_maps - assigned))
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
    for item in vpk_inventory():
        try:
            modified_at = int(item["path"].stat().st_mtime)
        except OSError:
            modified_at = 0
        addons.append(
            {
                "filename": item["filename"],
                "state": item["state"],
                "size": item["size"],
                "modified_at": modified_at,
                "kind": "map" if item["is_map_package"] else "mod",
                "maps": item["maps"],
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
    with JOBS_LOCK:
        return sorted(JOBS.values(), key=lambda job: job["created_at"], reverse=True)[:20]


def update_job(job_id, **fields):
    with JOBS_LOCK:
        JOBS[job_id].update(fields)


def install_workshop_job(job_id, kind, workshop_id):
    update_job(job_id, status="running", message="Installing...")
    result = run_cmd(
        ["/usr/bin/sudo", "-n", "/usr/local/bin/l4d2-webctl", "install-workshop", kind, workshop_id],
        timeout=1800,
    )
    message = result["stdout"] or result["stderr"] or "Install finished"
    update_job(
        job_id,
        status="succeeded" if result["ok"] else "failed",
        message=message[-2000:],
        finished_at=int(time.time()),
    )


def create_install_job(kind, workshop_id):
    if kind not in {"map", "mod"}:
        return {"ok": False, "message": "Kind must be map or mod"}
    if not WORKSHOP_ID_RE.match(workshop_id):
        return {"ok": False, "message": "Workshop ID must be numeric"}
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "kind": kind,
        "workshop_id": workshop_id,
        "status": "queued",
        "message": "Queued",
        "created_at": int(time.time()),
        "finished_at": None,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    thread = threading.Thread(
        target=install_workshop_job,
        args=(job_id, kind, workshop_id),
        daemon=True,
    )
    thread.start()
    return {"ok": True, "message": "Install queued", "job": job}


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
    main { max-width: 1080px; margin: 0 auto; padding: 24px; }
    .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
    .card { background: #fff; border: 1px solid #d9ded8; border-radius: 8px; padding: 16px; }
    .room-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .name { font-weight: 700; font-size: 18px; }
    .pill { border-radius: 999px; padding: 4px 9px; font-size: 12px; background: #e8ece8; color: #2c3b33; }
    .pill.ok { background: #dff1e5; color: #11602e; }
    dl { display: grid; grid-template-columns: 112px 1fr; gap: 8px 12px; margin: 16px 0; font-size: 14px; }
    dt { color: #68706a; }
    dd { margin: 0; overflow-wrap: anywhere; }
    button { height: 36px; border: 1px solid #b8c1ba; background: #25362d; color: #fff; border-radius: 7px; padding: 0 13px; cursor: pointer; }
    button:disabled { opacity: .55; cursor: wait; }
    select { height: 36px; min-width: 150px; max-width: 100%; border: 1px solid #b8c1ba; border-radius: 7px; background: #fff; padding: 0 9px; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .field { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    input { height: 34px; min-width: 180px; border: 1px solid #b8c1ba; border-radius: 7px; background: #fff; padding: 0 9px; }
    .toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; }
    .maps { margin-top: 16px; }
    .maps-list { display: grid; gap: 10px; font-size: 13px; line-height: 1.8; }
    details { border-top: 1px solid #e4e7e3; padding-top: 8px; }
    details:first-child { border-top: 0; padding-top: 0; }
    summary { cursor: pointer; font-weight: 650; }
    .chapter-list { columns: 2 220px; margin-top: 6px; }
    .stack { display: grid; gap: 16px; margin-top: 16px; }
    .rows { display: grid; gap: 8px; margin-top: 12px; }
    .row { display: grid; grid-template-columns: minmax(150px, 1fr) 88px 86px 130px; gap: 8px; align-items: center; font-size: 13px; }
    .job { padding: 8px 0; border-top: 1px solid #e4e7e3; font-size: 13px; }
    .mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }
    .muted { color: #68706a; font-size: 13px; }
    #notice { min-height: 20px; }
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
          <div class="name">Workshop Install</div>
          <span class="pill">Map / Mod</span>
        </div>
        <div class="field" style="margin-top: 14px">
          <input id="workshop-id" inputmode="numeric" autocomplete="off" placeholder="Workshop ID">
          <select id="workshop-kind">
            <option value="map">Map</option>
            <option value="mod">Mod</option>
          </select>
          <button id="install-workshop">Install</button>
        </div>
        <div id="jobs" style="margin-top: 12px"></div>
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
    const noticeEl = document.querySelector("#notice");
    let currentState = null;

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
        <div class="actions">
          <select data-campaign-select="${room.id}"></select>
          <select data-map-select="${room.id}"></select>
          <button data-save="${room.id}">Save</button>
          <button data-save-restart="${room.id}">Save & Restart</button>
          <button data-restart="${room.id}">Restart</button>
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
        return `<div class="row">
          <div><div class="mono">${esc(addon.filename)}</div><div class="muted">${esc(maps)}</div></div>
          <div>${addon.state}</div>
          <div>${sizeMb} MB</div>
          <button data-addon="${esc(addon.filename)}" data-addon-state="${target}">${label}</button>
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
        <span class="mono">${esc(job.kind)} ${esc(job.workshop_id)}</span>
        <div class="muted">${esc(job.message)}</div>
      </div>`).join("");
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
      const kind = document.querySelector("#workshop-kind").value;
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

    document.querySelector("#refresh").addEventListener("click", loadState);
    document.querySelector("#install-workshop").addEventListener("click", event => {
      event.target.disabled = true;
      installWorkshop().finally(() => event.target.disabled = false);
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
      if (!filename || !state) return;
      event.target.disabled = true;
      setAddonState(filename, state).finally(() => event.target.disabled = false);
    });
    loadState().catch(err => noticeEl.textContent = err.message);
    setInterval(() => loadState().catch(() => {}), 30000);
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
        if self.path == "/" or self.path == "/index.html":
            payload = render_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/api/state":
            self.send_json(200, snapshot())
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
        if self.path == "/api/addon/state":
            filename = fields.get("filename", [""])[0]
            state = fields.get("state", [""])[0]
            result = set_addon_state(filename, state)
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
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Serving L4D2 manager on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
