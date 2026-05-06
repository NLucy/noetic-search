"""Trace generation for the browser visualization.

The trace is a concrete snapshot of one benchmark query moving through Noetic
Search. It is not a separate algorithm. It runs the same retrieval,
graph-building, spectral detection, diffusion, basin scoring, and ranking code
used by the package, then writes the intermediate artifacts to JSON.

Key variables:
    `max_points`: Maximum number of corpus chunks shown in the browser. The
        trace always includes hybrid candidates, graph candidates, winner chunks,
        and target evidence for the selected case before filling the rest.
    `candidate_limit`: Number of hybrid candidates retrieved from first-stage
        search.
    `result_limit`: Number of candidates admitted into the local graph.
    `diffusion_steps`: Number of diffusion time steps captured in the trace.
    `edge_threshold`: Minimum embedding similarity used to create graph edges.
    `points`: Browser-facing chunk records with 2D coordinates and pipeline
        flags.
    `energy_steps`: Diffusion energy snapshots, one dictionary per time step.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from noetic_systems.database import Database
from noetic_systems.reconciliation.basins import build_basins, calculate_uncertainty
from noetic_systems.reconciliation.diffusion import diffuse, seed_energy
from noetic_systems.reconciliation.graph import (
    build_evidence_graph,
)
from noetic_systems.reconciliation.metrics import (
    calculate_dispersion,
    calculate_modularity,
    document_specificity,
)
from noetic_systems.reconciliation.ranking import rank_basin_documents
from noetic_systems.reconciliation.spectral import detect_communities
from noetic_systems.search.hybrid import HybridSearch
from noetic_systems.search.semantic import SearchResult


DEFAULT_TRACE_PATH = Path("docs/trace.json")
MULTI_BASIN_TRACE_CASE_ID = "multi_basin_release"
DEFAULT_TRACE_EDGE_THRESHOLD = 0.82


def generate_trace(
    *,
    data_path: Path,
    output_path: Path = DEFAULT_TRACE_PATH,
    case_id: str = MULTI_BASIN_TRACE_CASE_ID,
    collection_name: str = "noetic_trace",
    blind: bool = True,
    max_points: int = 500,
    candidate_limit: int = 50,
    result_limit: int = 30,
    diffusion_steps: int = 10,
    damping: float = 0.85,
    edge_threshold: float = DEFAULT_TRACE_EDGE_THRESHOLD,
) -> dict[str, Any]:
    """Generate and write one browser visualization trace.

    Args:
        data_path: Hard benchmark JSON path.
        output_path: Destination JSON path for the browser viewer.
        case_id: Benchmark case id to visualize.
        collection_name: Temporary Chroma collection name.
        blind: Whether to strip benchmark-only metadata before indexing.
        max_points: Maximum corpus points to include in the 2D view.
        candidate_limit: Hybrid candidates retrieved for the query.
        result_limit: Candidates admitted into the local graph.
        diffusion_steps: Number of diffusion updates to capture.
        damping: Fraction of energy allowed to move per diffusion step.
        edge_threshold: Minimum embedding similarity for graph edges.

    Returns:
        Trace dictionary written to `output_path`.
    """
    data = (
        multi_basin_trace_data()
        if case_id == MULTI_BASIN_TRACE_CASE_ID
        else json.loads(data_path.read_text())
    )
    case = data["cases"][case_id]
    target_ids = target_doc_ids(data, case_id)
    corpus = strip_custom_metadata(data) if blind else data["corpus"]

    database = Database(collection_name=collection_name, reset=True)
    try:
        database.add_documents(corpus)
        hybrid = HybridSearch(database)

        query = case["query"]
        candidates = hybrid.search(query, limit=candidate_limit)
        graph_candidates = candidates[:result_limit]
        doc_index = {result.id: result for result in graph_candidates}
        graph, evidence_edges = build_evidence_graph(database, doc_index, edge_threshold)
        communities = detect_communities(graph)

        energy = seed_energy(graph_candidates)
        energy_steps = [dict(energy)]
        for _ in range(diffusion_steps):
            energy = diffuse(energy, graph, damping)
            energy_steps.append(dict(energy))

        basins = build_basins(communities, energy, graph)
        basins = sorted(basins, key=lambda basin: basin.score, reverse=True)
        modularity = calculate_modularity(graph, communities)
        dispersion = calculate_dispersion(energy)
        uncertainty = calculate_uncertainty(basins, modularity, dispersion)

        specificity = document_specificity(graph_candidates)
        if basins:
            ranked_winner_documents = rank_basin_documents(
                list(basins[0].documents),
                energy,
                specificity,
            )
            winner = replace(basins[0], documents=tuple(ranked_winner_documents))
            basins = [winner, *basins[1:]]
        else:
            winner = None

        visible_ids = select_visible_ids(
            data["corpus"],
            candidates,
            graph_candidates,
            list(winner.documents) if winner else [],
            target_ids,
            max_points,
        )
        embeddings = fetch_embeddings(database, visible_ids)
        coordinates = project_embeddings(embeddings)
        corpus_by_id = {doc["id"]: doc for doc in data["corpus"]}
        candidate_ranks = {result.id: index + 1 for index, result in enumerate(candidates)}
        graph_ranks = {
            result.id: index + 1
            for index, result in enumerate(graph_candidates)
        }
        final_ids = set(winner.documents[:5] if winner else ())
        winner_ids = set(winner.documents if winner else ())

        points = [
            point_record(
                doc_id,
                corpus_by_id[doc_id],
                coordinates[doc_id],
                candidate_ranks,
                graph_ranks,
                communities,
                energy_steps,
                target_ids,
                winner_ids,
                final_ids,
            )
            for doc_id in visible_ids
        ]

        trace = {
            "case": {
                "id": case_id,
                "query": query,
                "expected_stance": case["expected_stance"],
                "target_ids": sorted(target_ids),
            },
            "settings": {
                "blind": blind,
                "max_points": max_points,
                "candidate_limit": candidate_limit,
                "result_limit": result_limit,
                "diffusion_steps": diffusion_steps,
                "damping": damping,
                "edge_threshold": edge_threshold,
            },
            "points": points,
            "edges": graph_edges(graph),
            "evidence_edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "type": edge.type,
                    "weight": edge.weight,
                    "reason": edge.reason,
                }
                for edge in evidence_edges
            ],
            "energy_steps": energy_steps,
            "basins": [
                {
                    "id": basin.id,
                    "label": basin.label,
                    "score": basin.score,
                    "energy": basin.energy,
                    "cohesion": basin.cohesion,
                    "support": basin.support,
                    "duplicate_penalty": basin.duplicate_penalty,
                    "documents": list(basin.documents),
                    "target_fraction": target_fraction(basin.documents, target_ids),
                }
                for basin in basins
            ],
            "winner": {
                "label": winner.label if winner else "none",
                "documents": list(winner.documents[:5] if winner else []),
                "score": winner.score if winner else 0.0,
            },
            "metrics": {
                "modularity": modularity,
                "dispersion": dispersion,
                "uncertainty": uncertainty,
                "target_fraction_top5": target_fraction(
                    winner.documents[:5] if winner else [],
                    target_ids,
                ),
            },
            "steps": [
                "corpus",
                "hybrid",
                "graph",
                "spectral",
                "diffusion",
                "basins",
                "final",
            ],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(trace, indent=2))
        return trace
    finally:
        database.reset()


def target_doc_ids(data: dict[str, Any], case_id: str) -> set[str]:
    """Return benchmark target document ids for one case.

    Args:
        data: Hard benchmark payload.
        case_id: Benchmark case id.

    Returns:
        Target evidence document ids.
    """
    return {
        doc["id"]
        for doc in data["corpus"]
        if doc["metadata"].get("case") == case_id
        and doc["metadata"].get("gold") == "target"
    }


def multi_basin_trace_data() -> dict[str, Any]:
    """Build a homogeneous trace corpus with real basin separation.

    The hard benchmark is optimized for evaluation, not always for visual
    explanation. Some benchmark queries produce one coherent evidence region,
    which is correct but visually unhelpful when teaching basin formation. This
    trace corpus stays inside one payments domain, then creates two internal
    evidence regions around settlement readiness and fraud readiness. The goal
    is a teaching example where basins emerge inside a shared field instead of
    looking like unrelated topic islands.

    Returns:
        Benchmark-shaped payload consumed by `generate_trace`.
    """
    topics = {
        "settlement": [
            "ledger reconciliation backlog",
            "ACH posting delay",
            "processor timeout retry",
            "merchant payout queue",
            "reserve balance mismatch",
            "settlement file validation",
            "clearing window exception",
            "reversal posting defect",
            "batch cutoff pressure",
            "bank response latency",
            "funding hold review",
            "settlement rollback runbook",
            "duplicate payout exposure",
            "payment rail degradation",
            "nightly close failure",
        ],
        "fraud": [
            "fraud review queue growth",
            "manual approval backlog",
            "chargeback signal spike",
            "account takeover alerts",
            "velocity rule false positives",
            "risk model drift",
            "dispute intake surge",
            "merchant monitoring exception",
            "suspicious refund pattern",
            "identity verification delay",
            "fraud analyst capacity",
            "case escalation SLA",
            "risk threshold override",
            "blocked transaction review",
            "fraud release gate",
        ],
    }

    corpus: list[dict[str, Any]] = []
    for topic, phrases in topics.items():
        for index, phrase in enumerate(phrases, start=1):
            doc_id = f"{topic}-{index}"
            corpus.append(
                {
                    "id": doc_id,
                    "text": (
                        "Payment release decision evidence operational risk "
                        f"readiness. {topic} control area: {phrase}. "
                        f"{topic} owners assess go/no-go launch risk for the "
                        "payments platform."
                    ),
                    "metadata": {
                        "source": "demo",
                        "domain": "payments",
                        "title": f"{topic} release evidence {index}",
                        "case": MULTI_BASIN_TRACE_CASE_ID,
                    },
                }
            )

    for index in range(60):
        if index % 3 == 0:
            context = "settlement checkpoint review and payment rail readiness"
        elif index % 3 == 1:
            context = "fraud checkpoint review and risk operations readiness"
        else:
            context = "shared release coordination and customer impact review"
        corpus.append(
            {
                "id": f"background-{index}",
                "text": (
                    f"Payment release context note {index}: {context}. "
                    "The note is related to the same payments launch field, "
                    "but it is lower-specificity context rather than direct "
                    "decision evidence."
                ),
                "metadata": {
                    "source": "demo",
                    "domain": "payments",
                    "title": f"background note {index}",
                },
            }
        )

    return {
        "corpus": corpus,
        "cases": {
            MULTI_BASIN_TRACE_CASE_ID: {
                "query": (
                    "payment release decision evidence operational risk "
                    "readiness"
                ),
                "expected_stance": (
                    "The trace should show two coherent payments-release "
                    "evidence regions in one domain: settlement readiness and "
                    "fraud readiness."
                ),
            }
        },
        "metadata": {
            "name": "homogeneous multi-basin trace demo",
            "document_count": len(corpus),
        },
    }

def strip_custom_metadata(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Strip benchmark-only labels before indexing.

    Args:
        data: Hard benchmark payload.

    Returns:
        Corpus documents with ordinary deployable metadata only.
    """
    allowed = {"source", "domain", "title", "url", "created_at", "document_id"}
    return [
        {
            "id": doc["id"],
            "text": doc["text"],
            "metadata": {
                key: value
                for key, value in doc.get("metadata", {}).items()
                if key in allowed
            },
        }
        for doc in data["corpus"]
    ]


def select_visible_ids(
    corpus: list[dict[str, Any]],
    candidates: list[SearchResult],
    graph_candidates: list[SearchResult],
    winner_ids: list[str],
    target_ids: set[str],
    max_points: int,
) -> list[str]:
    """Select corpus ids shown in the browser view.

    Args:
        corpus: Full benchmark corpus.
        candidates: Hybrid candidates.
        graph_candidates: Graph-admitted candidates.
        winner_ids: Ordered winning-basin document ids.
        target_ids: Target evidence ids for the selected case.
        max_points: Maximum number of ids to return.

    Returns:
        Stable list of visible document ids.
    """
    required = [
        *[result.id for result in candidates],
        *[result.id for result in graph_candidates],
        *winner_ids,
        *sorted(target_ids),
    ]
    visible: list[str] = []
    seen: set[str] = set()
    for doc_id in required:
        if doc_id not in seen:
            visible.append(doc_id)
            seen.add(doc_id)

    # Fill the background deterministically so repeated traces do not jump.
    for doc in sorted(corpus, key=lambda item: item["id"]):
        if len(visible) >= max_points:
            break
        if doc["id"] not in seen:
            visible.append(doc["id"])
            seen.add(doc["id"])
    return visible


def fetch_embeddings(database: Database, ids: list[str]) -> dict[str, list[float]]:
    """Fetch embeddings for visible documents.

    Args:
        database: Database containing benchmark documents.
        ids: Document ids to fetch.

    Returns:
        Embeddings by document id.
    """
    result = database.collection.get(ids=ids, include=["embeddings"])
    embeddings = result.get("embeddings")
    if embeddings is None:
        return {}
    return {
        doc_id: [float(value) for value in vector]
        for doc_id, vector in zip(result["ids"], embeddings)
    }


def project_embeddings(
    embeddings: dict[str, list[float]],
) -> dict[str, tuple[float, float]]:
    """Project embeddings into two dimensions with PCA.

    Args:
        embeddings: Embeddings by document id.

    Returns:
        Normalized `(x, y)` coordinates by document id.
    """
    ids = list(embeddings)
    if not ids:
        return {}
    matrix = np.array([embeddings[doc_id] for doc_id in ids], dtype=float)
    matrix = matrix - matrix.mean(axis=0, keepdims=True)
    if matrix.shape[0] == 1:
        return {ids[0]: (0.0, 0.0)}

    # PCA keeps the visualization deterministic and explainable. It is not
    # trying to beautify the clusters; it is showing the largest variance axes.
    _, _, vt = np.linalg.svd(matrix, full_matrices=False)
    projected = matrix @ vt[:2].T
    if projected.shape[1] == 1:
        projected = np.column_stack([projected[:, 0], np.zeros(len(ids))])

    max_abs = np.maximum(np.abs(projected).max(axis=0), 1e-9)
    normalized = projected / max_abs
    return {
        doc_id: (float(x), float(y))
        for doc_id, (x, y) in zip(ids, normalized)
    }


def point_record(
    doc_id: str,
    doc: dict[str, Any],
    coordinate: tuple[float, float],
    candidate_ranks: dict[str, int],
    graph_ranks: dict[str, int],
    communities: dict[str, int],
    energy_steps: list[dict[str, float]],
    target_ids: set[str],
    winner_ids: set[str],
    final_ids: set[str],
) -> dict[str, Any]:
    """Build one browser-facing point record.

    Args:
        doc_id: Document id.
        doc: Source corpus document.
        coordinate: Projected 2D coordinate.
        candidate_ranks: Hybrid rank by document id.
        graph_ranks: Graph-candidate rank by document id.
        communities: Spectral community id by document id.
        energy_steps: Diffusion energy snapshots.
        target_ids: Target evidence ids.
        winner_ids: Winning basin ids.
        final_ids: Returned top-5 ids.

    Returns:
        JSON-compatible point record.
    """
    return {
        "id": doc_id,
        "x": coordinate[0],
        "y": coordinate[1],
        "text": doc["text"][:220],
        "domain": doc.get("metadata", {}).get("domain", ""),
        "source": doc.get("metadata", {}).get("source", ""),
        "is_candidate": doc_id in candidate_ranks,
        "candidate_rank": candidate_ranks.get(doc_id),
        "is_graph_candidate": doc_id in graph_ranks,
        "graph_rank": graph_ranks.get(doc_id),
        "community": communities.get(doc_id),
        "is_target": doc_id in target_ids,
        "is_winner": doc_id in winner_ids,
        "is_final": doc_id in final_ids,
        "energy": [
            float(step.get(doc_id, 0.0))
            for step in energy_steps
        ],
    }


def graph_edges(graph: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    """Serialize unique graph edges.

    Args:
        graph: Weighted adjacency mapping.

    Returns:
        Unique undirected graph edges.
    """
    edges = []
    seen: set[tuple[str, str]] = set()
    for source, neighbors in graph.items():
        for target, weight in neighbors.items():
            key = tuple(sorted((source, target)))
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "weight": float(weight),
                }
            )
    return sorted(edges, key=lambda edge: edge["weight"], reverse=True)


def target_fraction(
    doc_ids: list[str] | tuple[str, ...],
    target_ids: set[str],
) -> float:
    """Calculate fraction of ids that are target evidence.

    Args:
        doc_ids: Document ids to score.
        target_ids: Target evidence ids.

    Returns:
        Fraction of ids in `target_ids`.
    """
    if not doc_ids:
        return 0.0
    return sum(1 for doc_id in doc_ids if doc_id in target_ids) / len(doc_ids)
