#!/bin/bash
# GeoLite — crea .zip e .dmg per ogni app costruita e li copia nelle release del sito.
# Uso: package.sh   (richiede che packaging/build_app.sh abbia già girato per v1 e v0.1)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${GEOLITE_BUILD_DIR:-/private/var/folders/r4/xrlks6cd1ln12b6rd316h8k80000gp/T/opencode/geolite-build}"
OUT="$ROOT/web_download/releases"
DIST="$ROOT/dist"
mkdir -p "$OUT" "$DIST"

package_one() {
  local APPNAME="$1" ZIPNAME="$2"
  local APP="$WORK/$APPNAME.app"
  [ -d "$APP" ] || { echo "manca $APP — esegui prima build_app.sh" >&2; exit 1; }

  echo "==> $APPNAME: preparazione stage"
  local STAGE="$WORK/stage-$ZIPNAME"
  rm -rf "$STAGE" "$WORK/dmg-$ZIPNAME" "$DIST/$ZIPNAME.zip"
  mkdir -p "$STAGE"
  cp -R "$APP" "$STAGE/"
  ln -s /Applications "$STAGE/Applicazioni"

  echo "==> $APPNAME: zip (ditto, preserva permessi e firma)"
  ( cd "$STAGE" && ditto -c -k --sequesterRsrc --keepParent "$APPNAME.app" "$DIST/$ZIPNAME.zip" )

  echo "==> $APPNAME: dmg"
  hdiutil create -volname "$APPNAME" -srcfolder "$STAGE" -ov -format UDZO \
    -imagekey zlib-level=9 "$WORK/dmg-$ZIPNAME.dmg" >/dev/null
  mv "$WORK/dmg-$ZIPNAME.dmg" "$OUT/$ZIPNAME.dmg"
  cp "$DIST/$ZIPNAME.zip" "$OUT/$ZIPNAME.zip"
  rm -rf "$STAGE"

  echo "==> $APPNAME: verifiche"
  hdiutil imageinfo "$OUT/$ZIPNAME.dmg" >/dev/null && echo "    dmg leggibile OK"
  unzip -tqq "$OUT/$ZIPNAME.zip" >/dev/null && echo "    zip integro OK"
  codesign --verify --deep --strict "$APP" && echo "    firma app OK"
}

package_one "GeoLite v1"   "geolite-v1"
package_one "GeoLite v0.1" "geolite-v0.1"

echo
echo "==> Release in $OUT:"
ls -lh "$OUT"
echo
echo "==> SHA-256 (da inserire nel sito):"
cd "$OUT"
shasum -a 256 geolite-v1.dmg geolite-v0.1.dmg geolite-v1.zip geolite-v0.1.zip
