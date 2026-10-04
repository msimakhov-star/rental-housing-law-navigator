"""Deterministic templated explanations (English, Spanish). No LLM, no en/em dashes."""
import hashlib, json, re
from pathlib import Path
from . import apply as apply_mod

ES_FILE = Path(__file__).resolve().parent.parent / "work" / "es_rules.json"
NOTICE_EN = "Not legal advice."
NOTICE_ES = "Esto no es asesoramiento legal."
_es_cache = {}

MISS_EN = {"units": "the number of units in the building", "year_built": "the year the building was built",
           "building_age_years": "the exact age of the building (it falls on the threshold year)",
           "co_date": "the certificate of occupancy or first occupancy date (we only have the year built, and it is not decisive)",
           "legal_city": "a confirmed legal city for the address"}
MISS_ES = {"units": "el número de unidades del edificio", "year_built": "el año de construcción del edificio",
           "building_age_years": "la edad exacta del edificio (coincide con el año límite)",
           "co_date": "la fecha del certificado de ocupación o de primera ocupación (solo tenemos el año de construcción y no es decisivo)",
           "legal_city": "una ciudad legal confirmada para la dirección"}


def _clean(s):
    return re.sub(r"\s*[–—]\s*", ", ", s or "")


def _sent(s):
    s = _clean(str(s)).strip()
    return s if not s or s[-1] in ".!?" else s + "."


def _es_rules():
    if "d" not in _es_cache:
        try:
            _es_cache["d"] = json.loads(ES_FILE.read_text(encoding="utf-8")) if ES_FILE.exists() else {}
        except Exception:
            _es_cache["d"] = {}
    return _es_cache["d"]


def es_sha(rule):
    """Hash of the English fields a Spanish entry was translated from; a stale or misaligned entry never matches."""
    return hashlib.sha256(f"{rule.get('title', '')}\n{rule.get('requirement', '')}\n{rule.get('key_value') or ''}".encode("utf-8")).hexdigest()


def es_entry(rule):
    e = _es_rules().get(rule["team_rule_id"]) or {}
    return e if e.get("src_sha") == es_sha(rule) else {}


def _list(items, conj):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" {conj} " + items[-1]


def _miss(miss, lang):
    t, un, conj = (MISS_EN, "{} (not in our data)", "and") if lang == "en" else (MISS_ES, "{} (no está en nuestros datos)", "y")
    items = [t.get(m) or un.format(m) for m in miss] or (["some facts"] if lang == "en" else ["algunos datos"])
    return _list(items, conj)


def _items(miss, lang):
    t = MISS_EN if lang == "en" else MISS_ES
    return "; ".join(t.get(m) or m for m in miss) or ("some facts" if lang == "en" else "algunos datos")


def _hints(miss, lang):
    en = lang == "en"
    h = []
    if "units" in miss:
        h.append("the number of units (county assessor records, or the landlord)" if en else "el número de unidades (registros del tasador del condado, o el arrendador)")
    if any(m in miss for m in ("year_built", "co_date", "building_age_years")):
        h.append("when the building was built or first occupied (county assessor or the city rent board)" if en else "cuándo se construyó o se ocupó por primera vez el edificio (el tasador del condado o la junta municipal de alquileres)")
    if any(m not in ("units", "year_built", "co_date", "building_age_years", "legal_city") for m in miss):
        h.append("other facts such as whether the owner lives in the building or whether a special exemption was granted (the landlord or the city housing office can say)" if en
                 else "otros datos, como si el propietario vive en el edificio o si se concedió una exención especial (el arrendador o la oficina municipal de vivienda pueden decirlo)")
    return ((" What you could check: " if en else " Qué puede comprobar: ") + "; ".join(h) + ".") if h else ""


def _ver(rs, lang):
    if not rs.get("earlier_version"):
        return ""
    e = rs.get("effective_date")
    return (f" The current version of this rule took effect on {e}; an earlier version applied before then, so the details may differ." if lang == "en"
            else f" La versión actual de esta norma entró en vigor el {e}; antes regía una versión anterior, por lo que los detalles pueden diferir.")


def _facts_desc(entry, facts, lang):
    parts = []
    if "units" in entry["facts_used"] and (facts.get("units") is not None or facts.get("units_min") is not None):
        if facts.get("units") is not None:
            parts.append(f"{facts['units']} units" if lang == "en" else f"{facts['units']} unidades")
        else:
            parts.append(f"at least {facts['units_min']} units" if lang == "en" else f"al menos {facts['units_min']} unidades")
    if "year_built" in entry["facts_used"] and facts.get("year_built") is not None:
        parts.append(f"built in {facts['year_built']}" if lang == "en" else f"construido en {facts['year_built']}")
    return _list(parts, "and" if lang == "en" else "y") if parts else ""


def _when(d, lang):
    if d == "{ASOF}":  # detail timelines: the UI substitutes the selected as-of date
        return "as of {ASOF}" if lang == "en" else "a fecha de {ASOF}"
    if d.startswith("0000"):
        return "before any known effective date" if lang == "en" else "antes de cualquier fecha de vigencia conocida"
    return f"as of {d}" if lang == "en" else f"a fecha de {d}"


def _what(rule, lang):
    title, req = rule["title"], rule.get("requirement")
    if lang == "es":
        es = es_entry(rule)
        title, req = es.get("title_es") or title, es.get("requirement_es") or req
    s = f"{title}: {_sent(req)}" if req else _sent(title)
    kv = rule.get("key_value")
    if lang == "es" and kv:
        kv = es_entry(rule).get("key_value_es") or kv
    if kv:
        s += (f" Key figure: {_sent(kv)}" if lang == "en" else f" Cifra clave: {_sent(kv)}")
    return _clean(s)


def explain(entry, rule, rules, facts, d, parts=False):
    """-> (explanation_en, explanation_es) for one result entry at as-of date d.
    parts=True returns only the address-specific reasoning (no rule title, requirement, citation or notice),
    which the UI combines with the rule record."""
    k, rs = entry["reason"]["kind"], entry["reason"]
    out, whys = [], []
    for lang in ("en", "es"):
        en = lang == "en"
        w, cite = _when(d, lang), _clean(rule["citation"])
        j = rule["jurisdiction"]
        head = _what(rule, lang)
        others = [rules[o] for o in rs.get("others", [])]
        on = _list([f"{o['title']} ({o['jurisdiction']}, {_clean(o['citation'])})" for o in others], "and" if en else "y") if others else ""
        if k == "applies":
            fd = _facts_desc(entry, facts, lang)
            conds = rule.get("applies_if") or rule.get("exempt_if")
            if conds and fd:
                why = (f"the building facts we have ({fd}) meet its coverage conditions and none of its exemptions applies" if en
                       else f"los datos del edificio que tenemos ({fd}) cumplen sus condiciones de cobertura y no se aplica ninguna exención")
            elif conds:
                why = "its coverage conditions are met" if en else "se cumplen sus condiciones de cobertura"
            else:
                why = f"it covers residential rentals in {j}" if en else f"cubre los alquileres residenciales en {j}"
            body = (f"This rule applies to this address {w}: {why}." if en else f"Esta norma se aplica a esta dirección {w}: {why}.")
        elif k == "unknown_facts":
            body = (f"We cannot tell yet whether this rule applies to this address {w}. It depends on facts we do not have: {_items(entry['missing_facts'], lang)}."
                    if en else f"Todavía no podemos saber si esta norma se aplica a esta dirección {w}. Depende de datos que no tenemos: {_items(entry['missing_facts'], lang)}.")
            if "units" in entry["missing_facts"] and facts.get("units_min") and not apply_mod.TRUST_UNITS_MIN:
                body += (f" The property class suggests at least {facts['units_min']} units, but the unit count itself is not in the data, so we do not rely on it." if en
                         else f" La clase de propiedad sugiere al menos {facts['units_min']} unidades, pero el número de unidades no está en los datos, así que no nos basamos en ello.")
            body += _hints(entry["missing_facts"], lang)
        elif k == "unknown_city":
            body = (f"We could not confirm which city this address is legally in, so we cannot tell whether this city rule applies {w}."
                    if en else f"No pudimos confirmar en qué ciudad está legalmente esta dirección, por lo que no podemos saber si esta norma municipal se aplica {w}.")
        elif k == "unknown_precedence":
            body = (f"This rule would apply {w} unless {on} covers this building. That depends on facts we do not have: {_items(rs.get('others_missing', []), lang)}."
                    if en else f"Esta norma se aplicaría {w} salvo que {on} cubra este edificio. Eso depende de datos que no tenemos: {_items(rs.get('others_missing', []), lang)}.")
            body += _hints(rs.get("others_missing", []), lang)
        elif k == "superseded":
            body = (f"Another rule takes precedence at this address {w}: {on}. This rule yields to it and does not govern here."
                    if en else f"Otra norma tiene prioridad en esta dirección {w}: {on}. Esta norma cede ante ella y no rige aquí.")
        elif k == "not_yet_effective":
            e = rs.get("effective_date")
            when = (f"it takes effect on {e}" if e else "no effective date is known") if en else (f"entra en vigor el {e}" if e else "no se conoce fecha de entrada en vigor")
            if rule.get("status") == "in_force" and e:  # earlier as-of date than the current version: say so honestly
                body = (f"The current version of this rule was not yet in effect {w}: it took effect on {e}. Earlier versions may have applied; this tool models only the current version." if en
                        else f"La versión actual de esta norma aún no estaba en vigor {w}: entró en vigor el {e}. Pueden haber regido versiones anteriores; esta herramienta solo modela la versión actual.")
            else:
                body = (f"This rule is not yet in effect {w}: {when}." if en else f"Esta norma aún no está en vigor {w}: {when}.")
            if rs.get("coverage") == "UNKNOWN":
                body += (f" Whether it will cover this building depends on facts we do not have: {_items(entry['missing_facts'], lang)}." if en
                         else f" Que cubra este edificio depende de datos que no tenemos: {_items(entry['missing_facts'], lang)}.")
        else:  # pending
            body = (f"This is a proposed measure (a bill) and is not law {w}; it would matter only if enacted." if en
                    else f"Esta es una medida propuesta (un proyecto de ley) y no es ley {w}; solo importaría si se aprueba.")
            if rs.get("coverage") == "UNKNOWN":
                body += (f" Whether it would cover this building depends on facts we do not have: {_items(entry['missing_facts'], lang)}." if en
                         else f" Que cubriera este edificio dependería de datos que no tenemos: {_items(entry['missing_facts'], lang)}.")
        why = body + (_ver(rs, lang) if k in ("applies", "unknown_facts", "unknown_precedence", "superseded", "unknown_city") else "")
        if entry.get("result") in ("applies", "superseded", "pending", "not_yet_effective") and (entry.get("confidence") or 1) < 0.6:
            why += (" Low confidence: flagged for human review (the source is a secondary or partial page, or the facts are incomplete)." if en
                    else " Confianza baja: marcado para revisión humana (la fuente es una página secundaria o parcial, o faltan datos).")
        if entry.get("conflict_flag"):
            why += (f" Flagged for human review: {entry['conflict_note']}" if en
                    else f" Marcado para revisión humana: {_clean(entry['conflict_note'])} (texto original en inglés).")
        whys.append(_clean(why))
        txt = f"{head} {why}"
        dot = "" if cite.endswith(".") else "."
        txt += (f" Source: {cite}{dot} {NOTICE_EN}" if en else f" Fuente: {cite}{dot} {NOTICE_ES}")
        out.append(_clean(txt))
    return tuple(whys) if parts else tuple(out)
