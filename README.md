# Noetic Search

Noetic Search (from *noesis*, direct intellectual apprehension or understanding)
is a post-retrieval reconciliation layer for hybrid search.

The system assumes a conventional first-stage retriever has already produced a
candidate set. It then builds a local weighted graph over those candidates
and returns a compact linked-evidence set by preserving strong hybrid anchors
and promoting graph-connected support chunks. It also detects spectral basin
boundaries and runs diffusion as an explicit research and inspection path.

It is not a replacement for vector search, BM25, reranking, or LLM reasoning. It
operates between candidate retrieval and prompt construction.

## Quickstart

Prerequisite: install `uv` if it is not already available.

Clone the repository, then run the package directly from the repo root:

```bash
git clone git@github.com:NLucy/noetic-search.git
cd noetic-search
uv run noetic demo
```

Run the test suite and strict documentation build:

```bash
uv run python -m unittest discover -s tests
uv run mkdocs build --strict
```

Generate the browser trace and serve the docs:

```bash
uv run noetic trace
uv run mkdocs serve
```

Then open:

```text
http://127.0.0.1:8000/
```

## Algorithm

```text
query
  -> hybrid candidates
  -> candidate graph
  -> linked-evidence ranking
  -> chunks

optional inspection path:
  candidate graph
  -> spectral basin boundaries
  -> whole-graph diffusion diagnostic
  -> basin-constrained diffusion over fixed basins
  -> score fixed basins
  -> uncertainty and basin field
```

The default `linked` return policy does not select chunks from diffusion. It
uses the calibrated graph directly: keep the strongest first-stage anchors,
then promote candidates that are connected to those anchors through strong
semantic, lexical-salience, cross-reference, or duplicate edges.

The optional research path proposes basin boundaries with the graph Laplacian
and Fiedler vector, runs whole-graph diffusion as a diagnostic, constrains
diffusion inside fixed basins, and scores those basins. It is valuable for the
trace viewer, uncertainty research, and the alternate `basin` return policy, but
it is not the benchmarked production selector.

## Documentation

Build and serve the documentation locally:

```bash
uv run mkdocs serve
```

Then open:

```text
http://127.0.0.1:8000/
```

The documentation has seven entry points:

- `Overview`: high-level system description and return surfaces.
- `The Math`: step-by-step treatment of candidates, graph construction,
  linked-evidence ranking, and result formatting.
- `Spectral Diffusion`: diagnostic and research treatment of the Laplacian,
  Fiedler vector, diffusion time steps, basin scoring, and uncertainty.
- `Production Trace`: browser visualization of one HotpotQA case moving through
  retrieval, graph construction, linked-evidence ranking, and final chunk
  return.
- `Diagnostic Trace`: the same HotpotQA case with the corpus-native `auto`
  graph formula enabled, exposing spectral basins, whole-graph diffusion,
  basin-constrained diffusion, and basin scoring for research inspection.

The committed documentation is the source of truth for the current algorithm.
Private study notes, sketches, and local presentation artifacts are not required
to run or understand the package.

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

## Benchmarks

The headline benchmark is external multi-hop evidence recovery. The internal
synthetic benchmark remains useful as a regression fixture, but it is not the
primary evidence for the claim.

![Hybrid versus Noetic auto support recall](docs/assets/benchmark_summary.svg)

Reproduce the headline external run:

```bash
uv run --extra eval python scripts/evaluate_multihop_objectives.py \
  --limit-cases 300 \
  --ks 5,10,20,30 \
  --objectives auto,reference_forward,lexical_salience_heavy,anti_hub,semantic_heavy \
  --benchmarks hotpotqa,2wikimultihopqa,musique \
  --json-report reports/multihop_objectives_grounded_auto_300.json

uv run python scripts/summarize_benchmark_suite.py \
  --multihop-report reports/multihop_objectives_grounded_auto_300.json \
  --clinical-report reports/clinical_evidence_frontier.json \
  --ks 5,10 \
  --json-report reports/benchmark_suite_summary.json

uv run python scripts/render_benchmark_chart.py \
  --summary reports/benchmark_suite_summary.json \
  --output docs/assets/benchmark_summary.svg
```

### Clinical Evidence Retrieval

The clinical benchmark is a new research track for high-stakes compact evidence
assembly. It is synthetic and retrieval-only: it does not diagnose, recommend
treatment, or score generated medical answers. Each case asks for the five
chunks needed to evaluate a medication-safety concern, with gold support chunks,
safety-critical chunks, and plausible decoys.

Generate the benchmark:

```bash
uv run python tests/data/generate_clinical_evidence_benchmark.py
```

Run the clinical retrieval evaluation:

```bash
uv run python scripts/evaluate_clinical_benchmark.py --blind --ks 5,10
```

Run the same evaluation with corpus-level graph calibration:

```bash
uv run python scripts/evaluate_clinical_benchmark.py --blind --ks 5,10 --calibrate-graph --graph-objective auto
```

Clinical metrics include standard precision, recall, hit rate, and MRR, plus:

- `exact_support`: whether all required support chunks appear within top-k.
- `critical_recall`: fraction of safety-critical support chunks recovered.
- `critical_miss_rate`: fraction of safety-critical support chunks missed.
- `decoy_rate`: whether a plausible off-chain decoy entered top-k.

This benchmark is intentionally harder than the current public multi-hop runs
and should not be read as a diagnostic benchmark. It is a retrieval-risk
benchmark: how much critical support is recovered, and how much plausible
off-chain material enters the compact return. `decoy_rate` is reported beside
critical recall as a domain risk annotation, not as the sole score.

### HotpotQA

HotpotQA is the primary external benchmark because it provides multi-hop
questions with supporting facts. The evaluation converts each context paragraph
into a retrieval document and measures whether the known supporting paragraphs
appear near the top.

Run HotpotQA retrieval evaluation:

```bash
uv run --extra eval python scripts/evaluate_hotpotqa.py --limit-cases 100 --ks 1,3,5,10,20,30
```

Run HotpotQA layer ablations:

```bash
uv run --extra eval python scripts/evaluate_hotpotqa.py --limit-cases 100 --ks 1,3,5,10,20,30 --ablations
```

Test unsupervised graph calibration:

```bash
uv run --extra eval python scripts/evaluate_hotpotqa.py --limit-cases 300 --ks 1,3,5,10,20,30 --calibrate-graph
```

Compare graph-health objectives:

```bash
uv run --extra eval python scripts/evaluate_hotpotqa_objectives.py --limit-cases 300 --ks 1,3,5,10,20,30 --objectives balanced,lexical_salience_heavy,reference_forward,anti_hub,semantic_heavy
```

Compare the same objectives across HotpotQA, 2WikiMultiHopQA, and MuSiQue:

```bash
uv run --extra eval python scripts/evaluate_multihop_objectives.py --limit-cases 300 --ks 5,10,20,30 --objectives auto,reference_forward,lexical_salience_heavy,anti_hub,semantic_heavy --benchmarks hotpotqa,2wikimultihopqa,musique --json-report reports/multihop_objectives_grounded_auto_300.json
```

Run focused production ablations over the linked-evidence path:

```bash
uv run --extra eval python scripts/evaluate_linked_ablation.py --benchmarks hotpotqa,2wikimultihopqa,musique --limit-cases 100 --ks 5,10 --json-report reports/linked_ablation_100.json
```

Train graph-health operating ranges on training cases, select on validation
cases, then evaluate the frozen configuration on held-out cases:

```bash
uv run --extra eval python scripts/tune_graph_health_config.py --benchmarks hotpotqa,2wikimultihopqa,musique --train-cases 300 --validation-cases 300 --test-cases 300 --validation-finalists 8 --ks 5,10 --json-report reports/graph_health_config_validation.json
```

Summarize the external multi-hop suite and clinical frontier:

```bash
uv run python scripts/summarize_benchmark_suite.py --multihop-report reports/multihop_objectives_grounded_auto_300.json --clinical-report reports/clinical_evidence_frontier.json --ks 5,10 --json-report reports/benchmark_suite_summary.json
```

Run the diffusion-health diagnostic study:

```bash
uv run --extra eval python scripts/evaluate_diffusion_health.py --limit-cases 300 --ks 1,3,5,10,20,30 --objectives balanced,lexical_salience_heavy,reference_forward,anti_hub,semantic_heavy --benchmarks hotpotqa,2wikimultihopqa,musique
```

Current 300-case production result:

```text
dataset: hotpotqa/hotpot_qa
subset/split: distractor/validation
cases: 300
documents: 2964

variant  k   P@k    R@k    Hit@k  MRR@k
hybrid   5   0.311  0.777  0.983  0.892
hybrid   10  0.181  0.907  1.000  0.895
hybrid   20  0.095  0.953  1.000  0.895
hybrid   30  0.064  0.963  1.000  0.895
noetic   5   0.332  0.830  0.987  0.894
noetic   10  0.188  0.940  1.000  0.896
noetic   20  0.096  0.962  1.000  0.896
noetic   30  0.064  0.967  1.000  0.896
```

The current external claim is narrow: Noetic preserves hybrid's first-hop
strength and improves compact multi-hop evidence recovery by promoting linked
support chunks from the graph. The measured benchmark gain comes from graph
construction and linked-evidence ranking, not from diffusion alone.

Focused 100-case linked-production ablation:

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

This is the current source-of-lift result. Anchors alone reproduce hybrid.
Generic graph support alone hurts badly. The lift comes from preserving strong
hybrid anchors and promoting candidates linked to those anchors. Static defaults
already improve hybrid; corpus-native `auto` adds a smaller additional gain.

### Corpus-Native Calibration

`auto` is the corpus-native calibration path. It chooses graph weights from
corpus structure before query-time retrieval runs. It is useful, but the
ablation above shows the core production mechanism does not depend on a hidden
tuned formula. The selector scores candidate graph formulas by:

- graph density: enough edges to support expansion without collapsing into a
  dense field;
- largest connected component ratio: preserving a usable main component without
  requiring complete graph collapse;
- Freeman degree centralization: avoiding formulas where a few generic chunks
  dominate as hubs;
- duplicate pressure: avoiding repeated material masquerading as support;
- lexical fit: choosing lexical thresholds that match observed salience;
- resonance health: preserving semantic-plus-lexical agreement edges that
  diffusion and linked ranking can use;
- bridge risk: reducing semantic-only bridges that look related but are weakly
  anchored.

This is not query-specific tuning. It is corpus-native graph calibration:

```text
corpus text + embeddings -> graph health measurements -> frozen graph formula
```

The frozen formula is then evaluated on retrieval cases.

The graph measurements are standard or explicitly retrieval-native. Graph
density, largest connected component ratio, and Freeman degree centralization
describe graph structure. Duplicate pressure, lexical fit, agreement density,
and bridge risk describe retrieval evidence behavior. Their operating ranges and
mixture weights are held in `GraphHealthConfig`.

The current `GraphHealthConfig` values are fixed, interpretable operating
priors. They are not claimed to be theoretically optimal. The research contract
is that those priors are frozen before held-out evaluation, and any future
learned configuration must be selected on development benchmarks and evaluated
unchanged on held-out data.

When calibration is not supplied, the implementation falls back to static
engineering defaults. These defaults are useful for a cold start, tests, and
simple integration. The focused linked ablation shows they already improve over
hybrid; the 300-case headline chart reports the corpus-native `auto` path:

```text
semantic_weight            1.00
semantic_threshold         0.50
lexical_threshold          0.08
lexical_weight             0.20
cross_reference_weight     0.55
near_duplicate_threshold   0.86
near_duplicate_weight      0.05

anchor_count               4
query_weight               0.50
link_weight                0.35
support_weight             0.15
anchor_bonus               2.00
```

The benchmarked production path is linked-evidence ranking with
corpus-calibrated graph weights, preferably `objective="auto"`.

The important order is:

```text
1. Before queries:
   profile the corpus
   measure semantic and lexical pair structure
   try candidate edge formulas
   score graph health
   freeze GraphWeights

2. At query time:
   run hybrid retrieval
   build the candidate graph with the frozen weights
   preserve hybrid anchors
   promote graph-connected support chunks

3. In diagnostics and basin mode:
   seed diffusion with hybrid result energy
   let energy move across the weighted graph
   inspect where energy settles, leaks, or concentrates
```

So diffusion does not create the current `auto` weights directly. Calibration
chooses weights by asking whether the corpus graph has enough healthy structure:
agreement edges, controlled density, limited hub pressure, limited duplication,
and reduced semantic-only bridge risk. Diffusion then uses those weighted edges
at query time for diagnostics and basin-return research.

### Agreement, Tension, and Bridge Risk

The current theory is that a useful evidence graph is not built from similarity
alone. Similarity says two chunks are near one another. It does not say the
relationship is grounded enough to promote into a compact return.

Noetic separates four retrieval-native signals:

- `agreement`: semantic similarity and lexical anchoring both support the
  relationship;
- `tension`: one channel sees a relationship that the other channel does not
  support;
- `resonance`: agreement edges form a usable local support field rather than
  isolated pairwise matches;
- `bridge_risk`: semantic-only edges create plausible paths into weakly
  anchored neighboring material.

The conceptual relation formula is:

```text
Relation(i,j) = Agreement(i,j) - Tension(i,j) - Redundancy(i,j)
```

The calibration formula is:

```text
GraphHealth =
  density_score
+ connectivity_score
+ centralization_score
+ duplicate_score
+ lexical_fit_score
+ resonance_score
+ bridge_safety_score
```

`auto` selects the candidate graph formula with the strongest graph-health
score under the configured health objective. This is the basis for the current
claim: the method derives a corpus-native edge formula, freezes it, and then
tests whether that formula improves compact evidence recovery. The current
health objective is an interpretable prior validated by held-out benchmark
results; it is not presented as a final derived law. A larger validation study
should learn or justify the health-objective ranges across broader corpora.

Applied to one pair of chunks, the theory is:

```text
semantic high + lexical high
  -> agreement edge

semantic high + lexical weak
  -> possible bridge, higher tension

lexical high + semantic weak
  -> surface overlap, higher tension

near duplicate or generic hub behavior
  -> redundancy pressure
```

Applied to the whole corpus, the theory is:

```text
choose weights that make enough agreement edges for support to travel
without letting semantic-only bridges or generic hubs dominate the field
```

Historical 1,000-case named-objective comparison:

```text
variant                 k   P@k    R@k    Hit@k  MRR@k
hybrid                  5   0.309  0.773  0.976  0.902
balanced                5   0.322  0.805  0.978  0.902
lexical_salience_heavy  5   0.324  0.809  0.978  0.902
reference_forward       5   0.326  0.814  0.978  0.902
anti_hub                5   0.321  0.802  0.976  0.902
semantic_heavy          5   0.318  0.795  0.978  0.902

hybrid                 10   0.177  0.884  0.998  0.905
balanced               10   0.180  0.899  0.994  0.904
lexical_salience_heavy 10   0.181  0.903  0.994  0.904
reference_forward      10   0.181  0.905  0.994  0.904
anti_hub               10   0.180  0.898  0.994  0.904
semantic_heavy         10   0.179  0.893  0.992  0.904
```

This older comparison is retained as background for the named objectives. The
current headline result is the grounded `auto` run below. The background result
is still useful because semantic-heavy weighting is weaker, while lexical
salience and cross-reference weighting improve compact multi-hop support
recovery. The MRR change is small because hybrid already retrieves a first
supporting paragraph well; the measured gain is in recovering the linked
supporting paragraph inside a smaller returned set.

Current 300-case cross-benchmark objective result with `auto` included:

```text
benchmark         variant                 R@5    R@10   note
HotpotQA          hybrid                  0.777  0.907
HotpotQA          auto                    0.830  0.940  grounded default
HotpotQA          lexical_salience_heavy  0.838  0.942  best @5
HotpotQA          reference_forward       0.837  0.947  best @10

2WikiMultiHopQA   hybrid                  0.687  0.754
2WikiMultiHopQA   auto                    0.725  0.787  grounded default
2WikiMultiHopQA   reference_forward       0.730  0.791  best @5
2WikiMultiHopQA   lexical_salience_heavy  0.728  0.792  best @10

MuSiQue           hybrid                  0.600  0.677
MuSiQue           auto                    0.605  0.693  grounded default
MuSiQue           reference_forward       0.607  0.693  best @5
```

Across the three external corpora, grounded `auto` improves hybrid at `@5` and
`@10` without looking at question labels. It is not always the absolute best
named variant. Lexical-heavy and reference-forward objectives can edge it on
individual corpora, which is useful evidence for the formula: compact multi-hop
recovery benefits from semantic/lexical agreement and explicit reference
structure, while pure semantic-heavy weighting is weaker.

Current clinical frontier summary:

```text
variant                         critical_recall@5  decoy_rate@5
hybrid                          0.225              0.000
noetic_resonance                0.367              0.667
noetic_resonance_risk_aware     0.150              0.333

variant                         critical_recall@10 decoy_rate@10
hybrid                          0.475              1.000
noetic_resonance_risk_aware     0.517              0.833
```

The clinical result is not the primary retrieval claim. It is a research signal:
graph expansion can recover more critical support, but medical-style retrieval
needs explicit reporting of decoy exposure.

Current diffusion-health diagnostic result:

```text
benchmark         strongest dynamic signal
HotpotQA          neighbor_transfer, low isolation, moderate spread
2WikiMultiHopQA   field_flooding, flow_coherence, low isolation
MuSiQue           neighbor_transfer, low isolation
```

The diagnostic is label-free: each sampled node is activated, energy diffuses
through the objective's graph, and the graph is measured without using answers
or supporting-fact labels. The stable finding is that useful objectives are not
the sparsest objectives. They allow energy to reach direct neighbors while
avoiding isolated calibration graphs. The aggregate health score is useful as a
screen, but it is not yet strong enough to choose production weights by itself;
raw diagnostic metrics remain more informative.

### Internal Fixture

Generate the internal adversarial fixture:

```bash
uv run python tests/data/generate_hard_rag_benchmark.py
```

Evaluate the fixture:

```bash
uv run python scripts/evaluate_hard_benchmark.py --blind
```

Run fixture ablations:

```bash
uv run python scripts/evaluate_hard_benchmark.py --blind --ablations
```

The fixture mixes ten decision domains with plausible decoys, stale notes,
duplicated evidence, unrelated distractor documents, and distributed target
evidence. Blind mode strips benchmark-only labels before indexing. It is useful
for regression and pipeline diagnosis, especially for comparing linked return
against basin-only return:

```bash
uv run python scripts/evaluate_hard_benchmark.py --blind --return-policy basin
uv run python scripts/evaluate_hard_benchmark.py --blind --return-policy linked
```

MoreHopQA is the harder follow-on benchmark because it shifts from extractive
support recovery toward generative multi-hop reasoning. CoRAG MultiHopQA is a
possible later trace benchmark because it includes intermediate retrieval and
generation paths.

## Trace Viewers

Generate the default browser trace. The default is the HotpotQA Big Stone Gap
case used in the production and diagnostic docs.

```bash
uv run noetic trace
```

To regenerate the diagnostic trace for the same HotpotQA case:

```bash
uv run noetic trace --calibrate-graph --graph-objective auto --output docs/diagnostics_trace.json
```

Serve the docs and open `Production Trace` or `Diagnostic Trace`:

```bash
uv run mkdocs serve
```

The trace shows the corpus as a neutral field, highlights hybrid candidates,
draws evidence edges, marks the linked-evidence final return, and keeps spectral
basins plus diffusion as diagnostic panels. The default trace is generated by
`src/noetic_systems/trace.py` using the same retrieval, graph construction, and
linked-evidence ranking used by the production path, plus the research
diagnostics used for explanation. Benchmark labels in the trace case are
stripped before indexing unless `--labeled` is passed.

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

- `result.chunks(database)` returns LLM-ready chunks from the linked evidence set.
- `result.strongest_basin(database)` returns diagnostic basin payloads when
  diagnostics are included; otherwise it reflects the linked evidence set.
- `result.evidence_field()` returns the inspection field: linked return,
  optional competing basins, support edges, uncertainty, graph metrics, and a
  `diagnostics_included` flag.

## Implementation Notes

The current implementation uses:

- ChromaDB for storage and embeddings.
- BM25 plus vector retrieval for hybrid candidates.
- Embedding, lexical-salience, cross-reference, and near-duplicate signals for
  graph weights.
- Linked-evidence return by default: preserve strong hybrid anchors and promote
  graph-connected support chunks.
- Normalized graph Laplacian eigendecomposition, whole-graph diffusion, and
  basin-constrained diffusion remain available for diagnostics, trace
  visualization, and `return_policy="basin"`.

### Latency Notes

Compare production latency against `hybrid@candidate_limit`, not
`hybrid@final_k`. The production path retrieves a broad candidate set before
graph work:

```text
hybrid_search(query, k=50)
  -> graph over top 30
  -> linked-evidence ranking
  -> top 5 chunks
```

The fair baseline is therefore:

```text
hybrid_search(query, k=50)
```

The linked production path should not run diagnostics. Do not compute spectral
partitions, Laplacian eigendecomposition, diffusion, basin scoring, uncertainty,
or document specificity for ordinary linked retrieval. Those are available for
trace, research, and `return_policy="basin"`.

Latency-critical implementation details:

- Batch-fetch embeddings for all graph candidates.
- Vectorize pairwise cosine similarity with matrix normalization.
- Keep graph size bounded. With `result_limit=30`, graph construction checks
  `435` pairs; with `result_limit=50`, it checks `1225`.
- Keep linked ranking to query score, graph support, and strongest edge to the
  preserved hybrid anchors.
- Profile embedding fetch, pairwise similarity, lexical salience, and accidental
  diagnostic work if Noetic linked retrieval is much slower than `hybrid@50`.
