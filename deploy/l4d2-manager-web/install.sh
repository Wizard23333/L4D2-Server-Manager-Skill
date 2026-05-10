#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" ]]; then
  echo "Run as root: sudo bash install.sh"
  exit 1
fi

APP_DIR="/opt/l4d2-manager-web"
STATE_DIR="/var/lib/l4d2-manager-web"
ENV_FILE="/etc/l4d2-manager-web.env"
SERVICE_FILE="/etc/systemd/system/l4d2-manager-web.service"
SUDOERS_FILE="/etc/sudoers.d/l4d2-manager-web"

if ! id l4d2web >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin l4d2web
fi

install -d -m 0755 "$APP_DIR"
install -d -o l4d2web -g l4d2web -m 0750 "$STATE_DIR"
install -d -o l4d2web -g l4d2web -m 0750 "$STATE_DIR/jobs"
install -m 0755 app.py "$APP_DIR/app.py"
install -m 0755 l4d2-webctl /usr/local/bin/l4d2-webctl
install -m 0644 vpk_extract.py "$APP_DIR/vpk_extract.py"
install -m 0644 l4d2-manager-web.service "$SERVICE_FILE"
install -m 0440 l4d2-manager-web.sudoers "$SUDOERS_FILE"

if [[ ! -f "$ENV_FILE" ]]; then
  password="$(python3 - <<'PY'
import secrets
import string
alphabet = string.ascii_letters + string.digits
print("".join(secrets.choice(alphabet) for _ in range(24)))
PY
)"
  cat >"$ENV_FILE" <<EOF
L4D2_WEB_HOST=0.0.0.0
L4D2_WEB_PORT=8080
L4D2_WEB_USER=admin
L4D2_WEB_PASSWORD=$password
EOF
  chmod 0600 "$ENV_FILE"
  echo "Created $ENV_FILE"
else
  echo "Keeping existing $ENV_FILE"
fi

visudo -cf "$SUDOERS_FILE"
systemctl daemon-reload
systemctl enable l4d2-manager-web
systemctl restart l4d2-manager-web
systemctl status l4d2-manager-web --no-pager

echo
echo "URL: http://SERVER_IP:8080/"
echo "User: admin"
echo "Password is stored in $ENV_FILE"
