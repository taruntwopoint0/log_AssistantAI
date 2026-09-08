"""Assess how well the application logs, and tell its developers.

This is not about whether the paste was big enough. It is feedback on the
logging itself: the practices that made this investigation harder than it
needed to be, and the ones the team already gets right.

Every check is deterministic - a regex or a comparison over what the parser
already extracted. No model is involved in deciding whether a practice is
present, how much it cost, or what to do about it. The model is not consulted
here at all.

Each finding carries three things, because a finding without them is just
criticism:

    observed  what the log actually did
    impact    what that cost THIS investigation, in concrete terms
    fix       the change a developer would make

Checks that pass are reported too. A report that only lists faults reads as
nagging and gets ignored; showing what the team already does well is what makes
the rest credible.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

# A correlation identifier: a GUID, or a named field carrying one.
GUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I
)
CORRELATION_KEY_RE = re.compile(
    r"\b(correlation[_\- ]?id|trace[_\- ]?id|request[_\- ]?id|operation[_\- ]?id|"
    r"x-request-id|activity[_\- ]?id|span[_\- ]?id)\b",
    re.I,
)
DURATION_RE = re.compile(
    r"\b(elapsed|duration|took|completed in|finished in|latency|ms\b|"
    r"\d+\s*(ms|milliseconds|seconds|secs?)\b)",
    re.I,
)
ATTEMPT_RE = re.compile(r"\b(attempt|retry|retries|try)\s*[#:]?\s*\d+", re.I)
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class LogFinding:
    id: str
    name: str
    passed: bool
    severity: str          # high | medium | low  (only meaningful when failed)
    observed: str
    impact: str
    fix: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "passed": self.passed,
            "severity": self.severity, "observed": self.observed,
            "impact": self.impact, "fix": self.fix,
        }


@dataclass
class LogQuality:
    findings: list[LogFinding] = field(default_factory=list)
    passed: int = 0
    total: int = 0

    @property
    def gaps(self) -> list[LogFinding]:
        return [f for f in self.findings if not f.passed]

    @property
    def strengths(self) -> list[LogFinding]:
        return [f for f in self.findings if f.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "total": self.total,
            "findings": [f.to_dict() for f in self.findings],
            "gaps": [f.to_dict() for f in self.gaps],
            "strengths": [f.to_dict() for f in self.strengths],
        }


# --------------------------------------------------------------------------

def assess(parsed, facts: dict[str, Any]) -> LogQuality:
    """Return a LogQuality report for one pasted log.

    ``parsed`` is the ParseResult from parser.py; ``facts`` its derived facts.
    """
    blocks = parsed.blocks
    all_text = "\n".join(b.text for b in blocks)
    error_blocks = [b for b in blocks if b.is_error]
    error_text = "\n".join(b.text for b in error_blocks)
    findings: list[LogFinding] = []

    def add(**kw):
        findings.append(LogFinding(**kw))

    # -- 1. correlation id -------------------------------------------------
    has_corr = bool(GUID_RE.search(all_text) or CORRELATION_KEY_RE.search(all_text))
    corr_in_error = bool(
        error_text and (GUID_RE.search(error_text) or CORRELATION_KEY_RE.search(error_text))
    )
    add(
        id="correlation_id",
        name="Correlation id on every line",
        passed=corr_in_error if error_blocks else has_corr,
        severity="high",
        observed=("A correlation id is present on the error."
                  if corr_in_error else
                  "No correlation or trace id appears anywhere in this block."
                  if not has_corr else
                  "A correlation id appears elsewhere but not on the error line."),
        impact=("Lines from this run can be tied to the same request across "
                "services." if corr_in_error else
                "This failure cannot be joined to the gateway, database or "
                "upstream logs for the same request. Every cross-system "
                "correlation has to be done by timestamp, by hand."),
        fix=("Keep it." if corr_in_error else
             "Attach a correlation id to the Serilog LogContext at the start of "
             "each cycle and emit it on every line, including errors. In .NET: "
             "LogContext.PushProperty(\"CorrelationId\", id)."),
    )

    # -- 2. timezone on timestamps ----------------------------------------
    dated = [b for b in blocks if b.date]
    add(
        id="timestamp_timezone",
        name="Timestamps carry a date and offset",
        passed=bool(dated),
        severity="medium",
        observed=("Timestamps include the date." if dated
                  else "Timestamps are time-only, with no date."),
        impact=("Lines can be aligned with other systems without guessing the day."
                if dated else
                "A run crossing midnight, or comparison with a UTC-logging "
                "system, needs the date inferred by hand."),
        fix=("Keep it." if dated else
             "Set the Serilog output template to include a full timestamp with "
             "offset: {Timestamp:yyyy-MM-dd HH:mm:ss.fff zzz}."),
    )

    # -- 3. duration logged, not derived -----------------------------------
    duration_logged = bool(DURATION_RE.search(all_text))
    add(
        id="explicit_duration",
        name="Duration logged on completion and failure",
        passed=duration_logged,
        severity="high",
        observed=("An explicit duration appears in the log." if duration_logged else
                  "No operation logs how long it took. Elapsed time had to be "
                  "derived by subtracting two timestamps."),
        impact=("Slow runs are visible before they fail." if duration_logged else
                "A run that is degrading but still succeeding is invisible. "
                "Nothing shows the trend until the day it crosses the limit "
                "and starts failing."),
        fix=("Keep it." if duration_logged else
             "Wrap each outbound call in a Stopwatch and log the elapsed "
             "milliseconds on both success and failure. That single field turns "
             "this failure from a surprise into a trend you can alert on."),
    )

    # -- 4. size at the point of failure -----------------------------------
    count = facts.get("record_count")
    size_on_error = bool(
        count is not None and error_text and re.search(rf"\b{count}\b", error_text)
    )
    add(
        id="size_at_failure",
        name="Payload size recorded on the failure itself",
        passed=size_on_error,
        severity="high",
        observed=("The failing record count appears on the error." if size_on_error
                  else "The record count is logged on a separate earlier line, "
                       "not on the error."),
        impact=("Size-dependent failures are obvious from the error alone."
                if size_on_error else
                "The error alone does not show that this was a large batch. "
                "The size-dependence of this fault is only visible if somebody "
                "pastes the preceding lines too - which is exactly why it went "
                "undiagnosed."),
        fix=("Keep it." if size_on_error else
             "Include the batch size, and the entity name, in the error's "
             "structured properties so the failure carries its own context."),
    )

    # -- 5. structured logging ---------------------------------------------
    json_lines = 0
    for b in blocks:
        t = b.message.strip()
        if t.startswith("{") and t.endswith("}"):
            try:
                json.loads(t)
                json_lines += 1
            except ValueError:
                pass
    structured = bool(blocks) and json_lines >= max(1, len(blocks) // 2)
    add(
        id="structured_logging",
        name="Structured fields rather than interpolated text",
        passed=structured,
        severity="medium",
        observed=("Lines are emitted as structured JSON." if structured else
                  "Lines are rendered plain text with values interpolated into "
                  "the message."),
        impact=("Values can be filtered and aggregated without regular expressions."
                if structured else
                "Every value in this investigation had to be recovered by regex. "
                "A message-format change silently breaks that extraction."),
        fix=("Keep it." if structured else
             "Use Serilog message templates with named properties - "
             "Log.Information(\"Fetched {RecordCount} for {Entity}\", n, entity) - "
             "and add a JSON sink alongside the human-readable one."),
    )

    # -- 6. attempt / retry number -----------------------------------------
    has_attempt = bool(ATTEMPT_RE.search(all_text))
    add(
        id="attempt_number",
        name="Attempt number on retried operations",
        passed=has_attempt,
        severity="low",
        observed=("Attempt numbers are logged." if has_attempt else
                  "No attempt or retry counter appears."),
        impact=("A retry storm is distinguishable from repeated independent "
                "failures." if has_attempt else
                "Four identical errors could be four separate cycles or one "
                "cycle retrying four times. Nothing in the log tells them "
                "apart, and the two need opposite responses."),
        fix=("Keep it." if has_attempt else
             "Log the attempt number and the retry policy's delay on every "
             "retried call."),
    )

    # -- 7. endpoint identified on the error -------------------------------
    has_endpoint = bool(facts.get("endpoint_url"))
    add(
        id="endpoint_on_error",
        name="Target endpoint named in the error",
        passed=has_endpoint,
        severity="medium",
        observed=("The error names the endpoint it was calling." if has_endpoint
                  else "The error does not name the endpoint."),
        impact=("The failing dependency is identifiable from the error alone."
                if has_endpoint else
                "Which downstream call failed has to be inferred from the "
                "stack trace or the surrounding lines."),
        fix=("Keep it." if has_endpoint else
             "Include the request URI in the error's properties."),
    )

    # -- 8. exception chain preserved --------------------------------------
    chain = facts.get("exception_types") or []
    chain_kept = len(chain) > 1 or "--->" in all_text
    add(
        id="exception_chain",
        name="Inner exceptions preserved",
        passed=chain_kept if facts.get("has_error") else True,
        severity="high",
        observed=(f"The full chain is logged: {' -> '.join(chain)}." if chain_kept
                  else "Only the outermost exception is logged."
                  if facts.get("has_error") else "No error in this log."),
        impact=("The distinguishing symptom survives to the log."
                if chain_kept else
                "The outer exception is almost always generic - 'An error "
                "occurred while sending the request' - and the inner one "
                "carries the actual cause. Without it there is nothing to "
                "diagnose from."),
        fix=("Keep it." if chain_kept else
             "Log the exception object itself, not ex.Message. Serilog "
             "serialises the whole chain when you pass the exception."),
    )

    # -- 9. outcome logged on success too ----------------------------------
    success_logged = facts.get("success_count", 0) > 0
    add(
        id="success_outcome",
        name="Successful operations logged, not only failures",
        passed=success_logged,
        severity="medium",
        observed=("Successful batches are logged with their outcome."
                  if success_logged else
                  "Only failures appear. Successful work is silent."),
        impact=("A baseline exists to compare the failure against - which is "
                "what made the throughput rate measurable here."
                if success_logged else
                "With no successful run to compare against, throughput has to "
                "be assumed from configuration rather than measured, which "
                "weakens every timing conclusion."),
        fix=("Keep it." if success_logged else
             "Log completion of each batch with its size, status and duration, "
             "even on the happy path."),
    )

    # -- 10. severity levels used ------------------------------------------
    levels = {b.level for b in blocks}
    uses_levels = len(levels) > 1
    add(
        id="severity_levels",
        name="Severity levels used meaningfully",
        passed=uses_levels,
        severity="low",
        observed=(f"Multiple levels in use: {', '.join(sorted(levels))}."
                  if uses_levels else
                  f"Only one level appears: {', '.join(sorted(levels)) or 'none'}."),
        impact=("Errors can be filtered and alerted on without parsing message text."
                if uses_levels else
                "Alerting has to match on message content, which breaks whenever "
                "the wording changes."),
        fix=("Keep it." if uses_levels else
             "Use INF for progress, WRN for degradation and ERR for failure, "
             "and make alerting key off the level."),
    )

    findings.sort(key=lambda f: (f.passed, SEVERITY_ORDER.get(f.severity, 3)))
    return LogQuality(
        findings=findings,
        passed=sum(1 for f in findings if f.passed),
        total=len(findings),
    )
