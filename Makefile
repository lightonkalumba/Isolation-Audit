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

all: calibrate test figures prereg

theory-checks:
	$(PY) theory/theory_check_1.py && $(PY) theory/theory_check_2.py
