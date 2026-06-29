"""
RAG pipeline ingestion — Lab 2 deliverable.

Reads Markdown policy files, chunks them semantically by headers,
enriches metadata, embeds with Google Gemini, and stores in ChromaDB.

Usage:
    python -m src.ingestion.ingest_data
"""

import os
import re
from typing import Optional

import chromadb
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.config import (
    GOOGLE_API_KEY,
    POLICIES_DIR,
    CHROMA_DIR,
)

COLLECTION_NAME = "onboarding_knowledge"
EMBEDDING_MODEL = "models/gemini-embedding-001"


# ---------------------------------------------------------------------------
# 1. Read policy files
# ---------------------------------------------------------------------------

def _load_markdown_files(directory: str) -> list[dict]:
    """Return a list of dicts with keys 'filename', 'content' for every .md file."""
    docs: list[dict] = []
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(directory, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        docs.append({"filename": fname, "content": content})
        print(f"  Loaded {fname} ({len(content)} chars)")
    return docs


# ---------------------------------------------------------------------------
# 2. Clean text
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Strip excessive whitespace and normalize markdown headers."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^(#{1,6})([^ #])", r"\1 \2", text, flags=re.MULTILINE)
    return text.strip()


# ---------------------------------------------------------------------------
# 3. Semantic chunking by headers
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def _chunk_by_headers(text: str) -> list[dict]:
    """Split markdown into chunks on ## and ### boundaries."""
    matches = list(_HEADER_RE.finditer(text))

    if not matches:
        return [{"header": "Full Document", "level": 1, "body": text}]

    chunks: list[dict] = []

    preamble = text[: matches[0].start()].strip()
    if preamble:
        chunks.append({"header": "Preamble", "level": 1, "body": preamble})

    for i, match in enumerate(matches):
        level = len(match.group(1))
        header = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        if len(body) < 30:
            continue

        chunks.append({"header": header, "level": level, "body": body})

    return chunks


# ---------------------------------------------------------------------------
# 4. Metadata enrichment
# ---------------------------------------------------------------------------

_DOC_TYPE_MAP: dict[str, str] = {
    "onboarding_policy": "policy",
    "compliance_guidelines": "compliance",
    "engineering_handbook": "handbook",
    "benefits_guide": "benefits",
    "sales_handbook": "handbook",
    "hr_handbook": "handbook",
    "finance_handbook": "handbook",
    "marketing_handbook": "handbook",
}

_DEPARTMENT_MAP: dict[str, str] = {
    "onboarding_policy": "all",
    "compliance_guidelines": "all",
    "engineering_handbook": "engineering",
    "benefits_guide": "all",
    "sales_handbook": "sales",
    "hr_handbook": "hr",
    "finance_handbook": "finance",
    "marketing_handbook": "marketing",
}

_CRITICAL_KEYWORDS = [
    "must", "required", "mandatory", "compliance", "legal",
    "i-9", "w-4", "eeoc", "osha", "hipaa", "immediately",
    "termination", "penalty",
]
_HIGH_KEYWORDS = [
    "deadline", "within", "days", "before start", "prior to",
    "insurance", "background check", "nda",
]
_MEDIUM_KEYWORDS = [
    "recommended", "should", "guideline", "training", "benefits",
    "enroll", "401k",
]


def _infer_priority(text: str) -> str:
    lower = text.lower()
    if any(kw in lower for kw in _CRITICAL_KEYWORDS):
        return "critical"
    if any(kw in lower for kw in _HIGH_KEYWORDS):
        return "high"
    if any(kw in lower for kw in _MEDIUM_KEYWORDS):
        return "medium"
    return "low"


def _enrich_metadata(chunk: dict, filename: str) -> dict:
    stem = os.path.splitext(filename)[0]
    return {
        "doc_type": _DOC_TYPE_MAP.get(stem, "policy"),
        "department": _DEPARTMENT_MAP.get(stem, "all"),
        "priority_level": _infer_priority(chunk["body"]),
        "source_file": filename,
        "last_updated": "2024-03-01",
        "section_header": chunk["header"],
        "header_level": chunk["level"],
    }


# ---------------------------------------------------------------------------
# 5. Build LangChain Documents
# ---------------------------------------------------------------------------

def _build_documents(raw_docs: list[dict]) -> list[Document]:
    documents: list[Document] = []
    for raw in raw_docs:
        cleaned = _clean_text(raw["content"])
        chunks = _chunk_by_headers(cleaned)
        for chunk in chunks:
            metadata = _enrich_metadata(chunk, raw["filename"])
            doc = Document(page_content=chunk["body"], metadata=metadata)
            documents.append(doc)
    return documents


# ---------------------------------------------------------------------------
# 6. Embed & store in ChromaDB
# ---------------------------------------------------------------------------

def _get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Instantiate the Google Gemini embeddings model."""
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )


def _store_in_chroma(documents: list[Document]) -> chromadb.Collection:
    embeddings_model = _get_embeddings()

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"  Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    import time

    texts = [doc.page_content for doc in documents]
    metadatas = [doc.metadata for doc in documents]
    ids = [f"chunk-{i:04d}" for i in range(len(documents))]

    print(f"  Embedding {len(texts)} chunks with {EMBEDDING_MODEL} ...")

    # Batch to respect Gemini free-tier rate limits (100 req/min)
    BATCH_SIZE = 80
    vectors = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        print(f"    Batch {start // BATCH_SIZE + 1}: embedding {len(batch)} chunks ...")
        batch_vectors = embeddings_model.embed_documents(batch)
        vectors.extend(batch_vectors)
        if start + BATCH_SIZE < len(texts):
            print("    Waiting 60s for rate limit ...")
            time.sleep(60)

    collection.upsert(
        ids=ids,
        embeddings=vectors,
        documents=texts,
        metadatas=metadatas,
    )

    print(f"  Stored {collection.count()} chunks in ChromaDB at {CHROMA_DIR}")
    return collection


# ---------------------------------------------------------------------------
# 7. Query helper (reusable by agents / tools)
# ---------------------------------------------------------------------------

def query_knowledge_base(
    query: str,
    filters: Optional[dict] = None,
    k: int = 3,
) -> list[Document]:
    """Retrieve the top-k relevant chunks from ChromaDB."""
    embeddings_model = _get_embeddings()
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(COLLECTION_NAME)

    query_embedding = embeddings_model.embed_query(query)

    query_kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results": k,
        "include": ["documents", "metadatas", "distances"],
    }
    if filters:
        query_kwargs["where"] = filters

    results = collection.query(**query_kwargs)

    documents: list[Document] = []
    for doc_text, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        meta_with_score = {**meta, "relevance_score": round(1 - distance, 4)}
        documents.append(Document(page_content=doc_text, metadata=meta_with_score))

    return documents


# ---------------------------------------------------------------------------
# 8. Main ingestion pipeline
# ---------------------------------------------------------------------------

def ingest_all() -> None:
    """Execute the full ingestion pipeline."""
    print("=" * 60)
    print("RAG Ingestion Pipeline — Onboarding Knowledge Base")
    print("=" * 60)

    print("\n[1/4] Loading Markdown policy files ...")
    raw_docs = _load_markdown_files(POLICIES_DIR)
    print(f"  Loaded {len(raw_docs)} file(s)")

    print("\n[2/4] Chunking and enriching metadata ...")
    documents = _build_documents(raw_docs)
    print(f"  Produced {len(documents)} chunks")

    doc_types = {}
    priorities = {}
    for doc in documents:
        dt = doc.metadata["doc_type"]
        pr = doc.metadata["priority_level"]
        doc_types[dt] = doc_types.get(dt, 0) + 1
        priorities[pr] = priorities.get(pr, 0) + 1
    print(f"  doc_type distribution:    {doc_types}")
    print(f"  priority distribution:    {priorities}")

    print("\n[3/4] Embedding and storing in ChromaDB ...")
    _store_in_chroma(documents)

    print("\n[4/4] Running verification query ...")
    test_results = query_knowledge_base(
        "What documents are required before an employee's start date?", k=3
    )
    for i, doc in enumerate(test_results, 1):
        score = doc.metadata.get("relevance_score", "n/a")
        src = doc.metadata.get("source_file", "unknown")
        header = doc.metadata.get("section_header", "—")
        print(f"  Result {i}: [{src}] {header}  (score: {score})")

    print("\n" + "=" * 60)
    print("Ingestion complete!")
    print("=" * 60)


if __name__ == "__main__":
    ingest_all()
