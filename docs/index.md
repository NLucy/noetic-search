<div class="noetic-page">
  <section class="hero">
    <p class="eyebrow">Core thesis</p>
    <h1>Broad retrieval for recall. Graph reconciliation for precision.</h1>
    <p>
      Noetic Search is a post-retrieval reconciliation layer for hybrid search.
      Hybrid retrieval finds plausible candidates; Noetic builds a local graph,
      preserves strong retrieval anchors, and promotes graph-connected support
      chunks into a compact evidence set.
    </p>
  </section>

  <section class="grid two">
    <article>
      <h2>Standard Hybrid</h2>
      <pre>query -> hybrid search -> top 5 chunks -> LLM</pre>
      <p>
        The LLM receives raw rank. If the first five chunks are stale,
        repetitive, or shallow, the model has to repair retrieval inside the
        prompt.
      </p>
    </article>
    <article>
      <h2>Noetic Search</h2>
      <pre>query -> candidates
      -> graph
      -> linked-evidence ranking
      -> result -> LLM</pre>
      <p>
        The LLM receives a selected evidence surface, not a pile of nearest
        neighbors.
      </p>
    </article>
  </section>

  <section class="grid three">
    <article>
      <h2>What It Does</h2>
      <p>
        It turns a broad candidate field into a smaller, connected evidence set
        before the LLM sees the prompt.
      </p>
    </article>
    <article>
      <h2>What It Does Not Do</h2>
      <p>
        It does not replace vector search, BM25, rerankers, or LLM reasoning. It
        changes the step after candidate retrieval.
      </p>
    </article>
    <article>
      <h2>Current Signal</h2>
      <p>
        Focused ablations show that the lift comes from anchor-linked graph
        promotion. Hybrid finds strong entry points; Noetic promotes candidates
        connected to those anchors. Static graph defaults already improve
        hybrid, while corpus-native <code>auto</code> adds a smaller gain.
      </p>
    </article>
  </section>

  <section class="panel">
    <p class="eyebrow">Ablation result</p>
    <h2>The useful signal is anchor-linked promotion.</h2>
    <p>
      On the 100-case linked-production ablation across HotpotQA,
      2WikiMultiHopQA, and MuSiQue, raw hybrid averaged <code>0.738</code>
      recall across <code>@5</code> and <code>@10</code>. Static linked Noetic
      averaged <code>0.777</code>; auto-calibrated linked Noetic averaged
      <code>0.783</code>. Anchors alone matched hybrid, and support-only graph
      ranking fell to <code>0.501</code>.
    </p>
    <p>
      The production claim is therefore narrow: preserve first-stage hybrid
      anchors, then use the local graph to promote connected support chunks.
      Calibration remains useful configuration work, but it is not the main
      source of the measured lift.
    </p>
  </section>

  <section class="panel figure-panel">
    <p class="eyebrow">Benchmark signal</p>
    <h2>The auto path improves compact support recall in the headline run.</h2>
    <img src="assets/benchmark_summary.svg" alt="Bar chart comparing Hybrid and Noetic auto recall on HotpotQA, 2WikiMultiHopQA, and MuSiQue.">
  </section>

  <section class="panel">
    <p class="eyebrow">Ablation key</p>
    <h2>The ablation separates the mechanism from the surrounding graph.</h2>
    <p>
      The focused ablation compares mean support recall across <code>@5</code>
      and <code>@10</code>. Raw hybrid scores <code>0.738</code>.
      Auto-calibrated linked Noetic scores <code>0.783</code>, a 4.5
      percentage-point absolute gain and a 6.1% relative improvement over
      hybrid.
    </p>
    <pre>variant                 mean recall across @5/@10
hybrid                  0.738
linked_static           0.777
linked_auto             0.783
anchors_only            0.738
no_anchor_affinity      0.756
anchor_affinity_only    0.780
support_only            0.501
semantic_only           0.743
lexical_only            0.742</pre>
    <div class="symbols">
      <div><code>hybrid</code><span>Baseline hybrid ranking, with no Noetic reconciliation.</span></div>
      <div><code>linked_static</code><span>Anchor-linked graph ranking with fixed default graph weights.</span></div>
      <div><code>linked_auto</code><span>Anchor-linked graph ranking with corpus-calibrated graph weights.</span></div>
      <div><code>anchors_only</code><span>Preserved hybrid anchors only; tests whether the result is merely the original top hybrid hits.</span></div>
      <div><code>no_anchor_affinity</code><span>Graph ranking without the direct anchor-affinity term; tests whether generic graph structure is enough.</span></div>
      <div><code>anchor_affinity_only</code><span>Candidates ranked only by their strongest graph edge to a preserved hybrid anchor.</span></div>
      <div><code>support_only</code><span>Candidates ranked only by weighted graph degree; tests broad graph centrality by itself.</span></div>
      <div><code>semantic_only</code><span>Graph edges built from embedding similarity only.</span></div>
      <div><code>lexical_only</code><span>Graph edges built from lexical salience overlap only.</span></div>
    </div>
    <p>
      The pattern is the important part. Anchors alone reproduce hybrid.
      Support-only graph ranking performs poorly. The lift comes from promoting
      candidates connected to strong hybrid anchors.
    </p>
  </section>

  <section class="grid two">
    <article>
      <h2>Agreement</h2>
      <p>
        A relationship is strongest when semantic similarity and lexical
        salience both support it. Agreement edges are the preferred paths for
        promoting lower-ranked support chunks.
      </p>
    </article>
    <article>
      <h2>Tension</h2>
      <p>
        A relationship is riskier when semantic similarity is high but lexical
        anchoring is weak, or when surface overlap lacks conceptual fit. The
        graph tracks this as bridge risk rather than treating every neighbor as
        support.
      </p>
    </article>
  </section>

  <section class="panel">
    <p class="eyebrow">Return surfaces</p>
    <h2>One reconciliation result, multiple caller views.</h2>
    <div class="surface-list">
      <div><code>chunks()</code><span>Compact LLM-ready chunks from the linked-evidence return policy.</span></div>
      <div><code>strongest_basin()</code><span>The strongest diagnostic basin when diagnostics are requested.</span></div>
      <div><code>evidence_field()</code><span>The inspection field: linked return, optional basins, support edges, uncertainty, and graph metrics.</span></div>
    </div>
  </section>

  <section class="panel">
    <p class="eyebrow">Implementation</p>
    <h2>The core path is intentionally small.</h2>
    <pre>Database
  -> SemanticSearch + LexicalSearch
  -> HybridSearch
  -> Reconciler.reconcile()
  -> ReconciliationResult
  -> chunks()

optional diagnostics:
  -> strongest_basin() or evidence_field()</pre>
  </section>

  <section class="grid two">
    <article>
      <h2>The Math</h2>
      <p>
        The production path: candidates, graph construction, linked-evidence
        ranking, and result formatting.
      </p>
      <p><a href="process/">Open The Math</a></p>
    </article>
    <article>
      <h2>Evidence Graph</h2>
      <p>
        The relationship model: agreement edges, bridge risk, surface overlap
        risk, and redundancy pressure.
      </p>
      <p><a href="evidence_graph/">Open Evidence Graph</a></p>
    </article>
  </section>

  <section class="grid two">
    <article>
      <h2>Auto Calibration</h2>
      <p>
        The corpus-native process that selects frozen graph weights before
        query-time retrieval.
      </p>
      <p><a href="auto_calibration/">Open Auto Calibration</a></p>
    </article>
    <article>
      <h2>Spectral Diffusion</h2>
      <p>
        The diagnostic path: Laplacian splitting, diffusion time steps, basin
        scoring, uncertainty, and how this research path audits the graph.
      </p>
      <p><a href="spectral_diffusion/">Open Spectral Diffusion</a></p>
    </article>
  </section>

  <section class="grid two">
    <article>
      <h2>Production Trace</h2>
      <p>
        A real HotpotQA case where hybrid top-5 recovers one supporting
        paragraph and Noetic linked top-5 recovers both. This is the benchmarked
        path: candidates, graph, linked ranking, result.
      </p>
      <p><a href="trace/">Open the production trace</a></p>
    </article>
    <article>
      <h2>Diagnostic Trace</h2>
      <p>
        The same HotpotQA case viewed through spectral basins, whole-graph
        diffusion, basin-constrained diffusion, and basin scoring. This view
        uses the corpus-native <code>auto</code> graph formula so the same case
        exposes multiple diagnostic basins.
      </p>
      <p><a href="diagnostics_trace/">Open the diagnostic trace</a></p>
    </article>
  </section>
</div>
