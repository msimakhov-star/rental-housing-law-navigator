# Rental Housing Law Navigator

Live demo: TODO-FILL (live link)

Users type an address and a date to see which rules apply. The system displays which rules are known or unknown with a quoted source sentence and a plain explanation in English and Spanish. Each rule check can end as yes, no or unknown. The scope covers 3 states, 10 cities, and 6 rule categories.

## How it works

* Find the legal city.
* Test each rule against building facts.
* Say when a local rule supersedes a state rule.
* Run change tests T1 to T5 with an as-of date.

## Responsible design

* Each rule check can end as yes, no or unknown.
* A validator checks every quote is copied word for word from the corpus.
* Each answer shows the quoted source sentence and a link to the source.
* Pending and not yet effective laws are shown as such.

## Outputs

- `outputs/rules.json`: rule records in the official schema, with citation and quoted span
- `outputs/lookups.json`: results for all 500 sample addresses as of 2026-10-01
- `outputs/changes.json`: affected addresses and conflict flags for change tests T1 to T5
- `outputs/lookups_detail.json`: richer data used by the web demo (`web/`)

## Run it

Python 3.12 or newer, standard library only. No install step.

```sh
python3 -m navigator.validate --rules outputs/rules_engine.json   # rule records and quotes
python3 -m navigator.pipeline check                               # consistency of outputs
python3 -m unittest discover -s tests -p 'test_*.py'              # unit tests
python3 eval/score_proxy.py                                       # our own proxy scorer, not the organizers' score.py
cd web && python3 -m http.server 8000                             # demo at http://localhost:8000
```

Rebuild from the caches: `scripts/run_all.sh` (needs the organizers' starter pack in `data/`; it is not redistributed here).
Extraction with a model: see `docs/llm_backends.md`. Adding a city: see `docs/ADD_JURISDICTION.md`. Method: `docs/METHOD_NOTE.md`.

## Limitations

* 30.9 percent of results are unknown.
* San Diego rows lack year built data.
* 32 Boston rows lack unit data.
* Some effective dates are version dates with an earlier version note.
* No human or lawyer reviewed the tool.
* Production extraction used Claude Code agents with only 4 logged demo calls.
* Adding a city requires source text and config entries.
* Not legal advice.
