#!/usr/bin/env python3
import os
import struct
import sys
from pathlib import Path


SIGNATURE = 0x55AA1234
INLINE_ARCHIVE = 0x7FFF
ALLOWED_TOP_LEVEL = {"maps", "missions", "materials", "models", "sound", "scripts"}


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def read_null_string(handle):
    data = []
    while True:
        char = handle.read(1)
        if not char or char == b"\x00":
            break
        data.append(char)
    return b"".join(data).decode("utf-8", errors="ignore")


def safe_relative_path(path):
    normalized = Path(path.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        return None
    if not normalized.parts or normalized.parts[0].lower() not in ALLOWED_TOP_LEVEL:
        return None
    return normalized


def iter_entries(vpk_path):
    with open(vpk_path, "rb") as handle:
        header = handle.read(8)
        if len(header) != 8:
            fail("VPK header is too short")
        signature, version = struct.unpack("<II", header)
        if signature != SIGNATURE:
            fail("Input is not a VPK file")
        tree_size_data = handle.read(4)
        if len(tree_size_data) != 4:
            fail("VPK tree header is too short")
        tree_size = struct.unpack("<I", tree_size_data)[0]
        if version == 2:
            handle.read(16)
            header_size = 28
        elif version == 1:
            header_size = 12
        else:
            fail(f"Unsupported VPK version: {version}")
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
                        fail("VPK tree entry is truncated")
                    _crc, preload_bytes, archive_index, entry_offset, entry_size, _term = struct.unpack("<IHHIIH", entry_data)
                    preload = handle.read(preload_bytes)
                    path_name = "" if path in (" ", ".") else path
                    entry_name = f"{path_name}/{filename}.{extension}" if path_name else f"{filename}.{extension}"
                    yield {
                        "name": entry_name.replace("\\", "/"),
                        "archive_index": archive_index,
                        "entry_offset": entry_offset,
                        "entry_size": entry_size,
                        "preload": preload,
                        "data_start": data_start,
                    }


def extract(vpk_path, target_dir):
    vpk_path = Path(vpk_path)
    target_dir = Path(target_dir)
    if not vpk_path.is_file():
        fail(f"VPK not found: {vpk_path}")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_root = target_dir.resolve()
    extracted = 0
    with open(vpk_path, "rb") as data_handle:
        for entry in iter_entries(vpk_path):
            relative = safe_relative_path(entry["name"])
            if relative is None:
                continue
            if entry["archive_index"] != INLINE_ARCHIVE:
                fail("Multi-part VPK archives are not supported by this extractor")
            destination = (target_dir / relative).resolve()
            try:
                destination.relative_to(target_root)
            except ValueError:
                fail(f"Refusing to extract outside target: {entry['name']}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            data_handle.seek(entry["data_start"] + entry["entry_offset"])
            with open(destination, "wb") as output:
                output.write(entry["preload"])
                remaining = entry["entry_size"]
                while remaining:
                    chunk = data_handle.read(min(1024 * 1024, remaining))
                    if not chunk:
                        fail(f"VPK data is truncated: {entry['name']}")
                    output.write(chunk)
                    remaining -= len(chunk)
            extracted += 1
    print(f"extracted {extracted} files from {vpk_path.name}")


def main():
    if len(sys.argv) != 3:
        fail("usage: vpk_extract.py <input.vpk> <target_dir>")
    extract(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
