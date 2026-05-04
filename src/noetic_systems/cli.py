from __future__ import annotations

import argparse
import json

from .corpus import demo_corpus
from .database import Database
from .llm import OpenAIResponsesClient, build_llm_experiment
from .reconciliation import Reconciler


QUERIES = {
    "battery": "Should I trust the battery life claims?",
    "camera": "Is the camera actually good?",
    "value": "Is this device a good value?",
    "balanced": "What is the overall stable conclusion?",
}


def main() -> None:
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
