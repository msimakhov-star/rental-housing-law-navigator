"""Validate extraction/rules files. Exit 1 on any error.
  python3 -m navigator.validate --extract work/extract[/Dxxx.json]
  python3 -m navigator.validate --rules outputs/rules_engine.json
  python3 -m navigator.validate --selftest"""
import argparse, re, sys
from pathlib import Path
from .common import *

FACTS = {"units", "year_built", "building_age_years", "co_date"}
OPS = {">=", ">", "<=", "<", "==", "!="}
REQ = ["jurisdiction", "level", "category", "status", "title", "requirement", "citation", "source_url", "quoted_span"]
DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
DASH = re.compile("[–—]")
TEXT_FIELDS = ["title", "requirement", "key_value", "coverage_conditions", "exemptions", "interaction", "conflict_note", "citation"]


def pred_errors(p, path="pred"):
    if p is None:
        return []
    if not isinstance(p, dict):
        return [f"{path}: not an object"]
    ks = set(p)
    if ks <= {"all", "any"} and len(ks) == 1:
        k = next(iter(ks))
        if not isinstance(p[k], list) or not p[k]:
            return [f"{path}.{k}: needs a non-empty list"]
        return [e for i, x in enumerate(p[k]) for e in pred_errors(x, f"{path}.{k}[{i}]")]
    if ks == {"not"}:
        return pred_errors(p["not"], f"{path}.not")
    if ks == {"unavailable"}:
        return [] if isinstance(p["unavailable"], str) and p["unavailable"] else [f"{path}: empty unavailable"]
    if ks == {"fact", "op", "value"}:
        e = []
        if p["fact"] not in FACTS: e.append(f"{path}: unknown fact {p['fact']!r}")
        if p["op"] not in OPS: e.append(f"{path}: bad op {p['op']!r}")
        if p["fact"] == "co_date" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(p["value"])): e.append(f"{path}: co_date value must be yyyy-mm-dd")
        if p["fact"] != "co_date" and not isinstance(p["value"], (int, float)): e.append(f"{path}: numeric fact needs numeric value")
        return e
    return [f"{path}: unrecognised shape {sorted(ks)}"]


def desc_errors(lst, path):
    if lst in (None, []):
        return []
    if not isinstance(lst, list):
        return [f"{path}: not a list"]
    return [f"{path}[{i}]: bad descriptor {d!r}" for i, d in enumerate(lst)
            if not (isinstance(d, dict) and d.get("jurisdiction") in JURISDICTIONS and d.get("category") in CATEGORIES)]


def rule_errors(r, doc_id=None, engine=True):
    e = [f"missing {k}" for k in REQ if r.get(k) in (None, "")]
    if r.get("jurisdiction") not in JURISDICTIONS: e.append(f"jurisdiction {r.get('jurisdiction')!r} not in allowed set")
    if r.get("level") not in ("state", "city"): e.append("level must be state|city")
    elif (r.get("jurisdiction") in STATES) != (r["level"] == "state"): e.append("level does not match jurisdiction")
    if r.get("category") not in CATEGORIES: e.append(f"bad category {r.get('category')!r}")
    if r.get("status") not in STATUSES: e.append(f"bad status {r.get('status')!r}")
    ed = r.get("effective_date")
    if ed is not None and not DATE.match(str(ed)): e.append(f"effective_date {ed!r} not ISO")
    dk = r.get("date_kind")
    if dk is not None and dk not in ("law", "version"): e.append("date_kind must be law|version")
    if dk and not r.get("effective_date"): e.append("date_kind without effective_date")
    c = r.get("confidence")
    if c is not None and not (isinstance(c, (int, float)) and 0 <= c <= 1): e.append("confidence outside 0..1")
    q = r.get("quoted_span") or ""
    if len(q) < 20: e.append("quoted_span shorter than 20 chars")
    if len(q) > 400: e.append("quoted_span longer than 400 chars")
    sd = r.get("source_doc_id") or doc_id
    if doc_id and r.get("source_doc_id") not in (None, doc_id): e.append(f"source_doc_id {r['source_doc_id']} != file doc {doc_id}")
    if sd:
        if q and check_quote(sd, q) is None: e.append(f"quoted_span NOT FOUND in {sd}: {q[:70]!r}")
    else:
        e.append("no source_doc_id")
    for k in TEXT_FIELDS:
        if isinstance(r.get(k), str) and DASH.search(r[k]): e.append(f"{k}: contains en/em dash (use '-', 'to' or a comma)")
    if engine:
        e += pred_errors(r.get("applies_if"), "applies_if") + pred_errors(r.get("exempt_if"), "exempt_if")
        e += desc_errors(r.get("yields_to"), "yields_to") + desc_errors(r.get("conflicts_with"), "conflicts_with")
    return e


def check_extract(path):
    n_err = n_rules = 0
    files = sorted(Path(path).glob("D*.json")) + sorted(Path(path).glob("X*.json")) if Path(path).is_dir() else [Path(path)]
    for f in files:
        d = load_json(f)
        doc = d.get("doc_id") or f.stem
        errs = [] if "rules" in d and isinstance(d["rules"], list) else ["top-level 'rules' list missing"]
        for i, r in enumerate(d.get("rules", [])):
            n_rules += 1
            errs += [f"rule[{i}] ({r.get('citation')}): {m}" for m in rule_errors(r, doc)]
        if errs: print(f"{f.name}: {len(errs)} error(s)"); [print("  -", m) for m in errs]
        n_err += len(errs)
    print(f"{len(files)} file(s), {n_rules} rule(s), {n_err} error(s)")
    return n_err


def check_rules(path):
    d = load_json(path)
    rules = d["rules"] if isinstance(d, dict) else d
    errs, seen = [], set()
    for r in rules:
        rid = r.get("team_rule_id")
        if not rid: errs.append("rule without team_rule_id")
        elif rid in seen: errs.append(f"duplicate id {rid}")
        seen.add(rid)
        errs += [f"{rid}: {m}" for m in rule_errors(r, None)]
    [print("  -", m) for m in errs]
    print(f"{len(rules)} rule(s), {len(errs)} error(s)")
    return len(errs)


def selftest():
    assert pred_errors({"all": [{"fact": "units", "op": ">=", "value": 5}, {"unavailable": "owner type"}]}) == []
    assert pred_errors({"fact": "units", "op": "=>", "value": 5})
    assert pred_errors({"fact": "co_date", "op": "<=", "value": "1979"})
    assert desc_errors([{"jurisdiction": "CA", "category": "nope"}], "x")
    assert norm_ws("a \n  b") == "a b"
    r = {"jurisdiction": "CA", "level": "state", "category": "security_deposits", "status": "in_force", "title": "t",
         "requirement": "r", "citation": "c", "source_url": "u", "quoted_span": "short"}
    assert any("shorter" in m for m in rule_errors(r, "D025"))
    print("validate selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract"); ap.add_argument("--rules"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest: selftest(); sys.exit(0)
    sys.exit(1 if (check_extract(a.extract) if a.extract else check_rules(a.rules)) else 0)
