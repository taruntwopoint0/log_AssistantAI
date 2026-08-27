"""Stage 7: turn a finished decision into prose. THE ONLY AI IN THE PIPELINE.

By the time this module runs, the layer, the band, the evidence, the
eliminations and the runbook are already decided by stages 1-6. Nothing here
can change any of them. The model receives the conclusion as a given and is
asked to phrase it.

That is the whole reliability argument. If the model hallucinates, the result
is an awkward sentence next to a correct structured answer. If the model is
unavailable, ``_template()`` runs instead and the tool loses a paragraph and
nothing else. The dashboard renders the structured fields directly and never
parses this text.

This is also the only file that changes for the production port. Swap
``_call_gemini`` for the approved Azure OpenAI endpoint and the rest of the
engine is untouched.
"""

from __future__ import annotations

import os
import re
from typing import Any

from .redaction import Redactor

DEFAULT_MODEL = "gemini-3.5-flash-lite"
MAX_NARRATIVE_CHARS = 1400

SYSTEM_RULES = """You are writing the summary paragraph of an incident triage report for
bank infrastructure engineers.

Every fact below has already been established by deterministic analysis. Your job is
phrasing only.

Hard rules:
- Do not change, hedge, or re-derive the stated cause. State it as given.
- Do not introduce any system, component, cause, metric or number that is not listed below.
- Do not output a confidence percentage. The band is a word and is given to you.
- Do not recommend anything beyond the stated fix.
- If the cause is Unknown, say plainly that the evidence matched no known pattern and
  do not speculate about what it might be.
- 3 to 5 sentences. Plain prose, no headings, no bullet points, no markdown.
- Direct and concrete, no filler. Assume a tired on-call engineer is reading.
- Open with the cause. Do not set a scene, and never state a time of day that is
  not one of the timestamps given to you.
- Any all-caps placeholder in angle brackets, in the style of <EXAMPLE_1>, stands for
  an identifier that was withheld. Reproduce it character for character. Never expand
  one, translate it, guess what it stands for, or invent a new one.
"""


def write(
    payload: dict[str, Any],
    topology: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Return (narrative, source, meta).

    ``source`` is 'gemini' or 'template'. ``meta`` records exactly what left the
    machine: the token map and the verbatim prompt sent. Both are local-only and
    exist so the transparency claim can be shown rather than asserted.
    """
    empty_meta: dict[str, Any] = {
        "redactions": [], "prompt_sent": None, "leak_check_passed": None,
    }

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return _template(payload), "template", empty_meta

    raw_prompt = _build_prompt(payload)
    redactor = Redactor.from_payload(payload, topology or {}, scan_text=raw_prompt)
    prompt = redactor.redact(raw_prompt)

    # Belt and braces. If anything survived the token map, do not send at all -
    # fall back to the template rather than leak an internal identifier.
    leaked = redactor.leaked(prompt)
    if leaked:
        return _template(payload), "template", {
            "redactions": redactor.as_dicts(),
            "prompt_sent": None,
            "leak_check_passed": False,
            "blocked_identifiers": leaked,
        }

    meta = {
        "redactions": redactor.as_dicts(),
        "prompt_sent": prompt,
        "leak_check_passed": True,
    }

    try:
        text = _call_gemini(prompt, api_key)
    except Exception:
        # Any failure at all - missing SDK, bad key, network, quota, safety
        # block - falls back silently. The tool must not depend on this stage.
        return _template(payload), "template", meta

    text = _sanitise(redactor.restore(text))
    if not text:
        return _template(payload), "template", meta
    return text, "gemini", meta


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------

def _build_prompt(p: dict[str, Any]) -> str:
    conf = p["confidence"]
    lines = [
        SYSTEM_RULES,
        "",
        "ESTABLISHED FACTS",
        f"System: {p.get('system', 'BulkSuppliers Supplier Sync')}",
        f"Cause (decided by rules engine, not by you): {p['layer_name']} [{p['layer']}]",
        f"Confidence band (decided by scoring, not by you): {conf['band']}",
    ]

    if conf.get("cap_reason"):
        lines.append(f"Why the band is limited: {conf['cap_reason']}")

    if p.get("owner"):
        lines.append(f"Owning team: {p['owner']}")

    lines.append("")
    lines.append("EVIDENCE (use only these):")
    for e in p.get("evidence", []):
        lines.append(f"- {e['summary']}")

    eliminated = p.get("eliminated") or {}
    if eliminated:
        lines.append("")
        lines.append("RULED OUT (and why):")
        for layer, reason in eliminated.items():
            lines.append(f"- {layer}: {reason}")

    precedents = p.get("precedents") or []
    if precedents:
        best = precedents[0]
        lines.append("")
        lines.append(
            f"PRECEDENT: {best['incident_id']} on {best['date']}, "
            f"{best['similarity']:.0%} similar. {best['title']}. "
            f"Resolution: {best['resolution']} "
            f"The fix {'held' if best['fix_held'] else 'did not hold'}."
        )

    runbook = p.get("runbook") or {}
    if runbook.get("fix"):
        lines.append("")
        lines.append(f"PRESCRIBED FIX: {runbook['fix']}")
    if runbook.get("do_not"):
        lines.append("MUST NOT DO: " + " ".join(runbook["do_not"]))

    lines.append("")
    lines.append("Write the summary paragraph now.")
    return "\n".join(lines)


def _call_gemini(prompt: str, api_key: str) -> str:
    from google import genai
    from google.genai import types

    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=400,
        ),
    )
    return (resp.text or "").strip()


def _sanitise(text: str) -> str:
    """Strip formatting the model was told not to use, and cap the length.

    A model that ignores the instructions produces a badly formatted paragraph,
    not a wrong diagnosis, so this only tidies.
    """
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*•]\s*", "", text, flags=re.MULTILINE)
    text = text.replace("**", "").replace("`", "")
    text = re.sub(r"\n{2,}", "\n\n", text).strip()
    if len(text) > MAX_NARRATIVE_CHARS:
        cut = text[:MAX_NARRATIVE_CHARS]
        text = cut[: cut.rfind(".") + 1] if "." in cut else cut
    return text


# --------------------------------------------------------------------------
# Deterministic fallback
# --------------------------------------------------------------------------

def _template(p: dict[str, Any]) -> str:
    conf = p["confidence"]
    layer = p["layer"]
    facts = p.get("facts") or {}
    parts: list[str] = []

    if layer == "Unknown":
        checked = len(p.get("evidence", []))
        return (
            f"The evidence in this log matches no rule currently configured, so no "
            f"cause is being claimed. {checked} observation(s) were extracted and "
            f"none of them pinned a layer. Confidence is {conf['band']}. Run the "
            f"manual source checklist, and once the true cause is known add a rule "
            f"to config/rules.json so the next occurrence is recognised."
        )

    if layer == "Healthy":
        rc = facts.get("record_count")
        return (
            f"No failure was found in this log. "
            + (f"{rc} record(s) synced and every batch returned successfully. " if rc else "")
            + f"Confidence is {conf['band']}. "
            + (conf.get("cap_reason") or "")
        ).strip()

    # --- the failure case ---
    opening = f"The failure is at the {p['layer_name'].lower()} layer"
    if p.get("owner"):
        opening += f", owned by {p['owner']}"
    parts.append(opening + ".")

    rationale = (p.get("rule") or {}).get("rationale")
    if rationale:
        parts.append(rationale)

    key = [e["summary"] for e in p.get("evidence", []) if e.get("derived")][:3]
    if not key:
        key = [e["summary"] for e in p.get("evidence", [])][:3]
    if key:
        parts.append("The evidence: " + "; ".join(key) + ".")

    eliminated = p.get("eliminated") or {}
    if eliminated:
        names = list(eliminated)[:3]
        parts.append(
            f"Ruled out: {', '.join(names)}"
            + (f" and {len(eliminated) - len(names)} other layer(s)" if len(eliminated) > len(names) else "")
            + "."
        )

    precedents = p.get("precedents") or []
    if precedents:
        best = precedents[0]
        parts.append(
            f"This closely resembles {best['incident_id']} on {best['date']} "
            f"({best['similarity']:.0%} similar), where the fix "
            f"{'held' if best['fix_held'] else 'did not hold'}."
        )

    runbook = p.get("runbook") or {}
    if runbook.get("fix"):
        parts.append(runbook["fix"])

    parts.append(f"Confidence is {conf['band']}.")
    if conf.get("cap_reason"):
        parts.append(conf["cap_reason"])

    return " ".join(parts)
