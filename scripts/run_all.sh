#!/bin/sh
# Rebuild all outputs from the caches (no network, no model). Run from anywhere.
set -e
cd "$(dirname "$0")/.."
python3 -m navigator.merge_rules
python3 -m navigator.pipeline build
python3 -m navigator.pipeline check
