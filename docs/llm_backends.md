# Pluggable LLM backends for the extraction pipeline

Stage 1 (`navigator/extract.py`) and stage 2 (`navigator/consolidate.py`) are executable: they build the prompt from
`prompts/*.md` plus the CONTRACTS.md record spec, call a model, parse JSON, validate with `navigator.validate.rule_errors`,
retry with the error list as feedback, and write the result. Stdlib only. No key is needed for the default backend.

## Run
    python3 -m navigator.extract --doc D081 [--doc D080] [--all] [--out DIR] [--max-retries 2]
    python3 -m navigator.consolidate --group CA1|CA2|NJ|MA [--out DIR]
Default output dirs are `work/extract_run` and `work/consolidate_run`. `work/extract` and `work/consolidate` are only
written when passed literally as `--out work/extract` (guard in code, tested).

## Backends (env `LLM_BACKEND`, default `replay`)
- `replay`: returns the cached response, or raises CacheMiss naming the expected file. Offline, deterministic.
- `ollama`: `LLM_MODEL` (default gemma4:12b-nvfp4), `OLLAMA_NUM_CTX` (8192), `OLLAMA_URL`; sends think=false, format json, temperature 0, timeout 900 s.
- `openai`: any OpenAI-compatible endpoint: `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `LLM_MODEL` (Gemini compat endpoint, Groq, OpenRouter).
- `anthropic`: `ANTHROPIC_API_KEY`, `LLM_MODEL` (we have no API credits, so this path is untested).
- `manual`: writes the prompt to `work/llm/pending/<stage>_<key>.md`; an interactive agent session answers by writing
  `work/llm/responses/<stage>_<key>.json`; the next run picks it up (else raises Pending).
- `fake`: tests only (returns `LLM_FAKE_RESPONSE`).
HTTP 429/5xx are retried with backoff (max 3). Credentials are read from env only and never written anywhere.

## Cache, replay, audit
Every real call writes `work/llm_cache/<stage>/<key>.<sha8>.json` where sha8 is from sha256(model + system + prompt), and
appends one line to `outputs/audit/llm_calls.jsonl` {ts, stage, key, backend, model, prompt_sha256, response_chars,
seconds, ok, error}. A retry has a different prompt, so it has its own cache entry. Extraction records carry a `run` block
(validation errors left, retries, quote repairs). Quote repair: a quoted_span not found verbatim is replaced by the one
document line with difflib ratio >= 0.9, if exactly one exists.

## Reproduce offline (judges)
The cache entries of the local run below are in `work/llm_cache/extract/` (D080, D081, D083). With the same model name:
    LLM_BACKEND=replay python3 -m navigator.extract --doc D081 --out /tmp/x      # 0.0 s, same JSON
Another model name gives a CacheMiss (hash includes the model). The production records in `work/extract` and
`work/consolidate` were made by Claude Code agents following the same prompt files; they are not in this cache.

## Measured local run (gemma4:12b-nvfp4 via ollama, 16 GB Mac, num_ctx 8192, think off, 2026-10-04)
Prompts 14 KB to 18 KB. Quotes: all validated verbatim; `navigator.validate` errors 0 in all three.
- D081 (SF algorithmic ban page): 120 s, 1 rule, 0 retries. Same as the Claude record on jurisdiction, level, category,
  status, effective_date 2024-10-14, citation S.F. Admin. Code § 37.10C, source fields, engine fields. Different: title,
  requirement (omits the right to sue), key_value (drops the word "rental"), confidence 1.0 vs 0.9, quoted_span is the
  second sentence only (Claude's included the effective-date sentence).
- D080 (SF rent cap page): 186 s, 1 rule, 0 retries. Matches Claude on cell, citation, status, effective 2026-03-01;
  key_value "1.6%" vs "1.6% (3/1/26 to 2/28/27)".
- D083 (SF Rent Board rates page): 528 s, 1 retry. Local model returned 5 rules, Claude returned 1. Validator-clean but
  not good: cites § 37.10C (the algorithm ban) for both a 1.6% rent-cap record and a 4.2% deposit-interest record,
  splits relocation payment tables into three just_cause_eviction records (the prompt says to attach them to the
  underlying rule). Validation proves quotes are real, not that cells and cites are right.
Sample size is three tiny pages: this shows the pipeline runs end to end with a local open model, not extraction accuracy.

## Limitations
- No Claude API credits and the `claude` CLI is logged out, so the Claude path (`anthropic`) is untested here.
- A 12B local model follows simple single-rule pages but over-extracts on tables; slow (2 to 9 min per page).
- Stage 2 prompts are large (110 KB to 260 KB, about 30k to 65k tokens): needs a long-context strong model;
  `num_ctx 8192` cannot hold them. Stage 2 was not run with any real backend; only prompt building was checked.
