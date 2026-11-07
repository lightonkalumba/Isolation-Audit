"""CALIBRATION stage: uses ONLY calibration seeds 1000-1029. Writes results/thresholds.json.
Sets s* per budget and population size, baseline k, and fits the timing formula (delta, tau, n0)."""
import json, sys, time
import numpy as np
from scipy.optimize import least_squares

from miniboard.sim import make_episode
from audit.detect import audit, time_to_reach, flagged_runs
from experiments.common import CAL, BUDGETS, run_hours, fpr_table, pick_s, graph_info

S_LIST = list(range(3, 61))
S_FIT = [5, 8, 12, 20, 30]


def g_of(s, R, n0):
    return np.log(1 + s * (R - 1) / n0) / np.log(R)


def main():
    t0 = time.time(); out = {"cal_seeds": [CAL[0], CAL[-1]], "s_star": {}, "fpr_table": {}}
    for N in (200, 500, 1000):
        ben = [make_episode(N, s, "benign") for s in CAL]
        tab = fpr_table(ben, S_LIST)
        out["fpr_table"][str(N)] = {str(s): v for s, v in tab.items()}
        out["s_star"][str(N)] = {str(b): pick_s(tab, b) for b in BUDGETS}
        print("N=%d s* by budget:" % N, out["s_star"][str(N)], "(%.0fs)" % (time.time() - t0)); sys.stdout.flush()
        if N == 500:
            naive_list = [5, 10, 20, 50, 100, 200, 300, 400, 450, 490, 500]
            tabn = fpr_table(ben, naive_list, provenance=False)
            out["naive_fpr_table"] = {str(s): v for s, v in tabn.items()}
            out["s_naive"] = {str(b): pick_s(tabn, b) for b in BUDGETS}
            print("naive (B6) s* by budget:", out["s_naive"], {s: round(v, 2) for s, v in tabn.items()})
            out["k"] = {}
            rh = sum(run_hours(ep) for ep in ben)
            for which in ("zz", "op"):
                counts = [len(flagged_runs(ep, None, None, which)) for ep in ben]
                tk = {k: sum(c // k for c in counts) / (rh / 1000) for k in range(1, 400)}
                out["k"][which] = {str(b): pick_s(tk, b) for b in BUDGETS}
                print("baseline", which, "k by budget:", out["k"][which], "mean flagged runs/episode", np.mean(counts))
    # timing-formula fit on swarm calibration episodes (N=500)
    sw = [make_episode(500, s, "swarm") for s in CAL]
    rows = []; pool = []
    for ep in sw:
        res = audit(ep, s_stars=(3,), collect=True); gi = graph_info(res["edges"], ep.N)
        t0w = ep.truth["t_first_write"]
        tt = [time_to_reach(res["Shist"], s, t0w) for s in S_FIT]
        rows.append((gi["R"], tt))
        pool += gi["deg"][gi["nodes"]].tolist()
    def resid(x):
        dl, tau, n0 = np.exp(x)
        r = []
        for R, tt in rows:
            for s, t in zip(S_FIT, tt):
                if t is not None and t > 0 and R > 1:
                    r.append(np.log(t) - np.log(dl + tau * g_of(s, R, n0)))
        return r
    best = None
    for x0 in ([np.log(600), np.log(900), np.log(2.0)], [np.log(1500), np.log(300), np.log(5.0)], [np.log(300), np.log(3000), np.log(1.0)]):
        r = least_squares(resid, x0, bounds=([np.log(1), np.log(1), np.log(0.2)], [np.log(1e5), np.log(1e5), np.log(60)]))
        if best is None or r.cost < best.cost: best = r
    dl, tau, n0 = np.exp(best.x)
    out["timing_fit"] = dict(delta=float(dl), tau=float(tau), n0=float(n0), cost=float(best.cost),
                             R_median=float(np.median([r for r, _ in rows])))
    out["cal_deg_pool"] = [int(x) for x in pool]
    out["cal_swarm_R"] = [float(r) for r, _ in rows]
    print("timing fit: delta=%.0fs tau=%.0fs n0=%.2f ; median R on calibration swarms %.1f" % (dl, tau, n0, np.median([r for r, _ in rows])))
    json.dump(out, open("results/thresholds.json", "w"))
    print("calibration done in %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
