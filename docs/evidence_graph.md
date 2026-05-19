<div class="noetic-page">
  <section class="hero compact">
    <p class="eyebrow">Evidence graph</p>
    <h1>The graph is not a similarity graph. It is a relationship filter.</h1>
    <p>
      Noetic Search builds a query-local graph after hybrid retrieval. Each
      retrieved chunk is a node. Edges are created from retrieval-native signals
      that say whether two chunks can help form compact evidence.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Core distinction</p>
    <h2>An edge should mean more than closeness.</h2>
    <p>
      Vector similarity is useful, but closeness alone is not evidence. Two
      chunks can be semantically near because they share a topic, because one is
      generic background, or because they sit near the same broad concept while
      supporting different claims. Noetic therefore treats an edge as a
      structured relationship, not merely a nearest-neighbor score.
    </p>
    <pre>hybrid retrieval: which chunks match the query?
evidence graph: which retrieved chunks support one another?</pre>
    <p>
      The graph is query-local. It is built over the admitted candidates for one
      query, usually the first 30 chunks from a broader hybrid top-50 retrieval.
      It is not a permanent whole-corpus ontology and does not require special
      metadata labels.
    </p>
  </section>

  <section class="grid two">
    <article>
      <h2>Agreement Edge</h2>
      <p>
        Semantic similarity and lexical salience both support the relationship.
        This is the preferred edge type for compact evidence promotion.
      </p>
      <pre>semantic high
+ lexical high
= grounded relationship</pre>
    </article>
    <article>
      <h2>Bridge Risk</h2>
      <p>
        Embeddings see a relationship, but the text does not provide much
        lexical grounding. This can find useful paraphrases, but it can also
        create weak bridges into plausible off-chain material.
      </p>
      <pre>semantic high
+ lexical weak
= possible semantic-only bridge</pre>
    </article>
  </section>

  <section class="grid two">
    <article>
      <h2>Surface Overlap Risk</h2>
      <p>
        The chunks share words or phrases, but their meanings are not strongly
        aligned. This happens with ambiguous names, generic domain terms, and
        broad boilerplate.
      </p>
      <pre>lexical high
+ semantic weak
= surface overlap risk</pre>
    </article>
    <article>
      <h2>Redundancy Pressure</h2>
      <p>
        Near-duplicate chunks can make repeated evidence look like independent
        support. Noetic records this pressure so repetition does not inflate the
        value of a region.
      </p>
      <pre>near duplicate
= repeated evidence pressure</pre>
    </article>
  </section>

  <section class="panel">
    <p class="eyebrow">Signal channels</p>
    <h2>The implementation uses ordinary text and embeddings.</h2>
    <div class="symbols">
      <div><code>semantic_signal</code><span>Embedding cosine similarity between two retrieved chunks.</span></div>
      <div><code>lexical_signal</code><span>Overlap of salient terms and phrases after stop-word removal and local weighting.</span></div>
      <div><code>cross_reference_signal</code><span>Whether one chunk explicitly names the title-like label of another chunk.</span></div>
      <div><code>duplicate_signal</code><span>Whether the chunks are similar enough to behave like repeated evidence.</span></div>
    </div>
    <pre>A[i,j] =
  semantic_signal
+ lexical_signal
+ cross_reference_signal
+ duplicate_signal</pre>
    <p>
      The final adjacency weight is capped so one pair cannot become absolute
      simply because several signals fire. The resulting graph is the structure
      used by linked-evidence ranking and, when requested, spectral/diffusion
      diagnostics.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Production use</p>
    <h2>Linked ranking uses the graph without replacing hybrid retrieval.</h2>
    <p>
      The production path keeps the strongest hybrid anchors. Then it promotes
      lower-ranked candidates when they are strongly connected to those anchors
      and have local graph support. This lets a compact top-5 return include
      supporting chunks that raw hybrid top-5 may miss.
    </p>
    <pre>linked_score =
  0.50 * query_score
+ 0.35 * anchor_affinity
+ 0.15 * graph_support</pre>
    <div class="symbols">
      <div><code>query_score</code><span>Original hybrid retrieval score.</span></div>
      <div><code>anchor_affinity</code><span>Strongest graph edge to one of the preserved hybrid anchors.</span></div>
      <div><code>graph_support</code><span>How strongly the chunk is connected inside the local candidate graph.</span></div>
    </div>
    <p>
      The production ablation supports this design. Anchors alone reproduce
      hybrid. Graph support alone performs poorly. The lift comes from
      anchor-linked promotion: candidates connected to strong hybrid anchors
      move up without discarding the first-stage ranking signal.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">How to say it</p>
    <h2>The graph separates relationship quality from raw similarity.</h2>
    <p class="say-it">
      Noetic does not ask only whether a chunk is close to the query. It asks
      whether retrieved chunks form grounded support relationships with one
      another. Semantic and lexical agreement create trusted edges; disagreement
      between channels exposes bridge risk, surface overlap risk, and redundancy
      pressure.
    </p>
  </section>
</div>
