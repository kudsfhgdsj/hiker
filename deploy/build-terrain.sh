#!/bin/sh
# Baut aus einem feinen Geländemodell eines Gebiets Höhenkacheln für die eigene Karte,
# dazu Hangneigung und Höhenlinien (DATA_DIR/maps/<gebiet>.hires.sqlite und
# <gebiet>.derived.hires.sqlite). Die API nimmt
# sie vor den groben weltweiten Kacheln: schärfere Grate in Schummerung und 3D,
# genauere Hangneigung und Höhenlinien.
#
#   deploy/build-terrain.sh austria
#   deploy/build-terrain.sh bayern
#   deploy/build-terrain.sh switzerland
#   deploy/build-terrain.sh suedtirol
#
# Quellen (offene Daten; die Nennung steht danach in der Karte):
#   austria   BEV, Digitales Geländehöhenmodell, Höhenraster 5 m, CC BY 4.0
#             https://data.bev.gv.at (eine Datei, rund 19 GB)
#   bayern    LDBV (Bayerische Vermessungsverwaltung), DGM5, Gitterweite 5 m, CC BY 4.0
#             https://geodaten.bayern.de/opengeodata (rund 72.000 Dateien, 13 GB;
#             sie werden vorab zu einer Rasterdatei zusammengesetzt)
#   switzerland  swisstopo, swissALTI3D, 2 m (mit Liechtenstein), frei nutzbar mit
#             Quellenangabe; https://www.swisstopo.admin.ch (rund 44.000 Dateien, 52 GB;
#             sie werden beim Laden auf 5 m verkleinert und nicht aufbewahrt)
#   suedtirol Autonome Provinz Bozen – Südtirol, DTM 2,5 m, CC0; nur über den
#             Abrufdienst (WCS) der Provinz: rund 700 Quadrate zu 5 km, 11 GB, beim
#             Laden auf 5 m verkleinert und nicht aufbewahrt
#
#   MAP_TERRAIN_ZOOM=14   tiefste Zoomstufe (14 sind rund 6,5 m je Bildpunkt)
#   MAP_BUILD_CPUS=3      so viele Prozesse rechnen zugleich
#
# Aufwand für Österreich, grob: 19 GB Download (bleibt unter maps/build/sources und kann
# danach gelöscht werden), 5 bis 7 GB Ergebnis, ein bis zwei Stunden mit drei Kernen.
# Ein abgebrochener Lauf macht beim nächsten Aufruf weiter. Das Zusammenführen der
# Grenzkacheln schreibt in Pakete, die die API gerade liest: diesen Schritt nicht
# abbrechen (sonst das Skript einfach noch einmal starten).
set -eu

cd "$(dirname "$0")/.."
[ "$#" -eq 1 ] || { echo "Aufruf: $0 <gebiet>" >&2; exit 1; }
area="$1"
case "$area" in
  austria)
    url="https://data.bev.gv.at/download/DGM/Hoehenraster/DGM_R5.tif"
    metalink=""
    tiles=""
    file="DGM_R5.tif"
    attribution="Höhendaten Österreich: © BEV (DGM 5 m), CC BY 4.0"
    # Reicht mit gröberen Daten einige Kilometer über die Staatsgrenze.
    priority=0
    ;;
  bayern)
    # Viele kleine Textdateien (x y z) je Quadratkilometer, UTM 32.
    url=""
    metalink="https://geodaten.bayern.de/odd/a/dgm/dgm5xyz/meta/metalink/09.meta4"
    tiles=""
    srs="EPSG:25832"
    step=5
    file="bayern-dgm5.tif"
    attribution="Höhendaten Bayern: © Bayerische Vermessungsverwaltung (DGM5), CC BY 4.0"
    # Endet genau an der Landesgrenze: gilt dort vor einem Nachbarn, der hinüberreicht.
    priority=10
    ;;
  switzerland)
    # Ein GeoTIFF je Quadratkilometer, LV95. Die Adresse antwortet mit dem Verweis auf
    # die Liste der aktuellen Dateien.
    url=""
    metalink=""
    tiles="https://ogd.swisstopo.admin.ch/services/swiseld/services/assets/ch.swisstopo.swissalti3d/search?format=image%2Ftiff%3B%20application%3Dgeotiff%3B%20profile%3Dcloud-optimized&resolution=2.0&srid=2056&state=current&csv=true"
    srs="EPSG:2056"
    step=5
    size=1
    fetchers=6
    file="switzerland-5m.tif"
    attribution="Höhendaten Schweiz: © swisstopo (swissALTI3D)"
    priority=10
    ;;
  suedtirol)
    # Kein Download als Datei: Der Abrufdienst liefert Quadrate (UTM 32), deren Liste
    # hier entsteht. Die Ecke steht in einem Parameter ohne weitere Bedeutung (tile).
    url=""
    metalink=""
    tiles="suedtirol.list"
    srs="EPSG:25832"
    step=5
    size=5
    # Ein öffentlicher Dienst: wenige Abrufe zugleich.
    fetchers=3
    file="suedtirol-5m.tif"
    attribution="Höhendaten Südtirol: Autonome Provinz Bozen – Südtirol (DTM 2,5 m), CC0"
    priority=10
    ;;
  *) echo "Für '$area' ist noch kein Geländemodell hinterlegt (bisher: austria, bayern, switzerland, suedtirol)." >&2; exit 1 ;;
esac

DATA_DIR="${DATA_DIR:-$(sed -n 's/^DATA_DIR=//p' .env 2>/dev/null | tail -n 1)}"
DATA_DIR="${DATA_DIR:-./data}"
export DATA_DIR
ZOOM="${MAP_TERRAIN_ZOOM:-14}"
WORKERS="${MAP_BUILD_CPUS:-3}"
sources="$DATA_DIR/maps/build/sources"
mkdir -p "$sources"

if [ ! -f "$sources/$file" ] && [ -n "$metalink" ]; then
  echo "== Lade und setze zusammen: $file $(date '+%Y-%m-%d %H:%M') =="
  # Schon geholte Dateien bleiben liegen; ein abgebrochener Lauf macht weiter.
  docker compose --profile mapbuild run --rm --entrypoint python3 terrainbuild \
    /tool/mosaic_xyz.py --metalink "$metalink" --dir "/data/build/sources/${file%.tif}" \
    --out "/data/build/sources/$file" --srs "$srs" --step "$step" --workers "$WORKERS"
elif [ ! -f "$sources/$file" ] && [ -n "$tiles" ]; then
  echo "== Lade und verkleinere: $file $(date '+%Y-%m-%d %H:%M') =="
  if [ "$area" = suedtirol ]; then
    # Ausdehnung des Modells laut Dienst: 605–768 km Ost, 5120–5221 km Nord.
    service="https://geoservices9.civis.bz.it/geoserver/p_bz-Elevation/ows?service=WCS&version=2.0.1&request=GetCoverage&coverageId=p_bz-Elevation__DigitalTerrainModel-2.5m&format=image%2Ftiff"
    : > "$sources/$tiles"
    for east in $(seq 605 5 765); do
      for north in $(seq 5120 5 5220); do
        printf '%s&subset=E(%s000,%s000)&subset=N(%s000,%s000)&tile=_%04d-%04d_\n' "$service" \
          "$east" "$((east + 5))" "$north" "$((north + 5))" "$east" "$north" >> "$sources/$tiles"
      done
    done
    tiles="/data/build/sources/$tiles"
  fi
  docker compose --profile mapbuild run --rm --entrypoint python3 terrainbuild \
    /tool/mosaic_tiles.py --list "$tiles" --out "/data/build/sources/$file" \
    --srs "$srs" --step "$step" --size-km "$size" --workers "$fetchers"
elif [ ! -f "$sources/$file" ]; then
  echo "== Lade $file =="
  # Ein unterbrochener Download wird fortgesetzt; erst die ganze Datei bekommt den Namen.
  curl -fL --retry 5 -C - --no-progress-meter -o "$sources/$file.part" "$url"
  mv "$sources/$file.part" "$sources/$file"
fi

echo "== Höhenkacheln $area $(date '+%Y-%m-%d %H:%M') =="
docker compose --profile mapbuild run --rm terrainbuild \
  --source "/data/build/sources/$file" --out "/data/$area.hires.sqlite" \
  --max-zoom "$ZOOM" --workers "$WORKERS" --attribution "$attribution" --priority "$priority"

# Kacheln an der Grenze zweier Gebiete liegen in beiden Paketen, jeweils nur auf der
# eigenen Seite fein: beide Hälften zusammenführen.
packs=""
for pack in "$DATA_DIR"/maps/*.hires.sqlite; do
  case "$pack" in *.derived.hires.sqlite) continue ;; esac
  packs="$packs /data/$(basename "$pack")"
done
echo "== Grenzkacheln zusammenführen $(date '+%Y-%m-%d %H:%M') =="
# shellcheck disable=SC2086
docker compose --profile mapbuild run --rm --entrypoint python3 terrainbuild \
  /tool/join_packs.py $packs

echo "== Hangneigung und Höhenlinien $(date '+%Y-%m-%d %H:%M') =="
# Für alle Gebiete: Was schon da ist, bleibt; neu gerechnet wird nur, was fehlt, also
# auch die eben zusammengeführten Kacheln der Nachbarn.
build="--build"
for pack in $packs; do
  docker compose --profile mapbuild run --rm $build mappack "$pack" --derive "--workers=$WORKERS"
  build=""
done

echo "== fertig $(date '+%Y-%m-%d %H:%M') =="
ls -lh "$DATA_DIR/maps/$area.hires.sqlite" "$DATA_DIR/maps/$area.derived.hires.sqlite"
