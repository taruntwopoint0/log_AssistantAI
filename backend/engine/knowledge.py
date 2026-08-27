"""Stage 5: config loading and key lookup.

Deliberately boring. Runbooks and topology are fetched by key, never retrieved
semantically. There is no index, no embedding and no similarity search here.
The tool knows which runbook applies because the rules engine named the layer,
and the layer names its runbook in topology.json.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(
    os.environ.get("INVESTIGATOR_CONFIG_DIR")
    or Path(__file__).resolve().parents[2] / "config"
)

_FILES = ("topology", "rules", "runbooks", "incidents")


def _read(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing config file {path}. All four of {_FILES} are required."
        )
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    return {name: _read(name) for name in _FILES}


def reload_config() -> dict[str, Any]:
    """Drop the cache. Used by the /api/config/reload endpoint so a rules.json
    edit takes effect without restarting the server."""
    load_config.cache_clear()
    return load_config()


def layer_info(layer_id: str, topology: dict[str, Any]) -> dict[str, Any]:
    for layer in topology.get("layers", []):
        if layer["id"] == layer_id:
            return layer
    return {
        "id": layer_id,
        "name": layer_id,
        "candidate": False,
        "owner": None,
        "runbook_id": None,
        "primary_source": None,
    }


def candidate_layers(topology: dict[str, Any]) -> list[str]:
    return [l["id"] for l in topology.get("layers", []) if l.get("candidate")]


def runbook_for(layer_id: str, topology: dict[str, Any], runbooks: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    rb_id = layer_info(layer_id, topology).get("runbook_id")
    if not rb_id:
        return None, None
    return rb_id, runbooks.get(rb_id)


def source_status(topology: dict[str, Any], force_all_connected: bool = False) -> list[dict[str, Any]]:
    """Source list with connection state.

    ``force_all_connected`` backs the dashboard toggle. It changes only the
    coverage cap, never the layer decision, which is the point of the demo:
    the same log produces the same root cause with a different band.
    """
    out = []
    for s in topology.get("sources", []):
        out.append({
            "id": s["id"],
            "name": s["name"],
            "checks": s.get("checks", ""),
            "connected": True if force_all_connected else bool(s.get("connected")),
            "configured_connected": bool(s.get("connected")),
        })
    return out
