# Adding a jurisdiction (facts only; checked against the code on 2026-10-04)

Today the jurisdiction lists are hard-coded in several modules. The engine logic does not change, but the places below must be edited by hand. Stage 2 has never run on a real backend through the runner (production stage 2 was done by Claude Code agents), so expect to supervise it. Not legal advice.

## What you need first
- Source text of the law for the city (official or code publisher pages), saved as `data/corpus_extra/text/Xnnn.txt` or `data/corpus/text/Dnnn.txt` with the header lines `SOURCE:` and `RETRIEVED:`.
- A row per document in `data/corpus_extra/manifest.csv` (or `data/corpus/corpus_manifest.csv`): doc_id, jurisdictions, url, source_type, capture, retrieved_at, sha256, text_file, status.
- Addresses for the city in `data/sample_addresses.csv` with a `source_dataset` value, if you want lookups.

## Edit these places
1. `navigator/common.py`: add the exact string `"City, ST"` to `CITIES` (line 10). If the state is new, also `STATES` (line 9); `validate.py` line 55 uses STATES to check level vs jurisdiction.
2. `navigator/apply.py`: add the same string to `CITY_NAMES` (line 7). Lines 104 and 157 hard-code the state codes `("CA", "NJ", "MA")`: extend them for a new state.
3. `navigator/resolve.py`:
   - `IN_SCOPE` (line 12): `"City": "ST"`.
   - `DATASET_CITY` (line 14): map the start of the `source_dataset` value to the city name. States without an entry fall back to the postal city (NJ works this way).
   - `facts_for()` (line 144): add an `elif ds.startswith("<dataset>")` branch (the parcel adapter) that sets `units_min` and `units_source` from the assessor's use code. Exact `units` and `year_built` come from the CSV columns. Without a branch the city has no unit or class hint.
   - `parse_nj_units()` (line 136) is NJ specific. Add an equivalent only if your dataset encodes units in a description.
4. `navigator/consolidate.py`: add the city to a group in `GROUPS` (line 11), or a new group (its first entry is the state). The runner takes `--group`.
5. `navigator/test_map.py`: change test descriptors only if a new change test involves the city.
6. Prompts: `prompts/extract_doc.md` and `prompts/consolidate_cells.md` hold the jurisdiction strings and citation formats. Add the new jurisdiction string and its official citation style. `CONTRACTS.md` also lists the exact jurisdiction strings (the runners read it).
7. Spanish rule text: `work/es_rules.json` is keyed by rule id; new rules need entries, otherwise the Spanish view falls back to English text.
8. `web/`: if the UI hard-codes a city list, update it (check `web/app.js`).

## Run order
```sh
python3 -m navigator.resolve                                   # facts and legal-city stacks (needs network for the Census Geocoder; cached in work/geocode_cache)
python3 -m navigator.extract --doc Xnnn --out work/extract_run # stage 1 per document (set LLM_BACKEND; see docs/llm_backends.md)
python3 -m navigator.consolidate --group <GROUP> --out work/consolidate_run   # stage 2, long prompts (110 to 260 KB)
# review the *_run outputs, then copy to work/extract/ and work/consolidate/ (the runners only write there with the literal --out work/extract)
python3 -m navigator.merge_rules
python3 -m navigator.pipeline build
python3 -m navigator.pipeline check
python3 -m navigator.validate --rules outputs/rules_engine.json
python3 -m unittest discover -s tests -p 'test_*.py'
```
Check: new rules appear in `outputs/rules.json`, quotes validate verbatim, a sample address in the new city shows results in `outputs/lookups_detail.json`.
