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
# Bedarf, grob: ein Land wie die Schweiz oder Österreich rund 3 GB freien Arbeitsspeicher
# (MAP_BUILD_MEMORY=2g Java-Heap genügt, Standard 3g) und 10 bis 30 Minuten. Der Bau legt
# seine Zwischendaten auf die Platte (--storage=mmap), damit er mit wenig RAM auskommt;
# reicht der Speicher nicht, beendet das System den Bau (Exit-Code 137).
# Ein monatlicher Aufruf (cron) hält die Karte aktuell.
set -eu

cd "$(dirname "$0")/.."
[ "$#" -gt 0 ] || { echo "Aufruf: $0 <gebiet> [<gebiet> …]" >&2; exit 1; }

for area in "$@"; do
  case "$area" in
    *[!a-z0-9-]*|"") echo "Ungültiger Gebietsname: $area" >&2; exit 1 ;;
  esac
  echo "== $area =="
  DATA_DIR="${DATA_DIR:-$(sed -n 's/^DATA_DIR=//p' .env 2>/dev/null | tail -n 1)}"
  DATA_DIR="${DATA_DIR:-./data}"
  # 1. Grundkarte (OpenMapTiles-Schema); lädt dabei den OSM-Auszug.
  docker compose --profile mapbuild run --rm mapbuild \
    --download --area="$area" --storage=mmap \
    --download-dir=/data/build/sources --tmpdir=/data/build/tmp \
    --output="/data/build/$area.base.mbtiles" --force
  # Planetiler legt den Auszug mit Unterstrichen ab (nord-est → nord_est.osm.pbf); der
  # zweite Schritt sucht ihn unter dem Gebietsnamen.
  extract="$DATA_DIR/maps/build/sources/$(printf %s "$area" | tr - _).osm.pbf"
  [ "$extract" = "$DATA_DIR/maps/build/sources/$area.osm.pbf" ] \
    || mv "$extract" "$DATA_DIR/maps/build/sources/$area.osm.pbf"
  # 2. Wege mit ihrer Schwierigkeit (SAC-Skala, Klettersteige) aus demselben Auszug.
  docker compose --profile mapbuild run --rm mapbuild \
    generate-custom --schema=/schema/hiking.yml --area="$area" \
    --tmpdir=/data/build/tmp \
    --output="/data/build/$area.paths.mbtiles" --force
  # 3. Beides zu einer Datei zusammenfügen. Erst danach umbenennen: die API sieht nie
  #    eine halbe Karte.
  docker compose --profile mapbuild run --rm mapmerge \
    "/data/build/$area.base.mbtiles" "/data/build/$area.paths.mbtiles" "/data/build/$area.mbtiles"
  mv "$DATA_DIR/maps/build/$area.mbtiles" "$DATA_DIR/maps/$area.mbtiles"
  # Zwischenergebnisse und OSM-Auszug werden nicht mehr gebraucht; die Hilfsdaten bleiben.
  rm -f "$DATA_DIR/maps/build/$area.base.mbtiles" "$DATA_DIR/maps/build/$area.paths.mbtiles" \
    "$DATA_DIR/maps/build/sources/$area.osm.pbf"
  # 4. Ebenen-Paket für die App: Höhendaten, Hangneigung und Höhenlinien des Gebiets.
  #    Dauert je nach Größe einige Minuten bis eine Stunde; MAP_LAYERS=0 lässt es weg.
  if [ "${MAP_LAYERS:-1}" != 0 ]; then
    docker compose --profile mapbuild run --rm mappack "/data/$area.mbtiles"
  fi
  ls -lh "$DATA_DIR/maps/$area.mbtiles" "$DATA_DIR/maps/$area.layers.sqlite" 2>/dev/null
done
