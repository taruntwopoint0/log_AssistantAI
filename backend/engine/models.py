"""Typed structures passed between engine stages.

Every field here is produced by deterministic code. Nothing in this module is
written by, or shaped by, a language model. engine/writer.py consumes these
objects and turns them into prose; it never adds to them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class LogLine:
    """One physical line of the pasted log."""

    line_no: int
    raw: str
    time: str | None = None          # HH:MM:SS as it appeared
    date: str | None = None          # YYYY-MM-DD when the sink emitted one
    level: str | None = None         # normalised: VRB DBG INF WRN ERR FTL
    message: str | None = None       # header line message, continuations excluded
    is_header: bool = False


@dataclass
class LogBlock:
    """A header line plus every continuation line beneath it.

    Serilog writes an exception across many lines. The block is the unit the
    parser reasons about, because the diagnosis usually lives in the inner
    exception three lines below the header.
    """

    line_no: int
    time: str | None
    date: str | None
    level: str
    message: str
    continuation: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join([self.message, *self.continuation])

    @property
    def is_error(self) -> bool:
        return self.level in ("ERR", "FTL")


@dataclass
class Evidence:
    """One observation extracted from the log.

    ``source`` is the diagnostic source the observation *speaks about*, not the
    channel it arrived on. A log line reporting a stopped service is
    windows_service evidence even though it was read out of a log file. This is
    what lets corroboration count independent sources rather than line volume.
    """

    kind: str                        # e.g. exception_chain, elapsed, record_count
    summary: str                     # human-readable, shown in the evidence panel
    source: str                      # source id from topology.json
    line_no: int | None = None
    time: str | None = None
    value: Any = None
    derived: bool = False            # True when computed rather than read directly


@dataclass
class RuleMatch:
    rule_id: str
    layer: str
    title: str
    rationale: str
    specificity: str
    priority: int
    matched_conditions: list[str] = field(default_factory=list)
    eliminates: list[str] = field(default_factory=list)
    elimination_reasons: dict[str, str] = field(default_factory=dict)


@dataclass
class PrecedentMatch:
    incident_id: str
    date: str
    title: str
    layer: str
    similarity: float
    fix_held: bool
    resolution: str
    resolved_by: str | None
    time_to_resolve_hours: float | None
    components: dict[str, float] = field(default_factory=dict)
    recurrence: int = 1          # incidents collapsed into this one shape
    also: list[str] = field(default_factory=list)   # their ids, most recent first


@dataclass
class Dimension:
    name: str
    weight: float
    score: float                     # 0.0 - 1.0
    detail: str                      # why it scored what it scored

    @property
    def contribution(self) -> float:
        return self.weight * self.score


@dataclass
class Confidence:
    band: str                        # High | Medium | Inconclusive
    raw_band: str                    # band before the coverage cap
    raw_score: float
    dimensions: list[Dimension]
    capped: bool
    cap_reason: str | None
    coverage: float
    connected_sources: int
    total_sources: int


@dataclass
class Investigation:
    """The complete result. Stages 1-6 fill everything except ``narrative``."""

    layer: str
    layer_name: str
    owner: str | None
    runbook_id: str | None
    runbook: dict[str, Any] | None
    confidence: Confidence
    evidence: list[Evidence]
    rule: RuleMatch | None
    eliminated: dict[str, str]
    precedents: list[PrecedentMatch]
    facts: dict[str, Any]
    timing: dict[str, Any]
    sources: list[dict[str, Any]]
    narrative: str = ""
    narrative_source: str = "template"   # "gemini" or "template"
    parse_warnings: list[str] = field(default_factory=list)

    # Exactly what left the machine at stage 7. Empty when no model was called.
    # Local-only: rendered by the dashboard so the containment claim can be
    # shown to a risk reviewer rather than asserted.
    redactions: list[dict[str, str]] = field(default_factory=list)
    prompt_sent: str | None = None
    leak_check_passed: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Dimension.contribution is a property, so asdict drops it.
        for dim, src in zip(d["confidence"]["dimensions"], self.confidence.dimensions):
            dim["contribution"] = round(src.contribution, 4)
        return d
