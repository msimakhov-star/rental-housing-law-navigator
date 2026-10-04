"""Module B part 1: geocode sample addresses to legal jurisdiction stacks + normalise building facts.
Stdlib only. Usage: python3 -m navigator.resolve [--facts-only]
Cache: work/geocode_cache/<address_id>.json (reruns are free)."""
import csv, json, re, sys, time, threading, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "work" / "geocode_cache"
BASE = "https://geocoding.geo.census.gov/geocoder/geographies/"
IN_SCOPE = {"Los Angeles": "CA", "San Francisco": "CA", "San Diego": "CA", "Berkeley": "CA", "Santa Ana": "CA",
            "Jersey City": "NJ", "Hoboken": "NJ", "Newark": "NJ", "Boston": "MA", "Cambridge": "MA"}
DATASET_CITY = {"LA County": "Los Angeles", "DataSF": "San Francisco", "SANDAG": "San Diego", "Alameda": "Berkeley",
                "Boston": "Boston", "Cambridge": "Cambridge"}
ASOF_YEAR = 2026
_lock = threading.Lock(); _last = [0.0]


def expected_city(row):
    for k, v in DATASET_CITY.items():
        if row["source_dataset"].startswith(k):
            return v
    return row["postal_city"]  # NJ: postal city is one of the three NJ cities


def _get(url):
    for i in range(5):
        with _lock:  # ponytail: global pacing ~4 req/s total across workers
            w = _last[0] + 0.25 - time.time()
            if w > 0: time.sleep(w)
            _last[0] = time.time()
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.load(r)
        except Exception as e:
            err = str(e); time.sleep(2 ** i)
    return {"error": err}


def street_variants(s):
    s = re.sub(r"\s+(?:(?:APT|UNIT|STE|SUITE|LOT)\b|#)\s*\S*.*$", "", s.strip(), flags=re.I)
    s = re.sub(r"\s+M-D$", "", s).rstrip(".")
    out = [s]
    n = re.sub(r"\b0(\d(?:ST|ND|RD|TH))\b", r"\1", s)  # 05TH -> 5TH
    n = re.sub(r"\bAV\.?$", "AVE", n); n = re.sub(r"\bBLV$", "BLVD", n)
    if n != s: out.append(n); s = n
    m = re.match(r"^(\d+)[A-Z]?(?:\.\d)?\s*[-&/]\s*(\d+)[A-Z]?(?:\.\d)?\s+(.*)$", s)
    if m:
        out += [f"{m[1]} {m[3]}", f"{m[2]} {m[3]}"]
    m = re.match(r"^(\d+)([A-Z])\s+(.*)$", s)  # 335A Harvard -> 335 Harvard
    if m: out.append(f"{m[1]} {m[3]}")
    m = re.match(r"^(\d+)\s*[-&].*?(?:AVE|ST|RD|BLVD|DR)\b.*$", s)
    return list(dict.fromkeys(out))


def geocode(row):
    f = CACHE / f"{row['address_id']}.json"
    if f.exists():
        return json.loads(f.read_text())
    city = expected_city(row); st = row["state"]
    zipc = row["zip"] if st != "NJ" and re.fullmatch(r"\d{5}", row["zip"] or "") else ""
    attempts, match = [], None
    common = "&benchmark=Public_AR_Current&vintage=Current_Current&layers=all&format=json"
    for sv in street_variants(row["street_address"]):
        for z in ([zipc, ""] if zipc else [""]):
            q = {"street": sv, "city": city, "state": st}
            if z: q["zip"] = z
            d = _get(BASE + "address?" + urllib.parse.urlencode(q) + common)
            ms = d.get("result", {}).get("addressMatches", [])
            attempts.append({"endpoint": "address", "q": q, "n": len(ms), "error": d.get("error")})
            if ms: match = ms[0]; break
        if match: break
    if not match:
        for sv in street_variants(row["street_address"])[:1]:
            one = f"{sv}, {city}, {st}"
            d = _get(BASE + "onelineaddress?" + urllib.parse.urlencode({"address": one}) + common)
            ms = d.get("result", {}).get("addressMatches", [])
            attempts.append({"endpoint": "oneline", "q": one, "n": len(ms), "error": d.get("error")})
            if ms: match = ms[0]
    rec = {"address_id": row["address_id"], "match": match, "attempts": attempts}
    f.write_text(json.dumps(rec))
    return rec


def build_stack(row, rec):
    exp = expected_city(row); st = row["state"]
    out = {"state": st, "county": None, "place": None, "legal_city": None, "stack": [st], "geocode_status": "failed",
           "matched_address": None, "lat": None, "lon": None, "confidence": 0.0, "notes": ""}
    m = rec["match"]
    if m:
        g = m["geographies"]
        pl = (g.get("Incorporated Places") or [{}])[0].get("NAME")
        cdp = (g.get("Census Designated Places") or [{}])[0].get("NAME")
        co = (g.get("Counties") or [{}])[0].get("NAME")
        sub = (g.get("County Subdivisions") or [{}])[0].get("NAME")
        mst = (g.get("States") or [{}])[0].get("STUSAB") or st
        out.update(state=mst, county=co, place=pl or cdp or sub, matched_address=m.get("matchedAddress"),
                   lat=m["coordinates"]["y"], lon=m["coordinates"]["x"])
        # exact = raw street string matched on the address endpoint (zip or no-zip); anything else is non_exact
        hit = next(a for a in rec["attempts"] if a["n"])
        first_ok = hit["endpoint"] == "address" and hit["q"]["street"] == rec["attempts"][0]["q"]["street"]
        out["geocode_status"] = "exact" if first_ok else "non_exact"
        out["confidence"] = 0.97 if first_ok else 0.8
        if mst != st:
            out["notes"] += f"Geocoded state {mst} differs from dataset state {st}. "; out["confidence"] = 0.4
        if pl and row["source_dataset"].startswith(("Cambridge", "Boston", "DataSF")):
            nm0 = re.sub(r" (city|town)$", "", pl)
            if nm0 != exp:
                out["notes"] += f"Geocoder placed address in '{pl}' but city-limited source dataset says {exp}; trusting dataset (shared street name?). "
                out["place"] = f"{exp} city (dataset)"; pl = None; out["legal_city"] = f"{exp}, {mst}"
                out["county"] = None  # the geocoder's county belongs to the wrong city, so do not show it
                out["geocode_status"] = "non_exact"; out["confidence"] = 0.5
        if pl:
            nm = re.sub(r" (city|town|village|borough|CDP)$", "", pl)
            if nm in IN_SCOPE and IN_SCOPE[nm] == mst: out["legal_city"] = f"{nm}, {mst}"
            else: out["notes"] += f"Legal place '{pl}' is not an in-scope city. "
        else:
            out["notes"] += f"No incorporated place (CDP/subdivision: {cdp or sub}). "
        if not first_ok: out["notes"] += "Matched via street variant/no-zip/oneline retry. "
    else:
        out.update(geocode_status="fallback_postal", legal_city=f"{exp}, {st}", place=None, confidence=0.4,
                   notes="Census No_Match; legal city assumed from postal city/source dataset. ")
        out["county"] = None
    out["stack"] = [x for x in [out["state"], out["county"], out["legal_city"]] if x]
    out["notes"] = out["notes"].strip() or None
    return out


# ---------- facts ----------
def to_int(s):
    try: return int(float(s))
    except Exception: return None


def parse_nj_units(desc):
    """'6B-20U-G' / '3S-F-D-6U-NH' -> 20 / 6. Multi-part ('3B-7U/4B-24U-G') is ambiguous -> None."""
    if "/" in desc: return None
    m = re.fullmatch(r"\d+(?:S|B|S\+BT)?-?(?:[A-Z]-?){0,3}(\d+)U(?:-[A-Z]+)*", desc.replace(".", ""))
    m2 = re.search(r"(?<![\d])(\d+)U(?![A-Z])", desc)
    return int(m2[1]) if m2 else None


def facts_for(row):
    ds, uc, ud = row["source_dataset"], row["use_code"], row["use_description"]
    yb = to_int(row["year_built"]); u = to_int(row["units"])
    ynote = None
    if row["year_built"] in ("", None): ynote = "missing in source"
    elif yb is None or yb < 1800 or yb > ASOF_YEAR or (yb == 1800):
        ynote = f"impossible/placeholder year {row['year_built']}, set to null"; yb = None
    if u is not None and u <= 0: u = None
    umin = None; usrc = "none"; unote = "no unit count in source"
    if u is not None:
        usrc = "assessor"; unote = "exact count given by assessor"
    # class lower bounds
    if ds.startswith("NJ"):
        pj = parse_nj_units(ud)
        # ponytail: parsed NJ 'nnU' NOT promoted to units: only 1 row has an assessor count (A0227: 2 vs '93U'), cannot validate
        if u is not None and uc == "4C" and pj is not None and u != pj:
            unote = f"assessor units={u} conflicts with class 4C (>=5) and description '{ud}' ({pj}U): unreliable, units nulled"
            u = None; usrc = "none"; conflict = unote
        else: conflict = ""
        if uc == "4C":
            umin = 5
            if u is None:
                usrc = "use_code_class"
                unote = (conflict + "; " if conflict else "") + "NJ property class 4C = apartments, 5 or more units" + (f"; description '{ud}' suggests {pj}U (unvalidated hint, not used as units)" if pj else "")
    elif ds.startswith("LA"):
        if uc.startswith("05") or "Five or more" in ud:
            umin = 5
            if u is None: usrc, unote = "use_code_class", "LA use code 05xx 'Five or more apartments' => >=5"
    elif ds.startswith("DataSF"):
        umin = {"A5": 5, "A15": 15, "FS5": 5, "F5": 5}.get(uc)
        if u is None and umin: usrc, unote = "use_code_class", f"SF class {uc} ({ud}) lower bound"
        if uc == "TIC": umin = None; unote += "; TIC building 4 units or less per class"
    elif ds.startswith("SANDAG"):
        umin = 5
        if u is None: usrc, unote = "use_code_class", "SANDAG asr_landuse 14-16 = 5+ units"
    elif ds.startswith("Alameda"):
        umin = 5; usrc, unote = "use_code_class", "Alameda use code described as 5+ units; no count in sample"
    elif ds.startswith("Boston"):
        m = re.search(r"APT (\d+)-(\d+) UNITS", ud)
        if m: umin = int(m[1])
        if uc.startswith("A/"):
            usrc = "use_code_class" if (m or True) else "none"
            unote = ("A/112 'APT 7-30 UNITS' => 7 to 30 units (units_min=7)" if m else
                     f"Boston code {uc} '{ud}': apartment/residential parcel, unit count not in sample (class does not guarantee >=5)")
            if not m: usrc = "none"
    elif ds.startswith("Cambridge"):
        if uc == "111" and u is not None: umin = 4
        if uc == "112": umin = 9
    if umin is not None and u is not None and u < umin and usrc != "assessor":
        umin = None
    return {"year_built": yb, "units": u, "units_min": umin, "units_source": usrc, "units_note": unote,
            "use_code": uc, "use_description": ud, "year_note": ynote}


def main(facts_only=False):
    rows = list(csv.DictReader(open(ROOT / "data" / "sample_addresses.csv")))
    CACHE.mkdir(parents=True, exist_ok=True)
    facts = {r["address_id"]: facts_for(r) for r in rows}
    (ROOT / "work" / "address_facts.json").write_text(json.dumps(facts, indent=1))
    if facts_only: return
    with ThreadPoolExecutor(4) as ex:
        recs = list(ex.map(geocode, rows))
    jur, anomalies = {}, []
    for r, rec in zip(rows, recs):
        j = build_stack(r, rec); jur[r["address_id"]] = j
        exp = f"{expected_city(r)}, {r['state']}"
        if j["legal_city"] != exp or j["geocode_status"] in ("fallback_postal", "failed", "non_exact"):
            anomalies.append({"address_id": r["address_id"], "street": r["street_address"], "expected": exp,
                              "legal_city": j["legal_city"], "place": j["place"], "status": j["geocode_status"], "notes": j["notes"]})
    jur["_summary"] = {"n": len(rows), "by_status": dict(Counter(j["geocode_status"] for k, j in jur.items() if k[0] == "A")),
                       "by_legal_city": dict(Counter(str(j["legal_city"]) for k, j in jur.items() if k[0] == "A")),
                       "anomalies": anomalies}
    (ROOT / "work" / "jurisdictions.json").write_text(json.dumps(jur, indent=1))
    print(json.dumps({k: v for k, v in jur["_summary"].items() if k != "anomalies"}, indent=1), len(anomalies), "anomalies")


if __name__ == "__main__":
    main("--facts-only" in sys.argv)
