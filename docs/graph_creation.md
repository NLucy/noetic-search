<div class="noetic-page">
  <section class="hero compact">
    <p class="eyebrow">Step 2</p>
    <h1>Graph creation turns candidate chunks into weighted relationships.</h1>
    <p>
      After broad retrieval, each admitted chunk becomes a node. Edges describe
      whether two retrieved chunks can help form compact evidence.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Core distinction</p>
    <h2>The graph is not just nearest-neighbor similarity.</h2>
    <p>
      Vector similarity is useful, but closeness alone is not evidence. Two
      chunks can be close because they share a broad topic, repeat background,
      or use similar language while supporting different claims. Noetic treats
      an edge as a relationship signal, not merely a similarity score.
    </p>
    <pre>hybrid retrieval: which chunks match the query?
graph creation: which retrieved chunks support one another?</pre>
    <p>
      The graph is query-local. It is built over the admitted candidates for one
      query. It is not a permanent whole-corpus ontology and does not require
      special metadata labels.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Edge formula</p>
    <h2>One edge can combine several ordinary retrieval signals.</h2>
    <pre>A[i,j] =
  semantic_signal
+ lexical_signal
+ cross_reference_signal
+ duplicate_signal</pre>
    <div class="symbols">
      <div><code>A</code><span>The weighted adjacency matrix for the local candidate graph.</span></div>
      <div><code>A[i,j]</code><span>Relationship strength between candidate chunks i and j.</span></div>
      <div><code>semantic_signal</code><span>Embedding similarity contribution between the two chunks.</span></div>
      <div><code>lexical_signal</code><span>Shared salient word or phrase contribution after stop-word removal and local weighting.</span></div>
      <div><code>cross_reference_signal</code><span>Contribution added when one chunk explicitly names the title-like label of another chunk.</span></div>
      <div><code>duplicate_signal</code><span>Small near-duplicate contribution so repetition can later be detected and controlled.</span></div>
    </div>
  </section>

  <section class="grid two">
    <article>
      <h2>Agreement</h2>
      <p>
        Semantic similarity and lexical salience both support the relationship.
        Agreement edges are the preferred paths for promoting lower-ranked
        support chunks.
      </p>
      <pre>semantic high
+ lexical high
= grounded relationship</pre>
    </article>
    <article>
      <h2>Bridge Risk</h2>
      <p>
        Embeddings see a relationship, but the text gives little lexical
        grounding. This can find useful paraphrases, but it can also create weak
        bridges into off-chain material.
      </p>
      <pre>semantic high
+ lexical weak
= semantic-only bridge risk</pre>
    </article>
  </section>

  <section class="grid two">
    <article>
      <h2>Surface Overlap Risk</h2>
      <p>
        The chunks share words or phrases, but their meanings are not strongly
        aligned. This happens with ambiguous names, generic domain terms, and
        boilerplate.
      </p>
      <pre>lexical high
+ semantic weak
= surface overlap risk</pre>
    </article>
    <article>
      <h2>Redundancy Pressure</h2>
      <p>
        Near-duplicate chunks can make repeated evidence look like independent
        support. The graph records this pressure so repetition does not inflate
        the compact return.
      </p>
      <pre>near duplicate
= repeated evidence pressure</pre>
    </article>
  </section>

  <section class="panel">
    <p class="eyebrow">Key idea</p>
    <h2>The graph creates the relationships used by final selection.</h2>
    <p class="say-it">
      Final selection does not ask only whether a chunk matched the query. It
      also asks whether that chunk connects to strong retrieved anchors and has
      support inside the local graph.
    </p>
  </section>
</div>
