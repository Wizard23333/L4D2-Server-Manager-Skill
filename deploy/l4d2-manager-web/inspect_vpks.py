#!/usr/bin/env python3
import subprocess
from pathlib import Path


for path in sorted(Path("/opt/l4d2/left4dead2/addons").glob("*.vpk")):
    result = subprocess.run(
        ["/usr/bin/strings", str(path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    lines = [
        line
        for line in result.stdout.splitlines()
        if any(token in line.lower() for token in ("addoncontent_campaign", "addoncontent_map", ".bsp", "missions", "maps/"))
    ][:20]
    print(f"--- {path.name}")
    for line in lines:
        print(line)
