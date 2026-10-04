"""CLI: python3 -m navigator.pipeline build|check|ingest|rules-public  [--fixtures DIR --out DIR]"""
import argparse, datetime, json, shutil, sys
from collections import Counter, defaultdict
from .common import ROOT, AS_OF, RESULTS, load_json, dump_json, check_quote, manifest
from .apply import Engine, norm_date
from .explain import explain, _es_rules, es_entry, es_sha
from .changes import run_tests

NOTICE = "Not legal advice. This tool reports what public sources say and flags what it cannot tell; check with the city or a lawyer before acting."
ENGINE_ONLY = ["applies_if", "exempt_if", "yields_to", "conflicts_with"]


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cfg(fixtures=None, out=None):
    w, o = (ROOT / "work", ROOT / "outputs")
    c = {"rules": o / "rules_engine.json", "jur": w / "jurisdictions.json", "facts": w / "address_facts.json",
         "csv": None, "tests": [ROOT / "data/dev/change_tests.json", ROOT / "data/dev/change_tests_extra.json"],
         "ingested": o / "audit/ingested_tests.json", "out": o, "manifest": True}
    if fixtures:
        f = ROOT / fixtures if not str(fixtures).startswith("/") else __import__("pathlib").Path(fixtures)
        c.update(rules=f / "rules_engine.json", jur=f / "jurisdictions.json", facts=f / "address_facts.json", csv=f / "addresses.csv",
                 tests=[f / "change_tests.json"], ingested=(__import__("pathlib").Path(out) / "audit/ingested_tests.json") if out else None, manifest=False,
                 out=(__import__("pathlib").Path(out) if out else ROOT / "outputs"))
    elif out:
        c["out"] = __import__("pathlib").Path(out)
        c["ingested"] = c["out"] / "audit/ingested_tests.json"
    return c


def _event(c, stage, detail):
    p = c["out"] / "audit/events.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now(), "stage": stage, "actor": "engine", "detail": detail}, ensure_ascii=False) + "\n")


def _rows(c):
    if c["csv"]:
        import csv
        with open(c["csv"], newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    from .common import addresses
    return addresses()


def load_world(c):
    """-> rules(list), addrs {aid: {row, facts, loc, stack}}, notes(list)"""
    from .apply import CITY_NAMES
    d = load_json(c["rules"])
    rules = d["rules"] if isinstance(d, dict) else d
    notes = []
    jur = load_json(c["jur"]) if c["jur"].exists() else None
    facts = load_json(c["facts"]) if c["facts"].exists() else None
    if jur is None: notes.append("work/jurisdictions.json missing: fell back to postal_city mapping (low confidence)")
    if facts is None: notes.append("work/address_facts.json missing: fell back to CSV year_built/units (no lower bounds)")
    addrs = {}
    for r in _rows(c):
        a = r["address_id"]
        if facts and a in facts:
            f = facts[a]
        else:
            f = {"year_built": int(r["year_built"]) if r.get("year_built", "").isdigit() else None,
                 "units": int(float(r["units"])) if r.get("units") not in (None, "") else None, "units_min": None,
                 "units_source": "assessor" if r.get("units") else "none",
                 "use_code": r.get("use_code"), "use_description": r.get("use_description")}
        if jur and a in jur:
            j = jur[a]
            loc = {"state": r["state"], "legal_city": j.get("legal_city"), "geocode_status": j.get("geocode_status"), "postal_city": r.get("postal_city")}
            stack = {"state": j.get("state") or r["state"], "county": j.get("county"), "city": j.get("legal_city"),
                     "geocode_status": j.get("geocode_status"), "matched_address": j.get("matched_address"),
                     "lat": j.get("lat"), "lon": j.get("lon"), "notes": j.get("notes")}
        else:
            pc = f"{(r.get('postal_city') or '').strip().title()}, {r['state']}"
            lc = pc if pc in CITY_NAMES else None
            loc = {"state": r["state"], "legal_city": lc, "geocode_status": "fallback_postal", "postal_city": r.get("postal_city")}
            stack = {"state": r["state"], "county": None, "city": lc, "geocode_status": "fallback_postal", "matched_address": None,
                     "lat": None, "lon": None, "notes": "Legal city assumed from postal city (no geocode); low confidence."}
        addrs[a] = {"row": r, "facts": f, "loc": loc, "stack": stack}
    return rules, addrs, notes


def read_tests(c):
    tests = {}
    for p in c["tests"]:
        if p.exists():
            d = load_json(p)
            for t in (d if isinstance(d, list) else d.get("tests", [])):
                tests[t["test_id"]] = t
    if c.get("ingested") and c["ingested"].exists():
        tests.update(load_json(c["ingested"]))
    return [tests[k] for k in sorted(tests)]


def build(c=None, new_rule_ids=None, write=True):
    c = c or cfg()
    rules, addrs, notes = load_world(c)
    eng = Engine(rules, {a: {"facts": v["facts"], "loc": v["loc"]} for a, v in addrs.items()})
    alt_eng = Engine(rules, {a: {"facts": v["facts"], "loc": v["loc"]} for a, v in addrs.items()}, trust_units_min=True)
    R = eng.rules
    asof = AS_OF
    mf = manifest() if c["manifest"] else {}
    lookups, det_addr = {}, {}
    for a, v in addrs.items():
        cur = eng.at(a, asof)
        lookups[a] = [{"team_rule_id": rid, "result": e["result"],
                       "explanation": explain(e, R[rid], R, v["facts"], asof)[0], "conflict_flag": e["conflict_flag"]}
                      for rid, e in sorted(cur.items())]
        res = []
        use_alt = v["facts"].get("units") is None and v["facts"].get("units_min") is not None
        tlmap = eng.timeline_alt(a, alt_eng) if use_alt else {rid: [(d, e, None) for d, e in pts] for rid, pts in eng.timeline(a).items()}
        for rid, pts in sorted(tlmap.items()):
            tl = []
            for i, (d, e, alt_res) in enumerate(pts):
                if i < len(pts) - 1 and pts[i + 1][0] <= "2000-01-01":  # keeps the UI file small; no question in scope concerns dates before 2000
                    tl.append({"from": d, "result": "not_covered" if e is None else e["result"],
                               "explanation": "Before the earliest period this tool explains.",
                               "explanation_es": "Antes del primer periodo que explica esta herramienta."})
                    continue
                if e is None:
                    ent = {"from": d, "result": "not_covered", "explanation": "Not covered at this date.", "explanation_es": "No cubierto en esta fecha."}
                else:
                    en, es = explain(e, R[rid], R, v["facts"], "{ASOF}", parts=True)  # date-agnostic reasoning only, see CONTRACTS.md
                    ent = {"from": d, "result": e["result"], "explanation": en, "explanation_es": es}
                if use_alt and (alt_res or "not_covered") != ent["result"]:
                    ent["likely"] = alt_res or "not_covered"  # result if the class-derived unit bound were trusted (demo hint only)
                tl.append(ent)
            e = cur.get(rid) or next(x for _, x, _a in pts if x)
            now_res = cur[rid]["result"] if rid in cur else "not_covered"
            res.append({"team_rule_id": rid, "category": R[rid]["category"], "result": now_res,
                        "timeline": tl, "conflict_flag": e["conflict_flag"], "conflict_note": e["conflict_note"],
                        "confidence": e["confidence"], "facts_used": e["facts_used"], "missing_facts": e["missing_facts"],
                        "low_confidence": bool(now_res in ("applies", "superseded", "pending", "not_yet_effective") and e["confidence"] < 0.6)})
        r0 = v["row"]
        det_addr[a] = {"street_address": r0["street_address"], "postal_city": r0["postal_city"], "state": r0["state"], "zip": r0.get("zip"),
                       "facts": {k: v["facts"].get(k) for k in ("year_built", "units", "units_min", "units_source", "units_note", "use_code", "use_description")},
                       "stack": v["stack"], "results": res}
    tests = read_tests(c)
    changes, tdet, terr = run_tests(tests, eng, new_rule_ids)
    rules_detail = {}
    for rid, r in R.items():
        m = mf.get(r.get("source_doc_id"), {})
        rules_detail[rid] = {**r, "retrieved_at": m.get("retrieved_at"),
                             **{k: v for k, v in es_entry(r).items() if k in ("title_es", "requirement_es", "key_value_es")}}
    srcs = {}
    for r in R.values():
        m = mf.get(r.get("source_doc_id"))
        if m: srcs[m["doc_id"]] = {"doc_id": m["doc_id"], "url": m["url"], "retrieved_at": m.get("retrieved_at"), "sha256": m.get("sha256")}
    found = sum(1 for r in R.values() if check_quote(r.get("source_doc_id"), r.get("quoted_span")))
    ev = c["out"] / "audit/events.jsonl"
    runs = [json.loads(x) for x in ev.read_text().splitlines()[-40:]] if ev.exists() else []
    _x = load_json(c["rules"])
    stage_out = []
    if c["manifest"]:
        import glob, hashlib
        for pat in ("work/extract/*.json", "work/consolidate/*.json"):
            for f in sorted(glob.glob(str(ROOT / pat))):
                dd = load_json(f)
                stage_out.append({"file": f.split("/work/")[-1], "model": dd.get("extractor_model") or dd.get("consolidator_model"),
                                  "at": dd.get("extracted_at") or dd.get("consolidated_at"), "rules": len(dd.get("rules", [])),
                                  "sha256": hashlib.sha256(open(f, "rb").read()).hexdigest()})
    models = Counter(x["model"] or "unrecorded" for x in stage_out)
    detail = {"generated_at": now(), "as_of_default": asof, "not_legal_advice": NOTICE, "rules": rules_detail, "addresses": det_addr,
              "no_rule": _x.get("no_rule", []) if isinstance(_x, dict) else [], "gaps": _x.get("gaps", []) if isinstance(_x, dict) else [],
              "tests": tdet, "test_errors": terr,
              "audit": {"sources": sorted(srcs.values(), key=lambda x: x["doc_id"]), "runs": runs,
                        "validation": {"rules": "ok", "quotes_found": f"{found}/{len(R)}"}, "engine_notes": notes,
                        "llm_stage_outputs": {"files": len(stage_out), "by_model": dict(models)}}}
    summ = {"generated_at": now(), "as_of": asof, "addresses": len(addrs), "rules": len(R), "tests": sorted(changes), "test_errors": terr,
            "notes": notes, "counts": counts(eng, asof)}
    if write:
        o = c["out"]
        dump_json(o / "lookups.json", {"as_of": asof, "lookups": lookups})
        dump_json(o / "lookups_detail.json", detail, compact=True)
        dump_json(o / "changes.json", changes)
        dump_json(o / "audit/summary.json", summ)
        dump_json(o / "audit/llm_stage_outputs.json", stage_out)
        _event(c, "build", {"addresses": len(addrs), "rules": len(R), "tests": sorted(changes), "errors": terr, "notes": notes})
    return eng, lookups, changes, terr, summ


def counts(eng, asof):
    t = defaultdict(Counter)
    for a in eng.addrs:
        for rid, e in eng.at(a, asof).items():
            t[eng.rules[rid]["jurisdiction"]][e["result"]] += 1
    return {j: dict(v) for j, v in sorted(t.items())}


def check(c=None):
    c = c or cfg()
    errs = []
    rules, addrs, _ = load_world(c)
    lk = load_json(c["out"] / "lookups.json")
    ids = {r["team_rule_id"] for r in rules}
    if c["manifest"]:
        for r in rules:
            if not es_entry(r): errs.append(f"{r['team_rule_id']}: Spanish text missing or stale (src_sha does not match the current English title/requirement/key_value)")
    if set(lk["lookups"]) != set(addrs): errs.append(f"lookups cover {len(lk['lookups'])} addresses, expected {len(addrs)}")
    for a, es in lk["lookups"].items():
        for e in es:
            if e["result"] not in RESULTS: errs.append(f"{a}: bad result {e['result']}")
            if e["team_rule_id"] not in ids: errs.append(f"{a}: unknown rule {e['team_rule_id']}")
            if not e["explanation"].rstrip().endswith("Not legal advice."): errs.append(f"{a}/{e['team_rule_id']}: missing notice")
    used = {e["team_rule_id"] for es in lk["lookups"].values() for e in es if e["result"] == "applies"}
    for r in rules:
        if c["manifest"] and r["team_rule_id"] in used and not check_quote(r.get("source_doc_id"), r.get("quoted_span")):
            errs.append(f"{r['team_rule_id']}: quoted span no longer validates in {r.get('source_doc_id')}")
    ch = load_json(c["out"] / "changes.json")
    want = [t["test_id"] for t in read_tests(c)]
    for t in want:
        if t not in ch: errs.append(f"changes.json missing {t}")
    eng = Engine(rules, {a: {"facts": v["facts"], "loc": v["loc"]} for a, v in addrs.items()})
    for j, v in counts(eng, lk["as_of"]).items(): print(f"{j:20s}", v)
    print(f"{len(lk['lookups'])} addresses, {len(rules)} rules, tests {sorted(ch)}")
    for e in errs: print("ERROR", e)
    print("CHECK", "FAILED" if errs else "OK")
    return 1 if errs else 0


def rules_public(c=None):
    c = c or cfg()
    d = load_json(c["rules"]); rules = d["rules"] if isinstance(d, dict) else d
    from .merge_rules import PUBLIC
    dump_json(c["out"] / "rules.json", {"rules": [{k: r.get(k) for k in PUBLIC} for r in rules]})
    print(f"wrote {c['out'] / 'rules.json'} ({len(rules)} rules)")


def _snapshot(eng):
    return {a: {rid: e["result"] for rid, e in eng.at(a, AS_OF).items()} for a in eng.addrs}


def ingest(extract, tests_path=None, c=None):
    from .validate import check_extract
    from pathlib import Path
    c = c or cfg()
    ex = Path(extract)
    if check_extract(ex):
        print("extraction file invalid; nothing changed"); return 1
    d = load_json(ex)
    new = d["rules"]
    before_eng = build(c, write=False)[0]
    before = _snapshot(before_eng)
    cur = load_json(c["rules"]); rules = cur["rules"] if isinstance(cur, dict) else cur
    n = max([int(r["team_rule_id"].split("-")[1]) for r in rules if r["team_rule_id"].startswith("r-")] or [0])
    ids = []
    for r in new:
        n += 1
        r = dict(r); r["team_rule_id"] = f"r-{n:04d}"; ids.append(r["team_rule_id"]); rules.append(r)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (c["out"] / "audit").mkdir(parents=True, exist_ok=True)
    shutil.copy(c["rules"], c["out"] / f"audit/rules_engine.{ts}.json")
    if isinstance(cur, dict): cur["rules"] = rules
    dump_json(c["rules"], cur if isinstance(cur, dict) else {"rules": rules})
    docid = d.get("doc_id") or ex.stem
    ing = load_json(c["ingested"]) if c["ingested"].exists() else {}
    if tests_path:
        tl = load_json(tests_path); tl = tl if isinstance(tl, list) else tl.get("tests", [])
    else:
        tl = []
    new_tests = [t for t in tl if t.get("type") == "new_rule" or t.get("type") not in ("as_of", "boundary", "pending", "negative")]
    if not new_tests:
        new_tests = [{"test_id": "T6", "title": "New ordinance: " + "; ".join(r["title"] for r in new), "type": "new_rule",
                      "as_of": AS_OF, "expected_behavior": "Affected addresses for the newly ingested rule(s); future effective date reported as not_yet_effective."}]
    for t in new_tests:
        t = dict(t); t["rule_ids"] = ids
        ing[t["test_id"]] = t
    dump_json(c["ingested"], ing)
    eng, lk, changes, terr, summ = build(c)
    after = _snapshot(eng)
    changed = {a: {"before": {r: before[a].get(r) for r in set(before[a]) | set(after[a]) if before[a].get(r) != after[a].get(r)},
                   "after": {r: after[a].get(r) for r in set(before[a]) | set(after[a]) if before[a].get(r) != after[a].get(r)}}
               for a in after if before[a] != after[a]}
    t6 = {k: changes[k] for k in ing if k in changes}
    dump_json(c["out"] / f"audit/ingest_{docid}.json", {"ts": now(), "source_extract": str(ex), "rules_added": [
        {"team_rule_id": i, "title": r["title"], "jurisdiction": r["jurisdiction"], "status": r["status"], "effective_date": r.get("effective_date")} for i, r in zip(ids, new)],
        "addresses_changed": changed, "n_addresses_changed": len(changed), "changes_entries": t6, "test_errors": terr})
    _event(c, "ingest", {"doc": docid, "rules_added": ids, "addresses_changed": len(changed)})
    print(f"ingested {len(ids)} rule(s) {ids}; {len(changed)} addresses changed; tests {sorted(t6)}; errors {terr}")
    return 2 if terr else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="navigator.pipeline")
    ap.add_argument("cmd", choices=["build", "check", "ingest", "rules-public"])
    ap.add_argument("--extract"); ap.add_argument("--tests"); ap.add_argument("--fixtures"); ap.add_argument("--out")
    a = ap.parse_args(argv)
    c = cfg(a.fixtures, a.out)
    if not c["rules"].exists():
        print(f"ERROR: {c['rules']} not found (consolidators produce it)"); return 1
    if a.cmd == "build":
        eng, lk, ch, terr, summ = build(c)
        print(f"built {len(lk)} addresses, tests {sorted(ch)}; wrote {c['out']}")
        for j, v in summ["counts"].items(): print(f"  {j:20s}", v)
        for n in summ["notes"]: print("NOTE", n)
        for t, m in terr.items(): print(f"TEST ERROR {t}: {m}")
        return 2 if terr else 0
    if a.cmd == "check": return check(c)
    if a.cmd == "rules-public": return rules_public(c)
    if not a.extract: ap.error("ingest needs --extract")
    return ingest(a.extract, a.tests, c)


if __name__ == "__main__":
    sys.exit(main())
