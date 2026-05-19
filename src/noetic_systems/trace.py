"""Trace generation for the browser visualization.

The trace is a concrete snapshot of one benchmark query moving through Noetic
Search. It is not a separate algorithm. It runs the same retrieval,
graph-building and linked-evidence ranking code used by the production path,
plus the spectral, diffusion, and basin diagnostics used by the trace viewer,
then writes the intermediate artifacts to JSON.

Key variables:
    `max_points`: Maximum number of corpus chunks shown in the browser. The
        trace always includes hybrid candidates, graph candidates, returned
        chunks, diagnostic basin chunks, and target evidence before filling the
        rest.
    `candidate_limit`: Number of hybrid candidates retrieved from first-stage
        search.
    `result_limit`: Number of candidates admitted into the local graph.
    `diffusion_steps`: Number of diffusion time steps captured in the trace.
    `edge_threshold`: Minimum embedding similarity used to create graph edges.
    `points`: Browser-facing chunk records with 2D coordinates and pipeline
        flags.
    `whole_energy_steps`: Diffusion energy snapshots over the full graph, before
        cross-basin edges are removed. This is a diagnostic, not the scoring
        distribution.
    `energy_steps`: Diffusion energy snapshots inside fixed spectral basins.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from noetic_systems.database import Database
from noetic_systems.reconciliation.calibration import (
    GRAPH_OBJECTIVES,
    calibrate_corpus_graph_weights,
)
from noetic_systems.reconciliation.basins import (
    BASIN_SUPPORT_SATURATION,
    build_basins,
    calculate_uncertainty,
)
from noetic_systems.reconciliation.diffusion import (
    constrain_graph_to_communities,
    diffuse,
    seed_energy,
)
from noetic_systems.reconciliation.graph import (
    build_evidence_graph,
)
from noetic_systems.reconciliation.metrics import (
    calculate_dispersion,
    calculate_modularity,
    document_specificity,
    document_support,
)
from noetic_systems.reconciliation.ranking import (
    normalize_feature,
    rank_basin_documents,
    rank_linked_evidence,
)
from noetic_systems.reconciliation.spectral import detect_communities
from noetic_systems.search.hybrid import HybridSearch
from noetic_systems.search.semantic import SearchResult


DEFAULT_TRACE_CASE_ID = "hotpot_big_stone_gap"
DEFAULT_TRACE_DATA_PATH = Path("docs/hotpot_big_stone_gap.json")
DEFAULT_TRACE_PATH = Path("docs/production_trace.json")
DEFAULT_TRACE_EDGE_THRESHOLD = 0.75


def generate_trace(
    *,
    data_path: Path = DEFAULT_TRACE_DATA_PATH,
    output_path: Path = DEFAULT_TRACE_PATH,
    case_id: str = DEFAULT_TRACE_CASE_ID,
    collection_name: str = "noetic_trace",
    blind: bool = True,
    max_points: int = 500,
    candidate_limit: int = 50,
    result_limit: int = 36,
    diffusion_steps: int = 4,
    damping: float = 0.85,
    edge_threshold: float = DEFAULT_TRACE_EDGE_THRESHOLD,
    calibrate_graph: bool = False,
    graph_objective: str = "reference_forward",
    calibration_sample: int = 500,
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
        calibrate_graph: Whether to derive corpus-level graph weights before
            graph construction.
        graph_objective: Label-free objective used for graph calibration.
        calibration_sample: Documents sampled for graph calibration.

    Returns:
        Trace dictionary written to `output_path`.
    """
    if graph_objective not in GRAPH_OBJECTIVES:
        raise ValueError(f"unknown graph objective: {graph_objective}")
    data = json.loads(data_path.read_text())
    case = data["cases"][case_id]
    target_ids = target_doc_ids(data, case_id)
    corpus = strip_custom_metadata(data) if blind else data["corpus"]

    database = Database(collection_name=collection_name, reset=True)
    try:
        database.add_documents(corpus)
        graph_weights = None
        if calibrate_graph:
            graph_weights, _profile = calibrate_corpus_graph_weights(
                database,
                sample_limit=calibration_sample,
                objective=graph_objective,
            )
        hybrid = HybridSearch(database)

        query = case["query"]
        candidates = hybrid.search(query, limit=candidate_limit)
        graph_candidates = candidates[:result_limit]
        doc_index = {result.id: result for result in graph_candidates}
        graph, evidence_edges = build_evidence_graph(
            database,
            doc_index,
            edge_threshold,
            weights=graph_weights,
        )
        communities = detect_communities(graph)

        energy = seed_energy(graph_candidates)
        initial_energy = dict(energy)

        whole_energy = dict(energy)
        whole_energy_steps = [dict(whole_energy)]
        for _ in range(diffusion_steps):
            whole_energy = diffuse(whole_energy, graph, damping)
            whole_energy_steps.append(dict(whole_energy))

        basin_graph = constrain_graph_to_communities(graph, communities)
        energy_steps = [dict(energy)]
        for _ in range(diffusion_steps):
            energy = diffuse(energy, basin_graph, damping)
            energy_steps.append(dict(energy))

        basins = build_basins(communities, energy, graph)
        basins = sorted(basins, key=lambda basin: basin.score, reverse=True)
        modularity = calculate_modularity(graph, communities)
        dispersion = calculate_dispersion(energy)
        uncertainty = calculate_uncertainty(basins, modularity, dispersion)
        whole_graph_energy_winner = hybrid_seed_winner(basins, whole_energy)

        specificity = document_specificity(graph_candidates)
        support = document_support(graph)
        return_documents = tuple(rank_linked_evidence(graph_candidates, graph))
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

        final_documents = return_documents[:5]
        visible_ids = select_visible_ids(
            data["corpus"],
            candidates,
            graph_candidates,
            [*list(final_documents), *list(winner.documents if winner else [])],
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
        final_ids = set(final_documents)
        winner_ids = set(winner.documents if winner else ())

        points = [
            point_record(
                doc_id,
                corpus_by_id[doc_id],
                coordinates[doc_id],
                candidate_ranks,
                graph_ranks,
                communities,
                whole_energy_steps,
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
                "calibrate_graph": calibrate_graph,
                "graph_objective": graph_objective,
                "calibration_sample": calibration_sample,
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
            "whole_energy_steps": whole_energy_steps,
            "energy_steps": energy_steps,
            "basins": [
                {
                    "id": basin.id,
                    "label": basin.label,
                    "score": basin.score,
                    "seed_energy": basin_seed_energy(basin.documents, initial_energy),
                    "whole_energy": basin_seed_energy(basin.documents, whole_energy),
                    "whole_energy_delta": basin_seed_energy(basin.documents, whole_energy)
                    - basin_seed_energy(basin.documents, initial_energy),
                    "energy": basin.energy,
                    "energy_delta": basin.energy
                    - basin_seed_energy(basin.documents, initial_energy),
                    "energy_component": 0.45 * basin.energy,
                    "support_component": 0.25
                    * min(1.0, basin.support / BASIN_SUPPORT_SATURATION),
                    "cohesion_component": 0.20 * basin.cohesion,
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
            "return_policy": "linked",
            "return_documents": list(return_documents),
            "final_chunks": final_chunk_records(
                list(final_documents),
                graph_candidates,
                graph,
                support,
            ),
            "metrics": {
                "modularity": modularity,
                "dispersion": dispersion,
                "uncertainty": uncertainty,
                "hybrid_seed_winner": hybrid_seed_winner(basins, initial_energy),
                "whole_graph_energy_winner": whole_graph_energy_winner,
                "flow_alignment": winner.label == whole_graph_energy_winner
                if winner
                else False,
                "target_fraction_top5": target_fraction(
                    final_documents,
                    target_ids,
                ),
            },
            "steps": [
                "corpus",
                "hybrid",
                "graph",
                "spectral",
                "whole-diffusion",
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
    whole_energy_steps: list[dict[str, float]],
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
        whole_energy_steps: Full-graph diffusion energy snapshots.
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
        "whole_energy": [
            float(step.get(doc_id, 0.0))
            for step in whole_energy_steps
        ],
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


def basin_seed_energy(
    doc_ids: list[str] | tuple[str, ...],
    initial_energy: dict[str, float],
) -> float:
    """Calculate the initial hybrid-seeded energy inside a basin.

    Args:
        doc_ids: Basin document ids.
        initial_energy: Energy assigned before diffusion starts.

    Returns:
        Total initial energy in the basin.
    """
    return float(sum(initial_energy.get(doc_id, 0.0) for doc_id in doc_ids))


def hybrid_seed_winner(
    basins: list[Any],
    initial_energy: dict[str, float],
) -> str:
    """Return the basin with the largest initial hybrid energy.

    Args:
        basins: Scored basins.
        initial_energy: Energy assigned before diffusion starts.

    Returns:
        Label of the basin that started with the most retrieval energy.
    """
    if not basins:
        return "none"
    return max(
        basins,
        key=lambda basin: basin_seed_energy(basin.documents, initial_energy),
    ).label


def final_chunk_records(
    doc_ids: list[str],
    graph_candidates: list[SearchResult],
    graph: dict[str, dict[str, float]],
    support: dict[str, float],
) -> list[dict[str, float | str]]:
    """Describe why final chunks were selected by linked-evidence ranking.

    Args:
        doc_ids: Final ranked document ids.
        graph_candidates: Candidates admitted to the local evidence graph.
        graph: Weighted adjacency mapping over graph candidates.
        support: Weighted graph degree by document id.

    Returns:
        Final chunk ranking records with normalized linked-rank components.
    """
    candidate_ids = [candidate.id for candidate in graph_candidates]
    anchors = candidate_ids[:4]
    query_score = normalize_feature(
        {candidate.id: candidate.score for candidate in graph_candidates}
    )
    support_score = normalize_feature(support)
    anchor_affinity = normalize_feature(
        {
            doc_id: max(
                (graph.get(doc_id, {}).get(anchor, 0.0) for anchor in anchors),
                default=0.0,
            )
            for doc_id in candidate_ids
        }
    )
    records = []
    for rank, doc_id in enumerate(doc_ids, start=1):
        is_anchor = doc_id in anchors
        linked_score = (
            1.0
            if is_anchor
            else (
                0.50 * query_score.get(doc_id, 0.0)
                + 0.35 * anchor_affinity.get(doc_id, 0.0)
                + 0.15 * support_score.get(doc_id, 0.0)
            )
        )
        records.append(
            {
                "id": doc_id,
                "rank": rank,
                "is_anchor": is_anchor,
                "query_score": float(query_score.get(doc_id, 0.0)),
                "anchor_affinity": float(anchor_affinity.get(doc_id, 0.0)),
                "support_score": float(support_score.get(doc_id, 0.0)),
                "support": float(support.get(doc_id, 0.0)),
                "rank_score": float(linked_score),
            }
        )
    return records


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
