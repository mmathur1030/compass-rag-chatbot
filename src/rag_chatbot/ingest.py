from hashlib import sha256
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from rag_chatbot.config import Settings
from rag_chatbot.store import create_vector_store

SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf"}


def load_documents(path: Path) -> list[Document]:
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    documents: list[Document] = []

    for file in files:
        suffix = file.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            continue
        if suffix == ".pdf":
            reader = PdfReader(file)
            documents.extend(
                Document(
                    page_content=page.extract_text() or "",
                    metadata={"source": str(file), "page": index + 1},
                )
                for index, page in enumerate(reader.pages)
            )
        else:
            documents.append(
                Document(page_content=file.read_text(encoding="utf-8"), metadata={"source": str(file)})
            )

    return [document for document in documents if document.page_content.strip()]


def ingest_path(path: Path, settings: Settings) -> int:
    documents = load_documents(path)
    if not documents:
        raise ValueError(f"No supported documents found at {path} (use .txt, .md, or .pdf)")

    chunks = split_documents(documents)
    ids = [
        sha256(
            (
                f"{chunk.metadata.get('source')}:{chunk.metadata.get('page')}:"
                f"{chunk.metadata.get('start_index')}:{chunk.page_content}"
            ).encode()
        ).hexdigest()
        for chunk in chunks
    ]
    create_vector_store(settings).add_documents(chunks, ids=ids)
    return len(chunks)


def split_documents(documents: list[Document]) -> list[Document]:
    return RecursiveCharacterTextSplitter(
        chunk_size=1_000,
        chunk_overlap=200,
        add_start_index=True,
    ).split_documents(documents)
