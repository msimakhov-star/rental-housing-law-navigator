# Rental Housing Law Navigator: web UI

Static single page app. Vanilla HTML/CSS/JS, no build step, no CDN, no network calls except its own files.
Not legal advice: every view carries that banner and an "as of" date.

## Files
- `index.html`, `style.css`, `app.js`: the whole app (English and Spanish, light and dark, print stylesheet).
- `data/lookups_detail.json`: the real data (copied by `sync.sh`, about 7 MB, loaded once).
- `data/sample.json`: 7 addresses in the same shape, for offline work. Open the app with `?sample`.
- `sync.sh`: copies `../outputs/lookups_detail.json` into `data/`; refuses if the file is missing or invalid.

## Data contract (CONTRACTS.md, "UI contract")
The UI does no legal logic. It picks the last `timeline` entry with `from <= as-of date`, skips `not_covered`,
replaces `{ASOF}` in the explanation text, and reads `rules`, `no_rule`, `gaps`, `tests` and `audit` as given.

## Run locally
    ./sync.sh && python3 -m http.server 8765 --directory .   # then open http://localhost:8765/
Deep links: `#tab=lookup|changes|how&lang=en|es&asof=YYYY-MM-DD&addr=A0016`.

## Deploy (static host, publish the contents of `web/`)
- GitHub Pages: run `./sync.sh`, commit `web/`, Settings > Pages > deploy from the folder or branch holding it.
- Hugging Face static Space: create a Space with SDK "static", upload the files of `web/` (keep `data/`).
- Netlify drop: run `./sync.sh`, drag the `web/` folder onto app.netlify.com/drop.
