#!/bin/bash
# Restore a backup made by backup.sh. REPLACES the database and all stored files.
#
#   deploy/restore.sh /var/backups/hiker/hiker-20261004-031500.dump \
#                     /var/backups/hiker/hiker-20261004-031500.files.tar.gz [--yes]
set -euo pipefail

PROJECT_DIR=${HIKER_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
dump=${1:?usage: restore.sh <dump> <files.tar.gz> [--yes]}
files=${2:?usage: restore.sh <dump> <files.tar.gz> [--yes]}
dump=$(readlink -f "$dump")
files=$(readlink -f "$files")
[ -r "$dump" ] && [ -r "$files" ] || { echo "Backup files not readable." >&2; exit 1; }

if [ "${3:-}" != "--yes" ]; then
    read -r -p "This replaces the current database and files of hiker. Type 'restore' to go on: " answer
    [ "$answer" = "restore" ] || { echo "Cancelled."; exit 1; }
fi

cd "$PROJECT_DIR"
docker compose up -d db
docker compose stop web api

docker compose exec -T db sh -c \
    'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --exit-on-error' \
    < "$dump"

# The API container owns the files volume; it is used here without starting the API.
docker compose run --rm --no-deps -T api sh -c \
    'find /data/files -mindepth 1 -delete && tar -C /data/files -xzf -' < "$files"

docker compose up -d
echo "Restored. Check with: deploy/smoke_test.py (use SMOKE_EMAIL / SMOKE_PASSWORD)"
