# eval: PROXY scorer (not the organizers' score.py)
Not legal advice. Run from the repo root, stdlib only, offline.

    python3 eval/score_proxy.py [--rules outputs/rules.json] [--lookups outputs/lookups.json] [--changes outputs/changes.json]
    python3 eval/check_spots.py [outputs/lookups_detail.json]     # skips if absent
    python3 -m unittest tests.test_eval

Files: proxy_key.json (27 expected rules from docs only), cells.json (13 x 6 = 78 cells with evidence class),
spot_checks.json (13 hand-reasoned cases + 8 scope-leak checks), score_proxy.py, check_spots.py.

Report sections
- (a) schema validity of rules (official schema), lookups and changes (template shapes); exit code 1 on any hard error.
- (b) recall: proxy-key entries found by jurisdiction + category + cite regex (also tried on title: "via title_only"); field accuracy over status, effective_date, key_value where the key states them.
- (c) rules per cell. 0 where docs evidence a rule = extraction miss; >3 = padding or duplicate instruments.
- (d) share of quoted_spans found in the corpus (single_line / ws_normalized / missing), plus share of `applies` answers backed by a found quote and url.
- (e) invented-citation detector: number tokens of the citation absent from the source doc and quoted span.
- (f) T1..T5 expected sets from the geocoded stack (CSV postal city when work/jurisdictions.json is absent): precision, recall.
- (g) lookups sanity: 500 ids, enum, no `applies` on non-in_force rules, no failed rules listed, missing proxy rules per address, results by legal city.
- PROXY ESTIMATE out of 75: extraction 25*(0.7*recall+0.3*field_acc); address 20*mean(hit/(hit+2*miss)); citations 15*applies share; change 15*mean(T1..T5 jaccard, T3 half conflict flags).

What the proxy cannot know
- 31 of the 58 real key rules and the 19 no-rule findings: recall is on the 27 documented ones only.
- Real citation matching, partial credit, and the 100 held-out addresses; T6 (hour-16 ordinance).
- Coverage facts (CO date, owner type, exemptions): the spot checks assert only what the brief text states.
- Key dates given as month only are matched by prefix; the Berkeley date accepts either published value.
