#!/usr/bin/env python3
"""
Ingest an Obsidian vault into local LlamaIndex stores (PropertyGraph + Vector).

Install dependencies:
  pip install llama-index llama-index-embeddings-gigachat gigachat python-frontmatter

Example:
  export GIGACHAT_AUTH_DATA="<your_auth_data>"
  export GIGACHAT_SCOPE="GIGACHAT_API_PERS"
  python ingest_vault.py \
    --folders ontology 0-Slipbox 2-Areas/Code \
    --storage-graph ./storage_graph \
    --storage-vector ./storage_vector \
    --query "How is system design connected to devops?"
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    import frontmatter  # type: ignore
except Exception:
    frontmatter = None

from llama_index.core import (
    Document,
    PropertyGraphIndex,
    Settings,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.indices.property_graph import ImplicitPathExtractor
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.gigachat import GigaChatEmbedding

# Optional imports for direct relation upsert (supported by many graph stores)
try:
    from llama_index.core.graph_stores.types import EntityNode, Relation
except Exception:
    EntityNode = None
    Relation = None

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[^\]]*)\]\]")


@dataclass
class IngestConfig:
    folders: List[str]
    storage_graph: str
    storage_vector: str
    auth_data: str
    scope: str
    verify_ssl_certs: bool
    query: Optional[str]
    top_k: int
    phase: str
    resume: bool
    reset: bool
    retry_max: int


def parse_args() -> IngestConfig:
    parser = argparse.ArgumentParser(description="Ingest Obsidian vault into LlamaIndex graph+vector stores")
    parser.add_argument(
        "--folders",
        nargs="+",
        default=["ontology", "0-Slipbox", "2-Areas"],
        help="Folders to index",
    )
    parser.add_argument("--storage-graph", default="./storage_graph", help="Persist dir for PropertyGraphIndex")
    parser.add_argument("--storage-vector", default="./storage_vector", help="Persist dir for VectorStoreIndex")
    parser.add_argument(
        "--gigachat-auth-data",
        default=os.getenv("GIGACHAT_AUTH_DATA", ""),
        help="GigaChat auth data (or set GIGACHAT_AUTH_DATA)",
    )
    parser.add_argument(
        "--gigachat-scope",
        default=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
        help="GigaChat scope (e.g. GIGACHAT_API_PERS or GIGACHAT_API_CORP)",
    )
    parser.add_argument(
        "--verify-ssl-certs",
        action="store_true",
        default=False,
        help="Enable SSL cert verification for GigaChat client (default: False)",
    )
    parser.add_argument("--query", default=None, help="Optional sample similarity query after ingestion")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K for sample retrieval")
    parser.add_argument(
        "--phase",
        choices=["all", "graph", "vector"],
        default="all",
        help="Which ingest phase to run: all | graph | vector",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="Resume from previously completed phases (uses ingest_state.json)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        default=False,
        help="Reset storage and phase state before ingestion",
    )
    parser.add_argument(
        "--retry-max",
        type=int,
        default=5,
        help="Max retry attempts per embedding request on transient network errors",
    )

    args = parser.parse_args()
    return IngestConfig(
        folders=args.folders,
        storage_graph=args.storage_graph,
        storage_vector=args.storage_vector,
        auth_data=args.gigachat_auth_data,
        scope=args.gigachat_scope,
        verify_ssl_certs=args.verify_ssl_certs,
        query=args.query,
        top_k=args.top_k,
        phase=args.phase,
        resume=args.resume,
        reset=args.reset,
        retry_max=args.retry_max,
    )


def discover_markdown_files(folders: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for folder in folders:
        p = Path(folder)
        if not p.exists():
            print(f"[WARN] Folder does not exist and will be skipped: {folder}")
            continue
        if p.is_file() and p.suffix.lower() == ".md":
            files.append(p)
            continue
        for f in p.rglob("*.md"):
            files.append(f)
    # deterministic order
    return sorted(set(files))


def parse_frontmatter_and_body(text: str) -> Tuple[Dict, str]:
    """Parse YAML frontmatter; fallback to manual parser if python-frontmatter is unavailable."""
    if frontmatter is not None:
        try:
            post = frontmatter.loads(text)
            return dict(post.metadata or {}), post.content
        except Exception:
            pass

    # Manual fallback
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            raw = text[4:end]
            body = text[end + 5 :]
            meta: Dict[str, str] = {}
            for line in raw.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            return meta, body

    return {}, text


def extract_wikilinks(text: str) -> List[str]:
    links = [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]
    return sorted(set([l for l in links if l]))


def normalize_title_from_path(file_path: str) -> str:
    return Path(file_path).stem


def sanitize_metadata(value):
    """Convert metadata values into JSON-serializable primitives."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): sanitize_metadata(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_metadata(v) for v in value]
    return str(value)


def compact_metadata_for_index(meta: Dict) -> Dict:
    """
    Keep metadata lean to avoid parser metadata-length issues on small chunk sizes.
    """
    keep_keys = [
        "title",
        "file_path",
        "source",
        "type",
        "domain",
        "status",
        "updated",
        "related_moc",
        "wikilinks",
    ]
    out: Dict = {}
    for k in keep_keys:
        if k not in meta:
            continue
        v = meta[k]
        if k == "wikilinks":
            if isinstance(v, list):
                out[k] = [str(x) for x in v[:20]]
            continue
        if isinstance(v, (list, tuple, set)):
            continue
        out[k] = v
    return out


def load_documents_with_metadata(files: List[Path]) -> List[Document]:
    """
    Load markdown files directly, then enrich with parsed frontmatter and wikilinks.
    """
    if not files:
        return []

    print(f"[INFO] Loading {len(files)} markdown files from filesystem...")

    docs: List[Document] = []
    for f in files:
        file_path = str(f)
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        fm, body = parse_frontmatter_and_body(text)

        merged_meta = sanitize_metadata({**fm})
        if not merged_meta.get("title"):
            merged_meta["title"] = normalize_title_from_path(file_path) if file_path else "Untitled"
        if file_path:
            merged_meta["file_path"] = file_path
            merged_meta["source"] = file_path

        wikilinks = extract_wikilinks(body)
        merged_meta["wikilinks"] = wikilinks
        merged_meta = compact_metadata_for_index(merged_meta)

        docs.append(
            Document(
                text=body,
                metadata=merged_meta,
                id_=file_path or merged_meta["title"],
            )
        )

    print(f"[INFO] Prepared {len(docs)} documents with frontmatter metadata.")
    return docs


def build_title_lookup(documents: List[Document]) -> Dict[str, str]:
    """Map Obsidian-like wikilink targets to stable node IDs (best effort)."""
    mapping: Dict[str, str] = {}
    for d in documents:
        title = str(d.metadata.get("title") or "").strip()
        file_path = str(d.metadata.get("file_path") or "")
        stem = Path(file_path).stem if file_path else title
        node_id = str(getattr(d, "doc_id", "") or stem)
        for key in {title, stem}:
            if key:
                mapping.setdefault(key, node_id)
    return mapping


def add_wikilink_relations(graph_index: PropertyGraphIndex, documents: List[Document]) -> int:
    """
    Enrich graph store with wikilink relations.

    Strategy:
    1) If graph store exposes `upsert_triplet`, use simple triplets.
    2) Else, if it supports `upsert_nodes`/`upsert_relations`, create explicit relations.
    """
    graph_store = graph_index.property_graph_store
    title_lookup = build_title_lookup(documents)

    triplets: List[Tuple[str, str, str]] = []
    for d in documents:
        src_title = str(d.metadata.get("title") or "")
        src_path = str(d.metadata.get("file_path") or "")
        src = src_title or Path(src_path).stem or str(getattr(d, "doc_id", ""))
        for target in d.metadata.get("wikilinks", []) or []:
            tgt = title_lookup.get(target, target)
            triplets.append((src, "WIKILINKS_TO", tgt))

    inserted = 0

    if hasattr(graph_store, "upsert_triplet"):
        for s, r, o in triplets:
            graph_store.upsert_triplet(s, r, o)
            inserted += 1
        return inserted

    # Fallback for property graph stores with node/relation API
    if hasattr(graph_store, "upsert_nodes") and hasattr(graph_store, "upsert_relations") and EntityNode and Relation:
        node_ids = set()
        nodes = []
        relations = []
        for s, r, o in triplets:
            if s not in node_ids:
                nodes.append(EntityNode(label="Note", name=s))
                node_ids.add(s)
            if o not in node_ids:
                nodes.append(EntityNode(label="Note", name=o))
                node_ids.add(o)
            # EntityNode.id is deterministic from name in most graph-store implementations.
            relations.append(Relation(label=r, source_id=s, target_id=o))

        if nodes:
            graph_store.upsert_nodes(nodes)
        if relations:
            graph_store.upsert_relations(relations)
            inserted = len(relations)

    return inserted


class ResilientGigaChatEmbedding(GigaChatEmbedding):
    """GigaChat embedding wrapper with retry on transient API/network failures."""

    def __init__(self, *args, retry_max: int = 5, **kwargs):
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "retry_max", max(1, retry_max))

    def _get_text_embedding(self, text: str) -> List[float]:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retry_max + 1):
            try:
                return super()._get_text_embedding(text)
            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                transient = any(
                    x in msg
                    for x in [
                        "server disconnected",
                        "timeout",
                        "temporarily unavailable",
                        "connection reset",
                        "connection aborted",
                        "502",
                        "503",
                        "504",
                    ]
                )
                if not transient or attempt >= self.retry_max:
                    raise
                backoff = min(20, 2**attempt)
                print(
                    f"[WARN] Embedding request failed (attempt {attempt}/{self.retry_max}): {exc}. "
                    f"Retry in {backoff}s..."
                )
                time.sleep(backoff)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Unexpected embedding retry loop termination.")


def init_embedding_model(auth_data: str, scope: str, verify_ssl_certs: bool, retry_max: int) -> GigaChatEmbedding:
    if not auth_data:
        raise ValueError(
            "Missing GigaChat credentials. Set GIGACHAT_AUTH_DATA or pass --gigachat-auth-data."
        )

    try:
        embed_batch_size = int(os.getenv("GIGACHAT_EMBED_BATCH_SIZE", "1"))
        embed_model = ResilientGigaChatEmbedding(
            auth_data=auth_data,
            scope=scope,
            embed_batch_size=embed_batch_size,
            verify_ssl_certs=verify_ssl_certs,
            retry_max=retry_max,
        )
        return embed_model
    except Exception as exc:
        msg = str(exc)
        if "SSL" in msg.upper() or "CERT" in msg.upper():
            raise RuntimeError(
                "Failed to initialize GigaChatEmbedding due to SSL/certificate issue. "
                "Try --verify-ssl-certs=false (default) for local PoC or fix trust chain."
            ) from exc
        if "AUTH" in msg.upper() or "TOKEN" in msg.upper() or "401" in msg:
            raise RuntimeError(
                "Failed to initialize GigaChatEmbedding due to auth error. "
                "Check GIGACHAT_AUTH_DATA and GIGACHAT_SCOPE."
            ) from exc
        raise


def build_splitter() -> SentenceSplitter:
    # GigaChat embeddings have tight token limits on /embeddings.
    # Keep chunks short to avoid 413 Tokens limit exceeded.
    return SentenceSplitter(
        chunk_size=420,
        chunk_overlap=60,
        include_metadata=False,
    )


def build_graph_index(
    documents: List[Document],
    embed_model: GigaChatEmbedding,
    splitter: SentenceSplitter,
) -> PropertyGraphIndex:
    # Global default for retrieval-time embedding calls
    Settings.embed_model = embed_model

    print("[INFO] Building PropertyGraphIndex...")
    graph_storage = StorageContext.from_defaults()

    # Keep extractor pipeline simple and deterministic for local PoC.
    # We augment graph structure via wikilinks after index construction.
    graph_index = PropertyGraphIndex.from_documents(
        documents,
        storage_context=graph_storage,
        embed_model=embed_model,
        # Important: empty list would fallback to default SimpleLLMPathExtractor
        # which requires OpenAI package. Use only implicit extractor for LLM-free graph build.
        kg_extractors=[ImplicitPathExtractor()],
        use_async=False,
        transformations=[splitter],
        show_progress=True,
    )

    print("[INFO] Adding wikilink relations into graph store...")
    inserted = add_wikilink_relations(graph_index, documents)
    print(f"[INFO] Inserted wikilink relations: {inserted}")
    return graph_index


def build_vector_index(
    documents: List[Document],
    embed_model: GigaChatEmbedding,
    splitter: SentenceSplitter,
) -> VectorStoreIndex:
    print("[INFO] Building VectorStoreIndex (fallback/hybrid)...")
    vector_storage = StorageContext.from_defaults()
    vector_index = VectorStoreIndex.from_documents(
        documents,
        storage_context=vector_storage,
        embed_model=embed_model,
        use_async=False,
        transformations=[splitter],
        show_progress=True,
    )

    return vector_index


def persist_indexes(graph_index: PropertyGraphIndex, vector_index: VectorStoreIndex, cfg: IngestConfig) -> None:
    Path(cfg.storage_graph).mkdir(parents=True, exist_ok=True)
    Path(cfg.storage_vector).mkdir(parents=True, exist_ok=True)

    graph_index.storage_context.persist(persist_dir=cfg.storage_graph)
    vector_index.storage_context.persist(persist_dir=cfg.storage_vector)

    print(f"[INFO] Graph index persisted to: {cfg.storage_graph}")
    print(f"[INFO] Vector index persisted to: {cfg.storage_vector}")


def persist_graph_index(graph_index: PropertyGraphIndex, cfg: IngestConfig) -> None:
    Path(cfg.storage_graph).mkdir(parents=True, exist_ok=True)
    graph_index.storage_context.persist(persist_dir=cfg.storage_graph)
    print(f"[INFO] Graph index persisted to: {cfg.storage_graph}")


def persist_vector_index(vector_index: VectorStoreIndex, cfg: IngestConfig) -> None:
    Path(cfg.storage_vector).mkdir(parents=True, exist_ok=True)
    vector_index.storage_context.persist(persist_dir=cfg.storage_vector)
    print(f"[INFO] Vector index persisted to: {cfg.storage_vector}")


def state_path(cfg: IngestConfig) -> Path:
    return Path(cfg.storage_graph) / "ingest_state.json"


def load_state(cfg: IngestConfig) -> Dict:
    p = state_path(cfg)
    if not p.exists():
        return {
            "graph_done": False,
            "vector_done": False,
            "folders": cfg.folders,
            "documents": 0,
            "scope": cfg.scope,
            "updated_at": None,
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {
            "graph_done": False,
            "vector_done": False,
            "folders": cfg.folders,
            "documents": 0,
            "scope": cfg.scope,
            "updated_at": None,
        }


def save_state(cfg: IngestConfig, state: Dict) -> None:
    p = state_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = dt.datetime.utcnow().isoformat() + "Z"
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_storage_and_state(cfg: IngestConfig) -> None:
    for d in [cfg.storage_graph, cfg.storage_vector]:
        dp = Path(d)
        if dp.exists():
            shutil.rmtree(dp)
            print(f"[INFO] Removed storage dir: {d}")


def run_sample_query(graph_index: PropertyGraphIndex, vector_index: VectorStoreIndex, query: str, top_k: int) -> None:
    print("\n[INFO] Sample similarity search")
    print(f"[QUERY] {query}")

    # Vector retrieval (no LLM dependency for answer synthesis)
    try:
        vec_retriever = vector_index.as_retriever(similarity_top_k=top_k)
        vec_nodes = vec_retriever.retrieve(query)
        print(f"[VECTOR] Retrieved {len(vec_nodes)} nodes")
        for i, n in enumerate(vec_nodes[:top_k], 1):
            text = (n.text or "").replace("\n", " ").strip()
            print(f"  {i}. {text[:180]}")
    except Exception as exc:
        print(f"[WARN] Vector retrieval failed: {exc}")

    # Graph retrieval
    try:
        graph_retriever = graph_index.as_retriever(include_text=True, similarity_top_k=top_k)
        graph_nodes = graph_retriever.retrieve(query)
        print(f"[GRAPH] Retrieved {len(graph_nodes)} nodes")
        for i, n in enumerate(graph_nodes[:top_k], 1):
            text = (n.text or "").replace("\n", " ").strip()
            print(f"  {i}. {text[:180]}")
    except Exception as exc:
        print(f"[WARN] Graph retrieval failed: {exc}")


def save_ingest_manifest(documents: List[Document], cfg: IngestConfig) -> None:
    manifest = {
        "folders": cfg.folders,
        "documents": len(documents),
        "storage_graph": cfg.storage_graph,
        "storage_vector": cfg.storage_vector,
        "scope": cfg.scope,
    }
    out_path = Path(cfg.storage_graph) / "ingest_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    cfg = parse_args()

    print("[INFO] Vault ingestion started")
    print(f"[INFO] Folders: {cfg.folders}")

    if cfg.reset:
        reset_storage_and_state(cfg)

    files = discover_markdown_files(cfg.folders)
    if not files:
        print("[ERROR] No markdown files found in selected folders.")
        return 2

    print(f"[INFO] Markdown files discovered: {len(files)}")

    try:
        documents = load_documents_with_metadata(files)
        state = load_state(cfg)
        # If corpus shape changed, force re-run both phases.
        if state.get("documents") != len(documents) or state.get("folders") != cfg.folders:
            state["graph_done"] = False
            state["vector_done"] = False
        state["documents"] = len(documents)
        state["folders"] = cfg.folders
        state["scope"] = cfg.scope
        save_state(cfg, state)

        print("[INFO] Initializing GigaChat embeddings...")
        embed_model = init_embedding_model(
            auth_data=cfg.auth_data,
            scope=cfg.scope,
            verify_ssl_certs=cfg.verify_ssl_certs,
            retry_max=cfg.retry_max,
        )
        splitter = build_splitter()

        run_graph = cfg.phase in ("all", "graph")
        run_vector = cfg.phase in ("all", "vector")

        graph_index_opt: Optional[PropertyGraphIndex] = None
        vector_index_opt: Optional[VectorStoreIndex] = None

        if run_graph:
            if cfg.resume and state.get("graph_done"):
                print("[INFO] Skip graph phase (already completed in state).")
            else:
                graph_index = build_graph_index(documents, embed_model, splitter)
                persist_graph_index(graph_index, cfg)
                state["graph_done"] = True
                save_state(cfg, state)
                graph_index_opt = graph_index

        if run_vector:
            if cfg.resume and state.get("vector_done"):
                print("[INFO] Skip vector phase (already completed in state).")
            else:
                vector_index = build_vector_index(documents, embed_model, splitter)
                persist_vector_index(vector_index, cfg)
                state["vector_done"] = True
                save_state(cfg, state)
                vector_index_opt = vector_index

        save_ingest_manifest(documents, cfg)

        if cfg.query and run_vector:
            vector_ctx = StorageContext.from_defaults(persist_dir=cfg.storage_vector)
            vector_loaded = load_index_from_storage(vector_ctx)
            if graph_index_opt is not None and isinstance(vector_loaded, VectorStoreIndex):
                run_sample_query(graph_index_opt, vector_loaded, cfg.query, cfg.top_k)
            else:
                print("[INFO] --query provided, but graph phase was skipped; sample graph retrieval is skipped.")
        elif not cfg.query:
            print("[INFO] No --query provided. Skipping sample retrieval.")

        print("[INFO] Ingestion completed successfully.")
        return 0

    except Exception as exc:
        print(f"[ERROR] Ingestion failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
