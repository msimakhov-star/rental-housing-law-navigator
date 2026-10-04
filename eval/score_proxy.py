#!/usr/bin/env python3
"""PROXY scorer (stdlib only). Not the organizers' score.py. See eval/README.md."""
import argparse, csv, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from navigator import common  # noqa: E402

check_quote = common.check_quote   # module-level so tests can patch
doc_text = common.doc_text

CATS = common.CATEGORIES
RESULTS = common.RESULTS
J13 = common.JURISDICTIONS


# ---------- tiny JSON-schema validator ----------
def _isty(v, t):
    return {"string": isinstance(v, str), "null": v is None, "boolean": isinstance(v, bool),
            "number": isinstance(v, (int, float)) and not isinstance(v, bool),
            "integer": isinstance(v, int) and not isinstance(v, bool),
            "array": isinstance(v, list), "object": isinstance(v, dict)}[t]


def validate(v, sch, path="$"):
    errs = []
    if "type" in sch:
        ts = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_isty(v, t) for t in ts):
            return [f"{path}: expected {ts}, got {type(v).__name__}"]
    if "enum" in sch and v not in sch["enum"]:
        errs.append(f"{path}: {v!r} not in enum")
    if isinstance(v, str):
        if len(v) < sch.get("minLength", 0):
            errs.append(f"{path}: shorter than {sch['minLength']}")
        if "pattern" in sch and not re.search(sch["pattern"], v):
            errs.append(f"{path}: {v!r} fails pattern")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in sch and v < sch["minimum"]: errs.append(f"{path}: below minimum")
        if "maximum" in sch and v > sch["maximum"]: errs.append(f"{path}: above maximum")
    if isinstance(v, dict):
        for r in sch.get("required", []):
            if r not in v: errs.append(f"{path}: missing required '{r}'")
        for k, s in sch.get("properties", {}).items():
            if k in v: errs += validate(v[k], s, f"{path}.{k}")
    if isinstance(v, list) and "items" in sch:
        for i, x in enumerate(v): errs += validate(x, sch["items"], f"{path}[{i}]")
    return errs


STR_LIST = {"type": "array", "items": {"type": "string"}}
LOOKUP_ENTRY = {"type": "object", "required": ["team_rule_id", "result", "explanation", "conflict_flag"],
                "properties": {"team_rule_id": {"type": "string"}, "result": {"enum": RESULTS},
                               "explanation": {"type": "string"}, "conflict_flag": {"type": "boolean"}}}
LOOKUPS_SCHEMA = {"type": "object", "required": ["as_of", "lookups"],
                  "properties": {"as_of": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                                 "lookups": {"type": "object"}}}
CHANGE_ENTRY = {"type": "object", "required": ["affected_address_ids"],
                "properties": {"affected_address_ids": STR_LIST, "conflict_flag_address_ids": STR_LIST,
                               "notes": {"type": ["string", "null"]}}}


def load(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def rules_list(d):
    return d if isinstance(d, list) else (d or {}).get("rules", [])


def city_key(addr_row, jur):
    """(state, legal_city 'City, ST') for an address; geocoded stack if present, else CSV."""
    j = (jur or {}).get(addr_row["address_id"]) or {}
    st = j.get("state") or addr_row["state"]
    city = j.get("legal_city") or f"{addr_row['postal_city'].strip().title()}, {addr_row['state']}"
    return st, city


def load_addresses(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------- pieces ----------
def match_rules(key_entry, rules):
    rx = re.compile(key_entry["cite_regex"], re.I)
    out = []
    for r in rules:
        if r.get("jurisdiction") == key_entry["jurisdiction"] and r.get("category") == key_entry["category"]:
            if rx.search(str(r.get("citation", ""))): out.append((r, "cite"))
            elif rx.search(str(r.get("title", ""))): out.append((r, "title_only"))
    return out


def date_ok(key, got):
    if not got: return False
    return any(got == c or (len(c) < len(got) and got.startswith(c))
               for c in [key["effective_date"]] + key.get("effective_date_alt", []))


def field_hits(key, r):
    hits, total = {}, {}
    if "status" in key:
        total["status"] = 1; hits["status"] = int(r.get("status") == key["status"])
    if "effective_date" in key:
        total["effective_date"] = 1; hits["effective_date"] = int(date_ok(key, r.get("effective_date")))
    if key.get("key_value_hint"):
        total["key_value"] = 1
        hits["key_value"] = int(bool(re.search(key["key_value_hint"], str(r.get("key_value") or ""), re.I)))
    return hits, total


def recall_report(pkey, rules):
    rows, fh, ft = [], Counter(), Counter()
    for k in pkey:
        m = match_rules(k, rules)
        best, bh = None, -1
        for r, how in m:
            h, t = field_hits(k, r)
            if sum(h.values()) > bh: best, bh, bhits, btot, bhow = r, sum(h.values()), h, t, how
        row = {"id": k["id"], "found": bool(m), "n_matches": len(m)}
        if best:
            row.update(rule=best.get("team_rule_id"), via=bhow, hits=bhits, total=btot)
            fh.update(bhits); ft.update(btot)
        rows.append(row)
    nf = sum(r["found"] for r in rows)
    acc = sum(fh.values()) / sum(ft.values()) if ft else 0.0
    return {"rows": rows, "recall": nf / len(pkey) if pkey else 0.0, "n_found": nf, "n_key": len(pkey),
            "field_acc": acc, "field_detail": {f: (fh[f], ft[f]) for f in ft}}


def cell_report(cells, rules):
    cnt = Counter((r.get("jurisdiction"), r.get("category")) for r in rules)
    ev = {(c["jurisdiction"], c["category"]): c["evidence"] for c in cells}
    zero_but_evidenced = [k for k, e in ev.items() if e == "rule" and cnt[k] == 0]
    over = [k for k in ev if cnt[k] > 3]
    outside = [k for k in cnt if k not in ev]
    return {"counts": cnt, "evidence": ev, "zero_but_evidenced": zero_but_evidenced, "over3": over,
            "outside_grid": outside, "n_zero": sum(1 for k in ev if cnt[k] == 0)}


def citation_report(rules, lookups):
    kinds = Counter(); per = {}
    for r in rules:
        s = check_quote(r.get("source_doc_id"), r.get("quoted_span", "")) or "missing"
        kinds[s] += 1; per[r.get("team_rule_id")] = s != "missing" and bool(r.get("source_url"))
    ap = Counter()
    for lst in ((lookups or {}).get("lookups") or {}).values():
        for e in lst:
            if e.get("result") == "applies": ap[e.get("team_rule_id")] += 1
    tot = sum(ap.values())
    good = sum(n for rid, n in ap.items() if per.get(rid))
    return {"kinds": kinds, "n": len(rules), "share_rules": (kinds["single_line"] + kinds["ws_normalized"]) / len(rules) if rules else 0.0,
            "applies_total": tot, "applies_good": good, "share_applies": good / tot if tot else None,
            "bad_rules": [rid for rid, ok in per.items() if not ok]}


TOK = re.compile(r"\d+[A-Za-z]*(?:[.:\-]\d+[A-Za-z]*)*½?")


def invented_cites(rules):
    sus = []
    for r in rules:
        cit = str(r.get("citation", ""))
        hay = ((doc_text(r.get("source_doc_id")) or "") + "\n" + str(r.get("quoted_span", ""))).lower()
        toks = [t for t in TOK.findall(cit) if len(t) > 1]
        if not hay.strip():
            sus.append((r.get("team_rule_id"), cit, ["<no source text>"])); continue
        miss = [t for t in toks if t.lower() not in hay and t.replace("½", "").lower() not in hay]
        if miss: sus.append((r.get("team_rule_id"), cit, miss))
    return sus


def change_expected(rows, jur):
    st = {r["address_id"]: city_key(r, jur) for r in rows}
    ids = lambda f: sorted(a for a, (s, c) in st.items() if f(s, c))
    local = lambda c: c in ("Hoboken, NJ", "Jersey City, NJ")
    return {"T1": {"affected": ids(lambda s, c: s == "CA"), "conflict": []},
            "T2": {"affected": ids(lambda s, c: local(c)), "conflict": []},
            "T3": {"affected": ids(lambda s, c: s == "NJ"), "conflict": ids(lambda s, c: local(c))},
            "T4": {"affected": ids(lambda s, c: s == "MA"), "conflict": []},
            "T5": {"affected": [], "conflict": []}}


def prf(exp, got):
    e, g = set(exp), set(got); tp = len(e & g)
    p = tp / len(g) if g else (1.0 if not e else 0.0)
    r = tp / len(e) if e else (1.0 if not g else 0.0)
    j = tp / len(e | g) if (e | g) else 1.0
    return {"precision": p, "recall": r, "jaccard": j, "n_exp": len(e), "n_got": len(g)}


def change_report(rows, jur, changes):
    exp = change_expected(rows, jur); out = {}
    for t, e in exp.items():
        got = (changes or {}).get(t) or {}
        a = prf(e["affected"], got.get("affected_address_ids", []))
        c = prf(e["conflict"], got.get("conflict_flag_address_ids", [])) if t == "T3" else None
        out[t] = {"affected": a, "conflict": c, "present": t in (changes or {}),
                  "score": (0.5 * a["jaccard"] + 0.5 * c["jaccard"]) if c else a["jaccard"]}
    return out


def lookup_report(rows, jur, rules, lookups, pkey):
    L = (lookups or {}).get("lookups") or {}
    byid = {r.get("team_rule_id"): r for r in rules}
    rep = {"missing_addr": [a["address_id"] for a in rows if a["address_id"] not in L], "bad_enum": 0,
           "applies_bad_status": [], "unknown_rule_ids": set(), "failed_listed": 0}
    dist = defaultdict(Counter)
    km = {k["id"]: {r.get("team_rule_id") for r, _ in match_rules(k, rules)} for k in pkey}
    miss_by_key, addr_scores = Counter(), []
    for a in rows:
        aid = a["address_id"]; st, city = city_key(a, jur)
        lst = L.get(aid)
        ids = {e.get("team_rule_id") for e in lst or []}
        for e in lst or []:
            if e.get("result") not in RESULTS: rep["bad_enum"] += 1
            r = byid.get(e.get("team_rule_id"))
            if r is None: rep["unknown_rule_ids"].add(e.get("team_rule_id")); continue
            if r.get("status") == "failed": rep["failed_listed"] += 1
            if e.get("result") == "applies" and r.get("status") != "in_force":
                rep["applies_bad_status"].append((aid, r.get("team_rule_id"), r.get("status")))
            dist[city][e.get("result")] += 1
        hit = miss = 0
        for k in pkey:
            if k.get("status") == "failed" or k["jurisdiction"] not in (st, city): continue
            if km[k["id"]] & ids: hit += 1
            else: miss += 1; miss_by_key[k["id"]] += 1
        addr_scores.append(0.0 if lst is None else (hit / (hit + 2 * miss) if hit + miss else 1.0))
    rep.update(dist=dist, miss_by_key=miss_by_key,
               score=sum(addr_scores) / len(addr_scores) if addr_scores else 0.0)
    return rep


def schema_report(rules, lookups, changes, schema):
    out = {}
    errs = []
    for i, r in enumerate(rules):
        errs += [f"rule[{i}] {e}" for e in validate(r, schema)]
    ids = [r.get("team_rule_id") for r in rules]
    dup = [k for k, n in Counter(ids).items() if n > 1]
    out["rules"] = {"n": len(rules), "errors": errs, "dup_ids": dup}
    if lookups is not None:
        e = validate(lookups, LOOKUPS_SCHEMA)
        for aid, lst in (lookups.get("lookups") or {}).items():
            if not isinstance(lst, list): e.append(f"{aid}: not a list"); continue
            for i, x in enumerate(lst): e += [f"{aid}[{i}] {m}" for m in validate(x, LOOKUP_ENTRY)]
        out["lookups"] = {"errors": e}
    if changes is not None:
        e = []
        for t, v in changes.items(): e += [f"{t} {m}" for m in validate(v, CHANGE_ENTRY)]
        e += [f"missing test {t}" for t in ("T1", "T2", "T3", "T4", "T5") if t not in changes]
        out["changes"] = {"errors": e}
    return out


def estimate(rec, cit, chg, look):
    ext = 25 * (0.7 * rec["recall"] + 0.3 * rec["field_acc"]) if rec else None
    adr = 20 * look["score"] if look else None
    if cit is None: cz = None
    else: cz = 15 * (cit["share_applies"] if cit["share_applies"] is not None else cit["share_rules"])
    ch = 15 * sum(v["score"] for v in chg.values()) / len(chg) if chg else None
    parts = [ext, adr, cz, ch]
    return {"extraction": ext, "address": adr, "citations": cz, "change": ch,
            "total": sum(p for p in parts if p is not None), "have": [p is not None for p in parts]}


# ---------- run + print ----------
def run(a):
    P = lambda p: Path(p)
    rules_d, look, chg = load(a.rules), load(a.lookups), load(a.changes)
    rules = rules_list(rules_d)
    pkey = load(a.key)["rules"]; cells = load(a.cells)["cells"]
    schema = load(a.schema); rows = load_addresses(a.addresses)
    jur = load(a.jurisdictions)
    L = []; w = L.append; hard = 0
    w("PROXY SCORE REPORT (not the organizers' scorer; Not legal advice)")
    w(f"rules={a.rules} ({len(rules)})  lookups={a.lookups} ({'ok' if look else 'ABSENT'})  "
      f"changes={a.changes} ({'ok' if chg else 'ABSENT'})  geocode={'work/jurisdictions.json' if jur else 'CSV postal_city fallback'}")
    sch = rec = cell = cit = chr_ = lr = None
    if rules_d is not None:
        sch = schema_report(rules, look, chg, schema)
        w("\n(a) SCHEMA VALIDITY")
        for k, v in sch.items():
            e = v["errors"]; hard += len(e) + len(v.get("dup_ids", []))
            w(f"  {k}: {'OK' if not e and not v.get('dup_ids') else str(len(e)) + ' errors'}"
              + (f", duplicate ids {v['dup_ids']}" if v.get("dup_ids") else ""))
            for m in e[:8]: w(f"    - {m}")
        rec = recall_report(pkey, rules)
        w(f"\n(b) PROXY-KEY RECALL {rec['n_found']}/{rec['n_key']} = {rec['recall']:.2f}   field accuracy {rec['field_acc']:.2f} "
          f"{ {f: f'{h}/{t}' for f, (h, t) in rec['field_detail'].items()} }")
        for r in rec["rows"]:
            if not r["found"]: w(f"  MISS {r['id']}")
            else:
                bad = [f for f, h in r["hits"].items() if not h]
                if bad or r["via"] != "cite" or r["n_matches"] > 1:
                    w(f"  {r['id']}: rule {r['rule']} via {r['via']}, matches={r['n_matches']}" + (f", field misses {bad}" if bad else ""))
        cell = cell_report(cells, rules)
        w("\n(c) CELL COVERAGE (rules per cell; . = 0, *N = more than 3)")
        w("  " + "jurisdiction".ljust(18) + " ".join(c[:4].ljust(4) for c in CATS) + "   (rent just depo fee_ scre algo)")
        for j in J13:
            cs = []
            for c in CATS:
                n = cell["counts"][(j, c)]; cs.append(("*%d" % n if n > 3 else "." if n == 0 else str(n)).ljust(4))
            w("  " + j.ljust(18) + " ".join(cs))
        w(f"  cells with 0 rules: {cell['n_zero']}/78 (docs evidence a rule in {sum(e == 'rule' for e in cell['evidence'].values())} cells)")
        if cell["zero_but_evidenced"]: w(f"  ZERO but docs evidence a rule: {cell['zero_but_evidenced']}")
        if cell["over3"]: w(f"  >3 rules (padding?): {cell['over3']}")
        if cell["outside_grid"]: w(f"  rules outside the grid (bad jurisdiction/category): {cell['outside_grid']}")
        cit = citation_report(rules, look)
        w(f"\n(d) CITATIONS: quote found {cit['share_rules']:.2f} of rules  {dict(cit['kinds'])}")
        w("  applies answers backed by found quote + url: " +
          (f"{cit['applies_good']}/{cit['applies_total']} = {cit['share_applies']:.2f}" if cit["applies_total"] else "n/a (no applies)"))
        if cit["bad_rules"]: w(f"  rules with unverifiable quote: {cit['bad_rules'][:15]}")
        sus = invented_cites(rules)
        w(f"\n(e) INVENTED-CITATION DETECTOR: {len(sus)} suspicious")
        for rid, c, m in sus[:20]: w(f"  {rid} '{c}' tokens not in source: {m}")
    chr_ = change_report(rows, jur, chg) if chg is not None else None
    if chr_:
        w("\n(f) CHANGE TESTS (expected derived from geocoded stack)")
        for t, v in chr_.items():
            x = v["affected"]
            w(f"  {t}: expected {x['n_exp']} got {x['n_got']} precision {x['precision']:.2f} recall {x['recall']:.2f}"
              + (f" | conflict P {v['conflict']['precision']:.2f} R {v['conflict']['recall']:.2f}" if v["conflict"] else "")
              + ("" if v["present"] else "  (test absent)"))
    if look is not None and rules_d is not None:
        lr = lookup_report(rows, jur, rules, look, pkey)
        hard += len(lr["missing_addr"]) + lr["bad_enum"] + len(lr["applies_bad_status"]) + lr["failed_listed"]
        w(f"\n(g) LOOKUPS: addresses missing {len(lr['missing_addr'])}/{len(rows)}, bad enum {lr['bad_enum']}, "
          f"unknown rule ids {len(lr['unknown_rule_ids'])}, failed rules listed {lr['failed_listed']}, "
          f"applies on non-in_force rule {len(lr['applies_bad_status'])}")
        for x in lr["applies_bad_status"][:5]: w(f"    {x}")
        w(f"  proxy missing-rule counts by key: {dict(lr['miss_by_key'])}")
        w("  results by legal city:")
        for c, d in sorted(lr["dist"].items()): w(f"    {c.ljust(18)} {dict(d)}")
    est = estimate(rec, cit, chr_, lr)
    w("\nPROXY ESTIMATE (not a real score; missing parts count 0)")
    f = lambda v: "n/a" if v is None else f"{v:5.1f}"
    w(f"  extraction {f(est['extraction'])}/25 = 25*(0.7*recall + 0.3*field_acc) on proxy key only")
    w(f"  address    {f(est['address'])}/20 = 20*mean_addr(hit/(hit+2*miss)) vs proxy key; absent address = 0")
    w(f"  citations  {f(est['citations'])}/15 = 15*share of applies answers with found quote+url (rules share if none)")
    w(f"  change     {f(est['change'])}/15 = 15*mean(T1..T5 jaccard; T3 = half affected, half conflict)")
    w(f"  TOTAL      {est['total']:5.1f}/75  (PROXY ESTIMATE)")
    return "\n".join(L), hard


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    d = lambda p: str(ROOT / p)
    ap.add_argument("--rules", default=d("outputs/rules.json"))
    ap.add_argument("--lookups", default=d("outputs/lookups.json"))
    ap.add_argument("--changes", default=d("outputs/changes.json"))
    ap.add_argument("--key", default=str(HERE / "proxy_key.json"))
    ap.add_argument("--cells", default=str(HERE / "cells.json"))
    ap.add_argument("--schema", default=d("data/schema/rule_record.schema.json"))
    ap.add_argument("--addresses", default=d("data/sample_addresses.csv"))
    ap.add_argument("--jurisdictions", default=d("work/jurisdictions.json"))
    a = ap.parse_args(argv)
    text, hard = run(a)
    print(text)
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
