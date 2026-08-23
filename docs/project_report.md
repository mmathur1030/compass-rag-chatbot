# Compass: Enterprise Policy Q&A Bot

## Project overview

Compass is a RAG chatbot that helps ACME employees answer HR, technical, and compliance
questions from three sample enterprise policy manuals through a Streamlit interface. The system
was designed for at least 90% correct-source retrieval, 95% answer faithfulness, 100% valid
citations and refusals, and an 8-second p95 response time.

The project follows the code-heavy LangChain and LangGraph track. Pinecone provides hosted
embeddings, vector storage, and reranking, while Groq hosts the language model used for routing,
answer generation, citation repair, and evaluation judging.

## RAG framework

| Field | Decision |
|---|---|
| Use case | Employees ask policy, platform, and compliance questions in an internal Streamlit chatbot and receive answers grounded in approved documents. |
| Corpus | Three English UTF-8 sample ACME manuals in TXT format: an HR policy manual, a platform technical guide, and a compliance and security manual. |
| Ingestion and cleaning | The loader supports TXT, Markdown, and text-based PDF files. It removes empty documents, preserves Unicode, and attaches source, page (for PDFs), and chunk start metadata. |
| Ingestion and freshness | Ingestion is run manually from the command line. SHA-256 chunk IDs make re-ingesting unchanged content idempotent within a namespace; automated synchronization and stale-chunk deletion remain production work. |
| Chunking and embedding | A recursive character splitter creates 1,000-character chunks with 200-character overlap. Pinecone `multilingual-e5-large` converts each chunk into a 1,024-dimensional vector. |
| Storage | Pinecone index `compass-documents` separates content into `HR`, `Technical`, and `Compliance` namespaces. |
| Retrieval | Each selected namespace returns up to eight dense and eight local BM25 candidates. Reciprocal-rank fusion combines the rankings, Pinecone `bge-reranker-v2-m3` reranks the unique candidates, and the best four chunks become context. |
| Routing | A LangGraph node selects HR, Technical, Compliance, or All. Explicit cross-domain wording is also detected deterministically; All searches every namespace and preserves namespace diversity in the final context. |
| Refusal | If the highest reranker relevance score is below `0.05`, the graph returns a deterministic message explaining that the indexed documents do not contain enough relevant information. |
| Generation and citations | Groq-hosted `openai/gpt-oss-20b` answers only from numbered context blocks. A verification node normalizes citation formatting, checks citation numbers against the retrieved context, and requests a repair when necessary. |
| Conversation state | LangGraph's in-memory checkpointer stores message history under a thread ID so routing can interpret follow-up questions during the current process. |
| Evaluation | A fixed 15-question gold set measures routing, correct-source retrieval, keyword coverage, refusal behavior, citation validity, LLM-judged faithfulness, and end-to-end latency. |

## Dataset used

The corpus contains 26 indexed chunks across three namespaces:

| Namespace | Source | Content | Chunks |
|---|---|---|---:|
| HR | `data/hr/hr_policy.txt` | Leave, remote work, conduct, reviews, benefits, onboarding, discipline, and grievances | 8 |
| Technical | `data/technical/tech_docs.txt` | API authentication, rate limits, errors, architecture, deployment, database schema, webhooks, SDKs, and SLA | 9 |
| Compliance | `data/compliance/compliance_manual.txt` | Privacy, security, incidents, vendors, audits, acceptable use, access controls, and disaster recovery | 9 |

These are small sample manuals, not live corporate systems of record. They are suitable for
demonstrating and evaluating the pipeline, but not for drawing production-scale conclusions.

## End-to-end workflow

1. Load the TXT, Markdown, or PDF source files and discard empty content.
2. Split the text into overlapping chunks and attach source metadata.
3. Create a deterministic ID for every chunk.
4. Generate hosted embeddings and upsert the vectors into the appropriate Pinecone namespace.
5. Route each user question to one namespace or all three namespaces.
6. Run semantic dense search and exact-term BM25 search over the selected content.
7. Fuse both rankings, remove duplicate candidates, and rerank them globally.
8. Refuse the question when the best reranked evidence is below the relevance threshold.
9. Otherwise, send the four best numbered context chunks to the Groq model.
10. Validate the model's numbered citations and repair citation formatting when required.
11. Display the answer, searched namespaces, and sources in Streamlit.

## Prompts and agent instructions

The router prompt defines the four destinations and tells the model to use conversation history
for follow-up questions. Questions that span domains, are ambiguous, or cannot be confidently
assigned are routed to All.

The answer-generation prompt instructs the model to treat retrieved context as its only factual
source. Every factual claim must cite a numbered source. It also prohibits adding general
knowledge, inferring unstated requirements, strengthening modal language such as “should” into
“must,” or merging requirements from separate sources unless the documents explicitly connect
them.

The citation-repair prompt permits only citation numbers that exist in the current context and
instructs the model to remove unsupported facts rather than invent evidence. The faithfulness
judge is separately instructed to score factual support only, not writing quality.

The complete prompt text is version-controlled in `src/rag_chatbot/graph.py` and
`src/rag_chatbot/evaluation.py`.

## Evaluation design

The gold set contains 15 questions: nine direct or exact-term questions, two cross-document
questions, two ambiguous questions, and two questions the corpus cannot answer. Each example
declares its expected namespace, source file, key answer facts, and whether it should be
answerable.

Correct-source hit rate checks whether all expected files occur in the final retrieved context.
Keyword coverage checks for expected facts after Unicode and dash normalization. Citation
validity checks that the answer contains numbered citations and that every citation number maps
to a retrieved context block. Faithfulness is graded by the same Groq-hosted model using the
retrieved text; it is therefore an automated LLM-as-judge measurement, not a human audit.

## Final golden-test results

The final run in `evaluations/golden_run/` produced the following results:

| Metric | Target | Result | Status |
|---|---:|---:|---|
| Router accuracy | >= 90% | 100.0% | Met |
| Correct-source hit rate | >= 90% | 100.0% | Met |
| Answer faithfulness | >= 95% | 100.0% | Met |
| Citation validity | 100% | 100.0% | Met |
| Correct refusal | 100% | 100.0% | Met |
| Answer keyword coverage | No fixed target | 87.2% | Observed |
| Average response latency | No fixed target | 5.04 seconds | Observed |
| p95 response latency | <= 8 seconds | 12.78 seconds | **Not met** |

All 15 questions passed the current functional rubric. Dense-only and hybrid retrieval both
achieved a 100% correct-source hit rate on this small test corpus. Consequently, this run does
not demonstrate a measurable retrieval win from hybrid search; exact identifiers and a larger,
more confusable corpus are needed for a meaningful comparison.

The only missed target was tail latency. Questions routed to all three namespaces were the
slowest because they perform more Pinecone searches and rerank a larger candidate pool before
generation. The p95 result is based on only 15 sequential requests and can also vary with hosted
service and network conditions.

## Architecture iterations

1. The initial Chroma and OpenAI scaffold was replaced with Pinecone and Groq because those were
   the selected services and no OpenAI API key was available.
2. Pinecone hosted embeddings were configured with a vector dimension matching the index.
3. One default namespace was replaced by HR, Technical, and Compliance namespaces.
4. A LangGraph router was added to avoid searching unrelated collections for every question.
5. Local BM25, reciprocal-rank fusion, and Pinecone reranking were added to improve both
   exact-term and semantic retrieval.
6. A score threshold and deterministic refusal path were added for unsupported questions.
7. Numbered context blocks and a citation-verification node were added for traceability.
8. A modern Streamlit chat interface was added as the user-facing surface.
9. A 15-question checkpointed evaluation harness was added, including dense-versus-hybrid
   comparison and automated failure classification.
10. One cross-domain answer originally added an unsupported security claim. The grounding prompt
    was tightened to prohibit inferred best practices and require sentence-level support; the
    failed case was rerun and then passed the faithfulness judge.

## Learnings and observations

- Retrieval quality needs explicit testing; a plausible answer alone does not show that the
  correct evidence was found.
- Namespaces reduce the search space for focused questions, while cross-domain questions require
  both multi-namespace retrieval and deliberate source diversity.
- Dense retrieval and BM25 solve different problems, but a small, easy corpus can hide the
  benefit of hybrid retrieval.
- Valid citation numbers do not by themselves guarantee factual support, so citation validation
  and faithfulness evaluation serve different purposes.
- A relevance threshold creates a useful “I don't know” path, but it must be recalibrated when
  the corpus, embedding model, or reranker changes.
- Strict wording in the generation prompt materially reduced unsupported inference.
- Tail latency, rather than average latency, is the remaining performance concern.

## Known limitations and next steps

- Store source documents in durable object storage and automate ingestion after updates.
- Track document versions and delete stale Pinecone chunks when a source changes or is removed.
- Replace the in-memory LangGraph checkpointer with durable conversation storage.
- Calibrate the relevance threshold on a larger labeled set and report precision/recall for
  answer-versus-refusal decisions.
- Expand the corpus and gold set, then measure recall at k, ranking quality, and hybrid/reranking
  lift rather than only correct-source presence.
- Add human review or an independent judge model for faithfulness and citation correctness.
- Reduce p95 latency through parallel multi-namespace retrieval, caching, and profiling of model
  and reranker calls.
- Add authentication, authorization, audit logging, secret management, and document-level access
  controls before using real enterprise material.

## Reproducing the evaluation

After installing dependencies, configuring `.env`, and indexing the three namespaces, run:

```bash
uv run pytest -q
uv run rag-evaluate --output evaluations/golden_run
```

The detailed Markdown report, JSON results, retrieval comparison, and checkpoint are stored in
`evaluations/golden_run/`.
