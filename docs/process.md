<div class="noetic-page">
  <section class="hero compact">
    <p class="eyebrow">Technical path</p>
    <h1>How Noetic Search turns retrieved chunks into a selected evidence basin.</h1>
    <p>
      The pipeline follows the implementation order:
      <code>candidates -> graph -> spectral -> seeding -> diffusion -> basins -> uncertainty -> ranking -> result</code>.
      Each step has a narrow mathematical role and a concrete artifact.
    </p>
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
            evidence connection from embedding similarity, ordinary metadata
            when present, and near-duplicate signal.
          </p>
        </div>
        <p class="math-example">
          Two lower-ranked chunks can matter more together than two higher-ranked
          chunks that are isolated or repetitive.
        </p>
        <pre>A[i,j] = similarity_signal + metadata_signal + duplicate_signal</pre>
        <div class="symbols">
          <div><code>A</code><span>Weighted adjacency matrix.</span></div>
          <div><code>A[i,j]</code><span>Relationship strength between chunks i and j.</span></div>
          <div><code>i, j</code><span>Candidate chunk nodes in the local graph.</span></div>
        </div>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">3. Spectral</div>
      <div class="math-section">
        <h2>Detect basin boundaries with the Laplacian and Fiedler vector.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            Spectral detection turns the weighted graph into a matrix that can
            reveal natural regions. The subtraction does not produce a finished
            disagreement score. It builds the matrix used to find a low-cost
            split.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            Build <code>A</code>, the weighted adjacency matrix. Build
            <code>D</code>, whose diagonal stores total edge weight per node.
            Subtract to build <code>L = D - A</code>. Eigendecomposition uses
            <code>L</code> to find the Fiedler vector, whose values propose
            basin boundaries.
          </p>
        </div>
        <div class="deep-dive">
          <div class="math-block">
            <h3>Build A</h3>
            <p>
              <code>A</code> stores pairwise chunk relationships. If two chunks
              have edge weight <code>0.70</code>, that strength is stored in the
              matrix. If no edge exists, the entry is <code>0</code>.
            </p>
          </div>
          <div class="math-block">
            <h3>Build D</h3>
            <p>
              <code>D</code> stores total connection weight on the diagonal. If
              a node connects to neighbors with weights <code>10</code>,
              <code>5</code>, and <code>10</code>, its degree value is
              <code>25</code>.
            </p>
          </div>
          <div class="math-block">
            <h3>Build L</h3>
            <p>
              <code>L = D - A</code> is matrix construction. It encodes the rule
              for measuring weighted neighbor disagreement later; it is not
              itself a final disagreement score.
            </p>
          </div>
          <div class="math-block">
            <h3>Use L</h3>
            <p>
              Eigendecomposition finds graph-native value patterns. The Fiedler
              vector is the first useful nontrivial pattern. Splitting its
              values proposes fixed basin boundaries.
            </p>
          </div>
        </div>
        <pre>A = weighted edges
D[i,i] = total edge weight touching node i
L = D - A
Fiedler vector = second-smallest eigenvector of L
split Fiedler values -> candidate regions</pre>
        <p class="say-it">
          Spectral detects basin boundaries. Diffusion does not create or redraw
          them.
        </p>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">4. Seeding</div>
      <div class="math-section">
        <h2>Turn retrieval rank into energy for diffusion.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            Hybrid rank should matter because retrieval did useful work, but it
            should not be final truth. Seeding converts rank and score into the
            starting energy vector.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            Each candidate receives seed energy from its retrieval score,
            discounted by rank. The seed vector is normalized to sum to
            <code>1.0</code>.
          </p>
        </div>
        <pre>seed_i = retrieval_score_i / (rank_i + 1)
energy = seed / sum(seed)</pre>
        <p class="say-it">Seeding creates the energy vector; diffusion uses it immediately.</p>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">5. Diffusion</div>
      <div class="math-section">
        <h2>Redistribute seeded energy over the fixed graph.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            Diffusion asks where retrieval confidence settles after moving
            through evidence relationships. A supported lower-ranked chunk can
            rise; an isolated high-ranked decoy can lose dominance.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            At each time step, a node keeps some energy and passes the rest to
            neighbors in proportion to edge weight. The energy is normalized
            after each step.
          </p>
        </div>
        <pre>next_i = (1 - d) * energy_i
       + d * sum_j energy_j * A[j,i] / degree_j</pre>
        <p class="say-it">
          Diffusion updates node energy. It does not detect basin boundaries.
        </p>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">6. Basins</div>
      <div class="math-section">
        <h2>Score the fixed spectral basins.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            Spectral already proposed the basin boundaries. Diffusion updated
            energy on nodes. Basin scoring now chooses the strongest fixed
            region.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            Each fixed basin receives a score from settled energy, support,
            cohesion, and duplicate pressure.
          </p>
        </div>
        <pre>score = energy + support + cohesion - duplicate_penalty</pre>
        <div class="symbols">
          <div><code>energy</code><span>Diffused retrieval signal settled inside the basin.</span></div>
          <div><code>support</code><span>Enough useful chunks to represent an evidence position.</span></div>
          <div><code>cohesion</code><span>Mean internal edge strength.</span></div>
          <div><code>duplicate_penalty</code><span>Penalty for repeated evidence masquerading as support.</span></div>
        </div>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">7. Uncertainty</div>
      <div class="math-section">
        <h2>Measure whether the basin decision was clean.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            A winning basin is more useful when it wins clearly. Uncertainty
            reports structural risk in the candidate field.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            The score combines basin competition, energy dispersion, and
            modularity. It is not a truth probability; it is a structural
            caution signal.
          </p>
        </div>
        <pre>uncertainty = f(competition, dispersion, modularity)</pre>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">8. Ranking</div>
      <div class="math-section">
        <h2>Choose representatives inside the winning basin.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            The basin chooses the concept. Ranking chooses the best chunks to
            represent that concept in a compact LLM payload.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            Ranking happens only inside the winning basin. The default ordering
            favors specificity, with settled energy as a supporting signal.
          </p>
        </div>
        <pre>top_5 = rank_chunks(winning_basin, specificity + energy)</pre>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">9. Result</div>
      <div class="math-section">
        <h2>Expose chunks or the inspection field.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            The result step turns internal graph reconciliation into caller-facing
            surfaces.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            Applications can request compact chunks, the strongest basin payload,
            or the full evidence field with competitors and uncertainty.
          </p>
        </div>
        <pre>result.chunks(database, k=5)
result.strongest_basin(database)
result.evidence_field()</pre>
      </div>
    </article>
  </section>
</div>
