#!/usr/bin/env python3
"""RAG pipeline with traces, metrics, and logs via Bud observability.

Demonstrates a Retrieval-Augmented Generation pipeline instrumented with all
three OpenTelemetry signals:

* **Traces** — each pipeline stage is wrapped in a manual span via
  ``tracer.start_as_current_span()``.
* **Metrics** — counters and histograms (``get_meter()``) track document
  throughput, retrieval latency, and end-to-end pipeline duration.
* **Logs** — Python ``logging`` is bridged to OTel so ``rag_logger`` events
  are exported alongside traces and metrics.

Embeddings and vector retrieval are **simulated** — only the final LLM
generation step makes a real ``client.chat.completions.create()`` call.

Trace tree produced::

    rag-pipeline (root)
      ├── document-chunking
      ├── embed-query          (simulated)
      ├── embed-documents      (simulated)
      ├── vector-retrieval     (simulated cosine similarity)
      ├── context-assembly
      └── llm-generation       (real API call)

Usage:
    BUD_API_KEY=your-key python examples/observability/rag_pipeline.py
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import time

from bud import BudClient
from bud.observability import ObservabilityConfig, configure, get_meter, get_tracer, shutdown

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:56054")
API_KEY = os.environ.get("BUD_API_KEY", "my-test-api-key")
OTEL_ENDPOINT = os.environ.get("BUD_OTEL_ENDPOINT", "http://localhost:56054")

# ---------------------------------------------------------------------------
# Knowledge base (hardcoded documents)
# ---------------------------------------------------------------------------
DOCUMENTS = [
    "Retrieval-Augmented Generation (RAG) combines a retriever and a generator to answer questions using external knowledge sources.",
    "Vector databases store high-dimensional embeddings and support fast approximate nearest-neighbour search for semantic retrieval.",
    "Transformer models use self-attention mechanisms to capture long-range dependencies in sequential data.",
    "Fine-tuning a large language model on domain-specific data can significantly improve its accuracy on specialised tasks.",
    "Prompt engineering involves designing input prompts that guide a language model toward producing desired outputs.",
    "Cosine similarity measures the angle between two vectors and is commonly used to rank document relevance in embedding space.",
]

EMBEDDING_MODEL = "simulated-embed-v1"
EMBEDDING_DIM = 128

rag_logger = logging.getLogger("rag-pipeline")

# Metric instruments (initialized in main() after configure())
meter = None
documents_processed = None   # Counter
retrieval_latency = None     # Histogram (ms)
pipeline_duration = None     # Histogram (s)


# ---------------------------------------------------------------------------
# Helpers (pure-Python, no external deps)
# ---------------------------------------------------------------------------

def _fake_embedding(text: str, dimensions: int = EMBEDDING_DIM) -> list[float]:
    """Generate a deterministic pseudo-random embedding from *text*."""
    rng = random.Random(hash(text))
    return [rng.gauss(0, 1) for _ in range(dimensions)]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Pipeline stages — each creates its own child span
# ---------------------------------------------------------------------------

def document_chunking(tracer, documents: list[str]) -> list[str]:
    """Split documents into chunks (here each doc is already one chunk)."""
    with tracer.start_as_current_span("document-chunking") as span:
        span.set_attribute("chunking.strategy", "one-doc-per-chunk")
        # Simulate a small processing delay
        time.sleep(0.01)
        chunks = list(documents)
        span.set_attribute("chunking.chunk_count", len(chunks))
        documents_processed.add(len(chunks))
        rag_logger.info("Chunked %d documents", len(chunks))
    return chunks


def embed_query(tracer, query: str) -> list[float]:
    """Generate a (simulated) embedding for the user query."""
    with tracer.start_as_current_span("embed-query") as span:
        span.set_attribute("embedding.model", EMBEDDING_MODEL)
        span.set_attribute("embedding.dimensions", EMBEDDING_DIM)
        time.sleep(0.01)
        embedding = _fake_embedding(query)
    return embedding


def embed_documents(tracer, chunks: list[str]) -> list[list[float]]:
    """Generate (simulated) embeddings for every chunk."""
    with tracer.start_as_current_span("embed-documents") as span:
        span.set_attribute("embedding.model", EMBEDDING_MODEL)
        span.set_attribute("embedding.input_count", len(chunks))
        time.sleep(0.01)
        embeddings = [_fake_embedding(c) for c in chunks]
    return embeddings


def vector_retrieval(
    tracer,
    query_emb: list[float],
    doc_embs: list[list[float]],
    chunks: list[str],
    top_k: int = 3,
) -> list[tuple[str, float]]:
    """Retrieve the top-k most similar chunks via cosine similarity."""
    with tracer.start_as_current_span("vector-retrieval") as span:
        span.set_attribute("retrieval.top_k", top_k)
        t0 = time.perf_counter()
        scored = [
            (chunk, _cosine_similarity(query_emb, emb))
            for chunk, emb in zip(chunks, doc_embs)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        results = scored[:top_k]
        latency_ms = (time.perf_counter() - t0) * 1000
        retrieval_latency.record(latency_ms)
        span.set_attribute("retrieval.scores", json.dumps([round(s, 4) for _, s in results]))
        rag_logger.info("Retrieved top-%d chunks in %.1fms", top_k, latency_ms)
    return results


def context_assembly(tracer, retrieved: list[tuple[str, float]]) -> str:
    """Join retrieved chunks into a single context string."""
    with tracer.start_as_current_span("context-assembly") as span:
        context = "\n\n".join(chunk for chunk, _score in retrieved)
        span.set_attribute("context.chunk_count", len(retrieved))
        span.set_attribute("context.total_length", len(context))
    return context


def llm_generation(tracer, client: BudClient, context: str, query: str) -> str:
    """Call the real LLM with the assembled context and query."""
    with tracer.start_as_current_span("llm-generation") as span:
        model = "gpt"
        span.set_attribute("generation.model", model)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. Answer the user's question "
                        "based only on the following context:\n\n" + context
                    ),
                },
                {"role": "user", "content": query},
            ],
        )
        answer = response.choices[0].message.content or ""
        span.set_attribute("generation.response_length", len(answer))
        rag_logger.info("LLM generation completed: model=%s, len=%d", model, len(answer))
    return answer


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global meter, documents_processed, retrieval_latency, pipeline_duration

    configure(
        service_name="rag-pipeline-example",
        collector_endpoint=OTEL_ENDPOINT,
        api_key="my-test-api-key",
        config=ObservabilityConfig(log_level="INFO"),
    )

    meter = get_meter("rag-pipeline")
    documents_processed = meter.create_counter(
        "rag.documents.processed",
        unit="{document}",
        description="Number of documents chunked and processed",
    )
    retrieval_latency = meter.create_histogram(
        "rag.retrieval.latency",
        unit="ms",
        description="Vector retrieval latency",
    )
    pipeline_duration = meter.create_histogram(
        "rag.pipeline.duration",
        unit="s",
        description="Total RAG pipeline duration",
    )

    tracer = get_tracer("rag-pipeline")
    client = BudClient(api_key=API_KEY, base_url=BASE_URL)
    try:
        query = "How does RAG use vector retrieval to answer questions?"
        rag_logger.info("Starting RAG pipeline: query=%r", query)
        print(f"Query: {query}\n")

        with tracer.start_as_current_span("rag-pipeline"):
            pipeline_start = time.perf_counter()

            # 1. Chunk documents
            chunks = document_chunking(tracer, DOCUMENTS)

            # 2-3. Embed query and documents
            query_emb = embed_query(tracer, query)
            doc_embs = embed_documents(tracer, chunks)

            # 4. Retrieve top-k
            retrieved = vector_retrieval(tracer, query_emb, doc_embs, chunks)
            print("Retrieved chunks:")
            for chunk, score in retrieved:
                print(f"  [{score:.4f}] {chunk}")
            print()

            # 5. Assemble context
            context = context_assembly(tracer, retrieved)

            # 6. Generate answer (real LLM call)
            answer = llm_generation(tracer, client, context, query)
            print(f"Answer: {answer}")

            duration_s = time.perf_counter() - pipeline_start
            pipeline_duration.record(duration_s)
            rag_logger.info("RAG pipeline completed in %.2fs", duration_s)
    finally:
        client.close()
        shutdown()

    print("\nDone. Check your collector for traces, metrics, and logs.")


if __name__ == "__main__":
    main()
