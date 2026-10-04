#!/bin/sh
# Clean terminal walk-through for the technical and demo videos: prints a heading, runs one real command, pauses.
# Usage: sh scripts/demo_terminal.sh        (about 60 seconds; set PAUSE=4 for slower pacing)
cd "$(dirname "$0")/.."
P="${PAUSE:-2}"
step() { printf '\n\033[1m== %s\033[0m\n' "$1"; sleep "$P"; }
step "1. Rule records: schema, enums, dates and every quoted span found verbatim in the source text"
python3 -m navigator.validate --rules outputs/rules_engine.json; sleep "$P"
step "2. Extraction runner, offline replay of a cached local-model run (same code path as a live run)"
LLM_BACKEND=replay LLM_MODEL=gemma4:12b-nvfp4 python3 -m navigator.extract --doc D081 --out /tmp/demo_replay; sleep "$P"
step "3. Pipeline consistency: 500 addresses, results per city, change tests"
python3 -m navigator.pipeline check | tail -14; sleep "$P"
step "4. Change tests T1 to T5 (affected addresses, conflict flags on T3)"
python3 - <<'PY'
import json
c = json.load(open("outputs/changes.json"))
for t in sorted(c):
    v = c[t]
    print(f"{t}: {len(v['affected_address_ids']):>3} affected, {len(v.get('conflict_flag_address_ids', [])):>3} conflict flags")
PY
sleep "$P"
step "5. Spot checks derived from the organizer brief (ours, not an official scorer)"
python3 eval/check_spots.py | tail -2; sleep "$P"
step "6. Our own proxy evaluation (a self-made key; NOT the organizers' score.py)"
python3 eval/score_proxy.py | sed -n '/PROXY ESTIMATE/,$p'; sleep "$P"
step "7. Unit tests"
python3 -m unittest discover -s tests -p 'test_*.py' 2>&1 | grep -E '^(Ran|OK|FAILED)'
printf '\nNot legal advice. Done.\n'
