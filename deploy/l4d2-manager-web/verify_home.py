#!/usr/bin/env python3
import base64
import urllib.error
import urllib.request


env = {}
with open("/etc/l4d2-manager-web.env", encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value


def fetch(auth):
    headers = {}
    if auth:
        token = base64.b64encode(
            f"{env['L4D2_WEB_USER']}:{env['L4D2_WEB_PASSWORD']}".encode("utf-8")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    request = urllib.request.Request("http://127.0.0.1:8080/", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(f"auth={auth} status={response.status} length={len(body)}")
            print(body[:240].replace("\n", "\\n"))
    except urllib.error.HTTPError as exc:
        print(f"auth={auth} status={exc.code}")


fetch(False)
fetch(True)
