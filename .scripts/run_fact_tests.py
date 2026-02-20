#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import signal
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app


@dataclass
class FactCase:
    query: str
    expected_verdict: str
    expected_source: str
    expected_phrase: str


TESTS: List[FactCase] = [
    FactCase(
        query='Is it true that in the vault’s "Data Pipeline Architecture" note, Kafka is described as the de-facto choice for high-volume streaming ingestion?',
        expected_verdict="True",
        expected_source="0-Slipbox/Data Pipeline Architecture.md",
        expected_phrase="de-facto choice",
    ),
    FactCase(
        query="Does the vault state that Kafka is publish-subscribe messaging rethought as a distributed commit log?",
        expected_verdict="True",
        expected_source="2-Areas/Lists/Data Engineering Master List of Resources.md",
        expected_phrase="publish-subscribe messaging rethought as a distributed commit log",
    ),
    FactCase(
        query="Is Nakadi described in the vault as an open-source event messaging platform with a REST API on top of Kafka-like queues?",
        expected_verdict="True",
        expected_source="2-Areas/Lists/Data Engineering Master List of Resources.md",
        expected_phrase="Nakadi is an open source event messaging platform that provides a REST API on top of Kafka-like queues",
    ),
    FactCase(
        query='Is MSK listed in the vault as "Kafka as a service"?',
        expected_verdict="True",
        expected_source="2-Areas/Lists/AWS Components Master List.md",
        expected_phrase="Kafka as a service",
    ),
    FactCase(
        query="Does the vault define Event-Driven Architecture as a paradigm for producing, detecting, consuming, and reacting to events among loosely coupled components?",
        expected_verdict="True",
        expected_source="3-Resources/Highlights/Readwise/Articles/Learn About Cloud Functions Events and Triggers  Google Cloud Blog.md",
        expected_phrase="production, detection, consumption of, and reaction to events",
    ),
]


VERDICT_RE = re.compile(
    r"\bverdict\s*:\s*(true|false|partially true|insufficient evidence|unknown)\b",
    flags=re.IGNORECASE,
)


def parse_verdict(answer: str) -> str:
    m = VERDICT_RE.search(answer or "")
    if m:
        return m.group(1).strip().lower()
    low = (answer or "").lower()
    if "insufficient" in low or "недостаточно" in low:
        return "insufficient evidence"
    if "partially true" in low:
        return "partially true"
    if " false" in f" {low} ":
        return "false"
    if " true" in f" {low} ":
        return "true"
    return "unknown"


def run(tag: str, top_k: int) -> Dict[str, Any]:
    auth = os.getenv("GIGACHAT_AUTH_DATA", "")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    if not auth:
        raise RuntimeError("GIGACHAT_AUTH_DATA is not set")

    graph_index, vector_index = app.load_indexes("./storage_graph", "./storage_vector", auth, scope)
    llm = app.build_llm(auth_data=auth, scope=scope, model_name="GigaChat-Max")

    rows: List[Dict[str, Any]] = []
    for i, t in enumerate(TESTS, 1):
        t0 = time.perf_counter()
        sources = app.hybrid_retrieve(
            graph_index,
            vector_index,
            t.query,
            top_k=top_k,
            mode="Fact verification",
        )
        retrieval_sec = time.perf_counter() - t0

        infra_error = ""
        t1 = time.perf_counter()
        try:
            timed_out = {"flag": False}

            def _handler(_signum, _frame):
                timed_out["flag"] = True
                raise TimeoutError("fact-test case timeout")

            prev = signal.signal(signal.SIGALRM, _handler)
            signal.alarm(95)
            try:
                answer, meta = app.generate_answer_with_policy(llm, "Fact verification", t.query, sources)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, prev)
        except Exception as exc:
            infra_error = str(exc)
            answer = app.fallback_answer_from_sources("Fact verification", t.query, sources, infra_error)
            meta = {"second_pass_used": False, "second_pass_reason": "infra_error"}
        answer_sec = time.perf_counter() - t1

        source_paths = [s.file_path for s in sources]
        expected_source_found = t.expected_source in source_paths
        expected_phrase_found = any((t.expected_phrase.lower() in (s.excerpt or "").lower()) for s in sources)

        verdict = parse_verdict(answer)
        verdict_ok = verdict == t.expected_verdict.lower()

        fallback_used = (
            ("service error:" in (answer or "").lower())
            or ("temporary" in (infra_error or "").lower())
            or ("временно" in (answer or "").lower() and "deterministic" in (answer or "").lower())
        )

        passed = verdict_ok and expected_source_found
        rows.append(
            {
                "id": i,
                "query": t.query,
                "expected_verdict": t.expected_verdict,
                "expected_source": t.expected_source,
                "expected_phrase": t.expected_phrase,
                "pass": passed,
                "verdict": verdict,
                "verdict_ok": verdict_ok,
                "expected_source_found": expected_source_found,
                "expected_phrase_found": expected_phrase_found,
                "second_pass_used": bool(meta.get("second_pass_used")),
                "fallback_used": fallback_used,
                "infra_error": infra_error,
                "retrieval_sec": round(retrieval_sec, 3),
                "answer_sec": round(answer_sec, 3),
                "sources": source_paths,
                "answer": answer,
            }
        )

    total = len(rows)
    passed = sum(1 for r in rows if r["pass"])
    source_recall_k = sum(1 for r in rows if r["expected_source_found"]) / max(1, total)
    evidence_phrase_k = sum(1 for r in rows if r["expected_phrase_found"]) / max(1, total)
    verdict_acc = sum(1 for r in rows if r["verdict_ok"]) / max(1, total)
    fallback_rate = sum(1 for r in rows if r["fallback_used"]) / max(1, total)
    second_pass_rate = sum(1 for r in rows if r["second_pass_used"]) / max(1, total)
    avg_retrieval_sec = sum(r["retrieval_sec"] for r in rows) / max(1, total)
    avg_answer_sec = sum(r["answer_sec"] for r in rows) / max(1, total)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "tag": tag,
        "timestamp_utc": stamp,
        "top_k": top_k,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "source_recall_at_k": round(source_recall_k, 4),
        "evidence_phrase_at_k": round(evidence_phrase_k, 4),
        "verdict_accuracy": round(verdict_acc, 4),
        "fallback_rate": round(fallback_rate, 4),
        "second_pass_rate": round(second_pass_rate, 4),
        "avg_retrieval_sec": round(avg_retrieval_sec, 3),
        "avg_answer_sec": round(avg_answer_sec, 3),
    }
    return {"summary": summary, "results": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="adhoc", help="Label for this run")
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()

    out_dir = ROOT / ".scripts" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = run(args.tag, args.top_k)

    tag_safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", args.tag)
    stamp = payload["summary"]["timestamp_utc"]
    out_json = out_dir / f"fact_tests_{tag_safe}_{stamp}.json"
    out_md = out_dir / f"fact_tests_{tag_safe}_{stamp}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Fact Tests ({args.tag})",
        "",
        f"- timestamp_utc: {payload['summary']['timestamp_utc']}",
        f"- passed: {payload['summary']['passed']}/{payload['summary']['total']}",
        f"- source_recall_at_k: {payload['summary']['source_recall_at_k']}",
        f"- evidence_phrase_at_k: {payload['summary']['evidence_phrase_at_k']}",
        f"- verdict_accuracy: {payload['summary']['verdict_accuracy']}",
        f"- fallback_rate: {payload['summary']['fallback_rate']}",
        f"- second_pass_rate: {payload['summary']['second_pass_rate']}",
        f"- avg_retrieval_sec: {payload['summary']['avg_retrieval_sec']}",
        f"- avg_answer_sec: {payload['summary']['avg_answer_sec']}",
        "",
        "| # | pass | verdict | source_found | phrase_found | second_pass | query |",
        "|---|------|---------|--------------|--------------|-------------|-------|",
    ]
    for r in payload["results"]:
        q = r["query"].replace("|", "\\|")
        lines.append(
            f"| {r['id']} | {'✅' if r['pass'] else '❌'} | {r['verdict']} | "
            f"{'yes' if r['expected_source_found'] else 'no'} | "
            f"{'yes' if r['expected_phrase_found'] else 'no'} | "
            f"{'yes' if r['second_pass_used'] else 'no'} | {q} |"
        )
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(payload["summary"], ensure_ascii=False))
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
