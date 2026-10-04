#!/bin/sh
# Copy the pipeline output into web/data/. Refuses to publish if it is missing or not valid JSON.
set -e
cd "$(dirname "$0")"
SRC=../outputs/lookups_detail.json
[ -s "$SRC" ] || { echo "REFUSING: $SRC is missing or empty. Run: python3 -m navigator.pipeline build" >&2; exit 1; }
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['addresses'] and d['rules'] and d['tests']" "$SRC" || { echo "REFUSING: $SRC is not a valid lookups_detail file" >&2; exit 1; }
mkdir -p data
cp "$SRC" data/lookups_detail.json
echo "OK: copied $(wc -c < data/lookups_detail.json) bytes to web/data/lookups_detail.json"
