import argparse
import json
import unicodedata
from pathlib import Path
from statistics import mean
from time import perf_counter, sleep
from typing import TypedDict

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from rag_chatbot.config import Settings, get_settings
from rag_chatbot.graph import NAMESPACES, build_graph
from rag_chatbot.retrieval import HybridRetriever


class EvaluationQuestion(TypedDict):
    id: str
    category: str
    question: str
    expected_namespaces: list[str]
    expected_sources: list[str]
    expected_keywords: list[str]
    answerable: bool


class FaithfulnessGrade(BaseModel):
    score: float = Field(ge=0, le=1)
    explanation: str


FAITHFULNESS_PROMPT = """Grade whether the answer is supported by the supplied context.
Score 1.0 only when every factual claim is supported, 0.5 when some claims are unsupported,
and 0.0 when the answer contradicts or ignores the context. Do not grade writing quality.

Context:
{context}

Answer:
{answer}
"""


def load_questions(path: Path) -> list[EvaluationQuestion]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_names(documents) -> set[str]:
    return {Path(str(document.metadata.get("source", ""))).name for document in documents}


def _keyword_coverage(answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    normalized = _normalize_text(answer)
    return sum(_normalize_text(keyword) in normalized for keyword in keywords) / len(keywords)


def _normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    for dash in "‐‑‒–—―−":
        value = value.replace(dash, "-")
    value = " ".join(value.split())
    return value.replace(" %", "%")


def _failure_cause(result: dict) -> str | None:
    if not result["route_correct"]:
        return "namespace routing"
    if result["answerable"] and result["refused"]:
        return "relevance threshold rejected an answerable query"
    if not result["answerable"] and not result["refused"]:
        return "unanswerable query was not refused"
    if result["answerable"] and not result["source_hit"]:
        return "correct source missing from retrieved context"
    if result["answerable"] and result["keyword_coverage"] < 0.5:
        return "answer omitted expected facts"
    if not result["citation_valid"]:
        return "invalid or missing citation"
    faithfulness = result.get("faithfulness")
    if faithfulness is not None and faithfulness < 0.95:
        return "answer faithfulness below target"
    return None


def compare_retrieval(
    questions: list[EvaluationQuestion], settings: Settings
) -> list[dict]:
    retriever = HybridRetriever(settings)
    rows = []
    for item in questions:
        namespaces = item["expected_namespaces"] or list(NAMESPACES)
        row = {"id": item["id"], "answerable": item["answerable"]}
        for mode in ("dense", "hybrid"):
            started = perf_counter()
            result = retriever.retrieve(
                item["question"],
                namespaces,
                mode=mode,
                apply_threshold=False,
                apply_rerank=False,
            )
            found_sources = _source_names(result.documents)
            row[mode] = {
                "source_hit": all(
                    expected in found_sources for expected in item["expected_sources"]
                ),
                "top_score": result.top_score,
                "latency_seconds": perf_counter() - started,
            }
        rows.append(row)
    return rows


def run_full_evaluation(
    questions: list[EvaluationQuestion],
    settings: Settings,
    *,
    judge: bool,
    checkpoint_path: Path,
    rerun_ids: set[str] | None = None,
) -> list[dict]:
    graph = build_graph(settings)
    faithfulness_judge = None
    if judge:
        faithfulness_judge = ChatGroq(model=settings.chat_model, temperature=0).with_structured_output(
            FaithfulnessGrade
        )

    rows = []
    if checkpoint_path.exists():
        rows = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if rerun_ids:
        rows = [row for row in rows if row["id"] not in rerun_ids]
    for row in rows:
        row["keyword_coverage"] = _keyword_coverage(row["answer"], row["expected_keywords"])
        row["failure_cause"] = _failure_cause(row)
    completed_ids = {row["id"] for row in rows}
    for index, item in enumerate(questions):
        if item["id"] in completed_ids:
            continue
        started = perf_counter()
        state = graph.invoke(
            {"messages": [HumanMessage(content=item["question"])]},
            config={"configurable": {"thread_id": f"evaluation-{index}"}},
        )
        latency = perf_counter() - started
        answer = str(state["messages"][-1].content)
        selected = state["selected_namespaces"]
        documents = state.get("context", [])
        expected_namespaces = set(item["expected_namespaces"])
        route_correct = not expected_namespaces or expected_namespaces.issubset(selected)
        found_sources = _source_names(documents)
        source_hit = all(source in found_sources for source in item["expected_sources"])

        faithfulness = None
        faithfulness_explanation = None
        if faithfulness_judge and item["answerable"] and not state["refused"]:
            context = "\n\n".join(document.page_content for document in documents)
            try:
                grade = faithfulness_judge.invoke(
                    FAITHFULNESS_PROMPT.format(context=context, answer=answer)
                )
                faithfulness = grade.score
                faithfulness_explanation = grade.explanation
            except Exception as error:  # noqa: BLE001 - preserve evaluation progress
                faithfulness_explanation = f"Judge unavailable: {error}"

        row = {
            **item,
            "selected_namespaces": selected,
            "route_correct": route_correct,
            "retrieved_sources": sorted(found_sources),
            "retrieved_context": [document.page_content for document in documents],
            "source_hit": source_hit,
            "retrieval_score": state.get("retrieval_score", 0),
            "refused": state.get("refused", False),
            "refusal_correct": state.get("refused", False) == (not item["answerable"]),
            "answer": answer,
            "keyword_coverage": _keyword_coverage(answer, item["expected_keywords"]),
            "citation_valid": state.get("citation_valid", False),
            "faithfulness": faithfulness,
            "faithfulness_explanation": faithfulness_explanation,
            "latency_seconds": latency,
        }
        row["failure_cause"] = _failure_cause(row)
        rows.append(row)
        checkpoint_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(
            f"[{index + 1:02}/{len(questions)}] {item['id']}: "
            f"{row['failure_cause'] or 'pass'}",
            flush=True,
        )
    return rows


def judge_existing_results(
    rows: list[dict], settings: Settings, *, checkpoint_path: Path, delay: float
) -> list[dict]:
    judge = ChatGroq(model=settings.chat_model, temperature=0).with_structured_output(
        FaithfulnessGrade
    )
    retriever = HybridRetriever(settings)
    for row in rows:
        row["keyword_coverage"] = _keyword_coverage(row["answer"], row["expected_keywords"])
        row["failure_cause"] = _failure_cause(row)
    for index, row in enumerate(rows):
        if not row["answerable"] or row["refused"] or row.get("faithfulness") is not None:
            continue
        context = "\n\n".join(row.get("retrieved_context", []))
        if not context:
            retrieved = retriever.retrieve(row["question"], row["selected_namespaces"])
            row["retrieved_context"] = [doc.page_content for doc in retrieved.documents]
            context = "\n\n".join(row["retrieved_context"])
        try:
            grade = judge.invoke(FAITHFULNESS_PROMPT.format(context=context, answer=row["answer"]))
            row["faithfulness"] = grade.score
            row["faithfulness_explanation"] = grade.explanation
            row["failure_cause"] = _failure_cause(row)
            print(f"[judge {index + 1:02}/{len(rows)}] {row['id']}: {grade.score:.0%}", flush=True)
        except Exception as error:  # noqa: BLE001 - preserve partial judge results
            row["faithfulness_explanation"] = f"Judge unavailable: {error}"
            print(f"[judge {index + 1:02}/{len(rows)}] {row['id']}: unavailable", flush=True)
        checkpoint_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        sleep(delay)
    return rows


def summarize(rows: list[dict]) -> dict:
    judged = [row["faithfulness"] for row in rows if row["faithfulness"] is not None]
    latencies = sorted(row["latency_seconds"] for row in rows)
    p95_index = max(0, int(0.95 * len(latencies) + 0.999) - 1)
    return {
        "questions": len(rows),
        "router_accuracy": mean(row["route_correct"] for row in rows),
        "source_hit_rate": mean(row["source_hit"] for row in rows if row["answerable"]),
        "answer_keyword_coverage": mean(
            row["keyword_coverage"] for row in rows if row["answerable"]
        ),
        "refusal_accuracy": mean(row["refusal_correct"] for row in rows),
        "citation_validity": mean(row["citation_valid"] for row in rows),
        "faithfulness": mean(judged) if judged else None,
        "average_latency_seconds": mean(latencies),
        "p95_latency_seconds": latencies[p95_index],
        "passed": sum(row["failure_cause"] is None for row in rows),
    }


def write_markdown_report(path: Path, summary: dict, rows: list[dict], comparison: list[dict]) -> None:
    dense_hits = mean(row["dense"]["source_hit"] for row in comparison if row["answerable"])
    hybrid_hits = mean(row["hybrid"]["source_hit"] for row in comparison if row["answerable"])
    lines = [
        "# Compass RAG Evaluation Report",
        "",
        "## Summary",
        "",
        "| Metric | Result | Target |",
        "|---|---:|---:|",
        f"| Router accuracy | {summary['router_accuracy']:.1%} | 90% |",
        f"| Correct-source hit rate | {summary['source_hit_rate']:.1%} | 90% |",
        f"| Answer keyword coverage | {summary['answer_keyword_coverage']:.1%} | — |",
        f"| Refusal accuracy | {summary['refusal_accuracy']:.1%} | 100% |",
        f"| Citation validity | {summary['citation_validity']:.1%} | 100% |",
        f"| Faithfulness | {summary['faithfulness']:.1%} | 95% |"
        if summary["faithfulness"] is not None
        else "| Faithfulness | Not judged | 95% |",
        f"| Average latency | {summary['average_latency_seconds']:.2f}s | — |",
        f"| p95 latency | {summary['p95_latency_seconds']:.2f}s | 8.00s |",
        "",
        "## Dense versus hybrid retrieval",
        "",
        f"- Dense correct-source hit rate: **{dense_hits:.1%}**",
        f"- Hybrid correct-source hit rate: **{hybrid_hits:.1%}**",
        "",
        "## Question-level results",
        "",
        "| ID | Type | Route | Source | Refusal | Citations | Faithfulness | Latency | Failure |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        faithfulness = (
            f"{row['faithfulness']:.0%}" if row["faithfulness"] is not None else "—"
        )
        lines.append(
            f"| {row['id']} | {row['category']} | {'✓' if row['route_correct'] else '✗'} "
            f"| {'✓' if row['source_hit'] else '✗'} | {'✓' if row['refusal_correct'] else '✗'} "
            f"| {'✓' if row['citation_valid'] else '✗'} | {faithfulness} "
            f"| {row['latency_seconds']:.2f}s | {row['failure_cause'] or '—'} |"
        )
    lines.extend(["", "## Failure analysis", ""])
    failures = [row for row in rows if row["failure_cause"]]
    if not failures:
        lines.append("No failures under the current rubric.")
    else:
        for row in failures:
            lines.append(f"- **{row['id']}**: {row['failure_cause']}.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the Compass RAG pipeline.")
    parser.add_argument("--questions", type=Path, default=Path("evaluations/questions.json"))
    parser.add_argument("--output", type=Path, default=Path("evaluations/results"))
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument("--judge-only", action="store_true")
    parser.add_argument("--judge-delay", type=float, default=2.0)
    parser.add_argument("--rerun", action="append", default=[])
    args = parser.parse_args()

    questions = load_questions(args.questions)
    settings = get_settings()
    args.output.mkdir(parents=True, exist_ok=True)
    comparison_path = args.output / "retrieval_comparison.json"
    if comparison_path.exists():
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    else:
        comparison = compare_retrieval(questions, settings)
        comparison_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    checkpoint_path = args.output / "evaluation_checkpoint.json"
    if args.judge_only:
        if not checkpoint_path.exists():
            raise SystemExit("No evaluation checkpoint exists; run the evaluation first.")
        rows = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        rows = judge_existing_results(
            rows, settings, checkpoint_path=checkpoint_path, delay=args.judge_delay
        )
    else:
        rows = run_full_evaluation(
            questions,
            settings,
            judge=not args.skip_judge,
            checkpoint_path=checkpoint_path,
            rerun_ids=set(args.rerun),
        )
    summary = summarize(rows)
    (args.output / "evaluation_results.json").write_text(
        json.dumps({"summary": summary, "results": rows}, indent=2), encoding="utf-8"
    )
    write_markdown_report(args.output / "evaluation_report.md", summary, rows, comparison)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
