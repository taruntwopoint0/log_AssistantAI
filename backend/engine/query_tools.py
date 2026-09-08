"""Approved project queries. The model may choose one; the backend runs it.

This is the reliability boundary for the conversational layer. The model never
executes anything, never sees a query language, and never receives a fact that
did not come out of one of these functions. Every result carries its
provenance, so an answer can be traced to topology.json, to the current
investigation, or to a specific incident id.

A tool that cannot answer returns ok=False with a reason. That is the path that
produces "I don't have sufficient project evidence to determine the owner"
instead of a confident guess.

To add a capability, add a function here and register it in TOOLS. There is
deliberately no mechanism for the model to reach anything else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .graph import CURRENT, Graph


@dataclass
class ToolResult:
    tool: str
    ok: bool
    data: Any = None
    source: str = ""
    path: list[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool, "ok": self.ok, "data": self.data,
            "source": self.source, "path": self.path, "note": self.note,
        }


@dataclass
class DiagnosisContext:
    """Everything the conversational layer is allowed to know."""

    investigation: dict[str, Any]
    graph: Graph
    topology: dict[str, Any]
    runbooks: dict[str, Any]
    incidents: dict[str, Any]

    @property
    def inv(self) -> dict[str, Any]:
        return self.investigation

    @property
    def layer(self) -> str:
        return self.inv.get("layer", "Unknown")

    @property
    def diagnosed(self) -> bool:
        """False when the rules engine declined to name a cause."""
        return self.layer not in ("Unknown",)

    def limitations(self) -> list[str]:
        out: list[str] = []
        c = self.inv["confidence"]
        if c.get("cap_reason"):
            out.append(c["cap_reason"])
        if self.layer == "Unknown":
            out.append("No rule matched this evidence, so no cause is being claimed.")
        disconnected = [s["name"] for s in self.inv.get("sources", [])
                        if not s.get("connected")]
        if disconnected:
            out.append("Not connected, so silent rather than healthy: "
                       + ", ".join(disconnected) + ".")
        out.extend(self.inv.get("parse_warnings", []))
        return out


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

def get_diagnosis(ctx: DiagnosisContext) -> ToolResult:
    inv = ctx.inv
    c = inv["confidence"]
    if not ctx.diagnosed:
        return ToolResult(
            "get_diagnosis", ok=True,
            data={"layer": "Unknown", "band": c["band"],
                  "rule": None, "declined": True},
            source="current investigation (rules_engine.py)",
            note="The evidence matched no configured rule.",
        )
    return ToolResult(
        "get_diagnosis", ok=True,
        data={
            "layer": inv["layer"],
            "layer_name": inv["layer_name"],
            "band": c["band"],
            "evidence_score_pct": round(c["raw_score"] * 100),
            "rule_id": (inv.get("rule") or {}).get("rule_id"),
            "rule_rationale": (inv.get("rule") or {}).get("rationale"),
            "matched_conditions": (inv.get("rule") or {}).get("matched_conditions", []),
        },
        source="current investigation (rules_engine.py + scorer.py)",
    )


def get_owner(ctx: DiagnosisContext) -> ToolResult:
    """Incident -> CLASSIFIED_AS -> Layer -> OWNED_BY -> Team."""
    teams, path = ctx.graph.walk(CURRENT, ["CLASSIFIED_AS", "OWNED_BY"])
    if not teams:
        return ToolResult(
            "get_owner", ok=False, source="topology.json", path=path,
            note=(f"No owning team is recorded for layer {ctx.layer!r} in "
                  f"topology.json."),
        )
    return ToolResult(
        "get_owner", ok=True, data=[t.label for t in teams],
        source="topology.json (layers[].owner)", path=path,
    )


def get_application(ctx: DiagnosisContext) -> ToolResult:
    apps, path = ctx.graph.walk(CURRENT, ["AFFECTS"])
    apps = [a for a in apps if a.type == "Application"]
    if not apps:
        return ToolResult("get_application", ok=False, source="topology.json", path=path,
                          note="No application is recorded in topology.json.")
    a = apps[0]
    owners, opath = ctx.graph.walk(a.key, ["OWNED_BY"])
    return ToolResult(
        "get_application", ok=True,
        data={
            "name": a.label,
            "description": a.prop("description"),
            "environment": a.prop("environment"),
            "owner_team": owners[0].label if owners else None,
        },
        source="topology.json (application)", path=path + opath[1:],
    )


def get_services(ctx: DiagnosisContext) -> ToolResult:
    apps, _ = ctx.graph.walk(CURRENT, ["AFFECTS"])
    for a in apps:
        if a.type != "Application":
            continue
        svcs, path = ctx.graph.walk(a.key, ["RUNS_AS"])
        if svcs:
            return ToolResult("get_services", ok=True,
                              data=[s.label for s in svcs],
                              source="topology.json (application.runs_as_service)",
                              path=path)
    return ToolResult("get_services", ok=False, source="topology.json",
                      note="No Windows service is recorded for this application.")


def get_dependencies(ctx: DiagnosisContext) -> ToolResult:
    apps, _ = ctx.graph.walk(CURRENT, ["AFFECTS"])
    app = next((a for a in apps if a.type == "Application"), None)
    if app is None:
        return ToolResult("get_dependencies", ok=False, source="topology.json",
                          note="No application is recorded in topology.json.")
    calls, _ = ctx.graph.walk(app.key, ["CALLS"])
    deps, _ = ctx.graph.walk(app.key, ["DEPENDS_ON"])
    if not calls and not deps:
        return ToolResult("get_dependencies", ok=False, source="topology.json",
                          note="No dependencies are recorded for this application.")
    return ToolResult(
        "get_dependencies", ok=True,
        data={
            "calls": [{"host": n.label, "role": n.prop("role")} for n in calls],
            "depends_on": [{"host": n.label, "role": n.prop("role")} for n in deps],
        },
        source="topology.json (application.calls / depends_on)",
        path=[app.label, "CALLS / DEPENDS_ON"],
    )


def get_evidence(ctx: DiagnosisContext) -> ToolResult:
    ev = ctx.inv.get("evidence", [])
    if not ev:
        return ToolResult("get_evidence", ok=False, source="current investigation",
                          note="No evidence was extracted from this log.")
    return ToolResult(
        "get_evidence", ok=True,
        data=[{"summary": e["summary"], "source": e["source"],
               "derived": e.get("derived", False), "time": e.get("time")}
              for e in ev],
        source="current investigation (parser.py)",
    )


def get_eliminated_layers(ctx: DiagnosisContext) -> ToolResult:
    elim = ctx.inv.get("eliminated") or {}
    if not elim:
        return ToolResult("get_eliminated_layers", ok=False,
                          source="current investigation",
                          note="No layers were ruled out, because no rule matched.")
    return ToolResult(
        "get_eliminated_layers", ok=True,
        data=[{"layer": k, "reason": v} for k, v in elim.items()],
        source="current investigation (rules.json eliminations)",
    )


def get_confidence_explanation(ctx: DiagnosisContext) -> ToolResult:
    c = ctx.inv["confidence"]
    return ToolResult(
        "get_confidence_explanation", ok=True,
        data={
            "band": c["band"],
            "band_before_cap": c["raw_band"],
            "evidence_score_pct": round(c["raw_score"] * 100),
            "was_capped": c["capped"],
            "cap_reason": c.get("cap_reason"),
            "sources_connected": c["connected_sources"],
            "sources_total": c["total_sources"],
            "dimensions": [
                {"name": d["name"], "weight": d["weight"],
                 "score_pct": round(d["score"] * 100), "detail": d["detail"]}
                for d in c["dimensions"]
            ],
        },
        source="current investigation (scorer.py)",
    )


def get_runbook(ctx: DiagnosisContext) -> ToolResult:
    rb = ctx.inv.get("runbook")
    if not rb:
        return ToolResult("get_runbook", ok=False, source="runbooks.json",
                          note="No runbook is mapped to this layer.")
    return ToolResult(
        "get_runbook", ok=True,
        data={"id": ctx.inv.get("runbook_id"), "title": rb.get("title"),
              "symptom": rb.get("symptom"), "checks": rb.get("checks", []),
              "fix": rb.get("fix"), "do_not": rb.get("do_not", []),
              "escalate_to": rb.get("escalate_to")},
        source=f"runbooks.json ({ctx.inv.get('runbook_id')})",
    )


def get_next_checks(ctx: DiagnosisContext) -> ToolResult:
    rb = ctx.inv.get("runbook") or {}
    checks = rb.get("checks") or []
    if not checks:
        return ToolResult("get_next_checks", ok=False, source="runbooks.json",
                          note="No checks are recorded for this runbook.")
    return ToolResult("get_next_checks", ok=True, data=checks,
                      source=f"runbooks.json ({ctx.inv.get('runbook_id')}.checks)")


def get_what_not_to_do(ctx: DiagnosisContext) -> ToolResult:
    rb = ctx.inv.get("runbook") or {}
    do_not = rb.get("do_not") or []
    if not do_not:
        return ToolResult("get_what_not_to_do", ok=False, source="runbooks.json",
                          note="No do-not list is recorded for this runbook.")
    return ToolResult("get_what_not_to_do", ok=True, data=do_not,
                      source=f"runbooks.json ({ctx.inv.get('runbook_id')}.do_not)")


def find_related_incidents(ctx: DiagnosisContext) -> ToolResult:
    """Vector/lexical similarity picked these; the graph supplies the detail."""
    precedents = ctx.inv.get("precedents") or []
    if not precedents:
        return ToolResult(
            "find_related_incidents", ok=False, source="incidents.json",
            note=("No resolved incident in incidents.json resembles this failure "
                  "closely enough to report."),
        )
    out = []
    for p in precedents:
        node = ctx.graph.find("Incident", p["incident_id"])
        teams, _ = ctx.graph.walk(f"Incident:{p['incident_id']}",
                                  ["RESOLVED_BY", "OWNED_BY"])
        out.append({
            "incident_id": p["incident_id"],
            "date": p["date"],
            "title": p["title"],
            "similarity_pct": round(p["similarity"] * 100),
            "fix_held": p["fix_held"],
            "resolution": p["resolution"],
            "resolved_by": teams[0].label if teams else p.get("resolved_by"),
            "time_to_resolve_hours": p.get("time_to_resolve_hours"),
            "match_components": p.get("components", {}),
            "layer": node.label if node else None,
            "times_seen": p.get("recurrence", 1),
            "other_occurrences": p.get("also", []),
        })
    return ToolResult(
        "find_related_incidents", ok=True, data=out,
        source="incidents.json via precedent.py similarity + graph traversal",
        path=["This investigation", "SIMILAR_TO", "Incident", "RESOLVED_BY", "Fix"],
    )


def get_previous_resolution(ctx: DiagnosisContext) -> ToolResult:
    related = find_related_incidents(ctx)
    if not related.ok:
        return ToolResult("get_previous_resolution", ok=False,
                          source="incidents.json", note=related.note)
    best = related.data[0]
    return ToolResult(
        "get_previous_resolution", ok=True,
        data={"incident_id": best["incident_id"], "date": best["date"],
              "resolution": best["resolution"], "fix_held": best["fix_held"],
              "resolved_by": best["resolved_by"],
              "similarity_pct": best["similarity_pct"]},
        source=f"incidents.json ({best['incident_id']}.resolution)",
        path=["This investigation", "SIMILAR_TO", best["incident_id"], "RESOLVED_BY"],
    )


def get_incident_relationships(ctx: DiagnosisContext) -> ToolResult:
    rels = ctx.graph.relations(CURRENT)
    if not rels:
        return ToolResult("get_incident_relationships", ok=False, source="knowledge graph",
                          note="No relationships were derived for this investigation.")
    return ToolResult("get_incident_relationships", ok=True, data=rels,
                      source="knowledge graph (graph.py)")


def get_timing(ctx: DiagnosisContext) -> ToolResult:
    t = ctx.inv.get("timing") or {}
    if t.get("elapsed_seconds") is None:
        return ToolResult("get_timing", ok=False, source="current investigation",
                          note="No timing could be derived from this log.")
    return ToolResult(
        "get_timing", ok=True,
        data={k: t.get(k) for k in
              ("record_count", "elapsed_seconds", "projected_seconds",
               "ceiling_seconds", "client_timeout_seconds", "seconds_per_record",
               "rate_source", "rate_basis")},
        source="current investigation (parser.py derived facts)",
    )


def get_source_coverage(ctx: DiagnosisContext) -> ToolResult:
    sources = ctx.inv.get("sources", [])
    return ToolResult(
        "get_source_coverage", ok=True,
        data={
            "connected": [s["name"] for s in sources if s.get("connected")],
            "not_connected": [s["name"] for s in sources if not s.get("connected")],
        },
        source="topology.json (sources[].connected)",
    )


def get_limitations(ctx: DiagnosisContext) -> ToolResult:
    lims = ctx.limitations()
    return ToolResult("get_limitations", ok=True, data=lims,
                      source="current investigation")


def get_log_quality(ctx: DiagnosisContext) -> ToolResult:
    """How well the application logs, judged deterministically."""
    q = ctx.inv.get("log_quality") or {}
    if not q.get("total"):
        return ToolResult("get_log_quality", ok=False, source="current investigation",
                          note="No logging assessment was produced for this log.")
    return ToolResult(
        "get_log_quality", ok=True,
        data={
            "practices_present": q["passed"],
            "practices_checked": q["total"],
            "gaps": [
                {"name": g["name"], "severity": g["severity"],
                 "observed": g["observed"], "impact": g["impact"], "fix": g["fix"]}
                for g in q.get("gaps", [])
            ],
            "already_good": [g["name"] for g in q.get("strengths", [])],
        },
        source="current investigation (log_quality.py)",
    )


def get_prevention(ctx: DiagnosisContext) -> ToolResult:
    """What to change so this failure does not recur."""
    pv = ctx.inv.get("prevention") or {}
    items = pv.get("items") or []
    if not items:
        return ToolResult(
            "get_prevention", ok=False, source="runbooks.json",
            note=("No prevention guidance is recorded for this layer in "
                  "runbooks.json."),
        )
    data = {"actions": items}
    if pv.get("sizing"):
        s = pv["sizing"]
        data["recommended_batch_size"] = s["safe_batch_size"]
        data["sizing_basis"] = s["basis"]
    return ToolResult(
        "get_prevention", ok=True, data=data,
        source=f"runbooks.json ({ctx.inv.get('runbook_id')}.prevention)"
               + (" + computed from measured throughput" if pv.get("sizing") else ""),
    )


TOOLS: dict[str, Callable[[DiagnosisContext], ToolResult]] = {
    "get_diagnosis": get_diagnosis,
    "get_owner": get_owner,
    "get_application": get_application,
    "get_services": get_services,
    "get_dependencies": get_dependencies,
    "get_evidence": get_evidence,
    "get_eliminated_layers": get_eliminated_layers,
    "get_confidence_explanation": get_confidence_explanation,
    "get_runbook": get_runbook,
    "get_next_checks": get_next_checks,
    "get_what_not_to_do": get_what_not_to_do,
    "find_related_incidents": find_related_incidents,
    "get_previous_resolution": get_previous_resolution,
    "get_incident_relationships": get_incident_relationships,
    "get_timing": get_timing,
    "get_source_coverage": get_source_coverage,
    "get_limitations": get_limitations,
    "get_log_quality": get_log_quality,
    "get_prevention": get_prevention,
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "get_diagnosis": "the root cause that was determined, the rule that fired, and the band",
    "get_owner": "which team owns the layer that failed",
    "get_application": "which application or system is affected, and who owns it",
    "get_services": "the Windows service the application runs as",
    "get_dependencies": "what the application calls and depends on",
    "get_evidence": "the observations extracted from the log",
    "get_eliminated_layers": "which candidate causes were ruled out and why",
    "get_confidence_explanation": "why the confidence band is what it is, including the coverage cap",
    "get_runbook": "the full runbook: symptom, checks, fix, what not to do",
    "get_next_checks": "what to check next",
    "get_what_not_to_do": "actions to avoid",
    "find_related_incidents": "past incidents resembling this one",
    "get_previous_resolution": "what fixed the closest past incident, and whether it held",
    "get_incident_relationships": "how this incident connects to applications, teams, layers and hosts",
    "get_timing": "elapsed time, projected time, ceilings and throughput rate",
    "get_source_coverage": "which diagnostic sources are connected and which are not",
    "get_limitations": "what this investigation could not establish",
    "get_log_quality": "how well the application logs, and which logging practices are missing",
    "get_prevention": "what developers should change so this failure does not happen again",
}


def run_tools(names: list[str], ctx: DiagnosisContext) -> list[ToolResult]:
    """Execute an allowlisted set. Unknown names are dropped, never executed."""
    results: list[ToolResult] = []
    for name in dict.fromkeys(names):
        fn = TOOLS.get(name)
        if fn is None:
            continue
        try:
            results.append(fn(ctx))
        except Exception as exc:                    # a tool bug must not 500 the chat
            results.append(ToolResult(name, ok=False, source="",
                                      note=f"Tool failed: {type(exc).__name__}"))
    return results
