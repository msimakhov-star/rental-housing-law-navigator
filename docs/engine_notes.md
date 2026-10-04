# Engine notes (worker E)

Run from repo root: `python3 -m navigator.pipeline build|check|ingest --extract work/extract/<doc>.json [--tests f.json]|rules-public`.
Test: `python3 -m unittest tests.test_apply`. Fixtures (test-only rules): tests/fixtures; use `--fixtures tests/fixtures --out DIR`.

## Semantics
- Kleene logic. None applies_if = TRUE, None exempt_if = FALSE. Coverage = applies_if AND NOT exempt_if.
- units: only the exact assessor count decides. The class-derived lower bound `units_min` (NJ class 4C, Boston A/ codes, Berkeley and San Diego class descriptions) is NOT used while `TRUST_UNITS_MIN = False` in navigator/apply.py (the guide says to answer unknown rather than infer); the explanation still mentions it as a hint. Setting the flag to True lets a bound decide a test (>=5 TRUE if min>=5; <5 FALSE if min>=5), which would resolve about 200 of the 500 x rules cells that are unknown today.
- co_date proxies year_built vs cutoff YEAR; building_age_years = as_of year - year_built. Equal year (age == threshold) is UNKNOWN. Missing year_built is UNKNOWN.
- {"unavailable":...} is always UNKNOWN; its text is reported in missing_facts.
- Dates: yyyy and yyyy-mm mean the first day. in_force with date E: before E = not_yet_effective. not_yet_effective with null date stays not_yet_effective forever.
- Scope: state rules by dataset state. City rules by legal_city. legal_city null: unknown only if geocode_status is "failed" (restricted to the postal city's rule, else all in-state city rules); otherwise confirmed outside, rule omitted. Fallback postal mapping keeps its city but confidence x0.6 (non_exact x0.9, city rules only).
- Precedence uses RAW results of other rules at the same date (order independent): a rule that would be applies OR unknown becomes superseded when any rule it yields to applies at the address; if none applies but one is unknown, an applies rule becomes unknown (confidence x0.7).
- Conflicts: mutual flag when either rule lists the other in conflicts_with and both are applies/unknown/nye/pending. Rule-level conflict_flag/conflict_note propagates to every entry.
- Non-active rules (nye, pending): coverage FALSE omits, UNKNOWN keeps the temporal status and says coverage depends on missing facts.
- Timeline: evaluated at 0000-01-01 and every distinct effective date; compressed on (result, conflict_flag). If a rule drops out of coverage later (age based), a point with result "not_covered" is emitted (not in the lookups enum; UI should hide it).

## Change tests
- Key ids map to our rules via navigator/test_map.py (jurisdiction + category + regex on title+citation); zero or several matches raise MapError, recorded in lookups_detail "test_errors" and the build exits with code 2 (other outputs are still written). Descriptors are guesses until rules_engine.json exists: CONFIRM.
- as_of: differs between before/after (state restricted). conflict ids only for tests that declare conflict_with (T3), taken at as_of_after.
- boundary: union of 'applies'. pending: 'pending'. negative: asserts no city rent_increase_limits rule is 'applies' in the test states.
- new_rule (T6, unknown types): applies/unknown/nye/pending, separate unknown_address_ids in lookups_detail tests only (changes.json keeps the official shape).
- ingest stores the T6 test (synthesised if no new_rule test supplied) in outputs/audit/ingested_tests.json so later builds keep it; data/dev/change_tests_extra.json is read too.

## Limitations
- Facts limited to units, units_min, year_built. Owner type, tenancy, rent level etc. are always unknown.
- Precedence is one level deep on raw results; chains (A yields to B yields to C) resolve against B's raw status.
- Spanish text uses work/es_rules.json if present; else English rule text inside Spanish sentences.
- Quote validation in `check` covers only rules that are 'applies' somewhere.
