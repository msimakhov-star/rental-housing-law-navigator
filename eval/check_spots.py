#!/usr/bin/env python3
"""Run eval/spot_checks.json against outputs/lookups_detail.json (stdlib). Skips if the file is absent."""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import score_proxy as sp  # noqa: E402

OPS = {"eq": lambda a, b: a == b, "lt": lambda a, b: a < b, "lte": lambda a, b: a <= b,
       "gt": lambda a, b: a > b, "gte": lambda a, b: a >= b}


def selects(addr, sel):
    if addr.get("stack", {}).get("city") != sel["city"]: return False
    for fact in ("year_built", "units"):
        for op, v in (sel.get(fact) or {}).items():
            x = addr.get("facts", {}).get(fact)
            if op == "null":
                if (x is None) != v: return False
            elif x is None or not OPS[op](x, v): return False
    return True


def result_at(entry, date):
    tl = entry.get("timeline")
    if tl:
        cur = None
        for t in sorted(tl, key=lambda t: t["from"]):
            if t["from"] <= date: cur = t
        return cur["result"] if cur else None
    return entry.get("result")


def run(detail_path, spots_path, key_path, as_of=None):
    detail = json.loads(Path(detail_path).read_text(encoding="utf-8"))
    spots = json.loads(Path(spots_path).read_text(encoding="utf-8"))
    pkey = {k["id"]: k for k in json.loads(Path(key_path).read_text(encoding="utf-8"))["rules"]}
    date = as_of or spots.get("as_of", "2026-10-01")
    rules = detail.get("rules", {})
    rl = [dict(r, team_rule_id=rid) for rid, r in rules.items()]
    kids = {k: {r["team_rule_id"] for r, _ in sp.match_rules(e, rl)} for k, e in pkey.items()}
    addrs = detail.get("addresses", {})
    out, fails, passed = [], 0, 0

    def got(aid, key):
        res = {e["team_rule_id"]: e for e in addrs[aid].get("results", [])}
        hits = [res[r] for r in kids.get(key, ()) if r in res]
        return hits

    def check(aid, ex):
        hits = got(aid, ex["key"])
        if not hits:
            return ("absent" in ex["result_in"], "absent" + ("" if kids.get(ex["key"]) else " (rule not extracted)"))
        rs = {result_at(h, date) for h in hits}
        ok = bool(rs & set(ex["result_in"]))
        if ok and "conflict_flag" in ex:
            ok = any(h.get("conflict_flag") == ex["conflict_flag"] for h in hits)
        return ok, "/".join(sorted(map(str, rs))) + ("" if "conflict_flag" not in ex else f" flag={[h.get('conflict_flag') for h in hits]}")

    for c in spots["cases"]:
        m = sorted(a for a, v in addrs.items() if selects(v, c["select"]))
        if not m:
            out.append(f"{c['id']} SKIP no address matches {c['select']}"); continue
        for aid in m[:10]:
            for ex in c["expect"]:
                ok, g = check(aid, ex)
                passed += ok; fails += not ok
                if not ok: out.append(f"{c['id']} FAIL {aid} {ex['key']} expected {ex['result_in']} got {g}")
            for fb in c.get("forbid", []):
                for e in addrs[aid].get("results", []):
                    r = rules.get(e["team_rule_id"], {})
                    if r.get("category") == fb["category"] and result_at(e, date) == fb["result"] \
                            and not re.search(fb["except_cite_regex"], str(r.get("citation", "")), re.I):
                        fails += 1; out.append(f"{c['id']} FAIL {aid} forbidden {fb['category']}/{fb['result']}: {e['team_rule_id']} {r.get('citation')}")
                        break
                else: passed += 1
        out.append(f"{c['id']} checked {len(m[:10])} of {len(m)} matching addresses: {c['description']}")
    for lk in spots.get("scope_leaks", []):
        bad = [a for a, v in addrs.items() if v.get("stack", {}).get("city") != lk["home"] and got(a, lk["key"])
               and any(result_at(h, date) not in (None, "absent") for h in got(a, lk["key"]))]
        passed += not bad; fails += bool(bad)
        if bad: out.append(f"LEAK FAIL {lk['key']} appears outside {lk['home']}: {bad[:5]} (+{max(0, len(bad) - 5)})")
    out.append(f"SPOT CHECKS: {passed} passed, {fails} failed")
    return out, fails


def main(argv):
    d = Path(argv[1]) if len(argv) > 1 else ROOT / "outputs/lookups_detail.json"
    if not d.exists():
        print(f"SKIP: {d} not found"); return 0
    out, fails = run(d, HERE / "spot_checks.json", HERE / "proxy_key.json")
    print("\n".join(out)); return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
