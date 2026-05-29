"""Command-line interface for demos and LLM payload inspection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from noetic_systems.corpus import demo_corpus
from noetic_systems.database import Database
from noetic_systems.llm.experiment import Mode, build_llm_experiment
from noetic_systems.llm.openai_client import OpenAIResponsesClient
from noetic_systems.reconciliation.calibration import GRAPH_OBJECTIVES
from noetic_systems.reconciliation.engine import Reconciler
from noetic_systems.reconciliation.graph import GraphWeights
from noetic_systems.trace import (
    DEFAULT_TRACE_CASE_ID,
    DEFAULT_TRACE_DATA_PATH,
    DEFAULT_TRACE_EDGE_THRESHOLD,
    DEFAULT_TRACE_PATH,
    generate_trace,
)


QUERIES = {
    "battery": "Should I trust the battery life claims?",
    "camera": "Is the camera actually good?",
    "value": "Is this device a good value?",
    "balanced": "What is the overall stable conclusion?",
}


def main() -> None:
    """Parse command-line arguments and dispatch the selected command.

    Args:
        None.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser(prog="noetic")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo")
    demo.add_argument(
        "--query",
        choices=sorted(QUERIES),
        default="battery",
        help="demo query to run through retrieval and reconciliation",
    )
    demo.add_argument(
        "--diagnostics",
        action="store_true",
        help="show the spectral/diffusion diagnostic path instead of linked chunks",
    )

    llm_demo = subparsers.add_parser("llm-demo")
    llm_demo.add_argument(
        "--query",
        choices=sorted(QUERIES),
        default="battery",
        help="demo query to prepare for the Responses API",
    )
    llm_demo.add_argument(
        "--mode",
        choices=["top-k", "basin", "evidence-field"],
        default="basin",
        help="which LLM input surface to prepare",
    )
    llm_demo.add_argument(
        "--call-api",
        action="store_true",
        help="call the OpenAI Responses API instead of printing the payload",
    )
    llm_demo.add_argument(
        "--model",
        default=None,
        help="OpenAI model id; defaults to NOETIC_OPENAI_MODEL or the client default",
    )

    trace = subparsers.add_parser("trace")
    trace.add_argument(
        "--case",
        default=DEFAULT_TRACE_CASE_ID,
        help=(
            "trace case id to visualize; the default is the HotpotQA Big Stone "
            "Gap case."
        ),
    )
    trace.add_argument(
        "--data-path",
        type=Path,
        default=DEFAULT_TRACE_DATA_PATH,
        help="trace dataset JSON path",
    )
    trace.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_TRACE_PATH,
        help="trace JSON output path consumed by the docs viewer",
    )
    trace.add_argument(
        "--max-points",
        type=int,
        default=500,
        help="maximum corpus points to include in the browser view",
    )
    trace.add_argument(
        "--candidate-limit",
        type=int,
        default=30,
        help="hybrid candidates retrieved and admitted into the local graph",
    )
    trace.add_argument(
        "--hybrid-pool-limit",
        type=int,
        default=100,
        help="semantic and lexical channel depth used before hybrid truncation",
    )
    trace.add_argument(
        "--diffusion-steps",
        type=int,
        default=4,
        help="diffusion time steps to capture",
    )
    trace.add_argument(
        "--edge-threshold",
        type=float,
        default=DEFAULT_TRACE_EDGE_THRESHOLD,
        help="embedding similarity threshold for graph edges",
    )
    trace.add_argument(
        "--labeled",
        action="store_true",
        help="index benchmark labels instead of blind deployable metadata",
    )
    trace.add_argument(
        "--calibrate-graph",
        action="store_true",
        help="derive corpus-level graph weights before generating the trace",
    )
    trace.add_argument(
        "--graph-objective",
        choices=GRAPH_OBJECTIVES,
        default="reference_forward",
        help="label-free objective used with --calibrate-graph",
    )
    trace.add_argument(
        "--calibration-sample",
        type=int,
        default=500,
        help="documents sampled for corpus-level graph calibration",
    )

    args = parser.parse_args()
    if args.command == "demo":
        run_demo(args.query, args.diagnostics)
    elif args.command == "llm-demo":
        run_llm_demo(args.query, args.mode, args.call_api, args.model)
    elif args.command == "trace":
        run_trace(args)


def run_demo(query_name: str, diagnostics: bool) -> None:
    """Run the local reconciliation demo for a named query.

    Args:
        query_name: Key from `QUERIES` identifying the demo query.
        diagnostics: Whether to show basin diagnostics instead of production
            linked chunks.

    Returns:
        None.
    """
    query_text = QUERIES[query_name]

    database = Database(collection_name="noetic_demo", reset=True)
    database.add_documents(demo_corpus())
    demo_weights = GraphWeights(
        semantic_threshold=0.30,
        lexical_threshold=0.01,
        lexical_weight=0.35,
    )
    result = Reconciler(database, graph_weights=demo_weights).reconcile(
        query_text,
        candidate_limit=7,
        include_diagnostics=diagnostics,
    )

    print(f"query: {result.query}")
    print(f"return policy: {result.return_policy}")
    if not diagnostics:
        print()
        print("linked chunks:")
        for index, chunk in enumerate(result.chunks(database, k=5), start=1):
            print(
                f"{index}. {chunk['id']} "
                f"(query={chunk['query_score']:.3f}, support={chunk['support']:.3f})"
            )
        database.reset()
        return

    print(f"winning basin: {result.winner.label} ({result.winner.score:.3f})")
    print(f"basin energy: {result.winner.energy:.3f}")
    print(f"uncertainty: {result.uncertainty:.3f}")
    print(f"modularity: {result.modularity:.3f}")
    print(f"dispersion: {result.dispersion:.3f}")
    print()
    print("basins:")
    for basin in result.basins:
        docs = ", ".join(basin.documents)
        print(
            f"- {basin.label}: score={basin.score:.3f} "
            f"energy={basin.energy:.3f} [{docs}]"
        )

    database.reset()


def run_trace(args: argparse.Namespace) -> None:
    """Generate the browser visualization trace.

    Args:
        args: Parsed CLI arguments for the trace command.

    Returns:
        None.
    """
    trace = generate_trace(
        data_path=args.data_path,
        output_path=args.output,
        case_id=args.case,
        blind=not args.labeled,
        max_points=args.max_points,
        candidate_limit=args.candidate_limit,
        hybrid_pool_limit=args.hybrid_pool_limit,
        diffusion_steps=args.diffusion_steps,
        edge_threshold=args.edge_threshold,
        calibrate_graph=args.calibrate_graph,
        graph_objective=args.graph_objective,
        calibration_sample=args.calibration_sample,
    )
    print(f"wrote trace: {args.output}")
    print(f"case: {trace['case']['id']}")
    print(f"points: {len(trace['points'])}")
    print(f"edges: {len(trace['edges'])}")
    print(f"winner: {trace['winner']['label']} score={trace['winner']['score']:.3f}")


def run_llm_demo(
    query_name: str,
    mode: str,
    call_api: bool,
    model: str | None,
) -> None:
    """Build or send an LLM comparison payload for a demo query.

    Args:
        query_name: Key from `QUERIES` identifying the demo query.
        mode: Retrieval surface to prepare: `top-k`, `basin`, or
            `evidence-field`.
        call_api: Whether to call the Responses API instead of printing the
            request payload.
        model: Optional model id. When omitted, the client default or
            `NOETIC_OPENAI_MODEL` is used.

    Returns:
        None.
    """
    query_text = QUERIES[query_name]
    database = Database(collection_name="noetic_llm_demo", reset=True)
    database.add_documents(demo_corpus())
    experiment = build_llm_experiment(
        database,
        query_text,
        candidate_limit=7,
    )
    client = OpenAIResponsesClient(model=model) if model else OpenAIResponsesClient()
    messages = experiment.messages_for(cast(Mode, mode))
    payload = client.request_payload(messages)

    if call_api:
        print(client.create(messages))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    database.reset()
