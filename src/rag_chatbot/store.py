import os

from langchain_pinecone import PineconeEmbeddings, PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from rag_chatbot.config import Settings


def create_vector_store(
    settings: Settings, *, namespace: str | None = None
) -> PineconeVectorStore:
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY is missing; add it to your .env file")

    client = Pinecone(api_key=api_key)
    if not client.has_index(settings.pinecone_index):
        client.create_index(
            name=settings.pinecone_index,
            dimension=settings.pinecone_dimension,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=settings.pinecone_cloud,
                region=settings.pinecone_region,
            ),
        )

    return PineconeVectorStore(
        index=client.Index(settings.pinecone_index),
        embedding=PineconeEmbeddings(model=settings.embedding_model),
        namespace=namespace or settings.pinecone_namespace,
    )
