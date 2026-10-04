import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R))
from navigator import llm, extract
from navigator.common import doc_text

D = "D081"
LINE = next(l.strip() for l in doc_text(D).splitlines() if "37.10C" in l and len(l.strip()) > 40)
GOOD = {"jurisdiction": "San Francisco, CA", "level": "city", "category": "algorithmic_rent_setting", "status": "in_force",
        "title": "SF algorithmic ban", "requirement": "Ban.", "key_value": "ban", "effective_date": "2024-10-14",
        "citation": "S.F. Admin. Code § 37.10C", "source_doc_id": D, "source_url": "https://x.test/", "quoted_span": LINE,
        "confidence": 0.9, "conflict_flag": False, "conflict_note": None, "interaction": None, "applies_if": None,
        "exempt_if": None, "yields_to": [], "conflicts_with": []}


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        p = mock.patch.object(llm, "ROOT", self.root); p.start(); self.addCleanup(p.stop)
        e = mock.patch.dict(os.environ, {"LLM_BACKEND": "fake", "LLM_MODEL": "m1", "LLM_FAKE_RESPONSE": '{"a":1}'}); e.start(); self.addCleanup(e.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_cache_replay_and_audit(self):
        self.assertEqual(llm.complete("hi", stage="s", key="k"), '{"a":1}')
        os.environ["LLM_BACKEND"] = "replay"
        os.environ["LLM_FAKE_RESPONSE"] = "changed"
        self.assertEqual(llm.complete("hi", stage="s", key="k"), '{"a":1}')
        with self.assertRaises(llm.CacheMiss) as c:
            llm.complete("other prompt", stage="s", key="k")
        self.assertIn("k.", str(c.exception))
        line = json.loads((self.root / "outputs/audit/llm_calls.jsonl").read_text().splitlines()[0])
        self.assertTrue(line["ok"]); self.assertEqual(line["stage"], "s"); self.assertEqual(line["response_chars"], 7)
        self.assertNotIn("KEY", json.dumps(line).upper().replace("KEY\"", ""))  # no credential fields

    def test_manual_pending(self):
        os.environ["LLM_BACKEND"] = "manual"
        with self.assertRaises(llm.Pending):
            llm.complete("hi", stage="s", key="k")
        self.assertTrue((self.root / "work/llm/pending/s_k.md").exists())

    def test_fence_stripping(self):
        self.assertEqual(extract.parse_json('```json\n{"a": 2}\n```'), {"a": 2})
        self.assertEqual(extract.parse_json('Sure: {"a": 3} done'), {"a": 3})

    def run_doc(self, responses):
        prompts = []
        def fake(prompt, **kw):
            prompts.append(prompt); return responses[min(len(prompts) - 1, len(responses) - 1)]
        with mock.patch.object(llm, "complete", fake):
            res, _ = extract.extract_doc(D, max_retries=2)
        return res, prompts

    def test_retry_with_feedback(self):
        bad = dict(GOOD, category="nonsense")
        res, prompts = self.run_doc(["```json\n" + json.dumps({"rules": [bad]}) + "\n```", json.dumps({"rules": [GOOD]})])
        self.assertEqual(len(prompts), 2)
        self.assertIn("bad category", prompts[1])
        self.assertEqual(res["run"]["validation_errors"], [])
        self.assertEqual(res["run"]["retries"], 1)

    def test_quote_repair(self):
        typo = dict(GOOD, quoted_span=LINE.replace("a", "e", 2))
        res, prompts = self.run_doc([json.dumps({"rules": [typo]})])
        self.assertEqual(len(prompts), 1)
        self.assertEqual(res["rules"][0]["quoted_span"], LINE)
        self.assertEqual(len(res["run"]["repairs"]), 1)

    def test_refuse_work_extract(self):
        for out in ("./work/extract", str(R / "work/extract")):
            with mock.patch.object(extract, "extract_doc", side_effect=AssertionError("must not run")), \
                    self.assertRaises(SystemExit):
                extract.main(["--doc", D, "--out", out])


if __name__ == "__main__":
    unittest.main()
