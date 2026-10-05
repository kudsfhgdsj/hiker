#!/bin/sh
# Baut aus einem feinen Geländemodell eines Gebiets Höhenkacheln für die eigene Karte,
# dazu Hangneigung und Höhenlinien (DATA_DIR/maps/<gebiet>.hires.sqlite). Die API nimmt
# sie vor den groben weltweiten Kacheln: schärfere Grate in Schummerung und 3D,
# genauere Hangneigung und Höhenlinien.
#
#   deploy/build-terrain.sh austria
#
# Quellen (offene Daten; die Nennung steht danach in der Karte):
#   austria   BEV, Digitales Geländehöhenmodell, Höhenraster 5 m, CC BY 4.0
#             https://data.bev.gv.at (eine Datei, rund 19 GB)
#
#   MAP_TERRAIN_ZOOM=14   tiefste Zoomstufe (14 sind rund 6,5 m je Bildpunkt)
#   MAP_BUILD_CPUS=3      so viele Prozesse rechnen zugleich
#
# Aufwand für Österreich, grob: 19 GB Download (bleibt unter maps/build/sources und kann
# danach gelöscht werden), 5 bis 7 GB Ergebnis, ein bis zwei Stunden mit drei Kernen.
# Ein abgebrochener Lauf macht beim nächsten Aufruf weiter.
set -eu

cd "$(dirname "$0")/.."
[ "$#" -eq 1 ] || { echo "Aufruf: $0 <gebiet>" >&2; exit 1; }
area="$1"
case "$area" in
  austria)
    url="https://data.bev.gv.at/download/DGM/Hoehenraster/DGM_R5.tif"
    file="DGM_R5.tif"
    attribution="Höhendaten Österreich: © BEV (DGM 5 m), CC BY 4.0"
    ;;
  *) echo "Für '$area' ist noch kein Geländemodell hinterlegt (bisher: austria)." >&2; exit 1 ;;
esac

DATA_DIR="${DATA_DIR:-$(sed -n 's/^DATA_DIR=//p' .env 2>/dev/null | tail -n 1)}"
DATA_DIR="${DATA_DIR:-./data}"
export DATA_DIR
ZOOM="${MAP_TERRAIN_ZOOM:-14}"
WORKERS="${MAP_BUILD_CPUS:-3}"
sources="$DATA_DIR/maps/build/sources"
mkdir -p "$sources"

if [ ! -f "$sources/$file" ]; then
  echo "== Lade $file =="
  # Ein unterbrochener Download wird fortgesetzt; erst die ganze Datei bekommt den Namen.
  curl -fL --retry 5 -C - --no-progress-meter -o "$sources/$file.part" "$url"
  mv "$sources/$file.part" "$sources/$file"
fi

echo "== Höhenkacheln $area $(date '+%Y-%m-%d %H:%M') =="
docker compose --profile mapbuild run --rm terrainbuild \
  --source "/data/build/sources/$file" --out "/data/$area.hires.sqlite" \
  --max-zoom "$ZOOM" --workers "$WORKERS" --attribution "$attribution"

echo "== Hangneigung und Höhenlinien $(date '+%Y-%m-%d %H:%M') =="
docker compose --profile mapbuild run --rm --build mappack \
  "/data/$area.hires.sqlite" --derive "--workers=$WORKERS"

echo "== fertig $(date '+%Y-%m-%d %H:%M') =="
ls -lh "$DATA_DIR/maps/$area.hires.sqlite"
