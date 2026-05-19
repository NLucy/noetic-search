"""Post-retrieval evidence resolution for Noetic Search.

This package turns a broad hybrid-retrieval candidate set into a smaller,
graph-linked evidence set. The benchmarked production path builds a
query-conditioned graph, preserves strong hybrid anchors, promotes connected
support chunks, and exposes compact linked chunks. Spectral partitioning,
diffusion, and basin scoring remain available as explicit diagnostics and
research tools.

The package is intentionally organized by methodology. Graph construction
defines the local structure, ranking preserves strong hybrid anchors while
promoting graph-linked support, and result formatting presents the outcome to an
LLM or caller. The research modules add spectral partitioning, diffusion, basin
scoring, and structural uncertainty when inspection is requested. This keeps the
search idea inspectable: every stage has a specific mathematical role and a
concrete artifact that can be tested.

Import concrete modules directly, for example
`noetic_systems.reconciliation.engine.Reconciler` or
`noetic_systems.reconciliation.ranking.rank_linked_evidence`. The package
initializer does not re-export implementation symbols because the module names
are part of the teaching surface.
"""
