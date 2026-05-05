<div class="noetic-page">
  <section class="hero">
    <p class="eyebrow">Core thesis</p>
    <h1>Broad retrieval for recall. Graph reconciliation for precision.</h1>
    <p>
      Noetic Search is a post-retrieval reconciliation layer for hybrid search.
      Hybrid retrieval finds plausible candidates; Noetic builds a local graph,
      detects evidence basins, and returns representative chunks from the
      strongest basin.
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
      -> spectral
      -> diffusion
      -> basins
      -> uncertainty
      -> ranking
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
        It turns a broad candidate field into a smaller, coherent evidence
        region before the LLM sees the prompt.
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
        On the blind hard benchmark: standard hybrid top-5 is
        <strong>0/10</strong>; Noetic top-5 from hybrid top-50 is
        <strong>8/10</strong>.
      </p>
    </article>
  </section>

  <section class="panel">
    <p class="eyebrow">Return surfaces</p>
    <h2>One reconciliation result, multiple caller views.</h2>
    <div class="surface-list">
      <div><code>chunks()</code><span>Compact LLM-ready chunks from the winning basin.</span></div>
      <div><code>strongest_basin()</code><span>The winning basin with chunks, uncertainty, and metrics.</span></div>
      <div><code>evidence_field()</code><span>The inspection field: winner, competitors, support edges, uncertainty, and graph metrics.</span></div>
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
  -> chunks(), strongest_basin(), or evidence_field()</pre>
  </section>
</div>
