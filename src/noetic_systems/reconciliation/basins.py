"""Basin scoring for coherent evidence regions.

Basins are the candidate graph regions that Noetic Search treats as coherent
evidence positions. This module converts community assignments into scored
basins by combining diffused energy, internal graph cohesion, support count, and
duplicate penalties. We use basin scoring because the question is not only which
chunk is individually similar to the query, but which region of retrieved chunks
carries the strongest supported idea.

A basin is not assumed to be correct just because it has many nodes or high
energy. Repeated near-duplicates can look strong while adding little evidence.
The scoring terms make those tradeoffs explicit: energy says where the field
settled, cohesion says whether the region hangs together, support says whether
the basin contains enough material to represent a concept, and the duplicate
penalty reduces regions that are mostly repeated text.

Representative chunk selection is intentionally handled in
`noetic_systems.reconciliation.ranking`. This module decides how strong each
region is. Ranking decides which members of the winning region should be
returned.
"""

from __future__ import annotations

from collections import defaultdict

from noetic_systems.reconciliation.metrics import (
    calculate_cohesion,
    duplicate_penalty as calculate_duplicate_penalty,
)
from noetic_systems.reconciliation.models import Basin, ReturnRanker
from noetic_systems.reconciliation.ranking import rank_basin_documents
from noetic_systems.search.semantic import SearchResult


def build_basins(
    communities: dict[str, int],
    energy: dict[str, float],
    specificity: dict[str, float],
    query_score: dict[str, float],
    support: dict[str, float],
    echo: dict[str, float],
    return_ranker: ReturnRanker,
    graph: dict[str, dict[str, float]],
    doc_index: dict[str, SearchResult],
) -> list[Basin]:
    """Build scored basins from community assignments.

    Args:
        communities: Community assignment by document id.
        energy: Diffused energy by document id.
        specificity: Specificity score by document id.
        query_score: Hybrid query score by document id.
        support: Graph support by document id.
        echo: Query-echo score by document id.
        return_ranker: Strategy for ranking documents inside each basin.
        graph: Weighted adjacency mapping.
        doc_index: Candidate lookup by document id.

    Returns:
        Scored basins with internally ranked documents.
    """
    grouped: dict[int, list[tuple[str, float]]] = defaultdict(list)
    for doc_id, comm_id in communities.items():
        grouped[comm_id].append((doc_id, energy.get(doc_id, 0.0)))

    basins = []
    for comm_id, docs in grouped.items():
        energy_by_doc = dict(docs)
        # Rank representatives before storing the basin so result surfaces can
        # return the strongest region directly without recomputing chunk order.
        doc_ids = rank_basin_documents(
            list(energy_by_doc),
            energy_by_doc,
            specificity,
            query_score,
            support,
            echo,
            return_ranker,
        )
        cohesion = calculate_cohesion(doc_ids, graph)
        duplicate_penalty = calculate_duplicate_penalty(doc_ids, graph)
        basin_energy = float(sum(energy_by_doc.values()))
        support_score = min(1.0, len(doc_ids) / 6.0)
        # The field score uses settled graph signal, basin support, cohesion, and
        # duplicate pressure. It avoids source-level assumptions.
        score = (
            0.45 * basin_energy
            + 0.25 * support_score
            + 0.20 * cohesion
            - duplicate_penalty
        )

        basins.append(
            Basin(
                id=comm_id,
                label=f"basin-{comm_id}",
                score=float(max(0.0, min(1.0, score))),
                energy=basin_energy,
                documents=tuple(doc_ids),
                cohesion=float(cohesion),
                support=len(doc_ids),
                duplicate_penalty=float(duplicate_penalty),
            )
        )
    return basins
