# Rental Housing Law Navigator: contracts (single source of truth)

Challenge: Hack-Nation x RealPage, "Rental Housing Law Navigator". Brief: `docs/challenge_brief.txt`, guide: `docs/participant_guide.txt`, starter README: `docs/starter_README.md`.
Deadline: **Sun 2026-10-04 14:00 BST (09:00 ET)**.
ORGANIZER RULINGS (official reply in Discord #challenge-02-realpage, Sat 2026-10-03 about 23:20 BST; they override the brief PDF):
1. `score.py`, the dev answer key and expected dev outputs will NOT be shared. Participant videos show our own system output and validation, not score.py output.
2. The hour-16 ordinance (T6) is REMOVED. Five change tests T1 to T5 only, all in `data/dev/change_tests.json`. No live surprise document.
3. The citation metric uses SUPPLIED corpus text only (`data/corpus/text/D*.txt`). Link-only pages we fetch ourselves (`data/corpus_extra/`, ids `X...`) may be used for research, extraction and coverage but do NOT count toward citations. Organizers said capturing link-only ecode360 pages AND reporting rules from secondary sources are both fine.
Query date default: **2026-10-01**. Everything below is "as of" that date unless a test says otherwise.

## What is scored (75 of 100 auto, 25 judges)
- Extraction 25: our rules matched to a hidden key (58 rules + 19 "no rule at this level") **by jurisdiction + category + citation**; field accuracy on `effective_date`, `status`, `key_value`, `citation`. The key is almost certainly a grid: 13 jurisdictions (CA, NJ, MA + 10 cities) x 6 categories. So: ONE canonical record per legal instrument per cell, official citation format, no padding, no invented rules.
- Address coverage 20: hidden key for 100 of the 500 addresses. Missing a rule that applies costs 2x; `unknown` earns partial credit. Never omit a rule that might apply: use `unknown`.
- Citations 15: share of `applies` answers with a source + a `quoted_span` found in the SUPPLIED corpus (D* docs only, X* gap-fill docs do not count). => spans must be verbatim, and when a supplied D* doc supports a rule, `source_doc_id` and `quoted_span` must come from that D* doc even if an X* doc is richer.
- Change tracking 15: overlap with expected affected sets T1..T5 + conflict flags on T3.
- Judges 25: plain language 10, responsible design 10 (uncertainty, audit trail, guardrails), scalability 5.
- The scoring script and dev key are NOT in our starter folder and will not be shared (organizers confirmed). We build our own proxy in `eval/`.

## Hard rules (all workers)
1. Extraction must be AUTOMATED from the corpus text. Never hand-type a rule into `outputs/`. Rule records come from LLM reading source text (prompts in `prompts/`), then deterministic validation.
2. `quoted_span` must be copied verbatim from a corpus doc. Prefer a span that sits on ONE line of the source text (no newline inside), 20 to 300 chars. If a sentence wraps across lines and you need it whole, replace each newline+indent by a single space and keep everything else identical. Run `python3 -m navigator.validate` before you hand back.
3. Do not invent rules, citations, dates or numbers that the text does not support. Unsure => lower `confidence`, say so in `conflict_note`, or use `unknown`.
4. Every user-facing surface says "Not legal advice".
5. No customer/resident/pricing/non-public data. No bulk scraping. Gap-fill fetches are single-page reads of specific public URLs only (<= 15 pages in total), recorded in `data/corpus_extra/manifest.csv`.
6. Privacy: never write the author's personal email or school names anywhere (files, README, git). Git identity is already set to a noreply address in this repo; do not change it. No `Co-Authored-By` lines. Do not run `git push`, do not create remotes, do not publish anything.
7. No en or em dashes in any text you write (use commas, colons, "to").
8. Stay inside your ownership (table below). Never edit another worker's files; ask the orchestrator through your final report.

## Layout
```
data/corpus/text/Dxxx.txt          supplied corpus (54 docs), header: SOURCE:, RETRIEVED:
data/corpus/corpus_manifest.csv    87 docs (33 link-only)
data/corpus_extra/text/Xnnn.txt    gap-fill docs (same header format) + manifest.csv
data/sample_addresses.csv          500 addresses (address_id, street_address, postal_city, state, zip, year_built, units, use_code, use_description, ...)
data/schema/rule_record.schema.json  official rule schema
data/dev/change_tests.json         T1..T5 official definitions
work/extract/<doc_id>.json         stage 1: per-document candidate rules
work/consolidate/<STATE>.json      stage 2: canonical rules + no_rule findings per cell
work/jurisdictions.json            geocode results per address_id
outputs/rules.json                 SUBMISSION: {"rules":[...]} strict official fields only
outputs/rules_engine.json          superset with machine fields (applies_if, exempt_if, yields_to, conflicts_with, no_rule)
outputs/lookups.json               SUBMISSION: {"as_of","lookups":{address_id:[{team_rule_id,result,explanation,conflict_flag}]}}
outputs/lookups_detail.json        UI superset: facts, stack, citations, quoted spans, confidence, es text, timeline per rule
outputs/changes.json               SUBMISSION: {test_id:{affected_address_ids,conflict_flag_address_ids,notes}}
outputs/audit/                     append-only logs (jsonl): llm calls, decisions, validation reports
navigator/                         python package (stdlib only; python 3.12+)
eval/                              proxy key + proxy scorer
web/                               static live demo (reads outputs/*.json, no build step)
```

## Rule record (stage 1 / stage 2 output)
Official fields exactly as `data/schema/rule_record.schema.json` (team_rule_id, jurisdiction, level, category, status, title, requirement, key_value, coverage_conditions, exemptions, overrides, interaction, effective_date, citation, source_doc_id, source_url, quoted_span, confidence, conflict_flag, conflict_note).
- jurisdiction: `CA` | `NJ` | `MA` or `City, ST` with these exact strings: `Los Angeles, CA`, `San Francisco, CA`, `San Diego, CA`, `Berkeley, CA`, `Santa Ana, CA`, `Jersey City, NJ`, `Hoboken, NJ`, `Newark, NJ`, `Boston, MA`, `Cambridge, MA`.
- category enum: rent_increase_limits | just_cause_eviction | security_deposits | application_screening_fees | screening_restrictions | algorithmic_rent_setting.
- status as of 2026-10-01: in_force | not_yet_effective (enacted, effective later) | pending (bill) | failed (struck/defeated).
- effective_date: ISO `yyyy-mm-dd` (or `yyyy-mm`, `yyyy`) of the version currently operative or, for not_yet_effective, the future date; null when the text gives none. Never guess.
- key_value: headline number/formula ("5% + CPI, max 10%", "1.5 months' rent", "$50 cap").
- citation formats (match these): `Cal. Civ. Code § 1947.12`, `Cal. Gov. Code § 12955`, `N.J.S.A. 46:8-21.2`, `P.L.2025, c.405`, `M.G.L. c.186 § 15B`, `M.G.L. c.40P § 4`, `S.F. Admin. Code ch. 37`, `S.F. Admin. Code § 37.10C`, `L.A.M.C. § 151.00 et seq.`, `S.D.M.C. §§ 98.1101 to 98.1104`, `Berkeley Mun. Code ch. 13.63`, `Jersey City Code § 218-12`, `Hoboken Code ch. 158, art. II`. Use the instrument's own official cite, not a web page title.

Engine-only extension fields (in `outputs/rules_engine.json` and stage files; stripped from `outputs/rules.json`):
- `applies_if`: Pred or null (null = every residential rental in the jurisdiction). `exempt_if`: Pred or null.
- `yields_to`: list of `{"jurisdiction":..., "category":...}` descriptors (rules at another level that, when they apply to an address, take precedence over this one: result becomes `superseded`). `conflicts_with`: same descriptor list (possible preemption/conflict, human review flag).
- `no_rule` findings (stage 2 only): `{"jurisdiction","category","finding":"no_rule_at_this_level","evidence_doc_id","note"}`.

### Pred grammar (3-valued: TRUE / FALSE / UNKNOWN)
`{"all":[Pred...]}` `{"any":[Pred...]}` `{"not":Pred}` or a leaf:
- `{"fact":"units","op":">=","value":5}` ops `>= > <= < == !=`; numeric facts: `units`, `year_built`, `building_age_years` (= as_of year minus year_built).
- `{"fact":"co_date","op":"<=","value":"1979-06-13"}`: certificate-of-occupancy / first-occupancy date. Engine proxies it with `year_built`; building year < cutoff year => TRUE, > cutoff year => FALSE, == cutoff year => UNKNOWN. Use it whenever the law keys on certificate of occupancy or first occupancy, and `year_built` only when the law says "built"/"constructed".
- `{"unavailable":"owner-occupied building with 2 or fewer units"}`: any fact the data does not contain (owner type, owner occupancy, rent level, tenancy length, affordable restriction, single-family, etc.). Always UNKNOWN.
Result rule: rule applies iff `applies_if` TRUE and `exempt_if` FALSE (or null); `exempt_if` TRUE => omitted; any UNKNOWN left => `unknown`.

## Result values (lookups)
`applies` | `unknown` | `superseded` | `not_yet_effective` | `pending`. Failed rules and non-covered rules are omitted. "unknown" when a needed fact is missing or the cutoff year equals the building year.

## Ownership
| Worker | Owns |
|---|---|
| orchestrator | CONTRACTS.md, HANDOFF.md, prompts/, navigator/common.py, navigator/validate.py, final integration |
| X1..X7 extractors | `work/extract/<their doc ids>.json` only |
| G gap-fill | `data/corpus_extra/**` only |
| R resolver | `navigator/resolve.py`, `work/jurisdictions.json`, `tests/test_resolve.py`, `docs/resolve_notes.md` |
| E engine | `navigator/apply.py`, `navigator/changes.py`, `navigator/explain.py`, `navigator/pipeline.py`, `tests/test_apply.py`, outputs/lookups*.json, outputs/changes.json |
| V eval | `eval/**`, `tests/test_eval.py` |
| U web | `web/**` |
| consolidators | `work/consolidate/**`, `outputs/rules_engine.json`, `outputs/rules.json` |

Run checks from the repo root: `python3 -m navigator.validate --extract work/extract` etc.

## outputs/lookups_detail.json (UI contract; produced by `python3 -m navigator.pipeline build`)
```json
{"generated_at":"ISO","as_of_default":"2026-10-01","not_legal_advice":"Not legal advice. ...",
 "rules":{"r-0001":{ /* official rule fields + key_value, effective_date, status, citation, quoted_span, source_doc_id, source_url, retrieved_at (from manifest), applies_if, exempt_if, yields_to, conflicts_with, category, jurisdiction, level */ }},
 "addresses":{"A0001":{
   "street_address":"...","postal_city":"...","state":"CA","zip":"90028",
   "facts":{"year_built":1927,"units":32,"units_source":"assessor","use_code":"0500","use_description":"Five or more apartments"},
   "stack":{"state":"CA","county":"Los Angeles County","city":"Los Angeles, CA","geocode_status":"exact","matched_address":"...","lat":34.09,"lon":-118.32,"notes":null},
   "results":[{"team_rule_id":"r-0001","category":"rent_increase_limits",
      "timeline":[{"from":"0000-01-01","result":"not_yet_effective","explanation":"...","explanation_es":"..."},{"from":"2026-01-01","result":"applies","explanation":"...","explanation_es":"..."}],
      "conflict_flag":false,"conflict_note":null,"confidence":0.8,"facts_used":["units"],"missing_facts":["year_built"]}]}},
 "tests":{"T1":{"title":"...","type":"as_of","as_of_before":"2025-12-31","as_of_after":"2026-01-02","affected_address_ids":[],"conflict_flag_address_ids":[],"notes":"...","expected_behavior":"..."}},
 "no_rule":[{"jurisdiction":"NJ","category":"rent_increase_limits","finding":"no_rule_at_this_level","evidence_doc_id":"D067","note":"..."}],"gaps":[{"jurisdiction":"Hoboken, NJ","category":"just_cause_eviction","checked":["X001"],"note":"..."}],
 "audit":{"sources":[{"doc_id":"D024","url":"...","retrieved_at":"...","sha256":"..."}],"runs":[{"ts":"...","stage":"extract","actor":"...","detail":"..."}],"validation":{"rules":"ok","quotes_found":"58/58"}}}
```
The `timeline` lists change points sorted ascending; an entry is valid from its `from` date (inclusive) until the next entry. Query-date result = last entry with `from <= date`. Rules that never apply to the address are absent. Timeline `explanation`/`explanation_es` hold ONLY the address-specific reasoning (why this result, what is missing, conflict note); the UI shows them under the rule's own `title`/`title_es`, `requirement`/`requirement_es` and `key_value`/`key_value_es` from `rules[rid]`, and the citation and notice from the Source block and the page banner. They are date-agnostic: they contain the token `{ASOF}` where the as-of date belongs, and the UI MUST replace it with the date the user selected (the official outputs/lookups.json already has the real date 2026-10-01). Entries before 2000-01-01 that are followed by later entries carry a short placeholder text. A timeline entry may carry result `not_covered` (the rule stops covering the address from that date, e.g. an age-based exemption starts to apply): the UI must treat it as 'rule not shown'. The UI does no legal logic: it only reads this file.
