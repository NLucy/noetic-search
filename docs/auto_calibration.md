<div class="noetic-page">
  <section class="hero compact">
    <p class="eyebrow">Auto calibration</p>
    <h1>Auto chooses graph weights from corpus structure before queries run.</h1>
    <p>
      The production path works with fixed graph defaults or frozen
      corpus-native <code>auto</code> weights. Ablation shows the main lift comes
      from anchor-linked promotion, not from a hidden tuned formula. Auto
      calibration is still useful because it makes graph-weight selection
      explicit, inspectable, and reproducible.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Contract</p>
    <h2>Auto is corpus-level tuning, not query tuning.</h2>
    <p>
      Auto calibration samples the indexed corpus, measures pairwise structure,
      scores candidate graph formulas, and freezes one <code>GraphWeights</code>
      record. It does not inspect questions, labels, expected answers, LLM
      judgments, or benchmark targets.
    </p>
    <pre>index corpus
  -> sample chunks
  -> measure pairwise signals
  -> score candidate graph formulas
  -> freeze GraphWeights
  -> query-time linked retrieval</pre>
  </section>

  <section class="panel">
    <p class="eyebrow">Inputs</p>
    <h2>Auto measures the corpus using signals already available to RAG.</h2>
    <div class="symbols">
      <div><code>semantic_values</code><span>Pairwise embedding similarities across sampled chunks.</span></div>
      <div><code>lexical_values</code><span>Pairwise salient term and phrase overlap.</span></div>
      <div><code>cross_reference_rate</code><span>How often one chunk names another chunk's title-like label.</span></div>
      <div><code>duplicate_rate</code><span>How much near-duplicate pressure exists in the sample.</span></div>
      <div><code>graph_density</code><span>How many candidate pairs become edges under a formula.</span></div>
      <div><code>largest_component_ratio</code><span>How much of the graph sits in the main connected component.</span></div>
      <div><code>degree_centralization</code><span>How strongly graph degree concentrates around a small number of hubs.</span></div>
    </div>
  </section>

  <section class="panel">
    <p class="eyebrow">Candidate formulas</p>
    <h2>Auto tries many possible edge recipes.</h2>
    <p>
      A candidate formula is one possible <code>GraphWeights</code> setting. It
      changes semantic thresholds, lexical thresholds, semantic weight, lexical
      weight, cross-reference weight, and duplicate contribution.
    </p>
    <pre>GraphWeights(
  semantic_weight,
  semantic_threshold,
  lexical_threshold,
  lexical_weight,
  cross_reference_weight,
  near_duplicate_threshold,
  near_duplicate_weight,
)</pre>
    <p>
      The search includes named objective families such as
      <code>balanced</code>, <code>reference_forward</code>,
      <code>lexical_salience_heavy</code>, <code>anti_hub</code>, and
      <code>semantic_heavy</code>, plus a grid over semantic and lexical
      thresholds and weights. <code>auto</code> selects the highest-scoring
      candidate.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Objective</p>
    <h2>A healthy graph is connected, but not indiscriminate.</h2>
    <pre>GraphHealth =
  density_score
+ connectivity_score
+ centralization_score
+ duplicate_score
+ lexical_fit_score
+ resonance_score
+ bridge_safety_score</pre>
    <div class="symbols">
      <div><code>density_score</code><span>Rewards enough edges for support expansion while penalizing dense collapse.</span></div>
      <div><code>connectivity_score</code><span>Rewards a large usable connected component without requiring full graph collapse.</span></div>
      <div><code>centralization_score</code><span>Rewards low Freeman degree centralization so generic chunks do not dominate as hubs.</span></div>
      <div><code>duplicate_score</code><span>Rewards formulas that keep repeated material from looking like broad support.</span></div>
      <div><code>lexical_fit_score</code><span>Rewards lexical thresholds that match the observed corpus salience distribution.</span></div>
      <div><code>resonance_score</code><span>Rewards semantic-plus-lexical agreement edges that can support graph expansion.</span></div>
      <div><code>bridge_safety_score</code><span>Rewards formulas that limit semantic-only bridge risk.</span></div>
    </div>
  </section>

  <section class="panel">
    <p class="eyebrow">Measures</p>
    <h2>Graph health is grounded in explicit corpus measurements.</h2>
    <p>
      Each candidate formula is applied to the sampled corpus pairs. Auto then
      measures the graph that formula would create. The current score is a
      bounded weighted combination of established graph structure measures and
      retrieval-specific evidence measures. The measurements are not invented:
      graph density, largest connected component ratio, and Freeman degree
      centralization are standard graph descriptors. The open question is how
      strongly to weight them for retrieval, so those ranges and mixture weights
      live in an explicit <code>GraphHealthConfig</code>. The current values are
      fixed, interpretable operating priors, not a claim of theoretical
      optimality.
    </p>
    <pre>health =
  0.20 * density_score
+ 0.14 * connectivity_score
+ 0.14 * centralization_score
+ 0.12 * duplicate_score
+ 0.13 * lexical_score
+ 0.20 * resonance_score
+ 0.15 * bridge_score</pre>
    <div class="symbols">
      <div><code>density = |E| / (n(n-1)/2)</code><span>Standard graph density: fraction of possible undirected edges that exist.</span></div>
      <div><code>LCC_ratio = |V_largest_component| / |V|</code><span>Largest connected component ratio: how much of the sample belongs to the main usable component.</span></div>
      <div><code>degree_centralization</code><span>Freeman degree centralization: a standard hub-concentration measure with 0 for uniform degree and 1 for a star graph.</span></div>
      <div><code>duplicate_rate = duplicate_pairs / pair_count</code><span>Fraction of sampled pairs above the near-duplicate threshold.</span></div>
      <div><code>agreement_density = agreement_edges / pair_count</code><span>Fraction of sampled pairs with semantic similarity above threshold and lexical salience above threshold, excluding near-duplicates.</span></div>
      <div><code>bridge_rate = semantic_only_edges / semantic_edges</code><span>Fraction of semantic edges that lack lexical grounding.</span></div>
      <div><code>lexical_p75, lexical_p90</code><span>Corpus salience percentiles used to decide whether the lexical threshold is too loose or too strict.</span></div>
    </div>
  </section>

  <section class="panel">
    <p class="eyebrow">Scoring shape</p>
    <h2>The score prefers a middle structure, not maximum connectivity.</h2>
    <p>
      Density, largest connected component ratio, and agreement density use
      target-shaped scoring. Too few edges means support cannot expand. Too many
      edges means the graph collapses into an indiscriminate field. Full
      connectivity is also not automatically ideal because a single component
      can hide weak bridges. Degree centralization, duplicate pressure, and
      bridge risk use penalty ramps: they are acceptable at low levels and
      increasingly costly past a threshold.
    </p>
    <pre>density_score:
  best near density = 0.16
  penalize sparse graphs below that target
  penalize dense collapse above that target

resonance_score:
  best near agreement_density = 0.06
  rewards semantic + lexical agreement edges

connectivity_score:
  best near LCC_ratio = 0.82
  penalize fragmentation and complete collapse

centralization_score:
  1 - penalty(Freeman degree centralization, start=0.18, stop=0.55)

duplicate_score:
  1 - penalty(duplicate_rate, start=0.04, stop=0.18)

bridge_safety_score:
  1 - penalty(bridge_rate, start=0.20, stop=0.70)</pre>
    <p>
      <code>bridge_score</code> is multiplied by <code>resonance_score</code>.
      That prevents a graph from scoring well simply because it avoids risky
      bridges by creating almost no useful agreement edges.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Training protocol</p>
    <h2>The ranges and weights are explicit priors that can be validated.</h2>
    <p>
      There are two different things here. The graph measurements are grounded
      in graph theory and retrieval mechanics. The operating ranges and mixture
      weights are experimental parameters. The current repo uses fixed,
      interpretable priors and evaluates them after freezing. To support larger
      research work, the repo also includes a calibration script that can screen
      <code>GraphHealthConfig</code> candidates on training cases, select the
      winner on validation cases, and evaluate that frozen configuration on
      held-out cases.
    </p>
    <pre>uv run --extra eval python scripts/tune_graph_health_config.py \
  --benchmarks hotpotqa,2wikimultihopqa,musique \
  --train-cases 300 \
  --validation-cases 300 \
  --test-cases 300 \
  --validation-finalists 8 \
  --ks 5,10 \
  --json-report reports/graph_health_config_validation.json</pre>
    <p>
      This is supervised meta-calibration, not per-query tuning. Benchmark
      labels select the global graph-health configuration during development.
      Once selected, that configuration is frozen and the production path still
      uses only corpus text, embeddings, lexical salience, and query-time hybrid
      scores.
    </p>
    <p>
      In the initial 100-train/100-held-out sweep across HotpotQA,
      2WikiMultiHopQA, and MuSiQue, the default config tied for the best
      training score and improved held-out recall over hybrid on all three
      datasets at <code>@5</code> and <code>@10</code>. A later
      train/validation/held-out pilot again selected the default config, but
      also showed that MuSiQue can be less responsive. This supports the default
      as a reasonable baseline, not as a final formula.
    </p>
    <p>
      The linked-production ablation is the stronger source-of-lift evidence:
      static linked ranking and auto linked ranking both beat hybrid, while
      support-only graph ranking performs poorly. That means calibration should
      be presented as a configuration layer over the mechanism, not as the
      mechanism itself.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Implementation</p>
    <h2>Calibrate once, reuse for all queries over that index.</h2>
    <pre>weights, profile = calibrate_corpus_graph_weights(
    database,
    sample_limit=500,
    objective="auto",
)

reconciler = Reconciler(
    database,
    graph_weights=weights,
)

result = reconciler.reconcile(
    query,
    candidate_limit=50,
    result_limit=30,
    return_policy="linked",
)

chunks = result.chunks(database, k=5)</pre>
    <p>
      The frozen weights should be treated as index configuration. Recompute
      them when the corpus changes materially, when chunking changes, or when
      embedding models change.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Fallback</p>
    <h2>Static defaults are conservative and benchmarked separately.</h2>
    <pre>semantic_weight            1.00
semantic_threshold         0.50
lexical_threshold          0.08
lexical_weight             0.20
cross_reference_weight     0.55
near_duplicate_threshold   0.86
near_duplicate_weight      0.05</pre>
    <p>
      These values allow the package to run without calibration. The linked
      ablation shows they already improve over hybrid, which is useful because
      it reduces dependence on tuning. The stronger production recommendation is
      still to derive corpus-native weights with <code>objective="auto"</code>
      when a stable corpus is available.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">How to say it</p>
    <h2>Auto converts corpus statistics into a frozen graph formula.</h2>
    <p class="say-it">
      Auto calibration profiles the corpus once, scores possible graph formulas
      by structural health, freezes the selected <code>GraphWeights</code>, and
      then uses those weights for query-local evidence graphs. The per-corpus
      calibration step is unsupervised. The global health configuration can be
      benchmark-trained during development and then frozen for held-out use.
    </p>
  </section>
</div>
