"""Command-line interface for demos and LLM payload inspection."""

from __future__ import annotations

import argparse
import json

from noetic_systems.corpus import demo_corpus
from noetic_systems.database import Database
from noetic_systems.llm.experiment import build_llm_experiment
from noetic_systems.llm.openai_client import OpenAIResponsesClient
from noetic_systems.reconciliation.engine import Reconciler


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

    args = parser.parse_args()
    if args.command == "demo":
        run_demo(args.query)
    elif args.command == "llm-demo":
        run_llm_demo(args.query, args.mode, args.call_api, args.model)


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
