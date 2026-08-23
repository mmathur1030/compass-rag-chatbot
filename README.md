# Compass RAG chatbot

A measured enterprise RAG application built with LangChain, LangGraph, Pinecone, and Groq. It
routes questions across HR, Technical, and Compliance collections; combines dense and BM25
retrieval; reranks candidates; refuses low-confidence questions; and produces verified numbered
citations.

## Setup

1. Install dependencies (this also creates `.venv`):

   ```bash
   uv sync --extra dev
   ```

2. Create your local environment file and add your Groq and Pinecone API keys:

   ```bash
   cp .env.example .env
   ```

3. Put documents in a folder such as `data/`, then index them:

   ```bash
   uv run rag-chat ingest data
   ```

4. Start chatting:

   ```bash
   uv run rag-chat chat
   ```

   Or launch the Streamlit interface:

   ```bash
   uv run streamlit run app.py
   ```

On first ingestion the app creates a serverless Pinecone index using the cloud, region, and
dimension in `.env`. Pinecone's default `multilingual-e5-large` embedding model produces
1,024-dimensional vectors, matching `PINECONE_DIMENSION=1024`. If you change embedding models,
create a new index name and set the matching dimension. Stable chunk IDs make re-ingesting
unchanged documents idempotent within the configured namespace.

## How it fits together

- `ingest.py` loads and chunks source documents.
- `store.py` creates or connects to the Pinecone index and configures Pinecone embeddings.
- `retrieval.py` combines Pinecone dense search and local BM25 results with reciprocal-rank
  fusion, then uses Pinecone reranking.
- `graph.py` routes each question, retrieves and scores context, refuses weak matches, generates
  an answer, and verifies numbered citations.
- `cli.py` provides the `ingest` and `chat` commands and keeps each chat's message history.
- `evaluation.py` runs the fixed 15-question benchmark and writes machine-readable and Markdown
  reports to `evaluations/results/`.

Configuration lives in `.env`; see `.env.example` for available settings. LangSmith tracing is
optional and can be enabled there when you want to inspect retrieval and model calls.

## Evaluation

Run the complete benchmark:

```bash
uv run rag-evaluate
```

If the separate faithfulness judge is rate-limited, the run is checkpointed. Resume judging
without repeating retrieval and generation:

```bash
uv run rag-evaluate --judge-only --judge-delay 3
```

The gold questions are in `evaluations/questions.json`. The generated report includes routing,
source hit rate, answer coverage, refusal accuracy, citation validity, faithfulness, latency,
dense-versus-hybrid retrieval, and question-level failure causes.

## Useful next steps

Once the baseline works, add automated retrieval tests, document IDs for safe re-indexing,
streaming output, and a web UI. For production, use a durable LangGraph checkpointer and a
durable LangGraph checkpointer instead of process memory.
