#!/usr/bin/env python3
import base64
import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request


BASE = "http://127.0.0.1:8080"

env = {}
with open("/etc/l4d2-manager-web.env", encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value


def open_url(opener, path, data=None, headers=None):
    body = None
    request_headers = headers or {}
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        request_headers = {"Content-Type": "application/x-www-form-urlencoded", **request_headers}
    request = urllib.request.Request(BASE + path, data=body, headers=request_headers)
    try:
        with opener.open(request, timeout=5) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8", errors="replace")


plain = urllib.request.build_opener()
status, headers, body = open_url(plain, "/")
assert status == 200, status
assert "WWW-Authenticate" not in headers
assert "L4D2 Manager Login" in body or "Sign in" in body
print("unauth_home", status, len(body))

status, headers, body = open_url(plain, "/api/state")
assert status == 401, status
assert "WWW-Authenticate" not in headers
assert json.loads(body)["message"] == "Authentication required"
print("unauth_api", status)

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
status, headers, body = open_url(
    opener,
    "/api/login",
    {"username": env["L4D2_WEB_USER"], "password": "wrong-password"},
)
assert status == 401, status
assert not list(jar)
print("bad_login", status)

status, headers, body = open_url(
    opener,
    "/api/login",
    {"username": env["L4D2_WEB_USER"], "password": env["L4D2_WEB_PASSWORD"]},
)
assert status == 200, status
assert any(cookie.name == "l4d2web_session" for cookie in jar)
print("login", status)

status, headers, body = open_url(opener, "/")
assert status == 200, status
assert "L4D2 Server Manager" in body
is_react = 'id="root"' in body and "/assets/" in body
is_legacy = 'id="overview"' in body or 'id="rooms"' in body
assert is_react or is_legacy, "home must render React shell or legacy UI"
print("session_home", status, len(body), "react" if is_react else "legacy")

if is_react:
    asset_match = re.search(r'src="([^"]+/assets/[^"]+\.js)"', body)
    assert asset_match, "React shell must reference a JS asset"
    status, headers, asset_body = open_url(opener, asset_match.group(1))
    assert status == 200, status
    assert "javascript" in headers.get("Content-Type", "") or asset_body
    print("react_asset", status, len(asset_body))

status, headers, body = open_url(opener, "/api/state")
assert status == 200, status
assert "rooms" in json.loads(body)
print("session_api", status)

status, headers, body = open_url(opener, "/api/logout", {})
assert status == 200, status
print("logout", status)

status, headers, body = open_url(opener, "/api/state")
assert status == 401, status
print("after_logout_api", status)

token = base64.b64encode(
    f"{env['L4D2_WEB_USER']}:{env['L4D2_WEB_PASSWORD']}".encode("utf-8")
).decode("ascii")
status, headers, body = open_url(
    plain,
    "/api/state",
    headers={"Authorization": f"Basic {token}"},
)
assert status == 200, status
print("basic_api", status)
