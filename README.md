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

Hybrid retrieval first returns a broad candidate set, usually top 50. Noetic
keeps the strongest hybrid results as anchors, builds a graph over the admitted
candidates, and promotes chunks that are strongly connected to those anchors.

Edges use ordinary retrieval signals:

- embedding similarity;
- lexical salience overlap;
- explicit text-to-title cross-reference;
- near-duplicate pressure.

The linked ranker scores non-anchor candidates as:

```text
linked_score =
  0.50 * query_score
+ 0.35 * anchor_affinity
+ 0.15 * graph_support
```

`query_score` is the original hybrid score. `anchor_affinity` is the strongest
graph edge to a preserved hybrid anchor. `graph_support` is normalized weighted
degree inside the local candidate graph.

Focused ablations show the main signal:

![Hybrid versus Noetic auto support recall](docs/assets/benchmark_summary.svg)

```text
variant                 mean recall across @5/@10
hybrid                  0.738
linked_static           0.777
linked_auto             0.783
anchors_only            0.738
no_anchor_affinity      0.756
anchor_affinity_only    0.780
support_only            0.501
semantic_only           0.743
lexical_only            0.742
```

Anchors alone reproduce hybrid. Generic graph support alone performs poorly.
The lift comes from anchor-linked promotion.

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
- The Math
- Evidence Graph
- Auto Calibration
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
