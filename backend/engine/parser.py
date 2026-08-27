"""Stages 1-3: raw text -> log lines -> blocks -> typed evidence -> derived facts.

No network, no credentials, no AI. Pure regex and arithmetic, so the whole
decision path underneath it is unit testable offline.

Serilog output varies with sink configuration, so the header matcher accepts
every layout we have seen in the wild rather than one canonical form:

    11:20:07 INF message
    [11:20:07 INF] message
    2026-08-18 11:20:07.123 +05:30 [INF] message
    2026-08-18T11:20:07.1234567Z INF message
    2026-08-18 11:20:07.123 INF message
    11:20:07 [Information] message

A line that does not match a header is a continuation of the block above it.
That rule is what keeps a multi-line .NET stack trace attached to its ERR line.

FACT VOCABULARY produced by ``derive_facts`` and consumed by rules.json:

    has_error                    bool
    error_count                  int
    error_time                   str | None  HH:MM:SS of the first error block
    exception_types              list[str]   short names, outermost first
    error_text                   str         lowercased text of all error blocks
    http_status                  int | None
    endpoint_url                 str | None
    endpoint_host                str | None
    record_count                 int | None  failing batch, else sum of batches
    elapsed_seconds              float | None
    observed_seconds_per_record  float | None
    rate_source                  'observed' | 'baseline' | None
    projected_seconds            float | None
    projection_exceeds_elapsed   bool
    ceiling_seconds              float | None
    ceiling_hit                  bool
    small_batches_succeeded      bool
    success_count                int
    failure_count                int
    service_state                str | None
    client_timeout_seconds       float
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from .models import Evidence, LogBlock, LogLine

# --------------------------------------------------------------------------
# Stage 1: line and block recognition
# --------------------------------------------------------------------------

_LEVELS = (
    "VERBOSE|INFORMATION|WARNING|TRACE|DEBUG|FATAL|ERROR|INFO|WARN|"
    "VRB|DBG|INF|WRN|ERR|FTL|TRC"
)

HEADER_RE = re.compile(
    r"^\s*"
    r"(?:\[\s*)?"
    r"(?:(?P<date>\d{4}[-/]\d{2}[-/]\d{2})[T ]\s*)?"
    r"(?P<time>\d{2}:\d{2}:\d{2})"
    r"(?:[.,](?P<frac>\d{1,7}))?"
    r"(?:\s*(?P<tz>Z|[+-]\d{2}:?\d{2}))?"
    r"\s*\]?"
    r"\s*[\[<(]?\s*"
    r"(?P<level>" + _LEVELS + r")"
    r"\s*[\]>)]?"
    r"\s*:?\s*"
    r"(?P<msg>.*)$",
    re.IGNORECASE,
)

_LEVEL_CANON = {
    "VERBOSE": "VRB", "VRB": "VRB", "TRACE": "VRB", "TRC": "VRB",
    "DEBUG": "DBG", "DBG": "DBG",
    "INFORMATION": "INF", "INFO": "INF", "INF": "INF",
    "WARNING": "WRN", "WARN": "WRN", "WRN": "WRN",
    "ERROR": "ERR", "ERR": "ERR",
    "FATAL": "FTL", "FTL": "FTL",
}


def parse_lines(text: str) -> list[LogLine]:
    lines: list[LogLine] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        m = HEADER_RE.match(raw)
        if m and _looks_like_header(m, raw):
            lines.append(
                LogLine(
                    line_no=i,
                    raw=raw,
                    time=m.group("time"),
                    date=m.group("date"),
                    level=_LEVEL_CANON[m.group("level").upper()],
                    message=m.group("msg").strip(),
                    is_header=True,
                )
            )
        else:
            lines.append(LogLine(line_no=i, raw=raw, is_header=False))
    return lines


def _looks_like_header(m: re.Match, raw: str) -> bool:
    """Reject false positives from inside stack traces.

    A trace line such as ``at Foo.Bar() in C:\\src\\File.cs:line 59`` can carry
    something time-shaped. A real header starts at column zero or near it.
    """
    return len(raw) - len(raw.lstrip()) <= 3


def build_blocks(lines: list[LogLine]) -> tuple[list[LogBlock], list[str]]:
    blocks: list[LogBlock] = []
    warnings: list[str] = []
    current: LogBlock | None = None
    orphan_lines = 0

    for ln in lines:
        if ln.is_header:
            current = LogBlock(
                line_no=ln.line_no,
                time=ln.time,
                date=ln.date,
                level=ln.level or "INF",
                message=ln.message or "",
            )
            blocks.append(current)
        elif current is not None:
            if ln.raw.strip():
                current.continuation.append(ln.raw.rstrip())
        elif ln.raw.strip():
            orphan_lines += 1

    if orphan_lines:
        warnings.append(
            f"{orphan_lines} line(s) before the first recognised timestamp were ignored."
        )
    if not blocks:
        warnings.append(
            "No Serilog header line was recognised. Check the sink's output template "
            "against the formats listed in engine/parser.py."
        )
    return blocks, warnings


# --------------------------------------------------------------------------
# Stage 2: evidence extraction
# --------------------------------------------------------------------------

RECORDS_RE = re.compile(
    r"total\s+records\s+fetched\s+for\s+(?P<entity>.+?)\s*[:=]\s*(?P<count>\d+)", re.I
)
RECORDS_GENERIC_RE = re.compile(
    r"(?:fetched|retrieved|processing|synced)\s+(?P<count>\d+)\s+record", re.I
)
STARTED_RE = re.compile(r"(?P<entity>.+?)\s+sync(?:ed|ing)?\s+started", re.I)
COMPLETED_RE = re.compile(
    r"(?P<entity>.+?)\s+sync(?:ed|ing)?\s+(?:completed|finished|succeeded)", re.I
)
EXCEPTION_RE = re.compile(
    r"\b(?:[A-Za-z_][A-Za-z0-9_]*\.)*(?P<name>[A-Za-z_][A-Za-z0-9_]*Exception)\b"
)
URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")
STATUS_DOTNET_RE = re.compile(
    r"response\s+status\s+code\s+does\s+not\s+indicate\s+success\s*:\s*(?P<code>\d{3})", re.I
)
STATUS_LABELLED_RE = re.compile(
    r"status(?:\s*code)?\s*[:=]?\s*(?P<code>\d{3})\b", re.I
)
STATUS_PHRASE_RE = re.compile(
    r"\b(?P<code>\d{3})\s*[-\u2013]?\s*"
    r"(?:unauthorized|forbidden|bad\s+gateway|service\s+unavailable|gateway\s+time-?out|"
    r"not\s+found|internal\s+server\s+error)\b",
    re.I,
)
_PHRASE_TO_STATUS = {
    "unauthorized": 401,
    "forbidden": 403,
    "not found": 404,
    "internal server error": 500,
    "bad gateway": 502,
    "service unavailable": 503,
    "gateway timeout": 504,
    "gateway time-out": 504,
}
SERVICE_STATE_RE = re.compile(
    r"service\s+['\"]?(?P<name>[\w.\- ]+?)['\"]?\s+is\s+(?P<state>Stopped|Running|StartPending|StopPending|Paused)\b",
    re.I,
)
SERVICE_TERMINATED_RE = re.compile(
    r"service\s+terminated\s+unexpectedly|entered\s+the\s+stopped\s+state", re.I
)
_STATE_CANON = {
    "stopped": "Stopped", "running": "Running", "startpending": "StartPending",
    "stoppending": "StopPending", "paused": "Paused",
}


@dataclass
class Batch:
    entity: str
    line_no: int
    record_count: int | None = None
    start: str | None = None
    end: str | None = None
    ok: bool | None = None
    elapsed: float | None = None


@dataclass
class ParseResult:
    blocks: list[LogBlock]
    evidence: list[Evidence] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    batches: list[Batch] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _to_seconds(hhmmss: str | None) -> int | None:
    if not hhmmss:
        return None
    try:
        h, m, s = (int(p) for p in hhmmss.split(":"))
    except ValueError:
        return None
    return h * 3600 + m * 60 + s


def _elapsed(start: str | None, end: str | None) -> float | None:
    a, b = _to_seconds(start), _to_seconds(end)
    if a is None or b is None:
        return None
    delta = b - a
    if delta < 0:                      # run crossed midnight
        delta += 86400
    return float(delta)


def _norm_entity(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip(" .:-").lower()


def extract(blocks: list[LogBlock], topology: dict[str, Any]) -> ParseResult:
    result = ParseResult(blocks=blocks)
    ev = result.evidence
    batches: dict[str, Batch] = {}
    order: list[str] = []
    exception_types: list[str] = []
    error_texts: list[str] = []
    http_status: int | None = None
    endpoint_url: str | None = None
    service_state: str | None = None
    error_blocks: list[LogBlock] = []

    for block in blocks:
        text = block.text
        low = text.lower()

        # ---- record counts -------------------------------------------------
        m = RECORDS_RE.search(block.message)
        if m:
            key = _norm_entity(m.group("entity"))
            b = batches.setdefault(key, Batch(entity=m.group("entity").strip(), line_no=block.line_no))
            if key not in order:
                order.append(key)
            b.record_count = int(m.group("count"))
            ev.append(Evidence(
                kind="record_count",
                summary=f"{b.record_count} records fetched for {b.entity}",
                source="database_views",
                line_no=block.line_no, time=block.time, value=b.record_count,
            ))
        else:
            m = RECORDS_GENERIC_RE.search(block.message)
            if m:
                key = "batch"
                b = batches.setdefault(key, Batch(entity="batch", line_no=block.line_no))
                if key not in order:
                    order.append(key)
                b.record_count = int(m.group("count"))
                ev.append(Evidence(
                    kind="record_count",
                    summary=f"{b.record_count} records in batch",
                    source="database_views",
                    line_no=block.line_no, time=block.time, value=b.record_count,
                ))

        # ---- batch start / completion --------------------------------------
        m = STARTED_RE.search(block.message)
        if m and block.level == "INF":
            key = _norm_entity(m.group("entity"))
            b = batches.setdefault(key, Batch(entity=m.group("entity").strip(), line_no=block.line_no))
            if key not in order:
                order.append(key)
            b.start = block.time

        m = COMPLETED_RE.search(block.message)
        if m and block.level in ("INF", "WRN"):
            key = _norm_entity(m.group("entity"))
            b = batches.setdefault(key, Batch(entity=m.group("entity").strip(), line_no=block.line_no))
            if key not in order:
                order.append(key)
            b.end = block.time
            b.ok = True
            b.elapsed = _elapsed(b.start, b.end)
            if b.elapsed is not None and b.record_count:
                ev.append(Evidence(
                    kind="batch_success",
                    summary=(
                        f"{b.record_count} records for {b.entity} completed in "
                        f"{b.elapsed:.0f}s"
                    ),
                    source="ald_sat",
                    line_no=block.line_no, time=block.time,
                    value={"records": b.record_count, "elapsed": b.elapsed},
                ))

        # ---- service state -------------------------------------------------
        m = SERVICE_STATE_RE.search(text)
        if m:
            service_state = _STATE_CANON.get(m.group("state").lower(), m.group("state"))
            ev.append(Evidence(
                kind="service_state",
                summary=f"Service {m.group('name').strip()} is {service_state}",
                source="windows_service",
                line_no=block.line_no, time=block.time, value=service_state,
            ))
        elif SERVICE_TERMINATED_RE.search(text):
            service_state = "Stopped"
            ev.append(Evidence(
                kind="service_state",
                summary="Worker service terminated unexpectedly",
                source="windows_service",
                line_no=block.line_no, time=block.time, value="Stopped",
            ))

        # ---- errors --------------------------------------------------------
        if block.is_error:
            error_blocks.append(block)
            error_texts.append(low)

            for em in EXCEPTION_RE.finditer(text):
                name = em.group("name")
                if name not in exception_types:
                    exception_types.append(name)

            if http_status is None:
                http_status = _find_status(text)

            um = URL_RE.search(text)
            if um and endpoint_url is None:
                endpoint_url = um.group(0).rstrip('":,')

            # attach this failure to the most recent started, unfinished batch
            for key in reversed(order):
                b = batches[key]
                if b.start and b.ok is None:
                    b.ok = False
                    b.end = block.time
                    b.elapsed = _elapsed(b.start, b.end)
                    break

    # ---- error-derived evidence ---------------------------------------------
    if exception_types:
        ev.append(Evidence(
            kind="exception_chain",
            summary="Exception chain: " + " -> ".join(exception_types),
            source="app_logs",
            line_no=error_blocks[0].line_no if error_blocks else None,
            time=error_blocks[0].time if error_blocks else None,
            value=exception_types,
        ))

    inner = _inner_symptom(error_texts)
    if inner:
        ev.append(Evidence(
            kind="inner_symptom",
            summary=f"Inner symptom: {inner}",
            source="app_logs",
            line_no=error_blocks[0].line_no if error_blocks else None,
            time=error_blocks[0].time if error_blocks else None,
            value=inner,
        ))

    if http_status is not None:
        ev.append(Evidence(
            kind="http_status",
            summary=f"Endpoint returned HTTP {http_status}",
            source="ald_sat",
            value=http_status,
        ))

    endpoint_host = None
    if endpoint_url:
        endpoint_host = urlparse(endpoint_url).netloc or None
        host_meta = (topology.get("hosts") or {}).get(endpoint_host or "", {})
        ev.append(Evidence(
            kind="endpoint",
            summary=f"Target host {endpoint_host}"
                    + (f" ({host_meta['role']})" if host_meta.get("role") else ""),
            source=host_meta.get("source", "ald_sat"),
            value=endpoint_url,
        ))

    result.batches = [batches[k] for k in order]
    result.facts = _assemble_facts(
        result, topology,
        exception_types=exception_types,
        error_texts=error_texts,
        http_status=http_status,
        endpoint_url=endpoint_url,
        endpoint_host=endpoint_host,
        service_state=service_state,
        error_blocks=error_blocks,
    )
    return result


def _find_status(text: str) -> int | None:
    m = STATUS_DOTNET_RE.search(text)
    if m:
        return int(m.group("code"))
    m = STATUS_PHRASE_RE.search(text)
    if m:
        return int(m.group("code"))
    m = STATUS_LABELLED_RE.search(text)
    if m:
        code = int(m.group("code"))
        if 100 <= code <= 599:
            return code
    low = text.lower()
    for phrase, code in _PHRASE_TO_STATUS.items():
        if phrase in low:
            return code
    return None


_INNER_SYMPTOMS = (
    "the response ended prematurely",
    "connection refused",
    "no such host is known",
    "actively refused",
    "login failed for user",
    "pool size was reached",
    "timeout expired",
    "unhandled exception",
    "the operation was canceled",
    "ssl connection could not be established",
)


def _inner_symptom(error_texts: list[str]) -> str | None:
    joined = "\n".join(error_texts)
    for phrase in _INNER_SYMPTOMS:
        if phrase in joined:
            return phrase
    return None


# --------------------------------------------------------------------------
# Stage 3: derived facts
# --------------------------------------------------------------------------

def _assemble_facts(
    result: ParseResult,
    topology: dict[str, Any],
    *,
    exception_types: list[str],
    error_texts: list[str],
    http_status: int | None,
    endpoint_url: str | None,
    endpoint_host: str | None,
    service_state: str | None,
    error_blocks: list[LogBlock],
) -> dict[str, Any]:
    ev = result.evidence
    batches = result.batches
    failed = [b for b in batches if b.ok is False]
    succeeded = [b for b in batches if b.ok is True]

    # record count: the failing batch if there is one, else the sum of batches
    if failed and failed[0].record_count is not None:
        record_count = failed[0].record_count
    else:
        counts = [b.record_count for b in batches if b.record_count is not None]
        record_count = sum(counts) if counts else None

    elapsed = next((b.elapsed for b in failed if b.elapsed is not None), None)
    if elapsed is not None:
        ev.append(Evidence(
            kind="elapsed",
            summary=f"Failure arrived {elapsed:.0f}s after the batch started",
            source="app_logs", derived=True, value=elapsed,
            time=failed[0].end, line_no=failed[0].line_no,
        ))

    # throughput rate: prefer the largest successful batch in this same paste
    rate = None
    rate_source = None
    rate_basis = None
    usable = [b for b in succeeded if b.record_count and b.elapsed and b.record_count > 0]
    if usable:
        best = max(usable, key=lambda b: b.record_count or 0)
        rate = best.elapsed / best.record_count
        rate_source = "observed"
        rate_basis = f"{best.record_count} records in {best.elapsed:.0f}s at {best.end}"
    else:
        baseline = topology.get("throughput_baseline") or {}
        if baseline.get("seconds_per_record"):
            rate = float(baseline["seconds_per_record"])
            rate_source = "baseline"
            rate_basis = baseline.get("derived_from", "configured baseline")

    projected = None
    if rate and record_count:
        projected = rate * record_count
        ev.append(Evidence(
            kind="projection",
            summary=(
                f"At {rate:.3f}s/record ({rate_source}), {record_count} records "
                f"needs about {projected:.0f}s"
            ),
            source="ald_sat", derived=True,
            value={"rate": rate, "projected": projected, "basis": rate_basis},
        ))

    projection_exceeds_elapsed = bool(
        projected is not None and elapsed and projected > elapsed * 1.2
    )

    ceiling_seconds = None
    ceiling_hit = False
    for c in topology.get("known_ceilings", []):
        if elapsed is not None and abs(elapsed - c["seconds"]) <= c.get("tolerance", 5):
            ceiling_seconds = float(c["seconds"])
            ceiling_hit = True
            ev.append(Evidence(
                kind="ceiling",
                summary=(
                    f"{elapsed:.0f}s sits on the known {c['seconds']}s ceiling "
                    f"({c['typical_owner']})"
                ),
                source="ald_sat", derived=True, value=ceiling_seconds,
            ))
            break

    small_ok = any(b.record_count and b.record_count < 100 for b in succeeded)
    if small_ok and failed:
        ev.append(Evidence(
            kind="size_contrast",
            summary="Small batches to the same host succeeded in the same period",
            source="ald_sat", derived=True, value=True,
        ))

    client_timeout = float(topology.get("client_timeout_seconds", 100))
    if elapsed is not None and elapsed < client_timeout * 0.9:
        ev.append(Evidence(
            kind="client_ruled_out",
            summary=(
                f"{elapsed:.0f}s is well inside the {client_timeout:.0f}s client "
                f"timeout, so the client did not abort the call"
            ),
            source="app_logs", derived=True, value=client_timeout,
        ))

    return {
        "has_error": bool(error_blocks),
        "error_count": len(error_blocks),
        "error_time": error_blocks[0].time if error_blocks else None,
        "exception_types": exception_types,
        "error_text": "\n".join(error_texts),
        "http_status": http_status,
        "endpoint_url": endpoint_url,
        "endpoint_host": endpoint_host,
        "record_count": record_count,
        "elapsed_seconds": elapsed,
        "observed_seconds_per_record": rate,
        "rate_source": rate_source,
        "rate_basis": rate_basis,
        "projected_seconds": projected,
        "projection_exceeds_elapsed": projection_exceeds_elapsed,
        "ceiling_seconds": ceiling_seconds,
        "ceiling_hit": ceiling_hit,
        "small_batches_succeeded": small_ok,
        "success_count": len(succeeded),
        "failure_count": len(failed),
        "service_state": service_state,
        "client_timeout_seconds": client_timeout,
    }


def parse(text: str, topology: dict[str, Any]) -> ParseResult:
    """Full stages 1-3."""
    lines = parse_lines(text)
    blocks, warnings = build_blocks(lines)
    result = extract(blocks, topology)
    result.warnings.extend(warnings)
    if result.facts.get("has_error") and result.facts.get("elapsed_seconds") is None:
        result.warnings.append(
            "An error was found but no batch start line preceded it, so elapsed "
            "time could not be derived. Paste more of the log before the error."
        )
    return result
