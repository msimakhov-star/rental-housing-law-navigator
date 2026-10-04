"""Offline tests for eval/score_proxy.py and eval/check_spots.py using tiny fake files."""
import csv, importlib.util, json, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval")); sys.path.insert(0, str(ROOT))
import score_proxy as sp  # noqa: E402
import check_spots as cs  # noqa: E402

DOCS = {"D1": "Sec. 1947.12 limits rent to 5% plus CPI.\nLine two. P.L.2026, c.43 FAIR Act.", "D2": "Chapter 218-12 bans software."}


def rule(i, jur, cat, cit, **kw):
    r = {"team_rule_id": i, "jurisdiction": jur, "level": "state" if len(jur) == 2 else "city", "category": cat,
         "status": "in_force", "title": "t", "requirement": "r", "citation": cit, "source_url": "http://x",
         "quoted_span": "Sec. 1947.12 limits rent to 5% plus CPI.", "source_doc_id": "D1", "confidence": 0.9}
    r.update(kw); return r


class Base(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        sp.check_quote = lambda d, s: "single_line" if d in DOCS and s in DOCS[d] else None
        sp.doc_text = lambda d: DOCS.get(d)
        rows = [("A1", "Jersey City", "NJ"), ("A2", "Hoboken", "NJ"), ("A3", "Newark", "NJ"), ("A4", "Boston", "MA"), ("A5", "Los Angeles", "CA")]
        with open(self.t / "addr.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["address_id", "postal_city", "state", "street_address"])
            for a, c, s in rows: w.writerow([a, c, s, "1 Main"])
        self.rules = [rule("r1", "CA", "rent_increase_limits", "Cal. Civ. Code § 1947.12", key_value="5% + CPI", effective_date="2020-01-01"),
                      rule("r2", "Jersey City, NJ", "algorithmic_rent_setting", "Jersey City Code § 218-12", source_doc_id="D2",
                           quoted_span="Chapter 218-12 bans software.", effective_date="2025-06-01"),
                      rule("r3", "NJ", "algorithmic_rent_setting", "P.L.2026, c.43", status="not_yet_effective", effective_date="2027-07-01",
                           citation_note="x")]

    def args(self, rules=None, lookups=None, changes=None):
        def w(n, o):
            p = self.t / n; p.write_text(json.dumps(o)); return str(p)
        return sp.argparse.Namespace(
            rules=w("rules.json", {"rules": rules if rules is not None else self.rules}),
            lookups=w("lookups.json", lookups) if lookups else str(self.t / "none1"),
            changes=w("changes.json", changes) if changes else str(self.t / "none2"),
            key=str(ROOT / "eval/proxy_key.json"), cells=str(ROOT / "eval/cells.json"),
            schema=str(ROOT / "data/schema/rule_record.schema.json"), addresses=str(self.t / "addr.csv"),
            jurisdictions=str(self.t / "nojur.json"))


class TestStatic(unittest.TestCase):
    def test_key_and_cells(self):
        k = json.loads((ROOT / "eval/proxy_key.json").read_text())["rules"]
        c = json.loads((ROOT / "eval/cells.json").read_text())["cells"]
        self.assertEqual(len(c), 78); self.assertEqual(len({(x["jurisdiction"], x["category"]) for x in c}), 78)
        self.assertEqual(len({e["id"] for e in k}), len(k))
        for e in k:
            self.assertIn((e["jurisdiction"], e["category"]), {(x["jurisdiction"], x["category"]) for x in c})
        import re
        for e in k: re.compile(e["cite_regex"])
        self.assertTrue(sp.match_rules([e for e in k if e["id"] == "CA-RENT"][0],
                                       [rule("r", "CA", "rent_increase_limits", "Cal. Civ. Code §1947.12")]))

    def test_validator(self):
        sch = json.loads((ROOT / "data/schema/rule_record.schema.json").read_text())
        self.assertEqual(sp.validate(rule("r", "CA", "rent_increase_limits", "c"), sch), [])
        bad = rule("r", "CA", "nope", "c", effective_date="2020/01", quoted_span="short")
        self.assertEqual(len(sp.validate(bad, sch)), 3)


class TestScorer(Base):
    def test_schema_recall_cells_citation(self):
        a = self.args()
        text, hard = sp.run(a)
        self.assertEqual(hard, 0, text)
        rec = sp.recall_report(json.loads(Path(a.key).read_text())["rules"], self.rules)
        ids = {r["id"] for r in rec["rows"] if r["found"]}
        self.assertEqual(ids, {"CA-RENT", "JC-ALG", "NJ-ALG"})
        self.assertEqual(rec["field_detail"]["effective_date"], (2, 2))  # CA-RENT has no date in key
        cell = sp.cell_report(json.loads(Path(a.cells).read_text())["cells"], self.rules)
        self.assertEqual(cell["n_zero"], 78 - 3); self.assertEqual(cell["outside_grid"], [])
        cit = sp.citation_report(self.rules, None)
        self.assertEqual(cit["kinds"]["missing"], 0)

    def test_invented_citation(self):
        rs = self.rules + [rule("r9", "CA", "security_deposits", "Cal. Civ. Code § 9999.99")]
        sus = sp.invented_cites(rs)
        self.assertEqual([s[0] for s in sus], ["r9"])
        self.assertEqual(sp.invented_cites(self.rules[:2]), [])

    def test_changes(self):
        rows = sp.load_addresses(self.t / "addr.csv")
        exp = sp.change_expected(rows, None)
        self.assertEqual(exp["T1"]["affected"], ["A5"]); self.assertEqual(exp["T2"]["affected"], ["A1", "A2"])
        self.assertEqual(exp["T3"]["affected"], ["A1", "A2", "A3"]); self.assertEqual(exp["T3"]["conflict"], ["A1", "A2"])
        self.assertEqual(exp["T4"]["affected"], ["A4"]); self.assertEqual(exp["T5"]["affected"], [])
        good = {"T1": {"affected_address_ids": ["A5"]}, "T2": {"affected_address_ids": ["A1", "A2"]},
                "T3": {"affected_address_ids": ["A1", "A2", "A3"], "conflict_flag_address_ids": ["A1", "A2"]},
                "T4": {"affected_address_ids": ["A4"]}, "T5": {"affected_address_ids": []}}
        r = sp.change_report(rows, None, good)
        self.assertTrue(all(v["score"] == 1.0 for v in r.values()))
        good["T2"]["affected_address_ids"] = ["A1", "A3"]
        self.assertAlmostEqual(sp.change_report(rows, None, good)["T2"]["affected"]["precision"], 0.5)

    def test_lookups(self):
        def e(rid, res="applies", cf=False): return {"team_rule_id": rid, "result": res, "explanation": "x", "conflict_flag": cf}
        L = {"as_of": "2026-10-01", "lookups": {"A1": [e("r2"), e("r3", "not_yet_effective", True)], "A2": [e("r3", "not_yet_effective")],
                                              "A3": [e("r3", "nope")], "A4": [], "A5": [e("r1"), e("r3", "applies")]}}
        a = self.args(lookups=L)
        text, hard = sp.run(a)
        self.assertGreater(hard, 0)  # bad enum + applies on not_yet_effective rule
        rows = sp.load_addresses(a.addresses)
        pkey = json.loads(Path(a.key).read_text())["rules"]
        rep = sp.lookup_report(rows, None, self.rules, L, pkey)
        self.assertEqual(rep["bad_enum"], 1); self.assertEqual(rep["applies_bad_status"], [("A5", "r3", "not_yet_effective")])
        self.assertEqual(rep["missing_addr"], [])
        self.assertIn("PROXY ESTIMATE", text)
        L["lookups"].pop("A4"); rep = sp.lookup_report(rows, None, self.rules, L, pkey)
        self.assertEqual(rep["missing_addr"], ["A4"])

    def test_absent_files(self):
        a = self.args(); a.rules = str(self.t / "missing.json")
        text, hard = sp.run(a); self.assertEqual(hard, 0); self.assertIn("TOTAL", text)


class TestSpots(unittest.TestCase):
    def test_spots(self):
        t = Path(tempfile.mkdtemp())
        rules = {"r1": {"jurisdiction": "San Francisco, CA", "category": "rent_increase_limits", "citation": "S.F. Admin. Code ch. 37", "title": "Rent Ordinance"}}
        det = {"rules": rules, "addresses": {
            "A1": {"stack": {"city": "San Francisco, CA"}, "facts": {"year_built": 1962, "units": 20},
                   "results": [{"team_rule_id": "r1", "timeline": [{"from": "0000-01-01", "result": "applies"}]}]},
            "A2": {"stack": {"city": "San Francisco, CA"}, "facts": {"year_built": 1979, "units": 20}, "results": []}}}
        (t / "d.json").write_text(json.dumps(det))
        (t / "s.json").write_text(json.dumps({"as_of": "2026-10-01", "cases": [
            {"id": "X1", "description": "old", "select": {"city": "San Francisco, CA", "year_built": {"lte": 1975}},
             "expect": [{"key": "SF-RENT", "result_in": ["applies"]}], "source": "t"},
            {"id": "X2", "description": "cutoff year", "select": {"city": "San Francisco, CA", "year_built": {"eq": 1979}},
             "expect": [{"key": "SF-RENT", "result_in": ["unknown"]}], "source": "t"},
            {"id": "X3", "description": "none", "select": {"city": "Boston, MA"}, "expect": [], "source": "t"}]}))
        out, fails = cs.run(t / "d.json", t / "s.json", ROOT / "eval/proxy_key.json")
        self.assertEqual(fails, 1, out)  # X2 fails: rule absent for A2 but 'unknown' expected
        self.assertTrue(any("X3 SKIP" in x for x in out))
        self.assertEqual(cs.main(["x", str(t / "nope.json")]), 0)


if __name__ == "__main__":
    unittest.main()
