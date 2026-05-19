<div class="noetic-page trace-viewer">
  <section class="hero compact">
    <p class="eyebrow">Production trace</p>
    <h1>Watch a real HotpotQA win move through Noetic Search.</h1>
    <p>
      Generate the production trace with <code>uv run noetic trace</code>, then
      serve the docs. The browser renders
      the actual candidate field, graph edges, and linked-evidence return used
      by the benchmarked production path.
    </p>
    <p>
      This case asks: <strong>The director of the romantic comedy "Big Stone Gap"
      is based in what New York city?</strong> Hybrid top-5 finds the film
      paragraph but misses the director paragraph. Noetic linked top-5 returns
      both support paragraphs.
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
      max="4"
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
          <p id="traceKicker" class="trace-kicker">1 / 5</p>
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
          explicit cross-reference, and near-duplicate signal. Metadata remains
          payload only; it does not create graph edges.
        </p>
        <p>
          Some admitted candidates may have no visible edge. That means hybrid
          retrieval brought them into the field, but no relationship cleared the
          graph threshold.
        </p>
      </article>
      <article class="trace-step" data-step="linked">
        <p class="eyebrow">4. Linked Evidence</p>
        <h2>Rank the return set from graph-connected support.</h2>
        <p>
          This is the benchmarked production step. The strongest hybrid anchors
          are preserved, then graph-connected support chunks are promoted by
          query score, anchor affinity, and local graph support.
        </p>
        <p>
          The point is not to let the graph replace retrieval. The graph
          compresses a larger candidate pool into a smaller linked set that
          still preserves the query anchors.
        </p>
      </article>
      <article class="trace-step" data-step="final">
        <p class="eyebrow">5. Final Return</p>
        <h2>Return compact linked evidence.</h2>
        <p>
          These are the chunks that would be passed to the LLM through
          <code>chunks()</code>.
        </p>
        <p>
          Final return preserves strong hybrid anchors, then promotes candidates
          connected to those anchors through the evidence graph.
        </p>
        <p>
          This is the benchmarked production path. It is selected by
          linked-evidence ranking, not by diffusion or basin scoring.
        </p>
        <p>
          The ranking score combines original query score, anchor affinity, and
          graph support. Anchor affinity asks whether a candidate is strongly
          connected to one of the preserved top hybrid anchors.
        </p>
        <p>
          The diagnostics still exist in the codebase for research and
          inspection, but they are not part of this production trace.
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
    grid-template-columns: repeat(5, minmax(0, 1fr));
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
  const steps = [...document.querySelectorAll(".trace-step")];
  const state = {
    trace: null,
    step: "corpus",
    frame: 0,
    zoom: 1,
    drawnPoints: [],
  };
  const colors = ["#2563eb", "#059669", "#b45309", "#7c3aed", "#dc2626", "#0891b2"];
  const stepOrder = ["corpus", "hybrid", "graph", "linked", "final"];
  const stepTitles = {
    corpus: "Corpus field",
    hybrid: "Hybrid retrieval",
    graph: "Evidence graph",
    linked: "Linked evidence return",
    final: "Final return",
  };
  const shortStepTitles = {
    corpus: "Corpus",
    hybrid: "Hybrid",
    graph: "Graph",
    linked: "Linked",
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
    canvas.addEventListener("mousemove", updateTooltip);
    canvas.addEventListener("mouseleave", hideTooltip);
  }

  async function loadTrace() {
    for (const path of ["../production_trace.json", "/production_trace.json", "production_trace.json"]) {
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
      if (["graph", "linked", "final"].includes(state.step)) {
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
      return {
        x: centerX + (loc.x - centerX) * state.zoom,
        y: centerY + (loc.y - centerY) * state.zoom,
      };
    }
  }

  function pointRadius(point) {
    if (state.step === "final" && point.is_final) return 9.5;
    if (state.step === "linked" && point.is_final) return 8.5;
    if (point.is_graph_candidate && ["graph", "linked"].includes(state.step)) return 5.5;
    if (point.is_candidate && state.step === "hybrid") return 5.5;
    return 3;
  }

  function pointColor(point) {
    if (state.step === "final" && point.is_final) return "#047857";
    if (state.step === "linked" && point.is_final) return "#047857";
    if (["hybrid", "graph", "linked"].includes(state.step) && point.is_graph_candidate) return "#2563eb";
    if (state.step === "hybrid" && point.is_candidate) return "#60a5fa";
    return "#a8a29e";
  }

  function pointAlpha(point) {
    if (state.step === "corpus") return 0.58;
    if (state.step === "hybrid") return point.is_candidate ? 0.95 : 0.14;
    if (state.step === "graph") return point.is_graph_candidate ? 0.95 : 0.10;
    if (state.step === "linked") return point.is_final ? 1 : point.is_graph_candidate ? 0.32 : 0.07;
    if (state.step === "final") return point.is_final ? 1 : point.is_graph_candidate ? 0.20 : 0.07;
    return 0.4;
  }

  function drawEdges(trace, locations) {
    if (!["graph", "linked", "final"].includes(state.step)) return;
    const byId = new Map(trace.points.map((point) => [point.id, point]));
    ctx.save();
    for (const edge of trace.edges) {
      const a = locations.get(edge.source);
      const b = locations.get(edge.target);
      if (!a || !b) continue;
      const source = byId.get(edge.source);
      const target = byId.get(edge.target);
      const basinSeparatedStep = false;
      if (
        basinSeparatedStep
        && source?.community !== null
        && target?.community !== null
        && source?.community !== target?.community
      ) {
        continue;
      }
      if (state.step === "final" && !(source?.is_final || target?.is_final)) continue;
      if (state.step === "linked" && !(source?.is_final || target?.is_final)) continue;
      ctx.globalAlpha = state.step === "graph" ? 0.26 : state.step === "linked" ? 0.24 : 0.15;
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

  function drawCommunityLabels(trace, locations) {}

  function drawFinalLabels(trace, locations) {
    if (!["linked", "final"].includes(state.step)) return;
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
      traceQuery.innerHTML = "<code>uv run noetic trace</code>";
      stageMetric.textContent = "Run uv run noetic trace";
      return;
    }
    traceQuery.innerHTML = `Query: <code>${escapeHtml(trace.case.query)}</code>`;
    if (["linked", "final"].includes(state.step)) {
      const finalCount = trace.points.filter((point) => point.is_final).length;
      stageMetric.textContent = `returned ${finalCount} chunks`;
    } else {
      stageMetric.textContent = `${trace.points.length} chunks shown`;
    }
  }

  function renderLegend(trace) {
    if (!trace) {
      legend.textContent = "Generate docs/production_trace.json, then refresh this page.";
      return;
    }
    const chips = [["#a8a29e", "corpus field"]];
    if (["hybrid", "graph", "linked", "final"].includes(state.step)) {
      chips.push(["#60a5fa", "hybrid top-k"]);
    }
    if (["graph", "linked", "final"].includes(state.step)) {
      chips.push(["#2563eb", "graph candidates"]);
    }
    if (["linked", "final"].includes(state.step)) {
      chips.push(["#047857", "linked return"]);
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
    if (!trace || !["linked", "final"].includes(state.step)) {
      scorePanel.classList.remove("active");
      scorePanel.innerHTML = "";
      return;
    }

    const pointById = new Map(trace.points.map((point) => [point.id, point]));
    const targetIds = new Set(trace.case.target_ids || []);
    const hybridDocs = trace.points
      .filter((point) => point.candidate_rank && point.candidate_rank <= 5)
      .sort((left, right) => left.candidate_rank - right.candidate_rank)
      .map((point) => {
        const badge = targetIds.has(point.id) ? " <strong>support</strong>" : "";
        return `${point.candidate_rank}. ${escapeHtml(point.text)}${badge}`;
      })
      .join("<br>");
    const finalDocs = (trace.final_chunks || [])
      .map((chunk) => {
        const text = pointById.get(chunk.id)?.text || chunk.id;
        const badge = targetIds.has(chunk.id) ? " <strong>support</strong>" : "";
        const formula = chunk.is_anchor
          ? "preserved hybrid anchor"
          : `rank score ${formatNumber(chunk.rank_score)} = 0.50*query ${formatNumber(chunk.query_score)} + 0.35*anchor ${formatNumber(chunk.anchor_affinity)} + 0.15*support ${formatNumber(chunk.support_score)}`;
        return `${chunk.rank}. ${escapeHtml(text)}${badge}<br><span>${formula}; raw support ${formatNumber(chunk.support)}</span>`;
      })
      .join("<br>");
    const hybridTargetCount = trace.points
      .filter((point) => point.candidate_rank && point.candidate_rank <= 5 && targetIds.has(point.id))
      .length;
    const finalTargetCount = (trace.final_chunks || [])
      .filter((chunk) => targetIds.has(chunk.id))
      .length;

    scorePanel.classList.add("active");
    scorePanel.innerHTML = `
      <h3>${state.step === "linked" ? "Production path: linked evidence" : "Final production return"}</h3>
      <p><strong>HotpotQA support recovery:</strong> hybrid top-5 returns ${hybridTargetCount} of ${targetIds.size} support paragraphs; Noetic linked top-5 returns ${finalTargetCount} of ${targetIds.size}.</p>
      <p><strong>This is the default return path.</strong> It starts from a high-recall hybrid candidate set, preserves the strongest hybrid anchors, and then promotes chunks that are strongly connected to those anchors in the evidence graph.</p>
      <p>The ranking score combines original query score, anchor affinity, and graph support. Anchor affinity means a candidate is connected to one of the preserved top hybrid anchors. Graph support means the candidate has enough weighted relationships inside the admitted graph to act as useful context rather than an isolated hit.</p>
      <p>Hybrid top-5:<br>${hybridDocs}</p>
      <p>Returned linked evidence:<br>${finalDocs}</p>
    `;
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

  function draw() {
    const trace = state.trace;
    renderHeader(trace);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawField();

    if (!trace) {
      ctx.fillStyle = "#1f2933";
      ctx.font = "24px system-ui, sans-serif";
      ctx.fillText("No production_trace.json found.", 56, 86);
      ctx.font = "16px system-ui, sans-serif";
      ctx.fillText("Run: uv run noetic trace", 56, 122);
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
      ctx.restore();
      drawnPoints.push({ point, x: loc.x, y: loc.y, radius });
    }
    state.drawnPoints = drawnPoints;
    drawFinalLabels(trace, locations);
    renderLegend(trace);
    renderScorePanel(trace);
  }

  function updateStep(step) {
    state.step = step;
    const index = currentIndex();
    slider.value = String(index);
    prevButton.disabled = index === 0;
    nextButton.disabled = index === stepOrder.length - 1;
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

  buildControls();
  setZoom(1);
  loadTrace().then((trace) => {
    state.trace = trace;
    updateStep("corpus");
  });
})();
</script>
