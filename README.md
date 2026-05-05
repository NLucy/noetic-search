# Noetic Search

Noetic Search is a post-retrieval reconciliation layer for hybrid search.

The system assumes a conventional first-stage retriever has already produced a
candidate set. It then builds a local weighted graph over those candidates,
detects fixed spectral basin boundaries, diffuses seeded retrieval energy over
the graph, scores the fixed basins, and returns representative chunks from the
strongest basin.

It is not a replacement for vector search, BM25, reranking, or LLM reasoning. It
operates between candidate retrieval and prompt construction.

## Algorithm

```text
query
  -> hybrid candidates
  -> candidate graph
  -> spectral basin boundaries
  -> seed retrieval energy
  -> diffuse energy over fixed graph
  -> score fixed basins
  -> rank winning-basin chunks
  -> chunks or inspection field
```

The spectral step proposes basin boundaries using the graph Laplacian and
Fiedler vector. Diffusion does not create or modify those boundaries; it updates
seeded energy on graph nodes. Basin scoring then selects among the already
detected basins.

## Documentation

Build and serve the documentation locally:

```bash
uv run mkdocs serve
```

Then open:

```text
http://127.0.0.1:8000/
```

The documentation has two entry points:

- `Overview`: high-level system description and return surfaces.
- `The Math`: step-by-step treatment of candidates, graph construction,
  spectral detection, diffusion, basin scoring, uncertainty, ranking,
  and result formatting.

## Tests

Run the unit and integration test suite:

```bash
uv run python -m unittest discover -s tests
```

Run the documentation build in strict mode:

```bash
uv run mkdocs build --strict
```

Check for whitespace errors before committing:

```bash
git diff --check
```

## Demo

Run the local retrieval/reconciliation demo:

```bash
uv run noetic demo
```

## Benchmark

Generate the hard benchmark:

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

The benchmark mixes ten decision domains with plausible decoys, stale notes,
duplicated evidence, unrelated distractor documents, and distributed target
evidence. Blind mode strips benchmark-only labels before indexing.

## LLM Harness

The LLM layer builds Responses API input items.

```bash
uv run noetic llm-demo --mode basin
uv run noetic llm-demo --mode top-k
uv run noetic llm-demo --mode evidence-field
```

To make a live OpenAI call:

```bash
uv run --extra llm noetic llm-demo --mode basin --call-api
```

## Return Surfaces

- `result.chunks(database)` returns LLM-ready chunks from the winning basin.
- `result.strongest_basin(database)` returns the winning basin, chunks,
  uncertainty, and graph metrics.
- `result.evidence_field()` returns the inspection field: winning basin,
  competing basins, support edges, uncertainty, and graph metrics.

## Implementation Notes

The current implementation uses:

- ChromaDB for storage and embeddings.
- BM25 plus vector retrieval for hybrid candidates.
- Embedding and near-duplicate signals for graph weights.
- Normalized graph Laplacian eigendecomposition for spectral basin detection.
- Fixed-step diffusion for graph energy propagation.
- Specificity-first chunk ordering inside the winning basin.
