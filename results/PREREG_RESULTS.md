# PREREG results (replica, test seeds 2000-2029, thresholds from calibration seeds 1000-1029)

| ID | Tier | Verdict | Evidence |
|---|---|---|---|
| H1 | 0 | **PASS** | coupled fraction at alert 0.085 (<=0.10, falsifier >0.25); timing ratio obs/pred 0.91 (within 0.5-1.5); B6 detects 0.00 vs audit 0.97. Caveat: fitted tau, n0 sit on fit bounds; zz-regex (zz present) flags at minute 0, earlier than the audit. |
| H2a | 0 | **FALSIFIED** | agent-level benign S_max {'200': 4.2, '500': 9.7, '1000': 16.0}, log-log slope 0.84 (need <0.35); graph-level ER slope 0.11 (by construction); test false-alarm rate 0.87 vs budget 1.0 (limit 3x) OK. |
| H2b | 0 | **FALSIFIED** | alert-rate ratio naive/filtered at same s*: 2.32 (need >=10; falsified if <=3). Supplement: naive graph puts 100% of runs in one component and detects 0 of 30 swarms at precision>=0.8; filtered detects 97%. |
| H3a | 0 | **PASS** | graph-level measured/predicted: 1k: 1.13, 5k: 1.15, 20k: 1.00, 100k: 1.03 (grid resolution ~0.1; not monotone at 5k). |
| H3b | 0 | **PASS** | hub-targeted collapse measured 0.043 vs predicted 0.038 (ratio 1.14, need within 2x); random-loss tolerance 0.83 is 19x the hub-targeted one (need >=3x). Random-loss theory 0.92 vs measured 0.83 (theory optimistic). |
| H3c | 1 | **PASS (clause 1 only)** | 50% contour: natural multiplicity (mean m=2.4) c=0.010 vs m=1 c=0.025: reduction 60% (need >=25%). The low-and-slow clause (E3) was not run. |
| H4 | 1 | **FALSIFIED** | e=17.3 eligible reads/run, d_b=0.23: predicted onset (1-a)e=0.39 (a*=0.978); measured onset 0.11 (ratio 0.28, need within 2x). False alarms rise earlier than predicted; detection falls to 67% at a=0.99. |
| H5 | 1 | **PASS** | audit detection with zz 0.97 vs without 0.97 (change <=5 pp); zz-regex flags 0/30 episodes without zz (recall 100% -> 0%). |
| H6 | 1 | **NOT RUN** | wiki arm needs the real collusion.wiki export (owner: Real-data engineer). Validation is replica-only until it runs. |
| H7 | 2 | **NOT RUN** | compartmentalisation not run. |
| H8 | 2 | **NOT RUN** | re-formation not run. |
