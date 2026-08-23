import re
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from math import log
from pathlib import Path

from langchain_core.documents import Document
from langchain_pinecone import PineconeRerank

from rag_chatbot.config import Settings
from rag_chatbot.ingest import load_documents, split_documents
from rag_chatbot.store import create_vector_store

NAMESPACE_PATHS = {
    "HR": Path("data/hr"),
    "Technical": Path("data/technical"),
    "Compliance": Path("data/compliance"),
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_.-]*", text.lower())


def document_key(document: Document) -> str:
    identity = (
        f"{document.metadata.get('source')}:{document.metadata.get('page')}:"
        f"{document.metadata.get('start_index')}:{document.page_content}"
    )
    return sha256(identity.encode()).hexdigest()


class BM25Index:
    def __init__(self, documents: list[Document], *, k1: float = 1.5, b: float = 0.75):
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.tokenized = [_tokens(document.page_content) for document in documents]
        self.lengths = [len(tokens) for tokens in self.tokenized]
        self.average_length = sum(self.lengths) / max(len(self.lengths), 1)
        self.frequencies = [Counter(tokens) for tokens in self.tokenized]
        self.document_frequency = Counter(
            token for tokens in self.tokenized for token in set(tokens)
        )

    def search(self, query: str, *, k: int) -> list[Document]:
        query_tokens = _tokens(query)
        scores: list[tuple[float, int]] = []
        corpus_size = len(self.documents)
        for index, frequencies in enumerate(self.frequencies):
            score = 0.0
            for token in query_tokens:
                frequency = frequencies[token]
                if not frequency:
                    continue
                doc_frequency = self.document_frequency[token]
                inverse_frequency = log(
                    1 + (corpus_size - doc_frequency + 0.5) / (doc_frequency + 0.5)
                )
                length_factor = self.k1 * (
                    1 - self.b + self.b * self.lengths[index] / self.average_length
                )
                score += inverse_frequency * frequency * (self.k1 + 1) / (
                    frequency + length_factor
                )
            if score > 0:
                scores.append((score, index))
        scores.sort(reverse=True)
        return [self.documents[index] for _, index in scores[:k]]


def reciprocal_rank_fusion(
    dense_documents: list[Document], keyword_documents: list[Document], *, rank_constant: int = 60
) -> list[Document]:
    documents: dict[str, Document] = {}
    scores: Counter[str] = Counter()
    channels: dict[str, set[str]] = {}

    for channel, ranked_documents in (
        ("dense", dense_documents),
        ("keyword", keyword_documents),
    ):
        for rank, document in enumerate(ranked_documents, start=1):
            key = document_key(document)
            documents[key] = document
            scores[key] += 1 / (rank_constant + rank)
            channels.setdefault(key, set()).add(channel)
            document.metadata[f"{channel}_rank"] = rank

    ordered_keys = sorted(scores, key=scores.get, reverse=True)
    for key in ordered_keys:
        documents[key].metadata["fusion_score"] = scores[key]
        documents[key].metadata["retrieval_channels"] = sorted(channels[key])
    return [documents[key] for key in ordered_keys]


@dataclass
class RetrievalResult:
    documents: list[Document]
    candidates: list[Document]
    top_score: float
    refused: bool


class HybridRetriever:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.vector_stores = {
            namespace: create_vector_store(settings, namespace=namespace)
            for namespace in NAMESPACE_PATHS
        }
        self.keyword_indexes = {
            namespace: BM25Index(split_documents(load_documents(path)))
            for namespace, path in NAMESPACE_PATHS.items()
        }
        self.reranker = PineconeRerank(
            model=settings.rerank_model,
            top_n=max(settings.retrieval_candidate_k, settings.retrieval_k),
        )

    def _select_final_documents(
        self, reranked: list[Document], namespaces: list[str]
    ) -> list[Document]:
        selected: list[Document] = []
        selected_keys: set[str] = set()
        if len(namespaces) > 1:
            for namespace in namespaces:
                match = next(
                    (
                        document
                        for document in reranked
                        if document.metadata.get("namespace") == namespace
                    ),
                    None,
                )
                if match:
                    selected.append(match)
                    selected_keys.add(document_key(match))

        for document in reranked:
            if len(selected) >= self.settings.retrieval_k:
                break
            key = document_key(document)
            if key not in selected_keys:
                selected.append(document)
                selected_keys.add(key)
        return selected

    def retrieve(
        self,
        query: str,
        namespaces: list[str],
        *,
        mode: str = "hybrid",
        apply_threshold: bool = True,
        apply_rerank: bool = True,
    ) -> RetrievalResult:
        candidates: list[Document] = []
        for namespace in namespaces:
            dense = self.vector_stores[namespace].similarity_search(
                query, k=self.settings.retrieval_candidate_k
            )
            for document in dense:
                document.metadata["namespace"] = namespace

            keyword: list[Document] = []
            if mode == "hybrid":
                keyword = self.keyword_indexes[namespace].search(
                    query, k=self.settings.retrieval_candidate_k
                )
                for document in keyword:
                    document.metadata["namespace"] = namespace

            candidates.extend(reciprocal_rank_fusion(dense, keyword))

        unique_candidates = list({document_key(doc): doc for doc in candidates}.values())
        if not apply_rerank:
            top_score = max(
                (float(doc.metadata.get("fusion_score", 0)) for doc in unique_candidates),
                default=0.0,
            )
            return RetrievalResult(
                documents=self._select_final_documents(unique_candidates, namespaces),
                candidates=unique_candidates,
                top_score=top_score,
                refused=False,
            )
        reranked = list(self.reranker.compress_documents(unique_candidates, query))
        top_score = float(reranked[0].metadata.get("relevance_score", 0)) if reranked else 0.0
        refused = not reranked or (
            apply_threshold and top_score < self.settings.relevance_threshold
        )
        return RetrievalResult(
            documents=[] if refused else self._select_final_documents(reranked, namespaces),
            candidates=unique_candidates,
            top_score=top_score,
            refused=refused,
        )
