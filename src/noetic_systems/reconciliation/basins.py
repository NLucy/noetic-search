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

Representative chunk selection is intentionally handled later in
`noetic_systems.reconciliation.ranking`, after the winning basin is known. This
module decides only how strong each region is.
"""

from __future__ import annotations

from collections import defaultdict

from noetic_systems.reconciliation.metrics import (
    calculate_cohesion,
    duplicate_penalty as calculate_duplicate_penalty,
)
from noetic_systems.reconciliation.models import Basin


def build_basins(
    communities: dict[str, int],
    energy: dict[str, float],
    graph: dict[str, dict[str, float]],
) -> list[Basin]:
    """Build scored basins from community assignments.

    Args:
        communities: Community assignment by document id.
        energy: Diffused energy by document id.
        graph: Weighted adjacency mapping.

    Returns:
        Scored basins with unranked member documents.
    """
    grouped: dict[int, list[tuple[str, float]]] = defaultdict(list)
    for doc_id, comm_id in communities.items():
        grouped[comm_id].append((doc_id, energy.get(doc_id, 0.0)))

    basins = []
    for comm_id, docs in grouped.items():
        energy_by_doc = dict(docs)
        doc_ids = list(energy_by_doc)
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
