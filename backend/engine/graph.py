"""A lightweight knowledge graph built from the four config files.

DELIBERATELY SMALL. No graph database, no Cypher, no query language the model
can write into. Nodes and edges are built from config/topology.json,
config/runbooks.json and config/incidents.json at load time, plus the current
investigation as a transient CURRENT node. Traversal is a handful of dict
lookups.

The graph exists to answer relationship questions - who owns the thing that
broke, what does it depend on, which incidents resemble this one - with an
auditable path rather than a plausible sentence. Every answer a caller gets
back carries the path it was derived from, so the dashboard can show
"Team <- Application <- Incident" instead of asking anyone to trust it.

Node types:  Application Service API Database Host Team Layer Runbook
             Source Incident Evidence Fix
Relations:   OWNED_BY CALLS DEPENDS_ON RUNS_AS OBSERVED_BY USES_RUNBOOK
             CLASSIFIED_AS AFFECTS HAS_EVIDENCE ELIMINATES SIMILAR_TO
             RESOLVED_BY BELONGS_TO
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

CURRENT = "Incident:CURRENT"


@dataclass(frozen=True)
class Node:
    type: str
    id: str
    label: str
    props: tuple[tuple[str, Any], ...] = ()

    @property
    def key(self) -> str:
        return f"{self.type}:{self.id}"

    def prop(self, name: str, default: Any = None) -> Any:
        return dict(self.props).get(name, default)


@dataclass(frozen=True)
class Edge:
    src: str
    rel: str
    dst: str


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    _out: dict[str, list[Edge]] = field(default_factory=dict)
    _in: dict[str, list[Edge]] = field(default_factory=dict)

    # -- construction ------------------------------------------------------

    def add_node(self, type: str, id: str, label: str, **props: Any) -> str:
        node = Node(type=type, id=str(id), label=label,
                    props=tuple(sorted(props.items())))
        self.nodes[node.key] = node
        return node.key

    def add_edge(self, src: str, rel: str, dst: str) -> None:
        if src not in self.nodes or dst not in self.nodes:
            return                      # never create dangling relationships
        edge = Edge(src, rel, dst)
        if edge in self.edges:
            return
        self.edges.append(edge)
        self._out.setdefault(src, []).append(edge)
        self._in.setdefault(dst, []).append(edge)

    # -- traversal ---------------------------------------------------------

    def out(self, key: str, rel: str | None = None) -> list[Node]:
        return [self.nodes[e.dst] for e in self._out.get(key, [])
                if rel is None or e.rel == rel]

    def into(self, key: str, rel: str | None = None) -> list[Node]:
        return [self.nodes[e.src] for e in self._in.get(key, [])
                if rel is None or e.rel == rel]

    def relations(self, key: str) -> list[dict[str, str]]:
        """Every edge touching this node, as plain dicts for display."""
        out = [{"from": self.nodes[e.src].label, "rel": e.rel,
                "to": self.nodes[e.dst].label, "direction": "out"}
               for e in self._out.get(key, [])]
        inc = [{"from": self.nodes[e.src].label, "rel": e.rel,
                "to": self.nodes[e.dst].label, "direction": "in"}
               for e in self._in.get(key, [])]
        return out + inc

    def walk(self, start: str, rels: Iterable[str]) -> tuple[list[Node], list[str]]:
        """Follow a fixed chain of relations. Returns (end nodes, readable path).

        This is the only traversal primitive callers get. There is no
        general-purpose query language, so a model cannot ask the graph for
        something the code did not anticipate.
        """
        frontier = [start]
        path = [self.nodes[start].label] if start in self.nodes else [start]
        for rel in rels:
            nxt: list[str] = []
            for key in frontier:
                nxt.extend(n.key for n in self.out(key, rel))
            frontier = list(dict.fromkeys(nxt))
            path.append(rel)
            if not frontier:
                return [], path
        return [self.nodes[k] for k in frontier], path

    def find(self, type: str, id: str) -> Node | None:
        return self.nodes.get(f"{type}:{id}")


# --------------------------------------------------------------------------
# Building from config
# --------------------------------------------------------------------------

def build_static_graph(cfg: dict[str, Any]) -> Graph:
    """Everything knowable before an investigation runs."""
    topology = cfg["topology"]
    runbooks = cfg["runbooks"]
    incidents = cfg["incidents"]
    g = Graph()

    # --- teams ---
    teams: set[str] = set()
    if topology.get("owner_team"):
        teams.add(topology["owner_team"])
    for layer in topology.get("layers", []):
        if layer.get("owner"):
            teams.add(layer["owner"])
    for inc in incidents.get("incidents", []):
        if inc.get("resolved_by"):
            teams.add(inc["resolved_by"])
    for name in sorted(teams):
        g.add_node("Team", name, name)

    # --- application, its service and its dependencies ---
    app = topology.get("application") or {}
    app_key = None
    if app:
        app_key = g.add_node(
            "Application", app.get("id", "app"), app.get("name", "Application"),
            description=app.get("description", ""),
            environment=app.get("environment", ""),
        )
        if app.get("owner_team"):
            g.add_edge(app_key, "OWNED_BY", f"Team:{app['owner_team']}")
        if app.get("runs_as_service"):
            svc = g.add_node("Service", app["runs_as_service"], app["runs_as_service"])
            g.add_edge(app_key, "RUNS_AS", svc)
            if app.get("owner_team"):
                g.add_edge(svc, "OWNED_BY", f"Team:{app['owner_team']}")

    # --- hosts, typed by the role config gives them ---
    for host, meta in (topology.get("hosts") or {}).items():
        role = (meta.get("role") or "").lower()
        htype = "Database" if "sql" in role or "database" in role else "API"
        hkey = g.add_node(htype, host, host, role=meta.get("role", ""),
                          behind_intermediary=meta.get("behind_intermediary", False))
        g.add_node("Host", host, host)
        g.add_edge(hkey, "BELONGS_TO", f"Host:{host}")
        if meta.get("source"):
            src_key = f"Source:{meta['source']}"
            if src_key in g.nodes:
                g.add_edge(hkey, "OBSERVED_BY", src_key)

    # --- diagnostic sources ---
    for s in topology.get("sources", []):
        g.add_node("Source", s["id"], s["name"],
                   connected=bool(s.get("connected")), checks=s.get("checks", ""))
    # host -> source edges again, now that sources exist
    for host, meta in (topology.get("hosts") or {}).items():
        for htype in ("API", "Database"):
            hkey = f"{htype}:{host}"
            if hkey in g.nodes and meta.get("source"):
                g.add_edge(hkey, "OBSERVED_BY", f"Source:{meta['source']}")

    # --- application -> hosts ---
    if app_key:
        for host in app.get("calls", []):
            for htype in ("API", "Database", "Host"):
                if f"{htype}:{host}" in g.nodes:
                    g.add_edge(app_key, "CALLS", f"{htype}:{host}")
                    break
        for host in app.get("depends_on", []):
            for htype in ("Database", "API", "Host"):
                if f"{htype}:{host}" in g.nodes:
                    g.add_edge(app_key, "DEPENDS_ON", f"{htype}:{host}")
                    break

    # --- layers and runbooks ---
    for rb_id, rb in runbooks.items():
        g.add_node("Runbook", rb_id, rb.get("title", rb_id),
                   fix=rb.get("fix", ""), escalate_to=rb.get("escalate_to") or "")
    for layer in topology.get("layers", []):
        lkey = g.add_node("Layer", layer["id"], layer.get("name", layer["id"]),
                          candidate=bool(layer.get("candidate")))
        if layer.get("owner"):
            g.add_edge(lkey, "OWNED_BY", f"Team:{layer['owner']}")
        if layer.get("runbook_id"):
            g.add_edge(lkey, "USES_RUNBOOK", f"Runbook:{layer['runbook_id']}")
        if layer.get("primary_source"):
            g.add_edge(lkey, "OBSERVED_BY", f"Source:{layer['primary_source']}")

    # --- historical incidents ---
    for inc in incidents.get("incidents", []):
        ikey = g.add_node("Incident", inc["id"], inc.get("title", inc["id"]),
                          date=inc.get("date", ""), fix_held=bool(inc.get("fix_held")),
                          resolution=inc.get("resolution", ""),
                          time_to_resolve_hours=inc.get("time_to_resolve_hours"))
        if inc.get("layer"):
            g.add_edge(ikey, "CLASSIFIED_AS", f"Layer:{inc['layer']}")
        if inc.get("host"):
            for htype in ("API", "Database", "Host"):
                if f"{htype}:{inc['host']}" in g.nodes:
                    g.add_edge(ikey, "AFFECTS", f"{htype}:{inc['host']}")
                    break
        if inc.get("resolution"):
            fkey = g.add_node("Fix", inc["id"], inc["resolution"],
                              held=bool(inc.get("fix_held")))
            g.add_edge(ikey, "RESOLVED_BY", fkey)
            if inc.get("resolved_by"):
                g.add_edge(fkey, "OWNED_BY", f"Team:{inc['resolved_by']}")
        if app_key:
            g.add_edge(ikey, "AFFECTS", app_key)

    return g


def attach_investigation(g: Graph, inv: dict[str, Any], topology: dict[str, Any]) -> Graph:
    """Add the current investigation to a copy of the static graph."""
    live = Graph(nodes=dict(g.nodes), edges=list(g.edges))
    for e in live.edges:
        live._out.setdefault(e.src, []).append(e)
        live._in.setdefault(e.dst, []).append(e)

    ikey = live.add_node("Incident", "CURRENT", "This investigation",
                         band=inv["confidence"]["band"],
                         raw_band=inv["confidence"]["raw_band"])

    if inv.get("layer"):
        live.add_edge(ikey, "CLASSIFIED_AS", f"Layer:{inv['layer']}")

    app = topology.get("application") or {}
    if app.get("id"):
        live.add_edge(ikey, "AFFECTS", f"Application:{app['id']}")

    host = (inv.get("facts") or {}).get("endpoint_host")
    if host:
        for htype in ("API", "Database", "Host"):
            if f"{htype}:{host}" in live.nodes:
                live.add_edge(ikey, "AFFECTS", f"{htype}:{host}")
                break

    for i, ev in enumerate(inv.get("evidence", [])):
        ekey = live.add_node("Evidence", f"CURRENT-{i}", ev["summary"],
                             source=ev.get("source", ""), derived=ev.get("derived", False))
        live.add_edge(ikey, "HAS_EVIDENCE", ekey)
        if ev.get("source"):
            live.add_edge(ekey, "OBSERVED_BY", f"Source:{ev['source']}")

    for layer in (inv.get("eliminated") or {}):
        live.add_edge(ikey, "ELIMINATES", f"Layer:{layer}")

    for p in inv.get("precedents") or []:
        live.add_edge(ikey, "SIMILAR_TO", f"Incident:{p['incident_id']}")

    if inv.get("runbook_id"):
        live.add_edge(ikey, "USES_RUNBOOK", f"Runbook:{inv['runbook_id']}")

    return live
