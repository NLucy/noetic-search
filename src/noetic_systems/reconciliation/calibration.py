"""Unsupervised calibration for evidence graph construction.

Calibration estimates graph-weight settings from corpus-level document
structure without using queries, gold labels, answer correctness, or LLM
judgment. It measures the shape of pairwise semantic similarity, lexical
salience, explicit cross-reference frequency, and graph health, then returns a
single `GraphWeights` record that can be reused for queries over that index.

The purpose is not to infer answer correctness from the corpus. The purpose is
to avoid a single global edge formula when corpora have different structure. A
corpus with many explicit cross-references can safely give those edges more
weight. A corpus with sparse lexical salience should avoid overvaluing weak
shared tokens. A corpus with many near-duplicates should keep duplicate
contribution small and inspectable.

`GraphHealthConfig` makes the scoring objective explicit. The default config is
an inspectable operating prior, not a theoretically optimal law. Benchmark work
can train that config on development cases and freeze it for held-out evaluation
without changing any query-specific weights.

Key variables:
    `semantic_values`: Pairwise embedding similarities inside the candidate
        field.
    `lexical_values`: Pairwise lexical salience overlaps inside the candidate
        field.
    `cross_reference_rate`: Fraction of candidate pairs where one chunk names
        the title-like label of the other.
    `graph_density`: Estimated fraction of candidate pairs that become edges
        under calibrated thresholds.
    `largest_component_ratio`: Fraction of nodes in the largest connected
        component under calibrated thresholds.
    `degree_centralization`: Freeman degree centralization. Higher values mean
        edge mass is concentrated around a small number of hubs.
    `degree_skew`: Estimated max degree divided by mean degree. This remains in
        the profile as a simple diagnostic beside degree centralization.
    `duplicate_rate`: Fraction of candidate pairs above the near-duplicate
        threshold.
    `semantic_threshold`: Calibrated minimum similarity for semantic edges.
    `lexical_threshold`: Calibrated minimum salience overlap for lexical edges.
    `cross_reference_weight`: Calibrated weight for explicit text links.
"""

from __future__ import annotations

from dataclasses import dataclass

from noetic_systems.database import Database
from noetic_systems.reconciliation.graph import (
    GraphWeights,
    cosine_similarity,
    cross_reference,
    candidate_salience_maps,
    title_like_label,
    salience_overlap,
)
from noetic_systems.search.semantic import SearchResult

GRAPH_OBJECTIVES = (
    "auto",
    "balanced",
    "sparse",
    "dense",
    "semantic_heavy",
    "lexical_salience_heavy",
    "reference_forward",
    "anti_hub",
    "duplicate_conservative",
)
MANUAL_GRAPH_OBJECTIVES = tuple(
    objective
    for objective in GRAPH_OBJECTIVES
    if objective != "auto"
)


@dataclass(frozen=True)
class CalibrationProfile:
    """Measurements used to calibrate graph construction.

    Attributes:
        semantic_p75: Seventy-fifth percentile pairwise semantic similarity.
        semantic_p90: Ninetieth percentile pairwise semantic similarity.
        lexical_p75: Seventy-fifth percentile pairwise lexical salience overlap.
        lexical_p90: Ninetieth percentile pairwise lexical salience overlap.
        cross_reference_rate: Fraction of candidate pairs with explicit
            cross-reference evidence.
        graph_density: Estimated graph density after calibration.
        largest_component_ratio: Fraction of nodes in the largest connected
            component after calibration.
        degree_centralization: Freeman degree centralization after calibration.
        degree_skew: Estimated max degree divided by mean degree after
            calibration.
        duplicate_rate: Fraction of pairs above the near-duplicate threshold.
        pair_count: Number of candidate pairs measured.
    """

    semantic_p75: float
    semantic_p90: float
    lexical_p75: float
    lexical_p90: float
    cross_reference_rate: float
    graph_density: float
    largest_component_ratio: float
    degree_centralization: float
    degree_skew: float
    duplicate_rate: float
    pair_count: int


@dataclass(frozen=True)
class CandidateSignals:
    """Pairwise candidate-field signals used by calibration.

    Attributes:
        ids: Candidate ids in graph order.
        semantic_values: Pairwise embedding similarities.
        lexical_values: Pairwise lexical salience overlap scores.
        cross_reference_pairs: Candidate id pairs with explicit cross-reference.
        duplicate_rate: Fraction of pairs above the near-duplicate threshold.
    """

    ids: list[str]
    semantic_values: list[float]
    lexical_values: list[float]
    cross_reference_pairs: set[tuple[str, str]]
    duplicate_rate: float


@dataclass(frozen=True)
class GraphHealthConfig:
    """Operating ranges and weights for graph-health scoring.

    The measurements are standard graph or retrieval measurements. This config
    makes the operating ranges explicit so they can be trained on development
    corpora and then frozen for held-out evaluation.

    Attributes:
        density_target: Preferred graph density.
        density_left_width: Sparse-side tolerance for density scoring.
        density_right_width: Dense-side tolerance for density scoring.
        lcc_target: Preferred largest connected component ratio.
        lcc_left_width: Fragmentation-side tolerance for component scoring.
        lcc_right_width: Collapse-side tolerance for component scoring.
        centralization_start: Freeman centralization value where hub penalty
            begins.
        centralization_stop: Freeman centralization value where hub penalty is
            complete.
        duplicate_start: Duplicate rate where penalty begins.
        duplicate_stop: Duplicate rate where penalty is complete.
        agreement_target: Preferred agreement-edge density.
        agreement_left_width: Low-agreement tolerance.
        agreement_right_width: High-agreement tolerance.
        bridge_start: Semantic-only bridge rate where penalty begins.
        bridge_stop: Semantic-only bridge rate where penalty is complete.
        density_weight: Weight for density score.
        connectivity_weight: Weight for largest-component score.
        centralization_weight: Weight for degree-centralization score.
        duplicate_weight: Weight for duplicate score.
        lexical_weight: Weight for lexical-fit score.
        resonance_weight: Weight for agreement-density score.
        bridge_weight: Weight for bridge-safety score.
    """

    density_target: float = 0.16
    density_left_width: float = 0.12
    density_right_width: float = 0.20
    lcc_target: float = 0.82
    lcc_left_width: float = 0.42
    lcc_right_width: float = 0.18
    centralization_start: float = 0.18
    centralization_stop: float = 0.55
    duplicate_start: float = 0.04
    duplicate_stop: float = 0.18
    agreement_target: float = 0.06
    agreement_left_width: float = 0.04
    agreement_right_width: float = 0.14
    bridge_start: float = 0.20
    bridge_stop: float = 0.70
    density_weight: float = 0.20
    connectivity_weight: float = 0.14
    centralization_weight: float = 0.14
    duplicate_weight: float = 0.12
    lexical_weight: float = 0.13
    resonance_weight: float = 0.20
    bridge_weight: float = 0.15


@dataclass(frozen=True)
class GraphHealthScore:
    """Unsupervised score for a candidate graph formula.

    Attributes:
        objective: Candidate objective family.
        score: Final graph-health score in the `[0, 1]` interval.
        density_score: Reward for forming enough edges without collapsing into
            a dense blob.
        connectivity_score: Reward for keeping most sampled nodes in a usable
            graph component without requiring complete connectivity.
        centralization_score: Reward for low Freeman degree centralization.
        duplicate_score: Reward for keeping duplicate pressure modest.
        lexical_score: Reward for using lexical salience only when it exists in
            the corpus.
        resonance_score: Reward for retaining semantic-plus-lexical agreement
            edges that diffusion can actually use.
        bridge_score: Reward for avoiding semantic-only bridge edges.
        profile: Corpus profile under the candidate weights.
        weights: Candidate graph weights.
    """

    objective: str
    score: float
    density_score: float
    connectivity_score: float
    centralization_score: float
    duplicate_score: float
    lexical_score: float
    resonance_score: float
    bridge_score: float
    profile: CalibrationProfile
    weights: GraphWeights


@dataclass(frozen=True)
class AutoCalibrationResult:
    """Result of corpus-native graph formula selection.

    Attributes:
        selected: Best graph-health candidate.
        candidates: All scored candidate formulas, sorted by score descending.
    """

    selected: GraphHealthScore
    candidates: tuple[GraphHealthScore, ...]


def calibrate_graph_weights(
    database: Database,
    candidates: list[SearchResult],
    objective: str = "balanced",
    health_config: GraphHealthConfig | None = None,
) -> tuple[GraphWeights, CalibrationProfile]:
    """Calibrate graph weights from one candidate field.

    Args:
        database: Database containing candidate embeddings.
        candidates: Retrieved candidates admitted to graph construction.
        objective: Graph-health objective family.
        health_config: Optional graph-health scoring configuration.

    Returns:
        Calibrated graph weights and the profile used to derive them.
    """
    signals = measure_candidate_signals(database, candidates)
    if not signals.semantic_values:
        profile = profile_from_signals(signals, GraphWeights())
        return GraphWeights(), profile

    if objective == "auto":
        result = select_graph_weights(signals, health_config=health_config)
        return result.selected.weights, result.selected.profile

    weights = derive_graph_weights(signals, objective)
    profile = profile_from_signals(signals, weights)

    return (
        weights,
        profile,
    )


def calibrate_corpus_graph_weights(
    database: Database,
    *,
    sample_limit: int = 500,
    objective: str = "balanced",
    health_config: GraphHealthConfig | None = None,
) -> tuple[GraphWeights, CalibrationProfile]:
    """Calibrate graph weights from corpus-level document structure.

    This function does not inspect queries, gold labels, or retrieval outcomes.
    It samples stored documents from the collection and derives one weight record
    that can be reused for all future queries over that index.

    Args:
        database: Database containing the indexed corpus.
        sample_limit: Maximum number of stored documents to profile.
        objective: Graph-health objective family.
        health_config: Optional graph-health scoring configuration.

    Returns:
        Calibrated graph weights and the corpus profile used to derive them.
    """
    result = database.collection.get(
        limit=sample_limit,
        include=["documents", "metadatas"],
    )
    candidates = [
        SearchResult(
            id=doc_id,
            text=text,
            score=0.0,
            metadata=metadata or {},
        )
        for doc_id, text, metadata in zip(
            result.get("ids", []),
            result.get("documents", []),
            result.get("metadatas", []),
        )
    ]
    return calibrate_graph_weights(
        database,
        candidates,
        objective=objective,
        health_config=health_config,
    )


def calibrate_corpus_graph_formula(
    database: Database,
    *,
    sample_limit: int = 500,
    health_config: GraphHealthConfig | None = None,
) -> AutoCalibrationResult:
    """Select graph weights from corpus structure with no query labels.

    Args:
        database: Database containing the indexed corpus.
        sample_limit: Maximum number of stored documents to profile.
        health_config: Optional graph-health scoring configuration.

    Returns:
        Scored auto-calibration result.
    """
    result = database.collection.get(
        limit=sample_limit,
        include=["documents", "metadatas"],
    )
    candidates = [
        SearchResult(
            id=doc_id,
            text=text,
            score=0.0,
            metadata=metadata or {},
        )
        for doc_id, text, metadata in zip(
            result.get("ids", []),
            result.get("documents", []),
            result.get("metadatas", []),
        )
    ]
    signals = measure_candidate_signals(database, candidates)
    return select_graph_weights(signals, health_config=health_config)


def select_graph_weights(
    signals: CandidateSignals,
    health_config: GraphHealthConfig | None = None,
) -> AutoCalibrationResult:
    """Choose the healthiest graph weights from unsupervised candidates.

    Args:
        signals: Corpus-level pairwise signal measurements.
        health_config: Optional graph-health scoring configuration.

    Returns:
        Auto-calibration result with the selected candidate and full grid.
    """
    scored = tuple(
        sorted(
            (
                score_graph_weights(
                    objective,
                    weights,
                    signals,
                    health_config=health_config,
                )
                for objective, weights in candidate_graph_weights(signals)
            ),
            key=lambda candidate: candidate.score,
            reverse=True,
        )
    )
    if scored:
        return AutoCalibrationResult(selected=scored[0], candidates=scored)

    weights = GraphWeights()
    profile = profile_from_signals(signals, weights)
    fallback = GraphHealthScore(
        objective="balanced",
        score=0.0,
        density_score=0.0,
        connectivity_score=0.0,
        centralization_score=0.0,
        duplicate_score=0.0,
        lexical_score=0.0,
        resonance_score=0.0,
        bridge_score=0.0,
        profile=profile,
        weights=weights,
    )
    return AutoCalibrationResult(selected=fallback, candidates=(fallback,))


def candidate_graph_weights(signals: CandidateSignals) -> list[tuple[str, GraphWeights]]:
    """Generate corpus-native graph-weight candidates.

    Args:
        signals: Corpus-level pairwise signal measurements.

    Returns:
        Named graph-weight candidates.
    """
    candidates = [
        (objective, derive_graph_weights(signals, objective))
        for objective in MANUAL_GRAPH_OBJECTIVES
    ]
    semantic_percentiles = (0.75, 0.85, 0.90, 0.95, 0.98)
    lexical_percentiles = (0.75, 0.85, 0.90, 0.95, 0.98)
    semantic_weights = (0.85, 1.0, 1.15)
    lexical_weights = (0.12, 0.20, 0.32)

    for semantic_pct in semantic_percentiles:
        semantic_threshold = clamp(
            percentile(signals.semantic_values, semantic_pct),
            0.35,
            0.98,
        )
        for lexical_pct in lexical_percentiles:
            lexical_threshold = clamp(
                percentile(signals.lexical_values, lexical_pct),
                0.02,
                0.98,
            )
            for semantic_weight in semantic_weights:
                for lexical_weight in lexical_weights:
                    objective = (
                        "grid_"
                        f"s{int(semantic_pct * 100)}_"
                        f"l{int(lexical_pct * 100)}_"
                        f"sw{semantic_weight:.2f}_"
                        f"lw{lexical_weight:.2f}"
                    )
                    candidates.append(
                        (
                            objective,
                            GraphWeights(
                                semantic_weight=semantic_weight,
                                semantic_threshold=semantic_threshold,
                                lexical_threshold=lexical_threshold,
                                lexical_weight=lexical_weight,
                                cross_reference_weight=0.55,
                                near_duplicate_weight=(
                                    0.02
                                    if signals.duplicate_rate > 0.08
                                    else 0.05
                                ),
                            ),
                        )
                    )
    return candidates


def derive_graph_weights(
    signals: CandidateSignals,
    objective: str = "balanced",
) -> GraphWeights:
    """Derive graph weights from measured corpus structure.

    Args:
        signals: Corpus-level pairwise signal measurements.
        objective: Graph-health objective family.

    Returns:
        Graph weights for the selected objective.
    """
    if objective not in MANUAL_GRAPH_OBJECTIVES:
        raise ValueError(f"unknown graph objective: {objective}")

    semantic_p75 = percentile(signals.semantic_values, 0.75)
    lexical_p75 = percentile(signals.lexical_values, 0.75)
    lexical_p90 = percentile(signals.lexical_values, 0.90)
    cross_reference_rate = (
        len(signals.cross_reference_pairs) / len(signals.semantic_values)
        if signals.semantic_values
        else 0.0
    )

    semantic_weight = 1.0
    semantic_threshold = clamp(semantic_p75, 0.42, 0.62)
    lexical_threshold = clamp(lexical_p75, 0.06, 0.16)
    lexical_weight = 0.16 if lexical_p90 < 0.18 else 0.24
    cross_reference_weight = 0.45
    if cross_reference_rate > 0.02:
        cross_reference_weight = 0.65
    elif cross_reference_rate > 0.0:
        cross_reference_weight = 0.55
    near_duplicate_weight = 0.03 if signals.duplicate_rate > 0.08 else 0.05

    provisional = GraphWeights(
        semantic_weight=semantic_weight,
        semantic_threshold=semantic_threshold,
        lexical_threshold=lexical_threshold,
        lexical_weight=lexical_weight,
        cross_reference_weight=cross_reference_weight,
        near_duplicate_weight=near_duplicate_weight,
    )
    health = graph_health(signals, provisional)
    density = health.density
    degree_skew = health.degree_skew

    if density < 0.08:
        semantic_threshold = clamp(semantic_threshold - 0.04, 0.38, 0.62)
        lexical_threshold = clamp(lexical_threshold - 0.02, 0.04, 0.16)
    elif density > 0.32:
        semantic_threshold = clamp(semantic_threshold + 0.04, 0.42, 0.68)
        lexical_threshold = clamp(lexical_threshold + 0.02, 0.06, 0.22)
        lexical_weight *= 0.75

    if degree_skew > 4.0:
        lexical_weight *= 0.70

    if objective == "sparse":
        semantic_threshold = clamp(semantic_threshold + 0.06, 0.44, 0.72)
        lexical_threshold = clamp(lexical_threshold + 0.04, 0.08, 0.26)
        lexical_weight *= 0.75
    elif objective == "dense":
        semantic_threshold = clamp(semantic_threshold - 0.06, 0.34, 0.62)
        lexical_threshold = clamp(lexical_threshold - 0.03, 0.03, 0.16)
    elif objective == "semantic_heavy":
        semantic_weight = 1.15
        semantic_threshold = clamp(semantic_threshold - 0.02, 0.38, 0.62)
        lexical_weight *= 0.65
        cross_reference_weight *= 0.90
    elif objective == "lexical_salience_heavy":
        lexical_threshold = clamp(lexical_threshold - 0.03, 0.03, 0.16)
        lexical_weight *= 1.45
        semantic_weight = 0.90
    elif objective == "reference_forward":
        cross_reference_weight = max(cross_reference_weight, 0.75)
        lexical_threshold = clamp(lexical_threshold - 0.02, 0.03, 0.16)
        lexical_weight *= 1.15
    elif objective == "anti_hub":
        lexical_threshold = clamp(lexical_threshold + 0.05, 0.08, 0.28)
        lexical_weight *= 0.55
        semantic_threshold = clamp(semantic_threshold + 0.02, 0.42, 0.70)
    elif objective == "duplicate_conservative":
        near_duplicate_weight = 0.01
        lexical_weight *= 0.90

    return GraphWeights(
        semantic_weight=semantic_weight,
        semantic_threshold=semantic_threshold,
        lexical_threshold=lexical_threshold,
        lexical_weight=lexical_weight,
        cross_reference_weight=cross_reference_weight,
        near_duplicate_weight=near_duplicate_weight,
    )


def score_graph_weights(
    objective: str,
    weights: GraphWeights,
    signals: CandidateSignals,
    health_config: GraphHealthConfig | None = None,
) -> GraphHealthScore:
    """Score one graph-weight candidate from corpus structure.

    Args:
        objective: Candidate objective name.
        weights: Candidate graph weights.
        signals: Corpus-level pairwise signal measurements.
        health_config: Optional graph-health scoring configuration.

    Returns:
        Candidate health score.
    """
    config = health_config or GraphHealthConfig()
    profile = profile_from_signals(signals, weights)
    density_score = triangular_score(
        profile.graph_density,
        target=config.density_target,
        left_width=config.density_left_width,
        right_width=config.density_right_width,
    )
    connectivity_score = triangular_score(
        profile.largest_component_ratio,
        target=config.lcc_target,
        left_width=config.lcc_left_width,
        right_width=config.lcc_right_width,
    )
    centralization_score = 1.0 - ramp_score(
        profile.degree_centralization,
        start=config.centralization_start,
        stop=config.centralization_stop,
    )
    duplicate_score = 1.0 - ramp_score(
        profile.duplicate_rate,
        start=config.duplicate_start,
        stop=config.duplicate_stop,
    )
    lexical_score = lexical_health_score(profile, weights)
    resonance_score = agreement_density_score(signals, weights, health_config=config)
    bridge_score = (
        bridge_risk_score(signals, weights, health_config=config) * resonance_score
    )
    score = (
        config.density_weight * density_score
        + config.connectivity_weight * connectivity_score
        + config.centralization_weight * centralization_score
        + config.duplicate_weight * duplicate_score
        + config.lexical_weight * lexical_score
        + config.resonance_weight * resonance_score
        + config.bridge_weight * bridge_score
    )
    return GraphHealthScore(
        objective=objective,
        score=float(clamp(score, 0.0, 1.0)),
        density_score=float(clamp(density_score, 0.0, 1.0)),
        connectivity_score=float(clamp(connectivity_score, 0.0, 1.0)),
        centralization_score=float(clamp(centralization_score, 0.0, 1.0)),
        duplicate_score=float(clamp(duplicate_score, 0.0, 1.0)),
        lexical_score=float(clamp(lexical_score, 0.0, 1.0)),
        resonance_score=float(clamp(resonance_score, 0.0, 1.0)),
        bridge_score=float(clamp(bridge_score, 0.0, 1.0)),
        profile=profile,
        weights=weights,
    )


def agreement_density_score(
    signals: CandidateSignals,
    weights: GraphWeights,
    health_config: GraphHealthConfig | None = None,
) -> float:
    """Score whether thresholds retain enough agreement edges for diffusion.

    Args:
        signals: Corpus-level pairwise signal measurements.
        weights: Candidate graph weights.
        health_config: Optional graph-health scoring configuration.

    Returns:
        Resonance health score in the `[0, 1]` interval.
    """
    if not signals.semantic_values:
        return 0.0
    config = health_config or GraphHealthConfig()
    agreement_edges = 0
    for semantic, lexical in zip(signals.semantic_values, signals.lexical_values):
        if (
            semantic >= weights.semantic_threshold
            and semantic < weights.near_duplicate_threshold
            and lexical >= weights.lexical_threshold
        ):
            agreement_edges += 1
    density = agreement_edges / len(signals.semantic_values)
    return triangular_score(
        density,
        target=config.agreement_target,
        left_width=config.agreement_left_width,
        right_width=config.agreement_right_width,
    )


def bridge_risk_score(
    signals: CandidateSignals,
    weights: GraphWeights,
    health_config: GraphHealthConfig | None = None,
) -> float:
    """Score how much the formula avoids semantic-only bridge edges.

    Args:
        signals: Corpus-level pairwise signal measurements.
        weights: Candidate graph weights.
        health_config: Optional graph-health scoring configuration.

    Returns:
        Bridge safety score in the `[0, 1]` interval.
    """
    semantic_edges = 0
    semantic_only_edges = 0
    for semantic, lexical in zip(signals.semantic_values, signals.lexical_values):
        if semantic < weights.semantic_threshold:
            continue
        if semantic >= weights.near_duplicate_threshold:
            continue
        semantic_edges += 1
        if lexical < weights.lexical_threshold:
            semantic_only_edges += 1
    if semantic_edges == 0:
        return 0.0
    config = health_config or GraphHealthConfig()
    bridge_rate = semantic_only_edges / semantic_edges
    return 1.0 - ramp_score(
        bridge_rate,
        start=config.bridge_start,
        stop=config.bridge_stop,
    )


def lexical_health_score(
    profile: CalibrationProfile,
    weights: GraphWeights,
) -> float:
    """Score whether lexical settings match observed corpus salience.

    Args:
        profile: Corpus profile under candidate weights.
        weights: Candidate graph weights.

    Returns:
        Lexical health score in the `[0, 1]` interval.
    """
    if profile.lexical_p90 <= 0:
        return 1.0 if weights.lexical_weight <= 0.20 else 0.5
    if weights.lexical_threshold > profile.lexical_p90:
        return 0.25
    if weights.lexical_threshold < max(0.01, profile.lexical_p75 * 0.40):
        return 0.45
    return 1.0


def profile_candidate_field(
    database: Database,
    candidates: list[SearchResult],
) -> CalibrationProfile:
    """Measure pairwise candidate-field structure.

    Args:
        database: Database containing candidate embeddings.
        candidates: Retrieved candidates admitted to graph construction.

    Returns:
        Calibration profile derived from pairwise candidate signals.
    """
    return profile_from_signals(
        measure_candidate_signals(database, candidates),
        GraphWeights(),
    )


def measure_candidate_signals(
    database: Database,
    candidates: list[SearchResult],
) -> CandidateSignals:
    """Measure raw pairwise candidate-field signals.

    Args:
        database: Database containing candidate embeddings.
        candidates: Retrieved candidates admitted to graph construction.

    Returns:
        Candidate signal measurements.
    """
    ids = [candidate.id for candidate in candidates]
    if len(ids) < 2:
        return CandidateSignals([], [], [], set(), 0.0)

    result = database.collection.get(ids=ids, include=["embeddings"])
    embeddings_list = result.get("embeddings")
    if embeddings_list is None or len(embeddings_list) == 0:
        return CandidateSignals([], [], [], set(), 0.0)

    embeddings = dict(zip(result["ids"], embeddings_list))
    by_id = {candidate.id: candidate for candidate in candidates}
    salience_maps = candidate_salience_maps(candidates)
    labels = {
        candidate.id: title_like_label(candidate)
        for candidate in candidates
    }
    semantic_values: list[float] = []
    lexical_values: list[float] = []
    cross_reference_pairs: set[tuple[str, str]] = set()
    duplicates = 0

    for left_index, left_id in enumerate(ids):
        for right_id in ids[left_index + 1:]:
            semantic = float(cosine_similarity(embeddings[left_id], embeddings[right_id]))
            semantic_values.append(semantic)
            lexical_values.append(
                salience_overlap(salience_maps[left_id], salience_maps[right_id])
            )
            if cross_reference(by_id[left_id].text, labels[right_id]) or cross_reference(
                by_id[right_id].text,
                labels[left_id],
            ):
                cross_reference_pairs.add((left_id, right_id))
            if semantic >= GraphWeights().near_duplicate_threshold:
                duplicates += 1

    pair_count = len(semantic_values)
    return CandidateSignals(
        ids=ids,
        semantic_values=semantic_values,
        lexical_values=lexical_values,
        cross_reference_pairs=cross_reference_pairs,
        duplicate_rate=duplicates / pair_count if pair_count else 0.0,
    )


def profile_from_signals(
    signals: CandidateSignals,
    weights: GraphWeights,
) -> CalibrationProfile:
    """Build a calibration profile from measured signals and graph weights.

    Args:
        signals: Raw pairwise candidate signals.
        weights: Graph weights to estimate graph health.

    Returns:
        Calibration profile.
    """
    pair_count = len(signals.semantic_values)
    health = graph_health(signals, weights)
    return CalibrationProfile(
        semantic_p75=percentile(signals.semantic_values, 0.75),
        semantic_p90=percentile(signals.semantic_values, 0.90),
        lexical_p75=percentile(signals.lexical_values, 0.75),
        lexical_p90=percentile(signals.lexical_values, 0.90),
        cross_reference_rate=(
            len(signals.cross_reference_pairs) / pair_count
            if pair_count
            else 0.0
        ),
        graph_density=health.density,
        largest_component_ratio=health.largest_component_ratio,
        degree_centralization=health.degree_centralization,
        degree_skew=health.degree_skew,
        duplicate_rate=signals.duplicate_rate,
        pair_count=pair_count,
    )


@dataclass(frozen=True)
class GraphStructure:
    """Standard graph-structure measurements for one weight setting.

    Attributes:
        density: Edge density, `|E| / (n(n-1)/2)`.
        largest_component_ratio: Fraction of nodes in the largest connected
            component.
        degree_centralization: Freeman degree centralization for the graph.
        degree_skew: Max degree divided by mean degree.
    """

    density: float
    largest_component_ratio: float
    degree_centralization: float
    degree_skew: float


def graph_health(signals: CandidateSignals, weights: GraphWeights) -> GraphStructure:
    """Estimate standard graph structure under a weight setting.

    Args:
        signals: Raw pairwise candidate signals.
        weights: Graph weights to evaluate.

    Returns:
        Graph density, component, and degree-concentration measurements.
    """
    if not signals.ids or not signals.semantic_values:
        return GraphStructure(0.0, 0.0, 0.0, 0.0)

    degrees = {doc_id: 0 for doc_id in signals.ids}
    adjacency = {doc_id: set() for doc_id in signals.ids}
    edge_count = 0
    pair_index = 0
    for left_index, left_id in enumerate(signals.ids):
        for right_id in signals.ids[left_index + 1:]:
            semantic = signals.semantic_values[pair_index]
            lexical = signals.lexical_values[pair_index]
            has_edge = (
                semantic >= weights.semantic_threshold
                or lexical >= weights.lexical_threshold
                or (left_id, right_id) in signals.cross_reference_pairs
            )
            if has_edge:
                edge_count += 1
                degrees[left_id] += 1
                degrees[right_id] += 1
                adjacency[left_id].add(right_id)
                adjacency[right_id].add(left_id)
            pair_index += 1

    pair_count = len(signals.semantic_values)
    density = edge_count / pair_count if pair_count else 0.0
    mean_degree = sum(degrees.values()) / len(degrees) if degrees else 0.0
    degree_skew = max(degrees.values()) / mean_degree if mean_degree else 0.0
    return GraphStructure(
        density=float(density),
        largest_component_ratio=largest_component_ratio(adjacency),
        degree_centralization=degree_centralization(degrees),
        degree_skew=float(degree_skew),
    )


def largest_component_ratio(adjacency: dict[str, set[str]]) -> float:
    """Return the fraction of nodes in the largest connected component.

    Args:
        adjacency: Unweighted graph adjacency sets.

    Returns:
        Largest connected component size divided by node count.
    """
    if not adjacency:
        return 0.0
    seen: set[str] = set()
    largest = 0
    for start in adjacency:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        size = 0
        while stack:
            node = stack.pop()
            size += 1
            for neighbor in adjacency[node]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        largest = max(largest, size)
    return largest / len(adjacency)


def degree_centralization(degrees: dict[str, int]) -> float:
    """Compute Freeman degree centralization for an undirected graph.

    Freeman degree centralization is zero when degrees are uniform and one for a
    star graph. It is a standard hub-concentration measure.

    Args:
        degrees: Unweighted degree by node id.

    Returns:
        Degree centralization in the `[0, 1]` interval.
    """
    node_count = len(degrees)
    if node_count < 3:
        return 0.0
    max_degree = max(degrees.values(), default=0)
    numerator = sum(max_degree - degree for degree in degrees.values())
    denominator = (node_count - 1) * (node_count - 2)
    if denominator == 0:
        return 0.0
    return float(numerator / denominator)


def percentile(values: list[float], pct: float) -> float:
    """Return a percentile from numeric values.

    Args:
        values: Numeric values.
        pct: Percentile as a fraction in the `[0, 1]` interval.

    Returns:
        Requested percentile, or `0.0` when the input is empty.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * pct))
    return float(ordered[index])


def triangular_score(
    value: float,
    *,
    target: float,
    left_width: float,
    right_width: float,
) -> float:
    """Score a value by distance from an asymmetric target.

    Args:
        value: Value to score.
        target: Ideal value.
        left_width: Distance below target that reaches zero score.
        right_width: Distance above target that reaches zero score.

    Returns:
        Score in the `[0, 1]` interval.
    """
    if value <= target:
        return clamp(1.0 - ((target - value) / left_width), 0.0, 1.0)
    return clamp(1.0 - ((value - target) / right_width), 0.0, 1.0)


def ramp_score(value: float, *, start: float, stop: float) -> float:
    """Score how far a value has moved through a penalty ramp.

    Args:
        value: Value to score.
        start: Value where penalty begins.
        stop: Value where penalty reaches one.

    Returns:
        Penalty score in the `[0, 1]` interval.
    """
    if value <= start:
        return 0.0
    if value >= stop:
        return 1.0
    return (value - start) / (stop - start)


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a value to a closed interval.

    Args:
        value: Value to clamp.
        minimum: Lower bound.
        maximum: Upper bound.

    Returns:
        Clamped value.
    """
    return max(minimum, min(maximum, value))
