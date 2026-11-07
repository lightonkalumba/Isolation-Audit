"""H3a graph-level theory check. Uses ONLY the calibration degree pool (no test seeds)."""
import json
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

TH = json.load(open("results/thresholds.json")); pool = np.array(TH["cal_deg_pool"])
R = float((pool * (pool - 1)).mean() / pool.mean()); pred = 1 / R
print("pooled R = %.2f, predicted bond threshold 1/R = %.4f" % (R, pred))
out = dict(R_pool=R, predicted=pred, rows={})
for n in (1000, 5000, 20000, 100000):
    rng = np.random.default_rng(np.random.SeedSequence([1000, 77, n]))
    peaks = []
    for rep in range(4):
        deg = rng.choice(pool, n); deg[0] += deg.sum() % 2
        stubs = np.repeat(np.arange(n), deg); rng.shuffle(stubs); a, b = stubs[0::2], stubs[1::2]
        best = (-1, None)
        for mult in np.linspace(0.4, 3.0, 27):
            rho = min(1.0, mult * pred); keep = rng.random(len(a)) < rho
            g = coo_matrix((np.ones(int(keep.sum())), (a[keep], b[keep])), shape=(n, n)); _, lab = connected_components(g, directed=False)
            sz = np.sort(np.bincount(lab))[::-1]; second = sz[1] if len(sz) > 1 else 0
            if second > best[0]: best = (second, rho)
        peaks.append(best[1])
    meas = float(np.mean(peaks)); out["rows"][str(n)] = dict(measured=meas, ratio=meas / pred)
    print(n, out["rows"][str(n)])
json.dump(out, open("results/graph_level.json", "w"), indent=1)
