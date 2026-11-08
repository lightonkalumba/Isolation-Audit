"""Post hoc (not pre-registered). Added after the real-data arm.

Why: the replica's hub-collapse threshold and the real swarm's were both quoted
as (component nodes removed) / (total runs). The replica's swarm is ~12% of its
fleet; the real export is ~100% swarm, so the two numbers are not comparable.
This script recomputes both on a common basis and measures how much of the
apparent difference is swarm prevalence.

Outputs results/denominator.json.
"""
import json, sys
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from miniboard.sim import make_episode
from audit.detect import audit, first_good_alert
from experiments.common import (TEST, CAL, graph_info, pred_targeted, pred_random_nodes,
                                make_view, contour)

OUT = "results/denominator.json"
RES = {}
S_STAR = 4                      # primary budget at N = 500 (from calibration)


def comp_curve(gi, N, levels, mode="hubs", seed=0):
    """Largest-component size under blinding, as a share of the UNBLINDED component."""
    nodes = gi["nodes"]
    idx = {int(v): i for i, v in enumerate(nodes)}
    n = len(nodes)
    a = np.array([idx[int(x)] for x in gi["a"]])
    b = np.array([idx[int(x)] for x in gi["b"]])
    deg = gi["deg"][nodes].astype(float)
    order = np.argsort(-deg, kind="stable")
    rng = np.random.default_rng(seed)

    def giant(keep):
        m = keep[a] & keep[b]
        if m.sum() == 0:
            return int(keep.sum() > 0)
        A = coo_matrix((np.ones(m.sum()), (a[m], b[m])), shape=(n, n))
        _, l = connected_components(A, directed=False)
        l = l[keep]
        return int(np.bincount(l).max()) if len(l) else 0

    g0 = giant(np.ones(n, bool))
    out = []
    for lv in levels:
        if mode == "hubs":
            keep = np.ones(n, bool)
            keep[order[:int(round(lv * n))]] = False
            out.append(giant(keep) / g0)
        else:
            v = [giant(rng.random(n) >= lv) / g0 for _ in range(10)]
            out.append(float(np.mean(v)))
    return np.array(out), g0


# ---------- 1. replica, test seeds: structure on a per-component basis ----------
print("1. replica structure (test seeds, N=500)")
lv_h = np.round(np.arange(0, 0.81, 0.02), 3)
lv_r = np.round(np.arange(0, 1.0, 0.04), 3)
rows = []
for sd in TEST:
    ep = make_episode(500, sd, "swarm")
    r = audit(ep, s_stars=[S_STAR], collect=True)
    gi = graph_info(r["edges"], ep.N)
    k, frac_N = pred_targeted(gi, ep.N)
    ch, g0 = comp_curve(gi, ep.N, lv_h, "hubs")
    cr, _ = comp_curve(gi, ep.N, lv_r, "rand", seed=sd)
    rows.append(dict(comp=gi["comp"], R=gi["R"], prevalence=gi["comp"] / ep.N,
                     theory_perN=frac_N, theory_perComp=k / gi["comp"],
                     hub_half=contour(lv_h.tolist(), ch.tolist(), 0.5, increasing=False),
                     hub_dead=contour(lv_h.tolist(), ch.tolist(), 0.02, increasing=False),
                     rand_half=contour(lv_r.tolist(), cr.tolist(), 0.5, increasing=False),
                     rand_dead=contour(lv_r.tolist(), cr.tolist(), 0.02, increasing=False),
                     curve_h=ch.tolist()))


def med(k):
    v = [r[k] for r in rows if r[k] is not None]
    return float(np.median(v)) if v else None


RES["replica_structure"] = {k: med(k) for k in
                            ("comp", "R", "prevalence", "theory_perN", "theory_perComp",
                             "hub_half", "hub_dead", "rand_half", "rand_dead")}
RES["replica_hub_curve"] = dict(levels=lv_h.tolist(),
                                mean=np.mean([r["curve_h"] for r in rows], axis=0).tolist())
print("   ", {k: (round(v, 3) if v else v) for k, v in RES["replica_structure"].items()})

# ---------- 2. replica detection, expressed per component ----------
print("2. replica detection vs hub blinding, per component")
grid_N = [0, .002, .004, .006, .01, .015, .02, .03, .05, .08, .12, .2]
eps = [make_episode(500, sd, "swarm") for sd in TEST]
res0 = [audit(ep, s_stars=[S_STAR], collect=True) for ep in eps]
gis = [graph_info(r["edges"], ep.N) for ep, r in zip(eps, res0)]
orders = [np.argsort(-g["deg"], kind="stable") for g in gis]
prev = np.median([g["comp"] / 500 for g in gis])
prob = []
for lv in grid_N:
    ind = []
    for i, (ep, sd) in enumerate(zip(eps, TEST)):
        rng = np.random.default_rng(np.random.SeedSequence([sd, 5, int(round(lv * 10000))]))
        mask, run = make_view(ep, rng, "hubs", lv, order=orders[i])
        rr = audit(ep, mask=mask, run=run, s_stars=(S_STAR,))
        ind.append(1 if first_good_alert(rr["alerts"][S_STAR], ep.truth) else 0)
    prob.append(float(np.mean(ind)))
det_N = contour(grid_N, prob, 0.5, increasing=False)
RES["replica_detection"] = dict(grid_perN=grid_N, prob=prob, collapse_perN=det_N,
                                prevalence=float(prev),
                                collapse_perComp=float(det_N / prev) if det_N else None)
print("    detection collapse: %.3f of fleet = %.2f of swarm component"
      % (det_N, det_N / prev))

# ---------- 3. prevalence sweep: which number is invariant? ----------
print("3. prevalence sweep (calibration seeds)")
sweep = []
for mult in (1.0, 3.0, 10.0, 40.0, 150.0):
    rs = []
    for sd in CAL[:12]:
        ep = make_episode(500, sd, "swarm", ns_mult=min(0.00496 * mult, 1.0))
        r = audit(ep, s_stars=[S_STAR], collect=True)
        gi = graph_info(r["edges"], ep.N)
        if gi["comp"] < 20:
            continue
        k, fN = pred_targeted(gi, ep.N)
        rs.append((gi["comp"] / ep.N, fN, k / gi["comp"], gi["R"]))
    if not rs:
        continue
    A = np.array(rs)
    sweep.append(dict(ns_mult=0.00496 * mult, prevalence=float(np.median(A[:, 0])),
                      theory_perN=float(np.median(A[:, 1])),
                      theory_perComp=float(np.median(A[:, 2])),
                      R=float(np.median(A[:, 3]))))
    print("    prevalence %5.1f%%  per-fleet %.3f  per-component %.3f  R %.1f"
          % (100 * sweep[-1]["prevalence"], sweep[-1]["theory_perN"],
             sweep[-1]["theory_perComp"], sweep[-1]["R"]))
RES["prevalence_sweep"] = sweep
pn = [s["theory_perN"] for s in sweep]
pc = [s["theory_perComp"] for s in sweep]
RES["prevalence_spread"] = dict(perN_ratio=float(max(pn) / min(pn)),
                                perComp_ratio=float(max(pc) / min(pc)))
print("    spread across the sweep: per-fleet %.1fx, per-component %.1fx"
      % (RES["prevalence_spread"]["perN_ratio"], RES["prevalence_spread"]["perComp_ratio"]))

json.dump(RES, open(OUT, "w"), indent=1)
print("wrote", OUT)
