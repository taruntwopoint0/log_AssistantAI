"""FastAPI surface over the engine.

READ-ONLY BY DESIGN. This service never restarts anything, never remediates,
and never writes to any system it is diagnosing. The only thing it writes is a
local prediction log used to measure its own accuracy.
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from engine import knowledge, query_assistant
from engine.graph import attach_investigation, build_static_graph
from engine.pipeline import investigate
from engine.query_tools import DiagnosisContext
from gen_mock_logs import LABELS, SCENARIOS

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PREDICTIONS_LOG = Path(
    os.environ.get("INVESTIGATOR_PREDICTION_LOG") or BASE_DIR / "predictions.jsonl"
)


def _load_dotenv(path: Path = BASE_DIR / ".env") -> None:
    """Read backend/.env into the environment if it exists.

    Bootstrap concern, deliberately kept out of engine/. A real environment
    variable always wins, so this never overrides a value set by the shell or
    by a deployment. The file is gitignored; the key must never be committed
    and never reaches the React page, which only ever sees rendered prose.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

app = FastAPI(
    title="AI Investigation Assistant",
    description=(
        "Deterministic log triage. Stages 1-6 decide the root cause with no AI. "
        "Stage 7 writes the summary paragraph and nothing else."
    ),
    version="1.0.0",
)


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------

class InvestigateRequest(BaseModel):
    log: str = Field(..., description="The pasted log block.")
    all_sources_connected: bool = Field(
        False,
        description=(
            "Demo toggle. Treats every diagnostic source as connected, which "
            "lifts the coverage cap. Never changes the layer decision."
        ),
    )
    use_ai: bool = Field(
        True,
        description="Set false to force the deterministic template summary.",
    )


class FeedbackRequest(BaseModel):
    prediction_id: str
    actual_layer: str
    was_correct: bool | None = None
    note: str = ""


class AskRequest(BaseModel):
    question: str = Field(..., description="The engineer's question.")
    prediction_id: str | None = Field(
        None,
        description="Which investigation to ground against. Required for PROJECT mode.",
    )
    mode: str = Field("PROJECT", description="PROJECT (grounded) or GENERAL (model knowledge).")
    history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Prior turns as {role, content}, for follow-up questions.",
    )


# --------------------------------------------------------------------------
# Investigation cache, so a chat turn never re-runs the pipeline
# --------------------------------------------------------------------------

_INVESTIGATIONS: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_MAX_CACHED = 50


def _cache_investigation(prediction_id: str, payload: dict[str, Any]) -> None:
    _INVESTIGATIONS[prediction_id] = payload
    while len(_INVESTIGATIONS) > _MAX_CACHED:
        _INVESTIGATIONS.popitem(last=False)


def _context_for(prediction_id: str | None) -> DiagnosisContext | None:
    """Build the DiagnosisContext the conversational layer is allowed to see."""
    if not prediction_id:
        return None
    payload = _INVESTIGATIONS.get(prediction_id)
    if payload is None:
        return None
    cfg = knowledge.load_config()
    graph = attach_investigation(
        build_static_graph(cfg), payload, cfg["topology"]
    )
    return DiagnosisContext(
        investigation=payload,
        graph=graph,
        topology=cfg["topology"],
        runbooks=cfg["runbooks"],
        incidents=cfg["incidents"],
    )


# --------------------------------------------------------------------------
# Prediction log - so accuracy per band is measurable rather than asserted
# --------------------------------------------------------------------------

def _record_prediction(inv, request: InvestigateRequest) -> str:
    prediction_id = uuid4().hex[:12]
    row = {
        "prediction_id": prediction_id,
        "at": datetime.now(timezone.utc).isoformat(),
        "predicted_layer": inv.layer,
        "band": inv.confidence.band,
        "raw_band": inv.confidence.raw_band,
        "raw_score": inv.confidence.raw_score,
        "rule_id": inv.rule.rule_id if inv.rule else None,
        "coverage": inv.confidence.coverage,
        "all_sources_connected": request.all_sources_connected,
        "narrative_source": inv.narrative_source,
        "log_chars": len(request.log),
        "actual_layer": None,
        "was_correct": None,
        "note": "",
    }
    try:
        with PREDICTIONS_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        # Never fail an investigation because the log could not be written.
        pass
    return prediction_id


def _read_predictions() -> list[dict[str, Any]]:
    if not PREDICTIONS_LOG.exists():
        return []
    rows: list[dict[str, Any]] = []
    with PREDICTIONS_LOG.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    # Later rows for the same prediction_id supersede earlier ones.
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest[row.get("prediction_id", uuid4().hex)] = {
            **latest.get(row.get("prediction_id", ""), {}),
            **row,
        }
    return list(latest.values())


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def index():
    page = STATIC_DIR / "index.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    return FileResponse(page)


@app.get("/api/health")
def health():
    cfg = knowledge.load_config()
    return {
        "status": "ok",
        "config_dir": str(knowledge.CONFIG_DIR),
        "rules": len(cfg["rules"].get("rules", [])),
        "runbooks": len(cfg["runbooks"]) - 0,
        "incidents": len(cfg["incidents"].get("incidents", [])),
        "sources_connected": sum(
            1 for s in cfg["topology"].get("sources", []) if s.get("connected")
        ),
        "sources_total": len(cfg["topology"].get("sources", [])),
        "ai_configured": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "ai_model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    }


@app.post("/api/investigate")
def api_investigate(req: InvestigateRequest):
    if not req.log.strip():
        raise HTTPException(status_code=400, detail="No log text supplied.")

    inv = investigate(
        req.log,
        force_all_connected=req.all_sources_connected,
        use_ai=req.use_ai,
    )
    payload = inv.to_dict()
    payload["prediction_id"] = _record_prediction(inv, req)
    _cache_investigation(payload["prediction_id"], payload)
    return JSONResponse(payload)


@app.post("/api/ask")
def api_ask(req: AskRequest):
    """Ask the Diagnosis.

    PROJECT mode answers only from allowlisted lookups against this
    investigation and the project config. GENERAL mode answers ordinary
    technical questions from the model's own knowledge and is told not to
    present that as evidence about this incident.

    The model never decides the root cause, the band, the evidence or the
    eliminations. It selects a lookup; the backend runs it.
    """
    mode = (req.mode or "PROJECT").upper()
    ctx = _context_for(req.prediction_id) if mode == "PROJECT" else None

    if mode == "PROJECT" and ctx is None:
        raise HTTPException(
            status_code=400,
            detail=("PROJECT mode needs a completed investigation. Run one first, or "
                    "switch to GENERAL mode for general technical questions."),
        )

    answer = query_assistant.ask(req.question, mode, ctx, req.history)
    return JSONResponse(answer.to_dict())


@app.get("/api/tools")
def api_tools():
    """The complete set of lookups the model may choose from. Nothing else exists."""
    from engine.query_tools import TOOL_DESCRIPTIONS
    return {"tools": [{"name": n, "does": d} for n, d in TOOL_DESCRIPTIONS.items()]}


@app.get("/api/graph/{prediction_id}")
def api_graph(prediction_id: str):
    """The knowledge graph around one investigation, for inspection."""
    ctx = _context_for(prediction_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Unknown prediction_id.")
    from engine.graph import CURRENT
    return {
        "nodes": len(ctx.graph.nodes),
        "edges": len(ctx.graph.edges),
        "relationships": ctx.graph.relations(CURRENT),
    }


@app.get("/api/samples")
def api_samples():
    return [
        {"id": name, "label": LABELS.get(name, name), "chars": len(text)}
        for name, text in SCENARIOS.items()
    ]


@app.get("/api/samples/{name}")
def api_sample(name: str):
    if name not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"No sample named {name!r}.")
    return {"id": name, "label": LABELS.get(name, name), "log": SCENARIOS[name]}


@app.get("/api/config")
def api_config():
    cfg = knowledge.load_config()
    topology = cfg["topology"]
    return {
        "system": topology.get("system"),
        "owner_team": topology.get("owner_team"),
        "sources": knowledge.source_status(topology),
        "layers": topology.get("layers", []),
        "rules": [
            {
                "id": r["id"],
                "layer": r["layer"],
                "title": r.get("title", ""),
                "specificity": r.get("specificity"),
                "priority": r.get("priority"),
            }
            for r in cfg["rules"].get("rules", [])
        ],
        "incident_count": len(cfg["incidents"].get("incidents", [])),
    }


@app.post("/api/config/reload")
def api_config_reload():
    """Pick up edits to the four JSON files without restarting the server.

    This is the portability story made testable: change rules.json, reload,
    and the tool behaves differently with no code change.
    """
    cfg = knowledge.reload_config()
    return {
        "reloaded": True,
        "rules": len(cfg["rules"].get("rules", [])),
        "incidents": len(cfg["incidents"].get("incidents", [])),
    }


@app.post("/api/feedback")
def api_feedback(req: FeedbackRequest):
    """Attach the true root cause to a past prediction.

    This is what turns 'it felt accurate' into an accuracy figure per band.
    """
    rows = _read_predictions()
    match = next((r for r in rows if r["prediction_id"] == req.prediction_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Unknown prediction_id.")

    was_correct = (
        req.was_correct
        if req.was_correct is not None
        else match["predicted_layer"] == req.actual_layer
    )
    update = {
        **match,
        "actual_layer": req.actual_layer,
        "was_correct": was_correct,
        "note": req.note,
        "feedback_at": datetime.now(timezone.utc).isoformat(),
    }
    with PREDICTIONS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(update) + "\n")
    return {"recorded": True, "was_correct": was_correct}


@app.get("/api/accuracy")
def api_accuracy():
    """Accuracy per confidence band, over predictions that have feedback.

    A band is only meaningful if High is right more often than Medium. This is
    the endpoint that proves or disproves that.
    """
    rows = [r for r in _read_predictions() if r.get("actual_layer")]
    bands: dict[str, dict[str, int]] = {}
    for r in rows:
        b = bands.setdefault(r["band"], {"total": 0, "correct": 0})
        b["total"] += 1
        if r.get("was_correct"):
            b["correct"] += 1

    return {
        "scored_predictions": len(rows),
        "total_predictions": len(_read_predictions()),
        "by_band": {
            band: {
                **counts,
                "accuracy": round(counts["correct"] / counts["total"], 3)
                if counts["total"]
                else None,
            }
            for band, counts in sorted(bands.items())
        },
    }
