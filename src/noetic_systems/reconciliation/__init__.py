"""Post-retrieval evidence resolution for Noetic Search.

This package turns a broad hybrid-retrieval candidate set into a smaller,
coherent evidence region. It builds a query-conditioned graph, uses spectral
partitioning to detect basins, diffuses initial retrieval confidence across the
graph, scores those basins, and exposes either compact chunks or an inspection
payload.

The package is intentionally organized by methodology. Graph construction
defines the local structure, spectral partitioning finds coherent regions,
diffusion initializes retrieval energy and measures how it settles inside those
regions, basin scoring chooses the strongest region and reports structural risk,
ranking selects representative chunks from the winner, and result formatting
presents the outcome to an LLM or caller. This keeps the search idea
inspectable: every stage has a specific mathematical role and a concrete
artifact that can be tested.

Import concrete modules directly, for example
`noetic_systems.reconciliation.engine.Reconciler` or
`noetic_systems.reconciliation.diffusion.diffuse`. The package initializer does
not re-export implementation symbols because the module names are part of the
teaching surface.
"""
