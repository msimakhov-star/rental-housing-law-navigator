"""Deterministic three-valued rule engine (Kleene logic). Stdlib only, no LLM calls.
Facts per address: units, units_min, year_built (None = unknown). Location: state, legal_city, geocode_status."""
from collections import defaultdict

T, F, U = "TRUE", "FALSE", "UNKNOWN"
EARLY = "0000-01-01"
CITY_NAMES = ["Los Angeles, CA", "San Francisco, CA", "San Diego, CA", "Berkeley, CA", "Santa Ana, CA",
              "Jersey City, NJ", "Hoboken, NJ", "Newark, NJ", "Boston, MA", "Cambridge, MA"]


def norm_date(s):
    """yyyy, yyyy-mm, yyyy-mm-dd -> yyyy-mm-dd (partial dates mean the first day). None stays None."""
    if s in (None, ""):
        return None
    p = str(s).split("-")
    return f"{p[0]}-{p[1] if len(p) > 1 else '01'}-{p[2] if len(p) > 2 else '01'}"


def k_and(vals):
    return F if F in vals else (U if U in vals else T)


def k_or(vals):
    return T if T in vals else (U if U in vals else F)


def k_not(v):
    return {T: F, F: T, U: U}[v]


TRUST_UNITS_MIN = False  # see _leaf


def _cmp(op, c):
    """c = sign of (fact - value)."""
    return T if {">=": c >= 0, ">": c > 0, "<=": c <= 0, "<": c < 0, "==": c == 0, "!=": c != 0}[op] else F


def _sign(a, b):
    return (a > b) - (a < b)


def _leaf(p, facts, asof):
    """-> (value, used_facts set, missing list)"""
    if "unavailable" in p:
        return U, set(), [p["unavailable"]]
    fact, op, v = p["fact"], p["op"], p["value"]
    if fact == "units":
        u, m = facts.get("units"), facts.get("units_min")
        if u is not None:
            return _cmp(op, _sign(u, v)), {"units"}, []
        # ponytail: class-derived lower bounds (NJ 4C, Boston A/ codes) are inference, not data; the guide says say
        # unknown rather than guess, and an exact-key scorer would too. Flip TRUST_UNITS_MIN to use them.
        if m is None or not TRUST_UNITS_MIN:
            return U, set(), ["units"]
        # only a lower bound m is known: true count >= m
        val = {">=": T if m >= v else U, ">": T if m > v else U,
               "<=": F if m > v else U, "<": F if m >= v else U,
               "==": F if m > v else U, "!=": T if m > v else U}[op]
        return val, {"units"}, ([] if val != U else ["units"])
    if fact == "year_built":
        y = facts.get("year_built")
        if y is None:
            return U, set(), ["year_built"]
        return _cmp(op, _sign(y, v)), {"year_built"}, []
    if fact in ("building_age_years", "co_date"):
        y = facts.get("year_built")
        if y is None:
            return U, set(), ["year_built"]
        if fact == "co_date":
            a, b = y, int(str(v)[:4])
        else:
            a, b = int(asof[:4]) - y, v
        if a == b:  # boundary year: exact date unknown
            return U, {"year_built"}, [fact]
        return _cmp(op, _sign(a, b)), {"year_built"}, []
    return U, set(), [fact]


def eval_pred(p, facts, asof):
    """-> (TRUE|FALSE|UNKNOWN, facts_used set, missing_facts list). None = TRUE."""
    if p is None:
        return T, set(), []
    if "all" in p or "any" in p:
        kind = "all" if "all" in p else "any"
        rs = [eval_pred(c, facts, asof) for c in p[kind]]
        val = (k_and if kind == "all" else k_or)([r[0] for r in rs])
    elif "not" in p:
        r = eval_pred(p["not"], facts, asof)
        rs, val = [r], k_not(r[0])
    else:
        return _leaf(p, facts, asof)
    used = set().union(*[r[1] for r in rs])
    miss = []
    if val == U:
        for r in rs:
            miss += [m for m in r[2] if m not in miss]
    return val, used, miss


def _scope(rule, loc):
    """'in' | 'out' | 'unknown'"""
    j = rule["jurisdiction"]
    if rule.get("level") == "state" or j in ("CA", "NJ", "MA"):
        return "in" if j == loc["state"] else "out"
    if not j.endswith(", " + loc["state"]):
        return "out"
    if loc.get("legal_city"):
        return "in" if loc["legal_city"] == j else "out"
    # legal city null: unknown only when the geocode failed (else confirmed outside every in-scope city)
    if loc.get("geocode_status") == "failed":
        pc = (loc.get("postal_city") or "").strip().title()
        cand = f"{pc}, {loc['state']}"
        return "unknown" if (cand == j or cand not in CITY_NAMES) else "out"
    return "out"


def _temporal(rule, d):
    st, e = rule.get("status"), norm_date(rule.get("effective_date"))
    if st == "pending":
        return "pending"
    if st == "in_force":
        # date_kind 'version': E is an amendment/rate-year date of a rule that already existed, so earlier dates are not 'not yet effective'
        return "not_yet_effective" if (e and d < e and rule.get("date_kind") != "version") else "active"
    if st == "not_yet_effective":
        return "active" if (e and d >= e) else "not_yet_effective"
    return None  # failed or unknown status


def _matches(rule, descs):
    return any(rule["jurisdiction"] == x["jurisdiction"] and rule["category"] == x["category"] for x in descs or [])


def _raw(rule, facts, loc, d):
    if rule.get("status") == "failed":
        return None
    sc = _scope(rule, loc)
    temporal = _temporal(rule, d)
    if sc == "out" or temporal is None:
        return None
    a, ua, ma = eval_pred(rule.get("applies_if"), facts, d)
    x, ux, mx = eval_pred(rule["exempt_if"], facts, d) if rule.get("exempt_if") else (F, set(), [])
    cov = k_and([a, k_not(x)] + ([U] if sc == "unknown" else []))  # unknown scope: facts can still rule a rule out
    used = ua | ux
    miss = (["legal_city"] if sc == "unknown" else []) + (ma + mx if cov == U else [])
    miss = list(dict.fromkeys(miss))
    if cov == F:
        return None
    if temporal == "active":
        res = "applies" if cov == T else "unknown"
        kind = "applies" if cov == T else ("unknown_city" if sc == "unknown" else "unknown_facts")
    else:
        res, kind = temporal, temporal
    conf = float(rule.get("confidence") if rule.get("confidence") is not None else 0.5)
    if cov == U:
        conf *= 0.7
    if rule["jurisdiction"] not in ("CA", "NJ", "MA"):
        g = loc.get("geocode_status")
        conf *= 0.6 if g in ("fallback_postal", "failed") else (0.9 if g == "non_exact" else 1.0)
    return {"team_rule_id": rule["team_rule_id"], "category": rule["category"], "result": res,
            "reason": {"kind": kind, "coverage": cov, "effective_date": norm_date(rule.get("effective_date")),
                       "earlier_version": bool(rule.get("status") == "in_force" and rule.get("date_kind") == "version"
                                               and rule.get("effective_date") and d < norm_date(rule.get("effective_date"))),
                       "geocode_status": loc.get("geocode_status")},
            "facts_used": sorted(used), "missing_facts": miss, "conflict_flag": False, "conflict_note": None,
            "confidence": round(min(conf, 1.0), 2)}


def evaluate_address(rules, facts, loc, d):
    """rules: {team_rule_id: rule}. Returns {team_rule_id: entry} for non-omitted rules at date d (yyyy-mm-dd)."""
    out = {rid: e for rid, r in rules.items() if (e := _raw(r, facts, loc, d))}
    raw = {rid: e["result"] for rid, e in out.items()}
    rawmiss = {rid: e["missing_facts"] for rid, e in out.items()}
    for rid, e in out.items():  # precedence, decided on raw results only (order independent)
        r = rules[rid]
        if raw[rid] not in ("applies", "unknown") or not r.get("yields_to"):
            continue
        cands = [o for o in out if o != rid and _matches(rules[o], r["yields_to"])]
        hit = [o for o in cands if raw[o] == "applies"]
        unk = [o for o in cands if raw[o] == "unknown"]
        if hit:
            e["result"], e["reason"]["kind"], e["reason"]["others"] = "superseded", "superseded", sorted(hit)
        elif unk and raw[rid] == "applies":
            e["result"], e["reason"]["kind"], e["reason"]["others"] = "unknown", "unknown_precedence", sorted(unk)
            e["reason"]["others_missing"] = list(dict.fromkeys(m for o in unk for m in rawmiss[o]))
            e["confidence"] = round(e["confidence"] * 0.7, 2)
    live = {"applies", "unknown", "not_yet_effective", "pending"}
    pairs = defaultdict(set)
    for rid, e in out.items():
        for o in out:
            if o != rid and raw[o] in live and raw[rid] in live and (
                    _matches(rules[o], rules[rid].get("conflicts_with")) or _matches(rules[rid], rules[o].get("conflicts_with"))):
                pairs[rid].add(o); pairs[o].add(rid)
    for rid, e in out.items():
        r, notes = rules[rid], []
        if r.get("conflict_flag"):
            e["conflict_flag"] = True
            notes.append(r.get("conflict_note") or "Source discrepancy recorded for this rule; needs human review.")
        if pairs.get(rid):
            e["conflict_flag"] = True
            e["reason"]["conflicts"] = sorted(pairs[rid])
            notes.append("Possible conflict or preemption between " + " and ".join(
                f"{rules[x]['title']} ({rules[x]['citation']})" for x in sorted(pairs[rid] | {rid}, key=lambda z: (z != rid, z)))
                + "; flagged for human review.")
        e["conflict_note"] = " ".join(notes) or None
    return out


def distinct_dates(rules):
    ds = {EARLY}
    ds |= {norm_date(r.get("effective_date")) for r in rules.values() if r.get("effective_date")}
    # building_age_years depends on the as-of YEAR only, so a Jan 1 point per year captures every age-based flip
    ds |= {f"{y}-01-01" for y in range(1990, 2036)}
    return sorted(ds)


class Engine:
    """Holds rules + per-address facts/loc; memoises evaluation per (address, date)."""

    def __init__(self, rules, addrs, trust_units_min=None):
        """rules: list or dict of rule dicts. addrs: {aid: {"facts":{...}, "loc":{...}}}"""
        self.rules = rules if isinstance(rules, dict) else {r["team_rule_id"]: r for r in rules}
        self.addrs, self._c, self.trust = addrs, {}, trust_units_min
        self.dates = distinct_dates(self.rules)

    def at(self, aid, d):
        k = (aid, d)
        if k not in self._c:
            global TRUST_UNITS_MIN
            a, saved = self.addrs[aid], TRUST_UNITS_MIN
            if self.trust is not None:
                TRUST_UNITS_MIN = self.trust
            try:
                self._c[k] = evaluate_address(self.rules, a["facts"], a["loc"], d)
            finally:
                TRUST_UNITS_MIN = saved
        return self._c[k]

    def timeline_alt(self, aid, alt):
        """Like timeline(), also tracking the result under the alternative engine `alt` (class unit bounds trusted).
        {rid: [(from_date, entry_or_None, alt_result_or_None)]}"""
        tl = defaultdict(list)
        prev = {}
        for d in self.dates:
            cur, acur = self.at(aid, d), alt.at(aid, d)
            for rid in set(cur) | set(prev):
                e = cur.get(rid)
                a = (acur.get(rid) or {}).get("result")
                sig = ((e["result"], e["conflict_flag"], e["reason"].get("earlier_version")) if e else None, a)
                last = tl[rid][-1][3] if tl[rid] else "none"
                if sig != last and not (not tl[rid] and e is None):
                    tl[rid].append((d, e, a, sig))
            prev = cur
        return {rid: [(d, e, a) for d, e, a, _ in v] for rid, v in tl.items()}

    def timeline(self, aid):
        """{rid: [(from_date, entry_or_None)]} change points, compressed on (result, conflict_flag)."""
        tl = defaultdict(list)
        prev = {}
        for d in self.dates:
            cur = self.at(aid, d)
            for rid in set(cur) | set(prev):
                e = cur.get(rid)
                sig = (e["result"], e["conflict_flag"], e["reason"].get("earlier_version")) if e else None
                last = tl[rid][-1][2] if tl[rid] else "none"
                if sig != last and not (not tl[rid] and e is None):
                    tl[rid].append((d, e, sig))
            prev = cur
        return {rid: [(d, e) for d, e, _ in v] for rid, v in tl.items()}
