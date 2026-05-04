# Testing Results

The benchmark tests decision-grade retrieval under adversarial evidence.

It mixes plausible decoys, stale approvals, duplicated notes, distributed target
evidence, and unrelated cross-domain rubbish. Blind mode strips benchmark-only labels
before indexing.

## Standard Run

```bash
uv run python tests/data/generate_hard_rag_benchmark.py
uv run python evaluate_hard_benchmark.py --blind
```

## Current Result

```text
documents: 1340
cases: 10
standard hybrid top-5 majority accuracy: 0/10
standard hybrid top-1 decoy rate: 10/10
strongest-basin majority accuracy: 1/10
noetic top-5 from hybrid top-50 accuracy: 8/10
noetic top-5 uplift over standard top-5: +8 cases
candidate target-present rate: 10/10
target-heavy basin ranked first: 10/10
reconcile latency p50/p95 ms: 119.7/136.5
```

## Read

Hybrid retrieval finds the target evidence in every case, but raw top-5 is dominated
by decoys. Noetic usually compresses the broader candidate field into a better top-5.

The remaining failures are useful: target evidence is sometimes sparse inside the
result graph, or the winning basin is still polluted.

## Larger Demonstration

Generate a larger synthetic run:

```bash
uv run python tests/data/generate_hard_rag_benchmark.py \
  --variants 20 \
  --rubbish 50000 \
  --output tests/data/hard_rag_benchmark_large.json
```

Evaluate it:

```bash
uv run python evaluate_hard_benchmark.py \
  --data-path tests/data/hard_rag_benchmark_large.json \
  --collection-name hard_rag_benchmark_large_eval \
  --blind \
  --candidate-limit 50 \
  --result-limit 30 \
  --json-report reports/hard_rag_large_spectral.json
```

The key metrics are:

- `candidate target-present rate`: did retrieval find the evidence?
- `target-heavy basin ranked first`: did reconciliation choose the right region?
- `noetic top-5 from hybrid top-N`: did final chunk selection work?
- `reconcile latency p50/p95`: what did graph reconciliation cost?
