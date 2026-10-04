"""Deterministic map from the organizers' key-style test rule ids to our team_rule_ids.
Each descriptor: jurisdiction + category + regex over 'title + citation'. Zero or several matches => MapError."""
import re

TABLE = {
    "CA-ALG-01": {"jurisdiction": "CA", "category": "algorithmic_rent_setting", "re": r"AB 325|SB 763|16720|16729"},
    "HOB-ALG-01": {"jurisdiction": "Hoboken, NJ", "category": "algorithmic_rent_setting", "re": r"."},
    "JC-ALG-01": {"jurisdiction": "Jersey City, NJ", "category": "algorithmic_rent_setting", "re": r"."},
    "NJ-ALG-01": {"jurisdiction": "NJ", "category": "algorithmic_rent_setting", "re": r"FAIR|c\.\s?0?43\b|2026"},
    "MA-ALG-P1": {"jurisdiction": "MA", "category": "algorithmic_rent_setting", "re": r"S\.?\s?2983"},
    "MA-ALG-P2": {"jurisdiction": "MA", "category": "algorithmic_rent_setting", "re": r"H\.?\s?5222"},
    "MA-RENT-P1": {"jurisdiction": "MA", "category": "rent_increase_limits", "re": r"ballot|IP\s?25|25-21|initiative|question"},
}


class MapError(Exception):
    pass


def resolve(key, rules):
    """key: key-style id or an actual team_rule_id. rules: iterable of rule dicts (all statuses). -> team_rule_id"""
    rules = list(rules)
    for r in rules:
        if r["team_rule_id"] == key:
            return key
    d = TABLE.get(key)
    if d is None:
        raise MapError(f"test rule id {key!r} is neither a team_rule_id nor in navigator/test_map.py TABLE")
    hit = [r["team_rule_id"] for r in rules if r["jurisdiction"] == d["jurisdiction"] and r["category"] == d["category"]
           and re.search(d["re"], f"{r.get('title', '')} {r.get('citation', '')}", re.I)]
    if len(hit) != 1:
        raise MapError(f"test rule id {key!r} ({d['jurisdiction']}, {d['category']}, /{d['re']}/) matched {len(hit)} rules "
                       f"{hit}; fix the descriptor in navigator/test_map.py or the rule set")
    return hit[0]


def resolve_all(keys, rules):
    return [resolve(k, rules) for k in keys]
