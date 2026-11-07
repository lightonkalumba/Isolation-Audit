PY=python3
export PYTHONPATH := $(shell pwd)

calibrate:
	$(PY) experiments/calibrate.py

test:
	$(PY) experiments/test_stage.py

figures:
	$(PY) figures/make_figures.py

prereg:
	$(PY) experiments/prereg_eval.py

attribution:
	$(PY) experiments/attribution_fix.py

graph:
	$(PY) experiments/graph_level.py

clean-results:
	rm -f results/*.json results/*.log

all: calibrate test attribution graph prereg figures

theory-checks:
	$(PY) theory/theory_check_1.py && $(PY) theory/theory_check_2.py
