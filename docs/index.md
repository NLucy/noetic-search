<div class="noetic-page">
  <section class="hero">
    <p class="eyebrow">Core thesis</p>
    <h1>Broad retrieval for recall. Graph reconciliation for precision.</h1>
    <p>
      Noetic Search is a post-retrieval reconciliation layer for hybrid search.
      Hybrid retrieval finds a broad candidate field. Noetic turns that field
      into a compact evidence return before the LLM sees the prompt.
    </p>
  </section>

  <section class="grid three">
    <article>
      <h2>The Move</h2>
      <p>
        Preserve the strongest hybrid anchors, then promote lower-ranked chunks
        that remain query-relevant and connect to those anchors.
      </p>
    </article>
    <article>
      <h2>The Boundary</h2>
      <p>
        It does not replace vector search, BM25, rerankers, or LLM reasoning. It
        changes the step after candidate retrieval.
      </p>
    </article>
    <article>
      <h2>The Claim</h2>
      <p>
        The measured lift comes from anchor-linked promotion, not generic graph
        centrality or a hidden tuned formula.
      </p>
    </article>
  </section>

  <section class="panel figure-panel">
    <p class="eyebrow">Benchmark summary</p>
    <h2>Noetic improves compact support recall in the headline run.</h2>
    <img src="assets/benchmark_summary.svg" alt="Bar chart comparing Hybrid and Noetic protected three-anchor recall on HotpotQA, 2WikiMultiHopQA, and MuSiQue.">
    <p>
      On the benchmark summary, Noetic with 3 protected anchors improved mean
      recall from <code>0.733</code> to <code>0.764</code> across
      <code>@5/@10</code>: a 3.0 percentage-point absolute gain, or a 4.1%
      relative improvement over hybrid.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Ablation summary</p>
    <h2>The ablation supports the mechanism.</h2>
    <p>
      The focused ablation uses validation cases from HotpotQA,
      2WikiMultiHopQA, and MuSiQue. Anchors alone reproduce hybrid. Graph
      support alone performs poorly. Open graph ranking hurts early precision.
      Protected anchors improve compact recall.
    </p>
    <pre>variant                       mean R@5 across datasets
Hybrid baseline               0.687
3 protected anchors           0.723
4 protected anchors           0.720
2 protected anchors           0.718
Open 3-anchor ranking         0.686

variant                       mean R@10 across datasets
Hybrid baseline               0.780
3 protected anchors           0.804
4 protected anchors           0.806
5 protected anchors           0.807</pre>
    <p>
      The detailed story is split into the step pages below.
    </p>
  </section>

  <section class="grid two">
    <article>
      <h2>Candidate Selection</h2>
      <p>
        How broad hybrid retrieval creates the working field before graph
        reconciliation.
      </p>
      <p><a href="candidate_selection/">Open Candidate Selection</a></p>
    </article>
    <article>
      <h2>Graph Creation</h2>
      <p>
        How retrieved chunks become nodes and how ordinary text and embedding
        signals become edges.
      </p>
      <p><a href="graph_creation/">Open Graph Creation</a></p>
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
      <h2>Final Selection</h2>
      <p>
        How anchors are preserved, non-anchor chunks are scored, and the final
        compact return is selected.
      </p>
      <p><a href="final_selection/">Open Final Selection</a></p>
    </article>
  </section>

  <section class="grid two">
    <article>
      <h2>Spectral Diffusion</h2>
      <p>
        The diagnostic path: Laplacian splitting, diffusion time steps, basin
        scoring, uncertainty, and how this research path audits the graph.
      </p>
      <p><a href="spectral_diffusion/">Open Spectral Diffusion</a></p>
    </article>
    <article>
      <h2>Production Trace</h2>
      <p>
        A real HotpotQA case where hybrid top-5 recovers one supporting
        paragraph and Noetic top-5 recovers both. This is the benchmarked path:
        candidates, graph, final chunk scoring, result.
      </p>
      <p><a href="trace/">Open the production trace</a></p>
    </article>
  </section>

  <section class="grid two">
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
