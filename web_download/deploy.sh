#!/bin/bash
# GeoLite — pubblicazione su Cloudflare.
#
# PERCORSO PRINCIPALE (default): tutto il sito + le release su un bucket R2 con
# "Static website hosting" abilitato. Nessun limite di dimensione (i file sono da
# 156 a 615 MB: Cloudflare Pages li rifiuterebbe, limite 25 MiB a file), link relativi
# dell'index.html già pronti così.
#
# PERCORSO ALTERNATIVO (--pages): sito su Cloudflare Pages + release su R2.
# In quel caso i link in index.html vanno resi assoluti (cerca DOWNLOAD_BASE).
#
# Prerequisiti: Node.js; login già fatta con: npx wrangler login
#
# Uso:
#   web_download/deploy.sh            # carica SITO + RELEASE sul bucket R2
#   web_download/deploy.sh --pages    # pubblica il solo sito su Pages
#
# Setup iniziale (una tantum):
#   1. npx wrangler r2 bucket create geolite-releases
#   2. Dashboard -> R2 -> geolite-releases -> Settings -> Public access:
#        - abilita "Static website hosting" (index document: index.html)
#        - collega un dominio custom (es. download.geolite.it) oppure usa l'URL r2.dev

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BUCKET="${R2_BUCKET:-geolite-releases}"

if [ "${1:-}" = "--pages" ]; then
  echo "==> Deploy SITO su Cloudflare Pages (senza releases/)"
  DEPLOY_DIR="$ROOT/.deploy"
  rm -rf "$DEPLOY_DIR"; mkdir -p "$DEPLOY_DIR"
  cp "$ROOT/index.html" "$DEPLOY_DIR/"
  cp "$ROOT/_headers" "$DEPLOY_DIR/"
  cp -R "$ROOT/assets" "$DEPLOY_DIR/assets"
  ( cd "$DEPLOY_DIR" && npx wrangler pages deploy . --project-name=geolite-download )
  rm -rf "$DEPLOY_DIR"
  cat <<'EOF'

Fatto (sito su Pages). ATTENZIONE: i link download sono relativi (releases/...),
che su Pages NON esiste. Scegli una delle due:
  a) consigliata: usa R2 static website hosting per tutto  ->  web_download/deploy.sh
  b) oppure rendi assoluti i link in index.html verso il bucket R2 (cerca DOWNLOAD_BASE)
EOF
  exit 0
fi

mime_of() {
  case "$1" in
    *.html) echo "text/html; charset=utf-8" ;;
    *.svg)  echo "image/svg+xml" ;;
    *.png)  echo "image/png" ;;
    *.dmg)  echo "application/x-apple-diskimage" ;;
    *.zip)  echo "application/zip" ;;
    *)      echo "application/octet-stream" ;;
  esac
}

echo "==> Upload SITO + RELEASE sul bucket R2: $BUCKET"
FILES="index.html
$(cd "$ROOT" && ls assets/*)
$(cd "$ROOT" && ls releases/*)"

echo "$FILES" | while IFS= read -r f; do
  [ -n "$f" ] || continue
  echo "  -> $f"
  npx wrangler r2 object put "$BUCKET/$f" --file="$ROOT/$f" --content-type="$(mime_of "$f")"
done

cat <<EOF

Fatto. Ora (se non l'hai già fatto):
  Dashboard -> R2 -> $BUCKET -> Settings -> Public access
    1. abilita "Static website hosting" (index document: index.html)
    2. collega il dominio custom (es. download.geolite.it)
Il sito + i download saranno raggiungibili da quel dominio.

Ricorda: se rigeneri le release con packaging/package.sh, aggiorna SHA-256 e
dimensioni in index.html e riesegui questo script.
EOF
