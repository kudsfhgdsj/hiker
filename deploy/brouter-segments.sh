#!/bin/sh
# Holt die Wegdaten für BRouter (Kacheln von 5° x 5°, erzeugt aus OpenStreetMap, ODbL) von
# brouter.de nach DATA_DIR/brouter/segments. Ein erneuter Aufruf lädt nur, was sich seit dem
# letzten Mal geändert hat; die Daten werden dort etwa wöchentlich neu gebaut.
#
#   deploy/brouter-segments.sh                 # Alpenraum und alle gebauten Karten
#   deploy/brouter-segments.sh E5_N45 E10_N45  # einzelne Kacheln
#
# Eine Kachel heißt nach ihrer südwestlichen Ecke: E5_N45 reicht von 5° bis 10° Ost und von
# 45° bis 50° Nord. Je Kachel sind es etwa 100 bis 300 MB.
set -eu

cd "$(dirname "$0")/.."
DATA_DIR="${DATA_DIR:-$(sed -n 's/^DATA_DIR=//p' .env 2>/dev/null | tail -n 1)}"
DATA_DIR="${DATA_DIR:-./data}"
TARGET="$DATA_DIR/brouter/segments"
SOURCE="${BROUTER_SEGMENTS_URL:-https://brouter.de/brouter/segments4}"

# Ohne Angabe: der Alpenraum (Schweiz, Österreich, Süddeutschland, Norditalien, Slowenien,
# französische Alpen) und dazu alles, was die gebauten Karten unter DATA_DIR/maps abdecken.
# So gibt es überall dort Wegführung, wo es auch eine Karte gibt.
if [ "$#" -eq 0 ]; then
  covered="$(docker compose --profile mapbuild run --rm --build --entrypoint python mapsearch \
    -m app.modules.maps.coverage /data 2>/dev/null | tail -n 1 || true)"
  # shellcheck disable=SC2086
  set -- $(printf '%s\n' E5_N45 E10_N45 E15_N45 E5_N40 E10_N40 $covered | sort -u)
fi

mkdir -p "$TARGET"
for tile in "$@"; do
  case "$tile" in
    [EW][0-9]*_[NS][0-9]*) ;;
    *) echo "Unbekannte Kachel: $tile (erwartet z. B. E5_N45)" >&2; exit 1 ;;
  esac
  file="$TARGET/$tile.rd5"
  echo "$tile …"
  # -z: nur laden, wenn die Datei auf dem Server neuer ist; erst nach vollständigem
  # Download ersetzen, damit BRouter nie eine halbe Datei sieht.
  if [ -f "$file" ]; then
    curl -fL --retry 3 --no-progress-meter -z "$file" -o "$file.part" "$SOURCE/$tile.rd5"
  else
    curl -fL --retry 3 --no-progress-meter -o "$file.part" "$SOURCE/$tile.rd5"
  fi
  if [ -s "$file.part" ]; then
    mv "$file.part" "$file"
  else
    rm -f "$file.part"
    echo "  unverändert"
  fi
done
du -sh "$TARGET"
