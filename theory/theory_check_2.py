# Isolation Audit v2: Monte Carlo sanity checks for the theory in Section 6 (part 2). Fixed seeds; run: python3 theory_check_2.py
# Synthetic graphs only: these check the formulas, they are not project results.
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
rng = np.random.default_rng(11)

def powerlaw_degrees(N, gamma, kmin, kmax):
    ks = np.arange(kmin, kmax + 1); p = ks.astype(float) ** (-gamma); p /= p.sum()
    d = rng.choice(ks, size=N, p=p)
    if d.sum() % 2: d[0] += 1
    return d
def config_model(deg):
    stubs = np.repeat(np.arange(len(deg)), deg); rng.shuffle(stubs)
    u, v = stubs[0::2], stubs[1::2]; k = u != v; u, v = u[k], v[k]
    a, b = np.minimum(u, v), np.maximum(u, v)
    e = np.unique(np.stack([a, b], 1), axis=0); return e[:, 0], e[:, 1]
def comp_sizes(N, u, v):
    g = coo_matrix((np.ones(len(u)), (u, v)), shape=(N, N))
    n, lab = connected_components(g, directed=False); return np.sort(np.bincount(lab))[::-1]
def kappa_minus_1(u, v, N):
    d = np.bincount(np.concatenate([u, v]), minlength=N); d = d[d > 0].astype(float)
    return (d * (d - 1)).mean() / d.mean()

print("[CHECK 1b] does the measured threshold converge to the prediction as the population grows? (heavy tail, q=1, kmax=sqrt-ish cutoff)")
for N in (20000, 60000, 200000, 600000):
    kmax = int(min(300, np.sqrt(N * 1.8)))        # structural cutoff
    d = powerlaw_degrees(N, 2.5, 1, kmax); u, v = config_model(d)
    R = kappa_minus_1(u, v, N); pred = 1 / R
    grid = np.linspace(0.6 * pred, 2.0 * pred, 29)
    S2 = []
    for rho in grid:
        s = []
        for _ in range(3):
            keep = rng.random(len(u)) < rho
            sz = comp_sizes(N, u[keep], v[keep]); s.append(sz[1] / N)
        S2.append(np.mean(s))
    emp = grid[int(np.argmax(S2))]
    print(f"  N={N:7d} kmax={kmax:4d}  R={R:5.2f}  predicted rho*={pred:5.3f}  measured={emp:5.3f}  ratio={emp/pred:4.2f}")

print("\n[CHECK 6b] alert delay vs observed branching ratio, several simultaneous seeds n0 (Galton-Watson, Poisson offspring), s*=25")
def run(R, n0, s_star=25, max_gen=300, trials=3000):
    gens, fin = [], []
    for _ in range(trials):
        pop, tot, g = n0, n0, 0; hit = None
        while pop > 0 and g < max_gen:
            pop = rng.poisson(R * pop) if pop < 10**6 else int(R * pop)
            tot += pop; g += 1
            if hit is None and tot >= s_star: hit = g
            if tot > 10**5: break
        gens.append(hit); fin.append(tot)
    ok = [x for x in gens if x is not None]
    return len(ok) / trials, (np.median(ok) if ok else float('nan')), np.mean(fin)
for n0 in (1, 5):
    print(f"  n0={n0}")
    for R in (0.7, 0.85, 0.95, 1.0, 1.1, 1.3, 1.6, 2.0, 3.0):
        p, med, meanfinal = run(R, n0)
        if R < 1: extra = f"mean final cluster={meanfinal:5.1f} (theory n0/(1-R)={n0/(1-R):5.1f})"
        elif R == 1.0: extra = f"(theory: ~ s*/n0 = {25/n0:4.1f} generations)"
        else: extra = f"(mean-field generations ~ {np.log(1+25*(R-1)/n0)/np.log(R):4.1f})"
        print(f"    R_obs={R:4.2f}: P(alert)={p:4.2f}  median generations to alert={med:5.1f}   {extra}")
