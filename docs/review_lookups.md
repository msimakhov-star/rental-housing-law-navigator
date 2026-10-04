# Review R2: address lookups and change tests (as of 2026-10-01)

## Method
- Independent evaluator `work/review/audit.py` (no navigator import) re-derives every rule for all 500 addresses from `outputs/rules_engine.json`, `work/address_facts.json`, `work/jurisdictions.json`, using Kleene logic per CONTRACTS.md.
- Policy applied: exact assessor `units` only (`units_min` ignored); co_date and age at the boundary year are UNKNOWN; failed rules omitted; a state rule whose local rule (yields_to) applies is `superseded`, and is `unknown` when that local rule is unknown.
- 45-address stratified sample (5 per legal city), traced rule by rule in `work/review/sample.py`: SF A0106 A0115 A0384 A0105 A0081; LA A0445 A0107 A0022 A0235 A0437; SD A0346 A0322 A0019 A0094 A0497; Berkeley A0005 A0018 A0025 A0091 A0470; Hoboken A0002 A0168 A0227 A0489 A0040; JC A0008 A0012 A0026 A0116 A0017; Newark A0331 A0352 A0003 A0011 A0013; Boston A0098 A0217 A0194 A0036 A0006; Cambridge A0009 A0230 A0199 A0336 A0015.
- Hard cases covered: SF pre-1979 (A0115, A0384) and post-1979 (A0081 age 21, A0105 age 7); LA 1977 (A0445), 1978 (A0107), post-1978 (A0437 age 22, A0022 age 14); missing year_built (A0106, A0235, all SD, Berkeley); missing units (all NJ, Berkeley, Boston); non-exact geocode (A0009, A0115, A0168, A0384, A0346, A0098).
- Not present in the sample data: no SF building built in 1979, no CA building built in 2011 (age exactly 15) or 2021 (age 5). The engine's age-boundary handling is therefore untested by data; toggling it changes 0 cells.
- T1 to T5 recomputed in `work/review/changes_check.py` (T3 at 2026-10-01 vs 2027-07-02).

## Results
- Sample: 2 mismatches in 45 addresses (A0106, A0235, both r-0002). Full 500: 8 mismatches, all the same pattern. Every other rule distribution matches exactly.
- changes.json: T1 250 (all CA), T2 90 (Hoboken 40 + JC 50, no Newark), T3 140 NJ with 90 conflict flags (exactly Hoboken + JC), T4 110 (all MA), T5 empty. All five sets match my computation and the spec. No duplicate ids.
- lookups.json hygiene: 500 addresses, results only from the enum, no duplicate rule per address, every explanation says "Not legal advice".

## Mismatch table
| address_id | rule | expected (mine) | got | reason |
|---|---|---|---|---|
| A0106 (SF), A0257 (SF) | r-0002 | superseded | unknown | year_built missing: state age exemption unknown, SF r-0026 applies (applies_if null) |
| A0200, A0235, A0267, A0285, A0353, A0417 (LA) | r-0002 | superseded | unknown | same; LA r-0022 applies |

Either answer means "the state rule does not govern here". CONTRACTS.md says superseded when the local rule applies; the engine keeps the rule's own unknown. Low impact (about 2 cells in the hidden 100).

## Semantic risks (ranked by expected score impact; hidden cells = 20 percent of the 500)
1. **units_min ignored: 981 unknown cells (about 196 hidden).** `units` is null for 243 addresses. Every small-building exemption is "unavailable AND units <= 1..4", so for buildings that are 5+ by use-code class it would be FALSE truthfully. NJ class 4C means a dwelling for more than four families (N.J.A.C. 18:12-2.2, checked on Cornell LII). Using `units_min` would resolve NJ r-0007 to r-0011 (700), Newark r-0047 (50), JC r-0042 (28), Berkeley r-0005/34/35/37 (160) plus r-0002 to superseded (40), LA r-0005 (3). Keep A0227 unknown (assessor 2 vs class 4C). Note: `docs/engine_notes.md` says units_min IS used where the bound decides; the outputs do not use it (doc drift, or the brief's policy overrides it).
2. **State rule `superseded` vs key `applies`: 265 cells (about 53).** r-0002 superseded 147, r-0001 superseded 118. Legally defensible (local just cause / local rent control takes precedence), but if the key lists both levels as applies, superseded could be scored as a missed applies (2x).
3. **Rules that only ever return unknown because applies_if is one unavailable leaf: 140 cells (about 28).** r-0028 SF Fair Chance (80), r-0049 Boston DND policy (60). This is truthful and no shorter encoding resolves it. It is a partial error if the key omits them for market-rate buildings.
4. **r-0013 MA c.40P is `applies` in rent_increase_limits for all 110 MA addresses (about 22).** If the key treats MA rent as no_rule (T5 says no rent cap is reported), these are false positives. If the key has 40P as a rule, omitting it costs 2x. Keep it.
5. **Missing year_built (data gap, not encoding).** SD: year is null for all 50 addresses, so r-0001, r-0002 and r-0030 are unknown for 100 percent of them. Newark r-0046 is unknown for 96 percent (48/50). Hoboken r-0044 is unknown for 100 percent. It has a catch-all "155-2 not captured" leaf, and X001 holds only the 155-2 heading. Dropping that leaf resolves 0, because all 4 Hoboken rows with a year are under 30 years old. JC r-0042 keeps 22 unknown even with units_min. The fix is assessor year_built data (not checked whether the SD and NJ MOD-IV sources carry it).
6. **The 8 r-0002 cells above (about 2).**
7. **Timeline uses version dates.** r-0001 (2024-04-01), r-0002 (2026-01-01), r-0004 (2026-01-01) and r-0021 (2026-02-02) show not_yet_effective before those dates, though earlier versions were in force (AB 1482 since 2020, RSO since 1979). No effect at 2026-10-01 or on T1 (r-0006 only). It is visible in the demo's as-of view.
8. Minor: A0009 stack county is Suffolk, but the legal city is Cambridge (the source is the Cambridge property database, so the city is right). Berkeley r-0033 uses year_built < 1980, not co_date (0 cells, no Berkeley year known). Lookups carry conflict_flag on r-0021 (55) and r-0038 (40) from rule-level date conflicts; not scored, but it may confuse readers.

## Rules unknown for more than 90 percent of in-scope addresses
| rule | unknown/in scope | driving fact | does units_min or a shorter encoding fix it? |
|---|---|---|---|
| r-0007, r-0008, r-0009, r-0010, r-0011 (NJ) | 140/140 each | units | yes, all 140 |
| r-0047 Newark | 50/50 | units | yes, 50 |
| r-0042 JC | 50/50 | units, then year_built | 28 via units_min; 22 need year |
| r-0034, r-0035, r-0037 Berkeley | 40/40 each | units | yes, 40 each |
| r-0033 Berkeley | 40/40 | year_built (and units) | no |
| r-0030 San Diego | 50/50 | year_built | no |
| r-0044 Hoboken | 40/40 | unavailable catch-all + year_built | no |
| r-0046 Newark | 48/50 | year_built | no |
| r-0028 SF, r-0049 Boston | 80/80, 60/60 | unavailable only (program housing) | no (by design) |

## Per-rule distribution over 500 addresses (mine; matches lookups.json except r-0002: got superseded 147 / unknown 98)
| rule | jur | applies | unknown | superseded | nye | pending | omitted |
|---|---|---|---|---|---|---|---|
| r-0001 | CA | 27 | 100 | 118 | 0 | 0 | 255 |
| r-0002 | CA | 0 | 90 | 155 | 0 | 0 | 255 |
| r-0003, r-0004, r-0006 | CA | 250 | 0 | 0 | 0 | 0 | 250 |
| r-0005 | CA | 207 | 43 | 0 | 0 | 0 | 250 |
| r-0007 to r-0011 | NJ | 0 | 140 | 0 | 0 | 0 | 360 |
| r-0012 | NJ | 0 | 0 | 0 | 140 | 0 | 360 |
| r-0013, r-0015 to r-0018 | MA | 110 | 0 | 0 | 0 | 0 | 390 |
| r-0014 (failed) | MA | 0 | 0 | 0 | 0 | 0 | 500 |
| r-0019, r-0020 | MA | 0 | 0 | 0 | 0 | 110 | 390 |
| r-0021, r-0023 | LA | 47 | 8 | 0 | 0 | 0 | 445 |
| r-0022, r-0024 | LA | 80 | 0 | 0 | 0 | 0 | 420 |
| r-0025 | SF | 71 | 2 | 0 | 0 | 0 | 427 |
| r-0026, r-0027, r-0029 | SF | 80 | 0 | 0 | 0 | 0 | 420 |
| r-0028 | SF | 0 | 80 | 0 | 0 | 0 | 420 |
| r-0030 | SD | 0 | 50 | 0 | 0 | 0 | 450 |
| r-0031, r-0032 | SD | 50 | 0 | 0 | 0 | 0 | 450 |
| r-0033, r-0034, r-0035, r-0037 | Berkeley | 0 | 40 | 0 | 0 | 0 | 460 |
| r-0036, r-0038 | Berkeley | 40 | 0 | 0 | 0 | 0 | 460 |
| r-0039 to r-0041 | Santa Ana | 0 | 0 | 0 | 0 | 0 | 500 (no sample address) |
| r-0042 | JC | 0 | 50 | 0 | 0 | 0 | 450 |
| r-0043 | JC | 50 | 0 | 0 | 0 | 0 | 450 |
| r-0044 | Hoboken | 0 | 40 | 0 | 0 | 0 | 460 |
| r-0045 | Hoboken | 40 | 0 | 0 | 0 | 0 | 460 |
| r-0046 | Newark | 2 | 48 | 0 | 0 | 0 | 450 |
| r-0047 | Newark | 0 | 50 | 0 | 0 | 0 | 450 |
| r-0048 | Boston | 60 | 0 | 0 | 0 | 0 | 440 |
| r-0049 | Boston | 0 | 60 | 0 | 0 | 0 | 440 |
| r-0050 | Cambridge | 50 | 0 | 0 | 0 | 0 | 450 |

Not legal advice. Reproduce: `python3 work/review/audit.py && python3 work/review/changes_check.py && python3 work/review/write_findings.py`.
