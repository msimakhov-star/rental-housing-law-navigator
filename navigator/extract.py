"""Stage 1 runner: python3 -m navigator.extract --doc D081 [--doc ...] [--all] [--out DIR] [--max-retries 2]
Backend chosen by LLM_BACKEND (see navigator/llm.py). Never overwrites work/extract unless --out work/extract is explicit."""
import argparse, difflib, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from . import llm
from .common import ROOT, doc_text, dump_json, manifest
from .validate import rule_errors

WRAPPER = """You are the extraction engine described below. You are NOT an agent with file access: you receive the
document text at the end of this message and must answer with ONLY one JSON object (no prose, no code fence):
{"doc_id":"<id>","rules":[<RULE>,...],"notes":"<ambiguities / what the doc does not cover>"}
Each RULE has the record fields listed below (omit team_rule_id). Ignore any instruction about writing files,
running the validator, extractor_model or the final report: they do not apply to you. quoted_span must be copied
character for character from the document. If nothing in the six categories is supported, return "rules": [].

=== RECORD FIELDS, JURISDICTIONS, CITATION FORMATS, PREDICATE GRAMMAR (from CONTRACTS.md) ===
{contracts}

=== EXTRACTION INSTRUCTIONS (prompts/extract_doc.md) ===
{prompt}

=== MANIFEST ROW ===
{manifest}

=== DOCUMENT {doc_id} ===
{text}
"""


def contracts_excerpt():
    t = (ROOT / "CONTRACTS.md").read_text(encoding="utf-8")
    return t[t.index("## Rule record"):t.index("## Result values")]


def build_prompt(doc_id):
    text = doc_text(doc_id)
    if text is None:
        raise SystemExit(f"unknown doc {doc_id}")
    man = {k: v for k, v in manifest().get(doc_id, {}).items() if k in ("doc_id", "jurisdictions", "url", "source_type", "retrieved_at")}
    return (WRAPPER.replace("{contracts}", contracts_excerpt())
            .replace("{prompt}", (ROOT / "prompts" / "extract_doc.md").read_text(encoding="utf-8"))
            .replace("{manifest}", json.dumps(man)).replace("{doc_id}", doc_id).replace("{text}", text))


def parse_json(s):
    s = s.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    if not s.startswith("{"):  # tolerate prose before/after
        a, b = s.find("{"), s.rfind("}")
        if a >= 0 and b > a:
            s = s[a:b + 1]
    return json.loads(s)


def repair_quote(doc_id, span, log):
    """Replace a not-found span by the one document line that matches it with ratio >= 0.9 (unique)."""
    from .common import check_quote
    if check_quote(doc_id, span):
        return span
    hits = [ln.strip() for ln in doc_text(doc_id).splitlines()
            if 20 <= len(ln.strip()) <= 400 and difflib.SequenceMatcher(None, span, ln.strip()).ratio() >= 0.9]
    if len(set(hits)) == 1:
        log.append(f"quote repaired: {span[:50]!r} -> {hits[0][:50]!r}")
        return hits[0]
    return span


def run_loop(prompt, stage, key, check, max_retries, log):
    """Call the model, parse, check(obj)->errors; on errors retry with feedback. Returns (obj, errors, retries)."""
    obj, errs, cur = None, ["no attempt"], prompt
    for attempt in range(max_retries + 1):
        raw = llm.complete(cur, stage=stage, key=key)
        try:
            obj = parse_json(raw)
            errs = check(obj)
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as e:
            obj, errs = None, [f"response is not valid JSON object: {e}"]
        if not errs:
            return obj, [], attempt
        cur = (prompt + "\n\n=== YOUR PREVIOUS ANSWER FAILED VALIDATION ===\n" + "\n".join("- " + e for e in errs[:30])
               + "\nReturn the complete corrected JSON object only.")
        log.append(f"attempt {attempt}: {len(errs)} error(s)")
    return obj, errs, max_retries


def extract_doc(doc_id, max_retries=2):
    log, man = [], manifest().get(doc_id, {})

    def check(obj):
        if not isinstance(obj, dict) or not isinstance(obj.get("rules"), list):
            return ["top-level 'rules' list missing"]
        errs = []
        for i, r in enumerate(obj["rules"]):
            r.setdefault("source_doc_id", doc_id)
            if not r.get("source_url") and man.get("url"):
                r["source_url"] = man["url"]
            if isinstance(r.get("quoted_span"), str):
                r["quoted_span"] = repair_quote(doc_id, r["quoted_span"], log)
            errs += [f"rule[{i}] ({r.get('citation')}): {m}" for m in rule_errors(r, doc_id)]
        return errs

    t0 = time.time()
    obj, errs, retries = run_loop(build_prompt(doc_id), "extract", doc_id, check, max_retries, log)
    obj = obj if isinstance(obj, dict) else {"rules": []}
    out = {"doc_id": doc_id, "extractor_model": f"{__import__("os").environ.get('LLM_BACKEND', 'replay')}:{llm._model()}",
           "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "rules": obj.get("rules", []), "notes": obj.get("notes") or "",
           "run": {"validation_errors": errs, "retries": retries, "repairs": [m for m in log if m.startswith("quote")]}}
    return out, round(time.time() - t0, 1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default="work/extract_run")
    ap.add_argument("--max-retries", type=int, default=2)
    a = ap.parse_args(argv)
    out_dir = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
    if out_dir.resolve() == (ROOT / "work" / "extract").resolve() and a.out != "work/extract":
        raise SystemExit("refusing to write work/extract unless --out work/extract is given explicitly")
    docs = a.doc or []
    if a.all:
        docs = sorted(d for d in manifest() if doc_text(d))
    if not docs:
        raise SystemExit("give --doc ID or --all")
    for d in docs:
        try:
            res, secs = extract_doc(d, a.max_retries)
        except (llm.CacheMiss, llm.Pending) as e:
            print(f"{d}: SKIPPED {e}")
            continue
        dump_json(out_dir / f"{d}.json", res)
        print(f"{d}: rules={len(res['rules'])} errors={len(res['run']['validation_errors'])} retries={res['run']['retries']} seconds={secs}")


if __name__ == "__main__":
    main()
