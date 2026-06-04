#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/ts-exitbench"
CONFIG_DIR="/etc/ts-exitbench"
CONFIG_PATH="$CONFIG_DIR/config.json"
SERVICE_PATH="/etc/systemd/system/ts-exitbench-agent.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Please run as root: sudo ./install-agent.sh" >&2
  exit 1
fi

require_command python3
require_command tailscale
require_command systemctl
require_command tar

TAILSCALE_IP="$(tailscale ip -4 | head -n 1 | tr -d '[:space:]')"
if [[ -z "$TAILSCALE_IP" ]]; then
  echo "No Tailscale IPv4 found. Make sure this node is logged into Tailscale." >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

(
  cd "$SCRIPT_DIR"
  tar \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    -cf - .
) | (
  cd "$TMP_DIR"
  tar -xf -
)

cp -R "$TMP_DIR"/. "$INSTALL_DIR"/

if [[ ! -f "$CONFIG_PATH" ]]; then
  TOKEN="${TS_EXITBENCH_TOKEN:-$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)}"
  python3 - <<PY
from pathlib import Path
src = Path("$INSTALL_DIR/config.example.json")
dst = Path("$CONFIG_PATH")
text = src.read_text(encoding="utf-8")
text = text.replace("TAILSCALE_IPV4_HERE", "$TAILSCALE_IP")
text = text.replace("change-me-to-a-long-random-token", "$TOKEN")
dst.write_text(text, encoding="utf-8")
PY
  chmod 600 "$CONFIG_PATH"
  echo "Created $CONFIG_PATH"
  echo "Agent token: $TOKEN"
  echo "Use the same token in your client config.json."
else
  echo "Keeping existing config: $CONFIG_PATH"
fi

cp "$INSTALL_DIR/packaging/ts-exitbench-agent.service" "$SERVICE_PATH"
systemctl daemon-reload
systemctl enable --now ts-exitbench-agent
systemctl restart ts-exitbench-agent

echo
systemctl --no-pager --full status ts-exitbench-agent || true
echo
echo "Installed ts-exitbench agent on Tailscale IP: $TAILSCALE_IP"
echo "Config: $CONFIG_PATH"
