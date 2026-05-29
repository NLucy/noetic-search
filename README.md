# Noetic Search

Noetic Search is a post-retrieval reconciliation layer for hybrid search.

It keeps hybrid retrieval as the broad candidate selector, then reranks the
candidate set with a query-local evidence graph:

```text
query
  -> hybrid candidates
  -> evidence graph
  -> anchor-linked ranking
  -> compact chunks for an LLM
```

The goal is narrow and practical: return a smaller, better-supported context
set than `top_k` hybrid alone.

## Quickstart

```bash
git clone git@github.com:NLucy/noetic-search.git
cd noetic-search
uv run noetic demo
```

Run the test and documentation checks:

```bash
uv run python -m unittest discover -s tests
uv run mkdocs build --strict
```

Serve the docs:

```bash
uv run noetic trace
uv run mkdocs serve
```

Open `http://127.0.0.1:8000/`.

## Production Method

Hybrid retrieval first scores a fixed internal pool, usually 100 semantic and
100 lexical candidates. Noetic admits the top 30 fused hybrid results into a
query-local graph, protects the strongest 3 hybrid results as anchors, and
promotes chunks that are strongly connected to those anchors.

Edges use ordinary retrieval signals:

- embedding similarity;
- lexical salience overlap;
- explicit text-to-title cross-reference;
- near-duplicate pressure.

The production ranker gives each non-anchor candidate a final chunk score:

```text
final_chunk_score =
  0.50 * query_score
+ 0.35 * anchor_affinity
+ 0.15 * graph_support
```

`query_score` is the chunk's original hybrid score against the query.
`anchor_affinity` is the chunk's strongest graph edge to a preserved hybrid
anchor. `graph_support` is the chunk's normalized weighted degree inside the
local candidate graph. Anchors are preserved first; the highest-scoring
remaining chunks fill the compact return.

## Result

![Hybrid versus Noetic protected-anchor support recall](docs/assets/benchmark_summary.svg)

On the benchmark summary, Noetic with 3 protected anchors improved mean recall
from `0.733` to `0.764` across `@5/@10`: a 3.0 percentage-point absolute gain,
or a 4.1% relative improvement over hybrid.

The detailed ablation study is documented in the MkDocs site.

## Auto Calibration

`auto` is a corpus-level setup step, not a per-query tuning loop.

```text
index corpus
  -> sample chunks
  -> measure pairwise semantic and lexical structure
  -> score candidate GraphWeights
  -> freeze one GraphWeights record
  -> apply those weights when making query-local graphs
```

So the selected weights are added directly when graph edges are built. The
calibration step exists because different corpora have different lexical and
semantic density. Static defaults are available; `auto` derives a corpus-specific
weight profile before normal retrieval begins.

## Benchmarks

External retrieval benchmarks:

- HotpotQA;
- 2WikiMultiHopQA;
- MuSiQue.

Internal research fixture:

- clinical evidence retrieval.

The clinical benchmark is synthetic and retrieval-only. It does not diagnose,
recommend treatment, or evaluate generated medical answers.

Key scripts:

```bash
uv run --extra eval python scripts/evaluate_multihop_objectives.py
uv run --extra eval python scripts/evaluate_linked_ablation.py
uv run python scripts/evaluate_clinical_benchmark.py --blind --ks 5,10
```

Reports are written under `reports/`, which is gitignored.

## Documentation

The MkDocs site is the main learning surface:

- Overview
- Candidate Selection
- Graph Creation
- Auto Calibration
- Final Selection
- Spectral Diffusion
- Production Trace
- Diagnostic Trace

Run it with:

```bash
uv run mkdocs serve
```

## Notes

- ChromaDB stores documents and embeddings.
- Production linked retrieval does not run spectral partitioning or diffusion.
- Spectral partitioning and diffusion remain available for diagnostics and trace
  visualization.
- Compare latency against `hybrid@candidate_limit`, not `hybrid@final_k`.

## Clinical Direction

The long-term target domain is healthcare evidence retrieval: finding compact,
well-supported context for high-stakes review workflows where missing a key
chunk or surfacing a misleading decoy can matter.

The included clinical evidence dataset is synthetic by design. It models
medication-safety evidence chains with critical support chunks, plausible
decoys, background notes, and unrelated noise. Its purpose is to stress-test
retrieval behavior before any real clinical corpus is involved.

This repository is not a diagnostic system. The current claim is narrower:
Noetic Search studies whether graph-based reconciliation can improve the
evidence set handed to downstream reviewers or LLMs.
