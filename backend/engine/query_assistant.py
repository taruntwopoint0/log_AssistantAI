"""Ask the Diagnosis: the conversational layer.

WHERE THE RELIABILITY BOUNDARY SITS
===================================
    Code decides what happened      rules_engine.py, scorer.py
    Graph explains what connects    graph.py
    Vector search finds what is similar   precedent.py
    The model understands the question and explains verified facts   here

In PROJECT mode the model receives nothing except the output of allowlisted
functions in query_tools.py. It cannot query anything, cannot reach the raw log,
and cannot alter the layer, the band, the evidence or the eliminations - those
arrive as finished text and leave as finished text. If the tools return nothing,
the answer says so rather than filling the gap from general knowledge.

In GENERAL mode the model answers ordinary technical questions from its own
knowledge, and is told explicitly not to present that as evidence about this
incident.

Everything degrades: with no API key, PROJECT mode still answers from the tool
results through a deterministic formatter. Only the phrasing is lost.

This module is Gemini-specific in exactly one function, _call_model, mirroring
writer.py. That is the whole surface that changes for the Azure OpenAI port.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from .query_tools import TOOL_DESCRIPTIONS, TOOLS, DiagnosisContext, ToolResult, run_tools
from .redaction import Redactor
from .writer import DEFAULT_MODEL, _sanitise

MAX_TOOLS = 4
MAX_HISTORY_TURNS = 6

# GENERAL mode is a conversation, not a lookup: it gets a longer memory and
# room for a real answer with formatting.
GENERAL_HISTORY_TURNS = 14
GENERAL_MAX_TOKENS = 4000

PROJECT_RULES = """You are answering questions about an internal incident investigation that has
already been completed by deterministic code.

The VERIFIED FACTS below are the only source you may use. They were produced by
allowlisted lookups against the project's own configuration and investigation output.

Rules, in order of importance:
1. Answer only from the VERIFIED FACTS. Treat them as authoritative and final.
2. Never use general knowledge to supply a project fact. Never invent a team,
   application, service, dependency, incident, evidence item, owner, resolution or
   relationship. If it is not in the facts below, you do not know it.
3. If the facts do not answer the question, say so plainly - for example
   "I don't have sufficient project evidence to determine that." Then say what you
   would need. Do not guess and do not offer a likely answer.
4. Never change or reinterpret the root cause, the confidence band, the evidence or
   the eliminated layers. Report them as given. Never recompute confidence.
5. Distinguish evidence from inference. If you are drawing a conclusion from the
   facts rather than quoting one, say so.
6. Be brief and direct. Two to five sentences unless a list is genuinely clearer.
   No headings, no markdown, no preamble.
7. Any all-caps placeholder in angle brackets, in the style of <EXAMPLE_1>, stands for
   a withheld identifier. Reproduce it character for character. Never expand or guess it.
"""

GENERAL_RULES = """You are a technical assistant helping a bank infrastructure engineer
work through a live incident.

An incident investigation is open and its findings are given below. Use them as the
subject of the conversation: answer general technical questions, but answer them about
THIS failure rather than in the abstract. If the engineer asks "how do I fix a 60s
timeout", they mean the one in front of them.

Be genuinely useful:
- Answer the actual question, at the depth it deserves.
- Use markdown freely: headings, bullets, numbered steps, tables, fenced code blocks.
- Be concrete. Name real tools, real defaults, real config keys, real commands.
- Reason from the incident facts. You may go beyond them using your own technical
  knowledge - that is the point of this mode.
- Follow up naturally across turns; the history is yours to use.

One rule about honesty, and it matters:
- The INCIDENT CONTEXT below was established by deterministic analysis. Treat it as
  fact and never contradict it.
- Anything you add from your own knowledge is a suggestion, not a finding. Where you
  are speculating, inferring or listing possibilities, say so in plain words -
  "likely", "worth checking", "I cannot confirm this from the investigation".
- Never invent a specific detail about this system: no hostnames, team names, config
  values, version numbers or past incidents that are not in the context below.
- Any all-caps placeholder in angle brackets, like <EXAMPLE_1>, is a withheld
  identifier. Reproduce it exactly; never expand or guess it.

If the investigation reached no conclusion, say so, then help anyway: work from the
evidence that was extracted and suggest what to check, clearly marked as suggestion.
"""


NO_CONTEXT_RULES = """You are a technical assistant helping a bank infrastructure engineer.

No incident investigation is open, so answer from your own technical knowledge. Be
accurate and concrete, and use markdown where it helps. Do not invent details about
any specific system.
"""

SELECTOR_RULES = """Choose which lookups will answer the user's question.

Available operations:
{catalogue}

Reply with ONLY a JSON array of operation names, at most {max_tools}, most relevant
first. No prose, no code fence. If nothing fits, reply with [].
"""


@dataclass
class Answer:
    answer: str
    mode: str
    grounded: bool
    tools_used: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    model_used: bool = False
    selector: str = ""            # "model" | "keywords" | "default" | "n/a"
    redactions: list[dict[str, str]] = field(default_factory=list)
    error: str = ""               # why the model was not used, when it was not

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer, "mode": self.mode, "grounded": self.grounded,
            "tools_used": self.tools_used, "sources": self.sources,
            "tool_results": self.tool_results, "model_used": self.model_used,
            "selector": self.selector, "redactions": self.redactions,
            "error": self.error,
        }


# --------------------------------------------------------------------------
# Tool selection
# --------------------------------------------------------------------------

_KEYWORD_ROUTES: list[tuple[tuple[str, ...], list[str]]] = [
    (("who owns", "owner", "which team", "responsible", "whose", "escalate"),
     ["get_owner", "get_application"]),
    (("application", "which app", "which system", "affected", "service", "worker"),
     ["get_application", "get_services"]),
    (("depend", "downstream", "upstream", "calls", "connected to", "talks to"),
     ["get_dependencies", "get_application"]),
    (("why did you", "why is this", "why classif", "how do you know", "root cause",
      "why gateway", "how did you", "justify", "reasoning"),
     ["get_diagnosis", "get_evidence", "get_eliminated_layers"]),
    (("confidence", "medium", "why not high", "band", "how sure", "certain", "cap"),
     ["get_confidence_explanation", "get_source_coverage"]),
    (("ruled out", "eliminat", "rule out", "not galileo", "why not"),
     ["get_eliminated_layers", "get_diagnosis"]),
    (("seen this before", "seen before", "past", "previous", "similar", "history",
      "happened before", "precedent"),
     ["find_related_incidents", "get_previous_resolution"]),
    (("what fixed", "fix it last", "resolution", "resolved", "how was it fixed"),
     ["get_previous_resolution", "get_runbook"]),
    (("what should i check", "check next", "next step", "what now", "how do i fix",
      "what do i do", "remediat"),
     ["get_next_checks", "get_runbook"]),
    (("not do", "avoid", "should i not", "mistake", "don't"),
     ["get_what_not_to_do", "get_runbook"]),
    (("how long", "elapsed", "seconds", "timing", "timeout", "ceiling", "duration",
      "throughput", "rate", "records"),
     ["get_timing", "get_evidence"]),
    (("source", "coverage", "connected", "monitoring", "visibility"),
     ["get_source_coverage", "get_confidence_explanation"]),
    (("evidence", "proof", "observ", "what did you see", "log show"),
     ["get_evidence", "get_diagnosis"]),
    (("limitation", "what don't you know", "unsure", "gap", "missing"),
     ["get_limitations", "get_source_coverage"]),
    (("relationship", "graph", "connect", "topology", "map"),
     ["get_incident_relationships", "get_dependencies"]),
    (("runbook", "procedure", "playbook"), ["get_runbook"]),
    (("prevent", "happen again", "recur", "avoid this", "stop this", "long term",
      "permanent fix", "root fix", "so it doesn't", "future"),
     ["get_prevention", "get_runbook"]),
    (("log quality", "logging", "log better", "instrument", "observability",
      "correlation id", "structured log", "what should we log"),
     ["get_log_quality", "get_prevention"]),
]

_DEFAULT_TOOLS = ["get_diagnosis", "get_evidence", "get_confidence_explanation"]


def keyword_match(question: str) -> list[str]:
    """Deterministic router. Empty when nothing matched, so the caller can tell
    a confident routing decision from a shrug."""
    q = question.lower()
    picked: list[str] = []
    for needles, tools in _KEYWORD_ROUTES:
        if any(n in q for n in needles):
            picked.extend(tools)
    return list(dict.fromkeys(picked))[:MAX_TOOLS]


def select_tools_by_keyword(question: str) -> list[str]:
    return keyword_match(question) or list(_DEFAULT_TOOLS)


def _parse_tool_list(raw: str) -> list[str]:
    """Extract a JSON array of names, tolerating fences and stray prose."""
    text = raw.strip()
    text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    # Allowlist. Anything the model invented is dropped here, not executed.
    return [n for n in parsed if isinstance(n, str) and n in TOOLS][:MAX_TOOLS]


def select_tools(question: str, api_key: str | None) -> tuple[list[str], str]:
    """Route the question to lookups.

    The deterministic router runs first. When it matches, the model is not
    consulted at all - that halves both the latency and the API spend for the
    common questions, and keeps routing reproducible. The model is asked only
    when the keywords shrug, which is exactly the case they cannot cover.
    """
    hits = keyword_match(question)
    if hits:
        return hits, "keywords"
    if not api_key:
        return list(_DEFAULT_TOOLS), "default"

    catalogue = "\n".join(f"- {n}: {d}" for n, d in TOOL_DESCRIPTIONS.items())
    prompt = (
        SELECTOR_RULES.format(catalogue=catalogue, max_tools=MAX_TOOLS)
        + f"\nUser question: {question}\n"
    )
    try:
        chosen = _parse_tool_list(_call_model(prompt, api_key, max_tokens=2000))
    except Exception:
        return list(_DEFAULT_TOOLS), "default"
    if not chosen:
        return list(_DEFAULT_TOOLS), "default"
    return chosen, "model"


# --------------------------------------------------------------------------
# Prompt assembly
# --------------------------------------------------------------------------

def _render_facts(results: list[ToolResult]) -> str:
    lines: list[str] = []
    for r in results:
        if r.ok:
            lines.append(f"[{r.tool}]  (source: {r.source})")
            if r.path:
                lines.append(f"  path: {' -> '.join(r.path)}")
            lines.append("  " + json.dumps(r.data, indent=2, default=str)
                         .replace("\n", "\n  "))
        else:
            lines.append(f"[{r.tool}]  NOT AVAILABLE - {r.note}")
        lines.append("")
    return "\n".join(lines)


def _render_history(history: list[dict[str, str]], limit: int = MAX_HISTORY_TURNS) -> str:
    if not history:
        return ""
    turns = history[-limit:]
    out = ["EARLIER IN THIS CONVERSATION:"]
    for t in turns:
        role = "User" if t.get("role") == "user" else "You"
        out.append(f"{role}: {t.get('content', '').strip()}")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Deterministic answering, used when there is no model
# --------------------------------------------------------------------------

def _template_answer(question: str, results: list[ToolResult]) -> str:
    """Format verified results without a model.

    A failed lookup is reported before anything else. Answering "who owns this
    failure" with the owner of the application, because that lookup happened to
    succeed, is the near-miss this project exists to avoid - so a gap is stated
    plainly and the rest is clearly labelled as adjacent, not as the answer.
    """
    ok = [r for r in results if r.ok]
    missing = [r for r in results if not r.ok]

    parts: list[str] = []
    if missing:
        parts.append(
            "I don't have sufficient project evidence to answer that fully. "
            + " ".join(r.note for r in missing if r.note)
        )
    if ok:
        facts = " | ".join(
            f"{r.tool.replace('get_', '').replace('_', ' ')}: " + _flatten(r.data)
            for r in ok
        )
        lead = "What I do have: " if missing else ""
        parts.append(lead + facts
                     + f"  (sources: {', '.join(dict.fromkeys(r.source for r in ok))})")
    if not parts:
        return ("I don't have sufficient project evidence to answer that. "
                "No configured lookup covers this question.")
    return " ".join(parts)


def _flatten(data: Any, depth: int = 0) -> str:
    if data is None:
        return "none"
    if isinstance(data, (str, int, float, bool)):
        return str(data)
    if isinstance(data, list):
        return "; ".join(_flatten(d, depth + 1) for d in data[:6])
    if isinstance(data, dict):
        return ", ".join(f"{k}={_flatten(v, depth + 1)}"
                         for k, v in list(data.items())[:8] if v not in (None, "", []))
    return str(data)


# --------------------------------------------------------------------------
# Model call - the only Gemini-specific code in this module
# --------------------------------------------------------------------------

def _call_model(prompt: str, api_key: str, max_tokens: int = 2000) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=max_tokens),
    )
    return (resp.text or "").strip()


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def ask(
    question: str,
    mode: str,
    ctx: DiagnosisContext | None,
    history: list[dict[str, str]] | None = None,
) -> Answer:
    question = (question or "").strip()
    mode = "GENERAL" if str(mode).upper() == "GENERAL" else "PROJECT"
    history = history or []
    api_key = os.environ.get("GEMINI_API_KEY", "").strip() or None

    if not question:
        return Answer(answer="Ask me something about this investigation.",
                      mode=mode, grounded=(mode == "PROJECT"), selector="n/a")

    if mode == "GENERAL":
        return _answer_general(question, history, api_key, ctx)
    return _answer_project(question, ctx, history, api_key)


def _answer_general(question: str, history: list[dict[str, str]],
                    api_key: str | None,
                    ctx: DiagnosisContext | None = None) -> Answer:
    if not api_key:
        return Answer(
            answer=("General mode needs a model, and no GEMINI_API_KEY is configured. "
                    "PROJECT mode still works without one."),
            mode="GENERAL", grounded=False, selector="n/a",
        )
    brief = _incident_brief(ctx)
    rules = GENERAL_RULES if brief else NO_CONTEXT_RULES
    raw_prompt = (rules + "\n" + brief + _render_history(history, GENERAL_HISTORY_TURNS)
                  + f"\nQuestion: {question}\n\nAnswer:")

    # Same containment as PROJECT mode and writer.py: internal identifiers are
    # tokenised on the way out and restored on the way back. The context makes
    # this mode more useful, so it must not make it leakier.
    redactor = Redactor.from_payload(
        {"runbook": (ctx.inv.get("runbook") if ctx else None),
         "precedents": (ctx.inv.get("precedents") if ctx else None)},
        ctx.topology if ctx else {}, scan_text=raw_prompt,
    )
    prompt = redactor.redact(raw_prompt)
    if redactor.leaked(prompt):
        return Answer(
            answer=("An internal identifier could not be masked, so the question was "
                    "not sent. Ask it in PROJECT mode instead."),
            mode="GENERAL", grounded=False, selector="n/a",
            error="leak check failed",
        )

    try:
        # Deliberately NOT _sanitise(): that strips headings, bullets, bold and
        # code fences, which is right for PROJECT's terse grounded prose and
        # wrong for a general assistant. The dashboard renders this as markdown,
        # escaping HTML first so model output can never become live markup.
        text = redactor.restore(
            _call_model(prompt, api_key, max_tokens=GENERAL_MAX_TOKENS).strip())
    except Exception as exc:
        return Answer(
            answer=("The model is unavailable right now. PROJECT mode still works "
                    "without one."),
            mode="GENERAL", grounded=False, selector="n/a",
            error=f"{type(exc).__name__}: {exc}"[:300],
        )
    return Answer(
        answer=text or "No answer was produced.", mode="GENERAL",
        grounded=False, model_used=True, selector="n/a",
        sources=["this investigation (as context)", "model general knowledge"]
                if brief else ["model general knowledge"],
        redactions=redactor.as_dicts(),
    )


def _incident_brief(ctx: DiagnosisContext | None) -> str:
    """A compact statement of what the engine concluded, for GENERAL mode.

    GENERAL exists so an engineer can reason around the incident with the
    model's own knowledge. Without the incident in front of it that reasoning
    is generic and nearly useless, so the conclusion is supplied as context.

    What separates this from PROJECT mode is not the data but the licence: here
    the model may go beyond the facts, and is required to say when it does.
    PROJECT mode may not go beyond them at all.
    """
    if ctx is None:
        return ""

    inv = ctx.inv
    c = inv.get("confidence") or {}
    lines = ["INCIDENT CONTEXT — established by deterministic analysis, treat as fact",
             f"System: {ctx.topology.get('system', 'unknown')}"]

    if ctx.diagnosed:
        lines.append(f"Cause: {inv.get('layer_name')} [{inv.get('layer')}]")
        if inv.get("owner"):
            lines.append(f"Owning team: {inv['owner']}")
    else:
        lines.append("Cause: NOT DETERMINED. The evidence matched no configured rule, "
                     "so the engine declined to name a cause.")
    lines.append(f"Confidence: {c.get('band')}")
    if c.get("cap_reason"):
        lines.append(f"Why the band is limited: {c['cap_reason']}")

    if inv.get("narrative"):
        lines += ["", "SUMMARY AS SHOWN TO THE ENGINEER:", inv["narrative"]]

    ev = inv.get("evidence") or []
    if ev:
        lines += ["", "EVIDENCE EXTRACTED FROM THE LOG:"]
        lines += [f"- {e['summary']}" for e in ev[:14]]

    t = inv.get("timing") or {}
    if t.get("elapsed_seconds") is not None:
        lines += ["", "TIMING: "
                  f"{t.get('record_count')} records, cut after {t['elapsed_seconds']:.0f}s"
                  + (f", would have needed about {t['projected_seconds']:.0f}s"
                     if t.get("projected_seconds") else "")]

    rb = inv.get("runbook") or {}
    if rb.get("fix"):
        lines += ["", f"PRESCRIBED FIX: {rb['fix']}"]
    if rb.get("do_not"):
        lines.append("MUST NOT DO: " + " ".join(rb["do_not"]))

    return "\n".join(lines) + "\n"


def _answer_project(question: str, ctx: DiagnosisContext | None,
                    history: list[dict[str, str]], api_key: str | None) -> Answer:
    if ctx is None:
        return Answer(
            answer="Run an investigation first. PROJECT mode answers only from a "
                   "completed investigation and the project configuration.",
            mode="PROJECT", grounded=True, selector="n/a",
        )

    names, selector = select_tools(question, api_key)
    results = run_tools(names, ctx)
    if not results:
        results = run_tools(_DEFAULT_TOOLS, ctx)
        selector = "keywords"

    sources = [r.source for r in results if r.ok and r.source]
    payload = [r.to_dict() for r in results]

    if not api_key:
        return Answer(
            answer=_template_answer(question, results), mode="PROJECT", grounded=True,
            tools_used=[r.tool for r in results], sources=sources,
            tool_results=payload, model_used=False, selector=selector,
        )

    facts = _render_facts(results)
    raw_prompt = (
        PROJECT_RULES + "\n" + _render_history(history)
        + "\nVERIFIED FACTS\n==============\n" + facts
        + f"\nUser question: {question}\n\nAnswer:"
    )

    # Same containment as writer.py: internal identifiers are tokenised on the
    # way out and restored on the way back.
    redactor = Redactor.from_payload(
        {"runbook": ctx.inv.get("runbook"), "precedents": ctx.inv.get("precedents")},
        ctx.topology, scan_text=raw_prompt,
    )
    prompt = redactor.redact(raw_prompt)
    if redactor.leaked(prompt):
        return Answer(
            answer=_template_answer(question, results), mode="PROJECT", grounded=True,
            tools_used=[r.tool for r in results], sources=sources,
            tool_results=payload, model_used=False, selector=selector,
        )

    try:
        text = _sanitise(redactor.restore(_call_model(prompt, api_key)))
    except Exception as exc:
        # The facts are already verified, so the answer degrades to the
        # deterministic formatter rather than disappearing.
        return Answer(
            answer=_template_answer(question, results), mode="PROJECT", grounded=True,
            tools_used=[r.tool for r in results], sources=sources,
            tool_results=payload, model_used=False, selector=selector,
            error=f"{type(exc).__name__}: {exc}"[:300],
        )

    return Answer(
        answer=text or _template_answer(question, results),
        mode="PROJECT", grounded=True, tools_used=[r.tool for r in results],
        sources=sources, tool_results=payload, model_used=bool(text),
        selector=selector, redactions=redactor.as_dicts(),
    )
