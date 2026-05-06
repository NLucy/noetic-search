# Reconciliation Module Map

This package contains the post-retrieval reconciliation path for Noetic Search.
It turns a broad hybrid-retrieval candidate field into a scored evidence basin
and returns representative chunks from that basin.

The main idea is simple: first-stage retrieval should be broad, but final LLM
context should be coherent. Reconciliation is the layer between those two
requirements. It keeps the candidate field local to one query, turns candidates
into a graph, detects coherent regions in that graph, lets retrieval confidence
move through the graph, and returns the best representatives of the strongest
region.

The modules are named to match the durable implementation boundaries:

```text
engine -> graph -> spectral -> diffusion -> basins -> ranking -> result
       -> metrics -> models
```

## Reading Order

1. `engine.py`
   The orchestration layer. Start here to see the full sequence in one method:
   retrieve candidates, admit graph candidates, build the graph, detect basins,
   initialize and diffuse energy, score basins, estimate uncertainty, and return a
   result.
   The engine should stay thin. It answers "what happens next?" while each
   process module answers "how is this step computed?"
   Candidate admission is intentionally simple and stays here: the graph field
   is the first `result_limit` candidates from broad retrieval.

2. `graph.py`
   Builds the evidence graph. Chunks become nodes. Each chunk pair can receive
   one weighted evidence connection. That connection may combine embedding
   similarity and near-duplicate signal contributions. Metadata remains part of
   the returned chunk payload, but it does not create graph edges.
   This is where the retrieved list becomes a structure. The graph does not
   answer the query by itself; it defines which candidates can support, repeat,
   or relate to one another before spectral analysis and diffusion run.

3. `spectral.py`
   Uses the normalized graph Laplacian and Fiedler vector to propose basin
   boundaries. If the graph does not support a useful split, the field remains
   one basin.
   This is the graph-geometry step. The Laplacian asks where values can stay
   smooth inside a region and where they naturally separate. Accepted splits
   become candidate basins; rejected splits leave the field intact.
   This step defines the basin assignments. Diffusion later uses those fixed
   assignments; it does not create or redraw them.

4. `diffusion.py`
   Converts hybrid retrieval scores and ranks into the initial energy
   distribution, then runs discrete time-step propagation over a graph. The
   trace viewer uses the same diffusion update in two ways: first on the whole
   graph as a diagnostic for attraction, leakage, and absorption; then on a graph
   with cross-basin edges removed for basin scoring.
   In the scoring path, energy moves across same-basin weighted edges so support
   can travel through related chunks without leaking into a competing region.
   Initialization preserves the first-stage retrieval opinion without making it
   final. High-ranked chunks start with more influence, but lower-ranked chunks
   remain eligible to gain support through the graph.
   Each time step redistributes the current energy inside each basin. A chunk can
   gain importance because it is connected to other supported chunks in its
   region, and an isolated high-rank candidate can lose dominance because little
   support flows back to it.
   Diffusion does not find, move, or redraw basins; it measures how retrieval
   confidence settles on nodes inside the basins that spectral analysis already
   proposed.

5. `basins.py`
   Scores each fixed spectral basin using settled energy, support, cohesion, and
   duplicate pressure.
   This step chooses between regions, not individual chunks. A good basin should
   have energy that settled into it, enough members to represent an evidence
   position, internal coherence, and limited duplicate pressure.
   Support is bounded, but it now grows across a wider range before saturating,
   so a broad coherent basin can beat a narrower basin that started with more
   hybrid retrieval energy.
   This module also calculates structural uncertainty from basin competition,
   energy dispersion, and graph modularity. Basin competition is only knowable
   after basin scoring:
   if the runner-up basin is close to the winner, uncertainty rises. Dispersion
   checks whether diffused energy stayed scattered instead of settling, and
   modularity checks whether the graph split had a clear structure.

6. `ranking.py`
   Ranks representative chunks only inside the winning basin. Ranking happens
   after basin scoring because discarded basins do not need final return order.
   Once the winning region is known, the task becomes selecting the most useful
   representatives of that region for a compact LLM payload.

7. `result.py`
   Exposes caller-facing surfaces: document ids, LLM-ready chunks, strongest
   basin payloads, and the full evidence field. The default product surface is
   the winning basin's chunks. The inspection surface can also return competing
   basins so an engineer, evaluator, or LLM prompt can see what the winning
   basin beat and whether the field was structurally uncertain.

8. `metrics.py`
   Provides shared graph and text measurements used by basin scoring, uncertainty,
   ranking, and result payloads. Keeping these calculations together avoids
   hiding small scoring rules across the pipeline.

9. `models.py`
   Defines the small typed records passed between modules: `EvidenceEdge` and
   `Basin`.
   These records are intentionally plain. They make the pipeline easy to test
   because each stage passes explicit data rather than hidden state.

## Default Return

The normal caller path is:

```text
Reconciler.reconcile(query).chunks(database, k=5)
```

That returns the top representative chunks from the winning basin. The caller can
instead ask for `strongest_basin()` when it wants basin metrics alongside chunks,
or `evidence_field()` when it wants the inspection view with competing basins and
uncertainty reasons.

## What To Change Carefully

- Change `graph.py` carefully: edge weights define every downstream operation.
- Change `spectral.py` carefully: split guards decide whether basins exist.
- Change `diffusion.py` carefully: it determines how retrieval confidence is
  initialized and settles inside the fixed graph.
- Change `basins.py` carefully: basin scoring determines the winning region and
  uncertainty.
- Change `ranking.py` carefully: chunk ranking determines what the LLM actually sees.
