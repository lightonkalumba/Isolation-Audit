"""TEST stage: uses ONLY test seeds 2000-2029 and thresholds fixed by the calibration stage.
Run once. Writes results/results.json (+ results/raw.json for figures)."""
import json, os, sys, time
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from miniboard.sim import make_episode
from audit.detect import audit, first_good_alert, time_to_reach, flagged_runs, baseline_alert_times, score_alert
from experiments.common import (TEST, BUDGETS, PRIMARY, run_hours, graph_info, pred_random_nodes, pred_events,
                                pred_targeted, make_view, boot_ci, contour)

TH = json.load(open("results/thresholds.json"))
RES = {}; RAW = {}
t_start = time.time()


def tick(msg):
    print("[%4.0fs] %s" % (time.time() - t_start, msg)); sys.stdout.flush()


def s_for(N, budget):
    return TH["s_star"][str(N)][str(float(budget))]


def g_of(s, R, n0):
    return np.log(1 + s * (R - 1) / n0) / np.log(R)


def summarize_detect(eps, results, s, min_precision=0.8):
    rows = []
    for ep, res in zip(eps, results):
        g = first_good_alert(res["alerts"][s], ep.truth, min_precision)
        t0 = ep.truth["t_first_write"]
        if g is None:
            rows.append(dict(detected=0)); continue
        M = set(ep.truth["members"]); fin = set(res["final"])
        rows.append(dict(detected=1, t_flag_min=(g["t"] - t0) / 60.0, coupled_frac=g["coupled"] / len(M), precision=g["precision"],
                         recall=g["recall"], end_precision=len(M & fin) / max(len(fin), 1), end_recall=len(M & fin) / len(M)))
    det = [r for r in rows if r["detected"]]
    def med(k): return float(np.median([r[k] for r in det])) if det else None
    return dict(n=len(rows), detected=len(det) / len(rows), t_flag_median_min=med("t_flag_min"), coupled_frac_median=med("coupled_frac"),
                precision_median=med("precision"), recall_at_alert_median=med("recall"),
                end_precision_median=med("end_precision"), end_recall_median=med("end_recall"), per_episode=rows)


# ======================= T1: benign test, false alarms =======================
tick("T1 benign test episodes")
fp = {}; smax_by_N = {}; benign_stats = {}
for N in (200, 500, 1000):
    ben = [make_episode(N, s, "benign") for s in TEST]
    rh = sum(run_hours(ep) for ep in ben)
    sl = sorted(set(int(TH["s_star"][str(N)][str(float(b))]) for b in BUDGETS if TH["s_star"][str(N)][str(float(b))]) | {3})
    results = [audit(ep, s_stars=sl, collect=True) for ep in ben]
    fp[N] = {}
    for b in BUDGETS:
        s = TH["s_star"][str(N)][str(float(b))]
        a = sum(len(r["alerts"][s]) for r in results)
        fp[N][str(b)] = dict(s_star=s, alerts=a, fpr=a / (rh / 1000.0), episodes_with_alert=sum(1 for r in results if r["alerts"][s]))
    smax_by_N[N] = float(np.mean([r["smax"] for r in results]))
    if N == 500:
        ben500 = ben; ben500_res = results
        d_b = float(np.mean([2 * len(r["edges"]) / ep.N for ep, r in zip(ben, results)]))
        e_elig = float(np.mean([sum(1 for _ in r["edge_events"]) / ep.N for ep, r in zip(ben, results)]))
        benign_stats = dict(d_b=d_b, e_per_run=e_elig, mean_smax=smax_by_N[N])
RES["T1_false_alarms"] = {str(N): fp[N] for N in fp}
RES["T1_benign_smax_by_N"] = {str(N): v for N, v in smax_by_N.items()}
Ns = np.array(sorted(smax_by_N)); Sm = np.array([smax_by_N[n] for n in Ns])
RES["H2a_loglog_slope_agent"] = float(np.polyfit(np.log(Ns), np.log(Sm), 1)[0])
RES["benign_stats_N500"] = benign_stats
tick("FPR @ primary N=500: %s ; S_max by N: %s ; slope %.3f" % (fp[500][str(PRIMARY)], smax_by_N, RES["H2a_loglog_slope_agent"]))

# graph-level benign generator (ER with the measured benign mean degree) up to 100k
rng = np.random.default_rng(np.random.SeedSequence([2000, 99]))
gl = {}
for n in (1000, 5000, 20000, 100000):
    vals = []
    for _ in range(5):
        m = rng.poisson(benign_stats["d_b"] * n / 2); a = rng.integers(0, n, m); b = rng.integers(0, n, m); k = a != b
        g = coo_matrix((np.ones(int(k.sum())), (a[k], b[k])), shape=(n, n)); _, lab = connected_components(g, directed=False)
        vals.append(np.bincount(lab).max())
    gl[n] = float(np.mean(vals))
RES["H2a_graph_level_smax"] = {str(k): v for k, v in gl.items()}
RES["H2a_loglog_slope_graph"] = float(np.polyfit(np.log(list(gl)), np.log(list(gl.values())), 1)[0])
tick("graph-level benign S_max %s slope %.3f" % (gl, RES["H2a_loglog_slope_graph"]))

# ablation: provenance off (B6) on the same benign episodes at the SAME s* as the filtered detector
s1 = s_for(500, PRIMARY); rh500 = sum(run_hours(ep) for ep in ben500)
nv = [audit(ep, s_stars=(s1, TH["s_naive"][str(PRIMARY)]), provenance=False) for ep in ben500]
a_same = sum(len(r["alerts"][s1]) for r in nv)
share = float(np.mean([len(r["final"]) / ep.N for ep, r in zip(ben500, nv)]))
RES["H2b_ablation"] = dict(s_same=s1, alerts=a_same, fpr_same_s=a_same / (rh500 / 1000.0), filtered_fpr=fp[500][str(PRIMARY)]["fpr"],
                           ratio=(a_same / (rh500 / 1000.0)) / max(fp[500][str(PRIMARY)]["fpr"], 1e-9),
                           naive_largest_component_share_of_runs=share, s_naive_primary=TH["s_naive"][str(PRIMARY)])
tick("H2b ablation: %s" % RES["H2b_ablation"])

# ======================= T2: swarm test, detection and timing =======================
tick("T2 swarm test episodes")
det = {}; graphs = {}
for N in (200, 500, 1000):
    sw = [make_episode(N, s, "swarm") for s in TEST]
    sl = sorted(set(int(TH["s_star"][str(N)][str(float(b))]) for b in BUDGETS if TH["s_star"][str(N)][str(float(b))]) | {3})
    results = [audit(ep, s_stars=sl, collect=True) for ep in sw]
    det[N] = {}
    for b in (PRIMARY, 0.1):
        s = s_for(N, b)
        det[N][str(b)] = summarize_detect(sw, results, s); det[N][str(b)]["s_star"] = s
    if N == 500:
        sw500, sw500_res = sw, results
        gis = [graph_info(r["edges"], ep.N) for ep, r in zip(sw, results)]
        RES["swarm500_graph"] = dict(R=[g["R"] for g in gis], comp=[g["comp"] for g in gis], meandeg=[g["meandeg"] for g in gis],
                                     maxdeg_frac=[g["maxdeg_frac"] for g in gis], members=[len(ep.truth["members"]) for ep in sw])
        graphs[N] = gis
tick("detection summaries done")
for N in det:
    for b in det[N]:
        d = det[N][b]; d.pop("per_episode", None) if N != 500 else None
RES["T2_detection"] = {str(N): det[N] for N in det}
d500 = det[500][str(PRIMARY)]
tick("N=500 primary: detected %.2f, t_flag median %.1f min, coupled frac %.3f" % (d500["detected"], d500["t_flag_median_min"] or -1, d500["coupled_frac_median"] or -1))

# timing formula test (parameters fitted on calibration seeds only)
fit = TH["timing_fit"]; s1 = s_for(500, PRIMARY)
ratios = []
for ep, res, gi in zip(sw500, sw500_res, graphs[500]):
    t0 = ep.truth["t_first_write"]; tobs = time_to_reach(res["Shist"], s1, t0)
    if tobs and gi["R"] > 1:
        pred = fit["delta"] + fit["tau"] * g_of(s1, gi["R"], fit["n0"]); ratios.append(tobs / pred)
RES["H1_timing"] = dict(median_ratio_obs_over_pred=float(np.median(ratios)), within_50pct=bool(0.5 <= np.median(ratios) <= 1.5), n=len(ratios), fit=fit)
tick("H1 timing ratio median %.2f" % np.median(ratios))

# baselines at matched budget (N=500)
M_sets = [set(ep.truth["members"]) for ep in sw500]
def baseline_detect(which, k):
    out = []
    for ep, Ms in zip(sw500, M_sets):
        fl = flagged_runs(ep, None, None, which); t0 = ep.truth["t_first_write"]; hit = None
        for j in range(1, len(fl) // k + 1):
            S = set(r for _, r in fl[: j * k])
            if len(S & Ms) / len(S) >= 0.8:
                hit = (fl[j * k - 1][0] - t0) / 60.0; break
        out.append(hit)
    ok = [x for x in out if x is not None]
    return dict(k=k, detected=len(ok) / len(out), t_flag_median_min=float(np.median(ok)) if ok else None)
RES["T3_baselines"] = {"zz_regex": baseline_detect("zz", TH["k"]["zz"][str(PRIMARY)]),
                       "op_anomaly": baseline_detect("op", TH["k"]["op"][str(PRIMARY)])}
sn = TH["s_naive"][str(PRIMARY)]
nres = [audit(ep, s_stars=(sn,), provenance=False) for ep in sw500]
RES["T3_baselines"]["B6_naive"] = summarize_detect(sw500, nres, sn); RES["T3_baselines"]["B6_naive"].pop("per_episode"); RES["T3_baselines"]["B6_naive"]["s_star"] = sn
tick("baselines: %s" % {k: {kk: vv for kk, vv in v.items() if kk in ("detected", "t_flag_median_min")} for k, v in RES["T3_baselines"].items()})

# E1: convention change (no 'zz')
sw_nz = [make_episode(500, s, "swarm", zz=False) for s in TEST]
r_nz = [audit(ep, s_stars=(s1,)) for ep in sw_nz]
e1 = summarize_detect(sw_nz, r_nz, s1); e1.pop("per_episode")
Ms_nz = [set(ep.truth["members"]) for ep in sw_nz]
zz_nz = sum(1 for ep in sw_nz if len(flagged_runs(ep, None, None, "zz")) >= 1)
RES["H5_E1"] = dict(audit_detected_zz=d500["detected"], audit_detected_nozz=e1["detected"], audit_t_nozz=e1["t_flag_median_min"],
                    zz_regex_episodes_flagged_nozz=zz_nz, zz_regex_detected_zz=RES["T3_baselines"]["zz_regex"]["detected"])
tick("E1: %s" % RES["H5_E1"])

# ======================= T3: coverage sweeps =======================
tick("T4 coverage sweeps")
rng_ci = np.random.default_rng(12345)
R_list = np.array([g["R"] for g in graphs[500]])
pr_runs = [pred_random_nodes(R) for R in R_list]
pr_reads = [pred_events(g["m"], R) for g, R in zip(graphs[500], R_list)]
pr_reads_m1 = [1.0 / R for R in R_list]
pr_tgt = [pred_targeted(g, 500)[1] for g in graphs[500]]
orders = [np.argsort(-g["deg"], kind="stable") for g in graphs[500]]
# dedupe masks (m = 1: only the first supporting read of each pair is kept)
dd_masks = []
for ep, res in zip(sw500, sw500_res):
    mk = np.ones(len(ep.t), bool); seen = set()
    for eidx, key in res["edge_events"]:
        if key in seen: mk[eidx] = False
        else: seen.add(key)
    dd_masks.append(mk)
MODES = {
    "runs":     [0, .2, .4, .6, .8, .9, .95, .97, .98, .99],
    "reads":    [1, .5, .3, .2, .1, .05, .03, .02, .01],
    "reads_m1": [1, .5, .3, .2, .1, .05, .03, .02, .01],
    "all":      [1, .5, .3, .2, .1, .05, .03, .02, .01],
    "hubs":     [0, .002, .004, .006, .01, .015, .02, .03, .05, .08, .12, .2],
}
CODE = {"runs": 1, "reads": 2, "reads_m1": 3, "all": 4, "hubs": 5}
sweep = {}
for mode, grid in MODES.items():
    ck = "results/sweep_%s.json" % mode
    if os.path.exists(ck):
        sweep[mode] = json.load(open(ck)); tick("sweep %s loaded from checkpoint" % mode); continue
    prob = []; lo = []; hi = []
    for lv in grid:
        ind = []
        for i, (ep, sd) in enumerate(zip(sw500, TEST)):
            rng = np.random.default_rng(np.random.SeedSequence([sd, CODE[mode], int(round(lv * 10000))]))
            base = "reads" if mode == "reads_m1" else mode
            mask, run = make_view(ep, rng, base, lv, order=orders[i], dedupe_mask=dd_masks[i] if mode == "reads_m1" else None)
            res = audit(ep, mask=mask, run=run, s_stars=(s1,))
            ind.append(1 if first_good_alert(res["alerts"][s1], ep.truth) else 0)
        p = float(np.mean(ind)); l, h = boot_ci(ind, rng_ci, 2000)
        prob.append(p); lo.append(l); hi.append(h)
    sweep[mode] = dict(grid=grid, prob=prob, lo=lo, hi=hi)
    json.dump(sweep[mode], open(ck, "w"))
    tick("sweep %s: %s" % (mode, [round(x, 2) for x in prob]))
RES["T4_sweeps"] = sweep
RES["T4_predictions"] = dict(random_runs_median=float(np.median(pr_runs)), reads_median=float(np.median([x for x in pr_reads if x])),
                             reads_m1_median=float(np.median(pr_reads_m1)), targeted_median=float(np.median(pr_tgt)),
                             R_median=float(np.median(R_list)), mean_m=float(np.median([g["m"].mean() for g in graphs[500]])))
# measured contours
loss = sweep["runs"]; RES["T4_measured"] = {}
RES["T4_measured"]["runs_collapse_fraction_unobserved"] = contour(loss["grid"], loss["prob"], 0.5, increasing=False)
RES["T4_measured"]["hubs_collapse_fraction_blinded"] = contour(sweep["hubs"]["grid"], sweep["hubs"]["prob"], 0.5, increasing=False)
for mode in ("reads", "reads_m1", "all"):
    g = sweep[mode]["grid"][::-1]; p = sweep[mode]["prob"][::-1]
    RES["T4_measured"][mode + "_c_at_50pct"] = contour(g, p, 0.5, increasing=True)
tick("measured: %s ; predicted: %s" % (RES["T4_measured"], RES["T4_predictions"]))

# ======================= T5: attribution sweep =======================
tick("T5 attribution sweep")
A_GRID = [1.0, .95, .9, .8, .7, .6, .5, .4, .3, .2]
att = {}
if os.path.exists("results/att.json"):
    att = json.load(open("results/att.json")); A_GRID_RUN = []
else:
    A_GRID_RUN = A_GRID
for a in A_GRID_RUN:
    al = 0; ind = []
    for ep, sd in zip(ben500, TEST):
        rng = np.random.default_rng(np.random.SeedSequence([sd, 6, int(round(a * 1000))]))
        mask, run = make_view(ep, rng, "attrib", a)
        al += len(audit(ep, mask=mask, run=run, s_stars=(s1,))["alerts"][s1])
    for ep, sd in zip(sw500, TEST):
        rng = np.random.default_rng(np.random.SeedSequence([sd, 7, int(round(a * 1000))]))
        mask, run = make_view(ep, rng, "attrib", a)
        ind.append(1 if first_good_alert(audit(ep, mask=mask, run=run, s_stars=(s1,))["alerts"][s1], ep.truth) else 0)
    att[str(a)] = dict(fpr=al / (rh500 / 1000.0), detect=float(np.mean(ind)))
    json.dump(att, open("results/att.json", "w"))
RES["T5_attribution"] = dict(grid=A_GRID, table=att, d_b=benign_stats["d_b"], e_per_run=benign_stats["e_per_run"],
                             predicted_onset_1ma_e=(1 - benign_stats["d_b"]) / 2)
tick("attribution: %s" % {k: round(v["fpr"], 2) for k, v in att.items()})

# ======================= T6: structure sensitivity (flat hubs) =======================
sw_flat = [make_episode(500, s, "swarm", coord_boost=1.0, pop_coord=1.0, assign_targets=0) for s in TEST]
rf = [audit(ep, s_stars=(s1,), collect=True) for ep in sw_flat]
gf = [graph_info(r["edges"], ep.N) for ep, r in zip(sw_flat, rf)]
dfl = summarize_detect(sw_flat, rf, s1); dfl.pop("per_episode")
RES["T6_flat_hubs"] = dict(detection=dfl, R_median=float(np.median([g["R"] for g in gf])), maxdeg_frac_median=float(np.median([g["maxdeg_frac"] for g in gf])),
                           pred_targeted_median=float(np.median([pred_targeted(g, 500)[1] for g in gf])),
                           pred_random_median=float(np.median([pred_random_nodes(g["R"]) for g in gf])))
tick("flat hubs: %s" % RES["T6_flat_hubs"])

# ======================= raw series for figures =======================
RAW["Shist"] = {"swarm": [[(float(t), int(S)) for t, S in sw500_res[i]["Shist"]] for i in range(3)],
                "benign": [[(float(t), int(S)) for t, S in ben500_res[i]["Shist"]] for i in range(3)],
                "t_first_write": [sw500[i].truth["t_first_write"] for i in range(3)],
                "alert_t": [first_good_alert(sw500_res[i]["alerts"][s1], sw500[i].truth)["t"] if first_good_alert(sw500_res[i]["alerts"][s1], sw500[i].truth) else None for i in range(3)]}
RAW["detect_time_by_method"] = {"audit": [r.get("t_flag_min") for r in d500["per_episode"]]}
json.dump(RES, open("results/results.json", "w"), indent=1, default=lambda o: None if o is None else float(o))
json.dump(RAW, open("results/raw.json", "w"))
tick("test stage done; results saved")
