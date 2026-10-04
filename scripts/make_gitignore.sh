#!/bin/sh
# Write a .gitignore for the public repo. Not redistributing data/corpus (licence TBD); keeping outputs, quoted spans (in outputs), caches.
cd "$(dirname "$0")/.."
cat > .gitignore <<'EOF'
# built package
submission/
# supplied corpus and addresses: licence TBD, do not redistribute (get them from the organizers' starter pack)
data/corpus/
data/sample_addresses.csv
# gap-fill pages we fetched ourselves: also third-party text
data/corpus_extra/text/
# local scratch
__pycache__/
*.pyc
.DS_Store
.env
/tmp/
work/demo_local/
EOF
echo "wrote .gitignore"
