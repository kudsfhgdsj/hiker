#!/bin/sh
# Hält Karten und Wegdaten aktuell: baut jedes vorhandene Kartengebiet neu (Karte,
# Suchindex, Ebenen-Paket) und holt geänderte Wegdaten für BRouter. Gedacht für einen
# monatlichen Lauf, z. B. per cron in der Nacht:
#
#   15 2 1 * *  /opt/hiker/deploy/update-maps.sh >> /var/log/hiker-maps.log 2>&1
#
# Welche Gebiete es gibt, sagt der Ordner DATA_DIR/maps: jede <gebiet>.mbtiles wird neu
# gebaut. Ein neues Gebiet legt man einmal von Hand an (deploy/build-map.sh <gebiet>).
# Die alte Karte bleibt in Betrieb, bis die neue fertig ist; scheitert ein Gebiet, bleibt
# seine alte Karte, und die übrigen werden trotzdem gebaut.
#
#   MAP_BUILD_MEMORY=2g  Java-Heap des Kartenbaus (siehe build-map.sh)
#   MAP_LAYERS=0         Ebenen-Pakete nicht neu bauen (Höhendaten ändern sich kaum)
#
# Dauer: je Gebiet etwa 15 bis 30 Minuten. Der Rechner sollte dabei rund 3 GB freien
# Arbeitsspeicher haben.
set -u

cd "$(dirname "$0")/.."
DATA_DIR="${DATA_DIR:-$(sed -n 's/^DATA_DIR=//p' .env 2>/dev/null | tail -n 1)}"
DATA_DIR="${DATA_DIR:-./data}"
export DATA_DIR

# Nie zwei Läufe zugleich: der Kartenbau braucht den Speicher für sich.
LOCK="$DATA_DIR/maps/.update.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "Es läuft schon eine Aktualisierung ($LOCK). Abbruch." >&2
  exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM

failed=""
found=0
for map in "$DATA_DIR"/maps/*.mbtiles; do
  [ -f "$map" ] || continue
  found=1
  area="$(basename "$map" .mbtiles)"
  echo "=== $area $(date '+%Y-%m-%d %H:%M')"
  if ! deploy/build-map.sh "$area"; then
    echo "!!! $area ist gescheitert; die bisherige Karte bleibt." >&2
    failed="$failed $area"
  fi
done
[ "$found" = 1 ] || echo "Keine Karten unter $DATA_DIR/maps: nichts zu bauen."

echo "=== Wegdaten $(date '+%Y-%m-%d %H:%M')"
if deploy/brouter-segments.sh; then
  # BRouter liest geänderte Dateien erst nach einem Neustart sicher.
  docker compose restart brouter >/dev/null 2>&1 || true
else
  failed="$failed wegdaten"
fi

echo "=== fertig $(date '+%Y-%m-%d %H:%M')"
if [ -n "$failed" ]; then
  echo "Gescheitert:$failed" >&2
  exit 1
fi
