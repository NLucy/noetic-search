"""Data contracts for Noetic reconciliation.

The reconciliation pipeline passes a small set of typed records between
functional stages. These dataclasses describe evidence edges and scored basins
without owning behavior. We use explicit contracts so graph construction,
spectral partitioning, diffusion, basin scoring, and result formatting stay
decoupled and readable.

The two central records are `EvidenceEdge` and `Basin`. An edge records why two
candidates were connected and with what weight. A basin records a candidate
region selected from the graph: its score, energy, member documents, cohesion,
support, and duplicate penalty. The winning basin is later copied with its
documents ordered for return. These records are small enough to inspect directly
in tests and rich enough to explain why a result was returned.

The literal type defines the supported representative-chunk ranking strategies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReturnRanker = Literal["specificity", "purifier"]


@dataclass(frozen=True)
class EvidenceEdge:
    """Relationship between two candidate documents.

    Attributes:
        source: Source document id.
        target: Target document id.
        type: Edge category, such as embedding, metadata, or duplicate signal.
        weight: Non-negative edge weight.
        reason: Human-readable explanation for inspection output.
    """

    source: str
    target: str
    type: str
    weight: float
    reason: str


@dataclass(frozen=True)
class Basin:
    """Candidate region where evidence settles after diffusion.

    Attributes:
        id: Numeric basin identifier.
        label: Stable display label.
        score: Final basin score after energy, support, and penalties.
        energy: Total diffused energy inside the basin.
        documents: Document ids assigned to the basin. Only the winning basin is
            finally ordered for return.
        cohesion: Mean internal edge strength.
        support: Number of basin documents.
        duplicate_penalty: Penalty for near-duplicate internal support.
    """

    id: int
    label: str
    score: float
    energy: float
    documents: tuple[str, ...]
    cohesion: float
    support: int
    duplicate_penalty: float
