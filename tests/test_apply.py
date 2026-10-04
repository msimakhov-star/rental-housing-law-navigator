"""Offline engine tests on tests/fixtures (test-only rules). Run: python3 -m unittest tests.test_apply"""
import tempfile, unittest, json
from pathlib import Path
from navigator import apply as apply_mod
from navigator.apply import Engine, eval_pred, evaluate_address, norm_date
from navigator.pipeline import cfg, load_world, build, check, read_tests
from navigator.changes import run_tests
from navigator.test_map import resolve, MapError

NOW = "2026-10-01"


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp()
        cls.c = cfg("tests/fixtures", cls.out)
        rules, cls.addrs, _ = load_world(cls.c)
        cls.rules = rules
        cls.eng = Engine(rules, {a: {"facts": v["facts"], "loc": v["loc"]} for a, v in cls.addrs.items()})

    def res(self, a, d=NOW):
        return {r: e["result"] for r, e in self.eng.at(a, d).items()}

    def test_sf_example(self):  # 20 units, built 1962, SF
        r = self.res("A0001")
        self.assertEqual(r["r-0003"], "applies")
        self.assertEqual(r["r-0002"], "superseded")

    def test_cutoff_year_unknown(self):  # built 1979 == cutoff year 1979
        r = self.res("A0002")
        self.assertEqual(r["r-0003"], "unknown")
        self.assertEqual(r["r-0002"], "unknown")  # depends on whether the SF rule covers it
        self.assertEqual(self.eng.at("A0002", NOW)["r-0003"]["missing_facts"], ["co_date"])

    def test_age_boundary_unknown(self):  # built 2011, as_of 2026 => age 15 == threshold
        self.assertEqual(self.res("A0012")["r-0002"], "unknown")
        self.assertEqual(self.res("A0012", "2027-01-01")["r-0002"], "applies")

    def test_small_landlord_exemption(self):
        self.assertEqual(self.res("A0001")["r-0004"], "applies")      # 20 units: exemption FALSE
        self.assertEqual(self.res("A0004")["r-0004"], "unknown")      # units null
        self.assertNotIn("r-0004", self.res("A0003"))                 # 2 units: exempt TRUE => omitted

    def test_class_bound_not_trusted_by_default(self):  # inference is not data: unknown
        f = {"units": None, "units_min": 5, "year_built": None}
        self.assertFalse(apply_mod.TRUST_UNITS_MIN)
        self.assertEqual(eval_pred({"fact": "units", "op": ">=", "value": 5}, f, NOW)[0], "UNKNOWN")
        self.assertEqual(eval_pred({"fact": "units", "op": "<", "value": 5}, f, NOW)[0], "UNKNOWN")

    def test_lower_bound(self):
        apply_mod.TRUST_UNITS_MIN = True
        self.addCleanup(setattr, apply_mod, "TRUST_UNITS_MIN", False)
        f = {"units": None, "units_min": 5, "year_built": None}
        self.assertEqual(eval_pred({"fact": "units", "op": ">=", "value": 5}, f, NOW)[0], "TRUE")
        self.assertEqual(eval_pred({"fact": "units", "op": "<", "value": 5}, f, NOW)[0], "FALSE")
        self.assertEqual(eval_pred({"fact": "units", "op": ">=", "value": 9}, f, NOW)[0], "UNKNOWN")
        self.assertEqual(eval_pred({"unavailable": "owner type"}, f, NOW)[0], "UNKNOWN")
        # Kleene: FALSE beats UNKNOWN in all, TRUE beats UNKNOWN in any
        u = {"unavailable": "x"}; fl = {"fact": "units", "op": "<", "value": 5}
        self.assertEqual(eval_pred({"all": [u, fl]}, f, NOW)[0], "FALSE")
        self.assertEqual(eval_pred({"any": [u, {"not": fl}]}, f, NOW)[0], "TRUE")

    def test_t1_ab325(self):
        self.assertEqual(self.res("A0001", "2025-12-31")["r-0001"], "not_yet_effective")
        self.assertEqual(self.res("A0001", "2026-01-02")["r-0001"], "applies")

    def test_t3_nj_fair_and_conflicts(self):
        self.assertEqual(self.res("A0007")["r-0007"], "not_yet_effective")
        self.assertEqual(self.res("A0007", "2027-07-02")["r-0007"], "applies")
        flag = lambda a: self.eng.at(a, "2027-07-02")["r-0007"]["conflict_flag"]
        self.assertTrue(flag("A0005") and flag("A0006"))
        self.assertFalse(flag("A0007"))  # Newark: no local ban

    def test_pending_and_failed(self):
        r = self.res("A0008")
        self.assertEqual((r["r-0008"], r["r-0009"]), ("pending", "pending"))
        self.assertNotIn("r-0010", r)

    def test_legal_city_handling(self):
        self.assertEqual(self.res("A0010")["r-0006"], "unknown")      # geocode failed: city unconfirmed
        self.assertNotIn("r-0005", self.res("A0010"))                 # other postal city
        r = self.res("A0011")                                         # Oakland: confirmed outside all cities
        self.assertFalse({"r-0003", "r-0005", "r-0006"} & set(r))
        self.assertNotIn("r-0006", self.res("A0007"))                 # Newark gets no JC rule

    def test_dates(self):
        self.assertEqual(norm_date("2026"), "2026-01-01")
        self.assertEqual(norm_date("2026-03"), "2026-03-01")

    def test_timeline_compresses(self):
        tl = self.eng.timeline("A0001")["r-0001"]
        self.assertEqual([(d, e["result"]) for d, e in tl], [("0000-01-01", "not_yet_effective"), ("2026-01-01", "applies")])

    def test_changes(self):
        ch, det, err = run_tests(read_tests(self.c), self.eng)
        self.assertEqual(err, {})
        self.assertEqual(ch["T5"]["affected_address_ids"], [])
        self.assertEqual(ch["T2"]["affected_address_ids"], ["A0005", "A0006"])
        self.assertEqual(ch["T3"]["conflict_flag_address_ids"], ["A0005", "A0006", "A0010"])
        self.assertEqual(ch["T4"]["affected_address_ids"], ["A0008", "A0009"])

    def test_mapping_fails_loudly(self):
        with self.assertRaises(MapError): resolve("CA-ALG-01", [r for r in self.rules if r["team_rule_id"] != "r-0001"])
        with self.assertRaises(MapError): resolve("CA-ALG-01", self.rules + [dict(self.rules[0], team_rule_id="r-9999")])

    def test_build_and_check(self):
        eng, lk, ch, terr, _ = build(self.c)
        self.assertEqual(terr, {})
        self.assertEqual(len(lk), 12)
        self.assertEqual(check(self.c), 0)
        d = json.loads((Path(self.out) / "lookups_detail.json").read_text())
        self.assertIn("explanation_es", d["addresses"]["A0001"]["results"][0]["timeline"][0])
        txt = json.dumps(d, ensure_ascii=False)
        self.assertNotIn("—", txt); self.assertNotIn("–", txt)
        self.assertTrue(all(e["explanation"].endswith("Not legal advice.") for es in lk.values() for e in es))


if __name__ == "__main__":
    unittest.main()
