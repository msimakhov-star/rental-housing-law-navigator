"""Shared constants and helpers. Stdlib only."""
import csv, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATEGORIES = ["rent_increase_limits", "just_cause_eviction", "security_deposits",
              "application_screening_fees", "screening_restrictions", "algorithmic_rent_setting"]
STATUSES = ["in_force", "not_yet_effective", "pending", "failed"]
STATES = ["CA", "NJ", "MA"]
CITIES = ["Los Angeles, CA", "San Francisco, CA", "San Diego, CA", "Berkeley, CA", "Santa Ana, CA",
          "Jersey City, NJ", "Hoboken, NJ", "Newark, NJ", "Boston, MA", "Cambridge, MA"]
JURISDICTIONS = STATES + CITIES
RESULTS = ["applies", "unknown", "superseded", "not_yet_effective", "pending"]
AS_OF = "2026-10-01"


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump_json(p, obj, compact=False):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    s = json.dumps(obj, separators=(",", ":"), ensure_ascii=False) if compact else json.dumps(obj, indent=1, ensure_ascii=False)
    Path(p).write_text(s + "\n", encoding="utf-8")


def doc_path(doc_id):
    for d in ("data/corpus/text", "data/corpus_extra/text"):
        p = ROOT / d / f"{doc_id}.txt"
        if p.exists():
            return p
    return None


def doc_text(doc_id):
    p = doc_path(doc_id)
    return p.read_text(encoding="utf-8") if p else None


def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def check_quote(doc_id, span):
    """'single_line' if span is a substring of one raw line, 'ws_normalized' if it only matches after
    whitespace collapsing, None if absent (or doc unknown)."""
    t = doc_text(doc_id)
    if t is None or not span:
        return None
    if "\n" not in span and any(span in ln for ln in t.splitlines()):
        return "single_line"
    return "ws_normalized" if norm_ws(span) in norm_ws(t) else None


def manifest():
    with open(ROOT / "data/corpus/corpus_manifest.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    extra = ROOT / "data/corpus_extra/manifest.csv"
    if extra.exists():
        with open(extra, newline="", encoding="utf-8") as f:
            rows += list(csv.DictReader(f))
    return {r["doc_id"]: r for r in rows}


def addresses():
    with open(ROOT / "data/sample_addresses.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
