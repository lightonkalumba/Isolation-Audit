# PREREG: Isolation Audit (Apart Swarm Alignment Hackathon, Track 4)

**Status:** v1. Committed BEFORE any detector output, sweep or real-data analysis exists.
**Rule:** after the commit tagged `prereg-v1`, this file is append-only. Changes go in the Deviations log (section 8) with a timestamp and a reason. Never edit a prediction after seeing a result.

**Commit recipe (run tonight, before any sweep):**

```
git add PREREG.md theory_check_1.py theory_check_2.py
git commit -m "PREREG v1: hypotheses and falsifiers before any sweep"
git tag prereg-v1
git log -1 --format='%H %cI'     # paste hash and time into the report's methods section
```

Authors: [fill in] | Repo: [fill in]

---

## 1. Scope tiers

| Tier | Items |
|---|---|
| **0: must ship** | One MiniBoard channel profile (cache directory names). Detector with the provenance filter. False-alarm calibration. Coverage sweep, random versus hub-targeted loss, with the theory overlay. Limitations and Dual-Use appendix. One-command reproduction. |
| **1: should** | Attribution sweep (P4b). Multiplicity and low-and-slow (P2). Baselines B1, B3 (including zz-regex), B6. Evasions E1 and E6. **Wiki arm (protected: our only outside validation).** |
| **2: bonus** | Other channel profiles. Re-formation after wipe. Compartmentalisation (P5). E4, E5. Baselines B2, B4, B5. |

**Decision rule at Gate G2 (Sunday 17:00 CAT):** if any Tier 0 item is missing, stop all Tier 1 and Tier 2 work.

## 2. Fixed definitions

- **Run graph:** nodes are runs; a *strong* edge A to B exists when B GETs an agent-originated object that A wrote earlier; a *weak* edge when B's LIST returns it. **Primary analysis uses strong edges only**; weak edges are a secondary analysis.
- **Agent-originated:** first creation event is a run's write (judged by effect, including a GET that writes), or a made-up name that the cache then stored.
- **Alert:** largest component size S(t) >= s* and growth >= g*.
- **Detected episode:** an alert fires before the episode ends with precision >= 0.8 on the alerted component.
- **Time to flag:** simulated minutes from the first agent-originated write to the alert.
- **50% contour:** the smallest coverage at which detection probability >= 0.5 (we also report the 90% level for deployers).
- **False-alarm rate:** alerts per 1,000 run-hours on benign episodes.
- **R:** <k(k-1)>/<k> of the strong-edge graph (undirected projection), measured on the *full-log* swarm graph of each episode.


### 2b. Counting rules and episode configuration (fixed before any sweep)

- **Episode:** N runs for T = 12 simulated hours. Primary population N = 500 (also 200 and 1,000).
- **Alert counting:** an alert is a *distinct connected component* that first satisfies the alert rule; later growth or merging of an already-alerted component is not a new alert. **False-alarm rate = alerts on benign episodes / (N x T in hours / 1,000).**
- **Alert rule parameters:** the growth test g* = 0.2 (relative growth of the component over the previous 30 minutes) is fixed a priori; s* is calibrated on calibration seeds.
- **Budgets reported:** 10, **1 (primary)**, 0.1 and 0.01 alerts per 1,000 run-hours. If no s* <= N meets a budget, we report "cannot meet budget".
- **Graph-level theory check (H3a):** configuration-model graphs resampled from the empirical degree distribution of the full-log swarm graph at N in {1k, 5k, 20k, 100k}; measured threshold = peak of the second-largest component; predicted = 1/R.
- **Primary graph:** strong edges only; the allow-list ('/shared/') is applied; the provenance-off ablation (B6) is the naive first-toucher graph.

## 3. Calibration versus test (no peeking)

- Calibration seeds **1000-1029**: set s* and g*, fit tau, n0, K and the discovery rate to METR's anchors (53 agents / 1,188 messages at 3 h; 76 / 1,953 at 6 h).
- Test seeds **2000-2029**: every reported number. Thresholds are never tuned on test seeds.
- Primary false-alarm budget: **1 per 1,000 run-hours** (sensitivity at 0.1 and 10).
- Population sizes: agent-level N in {200, 500, 1000}; graph-level N in {1k, 5k, 20k, 100k}. (The benign S_max-versus-N slope in H2a is computed on the agent-level sizes and, as a check, on the graph-level benign generator up to 100k.)

## 4. Predictions and falsifiers

| ID | Tier | Prediction | Falsified if |
|---|---|---|---|
| **H1** (RQ1) | 0 | The alert fires when at most ~10% of eventual swarm members are coupled (median over test seeds); median time to flag is within +/-50% of the timing formula with fitted tau and n0. | Median coupled fraction at alert > 25%, or B6 (co-activity graph) flags as early or earlier at the same false-alarm budget (95% CIs overlap or B6 earlier). |
| **H2a** (RQ2, P4a) | 0 | With the provenance filter, benign largest-component size grows like ln N: log-log slope of S_max against N is below 0.35 across N in {200, 500, 1000} (agent level) and up to 100,000 (graph-level benign generator). Test false-alarm rate stays within 3x the calibration budget. | Slope >= 0.35, or test false-alarm rate > 3x the calibration budget. |
| **H2b** (RQ2) | 0 | Without the provenance filter, false alarms on the same benign episodes are at least 10x higher. | Ablation false-alarm rate is within 3x of the filtered rate (the filter does not matter). |
| **H3a** (RQ3, P1) | 0 | The measured random-loss 50% contour sits above the theory line 1/R_true by a factor <= 2 at N = 1,000, and the ratio shrinks as N grows over {1k, 5k, 20k, 100k}. | Ratio > 2 at N = 1,000, or the ratio at 100k is not smaller than at 1k. |
| **H3b** (RQ3, P3) | 0 | The fraction of top-degree runs whose blinding drops detection below 50% is within a factor 2 of the value predicted by recomputing R after deletion, and at least 3x smaller than the random-loss tolerance 1 - 1/R_true. | Outside a factor 2 of prediction, or targeted tolerance is not at least 3x smaller than random tolerance. |
| **H3c** (P2) | 1 | Raising mean supporting events per edge from 1 to ~3 lowers the 50% contour by >= 25%; low-and-slow (m toward 1) restores the single-event threshold within +/-20%. | Reduction < 10%. |
| **H4** (RQ2, P4b) | 1 | False alarms pass the budget when (1-a)e crosses (1-d_b)/2, with onset within +/-25% of the predicted value (d_b measured on benign episodes, e per run per window). | Onset more than a factor 2 from the prediction. |
| **H5** (RQ4) | 1 | Rename or convention change (drop 'zz', new naming) changes the audit's detection probability by <= 5 percentage points and cuts the zz-regex baseline's recall by >= 50%. | Audit detection changes by > 10 percentage points. |
| **H6** (RQ5) | 1 | On the public wiki export (identity = label, coupling = edit-after-edit), the alert (s* = 25 labels, growth >= 2x over 24 h) fires before 21 June and before the zz-regex's first hit. Sensitivity table for s* in {10, 25, 50}. **No false-alarm claim.** | The alert fires only after 21 June or after the zz-regex. If the export lacks timestamps or labels: declare no-go and say validation is replica-only. |
| **H7** (RQ6, P5) | 2 | A compartmentalised swarm (every component < s*) is merged by chance cross-links in >= 50% of seeds, or is capped at s* - 1 by construction; a collective-capability proxy falls >= 50% versus an un-partitioned swarm. | The partitioned swarm evades with no capability loss. |
| **H8** | 2 | After a wipe, second detection is >= 25% faster when run-ID and hub state carry over. | Reduction < 10%. |

## 5. Analysis plan

- Unit of replication: one seeded episode. At least 30 test seeds per condition; 95% bootstrap CIs over seeds (10,000 resamples).
- Episodes where the swarm never forms (final coupled fraction < 5% of N) are reported separately and never silently dropped.
- tau, n0, K, discovery rate and thresholds are fitted on calibration seeds only.
- No multiple-comparison correction; **all registered hypotheses are reported, including failures.**
- Real-data arm: identity, coupling rule, thresholds and baselines are fixed above, before looking at the data. No tuning after viewing.
- Experiments freeze at Gate G3 (Sunday 22:00 CAT). Nothing new after that.

## 6. What we report regardless of outcome

Every row in section 4 with its result (pass, fail or not run), the measured-versus-predicted gap, and every deviation.

## 7. Non-claims

- We do not claim how common swarms are, or performance on the real Artifactory logs (not public).
- The wiki arm validates shape and lead time only: identity is labels or IPs, read traces are incomplete, and the export has no benign traffic.
- Numbers such as "survives ~90% random loss but collapses at 2-3% hubs" came from *synthetic* graphs and are predictions until MiniBoard reproduces them.
- We do not claim to detect coordination without logged shared state, or channels outside the logged services.
- Novelty: "to our knowledge, first measured". We cite Frank (2026) as the nearest neighbour.

## 8. Deviations log (append-only)

| Date and time (CAT) | What changed | Why | Who |
|---|---|---|---|
| | | | |
