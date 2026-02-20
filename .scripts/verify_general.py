#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List

OUT_DIR = Path('.scripts/out')
OUT_DIR.mkdir(parents=True, exist_ok=True)

ROOT = Path('.')
APP_PATH = ROOT / 'app.py'
MANIFEST_PATH = ROOT / 'storage_graph' / 'ingest_manifest.json'

# Make project root importable when script runs from .scripts/
sys.path.insert(0, str(ROOT.resolve()))


def count_all_md() -> int:
    skip_patterns = [
        '/.git/',
        '/.archive/',
        '/venv/',
        '/venv-fresh/',
        '/storage_graph/',
        '/storage_vector/',
        '/node_modules/',
        '/content/',
        '/.scripts/out/',
    ]
    total = 0
    for dirpath, _, filenames in os.walk('.'):
        norm = dirpath.replace('\\', '/') + '/'
        if any(s in norm for s in skip_patterns):
            continue
        for fn in filenames:
            if fn.lower().endswith('.md'):
                total += 1
    return total


def static_checks(app_text: str) -> Dict:
    checks: Dict = {}

    # 1) no topic hardcode
    hardcoded_terms = [
        'Kafka', 'CAP Theorem', 'Consistent Hashing', 'CQRS',
        'Event-Driven Architecture', 'domain_hint_sources', 'if "kafka" in'
    ]
    found = [t for t in hardcoded_terms if t in app_text]
    checks['no_topic_hardcode'] = len(found) == 0
    checks['hardcode_hits'] = found

    # 2) all docs lexical search scope
    checks['lexical_walks_repo_root'] = 'for dirpath, _, filenames in os.walk(".")' in app_text

    # 3) modalities declared
    checks['has_vector_retrieval'] = 'vector_index.as_retriever' in app_text
    checks['has_graph_retrieval'] = 'graph_index.as_retriever' in app_text
    checks['has_lexical_retrieval'] = 'lexical_retrieve(' in app_text
    checks['has_document_expansion'] = 'expand_to_document_context' in app_text and 'source_type=f"{s.source_type}+document"' in app_text

    # 4) KB-only prompting rule
    checks['kb_only_prompt_rule'] = 'Use ONLY provided context when asserting facts.' in app_text

    return checks


def dynamic_checks() -> Dict:
    out: Dict = {}
    try:
        import app  # type: ignore

        auth_data = os.getenv('GIGACHAT_AUTH_DATA', '')
        scope = os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')

        # lexical corpus size (all md for fallback)
        corpus = app.load_lexical_corpus()
        out['lexical_corpus_docs'] = len(corpus)

        # index availability
        graph_exists = Path('storage_graph').exists()
        vector_exists = Path('storage_vector').exists()
        out['storage_graph_exists'] = graph_exists
        out['storage_vector_exists'] = vector_exists

        if graph_exists and vector_exists and auth_data:
            graph_index, vector_index = app.load_indexes('./storage_graph', './storage_vector', auth_data, scope)
            queries = [
                'Is it true that Kafka provides exactly-once semantics by default?',
                'Summarize CAP Theorem implications',
                'Database sharding hotspots rebalancing strategies',
            ]
            q_results: List[Dict] = []
            src_types = set()
            unknown_paths = 0
            for q in queries:
                sources = app.hybrid_retrieve(graph_index, vector_index, q, top_k=8)
                types = sorted({s.source_type for s in sources})
                src_types.update(types)
                up = sum(1 for s in sources if s.file_path == 'unknown')
                unknown_paths += up
                q_results.append({
                    'query': q,
                    'sources_count': len(sources),
                    'source_types': types,
                    'unknown_paths': up,
                    'first_paths': [s.file_path for s in sources[:5]],
                    'max_excerpt_chars': max((len(s.excerpt or '') for s in sources), default=0),
                })
            out['retrieval_source_types'] = sorted(src_types)
            out['unknown_paths_total'] = unknown_paths
            out['query_results'] = q_results
        else:
            out['retrieval_source_types'] = []
            out['unknown_paths_total'] = None
            out['query_results'] = []
            out['note'] = 'Skipped dynamic retrieval: indexes missing or GIGACHAT_AUTH_DATA missing.'

    except Exception as exc:
        out['dynamic_error'] = str(exc)

    return out


def main() -> int:
    app_text = APP_PATH.read_text(encoding='utf-8', errors='ignore')

    report: Dict = {}
    report.update(static_checks(app_text))
    report['md_total_excluding_service_dirs'] = count_all_md()

    if MANIFEST_PATH.exists():
        try:
            report['ingest_manifest'] = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        except Exception as exc:
            report['ingest_manifest_error'] = str(exc)

    report.update(dynamic_checks())

    # Assertions summary
    assertions = {
        '1_no_hardcode_generic_retrieval': bool(report.get('no_topic_hardcode')),
        '2_search_all_documents_lexical': report.get('lexical_corpus_docs', -1) >= report.get('md_total_excluding_service_dirs', 10**9),
        '3_hybrid_vector_graph_fulltext_and_doc_context': all([
            report.get('has_vector_retrieval'),
            report.get('has_graph_retrieval'),
            report.get('has_lexical_retrieval'),
            report.get('has_document_expansion'),
            any('vector' in t for t in (report.get('retrieval_source_types') or [])),
            any('graph' in t for t in (report.get('retrieval_source_types') or [])),
            any('lexical' in t for t in (report.get('retrieval_source_types') or [])),
        ]),
        '4_kb_only_prompting_rule_present': bool(report.get('kb_only_prompt_rule')),
    }
    report['assertions'] = assertions

    (OUT_DIR / 'verification_general.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    lines = [
        '# Verification Summary',
        '',
        f"- no_topic_hardcode: {report.get('no_topic_hardcode')}",
        f"- hardcode_hits: {report.get('hardcode_hits')}",
        f"- md_total_excluding_service_dirs: {report.get('md_total_excluding_service_dirs')}",
        f"- lexical_corpus_docs: {report.get('lexical_corpus_docs')}",
        f"- retrieval_source_types: {report.get('retrieval_source_types')}",
        f"- unknown_paths_total: {report.get('unknown_paths_total')}",
        f"- has_vector_retrieval: {report.get('has_vector_retrieval')}",
        f"- has_graph_retrieval: {report.get('has_graph_retrieval')}",
        f"- has_lexical_retrieval: {report.get('has_lexical_retrieval')}",
        f"- has_document_expansion: {report.get('has_document_expansion')}",
        f"- kb_only_prompt_rule: {report.get('kb_only_prompt_rule')}",
        '',
        '## Assertions',
    ]
    for k, v in assertions.items():
        lines.append(f"- {k}: {v}")

    (OUT_DIR / 'verification_general.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print('\n'.join(lines[:20]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
