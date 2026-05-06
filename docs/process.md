<div class="noetic-page">
  <section class="hero compact">
    <p class="eyebrow">Technical path</p>
    <h1>How Noetic Search turns retrieved chunks into a selected evidence basin.</h1>
    <p>
      The pipeline follows the implementation order:
      <code>candidates -> graph -> spectral -> whole-graph diffusion diagnostic -> basin diffusion -> basins -> uncertainty -> ranking -> result</code>.
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
            evidence connection from embedding similarity and near-duplicate
            signal. Metadata remains available on returned chunks, but it does
            not create graph edges.
          </p>
        </div>
        <p class="math-example">
          Two lower-ranked chunks can matter more together than two higher-ranked
          chunks that are isolated or repetitive.
        </p>
        <pre>A[i,j] = similarity_signal + duplicate_signal</pre>
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
            Subtract to build <code>L = D - A</code>, the combinatorial graph
            Laplacian. In production, Noetic uses the normalized graph
            Laplacian to reduce degree bias. Eigendecomposition uses that
            Laplacian to find the Fiedler vector, whose values propose basin
            boundaries.
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
            <h3>Build the Laplacian</h3>
            <p>
              <code>L = D - A</code> is called the combinatorial graph
              Laplacian. It is matrix construction: the result is not a finished
              separation and not a final disagreement score. It is the graph
              structure rewritten as a matrix that encodes how weighted neighbor
              disagreement should be measured.
            </p>
          </div>
          <div class="math-block">
            <h3>Use L</h3>
            <p>
              Eigendecomposition asks which value patterns are natural for this
              Laplacian. An eigenvector is a stable pattern for the matrix; its
              eigenvalue says how costly or unsmooth that pattern is on the
              graph. The smallest pattern is usually constant and does not split
              anything. The second-smallest pattern is the Fiedler vector. Its
              values give the first useful low-cost direction of separation, so
              splitting those values proposes fixed basin boundaries.
            </p>
          </div>
        </div>
        <pre>A = weighted edges
D[i,i] = total edge weight touching node i
L = D - A  (combinatorial graph Laplacian)
normalized Laplacian = degree-balanced version used for splitting
Fiedler vector = second-smallest eigenvector
split Fiedler values -> candidate regions</pre>
        <p class="say-it">
          Spectral detects basin boundaries. Diffusion does not create or redraw
          them.
        </p>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">4. Whole-Graph Diffusion</div>
      <div class="math-section">
        <h2>Let query energy move over the full graph.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            Hybrid rank should matter because retrieval did useful work, but it
            should not be final truth. Whole-graph diffusion asks where that
            retrieval signal wants to move when every graph edge is available.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            Each candidate receives initial energy from its retrieval score,
            discounted by rank and normalized to sum to <code>1.0</code>. At
            each time step, a node keeps some energy and passes the rest to
            neighbors in proportion to edge weight. Because cross-basin edges
            are still open, this diagnostic measures attraction, leakage, and
            absorption across the candidate field.
          </p>
        </div>
        <pre>raw_i = retrieval_score_i / (rank_i + 1)
energy_i = raw_i / sum(raw)
next_i = (1 - d) * energy_i
       + d * sum_j energy_j * A[j,i] / degree_j</pre>
        <p class="say-it">
          Whole-graph diffusion is diagnostic. It shows whether a basin absorbs
          or loses query energy before scoring keeps basins separate.
        </p>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">5. Basin Diffusion</div>
      <div class="math-section">
        <h2>Redistribute energy inside fixed spectral basins.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            Once competing regions are known, scoring should not let one
            explanation feed another. Cross-basin edges helped expose the
            structure, but final basin comparison should evaluate fixed regions.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            Remove edges whose endpoints belong to different spectral basins,
            then run the same time-step update inside each basin. Total energy
            is conserved per basin, so this step measures where support settles
            internally instead of moving energy between competitors.
          </p>
        </div>
        <pre>basin_graph = graph without cross-basin edges
basin_energy = diffuse(seed_energy, basin_graph)</pre>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">6. Basins</div>
      <div class="math-section">
        <h2>Score the fixed spectral basins.</h2>
        <div class="math-block">
          <h3>Intuition</h3>
          <p>
            Spectral proposed basin boundaries. Whole-graph diffusion shows
            attraction and leakage. Basin-constrained diffusion updates energy
            inside each fixed region. Basin scoring now chooses the strongest
            evidence region.
          </p>
        </div>
        <div class="math-block">
          <h3>Mechanics</h3>
          <p>
            Each fixed basin receives a score from settled energy, support,
            cohesion, and duplicate pressure. Support is capped, but it does
            not saturate immediately; a broader coherent region can beat a
            narrower region that received more initial hybrid energy.
          </p>
        </div>
        <pre>score = 0.45*energy + 0.25*support + 0.20*cohesion - duplicate_penalty</pre>
        <div class="symbols">
          <div><code>energy</code><span>Diffused retrieval signal settled inside the basin.</span></div>
          <div><code>support</code><span>Bounded count of chunks in the basin, saturated at the configured support limit.</span></div>
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
