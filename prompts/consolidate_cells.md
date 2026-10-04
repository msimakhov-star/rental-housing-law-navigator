# Stage 2: consolidate candidates into canonical rule records per cell

You consolidate the stage-1 candidates (`work/extract/*.json`) for ONE state group (CA, NJ or MA: the state itself plus its in-scope cities) into the final rule records. Read `CONTRACTS.md` and `prompts/extract_doc.md` first (record fields, predicate grammar, citation formats, hard rules).

Group membership is given in your task message (groups: CA1 = `CA`, Los Angeles, San Diego, Santa Ana; CA2 = San Francisco, Berkeley; NJ = `NJ`, Jersey City, Hoboken, Newark; MA = `MA`, Boston, Cambridge). Your cells are the 6 categories x the jurisdictions of your group. Other groups handle the other jurisdictions; a descriptor in `yields_to`/`conflicts_with` may point at a cell of another group (the merge script prunes descriptors that end up pointing at cells with no rule). Candidates for state-level rules that merely mention your cities belong to the group of the jurisdiction in their `jurisdiction` field.

## Inputs
- All candidate files `work/extract/*.json` (D... = supplied corpus, X... = gap-fill pages fetched from public sources, see `data/corpus_extra/manifest.csv`): use the ones whose rules belong to your group.
- The source texts themselves: `data/corpus/text/Dxxx.txt`, `data/corpus_extra/text/Xnnn.txt`. Open the source before you trust or change any field.
- Organizer-supplied facts that count as evidence: `data/dev/change_tests.json` (T1..T5: effective dates, enacted/pending/failed status of AB 325/SB 763, the Hoboken and Jersey City local bans, the NJ FAIR Act, the two MA bills, the struck MA ballot question), `docs/challenge_brief.txt` (examples of rules per category and their effective dates), `docs/participant_guide.txt` section 9 (known open questions).

## Decide, per cell
For every (jurisdiction, category) cell in your group choose ONE of:
1. One or more canonical rule records (usually one; two only when two distinct legal instruments genuinely govern that cell, e.g. two pending bills, or a statute plus a separate broker-fee statute).
2. A `no_rule` finding: the sources positively show or strongly imply that this level has no rule in that category (e.g. NJ has no statewide rent cap; Massachusetts bars local rent control so Boston and Cambridge have no local rent cap; a city page that says nothing about a category is NOT enough: say `no_rule` only with a reason, otherwise record it under `gaps`).
3. A gap: no evidence in any available source; list under `gaps` with the doc ids you checked. Do not invent a rule to fill a gap.

## Rules for canonical records
- Merge duplicates and overlapping candidates for the same instrument (same cite, same cell): keep the best primary-source text for `key_value`, `effective_date`; lower `confidence` when only a secondary page supports it; keep every supporting doc id in `interaction` or a note if useful. `source_doc_id`/`source_url` must be the doc whose text contains the `quoted_span`.
- CITATION METRIC (organizer ruling): only SUPPLIED corpus docs (`D...`) count for citations; gap-fill docs (`X...`) do not. So whenever any supplied D doc contains text that supports the rule (even a secondary web page), take `source_doc_id`, `source_url` and `quoted_span` from that D doc, and use X docs only to fill facts the D docs lack (effective date, status, official cite, coverage details); say so in `interaction`. Only when no D doc supports the rule at all, use an X doc as the source (the rule still counts for extraction and address coverage); mention `supplemental source` in `interaction`. Example: San Diego's algorithmic ban: quote D076 (supplied draft ordinance text) for the content, take status in_force and effective 2025-06-21 from X015 (codified text) and the brief.
- Re-verify every field against the source: status, effective_date (operative version), key_value, coverage_conditions, exemptions, citation format. Fix what is wrong. Do not guess dates.
- Effective-date policy: the date in the text wins. If a state statute's text carries no effective date but its enactment is documented, you may apply the constitutional default only when you can state the rule precisely (California regular-session statutes without urgency clause take effect January 1 of the following year, Cal. Const. art. IV s.8(c)(1)); mark it in `interaction`, cap `confidence` at 0.85, and cross-check against the organizer test definitions in data/dev/change_tests.json, which are authoritative for T1 to T5 facts. When two sources disagree (e.g. Berkeley ch. 13.63: ordinance text 2026-03-01 vs a law-firm alert January 2026; LA RSO formula 2026-02-02 vs 2026-01-24), keep the primary-source value, set `conflict_flag` true and describe both in `conflict_note`.
- `status` as of 2026-10-01 (in_force, not_yet_effective, pending, failed). A rule that was struck or defeated is `failed` (record it: it is evidence that nothing applies). Check that bills are not recorded as in force.
- `yields_to` and `conflicts_with`: use descriptors `{"jurisdiction","category"}` that point at cells that actually have a record in YOUR output or in another group's likely output (CA state rent cap and just cause yield to local rent control and local just-cause rules where those exist; NJ FAIR Act conflicts_with the Jersey City and Hoboken algorithmic rules). Prune descriptors that point at cells with no rule. Do not point a local rule at the state rule unless the text says the local rule defers.
- Predicates (`applies_if`, `exempt_if`): re-check each against the text. Keep the style from `prompts/extract_doc.md` (real leaves for units/year_built/co_date/building_age_years, `unavailable` only for facts the data lacks, exemptions as conjunctions so a 20-unit building resolves correctly). Remember the data: most addresses are multifamily; units may be missing; year_built may be missing.
- Citation format: one official cite per record in the CONTRACTS formats. For AB 325 / SB 763 use `Cal. Bus. & Prof. Code § 16729 (AB 325; SB 763)`. Keep `title` as the instrument's common name.
- `team_rule_id`: use temporary ids `<GROUP>-NN` (e.g. `CA-01`); the merge script renumbers globally. Rules must keep all official fields; every `quoted_span` must be verbatim from the source (run the validator).
- Consistency with the brief's list of real examples (docs/challenge_brief.txt, 'Rule categories, with real examples from the corpus'): for each example in your group, either find it in the candidates/sources or list it under `missing_expected` with what you checked (the answer key was built from public sources and may be richer than the supplied corpus; never fabricate to match).

## Output
Write `work/consolidate/<GROUP>.json`:
```json
{"group":"CA","consolidator_model":"<your model>","consolidated_at":"<ISO UTC>",
 "rules":[ {full record incl. team_rule_id, applies_if, exempt_if, yields_to, conflicts_with, overrides, interaction} ],
 "no_rule":[ {"jurisdiction":"NJ","category":"rent_increase_limits","finding":"no_rule_at_this_level","evidence_doc_id":"D067","note":"..."} ],
 "gaps":[ {"jurisdiction":"Hoboken, NJ","category":"just_cause_eviction","checked":["X003"],"note":"..."} ],
 "missing_expected":[ ... ],
 "decisions":[ "one line per non-obvious call: merged D016 into D027 because ...", ... ]}
```
Every cell of your group must appear exactly once across `rules` (with that jurisdiction+category), `no_rule` or `gaps`.
Then run `cd . && python3 -m navigator.validate --rules work/consolidate/<GROUP>.json` (it accepts {"rules":[...]}), fix all errors, and report in max 12 lines: counts (rules, no_rule, gaps), the list of records (jurisdiction / category / citation / status / effective_date), the conflicts you flagged, and the gaps that someone should try to close.
