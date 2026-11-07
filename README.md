# Isolation Audit

Apart Swarm Alignment Hackathon, Track 4. Detect swarm formation from the logs of supposedly isolated runs: nodes are runs, an edge means run A wrote an
agent-originated shared object and run B later read it; alert on the size and growth of the largest connected component.

**Read PREREG.md first.** It was committed and tagged `prereg-v1` before any code existed (`git log --reverse` shows it). Results are judged against it.

## Reproduce (about 3 minutes, CPU only)
```
pip install -r requirements.txt
make all          # calibrate -> test -> attribution -> graph-level -> PREREG table -> figures
```
Outputs: `results/*.json`, `results/PREREG_RESULTS.md` (pass/fail for every registered row), `figures/*.png`. A second `make all` from scratch reproduced the
first run exactly (fixed seeds). `make theory-checks` runs the two synthetic theory scripts.

## Layout
- `miniboard/sim.py` replica of the incident channel (shared cache, directory names as messages). Contract log format in `data/samples/*.jsonl`.
- `audit/detect.py` provenance by effect, strong/weak edges, streaming union-find, per-component alert rule, baselines.
- `experiments/` `calibrate.py` (seeds 1000-1029 only), `test_stage.py` (seeds 2000-2029), `attribution_fix.py`, `graph_level.py`, `prereg_eval.py`.
- `theory/` `theory_check_1.py`, `theory_check_2.py` (synthetic Monte Carlo checks of the percolation formulas).
- `docs/DEVLOG.md` every design decision and every deviation from PREREG, in order.

## Honest status
- All results are on a replica we built and calibrated to METR/OpenAI numbers. The real-data arm (collusion.wiki, H6) was NOT run.
- Registered predictions that FAILED on the replica: H2a, H2b, H4. They are reported, not hidden (see PREREG_RESULTS.md).
- Tier 2 items (H7, H8, other channel profiles) were not built.

## Provenance and AI assistance
All code in this repository was written during the hackathon weekend (nothing pre-existing). An AI assistant (Claude) wrote most of the code and the first
draft of the report text under the lead's direction; the team is responsible for checking it. Review the code before relying on any number.
