"""Attribution sweep (H4), corrected: e = all eligible reads per run; finer grid near a=1. Test seeds only, thresholds from calibration."""
import json
import numpy as np
from miniboard.sim import make_episode
from audit.detect import audit, first_good_alert
from experiments.common import TEST, PRIMARY, run_hours, make_view

TH = json.load(open("results/thresholds.json")); s1 = TH["s_star"]["500"][str(PRIMARY)]
ben = [make_episode(500, s, "benign") for s in TEST]; sw = [make_episode(500, s, "swarm") for s in TEST]
rh = sum(run_hours(e) for e in ben)

def eligible_reads(ep):
    created = np.zeros(len(ep.paths), bool); seen = np.zeros(len(ep.paths), bool)
    w = ((ep.op == 2) | (ep.op == 3)) & (ep.status == 201) & (ep.actor == 0)
    for p in ep.path[w]:
        created[p] = True
    ok = (ep.op == 0) & (ep.status == 200) & (ep.actor == 0) & created[ep.path] & ~ep.path_allow[ep.path]
    return ok.sum() / ep.N

e = float(np.mean([eligible_reads(ep) for ep in ben]))
d_b = float(np.mean([2 * len(audit(ep, s_stars=(3,), collect=True)["edges"]) / ep.N for ep in ben]))
grid = [1.0, .999, .995, .99, .985, .98, .975, .97, .96, .95, .9, .8]
tab = {}
for a in grid:
    al = 0; ind = []
    for ep, sd in zip(ben, TEST):
        rng = np.random.default_rng(np.random.SeedSequence([sd, 8, int(round(a * 10000))]))
        m, r = make_view(ep, rng, "attrib", a); al += len(audit(ep, mask=m, run=r, s_stars=(s1,))["alerts"][s1])
    for ep, sd in zip(sw, TEST):
        rng = np.random.default_rng(np.random.SeedSequence([sd, 9, int(round(a * 10000))]))
        m, r = make_view(ep, rng, "attrib", a); ind.append(1 if first_good_alert(audit(ep, mask=m, run=r, s_stars=(s1,))["alerts"][s1], ep.truth) else 0)
    tab[str(a)] = dict(fpr=al / (rh / 1000.0), detect=float(np.mean(ind)), one_minus_a_times_e=(1 - a) * e)
    print(a, tab[str(a)])
pred = (1 - d_b) / 2
onset = None
for a in grid:
    if tab[str(a)]["fpr"] > 3 * PRIMARY:
        x1 = tab[str(a)]["one_minus_a_times_e"]; prev = [g for g in grid if g > a][-1] if a != 1.0 else None
        if prev is not None:
            x0 = tab[str(prev)]["one_minus_a_times_e"]; y0 = tab[str(prev)]["fpr"]; y1 = tab[str(a)]["fpr"]
            onset = x0 + (3 * PRIMARY - y0) * (x1 - x0) / (y1 - y0)
        else:
            onset = x1
        break
out = dict(e_eligible_per_run=e, d_b=d_b, predicted_onset=pred, measured_onset=onset, table=tab,
           ratio=(onset / pred) if onset else None, predicted_a_star=1 - pred / e)
print(out["predicted_onset"], out["measured_onset"], out["ratio"], "e", e, "predicted a*", out["predicted_a_star"])
json.dump(out, open("results/attribution_fix.json", "w"), indent=1)
