"""Replace third-party gap-fill page texts in the PUBLIC copy by quote-only stubs.
Usage: python3 scripts/make_quote_stubs.py <public_repo_dir>
Keeps the full text only for government-hosted pages (OFFICIAL); for every other data/corpus_extra/text/Xnnn.txt writes
the SOURCE/RETRIEVED/VIA header plus ONLY the spans our rules quote (one per line), so the validators still pass and the
full text of news, law-firm and code-publisher pages is not redistributed."""
import glob, json, os, sys

OFFICIAL = {"X028", "X030"}  # government-hosted text (San Diego city server, Jersey City civicweb ordinance)
dst = sys.argv[1]
spans = {}
for f in glob.glob(os.path.join(dst, "work/extract/X*.json")) + glob.glob(os.path.join(dst, "work/consolidate/*.json")) + [os.path.join(dst, "outputs/rules_engine.json")]:
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    for r in d.get("rules", []):
        sid = r.get("source_doc_id")
        if sid and sid.startswith("X") and r.get("quoted_span"):
            spans.setdefault(sid, set()).add(r["quoted_span"])
n = 0
for p in sorted(glob.glob(os.path.join(dst, "data/corpus_extra/text/X*.txt"))):
    xid = os.path.basename(p)[:-4]
    if xid in OFFICIAL:
        continue
    head = []
    for ln in open(p, encoding="utf-8").read().splitlines()[:4]:
        head.append(ln)
    body = sorted(spans.get(xid, []))
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(head) + "\n\nQUOTE-ONLY STUB: the full page is not redistributed; fetch it from the SOURCE url above. Quoted spans used by our rules:\n" + "\n".join(body) + "\n")
    n += 1
print(f"stubbed {n} third-party pages; full text kept for {sorted(OFFICIAL)}")
