#!/bin/sh
# Build ./submission/ and run all checks. Exit non-zero on any failure. Not legal advice.
set -e
cd "$(dirname "$0")/.."
fail() { echo "FAIL: $1" >&2; exit 1; }

for f in outputs/rules.json outputs/lookups.json outputs/changes.json outputs/rules_engine.json outputs/lookups_detail.json; do
  [ -s "$f" ] || fail "$f missing or empty (run scripts/run_all.sh)"
  python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$f" || fail "$f is not valid JSON"
done
python3 - <<'PY' || exit 1
import json, csv, sys
rules = json.load(open("outputs/rules.json"))["rules"]
look = json.load(open("outputs/lookups.json"))["lookups"]
ch = json.load(open("outputs/changes.json"))
ids = {r["address_id"] for r in csv.DictReader(open("data/sample_addresses.csv"))}
bad = []
if not rules: bad.append("rules.json has no rules")
if len(look) != 500 or set(look) != ids: bad.append(f"lookups cover {len(look)} addresses, expected the 500 in data/sample_addresses.csv")
if sorted(ch) != ["T1", "T2", "T3", "T4", "T5"]: bad.append(f"changes.json keys {sorted(ch)}")
if bad: print("FAIL:", "; ".join(bad), file=sys.stderr); sys.exit(1)
print(f"OK data: {len(rules)} rules, {len(look)} addresses, tests {sorted(ch)}")
PY

echo "== validate"; python3 -m navigator.validate --rules outputs/rules_engine.json || fail "validate"
echo "== pipeline check"; python3 -m navigator.pipeline check || fail "pipeline check"
echo "== unit tests"; python3 -m unittest discover -s tests -p 'test_*.py' || fail "unit tests"
echo "== proxy (our own proxy scorer, NOT the organizers' score.py)"; python3 eval/score_proxy.py || fail "proxy scorer"

grep -qi "not legal advice" web/index.html || fail "web/index.html lacks 'not legal advice'"
[ -s web/data/lookups_detail.json ] || fail "web/data/lookups_detail.json missing (run web/sync.sh)"
cmp -s outputs/lookups_detail.json web/data/lookups_detail.json || fail "web/data/lookups_detail.json is stale (run web/sync.sh)"

rm -rf submission && mkdir -p submission/outputs
cp outputs/rules.json outputs/lookups.json outputs/changes.json submission/outputs/
cp outputs/rules.json outputs/lookups.json outputs/changes.json submission/
if [ -s docs/submission/README.public.md ]; then cp docs/submission/README.public.md submission/README.md
else echo "WARN: docs/submission/README.public.md missing, writing a stub README" >&2
  printf '# Rental Housing Law Navigator\n\nTODO: README. Not legal advice.\n' > submission/README.md; fi
cp -R web submission/web
echo "OK: submission/ built ($(find submission -type f | wc -l | tr -d ' ') files). Not legal advice."
