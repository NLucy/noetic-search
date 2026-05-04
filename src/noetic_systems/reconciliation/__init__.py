"""Post-retrieval evidence resolution for Noetic Search.

This package turns a broad hybrid-retrieval candidate set into a smaller,
coherent evidence region. It builds a query-conditioned graph, diffuses initial
retrieval confidence across that graph, partitions the graph into basins, scores
those basins, and exposes either compact chunks or an inspection payload.

The package is intentionally organized by methodology. Graph construction
defines the local structure, diffusion measures how retrieval confidence settles
inside that structure, spectral partitioning finds coherent regions, basin
scoring chooses the strongest region, and result formatting presents the outcome
to an LLM or caller. This keeps the search idea inspectable: every stage has a
specific mathematical role and a concrete artifact that can be tested.

Import concrete modules directly, for example
`noetic_systems.reconciliation.engine.Reconciler` or
`noetic_systems.reconciliation.diffusion.diffuse`. The package initializer does
not re-export implementation symbols because the module names are part of the
teaching surface.
"""
