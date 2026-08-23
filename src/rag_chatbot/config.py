import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    chat_model: str
    embedding_model: str
    pinecone_index: str
    pinecone_namespace: str
    pinecone_cloud: str
    pinecone_region: str
    pinecone_dimension: int
    retrieval_k: int
    retrieval_candidate_k: int
    rerank_model: str
    relevance_threshold: float


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        chat_model=os.getenv("CHAT_MODEL", "openai/gpt-oss-20b"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "multilingual-e5-large"),
        pinecone_index=os.getenv("PINECONE_INDEX", "compass-documents"),
        pinecone_namespace=os.getenv("PINECONE_NAMESPACE", "default"),
        pinecone_cloud=os.getenv("PINECONE_CLOUD", "aws"),
        pinecone_region=os.getenv("PINECONE_REGION", "us-east-1"),
        pinecone_dimension=int(os.getenv("PINECONE_DIMENSION", "1024")),
        retrieval_k=int(os.getenv("RETRIEVAL_K", "4")),
        retrieval_candidate_k=int(os.getenv("RETRIEVAL_CANDIDATE_K", "8")),
        rerank_model=os.getenv("RERANK_MODEL", "bge-reranker-v2-m3"),
        relevance_threshold=float(os.getenv("RELEVANCE_THRESHOLD", "0.05")),
    )
