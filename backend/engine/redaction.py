"""Replace internal identifiers with tokens before any prompt leaves the machine.

WHY THIS EXISTS
===============
Stage 7 is the only stage that talks to a third party. On the Gemini free tier
Google's terms allow content to be used for product improvement and read by
human reviewers. Even on a paid tier, sending bank-internal hostnames to an
external model is a conversation nobody wants to have with risk review.

The prompt already excludes the raw log, the stack trace and error_text - only
derived summaries are sent. This module closes the remaining gap: the derived
summaries still carry real hostnames, IPs, incident ids and team names.

HOW IT WORKS
============
Pseudonymisation, not deletion. ``gateway.suppliersync.internal`` becomes
``<HOST_1>`` on the way out and is restored on the way back, so the model
writes a coherent paragraph about a real failure without ever receiving a real
identifier. If the model drops or mangles a token, that token simply is not
restored - the structured fields the dashboard renders are untouched either way.

WHAT THIS DOES NOT DO
=====================
It redacts *identifiers*, not vocabulary. System and layer names - Galileo,
Aldavar, BulkSuppliers - still reach the model, because stripping them would
leave a prompt too generic to write from. Claim the narrow thing accurately:
internal hostnames, IP addresses, incident ids and team names never leave the
machine. Do not claim the model learns nothing about the estate.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
INCIDENT_RE = re.compile(r"\bINC-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", re.IGNORECASE)
FQDN_RE = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}\b", re.IGNORECASE)

DEFAULT_CONFIG = {
    "enabled": True,
    "internal_domain_suffixes": [".internal"],
    "redact_hosts": True,
    "redact_ips": True,
    "redact_incident_ids": True,
    "redact_owners": True,
}


@dataclass
class Redaction:
    token: str
    value: str
    kind: str


@dataclass
class Redactor:
    """A reversible token map for one investigation."""

    redactions: list[Redaction] = field(default_factory=list)
    enabled: bool = True

    # -- construction ------------------------------------------------------

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        topology: dict[str, Any],
        scan_text: str | None = None,
    ) -> "Redactor":
        """Build the token map.

        Candidates are gathered from the payload and topology, then kept only if
        they actually occur in ``scan_text`` - the prompt about to be sent. That
        keeps the map to what is genuinely leaving, so the panel a reviewer reads
        lists real exposure rather than every identifier the tool happens to know.
        """
        cfg = {**DEFAULT_CONFIG, **(topology.get("redaction") or {})}
        if not cfg.get("enabled", True):
            return cls(enabled=False)

        blob = json.dumps(payload, default=str)
        target = blob if scan_text is None else scan_text
        found: list[tuple[str, str]] = []      # (kind, value)

        if cfg.get("redact_hosts", True):
            suffixes = tuple(
                s.lower() for s in cfg.get("internal_domain_suffixes", [])
            )
            hosts = set(topology.get("hosts") or {})
            for m in FQDN_RE.finditer(blob):
                host = m.group(0)
                if suffixes and host.lower().endswith(suffixes):
                    hosts.add(host)
            for host in hosts:
                if host in blob:
                    found.append(("host", host))

        if cfg.get("redact_ips", True):
            for ip in dict.fromkeys(IP_RE.findall(blob)):
                found.append(("ip", ip))

        if cfg.get("redact_incident_ids", True):
            for inc in dict.fromkeys(INCIDENT_RE.findall(blob)):
                found.append(("incident", inc))

        if cfg.get("redact_owners", True):
            owners = {
                l.get("owner") for l in topology.get("layers", []) if l.get("owner")
            }
            rb = payload.get("runbook") or {}
            if rb.get("escalate_to"):
                owners.add(rb["escalate_to"])
            for p in payload.get("precedents") or []:
                if p.get("resolved_by"):
                    owners.add(p["resolved_by"])
            for owner in owners:
                if owner and owner in blob:
                    found.append(("team", owner))

        # Longest values first so a suffix never eats part of a longer match.
        found.sort(key=lambda t: -len(t[1]))

        counters: dict[str, int] = {}
        seen: set[str] = set()
        redactions: list[Redaction] = []
        for kind, value in found:
            if value in seen or value not in target:
                continue
            seen.add(value)
            counters[kind] = counters.get(kind, 0) + 1
            redactions.append(
                Redaction(token=f"<{kind.upper()}_{counters[kind]}>",
                          value=value, kind=kind)
            )
        return cls(redactions=redactions)

    # -- use ---------------------------------------------------------------

    def redact(self, text: str) -> str:
        for r in self.redactions:
            text = text.replace(r.value, r.token)
        return text

    def restore(self, text: str) -> str:
        """Put the real identifiers back.

        Tolerant of a model that changed the token's case. A token the model
        dropped entirely is simply not restored - never an error, because the
        narrative is decoration and the structured fields carry the answer.
        """
        for r in self.redactions:
            text = re.sub(re.escape(r.token), r.value, text, flags=re.IGNORECASE)
        return text

    def as_dicts(self) -> list[dict[str, str]]:
        """For the dashboard's transparency panel. Local display only."""
        return [
            {"token": r.token, "value": r.value, "kind": r.kind}
            for r in self.redactions
        ]

    def leaked(self, text: str) -> list[str]:
        """Any real identifier still present. Used as a self-check and by tests."""
        return [r.value for r in self.redactions if r.value in text]
