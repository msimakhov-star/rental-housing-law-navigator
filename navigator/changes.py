"""Change-test runner (T1..T6). run_tests -> (changes.json dict, detail dict for lookups_detail 'tests')."""
from collections import Counter
from .test_map import resolve_all, MapError

LIVE = ("applies", "unknown", "not_yet_effective", "pending")


def _res(eng, aid, rid, d):
    e = eng.at(aid, d).get(rid)
    return e["result"] if e else None


def _states(eng, test):
    st = test.get("states")
    return sorted(a for a, v in eng.addrs.items() if not st or v["loc"]["state"] in st)


def _counts(eng, aids, rids, d):
    c = Counter()
    for a in aids:
        for r in rids:
            c[_res(eng, a, r, d) or "omitted"] += 1
    return dict(c)


def _by_city(eng, aids):
    c = Counter((eng.addrs[a]["loc"].get("legal_city") or "(no in-scope city)") for a in aids)
    return dict(sorted(c.items()))


def run_test(t, eng, new_rule_ids=None):
    rules, typ = eng.rules, t.get("type")
    keys = t.get("rule_ids") or []
    try:
        rids = resolve_all(keys, rules.values()) if keys else []
    except MapError:
        if typ in ("as_of", "boundary", "pending", "negative"):
            raise
        rids = []
    if not rids and new_rule_ids:
        rids = list(new_rule_ids)
    aids = _states(eng, t)
    d = t.get("as_of")
    conf, extra, unknown = [], {}, []
    if typ == "as_of":
        b, a = t["as_of_before"], t["as_of_after"]
        aff = [x for x in aids if any(_res(eng, x, r, b) != _res(eng, x, r, a) for r in rids)]
        if "conflict_with" in t:
            cw = set(resolve_all(t["conflict_with"], rules.values()))
            conf = [x for x in aids if any(cw & set(((eng.at(x, a).get(r) or {}).get("reason") or {}).get("conflicts", [])) for r in rids)]
        extra = {"as_of_before": b, "as_of_after": a,
                 "counts_before": _counts(eng, aids, rids, b), "counts_after": _counts(eng, aids, rids, a)}
        notes = (f"Mapped {keys} to {rids}. Affected = addresses in {t.get('states') or 'all states'} whose result for the rule differs "
                 f"between {b} ({extra['counts_before']}) and {a} ({extra['counts_after']}). ")
        if "conflict_with" in t:
            notes += (f"Conflict flags: {len(conf)} addresses where the rule at {a} sits alongside a local rule it may conflict with "
                      f"({t['conflict_with']}); flagged for human review, not resolved by the engine. ")
    elif typ == "boundary":
        d = d or "2026-10-01"
        aff = [x for x in aids if any(_res(eng, x, r, d) == "applies" for r in rids)]
        extra = {"as_of": d, "per_rule": {r: sorted(x for x in aids if _res(eng, x, r, d) == "applies") for r in rids}}
        notes = f"Mapped {keys} to {rids}. Affected = addresses where any mapped rule is 'applies' on {d}; a rule is reported only for addresses whose legal city matches its jurisdiction."
    elif typ == "pending":
        d = d or "2026-10-01"
        aff = [x for x in aids if any(_res(eng, x, r, d) == "pending" for r in rids)]
        extra = {"as_of": d, "counts": _counts(eng, aids, rids, d)}
        notes = (f"Mapped {keys} to {rids}. Affected = addresses with result 'pending' on {d} (bills, not in force). "
                 "Coverage of a pending bill that depends on missing facts is still reported as pending.")
    elif typ == "negative":
        d = d or "2026-10-01"
        aff = []
        sts = set(t.get("states") or [])
        bad = [(x, r) for x in aids for r, e in eng.at(x, d).items()
               if e["result"] == "applies" and rules[r]["category"] == "rent_increase_limits"
               and rules[r]["level"] == "city" and (not sts or rules[r]["jurisdiction"].split(", ")[-1] in sts)]
        assert not bad, f"{t['test_id']}: a city rent cap is reported as applies for {bad[:5]} (n={len(bad)}); expected none (state bar on local rent control)"
        extra = {"as_of": d, "mapped_rules": rids, "mapped_rule_status": {r: rules[r]["status"] for r in rids}}
        notes = (f"Mapped {keys} to {rids} (status {extra['mapped_rule_status']}); failed rules are never reported. Asserted that no address in "
                 f"{sorted(sts)} has 'applies' for a city-level rent_increase_limits rule on {d}, so no rent cap is reported for Boston or Cambridge. Affected set is empty.")
    else:  # new_rule (T6) and unknown types
        d = d or "2026-10-01"
        aff = [x for x in aids if any(_res(eng, x, r, d) in LIVE for r in rids)]
        unknown = [x for x in aff if all(_res(eng, x, r, d) in ("unknown", None) for r in rids)]
        eds = {r: rules[r].get("effective_date") for r in rids}
        extra = {"as_of": d, "new_rule_ids": rids, "unknown_address_ids": unknown, "counts": _counts(eng, aids, rids, d)}
        notes = (f"New rule(s) {rids}, effective dates {eds}. Affected = addresses where the rule is applies, unknown, not_yet_effective or pending on {d}; "
                 f"{len(unknown)} of them are 'unknown' (coverage depends on missing facts). A rule whose effective date is after {d} is reported as "
                 "not_yet_effective, never as applies; partial dates mean the first day of the period; no date means not_yet_effective until a date is known.")
    detail = {"title": t.get("title"), "type": typ, "rule_ids": keys, "team_rule_ids": rids,
              "affected_address_ids": aff, "conflict_flag_address_ids": conf, "notes": notes,
              "expected_behavior": t.get("expected_behavior"), "affected_by_city": _by_city(eng, aff), **extra}
    return {"affected_address_ids": aff, "conflict_flag_address_ids": conf, "notes": notes}, detail


def run_tests(tests, eng, new_rule_ids=None):
    """-> (changes, details, errors). errors: {test_id: message} for tests that could not run (mapping/assertion)."""
    ch, det, err = {}, {}, {}
    for t in tests:
        try:
            ch[t["test_id"]], det[t["test_id"]] = run_test(t, eng, (new_rule_ids or {}).get(t["test_id"]) if isinstance(new_rule_ids, dict) else new_rule_ids)
        except (MapError, AssertionError) as ex:
            err[t["test_id"]] = str(ex)
    return ch, det, err
