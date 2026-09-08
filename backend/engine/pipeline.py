"""Orchestration of stages 1-7.

Read this function to understand the whole tool. Stages 1 through 6 run with no
network, no credentials and no AI. Stage 7 is optional and additive.
"""

from __future__ import annotations

from typing import Any

from . import knowledge, log_quality, precedent, prevention, rules_engine, scorer, writer
from .models import Investigation
from .parser import parse


def investigate(
    log_text: str,
    *,
    force_all_connected: bool = False,
    use_ai: bool = True,
) -> Investigation:
    cfg = knowledge.load_config()
    topology = cfg["topology"]
    rules_cfg = cfg["rules"]
    runbooks = cfg["runbooks"]
    incidents = cfg["incidents"]

    # -- stages 1-3: text -> evidence -> derived facts -----------------------
    parsed = parse(log_text, topology)

    # -- stage 4: evidence -> layer (no AI) ---------------------------------
    rule, all_hits = rules_engine.evaluate(parsed.facts, rules_cfg)
    layer = rule.layer if rule else "Unknown"

    # -- stage 5: layer -> owner, runbook (key lookup, no AI) ---------------
    info = knowledge.layer_info(layer, topology)
    runbook_id, runbook = knowledge.runbook_for(layer, topology, runbooks)
    candidates = knowledge.candidate_layers(topology)
    sources = knowledge.source_status(topology, force_all_connected)

    eliminated: dict[str, str] = {}
    if rule:
        for name in rule.eliminates:
            if name in candidates and name != layer:
                eliminated[name] = rule.elimination_reasons.get(
                    name, "Ruled out by " + rule.rule_id
                )

    # -- stage 5b: precedent (no AI) ----------------------------------------
    precedents = precedent.find_precedents(parsed.facts, layer, incidents, topology)

    # -- stage 6: confidence (no AI) ----------------------------------------
    confidence = scorer.score(
        evidence=parsed.evidence,
        facts=parsed.facts,
        rule=rule,
        all_hits=all_hits,
        precedents=precedents,
        candidates=candidates,
        layer=layer,
        sources=sources,
    )

    # -- developer-facing, deterministic ------------------------------------
    quality = log_quality.assess(parsed, parsed.facts)
    prevent = prevention.build(runbook, parsed.facts)

    investigation = Investigation(
        layer=layer,
        layer_name=info.get("name", layer),
        owner=info.get("owner"),
        runbook_id=runbook_id,
        runbook=runbook,
        confidence=confidence,
        evidence=parsed.evidence,
        rule=rule,
        eliminated=eliminated,
        facts=parsed.facts,
        precedents=precedents,
        timing=_timing(parsed, topology),
        sources=sources,
        parse_warnings=parsed.warnings,
        log_quality=quality.to_dict(),
        prevention=prevent.to_dict(),
    )

    # -- stage 7: prose (the only AI) ---------------------------------------
    payload = investigation.to_dict()
    payload["system"] = topology.get("system", "")
    if use_ai:
        narrative, source, meta = writer.write(payload, topology)
    else:
        narrative, source, meta = writer._template(payload), "template", {}
    investigation.narrative = narrative
    investigation.narrative_source = source
    investigation.redactions = meta.get("redactions", [])
    investigation.prompt_sent = meta.get("prompt_sent")
    investigation.leak_check_passed = meta.get("leak_check_passed")

    return investigation


def _timing(parsed, topology: dict[str, Any]) -> dict[str, Any]:
    """Everything the timing ruler in the dashboard needs.

    The ruler is the signature visual: the ceiling that cut the call against
    the time the batch would actually have needed.
    """
    f = parsed.facts
    return {
        "record_count": f.get("record_count"),
        "elapsed_seconds": f.get("elapsed_seconds"),
        "projected_seconds": f.get("projected_seconds"),
        "ceiling_seconds": f.get("ceiling_seconds"),
        "client_timeout_seconds": f.get("client_timeout_seconds"),
        "seconds_per_record": f.get("observed_seconds_per_record"),
        "rate_source": f.get("rate_source"),
        "rate_basis": f.get("rate_basis"),
        "ceiling_hit": f.get("ceiling_hit"),
        "batches": [
            {
                "entity": b.entity,
                "records": b.record_count,
                "start": b.start,
                "end": b.end,
                "elapsed": b.elapsed,
                "ok": b.ok,
            }
            for b in parsed.batches
        ],
    }
