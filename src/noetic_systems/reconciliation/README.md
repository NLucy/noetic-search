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

The modules are named to match the process:

```text
candidates -> graph -> spectral -> seeding -> diffusion -> basins
           -> uncertainty -> ranking -> result
```

## Reading Order

1. `engine.py`
   The orchestration layer. Start here to see the full sequence in one method:
   retrieve candidates, admit graph candidates, build the graph, detect basins,
   seed and diffuse energy, score basins, estimate uncertainty, and return a
   result.
   The engine should stay thin. It answers "what happens next?" while each
   process module answers "how is this step computed?"

2. `candidates.py`
   Selects the local graph candidate field from broad hybrid retrieval by
   preserving rank order up to the graph limit. This is intentionally neutral:
   it does not reinterpret the hybrid ranking before graph construction.
   Conceptually, this step sets the working field. It does not decide what is
   correct; it only limits the number of candidates that later graph operations
   must consider.

3. `graph.py`
   Builds the evidence graph. Chunks become nodes. Each chunk pair can receive
   one weighted evidence connection. That connection may combine embedding
   similarity, ordinary metadata, and near-duplicate signal contributions.
   This is where the retrieved list becomes a structure. The graph does not
   answer the query by itself; it defines which candidates can support, repeat,
   or relate to one another before spectral analysis and diffusion run.

4. `spectral.py`
   Uses the normalized graph Laplacian and Fiedler vector to propose basin
   boundaries. If the graph does not support a useful split, the field remains
   one basin.
   This is the graph-geometry step. The Laplacian asks where values can stay
   smooth inside a region and where they naturally separate. Accepted splits
   become candidate basins; rejected splits leave the field intact.
   This step defines the basin assignments. Diffusion later uses those fixed
   assignments; it does not create or redraw them.

5. `seeding.py`
   Converts hybrid retrieval scores and ranks into the initial energy
   distribution for diffusion.
   Seeding preserves the first-stage retrieval opinion without making it final.
   High-ranked chunks start with more influence, but lower-ranked chunks remain
   eligible to gain support through the graph. Seeding happens after basin
   detection because the spectral step only needs graph structure, not retrieval
   energy.

6. `diffusion.py`
   Runs discrete time-step propagation over the fixed evidence graph. Energy
   moves across weighted edges so support can travel through related chunks.
   Each time step redistributes the current energy. A chunk can gain importance
   because it is connected to other supported chunks, and an isolated high-rank
   candidate can lose dominance because little support flows back to it.
   Diffusion does not find, move, or redraw basins; it measures how retrieval
   confidence settles on nodes inside the basins that spectral analysis already
   proposed.

7. `basins.py`
   Scores each fixed spectral basin using settled energy, support, cohesion, and
   duplicate pressure.
   This step chooses between regions, not individual chunks. A good basin should
   have energy that settled into it, enough members to represent an evidence
   position, internal coherence, and limited duplicate pressure.

8. `uncertainty.py`
   Calculates structural uncertainty from basin competition, energy dispersion,
   and graph modularity. Basin competition is only knowable after basin scoring:
   if the runner-up basin is close to the winner, uncertainty rises. Dispersion
   checks whether diffused energy stayed scattered instead of settling, and
   modularity checks whether the graph split had a clear structure.

9. `ranking.py`
   Ranks representative chunks only inside the winning basin. Ranking happens
   after basin scoring because discarded basins do not need final return order.
   Once the winning region is known, the task becomes selecting the most useful
   representatives of that region for a compact LLM payload.

10. `result.py`
    Exposes caller-facing surfaces: document ids, LLM-ready chunks, strongest
    basin payloads, and the full evidence field. The default product surface is
    the winning basin's chunks. The inspection surface can also return competing
    basins so an engineer, evaluator, or LLM prompt can see what the winning
    basin beat and whether the field was structurally uncertain.

11. `models.py`
    Defines the small typed records passed between modules: `EvidenceEdge`,
    `Basin`, and algorithm mode literals.
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

- Change `candidates.py` carefully: it controls recall before graph reasoning.
- Change `graph.py` carefully: edge weights define every downstream operation.
- Change `spectral.py` carefully: split guards decide whether basins exist.
- Change `seeding.py` and `diffusion.py` carefully: they determine how retrieval
  confidence settles inside the fixed graph.
- Change `basins.py` carefully: basin scoring determines the winning region.
- Change `ranking.py` carefully: chunk ranking determines what the LLM actually sees.
