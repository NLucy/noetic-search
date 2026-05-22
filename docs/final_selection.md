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
      and overall graph support.
    </p>
    <pre>final_chunk_score =
  0.50 * query_score
+ 0.35 * anchor_affinity
+ 0.15 * graph_support

top_5 = anchors + highest final_chunk_score chunks</pre>
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
      The focused ablation uses 100 validation cases each from HotpotQA,
      2WikiMultiHopQA, and MuSiQue. It tests which scoring terms matter.
    </p>
    <pre>variant                       mean recall across @5/@10
Hybrid baseline               0.738
Noetic static weights         0.777
Noetic auto weights           0.783
Anchors only                  0.738
No anchor-link term           0.756
Anchor-link only              0.780
Graph support only            0.501
Semantic edges only           0.743
Lexical edges only            0.742</pre>
    <div class="symbols">
      <div><code>Hybrid baseline</code><span>Raw hybrid ranking, with no Noetic graph reconciliation.</span></div>
      <div><code>Noetic static weights</code><span>Production final chunk scoring with fixed default graph weights.</span></div>
      <div><code>Noetic auto weights</code><span>Production final chunk scoring with graph weights calibrated from the corpus before query time.</span></div>
      <div><code>Anchors only</code><span>Return only the preserved top hybrid anchors; tests whether Noetic is merely copying the original top hits.</span></div>
      <div><code>No anchor-link term</code><span>Remove the term that rewards a chunk for connecting to a preserved anchor.</span></div>
      <div><code>Anchor-link only</code><span>Rank candidates only by their strongest graph edge to a preserved hybrid anchor.</span></div>
      <div><code>Graph support only</code><span>Rank candidates only by weighted graph degree; tests broad graph centrality by itself.</span></div>
      <div><code>Semantic edges only</code><span>Build graph edges from embedding similarity only.</span></div>
      <div><code>Lexical edges only</code><span>Build graph edges from lexical salience overlap only.</span></div>
    </div>
    <p class="say-it">
      Anchors alone reproduce hybrid. Graph support alone performs poorly.
      Removing the anchor-link term hurts. The measured lift comes from
      promoting candidates connected to strong hybrid anchors.
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
