from pathlib import Path

from rag_chatbot.graph import _namespaces_for_route
from rag_chatbot.ingest import load_documents


def test_loads_text_and_ignores_unsupported_files(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("Useful knowledge", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"not an image")

    documents = load_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0].page_content == "Useful knowledge"
    assert documents[0].metadata["source"].endswith("notes.md")


def test_all_route_expands_to_every_namespace() -> None:
    assert _namespaces_for_route("All") == ["HR", "Technical", "Compliance"]


def test_specific_route_uses_only_that_namespace() -> None:
    assert _namespaces_for_route("HR") == ["HR"]
