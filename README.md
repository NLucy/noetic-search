# Noetic Search

Noetic Search is a post-retrieval reconciliation layer for hybrid search.

Hybrid search retrieves plausible candidates. Noetic reconciliation builds a local
graph over those candidates, finds the strongest evidence basin, and returns either
that basin's chunks or an inspection record of the full field.

It does not replace vector databases, BM25, rerankers, or LLMs. It changes the step
after candidate retrieval.

## Core Path

```text
query
  -> hybrid candidates
  -> candidate graph
  -> diffusion
  -> spectral basins
  -> strongest basin
  -> chunks or inspection field
```

The default product surface is simple: return the strongest basin's chunks, ordered
for useful evidence rather than individual retrieval rank.

## Why

Top-k treats candidates as independent items. That fails when the nearest chunks are
plausible, repetitive, stale, or shallow.

Noetic reconciliation asks a different question: which candidate region has the best
combined support after the retrieved field is connected and scored?

## Run

```bash
uv run noetic demo
uv run python -m unittest discover -s tests
```

## LLM Inputs

The LLM layer builds Responses API input items, not Chat Completions messages.

```bash
uv run noetic llm-demo --mode basin
uv run noetic llm-demo --mode top-k
uv run noetic llm-demo --mode evidence-field
```

To make a live OpenAI call:

```bash
uv run --extra llm noetic llm-demo --mode basin --call-api
```

## Hard Benchmark

Generate the benchmark:

```bash
uv run python tests/data/generate_hard_rag_benchmark.py
```

Evaluate blind retrieval and reconciliation:

```bash
uv run python evaluate_hard_benchmark.py --blind
```

Current default result on the 1,340-document hard benchmark:

```text
standard hybrid top-5 majority accuracy: 0/10
noetic top-5 from hybrid top-50 accuracy: 8/10
noetic top-5 uplift over standard top-5: +8 cases
candidate target-present rate: 10/10
target-heavy basin ranked first: 10/10
```

The benchmark mixes ten decision domains with decoys, stale notes, duplicated
approvals, unrelated distractor documents, and distributed target evidence. Blind mode strips
benchmark-only labels before indexing.

## Return Surfaces

- `result.strongest_basin(database)` returns the strongest basin, chunks, uncertainty, and graph metrics.
- `result.chunks(database)` returns only LLM-ready chunks from the strongest basin.
- `result.evidence_field()` returns the inspection field: winning basin, competing basins, support edges, uncertainty, and metrics.

## Implementation

The current implementation uses:

- ChromaDB for storage and embeddings
- BM25 plus vector retrieval for hybrid candidates
- embedding, metadata, and near-duplicate signal contributions for graph weights
- normalized-Laplacian eigendecomposition for spectral basin detection
- fixed-step diffusion for graph energy propagation
- specificity-first chunk ordering inside the winning basin
