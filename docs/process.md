# The Process

Noetic Search is a shift from returning individually ranked chunks to returning a
coherent evidence region.

Standard hybrid search asks:

```text
Which chunks are individually closest to this query?
```

Noetic Search asks:

```text
After retrieval, which group of chunks forms the strongest supported idea?
```

That difference matters. The LLM does not receive a pile of raw nearest neighbors and
then struggle to repair retrieval mistakes. It receives chunks selected from a
reconciled basin: a local concept formed inside the candidate field before prompting.

When we say Noetic Search has multihop reasoning built into search, we mean graph
support propagation. A chunk can gain importance through related chunks across one
or more graph edges. This is not hidden LLM chain-of-thought. It is explicit,
inspectable computation over retrieved evidence.

This is the same intuition behind spectral diffusion and manifold methods, but
applied locally. The manifold is not the whole corpus. The manifold is the retrieved
candidate field for one query.

## Why Local Matters

A whole-corpus manifold is elegant, but it is often too broad for retrieval-time
reasoning. It mixes many unrelated neighborhoods, historical topics, stale clusters,
and domain-specific structures before the user has asked a question.

Noetic Search builds a local graph only after hybrid retrieval. That gives the graph
three useful properties:

- it is small enough to compute at query time
- it is conditioned on the user's intent
- it preserves candidate recall while changing final selection

The goal is not to create a universal map of the corpus. The goal is to resolve the
evidence structure inside the candidates that retrieval already found.

## 1. Gather Candidates

The first step is still ordinary retrieval.

Hybrid search collects a larger candidate set using:

- vector search for semantic similarity
- BM25 lexical search for exact and rare-term matching
- optional metadata filters supplied by the caller

The output is a candidate field:

```text
document id
chunk text
metadata
hybrid retrieval score
```

In the hard benchmark, the reconciler usually starts from hybrid top 50 rather than
raw top 5.

### Principle

This step is about recall. Retrieval should be broad enough that the right evidence
is somewhere in the candidate set.

BM25 is a classic information retrieval method. It rewards terms that are frequent in
a document but rare across the corpus. Vector search is a semantic method. It finds
chunks that are close in embedding space even when the wording differs.

Hybrid search uses both because neither is sufficient alone.

### Why It Makes Sense Here

Noetic Search cannot recover evidence that never enters the candidate field. The
first job is therefore to retrieve broadly. The second job is to select intelligently.

That is the core product pattern:

```text
broad retrieval for recall
graph reconciliation for precision
```

## 2. Build The Evidence Graph

Each candidate becomes a node in a graph.

Weighted evidence connections join candidates that appear related. The current
implementation uses only signals available out of the box:

- embedding similarity
- shared ordinary metadata such as `document_id`, `url`, `title`, `domain`, `section`, `author`, or `source`
- very high embedding similarity as a near-duplicate signal

No labels are required. No LLM has to annotate the corpus. The graph is built from
raw chunks, embeddings, and ordinary metadata.

In the final adjacency graph, a pair of chunks has one connection weight. The
individual signals are kept as inspection records, then collapsed into that one
pairwise weight for diffusion and spectral partitioning.

### Principle

A ranked list treats chunks as isolated objects. A graph treats them as evidence that
can support, duplicate, or compete with other evidence.

Graphs are used this way in many fields:

- citation analysis, where papers support and cluster around ideas
- web ranking, where pages gain importance from links
- social network analysis, where communities emerge from relationships
- spectral clustering, where the geometry of a graph reveals natural partitions
- physical diffusion models, where signal spreads through a medium

Here, the graph is not modeling people or web pages. It is modeling retrieved chunks
as a local evidence field.

### Why It Makes Sense Here

Top-k misses relationships. Two chunks ranked 12 and 18 may be more important
together than chunks ranked 1 and 2. A graph lets the search layer notice that.

This is the first place where search begins to look like pre-LLM reasoning. The
system is no longer asking only, "Which chunk is close?" It is asking, "Which chunks
cohere?"

## 3. Seed Energy

Each node starts with energy from its hybrid retrieval score, decayed by rank:

```text
seed = retrieval_score / (rank + 1)
```

The values are normalized so total energy is 1.0.

This keeps the original retrieval signal. High-ranking candidates matter. They just
do not get the final word.

### Principle

This is similar to initialization in random-walk methods, belief propagation, and
PageRank-style algorithms. The starting distribution matters, but the graph controls
how that signal moves.

The seed says:

```text
Retrieval thinks these nodes are promising.
```

Diffusion then asks:

```text
Do those promising nodes have support?
```

### Why It Makes Sense Here

The reconciler should not throw away retrieval rank. Hybrid search is still doing
real work. But raw rank is only an initial belief, not a final answer.

This is the bridge between standard search and Noetic Search.

## 4. Diffuse Energy

Energy spreads through graph edges for a fixed number of iterations.

Each step does three things:

1. A node keeps part of its current energy.
2. The remaining energy flows to neighbors in proportion to edge weight.
3. Energies are normalized back to 1.0.

If a candidate is connected to other strong candidates, it can gain support. If it is
isolated, its influence remains narrow. If a cluster is repetitive but shallow, it can
collect energy but later be penalized by basin scoring and chunk ordering.

### Principle

Diffusion is a way of measuring influence through relationships.

It appears in:

- heat equations, where temperature spreads through a surface
- Markov chains, where probability moves across states
- PageRank, where importance flows through web links
- graph signal processing, where values are smoothed over graph structure
- manifold learning, where local neighborhoods reveal lower-dimensional structure

In Noetic Search, diffusion lets evidence perform a limited kind of multihop support
before the LLM sees anything.

### Why It Makes Sense Here

This is the key distinction from ordinary reranking.

A reranker usually scores each candidate against the query. Diffusion scores
candidates inside a field. A chunk can become more important because it connects to
other useful chunks, not merely because it is individually query-like.

That is why this can reduce LLM reasoning overhead. The LLM receives evidence that
has already been organized by support structure.

## 5. Detect Basins

After diffusion, the graph is partitioned into basins.

A basin is a coherent candidate region. In product terms, it is the search layer's
best approximation of an idea, concept, or evidence position.

The default detector uses eigendecomposition of the normalized graph Laplacian. The
important object is the Fiedler vector, which is the eigenvector associated with the
second-smallest eigenvalue. It proposes a natural split in the graph.

The reconciler accepts the split only when:

- both sides are large enough to be useful
- the split improves modularity
- the graph structure supports the separation

### Principle

The graph Laplacian is one of the central tools in spectral graph theory. It captures
how each node relates to its neighbors and how signal varies across the graph.

The smallest eigenvalue corresponds to the trivial constant structure. The
second-smallest eigenvector often reveals the best relaxed cut through the graph. In
plain English: it points toward a natural way to divide the graph into two regions
without cutting too much internal support.

This idea appears in:

- spectral clustering
- graph partitioning
- image segmentation
- numerical physics
- manifold learning
- community detection

### Why It Makes Sense Here

The retrieved candidate field often contains multiple possible stories:

- a stale approval story
- a real risk story
- a generic background story
- unrelated cross-domain noise

Spectral partitioning helps separate those stories as graph regions. Instead of
asking the LLM to discover those regions from a flat list, search does the first pass.

## 6. Score Basins

Each basin receives a field score.

The score is not raw diffusion energy. It combines several properties:

- settled energy
- support count
- cohesion
- duplicate penalty

This matters because the strongest evidence is not always the loudest cluster.

A narrow cluster of duplicate approvals may have high retrieval energy. A broader
basin with independent risk evidence may be more useful even if its individual
members were lower-ranked.

### Principle

This is multi-objective scoring. The system is balancing local relevance, graph
support, cohesion, and anti-duplication pressure.

This resembles ideas from:

- diversified search
- evidence aggregation
- ensemble methods
- graph community scoring
- information retrieval evaluation

The score is intentionally plain. It is a compact engineering judgment about
what makes a candidate region useful.

### Why It Makes Sense Here

The output should not be "the cluster with the most repeated wording." It should be
the basin that carries the best evidence.

That requires scoring the basin as a region, not merely summing the ranks of its
members.

## 7. Rank Chunks Inside The Winning Basin

Once the winning basin is selected, the system still has to choose which chunks to
return.

The default return order is specificity-first, with settled energy as a smaller
tie-in. Specificity is an IDF-like density measure. Chunks with rarer, more
information-dense terms inside the candidate field move upward.

This helps prevent generic exact-query boilerplate from crowding out more useful
evidence.

### Principle

This step combines two search instincts:

- use the basin to choose the concept
- use specificity to choose the best representatives of that concept

It is similar to selecting representative passages from a cluster after clustering,
except the cluster was formed from graph reconciliation rather than simple
nearest-neighbor grouping.

### Why It Makes Sense Here

The LLM does not need every member of a basin. It needs the best few chunks that
represent the basin.

This is where Noetic Search compresses a broad retrieval field back down to an
LLM-friendly payload.

## 8. Estimate Uncertainty

The system reports uncertainty from three signals:

- **Basin competition**: whether the runner-up basin is close to the winner.
- **Dispersion**: whether energy stayed scattered instead of settling.
- **Modularity**: whether the graph has a clear community structure.

Low uncertainty means the field settled cleanly. High uncertainty means the evidence
remained divided, diffuse, or weakly structured.

### Principle

This is not probabilistic truth. It is structural uncertainty.

The system is asking:

```text
Did the candidate field produce a clear winner?
```

That is useful because retrieval failures often leave a structural trace. The field
looks divided, noisy, or unstable.

### Why It Makes Sense Here

An LLM should not receive uncertain evidence as if it were settled. If the graph
shows competing basins, the final answer should carry that caveat.

The search layer can therefore hand the LLM both evidence and the confidence shape of
that evidence.

## 9. Return Chunks Or The Inspection Field

The same reconciliation result supports three caller paths:

- `result.strongest_basin(database)` returns the default Noetic surface: the strongest basin, chunks, uncertainty, and metrics.
- `result.chunks(database)` returns only LLM-ready chunks from the strongest basin.
- `result.evidence_field()` returns the inspection field: winning basin, competing basins, support edges, uncertainty, and graph metrics.

The LLM comparison harness can send baseline top-k chunks, the strongest basin, or
the full evidence field through Responses API input items.

The LLM can explain the result. It does not invent the evidence structure.

## What This Is Really Doing

Noetic Search moves part of the reasoning burden from the LLM into search.

It does not replace language reasoning. It reduces the amount of retrieval reasoning
the LLM has to perform after the prompt is built.

The LLM no longer receives:

```text
Here are the five chunks that individually ranked highest. Good luck.
```

It receives:

```text
Here are chunks selected from the strongest reconciled evidence basin.
Here is the uncertainty shape if you need it.
```

That is the point.

Noetic Search surfaces a coherent evidence concept instead of raw top-k.

## Code Map

The implementation is deliberately small.

| Process step | Main code |
| --- | --- |
| Store and fetch chunks | `src/noetic_systems/database.py` |
| Vector search | `src/noetic_systems/search/semantic.py` |
| BM25 lexical search | `src/noetic_systems/search/lexical.py` |
| Hybrid candidate ranking | `src/noetic_systems/search/hybrid.py` |
| Reconciliation orchestration | `src/noetic_systems/reconciliation/engine.py` |
| Candidate field admission | `src/noetic_systems/reconciliation/candidates.py` |
| Graph construction | `src/noetic_systems/reconciliation/graph.py` |
| Energy seeding | `src/noetic_systems/reconciliation/seeding.py::seed_energy()` |
| Diffusion | `src/noetic_systems/reconciliation/diffusion.py::diffuse()` |
| Spectral basin detection | `src/noetic_systems/reconciliation/spectral.py::detect_spectral_communities()` |
| Fiedler split | `src/noetic_systems/reconciliation/spectral.py::fiedler_split()` |
| Basin scoring | `src/noetic_systems/reconciliation/basins.py::build_basins()` |
| Intra-basin chunk ranking | `src/noetic_systems/reconciliation/ranking.py::rank_basin_documents()` |
| Uncertainty | `src/noetic_systems/reconciliation/uncertainty.py::calculate_uncertainty()` |
| Result surfaces | `src/noetic_systems/reconciliation/result.py` |
| LLM payloads | `src/noetic_systems/llm/experiment.py` |

The whole path is:

```text
Database
  -> SemanticSearch + LexicalSearch
  -> HybridSearch
  -> Reconciler.reconcile()
  -> ReconciliationResult
  -> strongest_basin(), chunks(), or evidence_field()
```
