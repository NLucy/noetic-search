<div class="noetic-page">
  <section class="hero compact">
    <p class="eyebrow">Technical path</p>
    <h1>How Noetic Search turns retrieved chunks into linked evidence.</h1>
    <p>
      The pipeline follows the implementation order:
      <code>candidates -> graph -> linked ranking -> result</code>.
      Each step has a narrow mathematical role and a concrete artifact.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Before query time</p>
    <h2>Corpus-native calibration chooses the graph formula.</h2>
    <p>
      The <code>auto</code> path profiles the corpus before query-time retrieval
      runs. It tries candidate graph formulas and scores them by graph health:
      density, largest connected component ratio, Freeman degree centralization,
      duplicate pressure, lexical fit, resonance health, and semantic-only
      bridge risk. The result is one frozen graph formula used at query time.
      Static fallback constants exist so the system can run cold, but the
      benchmarked production path uses corpus-native <code>auto</code> weights.
    </p>
    <pre>corpus text + embeddings
  -> pairwise semantic and lexical profiles
  -> graph-health grid
  -> frozen GraphWeights
  -> query-time graph construction</pre>
    <div class="symbols">
      <div><code>corpus text</code><span>The raw chunks that have been indexed. Calibration reads the same text that retrieval will later search.</span></div>
      <div><code>embeddings</code><span>Vector representations of those chunks. They provide the semantic side of each possible edge.</span></div>
      <div><code>pairwise semantic profile</code><span>The distribution of embedding similarities between sampled chunk pairs.</span></div>
      <div><code>pairwise lexical profile</code><span>The distribution of salient term and phrase overlap between sampled chunk pairs.</span></div>
      <div><code>graph-health grid</code><span>The set of candidate edge formulas tested against the sampled corpus structure.</span></div>
      <div><code>GraphWeights</code><span>The frozen edge formula selected by calibration: thresholds and weights for semantic, lexical, cross-reference, and duplicate signals.</span></div>
      <div><code>GraphHealthConfig</code><span>The scoring configuration that says how much to value density, connectivity, hub control, duplicate control, lexical fit, resonance, and bridge safety.</span></div>
      <div><code>static fallback constants</code><span>Fixed default edge settings used when calibration is not run.</span></div>
    </div>
    <p>
      Calibration builds candidate edge formulas from corpus-level pair
      measurements, scores those formulas, and freezes the best one. The
      health-score ranges and mixture weights are held in
      <code>GraphHealthConfig</code>. The current values are fixed,
      interpretable priors. Future research can select that config on
      development benchmarks and then freeze it for held-out evaluation.
    </p>
    <div class="symbols">
      <div><code>density</code><span>The fraction of possible chunk-pair edges that actually exist. Too sparse cannot expand support; too dense becomes indiscriminate.</span></div>
      <div><code>largest_component_ratio</code><span>The fraction of nodes inside the largest connected component. It measures whether the graph has a usable main evidence field.</span></div>
      <div><code>Freeman degree centralization</code><span>A standard graph measure of hub concentration. High centralization means a few generic chunks dominate many connections.</span></div>
      <div><code>duplicate_pressure</code><span>How often near-duplicate chunks would be connected. It guards against repeated evidence looking like independent support.</span></div>
      <div><code>lexical_fit</code><span>How well the lexical threshold matches the corpus's observed salience distribution.</span></div>
      <div><code>resonance_health</code><span>How often semantic similarity and lexical salience agree on the same edge. This is the preferred evidence relationship.</span></div>
      <div><code>semantic_only_bridge_risk</code><span>How often semantic similarity creates an edge without lexical grounding. This can indicate useful paraphrase, but also weak off-chain bridges.</span></div>
    </div>
  </section>

  <section class="panel">
    <p class="eyebrow">Query time</p>
    <h2>The frozen graph formula is applied to retrieved candidates.</h2>
    <p>
      After calibration, query-time retrieval is simple. Hybrid search returns
      candidates. Noetic admits the local working field, builds edges with the
      frozen <code>GraphWeights</code>, preserves the strongest hybrid anchors,
      and applies linked ranking.
    </p>
    <pre>query
  -> hybrid candidates
  -> graph with frozen GraphWeights
  -> linked-evidence ranking
  -> compact chunks</pre>
    <p>
      This page describes that production flow only.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Core theory</p>
    <h2>Similarity is not enough. The graph must measure agreement and tension.</h2>
    <p>
      A semantic neighbor can be true support, harmless background, or a
      plausible off-chain branch. The formula therefore treats relationships as
      structured evidence, not just closeness. Strong edges come from agreement:
      semantic similarity and lexical anchoring both support the relation.
      Risky edges come from tension: one channel sees a connection that the
      other does not ground.
    </p>
    <pre>Relation(i,j) = Agreement(i,j) - Tension(i,j) - Redundancy(i,j)</pre>
    <div class="symbols">
      <div><code>Agreement(i,j)</code><span>Semantic similarity and lexical salience both support the relationship between chunks i and j.</span></div>
      <div><code>Tension(i,j)</code><span>Mismatch between channels, such as high semantic similarity with weak lexical anchoring.</span></div>
      <div><code>Redundancy(i,j)</code><span>Duplicate or generic hub pressure that can make repeated material look like support.</span></div>
      <div><code>bridge_risk</code><span>Risk from semantic-only bridges into weakly anchored neighboring material.</span></div>
      <div><code>resonance</code><span>A usable support field formed by agreement edges, not just isolated pairwise matches.</span></div>
    </div>
  </section>

  <section class="panel">
    <p class="eyebrow">Calibration objective</p>
    <h2>The selected graph should be connected, but not indiscriminate.</h2>
    <p>
      <code>auto</code> chooses the formula whose graph has enough structure for
      support expansion while controlling dense collapse, generic hubs,
      duplicate pressure, and semantic-only bridge risk. The graph measurements
      are label-free at corpus-calibration time. If a project wants a stronger
      empirical footing, it can train the global <code>GraphHealthConfig</code>
      on development benchmarks, freeze it, and then evaluate the frozen setting
      on held-out cases. The current default should be read as a reasonable
      fixed prior, not a derived optimum.
    </p>
    <pre>GraphHealth =
  density_score
+ connectivity_score
+ centralization_score
+ duplicate_score
+ lexical_fit_score
+ resonance_score
+ bridge_safety_score</pre>
    <div class="symbols">
      <div><code>density_score</code><span>Rewards enough graph edges for support expansion while penalizing dense collapse.</span></div>
      <div><code>connectivity_score</code><span>Rewards a large usable connected component without requiring full graph collapse.</span></div>
      <div><code>centralization_score</code><span>Rewards low Freeman degree centralization so generic chunks do not dominate the field.</span></div>
      <div><code>duplicate_score</code><span>Rewards formulas that keep near-duplicate pressure limited.</span></div>
      <div><code>lexical_fit_score</code><span>Rewards lexical thresholds that match observed salience in the corpus.</span></div>
      <div><code>resonance_score</code><span>Rewards retaining enough non-duplicate semantic-plus-lexical agreement edges for graph expansion to be usable.</span></div>
      <div><code>bridge_safety_score</code><span>Rewards formulas that avoid excessive semantic-only bridges.</span></div>
    </div>
  </section>

  <section class="panel">
    <p class="eyebrow">Latency discipline</p>
    <h2>Compare the production path to hybrid at the same candidate depth.</h2>
    <p>
      The production path retrieves a broad candidate field before graph work.
      A fair latency comparison is therefore <code>hybrid@candidate_limit</code>
      versus <code>hybrid@candidate_limit + graph + linked ranking</code>, not
      Noetic top-5 versus hybrid top-5. The graph stage should be the added cost
      after broad retrieval, not a hidden change in the retrieval depth.
    </p>
    <pre>fair baseline:
hybrid_search(query, k=50)

production:
hybrid_search(query, k=50)
  -> graph over top 30
  -> linked ranking
  -> top 5 chunks</pre>
    <p>
      Linked-evidence retrieval only needs query score, graph support, and the
      strongest edge to the preserved anchors. The production selector does not
      need the research diagnostics described elsewhere in the docs.
    </p>
    <div class="symbols">
      <div><code>candidate_limit</code><span>Broad first-stage retrieval depth, usually 50.</span></div>
      <div><code>result_limit</code><span>Graph-admitted working field, usually 30.</span></div>
      <div><code>final_k</code><span>Compact chunk count returned to the caller, usually 5.</span></div>
      <div><code>result_limit*(result_limit-1)/2</code><span>Pair count for graph construction. A 30-node graph has 435 pairs; a 50-node graph has 1225.</span></div>
    </div>
  </section>

  <section class="math-path">
    <article class="math-item">
      <div class="math-tag">1. Candidates</div>
      <div class="math-section">
        <h2>Start with broad retrieval, not final truth.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            Hybrid retrieval is a recall machine. It gives a ranked field of
            plausible chunks, but the rank is only an initial opinion.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            The benchmark retrieves hybrid top 50. The reconciler then keeps a
            graph-sized candidate field, usually 30 chunks, so graph operations
            remain local and query-time feasible.
          </p>
        </div>
        <p class="math-example">
          If target evidence appears below raw top-5, standard RAG can miss it.
          Noetic still has a chance if broad retrieval admitted it to the field.
        </p>
        <pre>candidate_field = hybrid_search(query, top_n=50)</pre>
        <div class="symbols">
          <div><code>candidate_field</code><span>The broad retrieved set admitted for later graph work.</span></div>
          <div><code>hybrid_search</code><span>The first-stage retriever combining lexical and vector signals.</span></div>
          <div><code>query</code><span>The user's question or search request.</span></div>
          <div><code>top_n</code><span>How many first-stage candidates to retrieve before graph reconciliation.</span></div>
          <div><code>50</code><span>The default broad candidate count used by the trace and benchmark.</span></div>
        </div>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">2. Graph</div>
      <div class="math-section">
        <h2>Turn chunks into weighted relationships.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            A ranked list treats chunks as isolated objects. A graph lets chunks
            support, duplicate, or compete with one another.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            Each candidate becomes a node. Each pair can receive one weighted
            evidence connection from embedding similarity, lexical salience,
            explicit cross-reference, and near-duplicate signal. Metadata
            remains available on returned chunks, but the graph is built from
            ordinary text and embeddings.
          </p>
        </div>
        <p class="math-example">
          Two lower-ranked chunks can matter more together than two higher-ranked
          chunks that are isolated or repetitive.
        </p>
        <pre>A[i,j] = semantic_signal + lexical_signal + cross_reference_signal + duplicate_signal</pre>
        <div class="symbols">
          <div><code>A</code><span>Weighted adjacency matrix.</span></div>
          <div><code>A[i,j]</code><span>Relationship strength between chunks i and j.</span></div>
          <div><code>i, j</code><span>Candidate chunk nodes in the local graph.</span></div>
          <div><code>semantic_signal</code><span>Embedding similarity contribution between the two chunks.</span></div>
          <div><code>lexical_signal</code><span>Shared salient word or phrase contribution between the two chunks after stop-word removal and local IDF weighting.</span></div>
          <div><code>cross_reference_signal</code><span>Contribution added when one chunk explicitly names the title-like label of another chunk.</span></div>
          <div><code>duplicate_signal</code><span>Small near-duplicate contribution used so repetition can later be detected and penalized.</span></div>
        </div>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">3. Linked Ranking</div>
      <div class="math-section">
        <h2>Rank linked evidence for the compact return.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            The default return should preserve what hybrid found well while
            pulling in graph-connected support that raw top-k may rank too low.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            The linked-evidence policy keeps the strongest hybrid anchors, then
            scores the remaining graph candidates by original query score, edge
            strength to the anchors, and graph support. This is the
            benchmark-winning production path.
          </p>
        </div>
        <pre>linked_score = 0.50*query_score + 0.35*anchor_affinity + 0.15*support
top_5 = anchors + highest linked_score support chunks</pre>
        <div class="symbols">
          <div><code>linked_score</code><span>Default score for non-anchor candidates in the compact return policy.</span></div>
          <div><code>query_score</code><span>Normalized first-stage hybrid score.</span></div>
          <div><code>anchor_affinity</code><span>Strongest graph edge from this chunk to one of the preserved top hybrid anchors.</span></div>
          <div><code>support</code><span>Normalized weighted graph degree: how strongly the chunk is connected inside the candidate field.</span></div>
          <div><code>anchors</code><span>The strongest early hybrid candidates preserved at the front of the return set.</span></div>
          <div><code>top_5</code><span>The compact returned evidence set.</span></div>
        </div>
        <p class="say-it">
          The ablation result is direct: anchors alone equal hybrid, support-only
          graph ranking fails, and anchor-linked promotion is where the recall
          lift appears.
        </p>
        <img src="../assets/linked_ranking_illustration.svg" alt="Hybrid candidates become a graph; preserved anchors pull lower-ranked connected support chunks into the final compact return.">
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">4. Result</div>
      <div class="math-section">
        <h2>Return compact chunks.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            The result step turns graph reconciliation into caller-facing
            chunks. The production surface is intentionally small: a compact
            set of text and metadata for the caller or LLM.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            Applications call <code>chunks()</code>. The returned list follows
            the active production ranking policy and is already limited to the
            requested size.
          </p>
        </div>
        <pre>result.chunks(database, k=5)</pre>
        <div class="symbols">
          <div><code>result</code><span>The reconciliation result object returned by the pipeline.</span></div>
          <div><code>chunks</code><span>Method returning compact LLM-ready chunks from the active return policy.</span></div>
          <div><code>database</code><span>The document store used to materialize chunk text and metadata.</span></div>
          <div><code>k</code><span>Maximum number of chunks to return.</span></div>
          <div><code>5</code><span>The default compact return size used in the examples.</span></div>
        </div>
      </div>
    </article>

  </section>

  <section class="panel">
    <p class="eyebrow">Research path</p>
    <h2>Spectral diffusion is documented separately.</h2>
    <p>
      The diagnostic path is still part of the system, but it is not the
      benchmarked production selector. Read the Spectral Diffusion tab for the
      Laplacian, Fiedler vector, diffusion time steps, basin scoring, and
      uncertainty explanation.
    </p>
    <p><a href="../spectral_diffusion/">Open Spectral Diffusion</a></p>
  </section>
</div>
