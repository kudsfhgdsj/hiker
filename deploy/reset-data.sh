#!/bin/bash
# Empty a hiker instance: all accounts, tours, gear, foods, photos and GPX files are
# DELETED. Meant for test instances. The map tiles and the certificates of Caddy stay.
#
#   deploy/reset-data.sh          asks before deleting
#   deploy/reset-data.sh --yes    for scripts
set -euo pipefail

PROJECT_DIR=${HIKER_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
cd "$PROJECT_DIR"

# DATA_DIR as the stack uses it (from .env, default ./data).
DATA_DIR=$(docker compose config --format json | python3 -c \
    'import json, sys; print(json.load(sys.stdin)["services"]["init"]["volumes"][0]["source"])')
case "$DATA_DIR" in
    "" | "/") echo "Refusing to work on DATA_DIR=\"$DATA_DIR\"." >&2; exit 1 ;;
esac
[ -d "$DATA_DIR/db" ] || { echo "No instance found in $DATA_DIR." >&2; exit 1; }

echo "This deletes ALL data of the hiker instance in $DATA_DIR:"
echo "  $DATA_DIR/db  $DATA_DIR/files  $DATA_DIR/web-sessions"
if [ "${1:-}" != "--yes" ]; then
    read -r -p "Type 'delete' to go on: " answer
    [ "$answer" = "delete" ] || { echo "Cancelled."; exit 1; }
fi

docker compose down
rm -rf -- "$DATA_DIR/db" "$DATA_DIR/files" "$DATA_DIR/web-sessions"
docker compose up -d
echo "The instance is empty. The first account that registers becomes the administrator."
