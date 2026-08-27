"""Stage 4: facts -> layer.

This is where the root cause is decided. It is ordinary Python evaluating
declarative conditions from config/rules.json. No model is consulted here, and
no model output can reach this stage. If rules.json matches nothing, the answer
is Unknown and the pipeline says so rather than reaching for the nearest guess.
"""

from __future__ import annotations

import re
from typing import Any

from .models import RuleMatch


def _get(facts: dict[str, Any], name: str) -> Any:
    return facts.get(name)


def _as_number(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _eval_condition(cond: dict[str, Any], facts: dict[str, Any]) -> tuple[bool, str]:
    """Return (matched, human description of what was checked)."""
    fact_name = cond["fact"]
    op = cond["op"]
    expected = cond.get("value")
    actual = _get(facts, fact_name)
    label = fact_name.replace("_", " ")

    if op == "exists":
        return actual is not None, f"{label} is present"
    if op == "absent":
        return actual is None, f"{label} is absent"

    if op == "eq":
        return actual == expected, f"{label} is {expected}"
    if op == "ne":
        return actual != expected, f"{label} is not {expected}"

    if op in ("gt", "gte", "lt", "lte"):
        a, b = _as_number(actual), _as_number(expected)
        if a is None or b is None:
            return False, f"{label} is not a number"
        ok = {
            "gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b,
        }[op]
        symbol = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
        return ok, f"{label} ({_fmt(a)}) {symbol} {_fmt(b)}"

    if op == "in":
        return actual in (expected or []), f"{label} is one of {expected}"

    if op == "contains":
        if not isinstance(actual, (list, tuple)):
            return False, f"{label} is not a list"
        want = str(expected).lower()
        return (
            any(str(x).lower() == want for x in actual),
            f"{label} includes {expected}",
        )

    if op == "matches":
        text = "" if actual is None else str(actual)
        return (
            str(expected).lower() in text.lower(),
            f'{label} contains "{expected}"',
        )

    if op == "near":
        a, b = _as_number(actual), _as_number(expected)
        tol = float(cond.get("tolerance", 0))
        if a is None or b is None:
            return False, f"{label} is not a number"
        return (
            abs(a - b) <= tol,
            f"{label} ({_fmt(a)}) is within {_fmt(tol)} of {_fmt(b)}",
        )

    raise ValueError(f"Unknown operator {op!r} in rules.json for fact {fact_name!r}")


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:.3g}"


def evaluate_rule(rule: dict[str, Any], facts: dict[str, Any]) -> tuple[bool, list[str]]:
    matched: list[str] = []

    for cond in rule.get("all_of", []):
        ok, desc = _eval_condition(cond, facts)
        if not ok:
            return False, []
        matched.append(desc)

    any_of = rule.get("any_of", [])
    if any_of:
        hit = False
        for cond in any_of:
            ok, desc = _eval_condition(cond, facts)
            if ok:
                matched.append(desc)
                hit = True
        if not hit:
            return False, []

    for cond in rule.get("none_of", []):
        ok, _ = _eval_condition(cond, facts)
        if ok:
            return False, []

    if not rule.get("all_of") and not any_of:
        raise ValueError(f"Rule {rule.get('id')} has no conditions")

    return True, matched


def evaluate(facts: dict[str, Any], rules_cfg: dict[str, Any]) -> tuple[RuleMatch | None, list[RuleMatch]]:
    """Return (winning rule, all matching rules ordered by priority).

    The highest-priority match wins. Ties are impossible in practice because
    priorities are distinct, but a tie falls back to declaration order.
    """
    hits: list[RuleMatch] = []

    for rule in rules_cfg.get("rules", []):
        ok, matched = evaluate_rule(rule, facts)
        if ok:
            hits.append(
                RuleMatch(
                    rule_id=rule["id"],
                    layer=rule["layer"],
                    title=rule.get("title", rule["id"]),
                    rationale=rule.get("rationale", ""),
                    specificity=rule.get("specificity", "broad"),
                    priority=int(rule.get("priority", 0)),
                    matched_conditions=matched,
                    eliminates=list(rule.get("eliminates", [])),
                    elimination_reasons=dict(rule.get("elimination_reasons", {})),
                )
            )

    hits.sort(key=lambda r: -r.priority)
    return (hits[0] if hits else None), hits
