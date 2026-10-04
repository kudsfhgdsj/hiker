#!/bin/sh
# Baut die eigene Karte eines Gebiets aus OpenStreetMap-Rohdaten (ODbL) als Vektorkacheln
# nach DATA_DIR/maps/<gebiet>.mbtiles. Die API liefert sie danach sofort aus; die App kann
# die Datei herunterladen und die Karte ohne Netz zeigen.
#
#   deploy/build-map.sh switzerland            # ein Gebiet nach Geofabrik-Namen
#   deploy/build-map.sh alps                   # der ganze Alpenbogen
#   deploy/build-map.sh austria switzerland    # mehrere nacheinander
#
# Gebietsnamen wie bei download.geofabrik.de (z. B. liechtenstein, switzerland, austria,
# italy, bayern, alps). Der OSM-Auszug wird bei jedem Lauf neu geholt, die Hilfsdaten
# (Küstenlinien, Natural Earth, rund 1,5 GB) nur beim ersten Mal.
#
# Bedarf, grob: Schweiz rund 3 GB RAM und einige Minuten; Alpen rund 6 GB RAM (mit
# MAP_BUILD_MEMORY=6g in der .env), eine halbe Stunde und 15 GB freien Platz während des Baus.
# Ein monatlicher Aufruf (cron) hält die Karte aktuell.
set -eu

cd "$(dirname "$0")/.."
[ "$#" -gt 0 ] || { echo "Aufruf: $0 <gebiet> [<gebiet> …]" >&2; exit 1; }

for area in "$@"; do
  case "$area" in
    *[!a-z0-9-]*|"") echo "Ungültiger Gebietsname: $area" >&2; exit 1 ;;
  esac
  echo "== $area =="
  # Erst in eine eigene Datei bauen und dann umbenennen: die API sieht nie eine halbe Karte.
  docker compose --profile mapbuild run --rm mapbuild \
    --download --area="$area" \
    --download-dir=/data/build/sources --tmpdir=/data/build/tmp \
    --output="/data/build/$area.mbtiles" --force
  DATA_DIR="${DATA_DIR:-$(sed -n 's/^DATA_DIR=//p' .env 2>/dev/null | tail -n 1)}"
  DATA_DIR="${DATA_DIR:-./data}"
  mv "$DATA_DIR/maps/build/$area.mbtiles" "$DATA_DIR/maps/$area.mbtiles"
  # Der OSM-Auszug wird nicht mehr gebraucht; die Hilfsdaten bleiben für den nächsten Lauf.
  rm -f "$DATA_DIR/maps/build/sources/$area.osm.pbf"
  ls -lh "$DATA_DIR/maps/$area.mbtiles"
done
