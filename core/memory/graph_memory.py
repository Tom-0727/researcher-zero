from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

GRAPH_DB_PATH = Path("cache/graph_db.json")

NODE_TYPES = {
    "Taxonomy",
    "Category",
    "Concept",
    "Paper",
    "Benchmark",
    "Challenge",
}
EDGE_RELS = {
    "BELONGS_TO",
    "ADDRESSES",
    "MEASURES",
    "HAS_SOTA",
}

G = nx.DiGraph()


def add_node(node_type: str, node_id: str, **attrs: object) -> None:
    """Add a node with type and attributes."""
    if node_type not in NODE_TYPES:
        raise ValueError(f"unknown node type: {node_type}")
    if G.has_node(node_id):
        raise ValueError(f"node already exists: {node_id}")
    G.add_node(node_id, type=node_type, **attrs)


def add_edge(from_id: str, to_id: str, rel: str) -> None:
    """Add a directed edge with relationship type."""
    if rel not in EDGE_RELS:
        raise ValueError(f"unknown relationship: {rel}")
    if not G.has_node(from_id):
        raise ValueError(f"missing from node: {from_id}")
    if not G.has_node(to_id):
        raise ValueError(f"missing to node: {to_id}")
    if G.has_edge(from_id, to_id):
        raise ValueError(f"edge already exists: {from_id} -> {to_id}")
    G.add_edge(from_id, to_id, rel=rel)


def update_node(node_id: str, **attrs: object) -> None:
    """Update node attributes in-place."""
    if not G.has_node(node_id):
        raise ValueError(f"missing node: {node_id}")
    G.nodes[node_id].update(attrs)


def get_node(node_id: str) -> dict:
    """Get a node and its attributes."""
    if not G.has_node(node_id):
        raise ValueError(f"missing node: {node_id}")
    data = dict(G.nodes[node_id])
    data["id"] = node_id
    return data


def get_knowledge_graph() -> dict:
    """Return the Taxonomy→Category→Concept→Paper topology."""
    allowed_types = {"Taxonomy", "Category", "Concept", "Paper"}
    nodes = []
    edges = []

    for node_id, attrs in G.nodes.items():
        if attrs.get("type") in allowed_types:
            nodes.append({"id": node_id, **attrs})

    # Only keep BELONGS_TO edges inside the taxonomy subtree.
    for from_id, to_id, attrs in G.edges(data=True):
        if attrs.get("rel") != "BELONGS_TO":
            continue
        if (
            G.nodes[from_id].get("type") in allowed_types
            and G.nodes[to_id].get("type") in allowed_types
        ):
            edges.append({"from_id": from_id, "to_id": to_id, "rel": attrs["rel"]})

    return {"nodes": nodes, "edges": edges}


def get_challenges() -> list[dict]:
    """Return Challenge nodes with associated Benchmarks."""
    results: list[dict] = []
    for node_id, attrs in G.nodes.items():
        if attrs.get("type") != "Challenge":
            continue
        benchmarks = []

        # Benchmarks measure challenges via incoming MEASURES edges.
        for from_id, _, edge_attrs in G.in_edges(node_id, data=True):
            if edge_attrs.get("rel") != "MEASURES":
                continue
            if G.nodes[from_id].get("type") != "Benchmark":
                continue
            bench_data = dict(G.nodes[from_id])
            bench_data["id"] = from_id
            benchmarks.append(bench_data)

        results.append(
            {
                "challenge": {"id": node_id, **attrs},
                "benchmarks": benchmarks,
            }
        )
    return results


def save() -> None:
    """Persist graph to cache/graph_db.json."""
    data = nx.node_link_data(G)
    with GRAPH_DB_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load() -> nx.DiGraph:
    """Load graph from cache/graph_db.json into G."""
    with GRAPH_DB_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    graph = nx.node_link_graph(data)
    global G
    G = graph
    return G
