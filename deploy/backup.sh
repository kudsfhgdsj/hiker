#!/bin/bash
# Nightly backup of hiker: database dump and the stored files (photos, GPX).
#
#   BACKUP_DIR=/var/backups/hiker KEEP_DAYS=14 deploy/backup.sh
#
# Needs access to Docker. Keeps the backups of the last KEEP_DAYS days. A copy outside
# of this server is recommended; this script only writes to BACKUP_DIR.
set -euo pipefail

PROJECT_DIR=${HIKER_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/hiker}
KEEP_DAYS=${KEEP_DAYS:-14}
stamp=$(date +%Y%m%d-%H%M%S)
dump="$BACKUP_DIR/hiker-$stamp.dump"
files="$BACKUP_DIR/hiker-$stamp.files.tar.gz"

cd "$PROJECT_DIR"
umask 077
mkdir -p "$BACKUP_DIR"
trap 'rm -f "$dump.part" "$files.part"' EXIT

# The database in PostgreSQL's custom format (compressed, restorable with pg_restore).
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    > "$dump.part"
# Make sure the dump is readable before it replaces nothing and old backups are removed.
docker compose exec -T db pg_restore --list < "$dump.part" > /dev/null

docker compose exec -T api tar -C /data/files -cf - . | gzip > "$files.part"
gzip -t "$files.part"

mv "$dump.part" "$dump"
mv "$files.part" "$files"

find "$BACKUP_DIR" -maxdepth 1 -name 'hiker-*' -type f -mtime "+$KEEP_DAYS" -delete
echo "Backup written: $dump ($(du -h "$dump" | cut -f1)), $files ($(du -h "$files" | cut -f1))"
