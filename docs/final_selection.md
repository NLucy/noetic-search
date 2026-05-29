<div class="noetic-page">
  <section class="hero compact">
    <p class="eyebrow">Step 4</p>
    <h1>Final selection preserves anchors and scores the remaining chunks.</h1>
    <p>
      This is the production decision step. Anchors keep the strongest hybrid
      hits. The remaining candidates compete by final chunk score.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Mechanism</p>
    <h2>Each non-anchor candidate receives a final chunk score.</h2>
    <p>
      The score has three terms: direct query match, strongest edge to an anchor,
      and overall graph support. The default top-5 policy protects 3 hybrid
      anchors, leaving 2 compact-return slots for graph-promoted support.
    </p>
    <pre>final_chunk_score =
  0.50 * query_score
+ 0.35 * anchor_affinity
+ 0.15 * graph_support

top_5 = 3 protected anchors + 2 highest final_chunk_score chunks</pre>
    <div class="symbols">
      <div><code>final_chunk_score</code><span>The score used to decide which non-anchor chunks enter the compact return.</span></div>
      <div><code>query_score</code><span>Normalized first-stage hybrid score: how well this chunk directly matched the query.</span></div>
      <div><code>anchor_affinity</code><span>Strongest graph edge from this chunk to one of the preserved top hybrid anchors.</span></div>
      <div><code>graph_support</code><span>Normalized weighted graph degree: how strongly this chunk is connected inside the candidate field.</span></div>
      <div><code>anchors</code><span>The strongest early hybrid candidates preserved at the front of the return set.</span></div>
      <div><code>top_5</code><span>The compact returned evidence set.</span></div>
    </div>
  </section>

  <section class="panel figure-panel">
    <p class="eyebrow">Illustration</p>
    <h2>Lower-ranked support can move into the final return.</h2>
    <img src="../assets/linked_ranking_illustration.svg" alt="Hybrid candidates become a graph; preserved anchors pull lower-ranked connected support chunks into the final compact return.">
  </section>

  <section class="grid two">
    <article>
      <h2>What Moves Up</h2>
      <p>
        A lower-ranked chunk can move up when it still matches the query and has
        a strong graph edge to one of the preserved anchors.
      </p>
    </article>
    <article>
      <h2>What Falls Out</h2>
      <p>
        A chunk can fall out when it is isolated, repetitive, or only weakly
        connected to the anchor evidence.
      </p>
    </article>
  </section>

  <section class="panel">
    <p class="eyebrow">Ablation</p>
    <h2>The useful signal is anchor-linked promotion.</h2>
    <p>
      The focused ablation uses validation cases from HotpotQA,
      2WikiMultiHopQA, and MuSiQue. It tests whether anchors should be
      protected and how many anchors are useful.
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
    <div class="symbols">
      <div><code>Hybrid baseline</code><span>Raw hybrid ranking, with no Noetic graph reconciliation.</span></div>
      <div><code>Protected anchors</code><span>Keep the strongest hybrid candidates at the front, then fill remaining slots with graph-ranked support.</span></div>
      <div><code>Open ranking</code><span>Use anchors to define affinity, but allow every chunk to compete under the score formula. This usually hurts compact precision.</span></div>
      <div><code>3 protected anchors</code><span>The strongest observed top-5 policy in the anchor-count sweep.</span></div>
    </div>
    <p class="say-it">
      Anchor protection is not cosmetic. Open graph ranking lets connected
      chunks push out direct query matches and usually damages early precision.
      The measured top-5 lift comes from protecting 3 direct hybrid anchors and
      using the graph to choose 2 supporting chunks.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Output</p>
    <h2>The caller receives compact chunks.</h2>
    <pre>result.chunks(database, k=5)</pre>
    <p>
      The returned list is small enough for an LLM prompt or reviewer workflow,
      but it has been selected from a broader candidate field.
    </p>
  </section>
</div>
