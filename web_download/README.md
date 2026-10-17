# GeoLite — download site

Static site for downloading the GeoLite applications. No server required: it
works from any static host (GitHub Pages, Netlify, Cloudflare Pages, or even a
simple `python3 -m http.server`).

## Structure

```
web_download/
├── index.html          # single page (versions, explore, installation, licenses, credits)
├── assets/             # icons (icon-v1.svg, icon-v0.1.svg), favicon, logos
└── releases/           # downloadable files hosted by the site
    ├── geolite-v1.dmg
    ├── geolite-v1.zip
    ├── geolite-v0.1.dmg
    └── geolite-v0.1.zip
```

## Publishing

1. Build the apps (once):
   ```bash
   packaging/build_app.sh v1
   packaging/build_app.sh v0.1
   ```
2. Generate zip + dmg and copy them into `releases/`:
   ```bash
   packaging/package.sh
   ```
3. Update the SHA-256 values and the file sizes shown in the site cards
   with the ones printed by `package.sh` (they live in `index.html`, in the
   `<code>SHA-256 …</code>` lines and in the `.sub` labels of the buttons).
4. Publish (see below).

### Cloudflare: R2 static website hosting (consigliato)

The release files weigh 156–615 MB each. **Cloudflare Pages refuses any file
larger than 25 MiB**, so the whole folder — site + releases — goes to a single
**R2 bucket with static website hosting**: no size limits, no egress fees, and
the relative download links in `index.html` already work as they are.

One-time setup:

```bash
npx wrangler login                                # auth
npx wrangler r2 bucket create geolite-releases    # bucket sito + release
# Dashboard -> R2 -> geolite-releases -> Settings -> Public access:
#   1. enable "Static website hosting" (index document: index.html)
#   2. attach a custom domain (eg. download.geolite.it) or use the r2.dev URL
```

Every update:

```bash
web_download/deploy.sh          # uploads index.html + assets/ + releases/ to R2
```

### Alternative: Pages for the site + R2 for the releases

If you prefer the site on Cloudflare Pages, deploy it with:

```bash
web_download/deploy.sh --pages
```

Pages cannot host the release files, so in this setup the download links in
`index.html` must become absolute URLs pointing at the R2 bucket
(search for `DOWNLOAD_BASE` in `index.html`).

### Alternative hosts

The page itself is plain static files: without Cloudflare you can host
`index.html` + `assets/` anywhere (GitHub Pages, Netlify…) and put the
releases on any large-file host (GitHub Releases, S3…) — just keep the
download URLs in `index.html` pointing at wherever the files actually are.

## Choosing a version

The “Choose your version” section offers two side-by-side cards (v0.1 and v1),
each with two buttons: **.dmg** (disk image, drag into Applications) and
**zip** (same app, no disk). The two downloads are independent: anyone visiting
the site can grab either version at any time.

## Note on code signing

The apps are ad-hoc signed (without a paid Apple certificate): on first launch
macOS asks you to **right-click → Open**. The site already explains this in the
Installation section.
