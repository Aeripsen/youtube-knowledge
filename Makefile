PYTHON ?= python3

.PHONY: eval eval-check eval-llm eval-tune test

# Offline, deterministic, no API key. Writes evals/results/stub.json.
eval:
	$(PYTHON) -m evals.run

# Fail if a fresh stub run differs from the committed results file.
eval-check:
	$(PYTHON) -m evals.run --check

# Real provider. Needs ANTHROPIC_API_KEY and YK_EVAL_MODEL (a model id).
# Writes evals/results/anthropic+judge.json. Drop --llm-judge to skip the second opinion.
eval-llm:
	$(PYTHON) -m evals.run --provider anthropic --llm-judge

# Reprint the dev-split sweep that chose the stub thresholds.
eval-tune:
	$(PYTHON) -m evals.tune

test:
	$(PYTHON) -m unittest discover -s tests -t .
