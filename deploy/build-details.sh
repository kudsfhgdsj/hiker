#!/bin/sh
# Baut die Detail-Pakete der Kartengebiete für die App: feinere Höhendaten, Hangneigung
# und Höhenlinien zum Mitnehmen, in drei Stufen, die aufeinander aufbauen
# (DATA_DIR/maps/<gebiet>.detail1|2|3.layers.sqlite). In der App wählt man je Gebiet,
# wie fein es ohne Netz sein soll:
#
#   Klein   Höhen bis Zoom 12 (rund 25 m je Bildpunkt), Hangneigung bis 13, Höhenlinien alle 20 m
#   Mittel  dazu Höhen bis Zoom 13 (rund 13 m), Hangneigung bis 14
#   Voll    dazu Höhen bis Zoom 14 (rund 6,5 m), wie mit Netz
#
#   deploy/build-details.sh                 # alle vorhandenen Gebiete
#   deploy/build-details.sh switzerland     # ein Gebiet
#
# Es wird nichts geholt und nichts gerechnet: Die Pakete entstehen aus dem, was der Server
# schon vorab gebaut hat – zuerst die feinen Geländemodelle (deploy/build-terrain.sh),
# sonst sein eigenes Paket (deploy/prebuild-layers.sh). Also danach laufen lassen, und
# erneut, wenn ein Geländemodell dazukommt. Die Höhen stehen darin in Schritten von 25 cm;
# das halbiert die Größe. Aufwand, grob: je Gebiet 2 bis 4 GB und 10 bis 20 Minuten.
set -eu

cd "$(dirname "$0")/.."
DATA_DIR="${DATA_DIR:-$(sed -n 's/^DATA_DIR=//p' .env 2>/dev/null | tail -n 1)}"
DATA_DIR="${DATA_DIR:-./data}"
export DATA_DIR
WORKERS="${MAP_BUILD_CPUS:-3}"

if [ "$#" -eq 0 ]; then
  set -- $(for map in "$DATA_DIR"/maps/*.mbtiles; do [ -f "$map" ] && basename "$map" .mbtiles; done)
fi
[ "$#" -gt 0 ] || { echo "Keine Karten unter $DATA_DIR/maps." >&2; exit 1; }

build="--build"
for area in "$@"; do
  case "$area" in
    *[!a-z0-9-]*|"") echo "Ungültiger Gebietsname: $area" >&2; exit 1 ;;
  esac
  echo "=== $area $(date '+%Y-%m-%d %H:%M')"
  docker compose --profile mapbuild run --rm $build mappack \
    "/data/$area.mbtiles" --details "--workers=$WORKERS"
  build=""
done
echo "=== fertig $(date '+%Y-%m-%d %H:%M')"
ls -lh "$DATA_DIR"/maps/*.detail*.layers.sqlite
