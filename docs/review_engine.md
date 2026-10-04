# Engine review (R3)

Tests: `python3 -m unittest tests.test_review_engine` (41 tests, about 3 s). The 9 `test_BUG_*` tests fail on purpose; the other 32 pass.
I checked every fix below in a scratch copy (since deleted): all 41 tests pass except the ones that need fresh outputs (outputs must be rebuilt), tests.test_apply still passes, and a rebuild changes exactly 8 lookups (r-0002 goes from unknown to superseded). T3 stays at 90.

## Bugs (file:line as of 02:18 snapshot)
1. HIGH, `navigator/pipeline.py:114`: the placeholder "Before the earliest period" is used for any point before 2000 that is not the last one, even when that point is still in effect years later. Real data: 140 NJ timelines for r-0012 (the FAIR Act, which is the T3 demo) show the placeholder as the 2026-10-01 entry. Test: `test_BUG_timeline_entry_valid_at_asof_is_not_placeholder`.
   ```python
   if i < len(pts) - 1 and pts[i + 1][0] <= "2000-01-01":
   ```
2. MEDIUM, `navigator/apply.py:175`: precedence only runs for a yielding rule whose raw result is `applies`. When the state rule is `unknown` and the local rule it yields to is `applies`, the state rule stays `unknown` when it should be `superseded`. Real data: r-0002 (CA just cause) vs r-0022 (LA JCO) at 6 addresses and vs r-0026 (SF) at 2 (A0106, A0200, A0235, A0257, A0267, A0285, A0353, A0417). Test: `test_BUG_unknown_yielder_with_applying_target`.
3. MEDIUM (latent), `navigator/apply.py:177`: `status == "in_force"` drops a target with status `not_yet_effective` even after its date has passed (timeline after 2027-07-01, or any query date after the effective date). The filter adds nothing, because raw `applies` already means the rule is active. Test: `test_BUG_target_with_status_nye_whose_date_has_passed`. Fix for 2 and 3:
   ```python
   if raw[rid] not in ("applies", "unknown") or not r.get("yields_to"): continue
   cands = [o for o in out if o != rid and _matches(rules[o], r["yields_to"])]
   ...
   elif unk and raw[rid] == "applies":   # keep the unknown_precedence branch
   ```
4. MEDIUM (latent), `navigator/changes.py:49`: T3 conflict ids count any `conflict_flag` and ignore `conflict_with`. If anyone sets the rule-level `conflict_flag` on r-0012 (an easy thing to do for "possible preemption"), all 140 NJ addresses get flagged, Newark included. Test: `test_BUG_t3_rule_level_flag_floods_conflict_ids`.
   ```python
   cw = set(resolve_all(t["conflict_with"], rules.values()))
   conf = [x for x in aids if any(cw & set(((eng.at(x, a).get(r) or {}).get("reason") or {}).get("conflicts", [])) for r in rids)]
   ```
5. LOW, `navigator/apply.py:69` + `explain.py:12`: when `year_built` is missing, a co_date rule reports the missing fact as "co_date", and the text then says "we only have the year built, and it is not decisive", which is false. Real data: 14 lookups explanations. Test: `test_BUG_co_date_text_when_year_missing`. Fix: `return U, set(), ["year_built"]` for both facts.
6. LOW (no failed geocodes today), `navigator/apply.py:141`: when the scope is unknown the engine skips applies_if/exempt_if, so a rule the facts rule out still shows as `unknown`. Kleene AND(U, F) = F. Test: `test_BUG_failed_geocode_ignores_facts`.
   ```python
   cov = k_and([a, k_not(x)] + ([U] if sc == "unknown" else []))   # evaluate facts always; prepend "legal_city" to miss
   ```
7. LOW (latent), `navigator/explain.py:107`: with TRUST_UNITS_MIN=True and a bound that is not enough to decide, the text says "we do not rely on it". Fix: add `and not apply.TRUST_UNITS_MIN` to the condition. Test: `test_BUG_units_min_text_false_when_trusted`.
8. LOW, `navigator/merge_rules.py:22`: the sort key has no tie-breaker, so ids for rules in the same cell with the same date depend on the consolidator's list order. Real ties: r-0016/r-0017 (MA, 2025-08-01) and r-0015 (same date, different cell). Test: `test_BUG_ids_depend_on_input_order`. Fix: add `r.get("citation") or "", r.get("title") or ""` to the key. Note: this renumbers the current outputs once.
9. LOW, `navigator/merge_rules.py:31`: an `overrides` id that is not in idmap is kept verbatim and ends up dangling in rules.json. Fix: `[idmap[x] for x in r.get("overrides") or [] if x in idmap]`, and log what was dropped in `pruned`. Test: `test_BUG_dangling_overrides_kept`.

## Other observations (no failing test)
- `pipeline.rules_public` (line 200) strips only ENGINE_ONLY, while merge_rules writes only the PUBLIC fields. Today both produce the same output, but any extra machine field would leak through `rules-public`. Use `PUBLIC` from merge_rules in both places.
- Mutual yields (A yields to B and B yields to A) would mark both `superseded`, so nothing governs. Chains resolve one level deep. The real data has neither (`test_no_mutual_or_chained_yields`). Suggest a check for this in validate.
- merge returns only the error count, so unaccounted cells do not fail the exit code. There are 0 today.
- Timeline entries carry no `conflict_flag` field, even though compression is keyed on it.
- co_date with a Jan 1 cutoff and op `<` returns UNKNOWN in the equal year even though FALSE can be decided. This is conservative and acceptable.
- Dash audit: no en/em dash in lookups.json explanations, changes.json notes, or any rules.json field we write. Source dashes inside quoted_span: r-0027 (en dash between "March 1, 2026" and "February 28, 2027", verbatim from the source, leave as is).

## Checked and fine
- Kleene truth tables; all/any/not give the same result under every permutation of 3 children; empty all = TRUE, empty any = FALSE; missing facts are reported only when the result is UNKNOWN.
- Equal co_date year and equal age give UNKNOWN; year_built itself is exact; age uses the as-of year, not the effective date; negative ages compare numerically; yyyy and yyyy-mm mean the first day; leap day 2024-02-29 works.
- TRUST_UNITS_MIN=False: units_min never decides a leaf and never appears as a fact ("at least N") in explanations.
- Status matrix: in_force with a future date, nye with the date reached, nye with no date (stays nye), pending at any date, failed and unknown status omitted, non-active rules with FALSE coverage omitted.
- Precedence targets: applies gives superseded; unknown gives unknown_precedence with others_missing; a target in another city, not yet effective, or pending is ignored; results do not depend on rule order (all 120 permutations).
- Conflicts are flagged on both sides when only one rule declares them, and only when both rules are present (Newark is not flagged); the rule-level flag and note reach in_force, nye and pending entries.
- Timeline: compressed, never starts with None, yearly points catch age flips (2026 unknown, 2027 applies), drop-out emits None.
- Real outputs: for all 500 addresses, the lookups.json result equals the timeline entry valid at 2026-10-01, and there is no extra live rule; lookups match a fresh engine run; shapes are exact; every explanation ends with "Not legal advice." and contains no "{ASOF}".
- Change sets: T1 = all 250 CA addresses; T2 = JC + Hoboken (90); T3 = all 140 NJ with conflict ids = JC + Hoboken (90); T4 = all 110 MA; T5 empty.
- test_map: each key maps to exactly one rule. CA-ALG-01 r-0006, HOB-ALG-01 r-0045, JC-ALG-01 r-0043, NJ-ALG-01 r-0012 (nye 2027-07-01), MA-ALG-P1 r-0019, MA-ALG-P2 r-0020 (pending), MA-RENT-P1 r-0014 (failed).
- rules.json validates against the official schema (stdlib validator in the test), has exactly the PUBLIC fields in order, and equals rules_engine.json minus the engine fields. merge_rules prunes descriptors that point at missing cells or at the rule's own cell, accounts for every cell, and reproduces outputs/rules_engine.json from work/consolidate.
