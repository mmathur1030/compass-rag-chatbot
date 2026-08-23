import re
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, AnyMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from rag_chatbot.config import Settings
from rag_chatbot.retrieval import HybridRetriever


class RAGState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    context: NotRequired[list[Document]]
    selected_namespaces: NotRequired[list[str]]
    retrieval_score: NotRequired[float]
    refused: NotRequired[bool]
    citation_valid: NotRequired[bool]


NAMESPACES = ("HR", "Technical", "Compliance")


class NamespaceRoute(BaseModel):
    destination: Literal["HR", "Technical", "Compliance", "All"] = Field(
        description="The document namespace most likely to answer the question."
    )


SYSTEM_PROMPT = """You are a helpful assistant answering questions from retrieved documents.
Use the context below as your factual source. If the answer is not in the context, say you do
not know based on the indexed documents. Every factual claim must cite one or more numbered
sources using [1], [2], and so on. Never invent a citation number.

Strict grounding rules:
- Include only claims directly stated in the numbered context.
- Do not add general knowledge, inferred requirements, or recommended best practices.
- Do not strengthen words such as "should" into "must" or "must" into "never."
- Before responding, remove any sentence that cannot be supported by a specific context passage.
- When combining sources, keep each source's requirements separate unless the context explicitly
  connects them.

Context:
{context}
"""

CITATION_REPAIR_PROMPT = """Revise the answer so every factual claim is supported by the
numbered context. Use only citations [1] through [{source_count}]. Do not add facts. Return only
the corrected answer.

Context:
{context}

Answer to correct:
{answer}
"""

REFUSAL_MESSAGE = (
    "I couldn't find sufficiently relevant information in the indexed company documents "
    "to answer that question. Try rephrasing it or ask about HR, technical, or compliance topics."
)

ROUTER_PROMPT = """Classify the user's latest question by the document collection needed.

- HR: employment, benefits, leave, conduct, workplace, performance, or HR policy.
- Technical: systems, architecture, APIs, infrastructure, deployment, or technical documentation.
- Compliance: regulations, audits, controls, privacy, risk, or compliance requirements.
- All: the question crosses collections, is ambiguous, or cannot be assigned confidently.

Use the conversation history to understand follow-up questions. Return only the structured route.
"""


def _format_context(documents: list[Document]) -> str:
    sections = []
    for number, document in enumerate(documents, start=1):
        source = document.metadata.get("source", "unknown")
        page = document.metadata.get("page")
        label = f"{source}, page {page}" if page else str(source)
        sections.append(f"[{number}] {label}\n{document.page_content}")
    return "\n\n".join(sections)


def _namespaces_for_route(destination: str) -> list[str]:
    return list(NAMESPACES) if destination == "All" else [destination]


def explicitly_cross_domain(question: str) -> bool:
    lowered = question.casefold()
    domains = (
        any(term in lowered for term in ("hr", "employee", "leave", "work from home")),
        any(term in lowered for term in ("technical", "api", "webhook", "application credential")),
        any(
            term in lowered
            for term in (
                "compliance",
                "security",
                "audit",
                "privileged access",
                "system access",
                "access revoked",
                "terminated employee",
            )
        ),
    )
    return sum(domains) >= 2


def citations_are_valid(answer: str, source_count: int) -> bool:
    citations = [int(value) for value in re.findall(r"\[(\d+)]", answer)]
    return bool(citations) and all(1 <= citation <= source_count for citation in citations)


def normalize_citations(answer: str) -> str:
    return re.sub(r"【(\d+)】", r"[\1]", answer)


def build_graph(settings: Settings):
    retriever = HybridRetriever(settings)
    model = ChatGroq(model=settings.chat_model, temperature=0)
    router = model.with_structured_output(NamespaceRoute)
    router_prompt = ChatPromptTemplate.from_messages(
        [("system", ROUTER_PROMPT), ("placeholder", "{messages}")]
    )
    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("placeholder", "{messages}")]
    )

    def route_question(state: RAGState) -> dict:
        question = str(state["messages"][-1].content)
        if explicitly_cross_domain(question):
            return {"selected_namespaces": list(NAMESPACES)}
        route = (router_prompt | router).invoke({"messages": state["messages"]})
        return {"selected_namespaces": _namespaces_for_route(route.destination)}

    def retrieve(state: RAGState) -> dict:
        question = str(state["messages"][-1].content)
        result = retriever.retrieve(question, state["selected_namespaces"])
        return {
            "context": result.documents,
            "retrieval_score": result.top_score,
            "refused": result.refused,
        }

    def choose_answer_path(state: RAGState) -> Literal["generate", "refuse"]:
        return "refuse" if state["refused"] else "generate"

    def refuse(_: RAGState) -> dict:
        return {
            "messages": [{"role": "assistant", "content": REFUSAL_MESSAGE}],
            "citation_valid": True,
        }

    def generate(state: RAGState) -> dict:
        response = (prompt | model).invoke(
            {"messages": state["messages"], "context": _format_context(state["context"])}
        )
        return {"messages": [response]}

    def verify_citations(state: RAGState) -> dict:
        answer = normalize_citations(str(state["messages"][-1].content))
        source_count = len(state["context"])
        message_id = state["messages"][-1].id
        if citations_are_valid(answer, source_count):
            return {
                "messages": [AIMessage(content=answer, id=message_id)],
                "citation_valid": True,
            }

        repaired = model.invoke(
            CITATION_REPAIR_PROMPT.format(
                source_count=source_count,
                context=_format_context(state["context"]),
                answer=answer,
            )
        )
        repaired_answer = normalize_citations(str(repaired.content))
        return {
            "messages": [AIMessage(content=repaired_answer, id=message_id)],
            "citation_valid": citations_are_valid(repaired_answer, source_count),
        }

    workflow = StateGraph(RAGState)
    workflow.add_node("route_question", route_question)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("refuse", refuse)
    workflow.add_node("generate", generate)
    workflow.add_node("verify_citations", verify_citations)
    workflow.add_edge(START, "route_question")
    workflow.add_edge("route_question", "retrieve")
    workflow.add_conditional_edges("retrieve", choose_answer_path)
    workflow.add_edge("refuse", END)
    workflow.add_edge("generate", "verify_citations")
    workflow.add_edge("verify_citations", END)
    return workflow.compile(checkpointer=InMemorySaver())
