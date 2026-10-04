"""Stage 2 runner: python3 -m navigator.consolidate --group CA1|CA2|NJ|MA [--out DIR] [--max-retries 2]
Best with a strong model (prompts are large). Never overwrites work/consolidate unless --out work/consolidate is explicit."""
import argparse, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
from . import llm
from .common import CATEGORIES, ROOT, doc_text, dump_json, load_json
from .extract import run_loop
from .validate import rule_errors

GROUPS = {"CA1": ["CA", "Los Angeles, CA", "San Diego, CA", "Santa Ana, CA"],
          "CA2": ["San Francisco, CA", "Berkeley, CA"],
          "NJ": ["NJ", "Jersey City, NJ", "Hoboken, NJ", "Newark, NJ"],
          "MA": ["MA", "Boston, MA", "Cambridge, MA"]}
MAX_DOC = 12000

WRAPPER = """You are the consolidation engine described below. You are NOT an agent with file access: all inputs are in this
message. Answer with ONLY one JSON object (no prose, no code fence) with the keys rules, no_rule, gaps, missing_expected,
decisions exactly as described in the output section. Ignore instructions about writing files and running the validator.
GROUP: {group}. Jurisdictions: {juris}. Cells (jurisdiction x category): {n} cells = {juris} x {cats}.

=== RECORD FIELDS, JURISDICTIONS, CITATION FORMATS, PREDICATE GRAMMAR (from CONTRACTS.md) ===
{contracts}

=== CONSOLIDATION INSTRUCTIONS (prompts/consolidate_cells.md) ===
{prompt}

=== STAGE 1 CANDIDATES FOR THIS GROUP ===
{cands}

=== SOURCE TEXTS CITED BY THE CANDIDATES (truncated around the quoted spans) ===
{docs}
"""


def window(text, spans):
    if len(text) <= MAX_DOC:
        return text
    keep = max(MAX_DOC // max(len(spans), 1), 1500)
    parts = []
    for s in spans:
        i = text.find(s[:60])
        i = 0 if i < 0 else i
        parts.append(text[max(0, i - keep // 2): i + keep // 2])
    return "\n[...]\n".join(parts)[:MAX_DOC]


def build_prompt(group, extract_dir=None):
    from .extract import contracts_excerpt
    juris = GROUPS[group]
    d = Path(extract_dir) if extract_dir else ROOT / "work" / "extract"
    cands, spans = [], {}
    for f in sorted(d.glob("[DX]*.json")):
        for r in load_json(f).get("rules", []):
            if r.get("jurisdiction") in juris:
                cands.append(r)
                spans.setdefault(r.get("source_doc_id") or f.stem, []).append(r.get("quoted_span") or "")
    docs = "\n\n".join(f"--- {k} ---\n{window(doc_text(k) or '(text unavailable)', v)}" for k, v in sorted(spans.items()))
    return (WRAPPER.replace("{contracts}", contracts_excerpt())
            .replace("{prompt}", (ROOT / "prompts" / "consolidate_cells.md").read_text(encoding="utf-8"))
            .replace("{group}", group).replace("{juris}", ", ".join(juris)).replace("{n}", str(len(juris) * 6))
            .replace("{cats}", ", ".join(CATEGORIES)).replace("{cands}", json.dumps(cands, ensure_ascii=False))
            .replace("{docs}", docs))


def consolidate(group, max_retries=2, extract_dir=None):
    log = []

    def check(obj):
        if not isinstance(obj, dict) or not isinstance(obj.get("rules"), list):
            return ["top-level 'rules' list missing"]
        errs = []
        for r in obj["rules"]:
            errs += [f"{r.get('team_rule_id')} ({r.get('citation')}): {m}" for m in rule_errors(r, None)]
        cells = [(r.get("jurisdiction"), r.get("category")) for r in obj["rules"]] + \
                [(x.get("jurisdiction"), x.get("category")) for x in obj.get("no_rule", []) + obj.get("gaps", [])]
        missing = [(j, c) for j in GROUPS[group] for c in CATEGORIES if (j, c) not in cells]
        if missing:
            errs.append(f"cells absent from rules/no_rule/gaps: {missing}")
        return errs

    t0 = time.time()
    obj, errs, retries = run_loop(build_prompt(group, extract_dir), "consolidate", group, check, max_retries, log)
    obj = obj if isinstance(obj, dict) else {}
    out = {"group": group, "consolidator_model": f"{__import__('os').environ.get('LLM_BACKEND', 'replay')}:{llm._model()}",
           "consolidated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           **{k: obj.get(k, []) for k in ("rules", "no_rule", "gaps", "missing_expected", "decisions")},
           "run": {"validation_errors": errs, "retries": retries}}
    return out, round(time.time() - t0, 1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True, choices=list(GROUPS))
    ap.add_argument("--out", default="work/consolidate_run")
    ap.add_argument("--max-retries", type=int, default=2)
    a = ap.parse_args(argv)
    out_dir = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
    if out_dir.resolve() == (ROOT / "work" / "consolidate").resolve() and a.out != "work/consolidate":
        raise SystemExit("refusing to write work/consolidate unless --out work/consolidate is given explicitly")
    try:
        res, secs = consolidate(a.group, a.max_retries)
    except (llm.CacheMiss, llm.Pending) as e:
        raise SystemExit(f"{a.group}: SKIPPED {e}")
    dump_json(out_dir / f"{a.group}.json", res)
    print(f"{a.group}: rules={len(res['rules'])} no_rule={len(res['no_rule'])} gaps={len(res['gaps'])} "
          f"errors={len(res['run']['validation_errors'])} retries={res['run']['retries']} seconds={secs}")


if __name__ == "__main__":
    main()
