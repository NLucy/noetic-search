<div class="noetic-page trace-viewer">
  <section class="hero compact">
    <p class="eyebrow">Diagnostic trace</p>
    <h1>Inspect the spectral and diffusion research path.</h1>
    <p>
      Generate the diagnostic trace with
      <code>uv run noetic trace --calibrate-graph --graph-objective auto --output docs/diagnostics_trace.json</code>,
      then serve the docs. The browser renders the same real HotpotQA candidate
      field used by the Production Trace, but with the corpus-native
      <code>auto</code> graph formula enabled for diagnostics. This exposes
      graph edges, spectral basins, diffusion energy, and basin scores. This is
      not the benchmarked production selector; it is the research instrument for
      understanding graph behavior.
    </p>
    <p>
      This trace intentionally uses the same HotpotQA Big Stone Gap case as the
      Production Trace. The diagnostic knob is graph calibration, not a forced
      visual split: <code>auto</code> derives graph weights from corpus structure
      before query labels are evaluated. Under those calibrated edges, the same
      candidate field separates into multiple diagnostic basins.
    </p>
  </section>

  <div class="trace-controls" aria-label="Trace steps">
    <button id="tracePrev" class="trace-nav-button" type="button">Previous</button>
    <div class="trace-step-buttons" id="traceStepButtons"></div>
    <input
      id="traceSlider"
      class="trace-slider"
      type="range"
      min="0"
      max="7"
      value="0"
      step="1"
      aria-label="Trace step"
    />
    <button id="traceNext" class="trace-nav-button" type="button">Next</button>
  </div>

  <section class="trace-shell">
    <div class="trace-stage">
      <div class="trace-stage-head">
        <div>
          <p id="traceKicker" class="trace-kicker">1 / 8</p>
          <h2 id="traceStageTitle">Corpus field</h2>
          <p id="traceQuery" class="trace-query">Query loading</p>
        </div>
        <div id="traceStageMetric" class="trace-stage-metric">Loading trace</div>
      </div>
      <div class="trace-canvas-wrap">
        <div class="trace-zoom-controls" aria-label="Graphic zoom">
          <button id="traceZoomOut" class="trace-zoom-button" type="button" aria-label="Zoom out">-</button>
          <input
            id="traceZoomSlider"
            class="trace-zoom-slider"
            type="range"
            min="1"
            max="4"
            value="1"
            step="0.25"
            aria-label="Graphic zoom level"
          />
          <button id="traceZoomIn" class="trace-zoom-button" type="button" aria-label="Zoom in">+</button>
          <button id="traceZoomReset" class="trace-zoom-reset" type="button">Reset</button>
          <span id="traceZoomReadout" class="trace-zoom-readout">100%</span>
        </div>
        <div id="traceDiffusionControls" class="trace-diffusion-controls" aria-label="Diffusion time step">
          <button id="traceDiffusionPlay" class="trace-diffusion-button" type="button">Pause</button>
          <input
            id="traceDiffusionSlider"
            class="trace-diffusion-slider"
            type="range"
            min="0"
            max="4"
            value="0"
            step="1"
            aria-label="Diffusion time step"
          />
          <span id="traceDiffusionReadout" class="trace-diffusion-readout">t=0</span>
        </div>
        <canvas id="traceCanvas" width="1200" height="760"></canvas>
        <div id="traceTooltip" class="trace-tooltip" role="status"></div>
      </div>
      <div id="traceLegend" class="trace-legend"></div>
      <div id="traceScorePanel" class="trace-score-panel"></div>
    </div>
    <div class="trace-copy">
      <article class="trace-step" data-step="corpus">
        <p class="eyebrow">1. Corpus Field</p>
        <h2>Start with the local benchmark corpus sample.</h2>
        <p>
          Each point is a chunk in the available corpus sample. This first view
          is intentionally neutral: it shows the field before retrieval,
          graphing, or spectral basin detection imposes structure.
        </p>
      </article>
      <article class="trace-step" data-step="hybrid">
        <p class="eyebrow">2. Hybrid Retrieval</p>
        <h2>Highlight the broad first-stage candidates.</h2>
        <p>
          Hybrid search retrieves the top candidates for recall. The first five
          are shown separately because that is the standard RAG baseline.
        </p>
      </article>
      <article class="trace-step" data-step="graph">
        <p class="eyebrow">3. Graph</p>
        <h2>Connect admitted candidates with weighted evidence edges.</h2>
        <p>
          The graph is built from embedding similarity, lexical salience,
          explicit cross-reference, and near-duplicate signal. Ordinary
          metadata remains payload only; it does not create graph edges.
        </p>
        <p>
          Some admitted candidates may have no visible edge. That means hybrid
          retrieval brought them into the field, but no relationship cleared the
          graph threshold.
        </p>
      </article>
      <article class="trace-step" data-step="spectral">
        <p class="eyebrow">4. Spectral Basins</p>
        <h2>Use the normalized Laplacian and Fiedler split.</h2>
        <p>
          Spectral detection proposes fixed basin boundaries. Diffusion will use
          those assignments, not redraw them.
        </p>
        <p>
          In this HotpotQA trace, the admitted candidates are graphed with
          corpus-native <code>auto</code> weights. The normalized Laplacian now
          finds multiple low-cost regions inside the same candidate field. This
          is the honest knob: change the graph formula, then let spectral
          detection report whether the graph separates.
        </p>
      </article>
      <article class="trace-step" data-step="whole-diffusion">
        <p class="eyebrow">5. Whole-Graph Diffusion</p>
        <h2>Let retrieval energy move across the full graph.</h2>
        <p>
          This is a diagnostic step, not the production selector. Linked
          ranking asks which chunks should be returned. Diffusion asks how the
          hybrid retrieval signal behaves after it meets the graph.
        </p>
        <p>
          Whole-graph diffusion can reveal attraction, leakage, or absorption
          across the candidate field. Because the calibrated graph has multiple
          basins, this view shows whether energy remains in its seeded region or
          leaks into another diagnostic region before cross-basin edges are
          removed.
        </p>
      </article>
      <article class="trace-step" data-step="diffusion">
        <p class="eyebrow">6. Basin-Constrained Diffusion</p>
        <h2>Redistribute energy inside fixed basins.</h2>
        <p>
          This is the scoring diffusion path.
          Point size follows absolute seeded energy at the captured diffusion
          time step. Energy starts from hybrid rank and score, then moves
          through same-basin graph relationships.
        </p>
        <p>
          Because cross-basin edges are removed before diffusion, total basin
          energy is conserved. Diffusion does not move one basin's energy into
          another. It redistributes energy inside each fixed basin, which matters
          for representative chunks and for seeing whether support concentrates
          or stays scattered.
        </p>
        <p>
          This step tests how the hybrid signal behaves after it meets the graph.
          A high-rank chunk that is isolated stays thin. A lower-rank chunk can
          become more important when neighboring chunks also support it. Unlike
          whole-graph diffusion, this version keeps the basin competition fixed
          so final scoring does not reward one basin for draining another.
        </p>
      </article>
      <article class="trace-step" data-step="basins">
        <p class="eyebrow">7. Basin Scoring</p>
        <h2>Select the strongest evidence region.</h2>
        <p>
          The winning basin balances settled energy, support, cohesion, duplicate
          pressure, and uncertainty.
        </p>
        <p>
          The score is computed from the basin totals: settled energy, support,
          internal cohesion, and duplicate pressure. The panel under the graphic
          shows whether the winner was already the hybrid seed-energy winner or
          whether graph structure changed the decision.
        </p>
        <p>
          Basin selection does not have to coincide exactly with the production
          linked return. In this HotpotQA trace, the calibrated graph separates
          the two supporting paragraphs into different diagnostic basins. That
          means the graph sees distinct local regions inside the evidence chain,
          not that one support paragraph should be discarded.
        </p>
        <p>
          If a future real trace produces multiple basins, a lower-seed basin
          should only win when it clears a stricter standard: enough query energy
          to remain relevant, strong internal cohesion, non-duplicate support,
          and returned chunks that preserve the broader explanation. Size alone
          is not a sufficient reason.
        </p>
      </article>
      <article class="trace-step" data-step="final">
        <p class="eyebrow">8. Final Return</p>
        <h2>Compare basin diagnostics with the linked return.</h2>
        <p>
          The green numbered chunks are the production linked-evidence return.
          They are not required to come from one diagnostic basin. Production
          ranking preserves strong hybrid anchors and promotes graph-connected
          support chunks, even when spectral diagnostics split those chunks into
          different regions.
        </p>
        <p>
          In this trace, basin scoring selects the strongest single diagnostic
          region, but the linked return spans basins and recovers both HotpotQA
          support paragraphs. That is a useful signal: the answer is a
          multi-hop bridge, while the spectral diagnostic sees separable local
          neighborhoods around parts of that bridge.
        </p>
        <p>
          If basin selection and linked return agree, the graph is telling a
          compact single-region story. If they differ, as they do here, the
          diagnostic is telling us the evidence chain crosses regions. That is
          not automatically bad; it is exactly the kind of structure the linked
          return is meant to preserve.
        </p>
      </article>
    </div>
  </section>
</div>

<style>
  .trace-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
    gap: 28px;
    align-items: start;
    margin-top: 18px;
  }

  .trace-controls {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 12px;
    align-items: center;
    margin-top: 32px;
    padding: 14px;
    border: 1px solid rgba(20, 24, 28, 0.12);
    border-radius: 8px;
    background: #fffdf8;
    box-shadow: 0 12px 32px rgba(20, 24, 28, 0.07);
  }

  .trace-step-buttons {
    display: grid;
    grid-template-columns: repeat(8, minmax(0, 1fr));
    gap: 8px;
  }

  .trace-step-button,
  .trace-nav-button {
    min-height: 42px;
    border: 1px solid rgba(20, 24, 28, 0.14);
    border-radius: 6px;
    background: #ffffff;
    color: #16201d;
    font: inherit;
    font-size: 13px;
    font-weight: 700;
    line-height: 1.1;
    cursor: pointer;
  }

  .trace-step-button {
    display: grid;
    place-items: center;
    padding: 8px 6px;
  }

  .trace-step-button.active,
  .trace-nav-button:hover,
  .trace-step-button:hover {
    border-color: rgba(4, 120, 87, 0.42);
    background: #e7f5ef;
    color: #064e3b;
  }

  .trace-nav-button:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }

  .trace-slider {
    grid-column: 1 / -1;
    width: 100%;
    accent-color: #047857;
  }

  .trace-stage {
    min-height: 72vh;
    border: 1px solid rgba(20, 24, 28, 0.14);
    border-radius: 8px;
    background: #fffdf8;
    overflow: hidden;
    box-shadow: 0 18px 40px rgba(20, 24, 28, 0.08);
  }

  .trace-stage-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    min-height: 92px;
    padding: 18px 20px 16px;
    border-bottom: 1px solid rgba(20, 24, 28, 0.1);
  }

  .trace-kicker {
    margin: 0 0 4px;
    color: #6f6b63;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0;
    text-transform: uppercase;
  }

  .trace-stage-head h2 {
    margin: 0;
    font-size: clamp(22px, 2.4vw, 34px);
    line-height: 1.05;
  }

  .trace-query {
    max-width: 640px;
    margin: 9px 0 0;
    color: #46524c;
    font-size: 13px;
    line-height: 1.35;
  }

  .trace-query code {
    white-space: normal;
  }

  .trace-stage-metric {
    flex: 0 0 auto;
    max-width: 180px;
    padding: 8px 10px;
    border: 1px solid rgba(20, 24, 28, 0.12);
    border-radius: 6px;
    background: #f7f4ee;
    color: #2f342f;
    font-size: 12px;
    line-height: 1.35;
    text-align: right;
  }

  .trace-canvas-wrap {
    position: relative;
    padding: 12px;
    background: #f7f4ee;
  }

  .trace-tooltip {
    position: absolute;
    z-index: 3;
    display: none;
    max-width: min(360px, calc(100% - 32px));
    padding: 10px 12px;
    border: 1px solid rgba(20, 24, 28, 0.16);
    border-radius: 8px;
    background: rgba(255, 253, 248, 0.97);
    box-shadow: 0 14px 34px rgba(20, 24, 28, 0.14);
    color: #242a26;
    font-size: 12px;
    line-height: 1.35;
    pointer-events: none;
  }

  .trace-tooltip strong {
    display: block;
    margin-bottom: 4px;
    color: #111827;
    font-size: 12px;
  }

  .trace-zoom-controls {
    position: absolute;
    z-index: 2;
    right: 24px;
    top: 24px;
    display: grid;
    grid-template-columns: 32px minmax(92px, 132px) 32px auto auto;
    gap: 6px;
    align-items: center;
    padding: 7px;
    border: 1px solid rgba(20, 24, 28, 0.12);
    border-radius: 8px;
    background: rgba(255, 253, 248, 0.94);
    box-shadow: 0 10px 26px rgba(20, 24, 28, 0.08);
  }

  .trace-diffusion-controls {
    position: absolute;
    z-index: 2;
    left: 24px;
    bottom: 24px;
    display: none;
    grid-template-columns: auto minmax(120px, 180px) auto;
    gap: 8px;
    align-items: center;
    padding: 7px;
    border: 1px solid rgba(20, 24, 28, 0.12);
    border-radius: 8px;
    background: rgba(255, 253, 248, 0.94);
    box-shadow: 0 10px 26px rgba(20, 24, 28, 0.08);
  }

  .trace-diffusion-controls.active {
    display: grid;
  }

  .trace-diffusion-button {
    min-height: 30px;
    border: 1px solid rgba(20, 24, 28, 0.14);
    border-radius: 6px;
    background: #ffffff;
    color: #16201d;
    font: inherit;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    padding: 0 10px;
  }

  .trace-diffusion-button:hover {
    border-color: rgba(4, 120, 87, 0.42);
    background: #e7f5ef;
    color: #064e3b;
  }

  .trace-diffusion-slider {
    width: 100%;
    accent-color: #047857;
  }

  .trace-diffusion-readout {
    min-width: 34px;
    color: #4b514c;
    font-size: 12px;
    font-weight: 700;
    text-align: right;
  }

  .trace-zoom-button,
  .trace-zoom-reset {
    min-height: 30px;
    border: 1px solid rgba(20, 24, 28, 0.14);
    border-radius: 6px;
    background: #ffffff;
    color: #16201d;
    font: inherit;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
  }

  .trace-zoom-button {
    width: 32px;
    padding: 0;
  }

  .trace-zoom-reset {
    padding: 0 10px;
  }

  .trace-zoom-button:hover,
  .trace-zoom-reset:hover {
    border-color: rgba(4, 120, 87, 0.42);
    background: #e7f5ef;
    color: #064e3b;
  }

  .trace-zoom-slider {
    width: 100%;
    accent-color: #047857;
  }

  .trace-zoom-readout {
    min-width: 42px;
    color: #4b514c;
    font-size: 12px;
    font-weight: 700;
    text-align: right;
  }

  #traceCanvas {
    display: block;
    width: 100%;
    height: auto;
    aspect-ratio: 1200 / 760;
    border: 1px solid rgba(20, 24, 28, 0.08);
    border-radius: 6px;
    background: #f7f4ee;
  }

  .trace-legend {
    border-top: 1px solid rgba(20, 24, 28, 0.12);
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 14px 18px 16px;
    font-size: 13px;
    color: #3a3a35;
  }

  .trace-score-panel {
    display: none;
    border-top: 1px solid rgba(20, 24, 28, 0.12);
    padding: 14px 18px 18px;
    background: #fffdf8;
  }

  .trace-score-panel.active {
    display: grid;
    gap: 10px;
  }

  .trace-score-panel h3 {
    margin: 0;
    font-size: 14px;
  }

  .trace-score-panel p {
    margin: 0;
    color: #4b5563;
    font-size: 12px;
    line-height: 1.4;
  }

  .trace-score-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 8px;
  }

  .trace-score-card {
    border: 1px solid rgba(20, 24, 28, 0.12);
    border-radius: 8px;
    padding: 10px;
    background: #ffffff;
  }

  .trace-score-card.winner {
    border-color: rgba(4, 120, 87, 0.36);
    box-shadow: inset 4px 0 0 #047857;
  }

  .trace-score-card strong {
    display: block;
    margin-bottom: 5px;
    color: #111827;
    font-size: 13px;
  }

  .trace-score-card span {
    display: block;
    color: #4b5563;
    font-size: 12px;
    line-height: 1.35;
  }

  .trace-chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: 30px;
    padding: 6px 9px;
    border: 1px solid rgba(20, 24, 28, 0.12);
    border-radius: 6px;
    background: #ffffff;
    color: #353b36;
    line-height: 1.2;
  }

  .trace-swatch {
    width: 9px;
    height: 9px;
    border-radius: 999px;
    background: var(--trace-color, #64748b);
  }

  .trace-copy {
    min-height: 100%;
  }

  .trace-step {
    display: none;
    min-height: 100%;
    padding: 22px 20px 26px;
    border: 1px solid rgba(20, 24, 28, 0.1);
    border-radius: 8px;
    background: #fffdf8;
    transition: border-color 160ms ease, box-shadow 160ms ease;
  }

  .trace-step.active {
    display: block;
    border-color: rgba(4, 120, 87, 0.34);
    box-shadow: inset 4px 0 0 #047857;
  }

  .trace-step h2 {
    margin: 6px 0 12px;
    max-width: 520px;
  }

  .trace-step p {
    max-width: 560px;
  }

  @media (max-width: 900px) {
    .trace-controls {
      grid-template-columns: 1fr 1fr;
    }

    .trace-step-buttons {
      grid-column: 1 / -1;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      order: -1;
    }

    .trace-slider {
      grid-column: 1 / -1;
    }

    .trace-shell {
      grid-template-columns: 1fr;
    }

    .trace-stage {
      min-height: auto;
    }

    .trace-stage-head {
      flex-direction: column;
    }

    .trace-stage-metric {
      max-width: none;
      text-align: left;
    }

    .trace-zoom-controls {
      position: static;
      grid-template-columns: 32px minmax(0, 1fr) 32px auto auto;
      margin-bottom: 10px;
    }

    .trace-diffusion-controls {
      position: static;
      grid-template-columns: auto minmax(0, 1fr) auto;
      margin-bottom: 10px;
    }
  }
</style>

<script>
(() => {
  const canvas = document.getElementById("traceCanvas");
  const ctx = canvas.getContext("2d");
  const legend = document.getElementById("traceLegend");
  const scorePanel = document.getElementById("traceScorePanel");
  const tooltip = document.getElementById("traceTooltip");
  const stageKicker = document.getElementById("traceKicker");
  const stageTitle = document.getElementById("traceStageTitle");
  const traceQuery = document.getElementById("traceQuery");
  const stageMetric = document.getElementById("traceStageMetric");
  const stepButtons = document.getElementById("traceStepButtons");
  const slider = document.getElementById("traceSlider");
  const prevButton = document.getElementById("tracePrev");
  const nextButton = document.getElementById("traceNext");
  const zoomOutButton = document.getElementById("traceZoomOut");
  const zoomInButton = document.getElementById("traceZoomIn");
  const zoomResetButton = document.getElementById("traceZoomReset");
  const zoomSlider = document.getElementById("traceZoomSlider");
  const zoomReadout = document.getElementById("traceZoomReadout");
  const diffusionControls = document.getElementById("traceDiffusionControls");
  const diffusionPlayButton = document.getElementById("traceDiffusionPlay");
  const diffusionSlider = document.getElementById("traceDiffusionSlider");
  const diffusionReadout = document.getElementById("traceDiffusionReadout");
  const steps = [...document.querySelectorAll(".trace-step")];
  const state = {
    trace: null,
    step: "corpus",
    frame: 0,
    zoom: 1,
    diffusionPaused: false,
    drawnPoints: [],
  };
  const colors = ["#2563eb", "#059669", "#b45309", "#7c3aed", "#dc2626", "#0891b2"];
  const stepOrder = ["corpus", "hybrid", "graph", "spectral", "whole-diffusion", "diffusion", "basins", "final"];
  const stepTitles = {
    corpus: "Corpus field",
    hybrid: "Hybrid retrieval",
    graph: "Evidence graph",
    "whole-diffusion": "Whole-graph diffusion",
    spectral: "Spectral basins",
    diffusion: "Basin diffusion",
    basins: "Basin scoring",
    final: "Final return",
  };
  const shortStepTitles = {
    corpus: "Corpus",
    hybrid: "Hybrid",
    graph: "Graph",
    "whole-diffusion": "Whole Diff.",
    spectral: "Spectral",
    diffusion: "Basin Diff.",
    basins: "Basins",
    final: "Final",
  };

  function currentIndex() {
    return stepOrder.indexOf(state.step);
  }

  function buildControls() {
    stepButtons.innerHTML = stepOrder
      .map((step, index) => {
        const label = `${index + 1}. ${shortStepTitles[step]}`;
        return `<button class="trace-step-button" type="button" data-step="${step}" aria-label="${label}">${label}</button>`;
      })
      .join("");

    stepButtons.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => updateStep(button.dataset.step));
    });
    slider.addEventListener("input", () => updateStep(stepOrder[Number(slider.value)]));
    prevButton.addEventListener("click", () => {
      const nextIndex = Math.max(0, currentIndex() - 1);
      updateStep(stepOrder[nextIndex]);
    });
    nextButton.addEventListener("click", () => {
      const nextIndex = Math.min(stepOrder.length - 1, currentIndex() + 1);
      updateStep(stepOrder[nextIndex]);
    });
    zoomOutButton.addEventListener("click", () => setZoom(state.zoom - 0.25));
    zoomInButton.addEventListener("click", () => setZoom(state.zoom + 0.25));
    zoomResetButton.addEventListener("click", () => setZoom(1));
    zoomSlider.addEventListener("input", () => setZoom(Number(zoomSlider.value)));
    diffusionSlider.addEventListener("input", () => {
      state.diffusionPaused = true;
      setDiffusionFrame(Number(diffusionSlider.value));
    });
    diffusionPlayButton.addEventListener("click", () => {
      state.diffusionPaused = !state.diffusionPaused;
      renderDiffusionControls();
    });
    canvas.addEventListener("mousemove", updateTooltip);
    canvas.addEventListener("mouseleave", hideTooltip);
  }

  async function loadTrace() {
    for (const path of ["../diagnostics_trace.json", "/diagnostics_trace.json", "diagnostics_trace.json"]) {
      try {
        const response = await fetch(path, { cache: "no-store" });
        if (response.ok) return response.json();
      } catch (_) {
        // Try the next path. MkDocs paths differ between local and built pages.
      }
    }
    return null;
  }

  function viewPoints(trace) {
    const points = trace.points.filter((point) => {
      if (["graph", "whole-diffusion", "spectral", "diffusion", "basins", "final"].includes(state.step)) {
        return point.is_graph_candidate;
      }
      if (state.step === "hybrid") return point.is_candidate;
      return true;
    });
    return points.length > 0 ? points : trace.points;
  }

  function viewTransform(trace) {
    return { mode: "field" };
  }

  function fieldLocation(index, total) {
    const angle = index * 2.399963229728653;
    const radius = Math.sqrt((index + 0.5) / total);
    const wobble = ((index * 37) % 17) / 17 - 0.5;
    return {
      x: canvas.width / 2 + Math.cos(angle) * radius * canvas.width * 0.39,
      y: canvas.height / 2 + Math.sin(angle) * radius * canvas.height * 0.31 + wobble * 14,
    };
  }

  function mapPoint(point, view, index, total) {
    if (view.mode === "field") {
      const loc = fieldLocation(index, total);
      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;
      const basinSpreadStep = ["diffusion", "basins", "final"].includes(state.step);
      let basinOffsetX = 0;
      let basinOffsetY = 0;
      if (basinSpreadStep && point.is_graph_candidate && point.community !== null && state.trace) {
        const basinCount = Math.max(1, state.trace.basins.length);
        const angle = (point.community / basinCount) * Math.PI * 2 - Math.PI / 2;
        basinOffsetX = Math.cos(angle) * 230;
        basinOffsetY = Math.sin(angle) * 172;
      }
      return {
        x: centerX + (loc.x + basinOffsetX - centerX) * state.zoom,
        y: centerY + (loc.y + basinOffsetY - centerY) * state.zoom,
      };
    }
  }

  function pointRadius(point) {
    if (state.step === "whole-diffusion") {
      const step = Math.min(state.frame, point.whole_energy.length - 1);
      return 3.5 + Math.sqrt((point.whole_energy[step] || 0) * 960);
    }
    if (state.step === "diffusion") {
      const step = Math.min(state.frame, point.energy.length - 1);
      return 3.5 + Math.sqrt((point.energy[step] || 0) * 960);
    }
    if (state.step === "final" && point.is_final) return 9.5;
    if (state.step === "basins" && point.is_winner) return 7.5;
    if (point.is_graph_candidate && ["graph", "spectral"].includes(state.step)) return 5.5;
    if (point.is_candidate && state.step === "hybrid") return 5.5;
    return 3;
  }

  function pointColor(point) {
    if (state.step === "final" && point.is_final) return "#047857";
    if (state.step === "basins" && point.is_winner) return "#047857";
    if (["spectral", "whole-diffusion", "diffusion", "basins"].includes(state.step) && point.community !== null) {
      return colors[Math.abs(point.community) % colors.length];
    }
    if (["hybrid", "graph", "whole-diffusion"].includes(state.step) && point.is_graph_candidate) return "#2563eb";
    if (state.step === "hybrid" && point.is_candidate) return "#60a5fa";
    return "#a8a29e";
  }

  function pointAlpha(point) {
    if (state.step === "corpus") return 0.58;
    if (state.step === "hybrid") return point.is_candidate ? 0.95 : 0.14;
    if (state.step === "graph") return point.is_graph_candidate ? 0.95 : 0.10;
    if (["whole-diffusion", "spectral", "diffusion", "basins"].includes(state.step)) {
      return point.is_graph_candidate ? 0.95 : 0.08;
    }
    if (state.step === "final") return point.is_final ? 1 : point.is_winner ? 0.32 : 0.07;
    return 0.4;
  }

  function drawEdges(trace, locations) {
    if (!["graph", "whole-diffusion", "spectral", "diffusion", "basins", "final"].includes(state.step)) return;
    const byId = new Map(trace.points.map((point) => [point.id, point]));
    ctx.save();
    for (const edge of trace.edges) {
      const a = locations.get(edge.source);
      const b = locations.get(edge.target);
      if (!a || !b) continue;
      const source = byId.get(edge.source);
      const target = byId.get(edge.target);
      const basinSeparatedStep = ["diffusion", "basins", "final"].includes(state.step);
      if (
        basinSeparatedStep
        && source?.community !== null
        && target?.community !== null
        && source?.community !== target?.community
      ) {
        continue;
      }
      if (state.step === "final" && !(source?.is_winner && target?.is_winner)) continue;
      ctx.globalAlpha = state.step === "graph" ? 0.26 : 0.15;
      ctx.strokeStyle = "#334155";
      ctx.lineWidth = 0.5 + edge.weight * 1.4;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawField() {
    ctx.fillStyle = "#f7f4ee";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.strokeStyle = "rgba(20, 24, 28, 0.055)";
    ctx.lineWidth = 1;
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const spacing = 80 * state.zoom;
    const startX = centerX % spacing;
    const startY = centerY % spacing;
    for (let x = startX; x < canvas.width; x += spacing) {
      ctx.beginPath();
      ctx.moveTo(x, 34);
      ctx.lineTo(x, canvas.height - 34);
      ctx.stroke();
    }
    for (let y = startY; y < canvas.height; y += spacing) {
      ctx.beginPath();
      ctx.moveTo(34, y);
      ctx.lineTo(canvas.width - 34, y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawCommunityLabels(trace, locations) {
    if (!["spectral", "whole-diffusion", "diffusion", "basins", "final"].includes(state.step)) return;
    const groups = new Map();
    for (const point of trace.points) {
      if (!point.is_graph_candidate || point.community === null) continue;
      const loc = locations.get(point.id);
      const group = groups.get(point.community) || { x: 0, y: 0, count: 0 };
      group.x += loc.x;
      group.y += loc.y;
      group.count += 1;
      groups.set(point.community, group);
    }

    ctx.save();
    ctx.font = "600 17px system-ui, sans-serif";
    ctx.textBaseline = "middle";
    for (const [community, group] of groups.entries()) {
      const text = `basin ${community}`;
      const x = group.x / group.count;
      const y = group.y / group.count;
      const width = ctx.measureText(text).width + 22;
      ctx.fillStyle = "rgba(255, 253, 248, 0.88)";
      ctx.strokeStyle = "rgba(20, 24, 28, 0.12)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(x - width / 2, y - 44, width, 28, 6);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = colors[Math.abs(community) % colors.length];
      ctx.fillText(text, x - width / 2 + 11, y - 30);
    }
    ctx.restore();
  }

  function drawFinalLabels(trace, locations) {
    if (state.step !== "final") return;
    const finals = trace.points.filter((point) => point.is_final);
    ctx.save();
    ctx.font = "700 15px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    finals.forEach((point, index) => {
      const loc = locations.get(point.id);
      ctx.fillStyle = "#fffdf8";
      ctx.strokeStyle = "#047857";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(loc.x + 15, loc.y - 15, 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#047857";
      ctx.fillText(String(index + 1), loc.x + 15, loc.y - 15);
    });
    ctx.restore();
  }

  function renderHeader(trace) {
    const index = stepOrder.indexOf(state.step) + 1;
    stageKicker.textContent = `${index} / ${stepOrder.length}`;
    stageTitle.textContent = stepTitles[state.step];
    if (!trace) {
      traceQuery.innerHTML = "<code>uv run noetic trace --calibrate-graph --graph-objective auto --output docs/diagnostics_trace.json</code>";
      stageMetric.textContent = "Run uv run noetic trace --calibrate-graph --graph-objective auto --output docs/diagnostics_trace.json";
      return;
    }
    traceQuery.innerHTML = `Query: <code>${escapeHtml(trace.case.query)}</code>`;
    if (["whole-diffusion", "diffusion"].includes(state.step)) {
      stageMetric.textContent = `time step ${state.frame} of ${trace.settings.diffusion_steps}`;
    } else if (["spectral", "basins"].includes(state.step)) {
      stageMetric.textContent = `${trace.basins.length} basin${trace.basins.length === 1 ? "" : "s"} detected`;
    } else if (state.step === "final") {
      const finalCount = trace.points.filter((point) => point.is_final).length;
      stageMetric.textContent = `returned ${finalCount} chunks`;
    } else {
      stageMetric.textContent = `${trace.points.length} chunks shown`;
    }
  }

  function renderLegend(trace) {
    if (!trace) {
      legend.textContent = "Generate docs/diagnostics_trace.json, then refresh this page.";
      return;
    }
    const chips = [["#a8a29e", "corpus field"]];
    if (["hybrid", "graph", "whole-diffusion", "spectral", "diffusion", "basins", "final"].includes(state.step)) {
      chips.push(["#60a5fa", "hybrid top-k"]);
    }
    if (["graph", "whole-diffusion", "spectral", "diffusion", "basins", "final"].includes(state.step)) {
      chips.push(["#2563eb", "graph candidates"]);
    }
    if (["spectral", "whole-diffusion", "diffusion", "basins", "final"].includes(state.step)) {
      chips.push(["#7c3aed", `${trace.basins.length} basin${trace.basins.length === 1 ? "" : "s"}`]);
    }
    if (["basins", "final"].includes(state.step)) {
      chips.push(["#047857", `winner ${trace.winner.label}`]);
    }
    if (state.step === "whole-diffusion") {
      chips.push(["#0f766e", "full graph energy"]);
    }
    if (state.step === "diffusion") {
      chips.push(["#0f766e", "same-basin energy"]);
    }
    if (trace.case.target_ids.length > 0) {
      chips.push(["#f59e0b", "known support"]);
    }
    legend.innerHTML = chips
      .map(([color, text]) => `<span class="trace-chip"><span class="trace-swatch" style="--trace-color:${color}"></span>${text}</span>`)
      .join("");
  }

  function formatNumber(value) {
    return Number(value).toFixed(3);
  }

  function formatSignedNumber(value) {
    const number = Number(value);
    return `${number >= 0 ? "+" : ""}${number.toFixed(3)}`;
  }

  function renderScorePanel(trace) {
    if (!trace || !trace.basins.length || !["whole-diffusion", "basins", "final"].includes(state.step)) {
      scorePanel.classList.remove("active");
      scorePanel.innerHTML = "";
      return;
    }

    const winner = trace.basins[0];
    if (state.step === "whole-diffusion") {
      const flowCards = trace.basins.map((basin) => {
        const delta = basin.whole_energy_delta || 0;
        return `
          <div class="trace-score-card ${delta > 0 ? "winner" : ""}">
            <strong>${escapeHtml(basin.label)}</strong>
            <span>seed energy ${formatNumber(basin.seed_energy || 0)}</span>
            <span>whole-graph energy ${formatNumber(basin.whole_energy || 0)}</span>
            <span>flow delta ${formatSignedNumber(delta)}</span>
            <span>target fraction ${formatNumber(basin.target_fraction || 0)}</span>
          </div>
        `;
      }).join("");

      scorePanel.classList.add("active");
      scorePanel.innerHTML = `
        <h3>Diagnostic only: whole-graph diffusion</h3>
        <p><strong>This panel does not choose the winner.</strong> It lets energy cross every graph edge so we can measure attraction, leakage, and absorption. Positive flow delta means a basin absorbed energy from the surrounding field; negative delta means it leaked energy into neighbors.</p>
        <p>The next diffusion step removes cross-basin edges. That basin-constrained distribution is the one used for scoring.</p>
        <div class="trace-score-grid">${flowCards}</div>
      `;
      return;
    }

    const formula = "score = 0.45*energy + 0.25*support + 0.20*cohesion - duplicate penalty";
    const seedWinner = trace.metrics.hybrid_seed_winner || "unknown";
    const seedCopy = seedWinner === winner.label
      ? `${escapeHtml(winner.label)} was also the hybrid seed-energy winner. This trace is showing graph-based compression and representative selection, not a basin winner reversal.`
      : `${escapeHtml(winner.label)} beat ${escapeHtml(seedWinner)}, the basin with the largest initial hybrid seed energy. That is only defensible if the winner is not merely larger, but structurally healthier.`;
    const reversalCopy = seedWinner === winner.label
      ? "No reversal is claimed here. Hybrid found the strongest region, and Noetic compresses it into representative chunks."
      : "A reversal means hybrid gave another basin the head start. The winner must justify that reversal with enough seed energy to stay relevant, strong cohesion, non-duplicate support, and a final return that covers the fuller explanation.";
    const basinCards = trace.basins.map((basin) => {
      const supportScore = basin.support_component / 0.25;
      const isWinner = basin.label === winner.label;
      return `
        <div class="trace-score-card ${isWinner ? "winner" : ""}">
          <strong>${escapeHtml(basin.label)}${isWinner ? " selected" : ""}</strong>
          <span>score ${formatNumber(basin.score)}</span>
          <span>seed energy ${formatNumber(basin.seed_energy || 0)}</span>
          <span>whole delta ${formatSignedNumber(basin.whole_energy_delta || 0)}</span>
          <span>energy ${formatNumber(basin.energy)}</span>
          <span>energy delta ${formatSignedNumber(basin.energy_delta || 0)}</span>
          <span>score parts ${formatNumber(basin.energy_component || 0)} energy, ${formatNumber(basin.support_component || 0)} support, ${formatNumber(basin.cohesion_component || 0)} cohesion</span>
          <span>support ${basin.support} chunks (${formatNumber(supportScore)})</span>
          <span>cohesion ${formatNumber(basin.cohesion)}</span>
          <span>duplicate penalty ${formatNumber(basin.duplicate_penalty)}</span>
          <span>target fraction ${formatNumber(basin.target_fraction || 0)}</span>
        </div>
      `;
    }).join("");

    const pointById = new Map(trace.points.map((point) => [point.id, point]));
    const winnerDocs = trace.winner.documents
      .map((docId, index) => {
        const text = pointById.get(docId)?.text || docId;
        return `${index + 1}. <strong>${escapeHtml(docId)}</strong>: ${escapeHtml(text)}`;
      })
      .join("<br>");
    const targetIds = new Set(trace.case.target_ids || []);
    const linkedChunks = trace.final_chunks || [];
    const linkedDocs = linkedChunks
      .map((chunk, index) => {
        const docId = chunk.id;
        const point = pointById.get(docId);
        const basin = point?.community === null || point?.community === undefined
          ? "no basin"
          : `basin-${point.community}`;
        const target = targetIds.has(docId) ? " target" : "";
        const anchor = chunk.is_anchor ? " anchor" : "";
        const text = point?.text || docId;
        return `${index + 1}. <strong>${escapeHtml(docId)}</strong> (${escapeHtml(basin)}${target}${anchor}): ${escapeHtml(text)}`;
      })
      .join("<br>");
    const linkedBasins = [...new Set(
      linkedChunks
        .map((chunk) => pointById.get(chunk.id)?.community)
        .filter((community) => community !== null && community !== undefined)
        .map((community) => `basin-${community}`)
    )];
    const targetBasins = [...new Set(
      [...targetIds]
        .map((docId) => pointById.get(docId)?.community)
        .filter((community) => community !== null && community !== undefined)
        .map((community) => `basin-${community}`)
    )];
    const basinAgreementCopy = linkedBasins.length <= 1
      ? `The linked return stays inside ${escapeHtml(linkedBasins[0] || "one basin")}, so production ranking and basin diagnostics are telling the same compact-region story.`
      : `The linked return spans ${escapeHtml(linkedBasins.join(", "))}. That means production ranking is preserving a cross-basin evidence chain rather than forcing all returned support into the selected diagnostic basin.`;
    const targetSplitCopy = targetBasins.length <= 1
      ? `The known support paragraphs sit inside ${escapeHtml(targetBasins[0] || "one basin")}.`
      : `The known support paragraphs are split across ${escapeHtml(targetBasins.join(", "))}, so the spectral diagnostic separated the two-hop answer into distinct local regions.`;
    const finalCopy = state.step === "final"
      ? `
        <p><strong>Basin selection versus final return:</strong> ${basinAgreementCopy} ${targetSplitCopy}</p>
        <p><strong>Selected diagnostic-basin representatives:</strong><br>${winnerDocs}</p>
        <p><strong>Production linked return:</strong><br>${linkedDocs}</p>
      `
      : "";

    scorePanel.classList.add("active");
    scorePanel.innerHTML = `
      <h3>Why ${escapeHtml(winner.label)} wins</h3>
      <p>${formula}</p>
      <p><strong>Scoring path:</strong> These values use basin-constrained diffusion, where cross-basin edges have been removed. Whole-graph flow delta is shown as context, not as the final scoring energy.</p>
      <p><strong>Hybrid check:</strong> ${seedCopy}</p>
      <p><strong>Reversal standard:</strong> ${reversalCopy}</p>
      <div class="trace-score-grid">${basinCards}</div>
      ${finalCopy}
    `;
  }

  function renderDiffusionControls() {
    if (!state.trace || !["whole-diffusion", "diffusion"].includes(state.step)) {
      diffusionControls.classList.remove("active");
      return;
    }
    diffusionSlider.max = String(state.trace.settings.diffusion_steps);
    diffusionSlider.value = String(state.frame);
    diffusionReadout.textContent = `t=${state.frame}`;
    diffusionPlayButton.textContent = state.diffusionPaused ? "Play" : "Pause";
    diffusionControls.classList.add("active");
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function hideTooltip() {
    tooltip.style.display = "none";
  }

  function updateTooltip(event) {
    if (!state.drawnPoints.length) {
      hideTooltip();
      return;
    }

    const rect = canvas.getBoundingClientRect();
    const canvasX = ((event.clientX - rect.left) / rect.width) * canvas.width;
    const canvasY = ((event.clientY - rect.top) / rect.height) * canvas.height;
    let nearest = null;
    let nearestDistance = Infinity;
    for (const item of state.drawnPoints) {
      const distance = Math.hypot(canvasX - item.x, canvasY - item.y);
      if (distance < nearestDistance) {
        nearest = item;
        nearestDistance = distance;
      }
    }

    if (!nearest || nearestDistance > Math.max(28, nearest.radius + 16)) {
      hideTooltip();
      return;
    }

    const left = Math.min(
      rect.width - 18,
      Math.max(14, event.clientX - rect.left + 14),
    );
    const top = Math.max(14, event.clientY - rect.top + 14);
    tooltip.style.display = "block";
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
    tooltip.innerHTML = `<strong>${escapeHtml(nearest.point.id)}</strong>${escapeHtml(nearest.point.text)}`;
  }

  function setZoom(value) {
    state.zoom = Math.min(4, Math.max(1, value));
    zoomSlider.value = String(state.zoom);
    zoomReadout.textContent = `${Math.round(state.zoom * 100)}%`;
    draw();
  }

  function setDiffusionFrame(value) {
    const maxFrame = state.trace ? state.trace.settings.diffusion_steps : 0;
    state.frame = Math.min(maxFrame, Math.max(0, value));
    draw();
  }

  function draw() {
    const trace = state.trace;
    renderHeader(trace);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawField();

    if (!trace) {
      ctx.fillStyle = "#1f2933";
      ctx.font = "24px system-ui, sans-serif";
      ctx.fillText("No diagnostics_trace.json found.", 56, 86);
      ctx.font = "16px system-ui, sans-serif";
      ctx.fillText("Run: uv run noetic trace --calibrate-graph --graph-objective auto --output docs/diagnostics_trace.json", 56, 122);
      renderLegend(trace);
      renderScorePanel(trace);
      return;
    }

    const view = viewTransform(trace);
    const locations = new Map(
      trace.points.map((point, index) => [
        point.id,
        mapPoint(point, view, index, trace.points.length),
      ]),
    );
    const drawnPoints = [];
    drawEdges(trace, locations);
    drawCommunityLabels(trace, locations);

    for (const point of trace.points) {
      const loc = locations.get(point.id);
      const radius = pointRadius(point);
      ctx.save();
      ctx.globalAlpha = pointAlpha(point);
      ctx.fillStyle = pointColor(point);
      ctx.beginPath();
      ctx.arc(loc.x, loc.y, radius, 0, Math.PI * 2);
      ctx.fill();
      if (point.is_target && ["basins", "final"].includes(state.step)) {
        ctx.globalAlpha = 1;
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#f59e0b";
        ctx.stroke();
      }
      ctx.restore();
      drawnPoints.push({ point, x: loc.x, y: loc.y, radius });
    }
    state.drawnPoints = drawnPoints;
    drawFinalLabels(trace, locations);
    renderLegend(trace);
    renderScorePanel(trace);
    renderDiffusionControls();
  }

  function updateStep(step) {
    state.step = step;
    const index = currentIndex();
    slider.value = String(index);
    prevButton.disabled = index === 0;
    nextButton.disabled = index === stepOrder.length - 1;
    if (!["whole-diffusion", "diffusion"].includes(step)) {
      state.diffusionPaused = false;
    }
    steps.forEach((item) => item.classList.toggle("active", item.dataset.step === step));
    stepButtons
      .querySelectorAll("button")
      .forEach((button) => {
        const active = button.dataset.step === step;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
      });
    draw();
  }

  setInterval(() => {
    if (["whole-diffusion", "diffusion"].includes(state.step) && state.trace && !state.diffusionPaused) {
      setDiffusionFrame((state.frame + 1) % (state.trace.settings.diffusion_steps + 1));
    }
  }, 1300);

  buildControls();
  setZoom(1);
  loadTrace().then((trace) => {
    state.trace = trace;
    updateStep("corpus");
  });
})();
</script>
