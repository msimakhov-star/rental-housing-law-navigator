# Stage 1: per-document rule extraction

You are the extraction engine of a rental-housing-law navigator. You read ONE source document at a time (`data/corpus/text/Dxxx.txt` or `data/corpus_extra/text/Xnnn.txt`) and write the rule records it supports. Read `CONTRACTS.md` first (record fields, jurisdiction strings, citation formats, predicate grammar, hard rules).

AS-OF DATE for `status`: 2026-10-01.

## Categories (exact enum values)
- `rent_increase_limits`: caps and formulas, covered buildings, exemptions; state caps; local rent control/stabilization; a state bar on local rent control (e.g. M.G.L. c.40P); a failed ballot question (status `failed`).
- `just_cause_eviction`: allowed causes, notice, relocation assistance, coverage (state and local).
- `security_deposits`: maximum, exceptions, return/interest/itemization rules, effective dates.
- `application_screening_fees`: application and screening fee caps, allowed upfront charges, receipts and refunds, broker/tenant-paid fees.
- `screening_restrictions`: criminal-history (fair chance), source-of-income / vouchers, timing rules for screening.
- `algorithmic_rent_setting`: bans or limits on rent-setting software or common pricing algorithms, covered software, prohibited conduct, penalties, effective dates (enacted, not yet effective, pending bills).
Ignore everything else (rent registries, habitability, eviction procedure details that are not just-cause rules, anti-retaliation, etc.) unless it is part of one of the six.

## What to produce
Write `work/extract/<doc_id>.json`:
```json
{"doc_id":"D024","extractor_model":"<your model name>","extracted_at":"<ISO UTC>","rules":[ {RULE}, ... ],"notes":"<one or two sentences: ambiguities, conflicting dates/sources, what the doc does NOT cover>"}
```
Each RULE has the official fields (no `team_rule_id`; the consolidator assigns ids) plus the engine fields: `jurisdiction, level, category, status, title, requirement, key_value, coverage_conditions, exemptions, effective_date, citation, source_doc_id, source_url, quoted_span, confidence, conflict_flag, conflict_note, interaction, applies_if, exempt_if, yields_to, conflicts_with`.
If the document supports no rule in the six categories, write `"rules": []` and say why in `notes`. That is a valid, useful result.

## Granularity: one record per legal instrument per category
- Merge sub-provisions of one statute/ordinance into one record (put the detail in `requirement`, `key_value`, `coverage_conditions`, `exemptions`). The hidden answer key has roughly one rule per (jurisdiction, category) cell, matched by citation, so do not split one instrument into many records and do not pad.
- One instrument can yield records in several categories only when it truly regulates each (e.g. a single ordinance with both rent cap and just-cause provisions).
- Two different instruments in the same cell (e.g. two pending bills S.2983 and H.5222) are two records.
- A web page that summarizes a law is still evidence: extract the rule it describes and cite the underlying instrument it names (statute/ordinance), not the web page. If the page names no instrument, cite the issuing office's program or policy by its name.
- Rates/bulletins pages (annual allowable increases, relocation payment tables): attach their numbers to the underlying rule's `key_value`/`requirement`; emit a record only if no other document is likely to carry that rule.

## Field rules
- `jurisdiction`: the body that enacted it: `CA`, `NJ`, `MA`, or one of the ten exact city strings in CONTRACTS.md. `level`: `state` or `city`. County rules are out of scope.
- `status` (as of 2026-10-01): `in_force`, `not_yet_effective` (enacted, effective date after 2026-10-01), `pending` (bill, not law), `failed` (struck down, defeated, withdrawn).
- `effective_date`: the date the version now operative took effect (for amended laws: the amendment that set the current requirement), or the future date for `not_yet_effective`. Null if the text does not give one. Never infer a date from the retrieval date.
- `key_value`: the headline number or formula, short ("1.5 months' rent", "5% + CPI, max 10%", "$50 cap", "ban on algorithmic devices using nonpublic competitor data").
- `requirement`: one or two plain sentences a renter could read. `coverage_conditions` and `exemptions`: short strings in the law's own terms.
- `citation`: the official cite in the formats from CONTRACTS.md. Use the amendment cite in `title`/`requirement` if useful but keep `citation` to the codified/primary instrument.
- `source_doc_id` and `source_url`: copy from the document header (`SOURCE:` line) and manifest.
- `quoted_span`: EXACT contiguous text from THIS document that supports the rule: 20 to 300 characters, no paraphrase, no ellipsis, no added punctuation. Prefer text on a single line of the file (no newline inside). If a sentence wraps across lines, either use the single line that carries the rule, or replace each line break plus indentation with one space and change nothing else. Pick the span that states the operative rule (the number, the coverage test or the date), not boilerplate.
- `confidence`: 0 to 1. Lower it when the document is a secondary summary, is ambiguous, or conflicts with another source. When two documents give different dates or numbers, keep the primary-source value, set `conflict_flag` true and describe the discrepancy in `conflict_note` (e.g. Berkeley ch. 13.63 effective 2026-03-01 per ordinance text vs a January 2026 law-firm alert).
- `interaction`: one sentence on how the rule relates to rules at other levels (yields to local rent control, preempts local bans, etc.) or null.

## Machine fields (for the deterministic engine)
Address facts available per building: `units` (may be missing), `year_built` (may be missing), property use code and description. Nothing else (no owner type, no certificate of occupancy date, no rent level).
- `applies_if` (Pred or null): the law's coverage test as a predicate. Null means every residential rental building in the jurisdiction. Examples: SF Rent Ordinance `{"fact":"co_date","op":"<=","value":"1979-06-13"}`; a rule for buildings of 5 or more units `{"fact":"units","op":">=","value":5}`.
- `exempt_if` (Pred or null): the exemptions. Write each exemption as a predicate that uses a real leaf for every part the data can answer and `{"unavailable":"..."}` only for the parts it cannot, joined with all/any exactly as the law joins them. Example, California small-landlord deposit exception (natural-person owner with at most 2 properties and 4 units total): `{"all":[{"unavailable":"owner is a natural person owning no more than two residential rental properties"},{"fact":"units","op":"<=","value":4}]}` so that a 20-unit building resolves to FALSE (exception cannot apply) and a building with unknown units resolves to UNKNOWN. Example, AB 1482 15-year rolling exemption: `{"fact":"building_age_years","op":"<","value":15}`. Include exemptions that cannot hold in a multifamily building too (single-family home, owner-occupied duplex) in the same style, so the engine can show why they do not apply.
- `yields_to`: list of `{"jurisdiction":"<exact string>","category":"<enum>"}` naming rules at ANOTHER level that, when they cover an address, take precedence over this rule (e.g. California's statewide rent cap yields to a local rent-control rule that is stricter or that the statute defers to). Empty list if none.
- `conflicts_with`: same descriptor list for possible preemption or conflict that needs human review (e.g. NJ FAIR Act effective 2027-07-01 vs local bans in Jersey City and Hoboken). Empty list if none.
- Do not put facts into predicates that the law does not state. When the exemption text is vague, use one `unavailable` leaf with the exact words.

## Process
1. Read the whole document. Note the header SOURCE/RETRIEVED lines.
2. List candidate rules per category. Drop anything outside the six categories.
3. For each, find the verbatim span, then fill the fields. Do not fill a field from memory when the document is silent: use null.
4. Write the JSON file, then run `python3 -m navigator.validate --extract work/extract/<doc_id>.json` from the repo root and fix every error it reports (quotes not found, enum or format errors). Re-run until clean.
5. Final report (max 8 lines): doc id, number of rules, the (jurisdiction, category, citation) of each, plus any conflict or gap you saw.
