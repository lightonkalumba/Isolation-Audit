# Correction: the hub-fragility threshold was reported in the wrong unit

**Status:** found after the real-data arm ran. Post hoc, not pre-registered.
Reported in Section 4.2 and Appendix A of the v2 report rather than quietly
restating the corrected figure.

## What we claimed

The first version of this work reported that the audit collapses once **4.3% of
runs** are blinded by degree, against a Molloy–Reed prediction of 3.8% (H3b,
PASS). When the real-data arm gave a collapse at roughly **20% of nodes**, we
wrote that the replica had overstated hub fragility by about five times.

## What was wrong

Both numbers are *blinded nodes ÷ audited population*. They are not the same
quantity, because the two populations are not the same thing:

| | Replica | Real wiki graph |
|---|---|---|
| Audited population | 500 runs | 2,584 nodes |
| Swarm's coupled component | 55 (median) | 2,462 |
| Swarm share of the population | **11%** | **about 100%** |

In the replica the swarm is a small dense component inside a much larger fleet.
In the export, the publishers filtered to agent traffic, so essentially every
node *is* a swarm member. Dividing by the audited population therefore folds in
swarm prevalence, which differs between the two settings by roughly 9×.

**The direction of the claim was backwards.** On a common basis — share of the
swarm's own coupled component:

| | Replica | Real swarm |
|---|---|---|
| Molloy–Reed prediction | 0.365 | 0.212 |
| Measured | 0.39 (detection) | 0.15 – 0.24 (component) |

The real swarm is about **1.7× more** hub-fragile than our replica, not five
times less.

## How we tested the explanation

`experiments/denominator.py` sweeps the share of runs that discover the board
while holding everything else fixed (calibration seeds only):

| Swarm prevalence | Threshold per fleet | Threshold per component |
|---|---|---|
| 11.3% | 0.048 | 0.419 |
| 13.4% | 0.051 | 0.395 |
| 16.9% | 0.072 | 0.435 |
| 26.1% | 0.108 | 0.413 |
| 37.5% | 0.167 | 0.430 |

Per fleet: **3.5× spread**. Per component: **1.1× spread**.

A fragility threshold quoted as a share of the audited fleet is not a property
of the swarm. It is a property of how much of your fleet the swarm happened to
occupy during the test, and it does not transfer between deployments.

## What survives

The percolation account itself. On test seeds the same script measures the
replica's *detection* collapse at **0.39 of the coupled component** against a
predicted **0.365** — a ratio of 1.08. On the real graph the component halves at
0.15 and is gone by 0.24, bracketing the predicted 0.212. One prediction, two
swarms, both within about 15%.

So the theory predicts not just when the component fragments but when detection
fails — in the right units.

## What changed in the repo

- `experiments/denominator.py` added (post hoc; labelled as such in its header).
- `results/denominator.json` written by it.
- H3b in the report's Appendix B now reads **PASS (units corrected post hoc)**:
  the registered test passes exactly as written, and the correction is about
  what the passing number means outside the replica.

## Why this is in the repo rather than buried

The error was invisible until real data supplied a population with a different
swarm prevalence. That is the whole argument for running a real-data arm at all,
so removing the evidence would remove the point.
