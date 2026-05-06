"""Command-line interface for demos and LLM payload inspection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from noetic_systems.corpus import demo_corpus
from noetic_systems.database import Database
from noetic_systems.llm.experiment import build_llm_experiment
from noetic_systems.llm.openai_client import OpenAIResponsesClient
from noetic_systems.reconciliation.engine import Reconciler
from noetic_systems.trace import (
    DEFAULT_TRACE_EDGE_THRESHOLD,
    DEFAULT_TRACE_PATH,
    MULTI_BASIN_TRACE_CASE_ID,
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
        default=MULTI_BASIN_TRACE_CASE_ID,
        help=(
            "trace case id to visualize; the default is a built-in multi-basin "
            "teaching case"
        ),
    )
    trace.add_argument(
        "--data-path",
        type=Path,
        default=Path("tests/data/hard_rag_benchmark.json"),
        help="hard benchmark JSON path",
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
        default=50,
        help="hybrid candidates to retrieve for the trace",
    )
    trace.add_argument(
        "--result-limit",
        type=int,
        default=36,
        help="candidates admitted into the local graph",
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

    args = parser.parse_args()
    if args.command == "demo":
        run_demo(args.query)
    elif args.command == "llm-demo":
        run_llm_demo(args.query, args.mode, args.call_api, args.model)
    elif args.command == "trace":
        run_trace(args)


def run_demo(query_name: str) -> None:
    """Run the local reconciliation demo for a named query.

    Args:
        query_name: Key from `QUERIES` identifying the demo query.

    Returns:
        None.
    """
    query_text = QUERIES[query_name]

    database = Database(collection_name="noetic_demo", reset=True)
    database.add_documents(demo_corpus())
    result = Reconciler(database).reconcile(query_text, candidate_limit=7, result_limit=7)

    print(f"query: {result.query}")
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
        result_limit=args.result_limit,
        diffusion_steps=args.diffusion_steps,
        edge_threshold=args.edge_threshold,
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
        result_limit=7,
    )
    client = OpenAIResponsesClient(model=model) if model else OpenAIResponsesClient()
    messages = experiment.messages_for(mode)  # type: ignore[arg-type]
    payload = client.request_payload(messages)

    if call_api:
        print(client.create(messages))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    database.reset()
