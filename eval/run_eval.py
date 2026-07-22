"""Run eval_questions.py cases through chain.answer_with_sources and score them.

Usage:
    python -m eval.run_eval

Checks per case:
  - Citation format: does the answer contain at least one [n] reference?
    (Skipped for expected-refusal cases.)
  - Fiscal year correctness: if fiscal_year was set, do ALL cited chunks
    actually come from that year? (Catches metadata/filter bugs.)
  - Content: if expected_substrings is non-empty, does at least one appear
    in the answer (case-insensitive)?
  - Refusal behavior: for expect_refusal cases, does the answer actually
    decline instead of fabricating?

Writes a timestamped markdown report to eval/results.md.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chain import answer_with_sources
from eval.eval_questions import EVAL_CASES

REFUSAL_TEXT = "I don't have enough information in the retrieved filings to answer that."
CITATION_RE = re.compile(r"\[\d+\]")


def run_case(case: dict) -> dict:
    result = answer_with_sources(
        case["question"],
        ticker=case.get("ticker"),
        form_type=case.get("form_type"),
        fiscal_year=case.get("fiscal_year"),
    )
    answer = result["answer"]
    sources = result["sources"]

    checks = {}

    if case["expect_refusal"]:
        checks["refused_correctly"] = REFUSAL_TEXT in answer
    else:
        checks["has_citation"] = bool(CITATION_RE.search(answer))
        checks["not_a_refusal"] = REFUSAL_TEXT not in answer

        if case.get("fiscal_year") is not None and sources:
            years = {s["metadata"].get("fiscal_year") for s in sources}
            checks["year_matches"] = years == {case["fiscal_year"]}

        if case.get("expected_substrings"):
            lower = answer.lower()
            checks["content_match"] = any(s.lower() in lower for s in case["expected_substrings"])

    passed = all(checks.values()) if checks else False

    return {
        "id": case["id"],
        "question": case["question"],
        "answer": answer,
        "num_sources": len(sources),
        "checks": checks,
        "passed": passed,
    }


def main() -> None:
    results = []
    for i, case in enumerate(EVAL_CASES, start=1):
        print(f"[{i}/{len(EVAL_CASES)}] {case['id']} ... ", end="", flush=True)
        r = run_case(case)
        results.append(r)
        print("PASS" if r["passed"] else "FAIL")

    passed_count = sum(r["passed"] for r in results)
    total = len(results)
    print()
    print(f"Score: {passed_count}/{total} passed ({passed_count/total:.0%})")

    failed = [r for r in results if not r["passed"]]
    if failed:
        print()
        print("Failed cases:")
        for r in failed:
            print(f"  - {r['id']}: {r['checks']}")

    write_report(results, passed_count, total)


def write_report(results: list[dict], passed_count: int, total: int) -> None:
    lines = [
        "# Ask Your 10-K -- Eval Report",
        "",
        f"Run at: {datetime.now().isoformat(timespec='seconds')}",
        f"Score: {passed_count}/{total} ({passed_count/total:.0%})",
        "",
        "| ID | Passed | Checks | Sources |",
        "|---|---|---|---|",
    ]
    for r in results:
        checks_str = ", ".join(f"{k}={v}" for k, v in r["checks"].items())
        lines.append(f"| {r['id']} | {'✅' if r['passed'] else '❌'} | {checks_str} | {r['num_sources']} |")

    lines.append("")
    lines.append("## Full answers")
    for r in results:
        lines.append(f"### {r['id']}")
        lines.append(f"**Q:** {r['question']}")
        lines.append("")
        lines.append(f"**A:** {r['answer']}")
        lines.append("")

    report_path = Path(__file__).resolve().parent / "results.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()