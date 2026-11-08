PY=python3
.PHONY: all calibrate test figures prereg attribution graph denominator realdata clean-results theory-checks
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

denominator:
	$(PY) experiments/denominator.py

realdata:
	$(PY) realdata/real_data_arm.py data/wiki/ results/realdata/

all: calibrate test attribution graph prereg figures

theory-checks:
	$(PY) theory/theory_check_1.py && $(PY) theory/theory_check_2.py
