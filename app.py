#!/usr/bin/env python3
"""
Streamlit chat UI for KaaS local RAG/GraphRAG (LlamaIndex + GigaChat).

Run:
  pip install streamlit python-dotenv gigachat llama-index
  streamlit run app.py

Required env:
  GIGACHAT_AUTH_DATA=<token-or-auth-data>
Optional env:
  GIGACHAT_SCOPE=GIGACHAT_API_PERS
"""

from __future__ import annotations

import os
import re
import traceback
import math
import html
from functools import lru_cache
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from dotenv import load_dotenv

from llama_index.core import Settings, StorageContext, load_index_from_storage
from llama_index.core.indices.property_graph import ImplicitPathExtractor, PropertyGraphIndex
from llama_index.core.indices.vector_store import VectorStoreIndex
from llama_index.core.llms.mock import MockLLM
from llama_index.embeddings.gigachat import GigaChatEmbedding

# Native GigaChat SDK
from gigachat import GigaChat as NativeGigaChat
from gigachat.models import Chat, Messages, MessagesRole

# Optional reuse of local ingestion logic
try:
    import ingest_vault as ingest
except Exception:
    ingest = None


@dataclass
class SourceChunk:
    file_path: str
    score: Optional[float]
    excerpt: str
    wikilinks: List[str]
    source_type: str  # vector|graph


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "what",
    "about",
    "does",
    "is",
    "are",
    "of",
    "to",
    "in",
    "on",
    "a",
    "an",
    "it",
    "by",
    "you",
    "can",
    "only",
    "out",
    "says",
    "provide",
    "provides",
    "mentioned",
    "notes",
    "note",
    "summary",
    "summarize",
    "vault",
    "listed",
    "describe",
    "described",
    "define",
    "defined",
}


TOKEN_RE = re.compile(r"[\w\-]{3,}", flags=re.UNICODE)
VERDICT_RE = re.compile(r"\bverdict\s*:\s*(true|false|partially true|insufficient evidence|unknown)\b", re.IGNORECASE)


@dataclass
class SimpleLLMResponse:
    text: str


class GigaChatLLMWrapper:
    """
    Minimal custom LLM wrapper using gigachat.GigaChat directly.
    This avoids llama_index.llms.gigachat dependency.
    """

    def __init__(
        self,
        auth_data: str,
        scope: str = "GIGACHAT_API_PERS",
        verify_ssl_certs: bool = False,
        model_name: str = "GigaChat-Max",
    ) -> None:
        self.model_name = model_name
        self._client = NativeGigaChat(
            credentials=auth_data,
            scope=scope,
            timeout=35,
            verify_ssl_certs=verify_ssl_certs,
        )

    def complete(self, prompt: str, **kwargs: Any) -> SimpleLLMResponse:
        chat = Chat(
            model=self.model_name,
            messages=[Messages(role=MessagesRole.USER, content=prompt)],
            temperature=kwargs.get("temperature", 0.2),
            max_tokens=kwargs.get("max_tokens", 1200),
        )
        resp = self._client.chat(chat)
        content = resp.choices[0].message.content if resp and resp.choices else ""
        return SimpleLLMResponse(text=content)

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> SimpleLLMResponse:
        chat_messages = []
        for m in messages:
            role = (m.get("role") or "user").lower()
            if role == "assistant":
                msg_role = MessagesRole.ASSISTANT
            elif role == "system":
                msg_role = MessagesRole.SYSTEM
            else:
                msg_role = MessagesRole.USER
            chat_messages.append(Messages(role=msg_role, content=m.get("content") or ""))

        chat = Chat(
            model=self.model_name,
            messages=chat_messages,
            temperature=kwargs.get("temperature", 0.2),
            max_tokens=kwargs.get("max_tokens", 1200),
        )
        resp = self._client.chat(chat)
        content = resp.choices[0].message.content if resp and resp.choices else ""
        return SimpleLLMResponse(text=content)


# -----------------------------
# App helpers
# -----------------------------


def init_page() -> None:
    st.set_page_config(page_title="KaaS KB Agent", page_icon="🧠", layout="wide")
    st.title("🧠 KaaS Knowledge Agent")
    st.caption("Local RAG/GraphRAG over Obsidian vault | Локальный агент по базе знаний")


def get_env() -> Tuple[str, str]:
    load_dotenv(override=False)
    auth_data = os.getenv("GIGACHAT_AUTH_DATA", "")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    return auth_data, scope


def build_llm(auth_data: str, scope: str, model_name: str = "GigaChat-Max"):
    if not auth_data:
        raise ValueError("GIGACHAT_AUTH_DATA is empty.")

    return GigaChatLLMWrapper(
        auth_data=auth_data,
        scope=scope,
        verify_ssl_certs=False,
        model_name=model_name,
    )


@st.cache_resource(show_spinner=False)
def load_indexes(storage_graph: str, storage_vector: str, auth_data: str, scope: str):
    if not auth_data:
        raise ValueError("GIGACHAT_AUTH_DATA is required to load indexes.")

    # Avoid default OpenAI embed model resolution during index load/retrieval.
    Settings.embed_model = GigaChatEmbedding(
        auth_data=auth_data,
        scope=scope or "GIGACHAT_API_PERS",
        embed_batch_size=1,
        verify_ssl_certs=False,
    )
    # Avoid default OpenAI LLM resolution in PropertyGraphIndex constructor.
    Settings.llm = MockLLM()

    graph_ctx = StorageContext.from_defaults(persist_dir=storage_graph)
    vector_ctx = StorageContext.from_defaults(persist_dir=storage_vector)

    graph_index = load_index_from_storage(
        graph_ctx,
        llm=Settings.llm,
        kg_extractors=[ImplicitPathExtractor()],
    )
    vector_index = load_index_from_storage(vector_ctx)

    if not isinstance(graph_index, PropertyGraphIndex):
        # In some builds this might be generic base index with graph store attached.
        # We keep it as-is but type-hint usage remains retriever-based.
        pass

    if not isinstance(vector_index, VectorStoreIndex):
        pass

    return graph_index, vector_index


def node_to_source(node: Any, source_type: str) -> SourceChunk:
    score = getattr(node, "score", None)
    n = getattr(node, "node", node)
    metadata = getattr(n, "metadata", {}) or {}
    text = getattr(n, "text", "") or ""

    # In our current ingestion, many chunk nodes keep source metadata under relationships[SOURCE].
    rel = getattr(n, "relationships", {}) or {}
    rel_source = rel.get("1") or rel.get("SOURCE")
    # Enum keys are common in LlamaIndex; support both enum object and raw key.
    if rel_source is None:
        for k, v in rel.items():
            if str(k).endswith("SOURCE"):
                rel_source = v
                break
    rel_meta = getattr(rel_source, "metadata", {}) or {}

    file_path = (
        metadata.get("file_path")
        or metadata.get("source")
        or metadata.get("filename")
        or rel_meta.get("file_path")
        or rel_meta.get("source")
        or getattr(n, "ref_doc_id", None)
        or "unknown"
    )
    wikilinks = metadata.get("wikilinks") or rel_meta.get("wikilinks") or []
    if not isinstance(wikilinks, list):
        wikilinks = []

    excerpt = " ".join(text.strip().split())[:380]
    return SourceChunk(
        file_path=str(file_path),
        score=float(score) if score is not None else None,
        excerpt=excerpt,
        wikilinks=[str(w) for w in wikilinks[:10]],
        source_type=source_type,
    )


def strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter to avoid lexical bias on metadata keys."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + 5 :]


def query_tokens(query: str) -> List[str]:
    q = (query or "").strip().lower()
    tokens = [t for t in TOKEN_RE.findall(q) if t not in STOPWORDS and len(t) >= 3]
    # Preserve order, de-duplicate.
    seen = set()
    out = []
    for t in tokens:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def build_fact_subqueries(query: str) -> List[str]:
    """
    Build topic-agnostic fact-check subqueries:
    - original claim,
    - quoted/salient phrases,
    - entity + relation focused variants.
    """
    q = (query or "").strip()
    if not q:
        return []

    out: List[str] = [q]
    q_tokens = query_tokens(q)

    quoted = [p.strip() for p in re.findall(r"[\"“”']([^\"“”']{4,})[\"“”']", q) if p.strip()]
    for p in quoted[:2]:
        out.append(p)

    # Capitalized terms/acronyms often represent entities in technical claims.
    ents = re.findall(r"\b[A-Z][A-Za-z0-9\-]{2,}\b", q)
    ents = [e for e in ents if e.lower() not in STOPWORDS]
    ent_part = " ".join(ents[:4]).strip()

    relation_terms = [
        t
        for t in q_tokens
        if t
        in {
            "state",
            "states",
            "defined",
            "define",
            "described",
            "describe",
            "listed",
            "list",
            "means",
            "provides",
            "provide",
        }
    ]
    rel_part = " ".join(relation_terms[:2]).strip()

    # Long adjacent n-grams from query tokens capture exact claim shape.
    ngrams: List[str] = []
    for i in range(len(q_tokens) - 1):
        p = f"{q_tokens[i]} {q_tokens[i + 1]}"
        if len(p) >= 12:
            ngrams.append(p)
    for p in ngrams[:4]:
        out.append(p)

    focused = " ".join([x for x in [ent_part, rel_part] if x]).strip()
    if focused:
        out.append(focused)
    if ent_part and ngrams:
        out.append(f"{ent_part} {ngrams[0]}")

    seen = set()
    unique: List[str] = []
    for s in out:
        low = s.lower().strip()
        if not low or low in seen:
            continue
        seen.add(low)
        unique.append(s.strip())
    return unique[:8]


def retrieval_profile(mode: str) -> Dict[str, float]:
    """Mode-specific retrieval profile."""
    if mode == "Fact verification":
        return {
            "min_recall": 32.0,
            "recall_mult": 7.0,
            "vec_share": 0.25,
            "graph_share": 0.25,
            "lex_share": 0.50,
            "lex_anchors": 4.0,
        }
    if mode == "Summary":
        return {
            "min_recall": 24.0,
            "recall_mult": 6.0,
            "vec_share": 0.4,
            "graph_share": 0.25,
            "lex_share": 0.35,
            "lex_anchors": 2.0,
        }
    return {
        "min_recall": 20.0,
        "recall_mult": 5.0,
        "vec_share": 0.35,
        "graph_share": 0.25,
        "lex_share": 0.4,
        "lex_anchors": 2.0,
    }


def iter_token_positions(text_low: str, token: str, max_hits: int = 6) -> List[int]:
    out: List[int] = []
    start = 0
    while len(out) < max_hits:
        pos = text_low.find(token, start)
        if pos == -1:
            break
        out.append(pos)
        start = pos + len(token)
    return out


def best_excerpt_for_query(raw_text: str, query: str, window_before: int = 260, window_after: int = 720) -> str:
    """
    Pick the highest-scoring context window by query-term density.
    This avoids first-token/frontmatter bias and is topic-agnostic.
    """
    body = strip_frontmatter(raw_text)
    if not body.strip():
        body = raw_text
    low = body.lower()
    tokens = query_tokens(query)
    if not tokens:
        return " ".join(body[: (window_before + window_after)].split())

    # Weight rare query terms higher inside the target document.
    token_weights: Dict[str, float] = {}
    for t in tokens:
        freq = max(1, low.count(t))
        rarity = 1.0 / (freq**0.5)
        if "-" in t or len(t) >= 10:
            rarity += 0.25
        token_weights[t] = rarity

    # Phrase-level signals from query: quoted phrases + salient hyphenated terms.
    phrases = [p.strip().lower() for p in re.findall(r"[\"“”']([^\"“”']{4,})[\"“”']", query or "") if p.strip()]
    phrases.extend([t for t in tokens if "-" in t and len(t) >= 5])
    # Keep unique phrases preserving order.
    seen_phrases = set()
    uniq_phrases: List[str] = []
    for p in phrases:
        if p in seen_phrases:
            continue
        seen_phrases.add(p)
        uniq_phrases.append(p)

    candidate_positions: List[int] = []
    for t in tokens:
        candidate_positions.extend(iter_token_positions(low, t, max_hits=6))

    if not candidate_positions:
        return " ".join(body[: (window_before + window_after)].split())

    best_score = -1.0
    best_excerpt = ""
    for pos in candidate_positions:
        start = max(0, pos - window_before)
        end = min(len(body), pos + window_after)
        chunk = body[start:end]
        chunk_low = chunk.lower()

        coverage = 0.0
        density = 0.0
        for t in tokens:
            cnt = chunk_low.count(t)
            if cnt > 0:
                w = token_weights.get(t, 1.0)
                coverage += w
                density += min(cnt, 5) * (0.30 + 0.25 * w)

        phrase_boost = 0.0
        for p in uniq_phrases:
            if p and p in chunk_low:
                phrase_boost += 2.0

        score = coverage * 2.0 + density + phrase_boost
        if score > best_score:
            best_score = score
            best_excerpt = chunk

    if not best_excerpt:
        best_excerpt = body[: (window_before + window_after)]
    return " ".join(best_excerpt.split())


def document_context_for_query(raw_text: str, query: str) -> str:
    """
    Compose robust document-level context:
    1) top-of-document (title/intro),
    2) broad best-match window.
    """
    body = strip_frontmatter(raw_text)
    if not body.strip():
        body = raw_text

    head = " ".join(body[:900].split())
    match = best_excerpt_for_query(body, query, window_before=900, window_after=2200)
    if not match:
        return head
    if match in head:
        return head
    return f"{head}\n...\n{match}"


@st.cache_resource(show_spinner=False)
def load_lexical_corpus() -> List[Tuple[str, str, str]]:
    """Load all markdown files in repository for full-text fallback retrieval."""
    corpus: List[Tuple[str, str, str]] = []
    skip_parts = [
        "/.git/",
        "/.archive/",
        "/venv/",
        "/venv-fresh/",
        "/storage_graph/",
        "/storage_vector/",
        "/node_modules/",
        "/content/",
        "/.scripts/out/",
    ]
    for dirpath, _, filenames in os.walk("."):
        norm = dirpath.replace("\\", "/") + "/"
        if any(s in norm for s in skip_parts):
            continue
        for fn in filenames:
            if not fn.lower().endswith(".md"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                text = open(path, "r", encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            rel = path[2:] if path.startswith("./") else path
            body = strip_frontmatter(text)
            corpus.append((rel, body, body.lower()))
    return corpus


@st.cache_resource(show_spinner=False)
def load_wikilink_graph() -> Tuple[Dict[str, List[str]], Dict[str, str], Dict[str, str], Dict[str, List[str]]]:
    """
    Build lightweight wikilink graph from markdown corpus:
    - adjacency by file path,
    - title->path lookup,
    - raw content lookup,
    - reverse adjacency for incoming links.
    """
    adjacency: Dict[str, List[str]] = {}
    title_to_path: Dict[str, str] = {}
    path_to_raw: Dict[str, str] = {}
    incoming: Dict[str, List[str]] = {}

    for path, raw, _ in load_lexical_corpus():
        stem = os.path.splitext(os.path.basename(path))[0]
        title_to_path.setdefault(stem.lower(), path)
        path_to_raw[path] = raw

    for path, raw, _ in load_lexical_corpus():
        targets = [m.group(1).strip() for m in re.finditer(r"\[\[([^\]|#]+)(?:[^\]]*)\]\]", raw) if m.group(1).strip()]
        resolved: List[str] = []
        for t in targets:
            rp = title_to_path.get(t.lower())
            if rp:
                resolved.append(rp)
                incoming.setdefault(rp, []).append(path)
        adjacency[path] = sorted(set(resolved))
    return adjacency, title_to_path, path_to_raw, incoming


@lru_cache(maxsize=20000)
def token_document_frequency(token: str) -> int:
    t = (token or "").strip().lower()
    if not t:
        return 1
    df = 0
    for _, _, low in load_lexical_corpus():
        if t in low:
            df += 1
    return max(1, df)


def lexical_retrieve(query: str, top_k: int = 6) -> List[SourceChunk]:
    q = (query or "").strip().lower()
    if not q:
        return []
    tokens = query_tokens(q)
    if not tokens:
        return []
    phrases = [p.strip().lower() for p in re.findall(r"[\"“”']([^\"“”']{4,})[\"“”']", query or "") if p.strip()]

    corpus = load_lexical_corpus()
    total_docs = max(1, len(corpus))
    # IDF-like weighting to prioritize rare terms (e.g., product names) over generic words.
    doc_freq: Dict[str, int] = {}
    for t in tokens:
        doc_freq[t] = token_document_frequency(t)

    scored: List[Tuple[float, str, str]] = []
    for path, raw, low in corpus:
        score = 0.0
        matched_tokens = 0
        for t in tokens:
            cnt = low.count(t)
            if cnt:
                matched_tokens += 1
                idf = math.log((total_docs + 1) / (doc_freq[t] + 1)) + 1.0
                score += idf * (1.0 + min(cnt, 4) * 0.20)
        # Prefer candidates matching more distinct query terms.
        score += matched_tokens * 0.35
        if q in low:
            score += 5.0
        for p in phrases:
            if p and p in low:
                score += 4.0
        if score <= 0:
            continue

        excerpt = best_excerpt_for_query(raw, q)
        scored.append((score, path, excerpt))

    scored.sort(key=lambda x: -x[0])
    return [
        SourceChunk(
            file_path=path,
            # Keep lexical scores comparable but preserve ranking spread (avoid hard saturation).
            score=min(0.2 + score / 25.0, 0.98),
            excerpt=excerpt,
            wikilinks=[],
            source_type="lexical",
        )
        for score, path, excerpt in scored[:top_k]
    ]


def graph_store_retrieve(graph_index: Any, query: str, top_k: int = 6) -> List[SourceChunk]:
    """
    Graph fallback retrieval over persisted text_chunk nodes.
    This avoids brittle `get_triplets()` paths when graph contains malformed relation keys.
    """
    q = (query or "").strip().lower()
    if not q:
        return []
    tokens = query_tokens(q)
    if not tokens:
        return []

    store = getattr(graph_index, "property_graph_store", None)
    graph = getattr(store, "graph", None)
    nodes = getattr(graph, "nodes", {}) if graph is not None else {}
    if not isinstance(nodes, dict) or not nodes:
        return []

    scored: List[Tuple[float, str, str]] = []
    for node in nodes.values():
        if getattr(node, "label", None) != "text_chunk":
            continue
        text = str(getattr(node, "text", "") or "")
        if not text:
            continue
        low = text.lower()

        score = 0.0
        for t in tokens:
            cnt = low.count(t)
            if cnt:
                score += 1.2 + min(cnt, 4) * 0.2
        if q in low:
            score += 5.0
        if score <= 0:
            continue

        props = getattr(node, "properties", {}) or {}
        file_path = (
            props.get("ref_doc_id")
            or props.get("document_id")
            or props.get("doc_id")
            or "unknown"
        )
        excerpt = best_excerpt_for_query(text, q)
        scored.append((score, str(file_path), excerpt))

    scored.sort(key=lambda x: -x[0])
    return [
        SourceChunk(
            file_path=path,
            score=min(score / 10.0, 0.9),
            excerpt=excerpt,
            wikilinks=[],
            source_type="graph",
        )
        for score, path, excerpt in scored[:top_k]
    ]


def wikilink_graph_walk_retrieve(
    query: str,
    seed_hits: List[SourceChunk],
    top_k: int = 6,
) -> List[SourceChunk]:
    """
    Explicit graph traversal over wikilink graph:
    - seed from lexical/doc hits,
    - expand one-hop outgoing + incoming links,
    - rank neighbors by support to query.
    """
    adjacency, _, path_to_raw, incoming = load_wikilink_graph()
    if not seed_hits:
        return []

    seeds = [s.file_path for s in seed_hits[: min(8, len(seed_hits))]]
    neighbors: Dict[str, float] = {}
    for s in seeds:
        seed_w = 1.0
        for t in adjacency.get(s, []):
            neighbors[t] = max(neighbors.get(t, 0.0), seed_w * 0.9)
        for src in incoming.get(s, [])[:20]:
            neighbors[src] = max(neighbors.get(src, 0.0), seed_w * 0.7)

    out: List[SourceChunk] = []
    for path, base_w in neighbors.items():
        raw = path_to_raw.get(path, "")
        if not raw:
            continue
        excerpt = best_excerpt_for_query(raw, query)
        pseudo = SourceChunk(file_path=path, score=base_w, excerpt=excerpt, wikilinks=[], source_type="graph_walk")
        score = fact_support_score(pseudo, query) * 0.35 + base_w
        out.append(
            SourceChunk(
                file_path=path,
                score=score,
                excerpt=excerpt,
                wikilinks=[],
                source_type="graph_walk",
            )
        )

    out.sort(key=lambda x: -(x.score or 0.0))
    return out[:top_k]


def expand_to_document_context(sources: List[SourceChunk], query: str, max_docs: int = 6) -> List[SourceChunk]:
    """Promote chunk-level matches to larger document-level snippets to avoid mid-document context loss."""
    q = (query or "").lower()
    out: List[SourceChunk] = []
    seen = set()

    for s in sources:
        if s.file_path in seen:
            continue
        seen.add(s.file_path)
        out.append(s)
        if len(out) >= max_docs:
            break

    expanded: List[SourceChunk] = []
    for s in out:
        path = s.file_path
        try:
            raw = open(path, "r", encoding="utf-8", errors="ignore").read()
            doc_excerpt = document_context_for_query(raw, q)
            expanded.append(
                SourceChunk(
                    file_path=path,
                    score=s.score,
                    source_type=f"{s.source_type}+document",
                    wikilinks=s.wikilinks,
                    excerpt=doc_excerpt,
                )
            )
        except Exception:
            expanded.append(s)
    return expanded


def hybrid_retrieve(
    graph_index: Any,
    vector_index: Any,
    query: str,
    top_k: int = 6,
    mode: str = "Summary",
) -> List[SourceChunk]:
    prof = retrieval_profile(mode)
    # Stage-A recall pool (broad, high-recall)
    recall_k = max(int(prof["min_recall"]), int(top_k * prof["recall_mult"]))
    subqueries = [query]
    if mode == "Fact verification":
        sq = build_fact_subqueries(query)
        if sq:
            subqueries = sq

    vector_hits: List[SourceChunk] = []
    graph_hits: List[SourceChunk] = []
    graph_walk_hits: List[SourceChunk] = []
    lexical_hits: List[SourceChunk] = []
    lex_per_query = max(8, int(recall_k * prof["lex_share"] / max(1, len(subqueries))))
    for sq in subqueries:
        lexical_hits.extend(lexical_retrieve(sq, top_k=lex_per_query))

    # Vector retrieval
    try:
        vr = vector_index.as_retriever(similarity_top_k=max(8, int(recall_k * prof["vec_share"])))
        for sq in subqueries[:3]:
            v_nodes = vr.retrieve(sq)
            vector_hits.extend([node_to_source(n, "vector") for n in v_nodes])
    except Exception as exc:
        msg = str(exc).lower()
        if "temporary failure in name resolution" in msg or "connecterror" in msg:
            st.warning("Vector retrieval warning: network resolution issue; using graph+lexical fallback.")
        else:
            st.warning(f"Vector retrieval warning: {exc}")

    # Graph retrieval
    try:
        gr = graph_index.as_retriever(include_text=True, similarity_top_k=max(8, int(recall_k * prof["graph_share"])))
        for sq in subqueries[:3]:
            g_nodes = gr.retrieve(sq)
            graph_hits.extend([node_to_source(n, "graph") for n in g_nodes])
    except Exception as exc:
        msg = str(exc)
        low = msg.lower()
        suppress = (
            "_WIKILINKS_TO_" in msg
            or "detected nested async" in low
            or "nest_asyncio.apply()" in low
        )
        if not suppress:
            st.warning(f"Graph retrieval warning: {exc}")
    if not graph_hits:
        # Graph-store fallback is relatively expensive, keep primary claim only.
        graph_hits = graph_store_retrieve(graph_index, query, top_k=max(8, int(recall_k * prof["graph_share"])))
    use_graph_walk = mode != "Fact verification" or (len(graph_hits) < 3 or len(lexical_hits) < 10)
    if use_graph_walk:
        graph_walk_hits = wikilink_graph_walk_retrieve(query, lexical_hits, top_k=max(8, int(recall_k * 0.2)))

    # Balanced merge across retrieval modalities to avoid single-mode dominance.
    def take_unique(items: List[SourceChunk], used_paths: set, max_take: int) -> List[SourceChunk]:
        out: List[SourceChunk] = []
        for s in items:
            if s.file_path in used_paths:
                continue
            used_paths.add(s.file_path)
            out.append(s)
            if len(out) >= max_take:
                break
        return out

    used_paths: set = set()
    per_mode = max(6, int(recall_k * 0.3))
    merged: List[SourceChunk] = []
    merged.extend(take_unique(vector_hits, used_paths, per_mode))
    merged.extend(take_unique(graph_hits, used_paths, per_mode))
    merged.extend(take_unique(graph_walk_hits, used_paths, max(4, per_mode // 2)))
    merged.extend(take_unique(lexical_hits, used_paths, recall_k))
    lexical_anchors = lexical_hits[: int(prof["lex_anchors"])] if lexical_hits else []

    if not merged:
        merged = lexical_hits[:recall_k]

    # Final modality-agnostic rerank by explicit query-term support in path+excerpt.
    q_tokens = query_tokens(query)
    q_phrases = [p.strip().lower() for p in re.findall(r"[\"“”']([^\"“”']{4,})[\"“”']", query or "") if p.strip()]
    # Corpus-level token rarity (IDF-like) for stronger topic-specific ranking.
    total_docs = max(1, len(load_lexical_corpus()))
    token_idf: Dict[str, float] = {}
    for t in q_tokens:
        df = token_document_frequency(t)
        token_idf[t] = math.log((total_docs + 1) / (df + 1)) + 1.0
    # Derive phrase candidates from adjacent query tokens (topic-agnostic),
    # so exact technical expressions get stronger priority in ranking.
    q_ngram_phrases: List[str] = []
    for i in range(len(q_tokens) - 1):
        a, b = q_tokens[i], q_tokens[i + 1]
        if a in STOPWORDS or b in STOPWORDS:
            continue
        phrase = f"{a} {b}"
        if len(phrase) >= 12:
            q_ngram_phrases.append(phrase)
    # Keep unique while preserving order.
    seen_ng = set()
    q_ngram_phrases = [p for p in q_ngram_phrases if not (p in seen_ng or seen_ng.add(p))]

    def rerank_value(s: SourceChunk) -> float:
        path_low = s.file_path.lower()
        text = f"{path_low} {s.excerpt}".lower()
        coverage = 0.0
        density = 0.0
        for t in q_tokens:
            cnt = text.count(t)
            # Specificity weight: rare/long/hyphenated technical tokens matter more.
            spec = token_idf.get(t, 1.0)
            if "-" in t:
                spec += 0.8
            if len(t) >= 8:
                spec += 0.35
            if len(t) >= 12:
                spec += 0.25
            if cnt > 0:
                coverage += spec
                density += min(cnt, 5) * (0.12 + 0.08 * spec)
            # Token in filename/title is highly informative for vault notes.
            if t in path_low:
                coverage += 0.6 * spec
        phrase = 0.0
        for p in q_phrases:
            if p in text:
                phrase += 1.2
            if p in path_low:
                phrase += 3.5
        for p in q_ngram_phrases:
            if p in text:
                phrase += 1.25
            if p in path_low:
                phrase += 2.5
        base = s.score or 0.0
        return base * 0.45 + coverage * 0.5 + density + phrase

    merged.sort(key=rerank_value, reverse=True)
    candidates = merged[: max(recall_k, top_k * 4)]
    # Preserve strongest lexical anchors so exact vault wording is not dropped by noisy dense retrieval.
    for anchor in reversed(lexical_anchors):
        if all(c.file_path != anchor.file_path for c in candidates):
            if candidates:
                candidates = [anchor] + candidates[:-1]
            else:
                candidates = [anchor]
    # Stage-B precision pool (task-aware)
    if mode == "Fact verification":
        stage_b = assemble_fact_context(candidates, query, top_k=max(top_k, 8))
    else:
        stage_b = sorted(candidates, key=rerank_value, reverse=True)
    selected = stage_b[: max(top_k, 8)]
    return expand_to_document_context(selected, query=query, max_docs=max(top_k, 8))


def fact_support_score(source: SourceChunk, query: str) -> float:
    """Topic-agnostic relevance score for fact-check assertions."""
    tokens = query_tokens(query)
    if not tokens:
        return 0.0
    text = f"{source.file_path} {source.excerpt}".lower()

    matched = 0.0
    density = 0.0
    for t in tokens:
        cnt = text.count(t)
        if cnt > 0:
            w = 1.0 + (0.8 if "-" in t else 0.0) + (0.4 if len(t) >= 8 else 0.0)
            matched += w
            density += min(cnt, 4) * (0.10 + 0.08 * w)

    phrases: List[str] = []
    for i in range(len(tokens) - 1):
        p = f"{tokens[i]} {tokens[i + 1]}"
        if len(p) >= 12:
            phrases.append(p)
    seen = set()
    phrases = [p for p in phrases if not (p in seen or seen.add(p))]

    phrase_hits = 0.0
    for p in phrases:
        if p in text:
            phrase_hits += 1.2
        if p in source.file_path.lower():
            phrase_hits += 2.0

    base = source.score or 0.0
    return base * 0.25 + matched * 0.55 + density + phrase_hits


def split_into_sentences(text: str) -> List[str]:
    raw = (text or "").replace("\r", "\n")
    parts = re.split(r"(?<=[\.\!\?])\s+|\n+", raw)
    out: List[str] = []
    for p in parts:
        s = " ".join(p.strip().split())
        if len(s) < 25:
            continue
        out.append(s)
    return out


def sentence_support_score(sentence: str, query: str) -> float:
    sent = (sentence or "").lower()
    tokens = query_tokens(query)
    if not tokens:
        return 0.0
    score = 0.0
    matched = 0
    for t in tokens:
        cnt = sent.count(t)
        if cnt > 0:
            matched += 1
            w = 1.0 + (0.7 if "-" in t else 0.0) + (0.35 if len(t) >= 8 else 0.0)
            score += min(cnt, 4) * w
    if matched:
        score += (matched / max(1, len(tokens))) * 2.0
    return score


def collect_evidence_sentences(
    sources: List[SourceChunk],
    query: str,
    top_n: int = 8,
) -> List[Tuple[str, str, float]]:
    candidates: List[Tuple[str, str, float]] = []
    for s in sources[: max(6, top_n)]:
        for sent in split_into_sentences(s.excerpt):
            score = sentence_support_score(sent, query)
            if score <= 0:
                continue
            candidates.append((s.file_path, sent, score))
    candidates.sort(key=lambda x: -x[2])
    out: List[Tuple[str, str, float]] = []
    seen = set()
    for path, sent, score in candidates:
        key = (path, sent[:120].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append((path, sent, score))
        if len(out) >= top_n:
            break
    return out


def assemble_fact_context(candidates: List[SourceChunk], query: str, top_k: int) -> List[SourceChunk]:
    """
    Build final fact-check context:
    - prioritize high support,
    - preserve phrase anchors,
    - drop weak noisy candidates when enough strong ones exist.
    """
    if not candidates:
        return []
    ranked = sorted(candidates, key=lambda s: fact_support_score(s, query), reverse=True)

    tokens = query_tokens(query)
    phrases: List[str] = []
    for i in range(len(tokens) - 1):
        p = f"{tokens[i]} {tokens[i + 1]}"
        if len(p) >= 12:
            phrases.append(p)
    seen_p = set()
    phrases = [p for p in phrases if not (p in seen_p or seen_p.add(p))]

    strong: List[SourceChunk] = []
    for s in ranked:
        sc = fact_support_score(s, query)
        if sc >= 2.2:
            strong.append(s)

    anchors: List[SourceChunk] = []
    for s in ranked:
        text = f"{s.file_path} {s.excerpt}".lower()
        if any(p in text for p in phrases[:5]):
            anchors.append(s)

    selected: List[SourceChunk] = []
    seen = set()
    for s in anchors + strong + ranked:
        if s.file_path in seen:
            continue
        seen.add(s.file_path)
        selected.append(s)
        if len(selected) >= max(top_k, 8):
            break
    return selected


def build_mode_prompt(mode: str, user_input: str, sources: List[SourceChunk]) -> str:
    context_blocks = []
    for i, s in enumerate(sources, 1):
        links = ", ".join([f"[[{w}]]" for w in s.wikilinks[:5]]) if s.wikilinks else "-"
        context_blocks.append(
            f"[SOURCE {i}]\n"
            f"path: {s.file_path}\n"
            f"type: {s.source_type}\n"
            f"wikilinks: {links}\n"
            f"excerpt: {s.excerpt}\n"
        )
    context = "\n".join(context_blocks)

    system_rules = (
        "You are a knowledge-base assistant for a software company. "
        "Use ONLY provided context when asserting facts. "
        "If evidence is insufficient, explicitly say so. "
        "Respond bilingually (RU first, then EN). "
        "Include a concise reasoning summary (not hidden chain-of-thought), then final answer."
    )

    evidence_block = ""
    if mode == "Fact verification":
        ev_lines = []
        for i, (path, sent, score) in enumerate(collect_evidence_sentences(sources, user_input, top_n=8), 1):
            ev_lines.append(f"[EVIDENCE {i}] path: {path} | score: {score:.2f}\ntext: {sent}")
        if ev_lines:
            evidence_block = "\nEvidence candidates:\n" + "\n".join(ev_lines) + "\n"

        task = (
            "Task / Задача:\n"
            "Verify if the statement is true based on the context.\n"
            "Проверь утверждение на истинность по контексту.\n\n"
            f"Statement / Утверждение: {user_input}\n\n"
            "Output format:\n"
            "1) Verdict (True/False/Partially true/Insufficient evidence)\n"
            "2) Evidence For\n"
            "3) Evidence Against\n"
            "4) Confidence (0-100)\n"
            "5) Final concise answer (RU+EN)"
        )
    elif mode == "Summary":
        task = (
            "Task / Задача:\n"
            "Summarize the topic from context for engineering audience.\n"
            "Суммируй тему по контексту для инженерной аудитории.\n\n"
            f"Topic / Тема: {user_input}\n\n"
            "Output format:\n"
            "1) Key points\n"
            "2) Architecture/Process implications\n"
            "3) Risks and gaps\n"
            "4) Actionable next steps\n"
            "5) Final concise answer (RU+EN)"
        )
    else:  # Generation
        task = (
            "Task / Задача:\n"
            "Generate a new document idea/draft grounded in context.\n"
            "Сгенерируй идею/черновик нового документа, опираясь на контекст.\n\n"
            f"Description / Описание: {user_input}\n\n"
            "Output format:\n"
            "1) Document title\n"
            "2) Suggested type/domain/status\n"
            "3) Structured draft\n"
            "4) Suggested wikilinks\n"
            "5) Final concise answer (RU+EN)"
        )

    return (
        f"{system_rules}\n\n"
        f"{task}\n\n"
        f"Context:\n{context}\n"
        f"{evidence_block}"
    )


def build_fact_second_pass_prompt(user_input: str, sources: List[SourceChunk], first_answer: str) -> str:
    """
    Second-pass fact-check prompt:
    - acknowledges that vault evidence was insufficient,
    - allows using general model knowledge,
    - forces explicit provenance separation.
    """
    context_blocks = []
    for i, s in enumerate(sources, 1):
        links = ", ".join([f"[[{w}]]" for w in s.wikilinks[:5]]) if s.wikilinks else "-"
        context_blocks.append(
            f"[SOURCE {i}]\n"
            f"path: {s.file_path}\n"
            f"type: {s.source_type}\n"
            f"wikilinks: {links}\n"
            f"excerpt: {s.excerpt}\n"
        )
    context = "\n".join(context_blocks)

    ev_lines = []
    for i, (path, sent, score) in enumerate(collect_evidence_sentences(sources, user_input, top_n=8), 1):
        ev_lines.append(f"[EVIDENCE {i}] path: {path} | score: {score:.2f}\ntext: {sent}")
    ev_block = "\nEvidence candidates:\n" + "\n".join(ev_lines) + "\n" if ev_lines else ""

    return (
        "You are a software knowledge-base assistant.\n"
        "Previous pass could not verify statement from vault-only context.\n"
        "Now do a second pass using:\n"
        "1) vault context (if any), and\n"
        "2) general technical knowledge.\n\n"
        "STRICT OUTPUT REQUIREMENTS:\n"
        "- Clearly separate evidence origin:\n"
        "  A) Vault evidence status (sufficient/insufficient)\n"
        "  B) General-knowledge verdict\n"
        "- If vault is insufficient, explicitly say: 'KB data insufficient'.\n"
        "- Keep answer bilingual: RU first, then EN.\n"
        "- Include concise reasoning summary (not hidden chain-of-thought).\n"
        "- Include final verdict (True/False/Partially true/Unknown) and confidence 0-100.\n\n"
        f"Statement: {user_input}\n\n"
        f"First-pass answer:\n{first_answer}\n\n"
        f"Vault context:\n{context}\n"
        f"{ev_block}"
    )


def build_summary_retry_prompt(user_input: str, sources: List[SourceChunk], first_answer: str) -> str:
    context_blocks = []
    for i, s in enumerate(sources, 1):
        context_blocks.append(
            f"[SOURCE {i}] path: {s.file_path}\nexcerpt: {s.excerpt}\n"
        )
    context = "\n".join(context_blocks)
    return (
        "You are a software knowledge-base assistant.\n"
        "Your previous answer said context was insufficient.\n"
        "Retry using extractive summarization from the provided vault snippets only.\n"
        "If snippets are non-empty, you MUST provide a useful summary with key points.\n"
        "Use bilingual output (RU then EN).\n\n"
        f"Topic: {user_input}\n\n"
        f"Previous answer:\n{first_answer}\n\n"
        f"Context:\n{context}\n"
    )


def answer_is_insufficient(text: str) -> bool:
    low = (text or "").lower()
    markers = [
        "insufficient evidence",
        "insufficient context",
        "cannot be verified",
        "unable to verify",
        "verdict: insufficient",
        "kb data insufficient",
        "недостаточно доказательств",
        "недостаточно данных",
        "контекст недостаточен",
        "не удалось проверить",
    ]
    return any(m in low for m in markers)


def normalize_fact_answer_format(answer: str) -> str:
    """
    Enforce a machine-checkable verdict line for Fact verification responses.
    """
    text = (answer or "").strip()
    if not text:
        return "Verdict: Unknown\n\nRU: Нет ответа.\nEN: Empty answer."
    if VERDICT_RE.search(text):
        return text

    low = text.lower()
    if answer_is_insufficient(text):
        verdict = "Insufficient evidence"
    elif "partially true" in low or "частично" in low:
        verdict = "Partially true"
    elif "false" in low or "невер" in low:
        verdict = "False"
    elif "true" in low or "утверждение верно" in low or "верно." in low:
        verdict = "True"
    else:
        verdict = "Unknown"
    return f"Verdict: {verdict}\n\n{text}"


def deterministic_fact_fallback(user_input: str, sources: List[SourceChunk], error_msg: str) -> Optional[str]:
    """
    Vault-only deterministic fallback for yes/no fact checks when LLM is unavailable.
    Topic-agnostic: scores token/phrase support in retrieved sources.
    """
    if not sources:
        return None

    q = (user_input or "").strip().lower()
    tokens = query_tokens(q)
    if len(tokens) < 3:
        return None

    phrases = [p.strip().lower() for p in re.findall(r"[\"“”']([^\"“”']{4,})[\"“”']", user_input or "") if p.strip()]
    best_idx = -1
    best_score = 0.0
    best_ratio = 0.0
    matched_for_best: List[str] = []

    for i, s in enumerate(sources):
        text = f"{s.file_path}\n{s.excerpt}".lower()
        matched = [t for t in tokens if t in text]
        ratio = len(matched) / max(1, len(tokens))
        phrase_hits = sum(1 for p in phrases if p in text)
        score = ratio + phrase_hits * 0.35 + ((s.score or 0.0) * 0.15)
        if score > best_score:
            best_score = score
            best_ratio = ratio
            best_idx = i
            matched_for_best = matched

    if best_idx < 0:
        return None

    top = sources[best_idx]
    strong_support = best_ratio >= 0.55 and (
        len(matched_for_best) >= 4 or (len(tokens) <= 6 and len(matched_for_best) >= 3)
    )
    if not strong_support:
        return None

    confidence = min(95, int(60 + best_ratio * 35))
    excerpt = (top.excerpt or "").strip()
    if len(excerpt) > 420:
        excerpt = excerpt[:420].rstrip() + "..."

    return (
        "Verdict: True\n\n"
        "RU: GigaChat временно недоступен, поэтому применена детерминированная проверка только по базе знаний. "
        "Найдено сильное текстовое подтверждение утверждения в источниках.\n\n"
        f"- Основной источник: `{top.file_path}`\n"
        f"- Совпавшие термины: {', '.join(matched_for_best[:10])}\n"
        f"- Фрагмент: {excerpt}\n"
        f"- Confidence: {confidence}% (vault-only heuristic)\n\n"
        "EN: GigaChat is temporarily unavailable, so a deterministic vault-only check was used. "
        "Strong textual support for the claim was found in retrieved sources.\n\n"
        f"- Primary source: `{top.file_path}`\n"
        f"- Matched terms: {', '.join(matched_for_best[:10])}\n"
        f"- Excerpt: {excerpt}\n"
        f"- Confidence: {confidence}% (vault-only heuristic)\n\n"
        f"Service error: `{error_msg}`"
    )


def deterministic_fact_preverdict(user_input: str, sources: List[SourceChunk]) -> Optional[str]:
    """
    Deterministic vault-only pre-verdict (before LLM):
    returns high-confidence True when evidence is explicit and dense.
    """
    if not sources:
        return None

    ranked = sorted(sources, key=lambda s: fact_support_score(s, user_input), reverse=True)
    top = ranked[0]
    top_score = fact_support_score(top, user_input)
    evidence = collect_evidence_sentences(ranked, user_input, top_n=8)
    if not evidence:
        return None

    top_evidence = [e for e in evidence if e[0] == top.file_path]
    strong_sent = [e for e in top_evidence if e[2] >= 3.2]
    token_hits = len([t for t in query_tokens(user_input) if t in (top.excerpt or "").lower()])
    token_ratio = token_hits / max(1, len(query_tokens(user_input)))

    # Conservative threshold to avoid false positives on weak matches.
    if not (top_score >= 7.8 and (len(strong_sent) >= 1 or token_ratio >= 0.58)):
        return None

    confidence = min(96, int(66 + min(24, top_score * 2.5)))
    lines = []
    for i, (_, sent, score) in enumerate(top_evidence[:3], 1):
        lines.append(f"{i}) ({score:.2f}) {sent}")
    ev_text = "\n".join(lines)

    return (
        "Verdict: True\n\n"
        "RU: Утверждение подтверждается по данным базы знаний (детерминированная проверка до LLM).\n"
        f"- Основной источник: `{top.file_path}`\n"
        f"- Confidence: {confidence}%\n"
        "- Ключевые фрагменты:\n"
        f"{ev_text}\n\n"
        "EN: The claim is supported by vault evidence (deterministic pre-LLM check).\n"
        f"- Primary source: `{top.file_path}`\n"
        f"- Confidence: {confidence}%\n"
        "- Key evidence:\n"
        f"{ev_text}"
    )


def llm_generate_text(llm: Any, prompt: str) -> str:
    # Wrapper path
    if hasattr(llm, "complete"):
        resp = llm.complete(prompt)
        text = getattr(resp, "text", None)
        if text:
            return str(text)

    # Direct GigaChat fallback (if someone passed Native client)
    if isinstance(llm, NativeGigaChat):
        chat = Chat(
            model="GigaChat-Max",
            messages=[Messages(role=MessagesRole.USER, content=prompt)],
            temperature=0.2,
            max_tokens=1200,
        )
        resp = llm.chat(chat)
        return resp.choices[0].message.content if resp and resp.choices else ""

    return "No response generated."


def generate_answer_with_policy(
    llm: Any,
    mode: str,
    user_input: str,
    sources: List[SourceChunk],
) -> Tuple[str, Dict[str, Any]]:
    """
    Main answer policy:
    - standard prompt for selected mode,
    - for Fact verification with unknown/insufficient verdict, run second pass
      allowing general knowledge and mark the response explicitly.
    """
    meta: Dict[str, Any] = {
        "second_pass_used": False,
        "second_pass_reason": "",
    }

    # Deterministic pre-check for fact mode before any LLM call.
    if mode == "Fact verification":
        pre = deterministic_fact_preverdict(user_input, sources)
        if pre:
            meta["second_pass_used"] = False
            meta["second_pass_reason"] = "deterministic_preverdict"
            return pre, meta

    prompt = build_mode_prompt(mode, user_input, sources)
    first_answer = llm_generate_text(llm, prompt)

    if mode == "Summary":
        if answer_is_insufficient(first_answer) and sources:
            retry_prompt = build_summary_retry_prompt(user_input, sources, first_answer)
            retry_answer = llm_generate_text(llm, retry_prompt)
            if retry_answer and not answer_is_insufficient(retry_answer):
                return retry_answer, meta
        return first_answer, meta

    if mode != "Fact verification":
        return first_answer, meta

    first_answer = normalize_fact_answer_format(first_answer)

    if not answer_is_insufficient(first_answer):
        return first_answer, meta

    meta["second_pass_used"] = True
    meta["second_pass_reason"] = "kb_insufficient"
    second_prompt = build_fact_second_pass_prompt(user_input, sources, first_answer)
    second_answer = llm_generate_text(llm, second_prompt)
    second_answer = normalize_fact_answer_format(second_answer)
    marked_answer = (
        "⚠️ **KB insufficient -> General-knowledge second pass used / "
        "Недостаточно данных в базе -> применён второй проход с общими знаниями**\n\n"
        f"{second_answer}"
    )
    return marked_answer, meta


def fallback_answer_from_sources(mode: str, user_input: str, sources: List[SourceChunk], error_msg: str) -> str:
    """
    Deterministic fallback when LLM provider is temporarily unavailable.
    Uses only retrieved vault context.
    """
    top = sources[: min(5, len(sources))]
    bullet_lines = []
    for s in top:
        excerpt = (s.excerpt or "").strip()
        if len(excerpt) > 240:
            excerpt = excerpt[:240].rstrip() + "..."
        bullet_lines.append(f"- `{s.file_path}`: {excerpt}")

    body = "\n".join(bullet_lines) if bullet_lines else "- No relevant excerpts retrieved."

    if mode == "Summary":
        return (
            "RU: Не удалось обратиться к GigaChat (временная сетевая ошибка). "
            "Ниже extractive-summary по найденным фрагментам базы:\n"
            f"{body}\n\n"
            "EN: GigaChat is temporarily unavailable (network error). "
            "Below is an extractive summary from retrieved vault snippets:\n"
            f"{body}\n\n"
            f"Service error: `{error_msg}`"
        )

    if mode == "Fact verification":
        deterministic = deterministic_fact_fallback(user_input, sources, error_msg)
        if deterministic:
            return deterministic
        return (
            "RU: Проверка утверждения выполнена только по найденным источникам (без LLM-инференса) из-за сетевой ошибки GigaChat. "
            "Откройте источники ниже и повторите запрос после восстановления сети.\n\n"
            "EN: Fact check is limited to retrieved sources only (no LLM inference) due to a temporary GigaChat network error. "
            "Please retry when network is restored.\n\n"
            f"Service error: `{error_msg}`"
        )

    return (
        "RU: Генерация недоступна из-за временной сетевой ошибки GigaChat. "
        "Контекст источников сохранён, повторите запрос позже.\n\n"
        "EN: Generation is unavailable due to a temporary GigaChat network error. "
        "Retrieved sources are preserved; please retry later.\n\n"
        f"Service error: `{error_msg}`"
    )


def render_sources(sources: List[SourceChunk]) -> None:
    st.markdown("### Sources / Источники")
    for i, s in enumerate(sources, 1):
        score = f"{s.score:.4f}" if s.score is not None else "n/a"
        st.markdown(f"**{i}. `{s.file_path}`**  ")
        st.markdown(f"- type: `{s.source_type}` | score: `{score}`")
        if s.wikilinks:
            st.markdown("- wikilinks: " + ", ".join([f"`[[{w}]]`" for w in s.wikilinks[:8]]))
        excerpt = html.escape((s.excerpt or "").strip())
        st.markdown("- excerpt:")
        st.markdown(
            (
                "<div style='font-size: 0.95rem; line-height: 1.45; "
                "white-space: pre-wrap; margin: 0.1rem 0 0.6rem 0;'>"
                f"{excerpt}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def refresh_reingest_ui() -> None:
    st.markdown("### Refresh / Re-ingest")
    st.caption("Rebuild graph/vector indexes from vault folders.")

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        folder_input = st.text_input(
            "Folders to ingest",
            value="ontology,0-Slipbox,1-Projects,2-Areas,3-Resources",
            help="Comma-separated folders",
        )
    with c2:
        scope = st.text_input("Scope", value=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"))
    with c3:
        run_btn = st.button("🔄 Re-ingest index", use_container_width=True)

    if run_btn:
        if ingest is None:
            st.error("ingest_vault.py is not importable. Ensure file exists in project root.")
            return

        auth_data = os.getenv("GIGACHAT_AUTH_DATA", "")
        if not auth_data:
            st.warning("Missing GIGACHAT_AUTH_DATA. Set env var and retry.")
            return

        folders = [x.strip() for x in folder_input.split(",") if x.strip()]

        try:
            cfg = ingest.IngestConfig(
                folders=folders,
                storage_graph="./storage_graph",
                storage_vector="./storage_vector",
                auth_data=auth_data,
                scope=scope or "GIGACHAT_API_PERS",
                verify_ssl_certs=False,
                query=None,
                top_k=5,
            )
            with st.spinner("Running ingestion... / Выполняется индексация..."):
                files = ingest.discover_markdown_files(cfg.folders)
                docs = ingest.load_documents_with_metadata(files)
                graph_index, vector_index = ingest.build_indexes(docs, cfg)
                ingest.persist_indexes(graph_index, vector_index, cfg)
                ingest.save_ingest_manifest(docs, cfg)

            # Clear cached loaded indexes after refresh
            load_indexes.clear()
            st.success(f"Re-ingest completed. Indexed documents: {len(docs)}")
        except Exception as exc:
            st.error(f"Re-ingest failed: {exc}")
            st.code(traceback.format_exc())


def init_chat_state() -> None:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def main() -> None:
    init_page()
    init_chat_state()

    auth_data, scope = get_env()

    if not auth_data:
        st.warning(
            "⚠️ Missing GIGACHAT_AUTH_DATA. "
            "Set env var before chat and re-ingest. / Отсутствует GIGACHAT_AUTH_DATA."
        )

    with st.sidebar:
        st.header("Settings / Настройки")
        model_name = st.selectbox(
            "Model",
            options=["GigaChat-Max", "GigaChat-Pro", "GigaChat"],
            index=0,
        )
        top_k = st.slider("Top-K retrieval", min_value=3, max_value=15, value=6)
        mode = st.selectbox(
            "Mode / Режим",
            options=["Fact verification", "Summary", "Generation"],
            index=0,
        )

        st.markdown("---")
        refresh_reingest_ui()

    # Load indexes
    try:
        graph_index, vector_index = load_indexes("./storage_graph", "./storage_vector", auth_data, scope)
        st.success("Indexes loaded: storage_graph + storage_vector")
    except Exception as exc:
        st.error(
            "Failed to load indexes. Run ingest first via button or CLI. "
            f"Error: {exc}"
        )
        st.stop()

    # Build LLM
    llm = None
    if auth_data:
        try:
            llm = build_llm(auth_data=auth_data, scope=scope, model_name=model_name)
        except Exception as exc:
            st.error(f"Failed to initialize GigaChat LLM: {exc}")

    # Render previous chat
    for item in st.session_state.chat_history:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            if item.get("sources"):
                with st.expander("Sources", expanded=False):
                    render_sources(item["sources"])

    user_input = st.chat_input("Ask your knowledge base... / Задайте вопрос базе знаний...")

    if not user_input:
        return

    # Show user message
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    if llm is None:
        with st.chat_message("assistant"):
            st.warning("LLM is not initialized. Please set credentials and retry.")
        return

    with st.chat_message("assistant"):
        with st.spinner("Retrieving context... / Ищу релевантный контекст..."):
            sources = hybrid_retrieve(graph_index, vector_index, user_input, top_k=top_k, mode=mode)

        with st.spinner("Generating answer... / Генерирую ответ..."):
            try:
                answer, answer_meta = generate_answer_with_policy(llm, mode, user_input, sources)
            except Exception as exc:
                st.warning(
                    "LLM call failed (temporary). Returned fallback response from retrieved context only."
                )
                answer = fallback_answer_from_sources(mode, user_input, sources, str(exc))
                answer_meta = {"second_pass_used": False, "second_pass_reason": "llm_error"}

        # High-level reasoning summary (safe)
        second_pass_line = (
            "- fact policy: `two-pass (KB-only -> general-knowledge fallback)`\n"
            if mode == "Fact verification"
            else ""
        )
        second_pass_used = (
            "- second pass used: `yes (KB insufficient)`\n"
            if answer_meta.get("second_pass_used")
            else "- second pass used: `no`\n"
            if mode == "Fact verification"
            else ""
        )
        reasoning = (
            f"**Reasoning summary / Краткое обоснование**\n"
            f"- mode: `{mode}`\n"
            f"- context chunks: `{len(sources)}`\n"
            f"- retrieval: `hybrid (vector + graph + lexical)`\n"
            f"{second_pass_line}"
            f"{second_pass_used}"
        )

        st.markdown(reasoning)
        st.markdown(answer)

        with st.expander("Sources / Источники", expanded=False):
            render_sources(sources)

        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": reasoning + "\n\n" + answer,
                "sources": sources,
            }
        )


if __name__ == "__main__":
    main()
