#!/bin/sh
# Build a CLEAN public copy of the project next to this repo (../hacknation-realpage-public) with ONE commit:
# no private history, no organizer corpus, no personal email. Review it, then publish THAT folder.
# Usage: sh scripts/make_public_repo.sh
set -e
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DST="$SRC/../hacknation-realpage-public"
if [ -e "$DST" ]; then echo "refusing: $DST exists. Remove it first (rm -rf '$DST') to rebuild."; exit 1; fi
[ -f "$SRC/docs/submission/README.public.md" ] || { echo "missing docs/submission/README.public.md"; exit 1; }
mkdir -p "$DST/docs" "$DST/data" "$DST/outputs" "$DST/work"
for p in navigator prompts tests eval web scripts; do cp -R "$SRC/$p" "$DST/"; done
cp "$SRC"/outputs/*.json "$DST/outputs/"; cp -R "$SRC/outputs/audit" "$DST/outputs/audit"
for p in extract consolidate llm_cache geocode_cache; do [ -d "$SRC/work/$p" ] && cp -R "$SRC/work/$p" "$DST/work/"; done
for f in es_rules.json jurisdictions.json address_facts.json; do cp "$SRC/work/$f" "$DST/work/"; done
mkdir -p "$DST/work/demo_local" && cp "$SRC"/work/demo_local/*.json "$DST/work/demo_local/" 2>/dev/null || true
for f in engine_notes.md llm_backends.md resolve_notes.md review_rules.md review_lookups.md review_engine.md; do [ -f "$SRC/docs/$f" ] && cp "$SRC/docs/$f" "$DST/docs/"; done
cp "$SRC/docs/submission/METHOD_NOTE.md" "$DST/docs/METHOD_NOTE.md"
cp "$SRC/docs/submission/ADD_JURISDICTION.md" "$DST/docs/ADD_JURISDICTION.md"
cp "$SRC/CONTRACTS.md" "$DST/CONTRACTS.md"   # the stage runners and prompts read it
cp "$SRC/docs/submission/README.public.md" "$DST/README.md"
# official schemas and test definitions (small) and the manifests (URLs and hashes only); NOT the corpus text or the address CSV
mkdir -p "$DST/data/schema" "$DST/data/dev" "$DST/data/templates" "$DST/data/corpus" "$DST/data/corpus_extra"
cp "$SRC"/data/schema/*.json "$DST/data/schema/"; cp "$SRC"/data/dev/*.json "$DST/data/dev/"; cp "$SRC"/data/templates/*.json "$DST/data/templates/"
cp "$SRC/data/corpus/corpus_manifest.csv" "$SRC/data/corpus/links_only.csv" "$DST/data/corpus/"
cp "$SRC/data/corpus_extra/manifest.csv" "$DST/data/corpus_extra/"
# The supplied corpus (official texts, distributed publicly by the organizers) and the address sample are included so the repo runs
# end to end. Set NO_CORPUS=1 to leave them out. Third-party gap-fill pages are reduced to quote-only stubs.
if [ -z "$NO_CORPUS" ]; then
  cp -R "$SRC/data/corpus/text" "$DST/data/corpus/text"; cp "$SRC/data/sample_addresses.csv" "$DST/data/"
fi
mkdir -p "$DST/data/corpus_extra/text"; cp "$SRC"/data/corpus_extra/text/*.txt "$DST/data/corpus_extra/text/"
rm -rf "$DST/web/data/sample.json.bak" "$DST/scripts/preflight.md.bak"
find "$DST" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$DST" -name .DS_Store -delete 2>/dev/null || true
python3 "$SRC/scripts/make_quote_stubs.py" "$DST"
# no local absolute paths in published text
find "$DST" -type f \( -name '*.md' -o -name '*.sh' -o -name '*.txt' \) -not -path "*/data/*" -exec sed -i '' -e 's#.#.#g' -e 's#.#.#g' {} +
cat > "$DST/.gitignore" <<'IGN'
__pycache__/
*.pyc
.DS_Store
.env
submission/
IGN
# privacy gate: no personal webmail address in any file (the script itself is excluded from the scan)
if grep -rIl -i "@gmail\.com" --exclude=make_public_repo.sh "$DST" >/dev/null 2>&1; then echo "STOP: a gmail address was found in:"; grep -rIl -i "@gmail\.com" --exclude=make_public_repo.sh "$DST"; exit 1; fi
cd "$DST"
if [ -z "$NO_CORPUS" ]; then
  echo "smoke test of the public copy:"
  python3 -m navigator.validate --rules outputs/rules_engine.json | tail -1
  python3 -m navigator.pipeline check | tail -1
  python3 -m unittest discover -s tests -p 'test_*.py' 2>&1 | grep -E "^(Ran|OK|FAILED)"
fi
git init -q
git config user.name "hacknation-realpage"
git config user.email "noreply@users.noreply.github.com"
git add -A
git commit -q -m "Rental Housing Law Navigator: Hack-Nation x RealPage entry"
echo "built $DST"
du -sh "$DST" | cut -f1
git log --format='%an <%ae> %s'
git ls-files | wc -l | xargs echo "files tracked:"
