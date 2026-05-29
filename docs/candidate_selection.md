<div class="noetic-page">
  <section class="hero compact">
    <p class="eyebrow">Step 1</p>
    <h1>Candidate selection keeps recall broad before the graph does any work.</h1>
    <p>
      Noetic Search starts with ordinary hybrid retrieval. This is deliberate:
      the first stage should be good at recall, not forced to make the final
      compact decision.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Purpose</p>
    <h2>Hybrid retrieval creates the working field.</h2>
    <p>
      Hybrid search combines lexical and semantic retrieval. It returns a ranked
      list of plausible chunks for the query. Noetic does not replace this
      stage. It uses the broad list as the material for graph reconciliation.
    </p>
    <pre>query
  -> hybrid_search(query, pool=100)
  -> graph_candidates = top 30 hybrid results</pre>
    <div class="symbols">
      <div><code>query</code><span>The user's question or search request.</span></div>
      <div><code>hybrid_search</code><span>The first-stage retriever combining lexical and vector signals.</span></div>
      <div><code>candidate_limit</code><span>Number of chunks retrieved and admitted into the local graph. The common working value is 30.</span></div>
      <div><code>hybrid_pool_limit</code><span>Internal semantic and lexical channel depth used before hybrid scores are fused. The common value is 100 so score normalization is stable.</span></div>
      <div><code>graph_candidates</code><span>The actual local evidence field. These are the graph nodes.</span></div>
      <div><code>query_score</code><span>The original hybrid score for a chunk against the query. This is saved for final chunk scoring.</span></div>
    </div>
  </section>

  <section class="grid two">
    <article>
      <h2>Why Broad Retrieval</h2>
      <p>
        Raw top-5 retrieval can miss support that appears lower in the ranked
        list. A graph-sized candidate field gives Noetic enough material to
        recover that support before the final compact return is built.
      </p>
    </article>
    <article>
      <h2>Why Still Bounded</h2>
      <p>
        The graph is query-time work. Keeping the working field around 30 chunks
        makes pairwise graph construction small and auditable.
      </p>
    </article>
  </section>

  <section class="panel">
    <p class="eyebrow">Key idea</p>
    <h2>The first rank is an opinion, not the final answer.</h2>
    <p class="say-it">
      Candidate selection asks: which chunks are plausible enough to inspect
      together? Final selection happens later, after the graph has measured
      relationships among those chunks.
    </p>
  </section>
</div>
