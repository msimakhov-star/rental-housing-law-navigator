"""Pluggable LLM backend with cache + audit log. Stdlib only.
LLM_BACKEND = replay (default) | ollama | openai | anthropic | manual | fake (tests only).
Every real call is cached at work/llm_cache/<stage>/<key>.<sha8>.json and logged to outputs/audit/llm_calls.jsonl."""
import hashlib, json, os, time, urllib.error, urllib.request
from datetime import datetime, timezone
from .common import ROOT

DEFAULT_MODEL = "gemma4:12b-nvfp4"


class CacheMiss(RuntimeError):
    pass


class Pending(RuntimeError):
    pass


def cache_dir():
    return ROOT / "work" / "llm_cache"


def audit_path():
    return ROOT / "outputs" / "audit" / "llm_calls.jsonl"


def _model():
    return os.environ.get("LLM_MODEL") or DEFAULT_MODEL


def _sha(model, system, prompt):
    return hashlib.sha256((model + (system or "") + prompt).encode("utf-8")).hexdigest()


def _cache_file(stage, key, sha):
    return cache_dir() / stage / f"{key}.{sha[:8]}.json"


def _audit(**kw):
    p = audit_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **kw}) + "\n")


def _post(url, body, headers, timeout):
    data = json.dumps(body).encode("utf-8")
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if (e.code == 429 or e.code >= 500) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {e.code} from {url.split('?')[0]}")  # body omitted: may echo secrets
        except urllib.error.URLError as e:
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"connection error to {url}: {e.reason}")


def _msgs(prompt, system):
    return ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]


def _ollama(prompt, system, model, json_mode):
    base = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    body = {"model": model, "messages": _msgs(prompt, system), "stream": False, "think": False,
            "options": {"num_ctx": int(os.environ.get("OLLAMA_NUM_CTX", "8192")), "temperature": 0}}
    if json_mode:
        body["format"] = "json"
    return _post(base + "/api/chat", body, {}, 900)["message"]["content"]


def _openai(prompt, system, model, json_mode):
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = {"model": model, "messages": _msgs(prompt, system), "temperature": 0}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = _post(base + "/chat/completions", body, {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}, 900)
    return r["choices"][0]["message"]["content"]


def _anthropic(prompt, system, model, json_mode):
    body = {"model": model, "max_tokens": 8192, "messages": [{"role": "user", "content": prompt}]}
    if system:
        body["system"] = system
    r = _post("https://api.anthropic.com/v1/messages", body,
              {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"}, 900)
    return "".join(b.get("text", "") for b in r["content"])


def _manual(prompt, system, stage, key):
    pend = ROOT / "work" / "llm" / "pending" / f"{stage}_{key}.md"
    pend.parent.mkdir(parents=True, exist_ok=True)
    pend.write_text((f"SYSTEM:\n{system}\n\n" if system else "") + prompt, encoding="utf-8")
    resp = ROOT / "work" / "llm" / "responses" / f"{stage}_{key}.json"
    if resp.exists():
        return resp.read_text(encoding="utf-8")
    raise Pending(f"prompt written to {pend}; write the answer to {resp} and rerun")


def complete(prompt, *, stage, key, system=None, json_mode=True):
    backend = os.environ.get("LLM_BACKEND", "replay")
    model = _model()
    sha = _sha(model, system, prompt)
    cf = _cache_file(stage, key, sha)
    if backend == "replay":
        if cf.exists():
            return json.loads(cf.read_text(encoding="utf-8"))["response"]
        have = sorted(p.name for p in (cache_dir() / stage).glob(f"{key}.*.json")) if (cache_dir() / stage).exists() else []
        raise CacheMiss(f"no cached response for stage={stage} key={key} model={model} (expected {cf.name}; "
                        f"cached for this key: {have or 'none'}). Set LLM_MODEL to the model that produced the cache, "
                        f"or run with a real backend (LLM_BACKEND=ollama|openai|anthropic|manual).")
    t0, err, out = time.time(), None, ""
    try:
        if backend == "ollama": out = _ollama(prompt, system, model, json_mode)
        elif backend == "openai": out = _openai(prompt, system, model, json_mode)
        elif backend == "anthropic": out = _anthropic(prompt, system, model, json_mode)
        elif backend == "manual": out = _manual(prompt, system, stage, key)
        elif backend == "fake": out = os.environ.get("LLM_FAKE_RESPONSE", "{}")  # tests only
        else: raise ValueError(f"unknown LLM_BACKEND {backend!r}")
        return out
    except Pending:
        raise
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        raise
    finally:
        if err is not None or out:
            ok = err is None
            if ok:
                cf.parent.mkdir(parents=True, exist_ok=True)
                cf.write_text(json.dumps({"stage": stage, "key": key, "backend": backend, "model": model,
                                          "prompt_sha256": sha, "response": out}, ensure_ascii=False), encoding="utf-8")
            _audit(stage=stage, key=key, backend=backend, model=model, prompt_sha256=sha, response_chars=len(out),
                   seconds=round(time.time() - t0, 2), ok=ok, error=err)
