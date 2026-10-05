#!/bin/sh
# Baut Höhendaten, Hangneigung und Höhenlinien der Kartengebiete vorab, damit der Server
# sie beim Ansehen der Karte weder holen noch berechnen muss (DATA_DIR/maps/
# <gebiet>.server.sqlite). Einmalig je Gebiet: Höhendaten ändern sich nicht.
#
#   deploy/prebuild-layers.sh                 # alle vorhandenen Gebiete
#   deploy/prebuild-layers.sh switzerland     # ein Gebiet
#
#   MAP_PREBUILD_ZOOM=13   tiefste Zoomstufe (Standard 13; 14 braucht rund viermal so viel
#                          Zeit und Platz, 15 sechzehnmal)
#   MAP_BUILD_CPUS=3       so viele Prozesse rechnen zugleich
#
# Aufwand bei Stufe 13, grob: je Gebiet 1 bis 3 GB und eine halbe bis ganze Stunde mit drei
# Kernen; das Rechnen der Höhenlinien braucht die meiste Zeit. Ein abgebrochener Lauf macht
# beim nächsten Aufruf dort weiter, wo er war. Überlappen sich Gebiete, wird nichts doppelt
# gebaut. Die Höhenkacheln sind offene Daten und dürfen in dieser Menge geholt werden.
set -eu

cd "$(dirname "$0")/.."
DATA_DIR="${DATA_DIR:-$(sed -n 's/^DATA_DIR=//p' .env 2>/dev/null | tail -n 1)}"
DATA_DIR="${DATA_DIR:-./data}"
export DATA_DIR
ZOOM="${MAP_PREBUILD_ZOOM:-13}"
WORKERS="${MAP_BUILD_CPUS:-3}"

if [ "$#" -eq 0 ]; then
  set -- $(for map in "$DATA_DIR"/maps/*.mbtiles; do [ -f "$map" ] && basename "$map" .mbtiles; done)
fi
[ "$#" -gt 0 ] || { echo "Keine Karten unter $DATA_DIR/maps." >&2; exit 1; }

for area in "$@"; do
  case "$area" in
    *[!a-z0-9-]*|"") echo "Ungültiger Gebietsname: $area" >&2; exit 1 ;;
  esac
  echo "=== $area $(date '+%Y-%m-%d %H:%M')"
  docker compose --profile mapbuild run --rm --build mappack \
    "/data/$area.mbtiles" --server "--max-zoom=$ZOOM" "--workers=$WORKERS"
done
echo "=== fertig $(date '+%Y-%m-%d %H:%M')"
ls -lh "$DATA_DIR"/maps/*.server.sqlite
