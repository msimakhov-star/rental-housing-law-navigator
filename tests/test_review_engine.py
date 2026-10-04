"""Reviewer R3 adversarial engine tests. Run: python3 -m unittest tests.test_review_engine
Tests named test_BUG_* expose real defects (see docs/review_engine.md); they are meant to fail until fixed."""
import contextlib, io, itertools, json, re, shutil, unittest
from pathlib import Path
from navigator import apply as A
from navigator.apply import T, F, U, eval_pred, evaluate_address, k_and, k_or, k_not, norm_date, Engine
from navigator.explain import explain
from navigator.changes import run_test
from navigator.test_map import TABLE, resolve
from navigator.common import ROOT, AS_OF, RESULTS, CITIES, load_json
from navigator.merge_rules import merge, PUBLIC

OUT = ROOT / "outputs"
NOW = "2026-10-01"
DASH = re.compile("[" + chr(0x2013) + chr(0x2014) + "]")


def rule(rid, j, cat="rent_increase_limits", status="in_force", eff=None, ai=None, ex=None, y=(), cw=(), flag=False, note=None):
    return {"team_rule_id": rid, "jurisdiction": j, "level": "state" if j in ("CA", "NJ", "MA") else "city", "category": cat,
            "status": status, "effective_date": eff, "applies_if": ai, "exempt_if": ex,
            "yields_to": [{"jurisdiction": a, "category": b} for a, b in y], "conflicts_with": [{"jurisdiction": a, "category": b} for a, b in cw],
            "conflict_flag": flag, "conflict_note": note, "title": f"Title {rid}", "citation": f"Cite {rid}", "requirement": "Req.",
            "key_value": None, "confidence": 0.9}


def loc(city, state, g="exact", postal=None):
    return {"state": state, "legal_city": city, "geocode_status": g, "postal_city": postal}


def facts(units=None, year=None, umin=None):
    return {"units": units, "year_built": year, "units_min": umin}


def ev(rules, f, l, d=NOW):
    return evaluate_address({r["team_rule_id"]: r for r in rules}, f, l, d)


def res(rules, f, l, d=NOW):
    return {k: e["result"] for k, e in ev(rules, f, l, d).items()}


LEAF = {T: {"fact": "units", "op": ">=", "value": 1}, F: {"fact": "units", "op": ">=", "value": 99}, U: {"unavailable": "x"}}
F10 = facts(units=10)


class Kleene(unittest.TestCase):
    def test_truth_tables(self):
        for a, b in itertools.product((T, F, U), repeat=2):
            self.assertEqual(k_and([a, b]), F if F in (a, b) else (U if U in (a, b) else T))
            self.assertEqual(k_or([a, b]), T if T in (a, b) else (U if U in (a, b) else F))
        self.assertEqual([k_not(x) for x in (T, F, U)], [F, T, U])

    def test_order_independent_all_any_not(self):
        for vals in itertools.product((T, F, U), repeat=3):
            for kind in ("all", "any"):
                outs = {eval_pred({kind: [LEAF[v] for v in p]}, F10, NOW)[0] for p in itertools.permutations(vals)}
                self.assertEqual(len(outs), 1, (kind, vals))
                n = {eval_pred({"not": {kind: [LEAF[v] for v in p]}}, F10, NOW)[0] for p in itertools.permutations(vals)}
                self.assertEqual(n, {k_not(outs.pop())})

    def test_empty_and_null(self):
        self.assertEqual(eval_pred({"all": []}, F10, NOW)[0], T)
        self.assertEqual(eval_pred({"any": []}, F10, NOW)[0], F)
        self.assertEqual(eval_pred(None, F10, NOW)[0], T)

    def test_missing_only_when_unknown(self):
        self.assertEqual(eval_pred({"all": [LEAF[F], LEAF[U]]}, F10, NOW)[2], [])
        self.assertEqual(eval_pred({"any": [LEAF[T], LEAF[U]]}, F10, NOW)[2], [])
        self.assertEqual(eval_pred({"not": {"all": [LEAF[T], LEAF[U]]}}, F10, NOW)[2], ["x"])


class Boundaries(unittest.TestCase):
    def test_co_date_year_proxy(self):
        p = {"fact": "co_date", "op": "<=", "value": "1978-10-01"}
        self.assertEqual(eval_pred(p, facts(year=1977), NOW)[0], T)
        self.assertEqual(eval_pred(p, facts(year=1978), NOW)[:3:2], (U, ["co_date"]))
        self.assertEqual(eval_pred(p, facts(year=1979), NOW)[0], F)
        self.assertEqual(eval_pred({"fact": "co_date", "op": ">", "value": "1978"}, facts(year=1979), NOW)[0], T)
        self.assertEqual(eval_pred(p, facts(), NOW)[0], U)

    def test_year_built_is_exact(self):  # year_built is the fact itself: equal year is decidable
        self.assertEqual(eval_pred({"fact": "year_built", "op": "<", "value": 1980}, facts(year=1980), NOW)[0], F)

    def test_age_uses_asof_year_and_equal_is_unknown(self):
        p = {"fact": "building_age_years", "op": "<", "value": 15}
        self.assertEqual(eval_pred(p, facts(year=2011), "2026-10-01")[:3:2], (U, ["building_age_years"]))
        self.assertEqual(eval_pred(p, facts(year=2011), "2026-01-01")[0], U)
        self.assertEqual(eval_pred(p, facts(year=2011), "2027-01-01")[0], F)
        self.assertEqual(eval_pred(p, facts(year=2012), "2026-12-31")[0], T)
        # as-of year, not the rule's effective date
        r = rule("r1", "CA", eff="2020-01-01", ex=p)
        self.assertEqual(res([r], facts(year=2008), loc(None, "CA")), {"r1": "applies"})

    def test_negative_age(self):  # building not yet built at the as-of year: numeric compare, no abs()
        self.assertEqual(eval_pred({"fact": "building_age_years", "op": "<", "value": 15}, facts(year=2030), NOW)[0], T)
        self.assertEqual(eval_pred({"fact": "building_age_years", "op": ">=", "value": 0}, facts(year=2030), NOW)[0], F)

    def test_partial_and_leap_dates(self):
        self.assertEqual(norm_date("2025"), "2025-01-01")
        self.assertEqual(norm_date("2025-06"), "2025-06-01")
        self.assertIsNone(norm_date(None))
        for eff, before, on in (("2025-06", "2025-05-31", "2025-06-01"), ("2025", "2024-12-31", "2025-01-01"),
                                ("2024-02-29", "2024-02-28", "2024-02-29")):
            r = rule("r1", "CA", eff=eff)
            self.assertEqual(res([r], F10, loc(None, "CA"), before), {"r1": "not_yet_effective"})
            self.assertEqual(res([r], F10, loc(None, "CA"), on), {"r1": "applies"})

    def test_units_min_ignored_when_untrusted(self):
        self.assertFalse(A.TRUST_UNITS_MIN)
        f = facts(umin=50, year=1950)
        r = rule("r1", "CA", ai={"fact": "units", "op": ">=", "value": 5})
        e = ev([r], f, loc(None, "CA"))["r1"]
        self.assertEqual((e["result"], e["facts_used"], e["missing_facts"]), ("unknown", [], ["units"]))
        r2 = rule("r2", "CA", ai={"all": [{"fact": "year_built", "op": "<", "value": 1980}, {"fact": "units", "op": "<", "value": 5}]})
        self.assertEqual(res([r2], f, loc(None, "CA")), {"r2": "unknown"})  # a lower bound of 50 must not make it FALSE
        r3 = rule("r3", "CA", ai={"fact": "year_built", "op": "<", "value": 1980})
        e3 = ev([r3], f, loc(None, "CA"))["r3"]
        en = explain(e3, r3, {"r3": r3}, f, NOW)[0]
        self.assertNotIn("at least 50", en)
        self.assertIn("built in 1950", en)

    def test_BUG_units_min_text_false_when_trusted(self):  # explain.py:103 says "we do not rely on it" even when we did
        A.TRUST_UNITS_MIN = True
        self.addCleanup(setattr, A, "TRUST_UNITS_MIN", False)
        f = facts(umin=5)
        r = rule("r1", "CA", ai={"fact": "units", "op": ">=", "value": 9})
        e = ev([r], f, loc(None, "CA"))["r1"]
        self.assertEqual(e["result"], "unknown")
        self.assertNotIn("do not rely on it", explain(e, r, {"r1": r}, f, NOW)[0])

    def test_BUG_co_date_text_when_year_missing(self):  # explain.py MISS_EN['co_date'] claims we have the year built
        r = rule("r1", "Los Angeles, CA", ai={"fact": "co_date", "op": "<=", "value": "1978-10-01"})
        e = ev([r], facts(units=10), loc("Los Angeles, CA", "CA"))["r1"]
        self.assertEqual(e["result"], "unknown")
        self.assertNotIn("we only have the year built", explain(e, r, {"r1": r}, facts(units=10), NOW)[0])


class Dates(unittest.TestCase):
    L = loc(None, "CA")

    def test_status_matrix(self):
        cases = [("in_force", "2027-01-01", NOW, "not_yet_effective"), ("in_force", "2027-01-01", "2027-01-01", "applies"),
                 ("in_force", None, "0000-01-01", "applies"), ("not_yet_effective", "2026-01-01", NOW, "applies"),
                 ("not_yet_effective", "2027-07-01", NOW, "not_yet_effective"), ("not_yet_effective", None, "2100-01-01", "not_yet_effective"),
                 ("pending", None, NOW, "pending"), ("pending", "2020-01-01", "2030-01-01", "pending")]
        for st, eff, d, want in cases:
            self.assertEqual(res([rule("r1", "CA", status=st, eff=eff)], F10, self.L, d), {"r1": want}, (st, eff, d))
        self.assertEqual(res([rule("r1", "CA", status="failed")], F10, self.L), {})
        self.assertEqual(res([rule("r1", "CA", status="bogus")], F10, self.L), {})

    def test_nonactive_with_false_coverage_is_omitted(self):
        r = rule("r1", "CA", status="pending", ai={"fact": "units", "op": ">=", "value": 50})
        self.assertEqual(res([r], F10, self.L), {})


class Precedence(unittest.TestCase):
    LA = loc("Los Angeles, CA", "CA")
    LOCAL = ("Los Angeles, CA", "rent_increase_limits")

    def st(self, **k):
        return rule("s", "CA", y=[self.LOCAL], **k)

    def test_target_applies_supersedes(self):
        self.assertEqual(res([self.st(), rule("c", "Los Angeles, CA")], F10, self.LA), {"s": "superseded", "c": "applies"})

    def test_target_unknown_makes_unknown(self):
        c = rule("c", "Los Angeles, CA", ai={"unavailable": "rent level"})
        e = ev([self.st(), c], F10, self.LA)["s"]
        self.assertEqual((e["result"], e["reason"]["kind"], e["reason"]["others_missing"]), ("unknown", "unknown_precedence", ["rent level"]))

    def test_target_other_city_or_not_yet_effective(self):
        self.assertEqual(res([self.st(), rule("c", "Los Angeles, CA")], F10, loc("San Diego, CA", "CA"))["s"], "applies")
        self.assertEqual(res([self.st(), rule("c", "Los Angeles, CA", eff="2030-01-01")], F10, self.LA)["s"], "applies")
        self.assertEqual(res([self.st(), rule("c", "Los Angeles, CA", status="pending")], F10, self.LA)["s"], "applies")

    def test_BUG_target_with_status_nye_whose_date_has_passed(self):  # apply.py:177 filters status == in_force
        c = rule("c", "Los Angeles, CA", status="not_yet_effective", eff="2026-01-01")
        self.assertEqual(res([self.st(), c], F10, self.LA), {"s": "superseded", "c": "applies"})

    def test_BUG_unknown_yielder_with_applying_target(self):  # apply.py:175 skips raw unknown; real data: r-0002 vs r-0022/r-0026
        s = self.st(ex={"unavailable": "single-family home"})
        self.assertEqual(res([s, rule("c", "Los Angeles, CA")], F10, self.LA)["s"], "superseded")

    def test_chain_and_order_independence(self):
        rs = [rule("a", "CA", y=[self.LOCAL]), rule("b", "Los Angeles, CA", y=[("Los Angeles, CA", "just_cause_eviction")]),
              rule("c", "Los Angeles, CA", cat="just_cause_eviction"),
              rule("d", "CA", cat="just_cause_eviction", cw=[self.LOCAL]), rule("e", "Los Angeles, CA", ai={"unavailable": "z"}, y=[("CA", "security_deposits")])]
        base = {k: (v["result"], v["conflict_flag"]) for k, v in ev(rs, F10, self.LA).items()}
        self.assertEqual(base["a"][0], "superseded")
        for p in itertools.permutations(rs):
            self.assertEqual({k: (v["result"], v["conflict_flag"]) for k, v in ev(list(p), F10, self.LA).items()}, base)


class Conflicts(unittest.TestCase):
    def test_mutual_only_when_both_present(self):
        s = rule("s", "NJ", cat="algorithmic_rent_setting", status="not_yet_effective", eff="2027-07-01",
                 cw=[("Jersey City, NJ", "algorithmic_rent_setting")])
        c = rule("c", "Jersey City, NJ", cat="algorithmic_rent_setting")
        e = ev([s, c], F10, loc("Jersey City, NJ", "NJ"))
        self.assertTrue(e["s"]["conflict_flag"] and e["c"]["conflict_flag"])  # c is flagged although only s declares it
        self.assertEqual(e["c"]["reason"]["conflicts"], ["s"])
        e2 = ev([s, c], F10, loc("Newark, NJ", "NJ"))
        self.assertEqual(list(e2), ["s"])
        self.assertFalse(e2["s"]["conflict_flag"])

    def test_rule_level_flag_propagates(self):
        for st in ("in_force", "pending", "not_yet_effective"):
            r = rule("r", "CA", status=st, eff="2030-01-01" if st != "pending" else None, flag=True, note="two sources disagree")
            e = ev([r], F10, loc(None, "CA"))["r"]
            self.assertTrue(e["conflict_flag"])
            self.assertIn("two sources disagree", explain(e, r, {"r": r}, F10, NOW)[0])

    def _t3(self, flag):
        rs = [rule("fair", "NJ", cat="algorithmic_rent_setting", status="not_yet_effective", eff="2027-07-01", flag=flag,
                   cw=[("Jersey City, NJ", "algorithmic_rent_setting"), ("Hoboken, NJ", "algorithmic_rent_setting")]),
              rule("jc", "Jersey City, NJ", cat="algorithmic_rent_setting"), rule("hob", "Hoboken, NJ", cat="algorithmic_rent_setting")]
        addrs = {"J": {"facts": F10, "loc": loc("Jersey City, NJ", "NJ")}, "H": {"facts": F10, "loc": loc("Hoboken, NJ", "NJ")},
                 "N": {"facts": F10, "loc": loc("Newark, NJ", "NJ")}, "C": {"facts": F10, "loc": loc("Los Angeles, CA", "CA")}}
        t = {"test_id": "T3", "type": "as_of", "rule_ids": ["fair"], "as_of_before": NOW, "as_of_after": "2027-07-02",
             "states": ["NJ"], "conflict_with": ["jc", "hob"]}
        return run_test(t, Engine(rs, addrs))[0]

    def test_t3_synthetic(self):
        ch = self._t3(False)
        self.assertEqual(ch["affected_address_ids"], ["H", "J", "N"])
        self.assertEqual(ch["conflict_flag_address_ids"], ["H", "J"])

    def test_BUG_t3_rule_level_flag_floods_conflict_ids(self):  # changes.py:49 uses any conflict_flag, ignores conflict_with
        self.assertEqual(self._t3(True)["conflict_flag_address_ids"], ["H", "J"])

    def test_BUG_failed_geocode_ignores_facts(self):  # apply.py:140 skips applies_if when scope is unknown
        r = rule("c", "Los Angeles, CA", ai={"fact": "co_date", "op": "<=", "value": "1978-10-01"})
        self.assertEqual(res([r], facts(units=10, year=2010), loc(None, "CA", "failed", "Los Angeles")), {})


class Timeline(unittest.TestCase):
    def test_points_and_compression(self):
        rs = [rule("tpa", "CA", eff="2020-01-01", ex={"fact": "building_age_years", "op": "<", "value": 15}),
              rule("n", "CA", cat="security_deposits", status="not_yet_effective"),
              rule("p", "CA", cat="algorithmic_rent_setting", eff="2026-01-01")]
        eng = Engine(rs, {"A": {"facts": facts(year=2011, units=10), "loc": loc(None, "CA")}})
        tl = eng.timeline("A")
        self.assertEqual([(d, e["result"]) for d, e in tl["tpa"]], [("2026-01-01", "unknown"), ("2027-01-01", "applies")])
        self.assertEqual([(d, e["result"]) for d, e in tl["n"]], [("0000-01-01", "not_yet_effective")])
        self.assertEqual([(d, e["result"]) for d, e in tl["p"]], [("0000-01-01", "not_yet_effective"), ("2026-01-01", "applies")])
        for pts in tl.values():
            sig = [(e["result"], e["conflict_flag"]) if e else None for _, e in pts]
            self.assertTrue(all(a != b for a, b in zip(sig, sig[1:])))
            self.assertIsNotNone(pts[0][1])

    def test_drop_out_emits_none(self):  # coverage ends when the building turns 30
        r = rule("r", "NJ", ai={"fact": "building_age_years", "op": "<", "value": 30})
        tl = Engine([r], {"A": {"facts": facts(year=2000), "loc": loc(None, "NJ")}}).timeline("A")["r"]
        self.assertEqual([(d, e and e["result"]) for d, e in tl], [("0000-01-01", "applies"), ("2030-01-01", "unknown"), ("2031-01-01", None)])


class RealOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from navigator.pipeline import cfg, load_world
        cls.lk = load_json(OUT / "lookups.json")
        cls.det = load_json(OUT / "lookups_detail.json")
        cls.ch = load_json(OUT / "changes.json")
        cls.pub = load_json(OUT / "rules.json")
        cls.eng_rules = load_json(OUT / "rules_engine.json")["rules"]
        rules, addrs, _ = load_world(cfg())
        cls.addrs = addrs
        cls.eng = Engine(rules, {a: {"facts": v["facts"], "loc": v["loc"]} for a, v in addrs.items()})
        cls.city = {a: v["loc"].get("legal_city") for a, v in addrs.items()}

    def _valid_at(self, tl, d):
        return [t for t in tl if t["from"] <= d][-1:]

    def test_lookups_equal_timeline_at_asof(self):
        self.assertEqual(self.lk["as_of"], AS_OF)
        self.assertEqual(len(self.lk["lookups"]), 500)
        for a, es in self.lk["lookups"].items():
            tl = {r["team_rule_id"]: r["timeline"] for r in self.det["addresses"][a]["results"]}
            got = {e["team_rule_id"]: e["result"] for e in es}
            want = {rid: v[0]["result"] for rid, v in ((rid, self._valid_at(t, AS_OF)) for rid, t in tl.items())
                    if v and v[0]["result"] != "not_covered"}
            self.assertEqual(got, want, a)

    def test_BUG_timeline_entry_valid_at_asof_is_not_placeholder(self):  # pipeline.py:114 (i < len(pts)-1 is the wrong test)
        bad = [(a, r["team_rule_id"]) for a, v in self.det["addresses"].items() for r in v["results"]
               if (x := self._valid_at(r["timeline"], AS_OF)) and x[0]["explanation"].startswith("Before the earliest")]
        self.assertEqual(bad[:3], [], f"{len(bad)} entries")

    def test_pre2000_entries_have_placeholder(self):
        for v in self.det["addresses"].values():
            for r in v["results"]:
                tl = r["timeline"]
                for t, nxt in zip(tl, tl[1:]):
                    if nxt["from"] <= "2000-01-01":
                        self.assertTrue(t["explanation"].startswith("Before the earliest"))

    def test_lookups_fresh(self):  # outputs match the current engine at the as-of date
        for a, es in self.lk["lookups"].items():
            cur = self.eng.at(a, AS_OF)
            self.assertEqual({e["team_rule_id"]: (e["result"], e["conflict_flag"]) for e in es},
                             {k: (e["result"], e["conflict_flag"]) for k, e in cur.items()}, a)

    def test_lookups_shape_and_text(self):
        ids = {r["team_rule_id"] for r in self.pub["rules"]}
        self.assertEqual(set(self.lk), {"as_of", "lookups"})
        for a, es in self.lk["lookups"].items():
            self.assertEqual(len({e["team_rule_id"] for e in es}), len(es))
            for e in es:
                self.assertEqual(set(e), {"team_rule_id", "result", "explanation", "conflict_flag"})
                self.assertIn(e["result"], RESULTS)
                self.assertIn(e["team_rule_id"], ids)
                self.assertIsInstance(e["conflict_flag"], bool)
                self.assertTrue(e["explanation"].endswith("Not legal advice."))
                self.assertNotRegex(e["explanation"], DASH)
                self.assertNotIn("{ASOF}", e["explanation"])

    def test_changes_shape_and_expected_sets(self):
        self.assertEqual(sorted(self.ch), ["T1", "T2", "T3", "T4", "T5"])
        st = {a: v["row"]["state"] for a, v in self.addrs.items()}
        for k, v in self.ch.items():
            self.assertEqual(set(v), {"affected_address_ids", "conflict_flag_address_ids", "notes"})
            for f in ("affected_address_ids", "conflict_flag_address_ids"):
                self.assertEqual(v[f], sorted(set(v[f])))
                self.assertTrue(set(v[f]) <= set(self.addrs))
            self.assertNotRegex(v["notes"], DASH)
        self.assertEqual(set(self.ch["T1"]["affected_address_ids"]), {a for a, s in st.items() if s == "CA"})
        hj = {a for a, c in self.city.items() if c in ("Jersey City, NJ", "Hoboken, NJ")}
        self.assertEqual(set(self.ch["T2"]["affected_address_ids"]), hj)
        self.assertEqual(set(self.ch["T3"]["affected_address_ids"]), {a for a, s in st.items() if s == "NJ"})
        self.assertEqual(set(self.ch["T3"]["conflict_flag_address_ids"]), hj)
        self.assertEqual(set(self.ch["T4"]["affected_address_ids"]), {a for a, s in st.items() if s == "MA"})
        self.assertEqual(self.ch["T5"]["affected_address_ids"], [])

    def test_test_map_unique(self):
        want = {"CA-ALG-01": ("CA", "in_force"), "HOB-ALG-01": ("Hoboken, NJ", "in_force"), "JC-ALG-01": ("Jersey City, NJ", "in_force"),
                "NJ-ALG-01": ("NJ", "not_yet_effective"), "MA-ALG-P1": ("MA", "pending"), "MA-ALG-P2": ("MA", "pending"),
                "MA-RENT-P1": ("MA", "failed")}
        R = {r["team_rule_id"]: r for r in self.eng_rules}
        got = {k: resolve(k, self.eng_rules) for k in TABLE}
        self.assertEqual(len(set(got.values())), len(TABLE))
        for k, rid in got.items():
            self.assertEqual((R[rid]["jurisdiction"], R[rid]["status"]), want[k], k)
        self.assertEqual(R[got["NJ-ALG-01"]]["effective_date"], "2027-07-01")
        self.assertEqual(R[got["CA-ALG-01"]]["effective_date"], "2026-01-01")

    def test_no_mutual_or_chained_yields(self):
        cells = {}
        for r in self.eng_rules:
            cells.setdefault((r["jurisdiction"], r["category"]), []).append(r)
        for r in self.eng_rules:
            for d in r.get("yields_to") or []:
                for t in cells.get((d["jurisdiction"], d["category"]), []):
                    self.assertFalse(t.get("yields_to"), f"{r['team_rule_id']} yields to {t['team_rule_id']} which yields further")

    def test_rules_json_schema(self):
        schema = load_json(ROOT / "data/schema/rule_record.schema.json")
        self.assertEqual(set(self.pub), {"rules"})
        errs = [f"{r.get('team_rule_id')}: {m}" for r in self.pub["rules"] for m in validate(r, schema)]
        self.assertEqual(errs, [])
        self.assertEqual(len({r["team_rule_id"] for r in self.pub["rules"]}), len(self.pub["rules"]))
        for r in self.pub["rules"]:
            self.assertEqual(list(r), PUBLIC)  # strict official fields only
            for k, v in r.items():
                if k != "quoted_span" and isinstance(v, str):
                    self.assertNotRegex(v, DASH, f"{r['team_rule_id']}.{k}")

    def test_rules_json_matches_engine(self):
        self.assertEqual([{k: r.get(k) for k in PUBLIC} for r in self.eng_rules], self.pub["rules"])


def validate(obj, s, path=""):
    """Minimal stdlib JSON-schema check: type, enum, pattern, minLength, minimum, maximum, required, items, properties."""
    e = []
    tmap = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "array": list, "object": dict, "null": type(None)}
    if "type" in s:
        ts = s["type"] if isinstance(s["type"], list) else [s["type"]]
        ok = any(isinstance(obj, tmap[t]) and not (t in ("number", "integer") and isinstance(obj, bool)) for t in ts)
        if not ok:
            return [f"{path}: {type(obj).__name__} not in {ts}"]
    if "enum" in s and obj not in s["enum"]: e.append(f"{path}: {obj!r} not in enum")
    if isinstance(obj, str):
        if "pattern" in s and not re.search(s["pattern"], obj): e.append(f"{path}: {obj!r} !~ {s['pattern']}")
        if len(obj) < s.get("minLength", 0): e.append(f"{path}: shorter than {s['minLength']}")
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if "minimum" in s and obj < s["minimum"]: e.append(f"{path}: < minimum")
        if "maximum" in s and obj > s["maximum"]: e.append(f"{path}: > maximum")
    if isinstance(obj, dict):
        e += [f"{path}: missing {k}" for k in s.get("required", []) if k not in obj]
        e += [f"{path}: extra field {k}" for k in obj if "properties" in s and k not in s["properties"]]
        for k, sub in s.get("properties", {}).items():
            if k in obj: e += validate(obj[k], sub, f"{path}.{k}")
    if isinstance(obj, list) and "items" in s:
        for i, x in enumerate(obj): e += validate(x, s["items"], f"{path}[{i}]")
    return e


class MergeRules(unittest.TestCase):
    def setUp(self):
        self.tmp = ROOT / "work/review/tmp_merge"
        shutil.rmtree(self.tmp, ignore_errors=True)
        (self.tmp / "in").mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _merge(self, groups):
        files = []
        for i, g in enumerate(groups):
            p = self.tmp / "in" / f"G{i}.json"
            p.write_text(json.dumps(g)); files.append(str(p))
        with contextlib.redirect_stdout(io.StringIO()):
            merge(files, str(self.tmp / "out"))
        audit = load_json(sorted((self.tmp / "out/audit").glob("merge_*.json"))[-1])
        return load_json(self.tmp / "out/rules_engine.json")["rules"], load_json(self.tmp / "out/rules.json")["rules"], audit

    def test_prune_renumber_cells(self):
        a = rule("L-2", "Boston, MA", cat="security_deposits", y=[("MA", "security_deposits"), ("Boston, MA", "rent_increase_limits")],
                 cw=[("Boston, MA", "security_deposits")])
        b = rule("L-1", "MA", cat="security_deposits")
        rules, pub, audit = self._merge([{"rules": [a, b], "no_rule": [{"jurisdiction": "CA", "category": "rent_increase_limits"}]}])
        self.assertEqual([(r["team_rule_id"], r["jurisdiction"]) for r in rules], [("r-0001", "MA"), ("r-0002", "Boston, MA")])
        self.assertEqual(rules[1]["yields_to"], [{"jurisdiction": "MA", "category": "security_deposits"}])
        self.assertEqual(rules[1]["conflicts_with"], [])
        self.assertEqual(len(audit["pruned_descriptors"]), 2)
        self.assertEqual(audit["idmap"], {"L-1": "r-0001", "L-2": "r-0002"})
        self.assertEqual(len(audit["cells_unaccounted"]), 13 * 6 - 3)
        self.assertNotIn(["CA", "rent_increase_limits"], audit["cells_unaccounted"])
        self.assertTrue(all(list(r) == PUBLIC for r in pub))

    def test_BUG_ids_depend_on_input_order(self):  # merge_rules.py:22 sort key has no tie-breaker
        x, y = rule("x", "MA", cat="security_deposits", eff="2025-08-01"), rule("y", "MA", cat="security_deposits", eff="2025-08-01")
        x["citation"], y["citation"] = "M.G.L. c.186 § 15B", "M.G.L. c.112 § 87"
        r1 = {r["citation"]: r["team_rule_id"] for r in self._merge([{"rules": [x, y]}])[0]}
        r2 = {r["citation"]: r["team_rule_id"] for r in self._merge([{"rules": [y, x]}])[0]}
        self.assertEqual(r1, r2)

    def test_BUG_dangling_overrides_kept(self):  # merge_rules.py:31 keeps unknown ids verbatim
        a = rule("L-1", "MA", cat="security_deposits"); a["overrides"] = ["L-9"]
        self.assertEqual(self._merge([{"rules": [a]}])[0][0]["overrides"], [])

    def test_real_merge_reproduces_outputs(self):
        import glob
        files = sorted(glob.glob(str(ROOT / "work/consolidate/*.json")))
        with contextlib.redirect_stdout(io.StringIO()):
            merge(files, str(self.tmp / "out"))
        self.assertEqual(load_json(self.tmp / "out/rules_engine.json")["rules"], load_json(OUT / "rules_engine.json")["rules"])


if __name__ == "__main__":
    unittest.main()
