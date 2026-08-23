import argparse
import sys
from pathlib import Path
from uuid import uuid4

from langchain_core.messages import HumanMessage

from rag_chatbot.config import get_settings
from rag_chatbot.graph import build_graph
from rag_chatbot.ingest import ingest_path


def _chat() -> None:
    graph = build_graph(get_settings())
    config = {"configurable": {"thread_id": str(uuid4())}}
    print("RAG chat ready. Type 'quit' to exit.")
    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if question.lower() in {"quit", "exit"}:
            return
        if not question:
            continue
        result = graph.invoke({"messages": [HumanMessage(content=question)]}, config=config)
        print(f"\nSearched: {', '.join(result['selected_namespaces'])}")
        print(f"\nAssistant: {result['messages'][-1].content}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index documents and chat with them.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest", help="Index a file or directory")
    ingest_parser.add_argument("path", type=Path)
    subparsers.add_parser("chat", help="Start an interactive RAG chat")
    args = parser.parse_args()

    try:
        if args.command == "ingest":
            count = ingest_path(args.path, get_settings())
            print(f"Indexed {count} chunks from {args.path}")
        else:
            _chat()
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
