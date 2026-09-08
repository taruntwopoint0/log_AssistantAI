"""What the team should change so this does not recur.

Two sources, neither of them a model:

    runbooks.json[layer].prevention   the advice itself, as config
    this module                       the numbers, computed from the facts

Advice is domain knowledge and belongs in config alongside checks and do_not,
so another team adapts it by editing JSON. Numbers are arithmetic over the
measured facts and must never be written into the advice text - a hardcoded
"chunk to 200 records" is correct at exactly one throughput and quietly wrong
at every other. RB-GATEWAY-60S used to say that; now it does not.

The distinction that matters when presenting this: the runbook's ``fix`` is
what to do in the next hour. ``prevention`` is what to change so nobody is
woken for this again. Different audiences, different time horizons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Aim to finish inside this fraction of the ceiling. 0.6 leaves room for the
# variance a production run has and that a clean measurement does not.
HEADROOM = 0.6

AREA_ORDER = {"code": 0, "config": 1, "monitoring": 2, "process": 3}


@dataclass
class Sizing:
    """A concrete, derived recommendation. Only produced when the facts allow."""

    safe_batch_size: int
    ceiling_seconds: float
    seconds_per_record: float
    projected_seconds: float
    headroom_fraction: float
    basis: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe_batch_size": self.safe_batch_size,
            "ceiling_seconds": self.ceiling_seconds,
            "seconds_per_record": round(self.seconds_per_record, 4),
            "projected_seconds": round(self.projected_seconds, 1),
            "headroom_fraction": self.headroom_fraction,
            "basis": self.basis,
        }


@dataclass
class Prevention:
    items: list[dict[str, str]] = field(default_factory=list)
    sizing: Sizing | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "sizing": self.sizing.to_dict() if self.sizing else None,
        }


def _sizing(facts: dict[str, Any]) -> Sizing | None:
    """Largest batch that finishes inside the ceiling with headroom.

    Needs a ceiling and a throughput rate. Returns None rather than guessing
    when either is missing - the same rule the rest of the engine follows.
    """
    ceiling = facts.get("ceiling_seconds")
    rate = facts.get("observed_seconds_per_record")
    if not ceiling or not rate or rate <= 0:
        return None

    budget = ceiling * HEADROOM
    size = int(budget // rate)
    if size < 1:
        return None

    measured = facts.get("rate_source") == "observed"
    basis = (
        f"{ceiling:.0f}s ceiling x {HEADROOM:g} headroom / {rate:.3f}s per record"
        + (" (rate measured in this log)" if measured
           else " (rate from the configured baseline, not measured here)")
    )
    return Sizing(
        safe_batch_size=size,
        ceiling_seconds=float(ceiling),
        seconds_per_record=float(rate),
        projected_seconds=float(facts.get("projected_seconds") or 0.0),
        headroom_fraction=HEADROOM,
        basis=basis,
    )


def build(runbook: dict[str, Any] | None, facts: dict[str, Any]) -> Prevention:
    items = list((runbook or {}).get("prevention") or [])
    items.sort(key=lambda i: AREA_ORDER.get(i.get("area", ""), 9))
    return Prevention(items=items, sizing=_sizing(facts))
