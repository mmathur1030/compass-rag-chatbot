from langchain_core.documents import Document

from rag_chatbot.graph import citations_are_valid, explicitly_cross_domain, normalize_citations
from rag_chatbot.retrieval import BM25Index, reciprocal_rank_fusion


def test_bm25_prioritizes_exact_technical_term() -> None:
    documents = [
        Document(page_content="Employees receive paid annual leave."),
        Document(page_content="HTTP 429 responses include a Retry-After header."),
    ]

    results = BM25Index(documents).search("What does HTTP 429 mean?", k=1)

    assert results[0].page_content.startswith("HTTP 429")


def test_rank_fusion_records_both_retrieval_channels() -> None:
    shared = Document(page_content="OAuth 2.0 uses Bearer tokens.", metadata={"source": "tech"})
    other = Document(page_content="Annual leave is paid.", metadata={"source": "hr"})

    results = reciprocal_rank_fusion([shared, other], [shared])

    assert results[0].page_content == shared.page_content
    assert results[0].metadata["retrieval_channels"] == ["dense", "keyword"]


def test_numbered_citations_must_exist_in_context() -> None:
    assert citations_are_valid("Tokens expire after one hour [1].", 2)
    assert not citations_are_valid("Tokens expire after one hour.", 2)
    assert not citations_are_valid("Tokens expire after one hour [3].", 2)


def test_decorative_citation_brackets_are_normalized() -> None:
    assert normalize_citations("Use Bearer tokens【1】.") == "Use Bearer tokens[1]."


def test_explicit_cross_domain_question_is_detected() -> None:
    assert explicitly_cross_domain("Compare the technical and compliance policies.")
    assert not explicitly_cross_domain("How does API authentication work?")
    assert explicitly_cross_domain("When is a terminated employee's system access revoked?")
