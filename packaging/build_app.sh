#!/bin/bash
# GeoLite — build di un'app macOS (.app) da una cartella sorgente.
# Uso: build_app.sh <v1|v0.1>
# L'app contiene un runtime Python standalone (python-build-standalone) con le
# dipendenze preinstallate: l'utente finale non deve installare nulla.
set -euo pipefail

VERSION="${1:?uso: build_app.sh <v1|v0.1>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${GEOLITE_BUILD_DIR:-/private/var/folders/r4/xrlks6cd1ln12b6rd316h8k80000gp/T/opencode/geolite-build}"
PYTARBALL="$WORK/py311.tar.gz"

case "$VERSION" in
  v1)
    APPNAME="GeoLite v1"
    BUNDLE_ID="com.carloratti.geolite.v1"
    SHORT_VERSION="1.0"
    SRC="$ROOT/v1"
    PORT=8501
    ICON="$ROOT/icone/icona_geolite_v1.icns"
    EXTRA_LICENSES="$ROOT/packaging/licenses/LICENZA-v1.txt"
    PKGS=( streamlit==1.64.0 pandas==2.3.3 requests==2.34.2 Pillow==12.3.0 )
    ;;
  v0.1)
    APPNAME="GeoLite v0.1"
    BUNDLE_ID="com.carloratti.geolite.v01"
    SHORT_VERSION="0.1"
    SRC="$ROOT/v0.1"
    PORT=8601
    ICON="$ROOT/icone/icona_geolite_v0.1.icns"
    EXTRA_LICENSES=""
    PKGS=( streamlit==1.64.0 pandas==2.3.3 requests==2.34.2 folium==0.20.0 streamlit-folium==0.27.4 transformers==5.17.0 accelerate==1.15.0 torch==2.14.0 )
    ;;
  *) echo "sconosciuta: $VERSION" >&2; exit 1;;
esac

APPDIR="$WORK/$APPNAME.app"
RES="$APPDIR/Contents/Resources"
RUNTIME="$RES/runtime"
APP="$RES/app"
CREDITS="$ROOT/packaging/licenses/CREDITS-TERZE-PARTI.txt"

echo "==> [$VERSION] pulizia + scaffold"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/Contents/MacOS" "$RES" "$APP"

echo "==> [$VERSION] runtime Python standalone"
# Lock: due build parallele non devono estrarre il tarball nello stesso istante.
LOCK="$WORK/.pylock"
mkdir -p "$WORK"
while ! mkdir "$LOCK" 2>/dev/null; do sleep 1; done
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT
if [ ! -d "$WORK/python/bin" ]; then
  [ -f "$PYTARBALL" ] || curl -sL -o "$PYTARBALL" \
    "https://github.com/astral-sh/python-build-standalone/releases/download/20261013/cpython-3.11.17+20261013-aarch64-apple-darwin-install_only_stripped.tar.gz"
  EXTRACT="$(mktemp -d "$WORK/pyextract.XXXXXX")"
  tar xzf "$PYTARBALL" -C "$EXTRACT"
  rm -rf "$WORK/python"
  mv "$EXTRACT/python" "$WORK/python"
  rm -rf "$EXTRACT"
fi
rmdir "$LOCK" 2>/dev/null || true
trap - EXIT
cp -R "$WORK/python" "$RUNTIME"
"$RUNTIME/bin/python3" -c "import sys" || { echo "runtime non valido" >&2; exit 1; }
PY="$RUNTIME/bin/python3"

echo "==> [$VERSION] installazione dipendenze (poi pip viene rimosso)"
"$PY" -m pip install --no-cache-dir --quiet "${PKGS[@]}"
"$PY" -m pip uninstall -y --quiet pip >/dev/null 2>&1 || true
rm -rf "$RUNTIME"/lib/python3.11/idlelib \
       "$RUNTIME"/lib/python3.11/lib2to3 \
       "$RUNTIME"/lib/python3.11/tkinter \
       "$RUNTIME"/lib/python3.11/turtle* \
       "$RUNTIME"/bin/2to3* "$RUNTIME"/bin/idle* \
       "$RUNTIME"/lib/python3.11/site-packages/*.dist-info/RECORD 2>/dev/null || true

echo "==> [$VERSION] copia sorgenti (no __pycache__, .mov, .DS_Store, sqlite di sviluppo)"
rsync -a \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.DS_Store' \
  --exclude='*.sqlite3' \
  --exclude='*.mov' \
  --exclude='.gitignore' \
  "$SRC/" "$APP/"
cp "$CREDITS" "$APP/CREDITS-TERZE-PARTI.txt"
[ -n "$EXTRA_LICENSES" ] && cp "$EXTRA_LICENSES" "$APP/LICENZA.txt"

echo "==> [$VERSION] precaricamento bytecode (primo avvio più rapido)"
( cd "$APP" && "$PY" -c "import streamlit, pandas, requests" >/dev/null 2>&1 || true )

echo "==> [$VERSION] Info.plist + icona + launcher"
cat > "$APPDIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$APPNAME</string>
  <key>CFBundleDisplayName</key><string>$APPNAME</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleVersion</key><string>$SHORT_VERSION</string>
  <key>CFBundleShortVersionString</key><string>$SHORT_VERSION</string>
  <key>CFBundleExecutable</key><string>geolite</string>
  <key>CFBundleIconFile</key><string>app.icns</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.education</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSHumanReadableCopyright</key><string>Copyright © 2026 GeoLite</string>
</dict>
</plist>
PLIST
cp "$ICON" "$RES/app.icns"

cat > "$APPDIR/Contents/MacOS/geolite" <<LAUNCHER
#!/bin/bash
# Launcher GeoLite $APPNAME — avvia Streamlit in locale e apre il browser.
export PATH="/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED=1

RES="\$(cd "\$(dirname "\$0")/../Resources" && pwd)"
PY="\$RES/runtime/bin/python3"
APP="\$RES/app"
DATA="\$HOME/Library/Application Support/$APPNAME"
LOG="\$DATA/server.log"
PIDFILE="\$DATA/server.pid"
PORTFILE="\$DATA/server.port"
mkdir -p "\$DATA"

# Se un'istanza è già viva, riapri solo il browser.
if [ -f "\$PIDFILE" ] && [ -f "\$PORTFILE" ]; then
  OLD_PID="\$(cat "\$PIDFILE" 2>/dev/null || true)"
  OLD_PORT="\$(cat "\$PORTFILE" 2>/dev/null || true)"
  if [ -n "\$OLD_PID" ] && kill -0 "\$OLD_PID" 2>/dev/null && \\
     curl -sf "http://localhost:\$OLD_PORT/_stcore/health" >/dev/null 2>&1; then
    open "http://localhost:\$OLD_PORT"
    exit 0
  fi
fi

# Trova una porta libera a partire da $PORT.
PORT=$PORT
while nc -z -G 1 localhost "\$PORT" 2>/dev/null; do PORT=\$((PORT+1)); done

export GEOBRAIN_DB_PATH="\$DATA/geobrain_users.sqlite3"
cd "\$APP"
"\$PY" -m streamlit run app.py \\
  --server.port="\$PORT" \\
  --server.address="localhost" \\
  --server.headless=true \\
  --server.fileWatcherType="none" \\
  --browser.gatherUsageStats=false \\
  >>"\$LOG" 2>&1 &
PID=\$!
echo "\$PID" > "\$PIDFILE"
echo "\$PORT" > "\$PORTFILE"

cleanup() { kill "\$PID" 2>/dev/null || true; rm -f "\$PIDFILE" "\$PORTFILE"; }
trap cleanup EXIT INT TERM

# Attende che il server risponda (max ~30s).
READY=0
for _ in \$(seq 1 60); do
  if curl -sf "http://localhost:\$PORT/_stcore/health" >/dev/null 2>&1; then READY=1; break; fi
  kill -0 "\$PID" 2>/dev/null || break
  sleep 0.5
done

if [ "\$READY" = "1" ]; then
  if [ "\${GEOLITE_NO_BROWSER:-0}" != "1" ]; then open "http://localhost:\$PORT"; fi
  wait "\$PID"
else
  osascript -e 'display alert "$APPNAME non è riuscito ad avviarsi" message "Controlla il log:
~/Library/Application Support/$APPNAME/server.log" as critical' >/dev/null 2>&1 || true
  exit 1
fi
LAUNCHER
chmod +x "$APPDIR/Contents/MacOS/geolite"

echo "==> [$VERSION] firma ad-hoc (obbligatoria su Apple Silicon)"
codesign --force --deep -s - "$APPDIR" >/dev/null
codesign --verify --quiet "$APPDIR" && echo "    firma OK"

echo "==> [$VERSION] dimensioni:"
du -sh "$APPDIR"
echo "APP Built: $APPDIR"
