<div class="noetic-page">
  <section class="hero compact">
    <p class="eyebrow">Research path</p>
    <h1>What spectral diffusion is for.</h1>
    <p>
      Spectral diffusion is the diagnostic and research path around the
      production graph. It audits, explains, and stress-tests the graph; it does
      not currently choose the <code>auto</code> graph weights or the default
      production chunks.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Current role</p>
    <h2>Spectral diffusion audits the graph; it does not currently choose production weights.</h2>
    <p>
      The production selector is the linked-evidence path: hybrid candidates,
      calibrated graph construction, linked ranking, and compact returned
      chunks. The <code>auto</code> graph parameters are chosen before query time
      from corpus-native graph-health measurements. Spectral diffusion is not
      the mechanism that derives those weights.
    </p>
    <p>
      Spectral diffusion remains in the system because it tells us whether the
      graph behaves like an evidence field. The spectral step proposes basin
      boundaries from the graph Laplacian and Fiedler vector. Whole-graph
      diffusion then shows where hybrid-seeded query energy moves when all
      edges remain available. Basin-constrained diffusion shows how that same
      energy settles after cross-basin edges are removed. Together, these views
      expose coherence, leakage, hub collapse, weak bridges, and ambiguous
      basin structure.
    </p>
    <p>
      In practical terms, spectral diffusion is used for diagnostics, trace
      explanation, basin-return research, and future calibration research. It
      helps answer: did the graph form useful regions, did energy concentrate
      in the same region the scorer selected, and does uncertainty need to rise
      because the graph pulled the query signal elsewhere?
    </p>
    <pre>current production:
  auto graph weights -> linked-evidence ranking -> chunks

current research/diagnostics:
  calibrated graph -> spectral basins -> diffusion -> basin scores -> uncertainty

future research question:
  should diffusion-health signals become part of graph calibration?</pre>
    <p class="say-it">
      Auto builds the current graph. Spectral diffusion audits, explains, and
      stress-tests that graph.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Why do diffusion?</p>
    <h2>Diffusion audits retrieval confidence after it meets the graph.</h2>
    <p>
      Linked ranking asks which chunks should be returned. Diffusion asks a
      different question: what happens to retrieval confidence when it is
      allowed to move through the evidence graph? That makes diffusion useful
      even when it is not the production selector.
    </p>
    <pre>linked ranking asks: which chunks should be returned?
diffusion asks: how does query energy behave on the graph?</pre>
    <div class="symbols">
      <div><code>concentration</code><span>Whether query energy settles around a coherent support region.</span></div>
      <div><code>leakage</code><span>Whether energy leaves one region through weak or ambiguous bridges.</span></div>
      <div><code>fragmentation</code><span>Whether support is split across multiple diagnostic regions.</span></div>
      <div><code>stability</code><span>Whether basin boundaries still make sense after energy is allowed to move.</span></div>
      <div><code>uncertainty</code><span>Whether the graph structure should make us cautious about a compact return.</span></div>
    </div>
    <p>
      In the current production system, diffusion is best understood as graph
      instrumentation. It shows whether the candidate graph behaves like a
      useful evidence field: support should move locally, weak bridges should
      reveal leakage, hubs should not absorb everything, and multi-hop evidence
      may legitimately cross basin boundaries.
    </p>
    <p class="say-it">
      Production uses linked ranking to return chunks. Diffusion explains how
      confidence moves, where it concentrates, and where the graph may be
      structurally uncertain.
    </p>
  </section>

  <section class="panel">
    <p class="eyebrow">Where diffusion fits</p>
    <h2>Diffusion uses the weighted graph; it does not currently derive the weights.</h2>
    <p>
      After a query, hybrid retrieval assigns each candidate a score and rank.
      The diagnostic diffusion path converts that into seed energy, then lets
      the energy move over the calibrated graph. This shows where the query
      signal settles, leaks, or concentrates. It is an inspection and
      basin-return mechanism, not the current production linked-evidence
      selector.
    </p>
    <pre>seed_energy_i = hybrid_score_i / (rank_i + 1)
weighted graph = graph built with frozen GraphWeights
diffusion = seed energy moving over weighted graph edges</pre>
  </section>

  <section class="math-path">
    <article class="math-item">
      <div class="math-tag">1. Spectral</div>
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
            Laplacian. In the diagnostic path, Noetic uses the normalized graph
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
        <div class="symbols">
          <div><code>A</code><span>Weighted adjacency matrix built from graph edges.</span></div>
          <div><code>D</code><span>Degree matrix. Its diagonal stores each node's total incident edge weight.</span></div>
          <div><code>D[i,i]</code><span>Total edge weight touching node i.</span></div>
          <div><code>i</code><span>The node index for one candidate chunk.</span></div>
          <div><code>L</code><span>Combinatorial graph Laplacian, built as <code>D - A</code>.</span></div>
          <div><code>normalized Laplacian</code><span>Degree-balanced Laplacian used by the implementation for spectral splitting.</span></div>
          <div><code>Fiedler vector</code><span>The second-smallest eigenvector of the normalized Laplacian; its values propose a low-cost split.</span></div>
          <div><code>candidate regions</code><span>The proposed spectral basins produced by splitting Fiedler values.</span></div>
        </div>
        <p class="say-it">
          Spectral detects basin boundaries. Diffusion does not create or redraw
          them.
        </p>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">2. Whole-Graph Diffusion</div>
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
        <div class="symbols">
          <div><code>raw_i</code><span>Unnormalized starting energy for chunk i.</span></div>
          <div><code>retrieval_score_i</code><span>Hybrid retrieval score for chunk i.</span></div>
          <div><code>rank_i</code><span>Zero-based hybrid rank for chunk i; adding 1 prevents division by zero.</span></div>
          <div><code>energy_i</code><span>Normalized current energy assigned to chunk i.</span></div>
          <div><code>sum(raw)</code><span>Total unnormalized seed energy across the candidate field.</span></div>
          <div><code>next_i</code><span>Energy assigned to chunk i at the next diffusion time step.</span></div>
          <div><code>d</code><span>Damping value: the fraction of energy allowed to move across edges at each time step.</span></div>
          <div><code>energy_j</code><span>Current energy on neighboring chunk j.</span></div>
          <div><code>A[j,i]</code><span>Edge weight from neighbor j into chunk i.</span></div>
          <div><code>degree_j</code><span>Total edge weight touching neighbor j.</span></div>
          <div><code>sum_j</code><span>Sum over all neighbors j that can pass energy to chunk i.</span></div>
        </div>
        <p class="say-it">
          Whole-graph diffusion is diagnostic. It shows whether a basin absorbs
          or loses query energy before scoring keeps basins separate.
        </p>
        <div class="math-block">
          <h3>Flow Alignment</h3>
          <p>
            After basin scoring, compare the whole-graph energy winner with the
            scored basin winner. If they agree, the diagnostic and scoring path
            point at the same region. If they disagree, the result is not
            automatically wrong, but uncertainty should rise because the full
            graph pulled query energy toward a different basin.
          </p>
        </div>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">3. Basin Diffusion</div>
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
        <div class="symbols">
          <div><code>basin_graph</code><span>The candidate graph after removing edges whose endpoints are in different spectral basins.</span></div>
          <div><code>graph</code><span>The full query-conditioned evidence graph over admitted candidates.</span></div>
          <div><code>cross-basin edges</code><span>Edges connecting chunks assigned to different spectral basins.</span></div>
          <div><code>basin_energy</code><span>Energy distribution after diffusion is constrained inside fixed basins.</span></div>
          <div><code>diffuse</code><span>The repeated time-step update that moves energy over weighted graph edges.</span></div>
          <div><code>seed_energy</code><span>The initial energy distribution derived from hybrid score and rank.</span></div>
        </div>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">4. Basins</div>
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
          <div><code>score</code><span>Final basin score used to choose the winning region.</span></div>
          <div><code>0.45</code><span>Current weight assigned to basin energy.</span></div>
          <div><code>0.25</code><span>Current weight assigned to bounded support.</span></div>
          <div><code>0.20</code><span>Current weight assigned to cohesion.</span></div>
          <div><code>energy</code><span>Diffused retrieval signal settled inside the basin.</span></div>
          <div><code>support</code><span>Bounded count of chunks in the basin, saturated at the configured support limit.</span></div>
          <div><code>cohesion</code><span>Mean internal edge strength.</span></div>
          <div><code>duplicate_penalty</code><span>Penalty for repeated evidence masquerading as support.</span></div>
        </div>
      </div>
    </article>

    <article class="math-item">
      <div class="math-tag">5. Uncertainty</div>
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
            modularity. The trace also reports flow alignment: whether
            whole-graph diffusion favored the same basin selected by
            basin-constrained scoring. It is not a truth probability; it is a
            structural caution signal.
          </p>
        </div>
        <pre>uncertainty = f(competition, dispersion, modularity)
flow_alignment = whole_graph_winner == scored_winner</pre>
        <div class="symbols">
          <div><code>f(...)</code><span>A bounded combination of the listed structural caution signals.</span></div>
          <div><code>competition</code><span>How close the runner-up basin score is to the winner. A close second means the field did not produce a decisive region.</span></div>
          <div><code>dispersion</code><span>How scattered the final basin-constrained energy remains across chunks. High dispersion means energy did not settle cleanly.</span></div>
          <div><code>modularity</code><span>How strongly the graph supports the detected basin partition compared with a degree-preserving baseline.</span></div>
          <div><code>flow_alignment</code><span>Whether whole-graph diffusion and basin-constrained scoring favor the same basin.</span></div>
          <div><code>whole_graph_winner</code><span>The basin with the most energy after whole-graph diffusion.</span></div>
          <div><code>scored_winner</code><span>The basin selected by basin-constrained scoring.</span></div>
        </div>
        <div class="math-block">
          <h3>How To Read It</h3>
          <p>
            Uncertainty rises when the winner barely beats another basin, when
            energy remains scattered instead of settling, when graph boundaries
            are weak, or when whole-graph diffusion points at a different basin
            than the scoring path. It is a warning about evidence-field
            structure, not a probability that the answer is false.
          </p>
        </div>
      </div>
    </article>
  </section>
</div>
