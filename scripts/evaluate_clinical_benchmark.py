#!/usr/bin/env python
"""Evaluate compact clinical evidence retrieval.

This benchmark is retrieval-only. It does not diagnose, recommend treatment, or
score generated medical answers. Each case has a small set of gold evidence
chunks and plausible decoy chunks. The evaluator compares raw hybrid retrieval
with production Noetic linked-evidence retrieval using both standard IR metrics
and clinical evidence-safety metrics.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from noetic_systems.database import Database
from noetic_systems.evaluation.metrics import (
    add_metric_totals,
    average_metric_totals,
    empty_metric_totals,
    parse_k_values,
    ranking_metrics,
)
from noetic_systems.reconciliation.calibration import (
    GRAPH_OBJECTIVES,
    calibrate_corpus_graph_formula,
    calibrate_corpus_graph_weights,
)
from noetic_systems.reconciliation.basins import build_basins
from noetic_systems.reconciliation.diffusion import (
    constrain_graph_to_communities,
    diffuse,
    seed_energy,
)
from noetic_systems.reconciliation.engine import Reconciler
from noetic_systems.reconciliation.graph import build_evidence_graph
from noetic_systems.reconciliation.metrics import document_specificity
from noetic_systems.reconciliation.models import EvidenceEdge
from noetic_systems.reconciliation.ranking import rank_basin_documents
from noetic_systems.reconciliation.spectral import detect_communities

DEFAULT_K_VALUES = (1, 3, 5, 10)
UTILITY_LAMBDAS = (0.25, 0.5, 1.0)
SEMANTIC_EDGE_TYPES = {"embedding_similarity"}
LEXICAL_EDGE_TYPES = {"lexical_salience", "cross_reference"}
DUPLICATE_EDGE_TYPES = {"near_duplicate"}
SIGNATURE_FIELDS = (
    "hybrid_rank",
    "hybrid_score",
    "seed_energy",
    "final_energy",
    "diffusion_gain",
    "semantic_degree",
    "lexical_degree",
    "agreement_degree",
    "tension_degree",
    "duplicate_degree",
    "resonance_degree",
    "bridge_risk",
    "anchor_agreement",
    "anchor_tension",
    "anchor_resonance",
    "anchor_bridge_risk",
)


def document_ids_by_gold(data: dict[str, Any], case_id: str, label: str) -> set[str]:
    """Return document ids with a given gold label for one case.

    Args:
        data: Benchmark payload.
        case_id: Case identifier.
        label: Gold label to collect.

    Returns:
        Matching document ids.
    """
    return {
        doc["id"]
        for doc in data["corpus"]
        if doc["metadata"].get("case") == case_id
        and doc["metadata"].get("gold") == label
    }


def target_doc_ids(data: dict[str, Any], case_id: str) -> set[str]:
    """Return gold support document ids for one case.

    Args:
        data: Benchmark payload.
        case_id: Case identifier.

    Returns:
        Target evidence document ids.
    """
    return document_ids_by_gold(data, case_id, "target")


def dangerous_decoy_ids(data: dict[str, Any], case_id: str) -> set[str]:
    """Return decoy document ids for one case.

    Args:
        data: Benchmark payload.
        case_id: Case identifier.

    Returns:
        Decoy ids.
    """
    return document_ids_by_gold(data, case_id, "dangerous_decoy")


def critical_doc_ids(data: dict[str, Any], case_id: str) -> set[str]:
    """Return safety-critical target evidence ids for one case.

    Args:
        data: Benchmark payload.
        case_id: Case identifier.

    Returns:
        Target ids marked safety critical.
    """
    return {
        doc["id"]
        for doc in data["corpus"]
        if doc["metadata"].get("case") == case_id
        and doc["metadata"].get("gold") == "target"
        and doc["metadata"].get("safety_critical") is True
    }


def strip_custom_metadata(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Strip benchmark-only labels before indexing.

    Args:
        data: Benchmark payload.

    Returns:
        Corpus documents with deployable metadata only.
    """
    allowed = {"source", "domain", "title", "document_id"}
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


def clinical_metrics(
    ranked_ids: list[str] | tuple[str, ...],
    *,
    target_ids: set[str],
    critical_ids: set[str],
    decoy_ids: set[str],
    k: int,
) -> dict[str, float]:
    """Calculate clinical evidence retrieval metrics.

    Args:
        ranked_ids: Returned document ids.
        target_ids: Gold support document ids.
        critical_ids: Safety-critical support ids.
        decoy_ids: Decoy ids.
        k: Rank cutoff.

    Returns:
        Metrics for compact clinical evidence retrieval.
    """
    top_ids = set(ranked_ids[:k])
    exact_support = 1.0 if target_ids and target_ids.issubset(top_ids) else 0.0
    critical_recall = (
        len(top_ids & critical_ids) / len(critical_ids)
        if critical_ids
        else 0.0
    )
    decoy_rate = 1.0 if top_ids & decoy_ids else 0.0
    critical_miss_rate = 1.0 - critical_recall
    return {
        "exact_support": exact_support,
        "critical_recall": critical_recall,
        "critical_miss_rate": critical_miss_rate,
        "decoy_rate": decoy_rate,
    }


def add_clinical_totals(
    totals: dict[int, dict[str, float]],
    ranked_ids: list[str] | tuple[str, ...],
    *,
    target_ids: set[str],
    critical_ids: set[str],
    decoy_ids: set[str],
) -> None:
    """Accumulate clinical metrics for one ranked result.

    Args:
        totals: Mutable totals keyed by cutoff.
        ranked_ids: Returned document ids.
        target_ids: Gold support ids.
        critical_ids: Safety-critical support ids.
        decoy_ids: Decoy ids.

    Returns:
        None.
    """
    for k in totals:
        metrics = clinical_metrics(
            ranked_ids,
            target_ids=target_ids,
            critical_ids=critical_ids,
            decoy_ids=decoy_ids,
            k=k,
        )
        for name, value in metrics.items():
            totals[k][name] += value


def empty_clinical_totals(k_values: list[int]) -> dict[int, dict[str, float]]:
    """Create zeroed clinical metric totals.

    Args:
        k_values: Rank cutoffs.

    Returns:
        Clinical metric totals keyed by cutoff.
    """
    return {
        k: {
            "exact_support": 0.0,
            "critical_recall": 0.0,
            "critical_miss_rate": 0.0,
            "decoy_rate": 0.0,
        }
        for k in k_values
    }


def average_totals(
    totals: dict[int, dict[str, float]],
    count: int,
) -> dict[str, dict[str, float]]:
    """Average metric totals.

    Args:
        totals: Metric totals by cutoff.
        count: Number of cases.

    Returns:
        Averaged metrics keyed as `@k`.
    """
    denominator = count or 1
    return {
        f"@{k}": {
            name: value / denominator
            for name, value in metrics.items()
        }
        for k, metrics in totals.items()
    }


def pair_key(edge: EvidenceEdge) -> tuple[str, str]:
    """Return a stable undirected key for an evidence edge.

    Args:
        edge: Evidence edge to key.

    Returns:
        Sorted document-id pair.
    """
    return tuple(sorted((edge.source, edge.target)))


def normalize_edge_channel(
    values: dict[tuple[str, str], float],
) -> dict[tuple[str, str], float]:
    """Normalize one edge-signal channel to `[0, 1]`.

    Args:
        values: Raw edge-channel values by document pair.

    Returns:
        Normalized values by document pair.
    """
    maximum = max(values.values(), default=0.0)
    if maximum <= 0:
        return {key: 0.0 for key in values}
    return {
        key: value / maximum
        for key, value in values.items()
    }


def edge_signal_channels(
    edges: list[EvidenceEdge],
) -> dict[str, dict[tuple[str, str], float]]:
    """Split evidence edges into normalized semantic, lexical, and duplicate channels.

    Args:
        edges: Signal-contribution edge records.

    Returns:
        Normalized edge-channel values keyed by channel name and document pair.
    """
    semantic: dict[tuple[str, str], float] = {}
    lexical: dict[tuple[str, str], float] = {}
    duplicate: dict[tuple[str, str], float] = {}

    for edge in edges:
        key = pair_key(edge)
        if edge.type in SEMANTIC_EDGE_TYPES:
            semantic[key] = semantic.get(key, 0.0) + edge.weight
        elif edge.type in LEXICAL_EDGE_TYPES:
            lexical[key] = lexical.get(key, 0.0) + edge.weight
        elif edge.type in DUPLICATE_EDGE_TYPES:
            duplicate[key] = duplicate.get(key, 0.0) + edge.weight

    return {
        "semantic": normalize_edge_channel(semantic),
        "lexical": normalize_edge_channel(lexical),
        "duplicate": normalize_edge_channel(duplicate),
    }


def resonance_graph_from_channels(
    doc_ids: list[str],
    channels: dict[str, dict[tuple[str, str], float]],
    *,
    minimum_weight: float = 0.05,
) -> dict[str, dict[str, float]]:
    """Build a graph from semantic/lexical agreement and tension.

    Args:
        doc_ids: Candidate document ids admitted to the graph.
        channels: Normalized semantic, lexical, and duplicate edge channels.
        minimum_weight: Smallest retained resonance edge weight.

    Returns:
        Weighted adjacency mapping.
    """
    semantic = channels["semantic"]
    lexical = channels["lexical"]
    duplicate = channels["duplicate"]
    pairs = set(semantic) | set(lexical)
    graph: dict[str, dict[str, float]] = {doc_id: {} for doc_id in doc_ids}

    for left_id, right_id in pairs:
        semantic_value = semantic.get((left_id, right_id), 0.0)
        lexical_value = lexical.get((left_id, right_id), 0.0)
        duplicate_value = duplicate.get((left_id, right_id), 0.0)
        agreement = min(semantic_value, lexical_value)
        tension = abs(semantic_value - lexical_value)
        base = 0.50 * semantic_value + 0.50 * lexical_value

        # Agreement says both channels see a relationship. Tension says one
        # channel sees a strong relationship while the other does not. This is a
        # pure text/embedding signal: no medical labels, roles, or ontology.
        raw_weight = max(
            0.0,
            base
            + 0.75 * agreement
            - 0.45 * tension
            - 0.20 * duplicate_value,
        )
        weight = raw_weight / 1.75
        if weight >= minimum_weight:
            graph[left_id][right_id] = weight
            graph[right_id][left_id] = weight

    return graph


def resonance_graph_from_edges(
    doc_ids: list[str],
    edges: list[EvidenceEdge],
    *,
    minimum_weight: float = 0.05,
) -> dict[str, dict[str, float]]:
    """Build a resonance graph directly from evidence edge records.

    Args:
        doc_ids: Candidate document ids admitted to the graph.
        edges: Signal-contribution edge records.
        minimum_weight: Smallest retained resonance edge weight.

    Returns:
        Weighted adjacency mapping.
    """
    return resonance_graph_from_channels(
        doc_ids,
        edge_signal_channels(edges),
        minimum_weight=minimum_weight,
    )


def resonance_ranked_ids(
    reconciler: Reconciler,
    query: str,
    *,
    candidate_limit: int,
    edge_threshold: float,
    diffusion_steps: int = 10,
    damping: float = 0.85,
) -> list[str]:
    """Rank candidates with semantic/lexical resonance diffusion.

    Args:
        reconciler: Configured reconciliation engine.
        query: Query text.
        candidate_limit: Number of hybrid candidates retrieved and admitted into
            the local graph.
        edge_threshold: Minimum embedding similarity for semantic edges.
        diffusion_steps: Number of diffusion time steps.
        damping: Fraction of energy allowed to move per diffusion step.

    Returns:
        Ranked document ids from the strongest resonance basin.
    """
    graph_candidates = reconciler.hybrid.search(
        query,
        limit=candidate_limit,
        pool_limit=100,
    )
    if not graph_candidates:
        return []

    doc_index = {result.id: result for result in graph_candidates}
    _graph, edges = build_evidence_graph(
        reconciler.database,
        doc_index,
        edge_threshold,
        weights=reconciler.graph_weights,
    )
    graph = resonance_graph_from_edges(
        [result.id for result in graph_candidates],
        edges,
    )
    if not graph_edge_count(graph):
        return [result.id for result in graph_candidates]

    communities = detect_communities(graph)
    energy = seed_energy(graph_candidates)
    basin_graph = constrain_graph_to_communities(graph, communities)
    for _step in range(diffusion_steps):
        energy = diffuse(energy, basin_graph, damping)

    basins = sorted(
        build_basins(communities, energy, graph),
        key=lambda basin: basin.score,
        reverse=True,
    )
    if not basins:
        return [result.id for result in graph_candidates]

    specificity = document_specificity(graph_candidates)
    winner_ids = list(basins[0].documents)
    return rank_basin_documents(winner_ids, energy, specificity)


def signal_between(
    channels: dict[str, dict[tuple[str, str], float]],
    left_id: str,
    right_id: str,
) -> dict[str, float]:
    """Return pairwise channel values and derived tension terms.

    Args:
        channels: Normalized edge channels.
        left_id: First document id.
        right_id: Second document id.

    Returns:
        Semantic, lexical, duplicate, agreement, and tension values.
    """
    key = tuple(sorted((left_id, right_id)))
    semantic = channels["semantic"].get(key, 0.0)
    lexical = channels["lexical"].get(key, 0.0)
    duplicate = channels["duplicate"].get(key, 0.0)
    return {
        "semantic": semantic,
        "lexical": lexical,
        "duplicate": duplicate,
        "agreement": min(semantic, lexical),
        "tension": abs(semantic - lexical),
    }


def document_signature(
    doc_id: str,
    *,
    graph_candidates: list[Any],
    channels: dict[str, dict[tuple[str, str], float]],
    base_graph: dict[str, dict[str, float]],
    resonance_graph: dict[str, dict[str, float]],
    communities: dict[str, int],
    initial_energy: dict[str, float],
    final_energy: dict[str, float],
    anchors: list[str],
) -> dict[str, Any]:
    """Measure one document's structural retrieval fingerprint.

    Args:
        doc_id: Document id to inspect.
        graph_candidates: Candidate search results admitted to the graph.
        channels: Normalized edge channels.
        base_graph: Original evidence graph.
        resonance_graph: Agreement/tension graph.
        communities: Spectral basin assignment.
        initial_energy: Seed energy before diffusion.
        final_energy: Energy after basin-constrained diffusion.
        anchors: Early hybrid ids used as query anchors.

    Returns:
        Inspectable document-level signature.
    """
    candidate_ids = [candidate.id for candidate in graph_candidates]
    candidate_by_id = {
        candidate.id: candidate
        for candidate in graph_candidates
    }
    rank_by_id = {
        candidate.id: index + 1
        for index, candidate in enumerate(graph_candidates)
    }
    semantic_degree = 0.0
    lexical_degree = 0.0
    duplicate_degree = 0.0
    agreement_degree = 0.0
    tension_degree = 0.0

    for other_id in candidate_ids:
        if other_id == doc_id:
            continue
        pair = signal_between(channels, doc_id, other_id)
        semantic_degree += pair["semantic"]
        lexical_degree += pair["lexical"]
        duplicate_degree += pair["duplicate"]
        agreement_degree += pair["agreement"]
        tension_degree += pair["tension"]

    anchor_pairs = [
        signal_between(channels, doc_id, anchor_id)
        for anchor_id in anchors
        if anchor_id != doc_id
    ]
    anchor_agreement = max(
        (pair["agreement"] for pair in anchor_pairs),
        default=0.0,
    )
    anchor_tension = max(
        (pair["tension"] for pair in anchor_pairs),
        default=0.0,
    )
    anchor_resonance = max(
        (
            resonance_graph.get(doc_id, {}).get(anchor_id, 0.0)
            for anchor_id in anchors
            if anchor_id != doc_id
        ),
        default=0.0,
    )
    bridge_denominator = semantic_degree + lexical_degree
    bridge_risk = (
        tension_degree / bridge_denominator
        if bridge_denominator > 0
        else 0.0
    )
    anchor_denominator = anchor_agreement + anchor_tension
    anchor_bridge_risk = (
        anchor_tension / anchor_denominator
        if anchor_denominator > 0
        else 0.0
    )
    seed = initial_energy.get(doc_id, 0.0)
    final = final_energy.get(doc_id, 0.0)
    candidate = candidate_by_id.get(doc_id)

    return {
        "doc_id": doc_id,
        "hybrid_rank": rank_by_id.get(doc_id),
        "hybrid_score": candidate.score if candidate else 0.0,
        "basin": communities.get(doc_id),
        "seed_energy": seed,
        "final_energy": final,
        "diffusion_gain": final - seed,
        "semantic_degree": semantic_degree,
        "lexical_degree": lexical_degree,
        "agreement_degree": agreement_degree,
        "tension_degree": tension_degree,
        "duplicate_degree": duplicate_degree,
        "base_graph_degree": sum(base_graph.get(doc_id, {}).values()),
        "resonance_degree": sum(resonance_graph.get(doc_id, {}).values()),
        "bridge_risk": bridge_risk,
        "anchor_agreement": anchor_agreement,
        "anchor_tension": anchor_tension,
        "anchor_resonance": anchor_resonance,
        "anchor_bridge_risk": anchor_bridge_risk,
    }


def case_graph_diagnostics(
    reconciler: Reconciler,
    query: str,
    *,
    candidate_limit: int,
    edge_threshold: float,
    diffusion_steps: int = 10,
    damping: float = 0.85,
) -> dict[str, Any]:
    """Compute reusable graph diagnostics for one clinical case.

    Args:
        reconciler: Configured reconciliation engine.
        query: Query text.
        candidate_limit: Number of hybrid candidates retrieved and admitted into
            the local graph.
        edge_threshold: Minimum embedding similarity for semantic edges.
        diffusion_steps: Number of diffusion time steps.
        damping: Fraction of energy allowed to move per diffusion step.

    Returns:
        Graph candidates, channels, communities, energy, and resonance ranking.
    """
    graph_candidates = reconciler.hybrid.search(
        query,
        limit=candidate_limit,
        pool_limit=100,
    )
    doc_index = {result.id: result for result in graph_candidates}
    base_graph, edges = build_evidence_graph(
        reconciler.database,
        doc_index,
        edge_threshold,
        weights=reconciler.graph_weights,
    )
    candidate_ids = [result.id for result in graph_candidates]
    channels = edge_signal_channels(edges)
    resonance_graph = resonance_graph_from_channels(candidate_ids, channels)
    initial_energy = seed_energy(graph_candidates)
    final_energy = dict(initial_energy)

    if graph_edge_count(resonance_graph):
        communities = detect_communities(resonance_graph)
        basin_graph = constrain_graph_to_communities(resonance_graph, communities)
        for _step in range(diffusion_steps):
            final_energy = diffuse(final_energy, basin_graph, damping)

        basins = sorted(
            build_basins(communities, final_energy, resonance_graph),
            key=lambda basin: basin.score,
            reverse=True,
        )
        specificity = document_specificity(graph_candidates)
        if basins:
            resonance_ids = rank_basin_documents(
                list(basins[0].documents),
                final_energy,
                specificity,
            )
        else:
            resonance_ids = candidate_ids
    else:
        communities = {doc_id: 0 for doc_id in candidate_ids}
        resonance_ids = candidate_ids

    return {
        "graph_candidates": graph_candidates,
        "base_graph": base_graph,
        "resonance_graph": resonance_graph,
        "channels": channels,
        "communities": communities,
        "initial_energy": initial_energy,
        "final_energy": final_energy,
        "resonance_ids": resonance_ids,
    }


def graph_edge_count(graph: dict[str, dict[str, float]]) -> int:
    """Count undirected edges in an adjacency graph.

    Args:
        graph: Weighted adjacency mapping.

    Returns:
        Number of undirected edges.
    """
    return sum(len(neighbors) for neighbors in graph.values()) // 2


def guarded_resonance_ids(
    *,
    resonance_ids: list[str],
    hybrid_ids: list[str],
    signatures_by_doc: dict[str, dict[str, Any]],
    limit: int,
) -> list[str]:
    """Return resonance-ranked ids only when graph evidence supports them.

    Args:
        resonance_ids: Candidate ids ranked by resonance diffusion.
        hybrid_ids: Raw hybrid ids used as conservative fallback.
        signatures_by_doc: Document signatures keyed by document id.
        limit: Maximum number of ids to return.

    Returns:
        Ranked ids with unsupported resonance promotions removed.
    """
    accepted: list[str] = []
    for doc_id in resonance_ids:
        signature = signatures_by_doc.get(doc_id, {})
        has_resonance = signature.get("resonance_degree", 0.0) > 0
        is_anchor = signature.get("hybrid_rank") in {1, 2, 3, 4}
        if has_resonance or is_anchor:
            accepted.append(doc_id)

    for doc_id in hybrid_ids:
        if doc_id not in accepted:
            accepted.append(doc_id)
        if len(accepted) >= limit:
            break

    return accepted[:limit]


def risk_aware_resonance_ids(
    *,
    candidate_ids: list[str],
    signatures_by_doc: dict[str, dict[str, Any]],
    limit: int,
) -> list[str]:
    """Rank candidates by resonance support minus bridge risk.

    Args:
        candidate_ids: Candidate ids in hybrid order.
        signatures_by_doc: Document signatures keyed by document id.
        limit: Maximum number of ids to return.

    Returns:
        Ranked ids using label-free graph risk terms.
    """
    energy = normalize_signature_field(signatures_by_doc, "final_energy")
    resonance = normalize_signature_field(signatures_by_doc, "resonance_degree")
    anchor = normalize_signature_field(signatures_by_doc, "anchor_resonance")
    anchors = [
        doc_id
        for doc_id in candidate_ids
        if int(signatures_by_doc.get(doc_id, {}).get("hybrid_rank") or 10**9) <= 4
    ]

    def score(doc_id: str) -> tuple[float, int]:
        """Score one candidate for risk-aware ranking.

        Args:
            doc_id: Candidate document id.

        Returns:
            Descending score and ascending hybrid order.
        """
        signature = signatures_by_doc.get(doc_id, {})
        rank = int(signature.get("hybrid_rank") or 10**9)
        bridge_risk = float(signature.get("bridge_risk") or 0.0)
        anchor_bridge_risk = float(signature.get("anchor_bridge_risk") or 0.0)
        value = (
            0.30 * energy.get(doc_id, 0.0)
            + 0.30 * resonance.get(doc_id, 0.0)
            + 0.20 * anchor.get(doc_id, 0.0)
            - 0.35 * bridge_risk
            - 0.25 * anchor_bridge_risk
        )
        return value, -rank

    promoted = sorted(
        [doc_id for doc_id in candidate_ids if doc_id not in anchors],
        key=score,
        reverse=True,
    )
    return (anchors + promoted)[:limit]


def normalize_signature_field(
    signatures_by_doc: dict[str, dict[str, Any]],
    field: str,
) -> dict[str, float]:
    """Normalize a numeric signature field to `[0, 1]`.

    Args:
        signatures_by_doc: Document signatures keyed by document id.
        field: Numeric field name.

    Returns:
        Normalized values by document id.
    """
    values = {
        doc_id: float(signature.get(field) or 0.0)
        for doc_id, signature in signatures_by_doc.items()
    }
    maximum = max(values.values(), default=0.0)
    if maximum <= 0:
        return {doc_id: 0.0 for doc_id in values}
    return {
        doc_id: value / maximum
        for doc_id, value in values.items()
    }


def summarize_signature_groups(
    signatures: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Aggregate target and dangerous-decoy graph fingerprints.

    Args:
        signatures: Per-document signatures collected across benchmark cases.

    Returns:
        Group counts and mean diagnostic values.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for signature in signatures:
        groups.setdefault(signature["signature_group"], []).append(signature)

    summary: dict[str, dict[str, Any]] = {}
    for name, group in groups.items():
        summary[name] = {"count": len(group)}
        for field in SIGNATURE_FIELDS:
            values = [
                float(signature[field])
                for signature in group
                if signature.get(field) is not None
            ]
            summary[name][field] = sum(values) / len(values) if values else 0.0
    return summary


def clinical_utility(
    clinical: dict[str, dict[str, dict[str, float]]],
    k_values: list[int],
) -> dict[str, dict[str, dict[str, float]]]:
    """Calculate clinical utility under several decoy penalties.

    Args:
        clinical: Clinical metrics by variant and cutoff.
        k_values: Rank cutoffs.

    Returns:
        Utility scores by penalty and variant.
    """
    utility: dict[str, dict[str, dict[str, float]]] = {}
    for penalty in UTILITY_LAMBDAS:
        penalty_key = f"lambda_{penalty:g}"
        utility[penalty_key] = {}
        for variant, metrics_by_k in clinical.items():
            utility[penalty_key][variant] = {}
            for k in k_values:
                values = metrics_by_k[f"@{k}"]
                utility[penalty_key][variant][f"@{k}"] = (
                    values["critical_recall"]
                    - penalty * values["decoy_rate"]
                )
    return utility


def clinical_frontier(
    clinical: dict[str, dict[str, dict[str, float]]],
    k_values: list[int],
) -> dict[str, list[dict[str, Any]]]:
    """Build recall/risk frontier points for reporting.

    Args:
        clinical: Clinical metrics by variant and cutoff.
        k_values: Rank cutoffs.

    Returns:
        Frontier points keyed by cutoff.
    """
    frontier: dict[str, list[dict[str, Any]]] = {}
    for k in k_values:
        key = f"@{k}"
        points = [
            {
                "variant": variant,
                "critical_recall": metrics_by_k[key]["critical_recall"],
                "decoy_rate": metrics_by_k[key]["decoy_rate"],
                "exact_support": metrics_by_k[key]["exact_support"],
            }
            for variant, metrics_by_k in clinical.items()
        ]
        frontier[key] = sorted(
            points,
            key=lambda point: (
                point["decoy_rate"],
                -point["critical_recall"],
                point["variant"],
            ),
        )
    return frontier


def print_tables(
    ranking: dict[str, dict[str, dict[str, float]]],
    clinical: dict[str, dict[str, dict[str, float]]],
    utility: dict[str, dict[str, dict[str, float]]],
    k_values: list[int],
) -> None:
    """Print standard and clinical metric tables.

    Args:
        ranking: Ranking metrics by variant and cutoff.
        clinical: Clinical metrics by variant and cutoff.
        k_values: Cutoffs to print.

    Returns:
        None.
    """
    print("=== RANKING METRICS ===")
    print("variant            k   P@k    R@k    Hit@k  MRR@k")
    for variant, metrics_by_k in ranking.items():
        for k in k_values:
            values = metrics_by_k[f"@{k}"]
            print(
                f"{variant:18} {k:2d}  "
                f"{values['precision']:.3f}  "
                f"{values['recall']:.3f}  "
                f"{values['hit']:.3f}  "
                f"{values['mrr']:.3f}"
            )

    print()
    print("=== CLINICAL RETRIEVAL METRICS ===")
    print(
        "variant            k   exact  "
        "critical_recall  critical_miss  decoy_rate"
    )
    for variant, metrics_by_k in clinical.items():
        for k in k_values:
            values = metrics_by_k[f"@{k}"]
            print(
                f"{variant:18} {k:2d}  "
                f"{values['exact_support']:.3f}  "
                f"{values['critical_recall']:.3f}            "
                f"{values['critical_miss_rate']:.3f}          "
                f"{values['decoy_rate']:.3f}"
            )

    print()
    print("=== CLINICAL UTILITY ===")
    print("utility = critical_recall - lambda * decoy_rate")
    print("variant            k   lambda  utility")
    for penalty_key, variants in utility.items():
        penalty = penalty_key.removeprefix("lambda_")
        for variant, metrics_by_k in variants.items():
            for k in k_values:
                print(
                    f"{variant:18} {k:2d}  "
                    f"{penalty:>6}  "
                    f"{metrics_by_k[f'@{k}']:.3f}"
                )


def main() -> None:
    """Run the clinical evidence retrieval benchmark.

    Args:
        None.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-path",
        type=Path,
        default=Path("tests/data/clinical_evidence_benchmark.json"),
    )
    parser.add_argument("--collection-name", default="clinical_evidence_eval")
    parser.add_argument("--blind", action="store_true")
    parser.add_argument("--candidate-limit", type=int, default=30)
    parser.add_argument("--edge-threshold", type=float, default=0.5)
    parser.add_argument("--ks", type=parse_k_values, default=list(DEFAULT_K_VALUES))
    parser.add_argument("--limit-cases", type=int, default=None)
    parser.add_argument("--json-report", type=Path, default=None)
    parser.add_argument("--calibrate-graph", action="store_true")
    parser.add_argument(
        "--graph-objective",
        choices=GRAPH_OBJECTIVES,
        default="reference_forward",
    )
    parser.add_argument("--calibration-sample", type=int, default=500)
    args = parser.parse_args()

    data = json.loads(args.data_path.read_text())
    corpus = strip_custom_metadata(data) if args.blind else data["corpus"]

    database = Database(collection_name=args.collection_name, reset=True)
    database.add_documents(corpus)
    graph_weights = None
    auto_calibration = None
    if args.calibrate_graph:
        if args.graph_objective == "auto":
            auto_calibration = calibrate_corpus_graph_formula(
                database,
                sample_limit=args.calibration_sample,
            )
            graph_weights = auto_calibration.selected.weights
        else:
            graph_weights, _profile = calibrate_corpus_graph_weights(
                database,
                sample_limit=args.calibration_sample,
                objective=args.graph_objective,
            )
    reconciler = Reconciler(database, graph_weights=graph_weights)

    case_items = list(data["cases"].items())
    if args.limit_cases is not None:
        case_items = case_items[: args.limit_cases]

    max_k = max(args.ks)
    variants = (
        "hybrid",
        "noetic_linked",
        "noetic_diffusion",
        "noetic_resonance",
        "noetic_resonance_guarded",
        "noetic_resonance_risk_aware",
    )
    ranking_totals = {variant: empty_metric_totals(args.ks) for variant in variants}
    clinical_totals = {variant: empty_clinical_totals(args.ks) for variant in variants}
    rows = []
    signatures: list[dict[str, Any]] = []
    hybrid_times: list[float] = []
    noetic_times: list[float] = []

    for case_id, case in case_items:
        query = case["query"]
        targets = target_doc_ids(data, case_id)
        critical = critical_doc_ids(data, case_id)
        decoys = dangerous_decoy_ids(data, case_id)

        start = time.perf_counter()
        hybrid_ids = reconciler.hybrid_baseline(query, limit=max_k)
        hybrid_times.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        linked_result = reconciler.reconcile(
            query,
            candidate_limit=args.candidate_limit,
            edge_threshold=args.edge_threshold,
        )
        diffusion_result = reconciler.reconcile(
            query,
            candidate_limit=args.candidate_limit,
            edge_threshold=args.edge_threshold,
            return_policy="basin",
        )
        noetic_times.append((time.perf_counter() - start) * 1000)
        linked_ids = linked_result.document_ids(max_k)
        diffusion_ids = diffusion_result.document_ids(max_k)
        diagnostics = case_graph_diagnostics(
            reconciler,
            query,
            candidate_limit=args.candidate_limit,
            edge_threshold=args.edge_threshold,
        )
        resonance_ids = diagnostics["resonance_ids"][:max_k]
        graph_candidates = diagnostics["graph_candidates"]
        graph_candidate_ids = {candidate.id for candidate in graph_candidates}
        signatures_by_doc = {
            candidate.id: document_signature(
                candidate.id,
                graph_candidates=graph_candidates,
                channels=diagnostics["channels"],
                base_graph=diagnostics["base_graph"],
                resonance_graph=diagnostics["resonance_graph"],
                communities=diagnostics["communities"],
                initial_energy=diagnostics["initial_energy"],
                final_energy=diagnostics["final_energy"],
                anchors=[candidate.id for candidate in graph_candidates[:4]],
            )
            for candidate in graph_candidates
        }
        guarded_ids = guarded_resonance_ids(
            resonance_ids=diagnostics["resonance_ids"],
            hybrid_ids=hybrid_ids,
            signatures_by_doc=signatures_by_doc,
            limit=max_k,
        )
        risk_aware_ids = risk_aware_resonance_ids(
            candidate_ids=[candidate.id for candidate in graph_candidates],
            signatures_by_doc=signatures_by_doc,
            limit=max_k,
        )

        for variant, ranked_ids in {
            "hybrid": hybrid_ids,
            "noetic_linked": linked_ids,
            "noetic_diffusion": diffusion_ids,
            "noetic_resonance": resonance_ids,
            "noetic_resonance_guarded": guarded_ids,
            "noetic_resonance_risk_aware": risk_aware_ids,
        }.items():
            add_metric_totals(ranking_totals[variant], ranked_ids, targets)
            add_clinical_totals(
                clinical_totals[variant],
                ranked_ids,
                target_ids=targets,
                critical_ids=critical,
                decoy_ids=decoys,
            )

        selected_by_doc: dict[str, list[str]] = {}
        for variant, ranked_ids in {
            "hybrid": hybrid_ids,
            "noetic_linked": linked_ids,
            "noetic_diffusion": diffusion_ids,
            "noetic_resonance": resonance_ids,
            "noetic_resonance_guarded": guarded_ids,
            "noetic_resonance_risk_aware": risk_aware_ids,
        }.items():
            for doc_id in ranked_ids[:max_k]:
                selected_by_doc.setdefault(doc_id, []).append(variant)

        inspected_ids = (
            (
                targets
                | decoys
                | set(linked_ids)
                | set(diffusion_ids)
                | set(resonance_ids)
                | set(guarded_ids)
                | set(risk_aware_ids)
            )
            & graph_candidate_ids
        )
        case_signatures = []
        for doc_id in sorted(inspected_ids):
            if doc_id in targets:
                gold_label = "target"
            elif doc_id in decoys:
                gold_label = "dangerous_decoy"
            else:
                gold_label = "background"
            selected_by = selected_by_doc.get(doc_id, [])
            if gold_label == "target":
                signature_group = "target_retrieved" if selected_by else "target_missed"
            elif gold_label == "dangerous_decoy":
                signature_group = (
                    "decoy_retrieved"
                    if selected_by
                    else "decoy_not_retrieved"
                )
            else:
                signature_group = "background_retrieved"

            signature = dict(signatures_by_doc[doc_id])
            signature.update(
                {
                    "case": case_id,
                    "gold": gold_label,
                    "selected_by": selected_by,
                    "signature_group": signature_group,
                }
            )
            signatures.append(signature)
            case_signatures.append(signature)

        rows.append(
            {
                "case": case_id,
                "query": query,
                "answer": case.get("answer", ""),
                "target_ids": sorted(targets),
                "critical_ids": sorted(critical),
                "dangerous_decoy_ids": sorted(decoys),
                "hybrid_ids": hybrid_ids,
                "noetic_linked_ids": linked_ids,
                "noetic_diffusion_ids": diffusion_ids,
                "noetic_resonance_ids": resonance_ids,
                "noetic_resonance_guarded_ids": guarded_ids,
                "noetic_resonance_risk_aware_ids": risk_aware_ids,
                "diffusion_winner": diffusion_result.winner.label,
                "diffusion_uncertainty": diffusion_result.uncertainty,
                "clinical_signatures": case_signatures,
                "hybrid_at_5": ranking_metrics(hybrid_ids, targets, 5),
                "noetic_linked_at_5": ranking_metrics(linked_ids, targets, 5),
                "noetic_diffusion_at_5": ranking_metrics(diffusion_ids, targets, 5),
                "noetic_resonance_at_5": ranking_metrics(resonance_ids, targets, 5),
                "noetic_resonance_guarded_at_5": ranking_metrics(
                    guarded_ids,
                    targets,
                    5,
                ),
                "noetic_resonance_risk_aware_at_5": ranking_metrics(
                    risk_aware_ids,
                    targets,
                    5,
                ),
                "hybrid_clinical_at_5": clinical_metrics(
                    hybrid_ids,
                    target_ids=targets,
                    critical_ids=critical,
                    decoy_ids=decoys,
                    k=5,
                ),
                "noetic_linked_clinical_at_5": clinical_metrics(
                    linked_ids,
                    target_ids=targets,
                    critical_ids=critical,
                    decoy_ids=decoys,
                    k=5,
                ),
                "noetic_diffusion_clinical_at_5": clinical_metrics(
                    diffusion_ids,
                    target_ids=targets,
                    critical_ids=critical,
                    decoy_ids=decoys,
                    k=5,
                ),
                "noetic_resonance_clinical_at_5": clinical_metrics(
                    resonance_ids,
                    target_ids=targets,
                    critical_ids=critical,
                    decoy_ids=decoys,
                    k=5,
                ),
                "noetic_resonance_guarded_clinical_at_5": clinical_metrics(
                    guarded_ids,
                    target_ids=targets,
                    critical_ids=critical,
                    decoy_ids=decoys,
                    k=5,
                ),
                "noetic_resonance_risk_aware_clinical_at_5": clinical_metrics(
                    risk_aware_ids,
                    target_ids=targets,
                    critical_ids=critical,
                    decoy_ids=decoys,
                    k=5,
                ),
            }
        )

    total = len(case_items)
    ranking = {
        variant: average_metric_totals(totals, total)
        for variant, totals in ranking_totals.items()
    }
    clinical = {
        variant: average_totals(totals, total)
        for variant, totals in clinical_totals.items()
    }
    utility = clinical_utility(clinical, args.ks)
    frontier = clinical_frontier(clinical, args.ks)
    report = {
        "dataset": "synthetic_clinical_evidence",
        "cases": total,
        "documents": len(data["corpus"]),
        "candidate_limit": args.candidate_limit,
        "edge_threshold": args.edge_threshold,
        "calibrate_graph": args.calibrate_graph,
        "graph_objective": args.graph_objective,
        "auto_graph_objective": (
            auto_calibration.selected.objective
            if auto_calibration
            else None
        ),
        "auto_graph_score": (
            auto_calibration.selected.score
            if auto_calibration
            else None
        ),
        "ks": args.ks,
        "ranking": ranking,
        "clinical": clinical,
        "clinical_utility": utility,
        "clinical_frontier": frontier,
        "signature_summary": summarize_signature_groups(signatures),
        "latency_ms": {
            "hybrid_mean": sum(hybrid_times) / len(hybrid_times)
            if hybrid_times
            else 0.0,
            "noetic_mean": sum(noetic_times) / len(noetic_times)
            if noetic_times
            else 0.0,
        },
        "disclaimer": (
            "Synthetic retrieval benchmark only. Not medical advice, diagnosis, "
            "or clinical decision support."
        ),
    }

    print("=== CLINICAL EVIDENCE RETRIEVAL BENCHMARK ===")
    print(f"cases: {total}")
    print(f"documents: {len(data['corpus'])}")
    print(f"candidate limit: {args.candidate_limit}")
    print(f"edge threshold: {args.edge_threshold:.2f}")
    print(f"calibrate graph: {args.calibrate_graph}")
    print()
    print_tables(ranking, clinical, utility, args.ks)

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps({"metrics": report, "rows": rows}, indent=2))

    database.reset()


if __name__ == "__main__":
    main()
