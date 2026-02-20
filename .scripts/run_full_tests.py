#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app


@dataclass
class TestCase:
    mode: str
    query: str
    expected: str
    expected_source: str = ""


def contains_insufficient(text: str) -> bool:
    low = (text or "").lower()
    markers = [
        "insufficient evidence",
        "insufficient context",
        "cannot be verified",
        "kb data insufficient",
        "недостаточно",
        "контекст недостаточен",
        "не удалось проверить",
    ]
    return any(m in low for m in markers)


def evaluate(case: TestCase, answer: str, sources: List[app.SourceChunk]) -> Dict[str, Any]:
    low = (answer or "").lower()
    source_paths = [s.file_path for s in sources]
    has_expected_source = case.expected_source in source_paths if case.expected_source else True

    result = {
        "pass": False,
        "reason": "",
        "has_expected_source": has_expected_source,
        "sources": source_paths,
    }

    if case.mode == "Fact verification":
        wants_true = "true" in case.expected.lower()
        if wants_true:
            verdict_true = "verdict: true" in low or "\ntrue" in low or " true " in low
            result["pass"] = verdict_true and has_expected_source
            result["reason"] = "expected true verdict + expected source"
        else:
            result["pass"] = not contains_insufficient(answer)
            result["reason"] = "expected informative factual answer"
        return result

    # Summary tests
    result["pass"] = not contains_insufficient(answer)
    result["reason"] = "expected non-insufficient summary"
    return result


def main() -> None:
    out_dir = Path(".scripts/out")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = out_dir / f"full_tests_{stamp}.json"
    out_md = out_dir / f"full_tests_{stamp}.md"

    auth = os.getenv("GIGACHAT_AUTH_DATA", "")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    if not auth:
        raise RuntimeError("GIGACHAT_AUTH_DATA is not set")

    graph_index, vector_index = app.load_indexes("./storage_graph", "./storage_vector", auth, scope)
    llm = app.build_llm(auth_data=auth, scope=scope, model_name="GigaChat-Max")

    tests: List[TestCase] = [
        TestCase(
            mode="Fact verification",
            query='Is it true that in the vault’s "Data Pipeline Architecture" note, Kafka is described as the de-facto choice for high-volume streaming ingestion?',
            expected="True",
            expected_source="0-Slipbox/Data Pipeline Architecture.md",
        ),
        TestCase(
            mode="Fact verification",
            query="Does the vault state that Kafka is publish-subscribe messaging rethought as a distributed commit log?",
            expected="True",
            expected_source="2-Areas/Lists/Data Engineering Master List of Resources.md",
        ),
        TestCase(
            mode="Fact verification",
            query="Is Nakadi described in the vault as an open-source event messaging platform with a REST API on top of Kafka-like queues?",
            expected="True",
            expected_source="2-Areas/Lists/Data Engineering Master List of Resources.md",
        ),
        TestCase(
            mode="Fact verification",
            query='Is MSK listed in the vault as "Kafka as a service"?',
            expected="True",
            expected_source="2-Areas/Lists/AWS Components Master List.md",
        ),
        TestCase(
            mode="Fact verification",
            query="Does the vault define Event-Driven Architecture as a paradigm for producing, detecting, consuming, and reacting to events among loosely coupled components?",
            expected="True",
            expected_source="3-Resources/Highlights/Readwise/Articles/Learn About Cloud Functions Events and Triggers  Google Cloud Blog.md",
        ),
        TestCase(
            mode="Summary",
            query="Summarize what the vault says about Data Pipeline Architecture",
            expected="Should summarize note content",
        ),
        TestCase(
            mode="Summary",
            query="Give me a summary of Build a Lakehouse Architecture on AWS from the notes",
            expected="Should summarize note content",
        ),
        TestCase(
            mode="Summary",
            query="Summarize Kafka-related points from the vault",
            expected="Should summarize cross-note Kafka points",
        ),
        TestCase(
            mode="Summary",
            query="Summarize what the vault says about Consistent Hashing",
            expected="Structured summary expected",
        ),
        TestCase(
            mode="Summary",
            query="Give me a summary of Event-Driven Architecture from the notes",
            expected="Principles/pros/cons/patterns",
        ),
        TestCase(
            mode="Summary",
            query="Summarize the key points about Microservices vs Monolith in this knowledge base",
            expected="Comparison + tradeoffs",
        ),
        TestCase(
            mode="Summary",
            query="Provide a concise summary of CAP Theorem and its real-world implications",
            expected="CAP + CP/AP/CA implications",
        ),
        TestCase(
            mode="Summary",
            query="Summarize best practices for Database Sharding mentioned in the vault",
            expected="Sharding best practices",
        ),
    ]

    rows: List[Dict[str, Any]] = []
    for idx, t in enumerate(tests, 1):
        sources = app.hybrid_retrieve(graph_index, vector_index, t.query, top_k=8)
        infra_error = ""
        try:
            answer, meta = app.generate_answer_with_policy(llm, t.mode, t.query, sources)
        except Exception as exc:
            infra_error = str(exc)
            answer = app.fallback_answer_from_sources(t.mode, t.query, sources, infra_error)
            meta = {"second_pass_used": False, "second_pass_reason": "infra_error"}
        ev = evaluate(t, answer, sources)
        rows.append(
            {
                "id": idx,
                "mode": t.mode,
                "query": t.query,
                "expected": t.expected,
                "expected_source": t.expected_source,
                "pass": ev["pass"],
                "reason": ev["reason"],
                "has_expected_source": ev["has_expected_source"],
                "second_pass_used": bool(meta.get("second_pass_used")),
                "infra_error": infra_error,
                "sources": ev["sources"],
                "answer": answer,
            }
        )

    passed = sum(1 for r in rows if r["pass"])
    total = len(rows)
    summary = {
        "timestamp_utc": stamp,
        "total": total,
        "passed": passed,
        "failed": total - passed,
    }
    payload = {"summary": summary, "results": rows}
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# Full Test Run ({stamp})",
        "",
        f"- Total: {total}",
        f"- Passed: {passed}",
        f"- Failed: {total - passed}",
        "",
        "| # | Mode | Pass | Query | Second pass | Expected source found |",
        "|---|------|------|-------|-------------|-----------------------|",
    ]
    for r in rows:
        q = r["query"].replace("|", "\\|")
        md_lines.append(
            f"| {r['id']} | {r['mode']} | {'✅' if r['pass'] else '❌'} | {q} | "
            f"{'yes' if r['second_pass_used'] else 'no'} | "
            f"{'yes' if r['has_expected_source'] else 'no'} |"
        )
    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False))
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
