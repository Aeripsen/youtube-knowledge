"""Reproduce the choice of stub thresholds. Uses the dev split only.

    python -m evals.tune

Rule: maximize the mean of refusal accuracy and (1 - false refusal rate) on dev.
Ties go to the smaller min_score, then the smaller min_coverage.
"""
from __future__ import annotations

from evals.answerers import StubAnswerer
from evals.run import run

SCORES = (0.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
COVERAGES = (0.3, 0.4, 0.5, 0.6, 0.7)


def main() -> None:
    best = None
    for ms in SCORES:
        for mc in COVERAGES:
            dev = run(StubAnswerer(ms, mc))["metrics"]["dev"]["refusal"]
            balanced = (dev["refusal_accuracy_unanswerable"] + 1 - dev["false_refusal_rate_answerable"]) / 2
            print(f"min_score={ms:<4} min_coverage={mc:<4} balanced={balanced:.4f} {dev}")
            if best is None or balanced > best[0]:
                best = (balanced, ms, mc)
    print(f"chosen: min_score={best[1]} min_coverage={best[2]} (dev balanced {best[0]:.4f})")


if __name__ == "__main__":
    main()
