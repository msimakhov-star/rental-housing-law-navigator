import csv, json, unittest
from pathlib import Path
R = Path(__file__).resolve().parent.parent
IN = {"Los Angeles, CA", "San Francisco, CA", "San Diego, CA", "Berkeley, CA", "Jersey City, NJ", "Hoboken, NJ",
      "Newark, NJ", "Boston, MA", "Cambridge, MA"}
ids = [r["address_id"] for r in csv.DictReader(open(R / "data/sample_addresses.csv"))]
J = json.load(open(R / "work/jurisdictions.json")); F = json.load(open(R / "work/address_facts.json"))


class T(unittest.TestCase):
    def test_all_ids(self):
        self.assertEqual(len(ids), 500)
        for i in ids: self.assertIn(i, J); self.assertIn(i, F)

    def test_stack_consistent(self):
        for i in ids:
            j = J[i]
            self.assertEqual(j["stack"][0], j["state"])
            self.assertTrue(j["legal_city"] is None or j["legal_city"] in IN)
            if j["legal_city"]:
                self.assertEqual(j["stack"][-1], j["legal_city"]); self.assertTrue(j["legal_city"].endswith(", " + j["state"]))
            self.assertIn(j["geocode_status"], {"exact", "non_exact", "fallback_postal", "failed"})

    def test_samples(self):
        self.assertEqual(J["A0001"]["legal_city"], "Los Angeles, CA")
        self.assertEqual(J["A0001"]["county"], "Los Angeles County")
        self.assertEqual(J["A0002"]["legal_city"], "Hoboken, NJ")
        self.assertEqual(J["A0002"]["state"], "NJ")
        self.assertEqual(F["A0001"]["units"], 32); self.assertEqual(F["A0001"]["year_built"], 1927)
        self.assertEqual(F["A0002"]["year_built"], 2001); self.assertIsNone(F["A0002"]["units"]); self.assertEqual(F["A0002"]["units_min"], 5)

    def test_facts(self):
        for f in F.values():
            self.assertTrue(f["year_built"] is None or 1800 < f["year_built"] <= 2026)
            self.assertTrue(f["units"] is None or f["units"] > 0)
            self.assertIn(f["units_source"], {"assessor", "use_description_parsed", "use_code_class", "none"})
            if f["units"] and f["units_min"]: self.assertGreaterEqual(f["units"], f["units_min"])


if __name__ == "__main__": unittest.main()
