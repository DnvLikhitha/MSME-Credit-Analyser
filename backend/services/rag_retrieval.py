"""
Embedding-Based RAG Recommendation Service — Phase 4 (Upgraded)
=================================================================
Replaces in-context injection with a proper semantic retrieval pipeline:

  1. On startup / first call:
     - Embed all 7 government loan schemes using sentence-transformers
     - Store embeddings in ChromaDB (in-memory or persisted)

  2. On each recommendation request:
     - Build a query string from the business profile (risk band + key metrics)
     - Retrieve top-K most relevant schemes via cosine similarity
     - Inject ONLY those retrieved schemes into the Gemini prompt (true RAG)

Why this matters vs in-context injection:
  - In-context: ALL schemes injected every time → token cost grows with scheme count
  - RAG: Only relevant schemes injected → scales to 1000+ schemes with same token cost

ChromaDB: Self-hosted, no API key, runs in-process (zero infra overhead for MVP).
Model: all-MiniLM-L6-v2 (fast, small, excellent for semantic similarity tasks).
"""
import json
import logging
from typing import Optional

from backend.services.schemes_knowledge import GOVERNMENT_SCHEMES

logger = logging.getLogger(__name__)

# ── Lazy initialization ───────────────────────────────────────────────────────
_chroma_collection = None
_embedder = None

_COLLECTION_NAME = "msme_loan_schemes"
_TOP_K = 5  # Retrieve top-5 schemes, pass to Gemini for final ranking to top-3


def _get_embedder():
    """Lazy-load SentenceTransformer to avoid startup delay."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("[RAG] SentenceTransformer model loaded: all-MiniLM-L6-v2")
        except ImportError:
            logger.error("[RAG] sentence-transformers not installed. Run: pip install sentence-transformers")
            raise
    return _embedder


def _get_collection():
    """Return (or create) the ChromaDB collection with all scheme embeddings."""
    global _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection

    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        # In-memory client for MVP — change to chromadb.PersistentClient for persistence
        client = chromadb.Client(ChromaSettings(anonymized_telemetry=False))

        embedder = _get_embedder()

        # Build scheme documents (what we embed)
        documents = []
        metadatas = []
        ids = []

        for idx, scheme in enumerate(GOVERNMENT_SCHEMES):
            # Combine all relevant text fields for richer embedding
            doc_text = (
                f"Scheme: {scheme['scheme_name']}. "
                f"Type: {scheme['scheme_type']}. "
                f"Issued by: {scheme['issuing_body']}. "
                f"Description: {scheme['description']}. "
                f"Eligibility: {scheme['eligibility_criteria']}. "
                f"Max loan: INR {scheme['max_loan_amount_inr']:,}. "
                f"Collateral required: {scheme['collateral_required']}. "
                f"Interest: {scheme['interest_rate_range']}. "
                f"Tenure: {scheme['tenure']}."
            )
            documents.append(doc_text)
            metadatas.append({
                "scheme_name": scheme["scheme_name"],
                "scheme_type": scheme["scheme_type"],
                "issuing_body": scheme["issuing_body"],
                "max_loan_amount_inr": scheme["max_loan_amount_inr"],
                "collateral_required": str(scheme["collateral_required"]),
                "interest_rate_range": scheme["interest_rate_range"],
                "tenure": scheme["tenure"],
            })
            ids.append(f"scheme_{idx}")

        # Compute embeddings
        embeddings = embedder.encode(documents).tolist()

        # Create + populate collection
        _chroma_collection = client.create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        _chroma_collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        logger.info(f"[RAG] ChromaDB collection initialized with {len(documents)} scheme embeddings.")
        return _chroma_collection

    except ImportError:
        logger.warning("[RAG] chromadb not installed. Falling back to in-context injection.")
        return None


def build_query_from_profile(metrics_dict: dict, risk_score_dict: dict) -> str:
    """
    Build a natural-language query string that captures the business profile
    for semantic similarity search against scheme documents.
    """
    band = risk_score_dict.get("risk_band", "UNKNOWN")
    score = risk_score_dict.get("overall_score", 0)

    revenue = metrics_dict.get("annual_revenue")
    avg_bal = metrics_dict.get("avg_monthly_balance")
    bounces = metrics_dict.get("cheque_bounce_count", 0)
    collateral = metrics_dict.get("total_assets") is not None

    parts = [f"MSME business with {band} credit risk (score {score}/100)."]

    if revenue:
        rev_cr = revenue / 1e7
        parts.append(f"Annual turnover approximately INR {rev_cr:.2f} crore.")
    else:
        parts.append("Revenue data not available.")

    if avg_bal:
        parts.append(f"Average monthly bank balance INR {avg_bal:,.0f}.")

    if bounces and bounces > 0:
        parts.append(f"Has {int(bounces)} cheque bounce(s).")
    else:
        parts.append("No cheque bounces — clean banking record.")

    if not collateral:
        parts.append("No significant assets available as collateral — prefers collateral-free schemes.")

    if band == "HIGH":
        parts.append("Needs micro-finance or entry-level government scheme. Low income, starting stage.")
    elif band == "MEDIUM":
        parts.append("Eligible for MUDRA Kishore or CGTMSE with bank guarantee.")
    else:
        parts.append("Strong financials — eligible for SIDBI, CGTMSE, or Stand-Up India.")

    return " ".join(parts)


def retrieve_relevant_schemes(metrics_dict: dict, risk_score_dict: dict, top_k: int = _TOP_K) -> str:
    """
    Retrieve the top-K most semantically relevant schemes for this business profile.
    Returns a JSON string to be injected into the Gemini prompt.

    Falls back to full scheme list if ChromaDB/embeddings are unavailable.
    """
    try:
        collection = _get_collection()
        if collection is None:
            raise RuntimeError("ChromaDB unavailable")

        embedder = _get_embedder()
        query = build_query_from_profile(metrics_dict, risk_score_dict)
        logger.info(f"[RAG] Query: {query[:120]}...")

        query_embedding = embedder.encode([query]).tolist()[0]
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, len(GOVERNMENT_SCHEMES)),
            include=["documents", "metadatas", "distances"],
        )

        retrieved_schemes = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # Convert distance (lower=more similar for cosine) to similarity score
            similarity = round(1.0 - dist, 3)
            scheme_name = meta["scheme_name"]
            # Find original full scheme dict
            full_scheme = next(
                (s for s in GOVERNMENT_SCHEMES if s["scheme_name"] == scheme_name),
                meta,
            )
            retrieved_schemes.append({
                **full_scheme,
                "_similarity_score": similarity,
            })

        logger.info(
            f"[RAG] Retrieved {len(retrieved_schemes)} schemes via embedding similarity: "
            f"{[s['scheme_name'] for s in retrieved_schemes]}"
        )
        return json.dumps(retrieved_schemes, indent=2)

    except Exception as e:
        logger.warning(f"[RAG] Embedding retrieval failed ({e}). Falling back to full context injection.")
        # Graceful degradation: inject all schemes
        return json.dumps(GOVERNMENT_SCHEMES, indent=2)
