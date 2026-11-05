"""Run the evaluation and write a results file.

    python -m evals.run                         # offline stub, writes evals/results/stub.json
    python -m evals.run --check                 # fail if the stub run differs from the committed file
    python -m evals.run --provider anthropic --model <model-id>   # needs ANTHROPIC_API_KEY
    python -m evals.run --provider anthropic --model <id> --llm-judge

The stub run is deterministic: same inputs give a byte-identical results file.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from evals import metrics as M
from evals.answerers import (STUB_CANDIDATE_CHUNKS, STUB_MIN_COVERAGE, STUB_MIN_SCORE,
                             AnthropicAnswerer, LLMJudge, StubAnswerer)
from evals.golden import PROJECT_ROOT, load_questions, load_transcripts, text_in_range
from evals.retrieve import BM25, CHUNK_SECONDS, chunk_transcripts

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
K_VALUES = (1, 3, 5, 10)
K_MAX = max(K_VALUES)
SPLITS = ("all", "dev", "heldout")


def _r(x):
    return None if x is None else round(x, 4)


def score_question(q: dict, transcripts, index: BM25, answerer, judge=None) -> dict:
    hits = index.search(q["question"], K_MAX)
    ans = answerer.answer(q["question"], hits)
    row = {
        "id": q["id"], "split": q["split"], "answerable": q["answerable"],
        "video_id": q["video_id"], "question": q["question"],
        "refused": ans.refused, "answer": ans.text,
        "cite": None if ans.cite is None else
        {"video_id": ans.cite.video_id, "start": ans.cite.start, "end": ans.cite.end},
        "top_hit": {"video_id": hits[0][0].video_id, "start": hits[0][0].start,
                    "end": hits[0][0].end, "score": hits[0][1]},
    }
    if not q["answerable"]:
        return row

    gold = M.Span(q["video_id"], q["span"]["start"], q["span"]["end"])
    segs = transcripts[q["video_id"]]
    row["gold_span"] = q["span"]
    row["rank"] = M.first_relevant_rank([c.span for c, _ in hits], gold)
    if ans.refused:
        return row

    row["citation_valid"] = M.citation_valid(ans.cite, gold)
    cited_text = "" if ans.cite is None else text_in_range(
        transcripts.get(ans.cite.video_id, []), ans.cite.start, ans.cite.end)
    gold_text = text_in_range(segs, gold.start, gold.end)
    row["faithful_to_cited"] = M.entails_lite(ans.text, cited_text)
    row["supported_by_gold"] = M.entails_lite(ans.text, gold_text)
    answer_tokens = set(M.content_tokens(ans.text))
    row["has_key_terms"] = all(set(M.content_tokens(k)) <= answer_tokens for k in q["key_terms"])
    if judge is not None:
        row["llm_judge_supported_by_cited"] = judge.supported(ans.text, cited_text)
    return row


def aggregate(rows: list[dict]) -> dict:
    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    answered = [r for r in answerable if not r["refused"]]
    ranks = [r["rank"] for r in answerable]
    out = {
        "n_answerable": len(answerable),
        "n_unanswerable": len(unanswerable),
        "n_answered": len(answered),
        "retrieval": {f"recall@{k}": _r(M.recall_at_k(ranks, k)) for k in K_VALUES},
        "answers": {
            # Denominator: answerable questions the system did not refuse.
            "citation_validity": _r(M.rate([r["citation_valid"] for r in answered])),
            "faithfulness_to_cited_span_deterministic": _r(M.rate([r["faithful_to_cited"] for r in answered])),
            "supported_by_gold_span_deterministic": _r(M.rate([r["supported_by_gold"] for r in answered])),
            "contains_reference_key_terms": _r(M.rate([r["has_key_terms"] for r in answered])),
        },
        "refusal": {
            "refusal_accuracy_unanswerable": _r(M.rate([r["refused"] for r in unanswerable])),
            "false_refusal_rate_answerable": _r(M.rate([r["refused"] for r in answerable])),
        },
    }
    out["retrieval"][f"mrr@{K_MAX}"] = _r(M.mean_reciprocal_rank(ranks, K_MAX))
    judged = [r["llm_judge_supported_by_cited"] for r in answered if "llm_judge_supported_by_cited" in r]
    if judged:
        out["answers"]["SECOND_OPINION_llm_judge_faithfulness_to_cited_span"] = _r(M.rate(judged))
    return out


def run(answerer, judge=None, provider_config: dict | None = None) -> dict:
    transcripts = load_transcripts()
    questions = load_questions()
    index = BM25(chunk_transcripts(transcripts))
    rows = [score_question(q, transcripts, index, answerer, judge) for q in questions]
    return {
        "config": {
            "provider": answerer.name,
            **(provider_config or {}),
            "llm_judge": judge is not None,
            "retriever": "bm25", "chunk_seconds": CHUNK_SECONDS, "k_values": list(K_VALUES),
            "min_overlap_fraction": M.MIN_OVERLAP_FRACTION,
            "max_citation_seconds": M.MAX_CITATION_SECONDS,
            "min_support_ratio": M.MIN_SUPPORT_RATIO,
            "n_chunks": len(index.chunks),
            "n_transcripts": len(transcripts),
        },
        "metrics": {s: aggregate([r for r in rows if s == "all" or r["split"] == s]) for s in SPLITS},
        "questions": rows,
    }


def dumps(result: dict) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def stub_result() -> dict:
    return run(StubAnswerer(), provider_config={
        "stub_min_score": STUB_MIN_SCORE, "stub_min_coverage": STUB_MIN_COVERAGE,
        "stub_candidate_chunks": STUB_CANDIDATE_CHUNKS})


def summary(result: dict) -> str:
    lines = [f"provider={result['config']['provider']}"]
    for split in SPLITS:
        m = result["metrics"][split]
        flat = {**m["retrieval"], **m["answers"], **m["refusal"]}
        lines.append(f"[{split}] answerable={m['n_answerable']} answered={m['n_answered']} "
                     f"unanswerable={m['n_unanswerable']}")
        lines += [f"    {k:58s} {v}" for k, v in flat.items()]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=("stub", "anthropic"), default="stub")
    ap.add_argument("--model", default=os.environ.get("YK_EVAL_MODEL"),
                    help="model id for --provider anthropic and --llm-judge (or set YK_EVAL_MODEL)")
    ap.add_argument("--llm-judge", action="store_true",
                    help="also score faithfulness with an LLM judge (second opinion, off by default)")
    ap.add_argument("--out", type=Path, help="results path (default evals/results/<provider>.json)")
    ap.add_argument("--check", action="store_true",
                    help="stub only: exit 1 if the result differs from the committed file")
    args = ap.parse_args(argv)

    needs_api = args.provider == "anthropic" or args.llm_judge
    key = os.environ.get("ANTHROPIC_API_KEY")
    if needs_api and not key:
        print("ANTHROPIC_API_KEY is not set; use the default stub provider to run offline.", file=sys.stderr)
        return 2
    if needs_api and not args.model:
        print("set --model or YK_EVAL_MODEL to choose the model id.", file=sys.stderr)
        return 2

    judge = LLMJudge(args.model, key) if args.llm_judge else None
    if args.provider == "stub" and judge is None:
        result = stub_result()
    elif args.provider == "stub":
        result = run(StubAnswerer(), judge)
    else:
        result = run(AnthropicAnswerer(args.model, key), judge, provider_config={"model": args.model})

    suffix = "+judge" if judge else ""
    out = args.out or RESULTS_DIR / f"{args.provider}{suffix}.json"
    text = dumps(result)
    if args.check:
        if args.provider != "stub" or judge is not None:
            print("--check only applies to the offline stub run.", file=sys.stderr)
            return 2
        committed = (RESULTS_DIR / "stub.json").read_text(encoding="utf-8")
        if committed != text:
            print("stub results differ from evals/results/stub.json", file=sys.stderr)
            return 1
        print("stub results match evals/results/stub.json")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(summary(result))
    print(f"wrote {out.relative_to(PROJECT_ROOT) if out.is_relative_to(PROJECT_ROOT) else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
