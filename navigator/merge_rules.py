"""Merge stage-2 consolidation files into outputs/rules_engine.json (+ public outputs/rules.json).
  python3 -m navigator.merge_rules            # reads work/consolidate/*.json
Deterministic: renumbers ids r-0001.., prunes yields_to/conflicts_with descriptors that point at cells with no rule,
checks every cell of the 13 x 6 grid is accounted for, validates, writes an audit record."""
import glob, sys, time
from .common import *
from .validate import rule_errors

PUBLIC = ["team_rule_id", "jurisdiction", "level", "category", "status", "title", "requirement", "key_value",
          "coverage_conditions", "exemptions", "overrides", "interaction", "effective_date", "citation",
          "source_doc_id", "source_url", "quoted_span", "confidence", "conflict_flag", "conflict_note"]


def merge(files=None, out_dir=None):
    out = ROOT / (out_dir or "outputs")
    files = files or sorted(glob.glob(str(ROOT / "work/consolidate/*.json")))
    rules, no_rule, gaps, notes = [], [], [], []
    for f in files:
        d = load_json(f)
        rules += d.get("rules", []); no_rule += d.get("no_rule", []); gaps += d.get("gaps", [])
        notes += [{"group": d.get("group"), "decision": x} for x in d.get("decisions", [])]
    order = lambda r: (JURISDICTIONS.index(r["jurisdiction"]), CATEGORIES.index(r["category"]), r.get("effective_date") or "",
                       r.get("citation") or "", r.get("title") or "")
    rules.sort(key=order)
    idmap = {}
    for i, r in enumerate(rules, 1):
        idmap[r.get("team_rule_id")] = f"r-{i:04d}"
        r["team_rule_id"] = f"r-{i:04d}"
    cells = {(r["jurisdiction"], r["category"]) for r in rules}
    pruned = []
    for r in rules:
        for x in r.get("overrides") or []:
            if x not in idmap:
                pruned.append({"rule": r["team_rule_id"], "field": "overrides", "dangling_id": x})
        r["overrides"] = [idmap[x] for x in r.get("overrides") or [] if x in idmap]
        for k in ("yields_to", "conflicts_with"):
            keep = []
            for dsc in r.get(k) or []:
                if (dsc["jurisdiction"], dsc["category"]) in cells and (dsc["jurisdiction"], dsc["category"]) != (r["jurisdiction"], r["category"]):
                    keep.append(dsc)
                else:
                    pruned.append({"rule": r["team_rule_id"], "field": k, "descriptor": dsc})
            r[k] = keep
    covered = cells | {(x["jurisdiction"], x["category"]) for x in no_rule + gaps}
    missing = [(j, c) for j in JURISDICTIONS for c in CATEGORIES if (j, c) not in covered]
    errs = [f"{r['team_rule_id']}: {m}" for r in rules for m in rule_errors(r, None)]
    stamp = time.strftime("%Y%m%dT%H%M%S")
    dump_json(out / "rules_engine.json", {"rules": rules, "no_rule": no_rule, "gaps": gaps})
    dump_json(out / "rules.json", {"rules": [{k: r.get(k) for k in PUBLIC} for r in rules]})
    dump_json(out / "audit" / f"merge_{stamp}.json", {"idmap": idmap, "pruned_descriptors": pruned, "cells_unaccounted": missing,
                                                      "errors": errs, "decisions": notes, "files": [Path(f).name for f in files]})
    print(f"{len(rules)} rules, {len(no_rule)} no_rule, {len(gaps)} gaps, {len(pruned)} descriptors pruned, "
          f"{len(missing)} cells unaccounted, {len(errs)} errors")
    for m in missing: print("  UNACCOUNTED CELL:", m)
    for e in errs[:20]: print("  ERR:", e)
    return len(errs)


if __name__ == "__main__":
    sys.exit(1 if merge() else 0)
