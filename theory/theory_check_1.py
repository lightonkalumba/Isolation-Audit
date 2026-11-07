# Isolation Audit v2: Monte Carlo sanity checks for the theory in Section 6 (part 1). Fixed seeds; run: python3 theory_check_1.py
# Synthetic graphs only: these check the formulas, they are not project results.
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.optimize import brentq

rng = np.random.default_rng(7)

def powerlaw_degrees(N, gamma, kmin, kmax):
    ks = np.arange(kmin, kmax + 1)
    p = ks.astype(float) ** (-gamma); p /= p.sum()
    d = rng.choice(ks, size=N, p=p)
    if d.sum() % 2: d[0] += 1
    return d

def config_model(deg):
    stubs = np.repeat(np.arange(len(deg)), deg)
    rng.shuffle(stubs)
    u, v = stubs[0::2], stubs[1::2]
    keep = u != v
    u, v = u[keep], v[keep]
    a, b = np.minimum(u, v), np.maximum(u, v)
    e = np.unique(np.stack([a, b], 1), axis=0)          # simple graph
    return e[:, 0], e[:, 1]

def comp_sizes(N, u, v):
    g = coo_matrix((np.ones(len(u)), (u, v)), shape=(N, N))
    n, lab = connected_components(g, directed=False)
    return np.sort(np.bincount(lab))[::-1]

def degs(N, u, v):
    return np.bincount(np.concatenate([u, v]), minlength=N)

def kappa_minus_1(d):
    d = d[d > 0].astype(float)
    return (d * (d - 1)).mean() / d.mean()

# ---------- build graphs ----------
N = 60000
dpl = powerlaw_degrees(N, 2.5, 1, 300)
u, v = config_model(dpl)
d = degs(N, u, v)
R_true = kappa_minus_1(d)
print(f"[graph] heavy-tail config model: N={N}, mean deg={d.mean():.2f}, max deg={d.max()}, R=kappa-1={R_true:.2f}")

# ER graph, same mean degree
p_er = d.mean() / N
m_er = rng.binomial(N * (N - 1) // 2, p_er)
ue = rng.integers(0, N, m_er); ve = rng.integers(0, N, m_er)
k = ue != ve; ue, ve = ue[k], ve[k]
d_er = degs(N, ue, ve); R_er = kappa_minus_1(d_er)
print(f"[graph] ER same mean degree: mean deg={d_er.mean():.2f}, R=kappa-1={R_er:.2f}")

def sweep(u, v, N, q, rho_grid, seeds=4, mult=None, c_mode=False):
    """site prob q, edge-retention prob (rho or via multiplicity). returns mean giant frac and 2nd-largest frac."""
    G, S2 = [], []
    for rho in rho_grid:
        g_, s_ = [], []
        for _ in range(seeds):
            occ = rng.random(N) < q
            if c_mode:   # rho is event retention c ; edge survives if any of its m events survive
                p_edge = 1 - (1 - rho) ** mult
            else:
                p_edge = rho
            keep = (rng.random(len(u)) < p_edge) & occ[u] & occ[v]
            sz = comp_sizes(N, u[keep], v[keep])
            g_.append(sz[0] / N); s_.append(sz[1] / N)
        G.append(np.mean(g_)); S2.append(np.mean(s_))
    return np.array(G), np.array(S2)

grid = np.geomspace(0.003, 1.0, 36)

# ---------- CHECK 1: site-bond product threshold ----------
print("\n[CHECK 1] observed giant component appears when q*rho*(kappa-1) > 1")
for name, (uu, vv, R) in {"heavy-tail": (u, v, R_true), "ER": (ue, ve, R_er)}.items():
    for q in (1.0, 0.5, 0.25):
        G, S2 = sweep(uu, vv, N, q, grid)
        rho_pred = 1.0 / (q * R)
        rho_emp = grid[np.argmax(S2)]               # peak of 2nd-largest comp = critical point
        print(f"  {name:10s} q={q:4.2f}: predicted rho*={rho_pred:6.3f}   measured (2nd-comp peak)={rho_emp:6.3f}")

# ---------- CHECK 2: multiplicity (redundant events) ----------
print("\n[CHECK 2] repeated events per edge make coverage tolerance better than the naive formula")
m = 1 + rng.poisson(2.0, len(u))                     # events per edge, mean 3
def mean_edge_keep(c): return np.mean(1 - (1 - c) ** m)
q = 1.0
c_pred_mult = brentq(lambda c: q * mean_edge_keep(c) * R_true - 1, 1e-6, 1)
c_pred_naive = 1.0 / (q * R_true)
G, S2 = sweep(u, v, N, q, grid, mult=m, c_mode=True)
c_emp = grid[np.argmax(S2)]
print(f"  mean events/edge={m.mean():.1f}; naive c*={c_pred_naive:.3f}; multiplicity-corrected c*={c_pred_mult:.3f}; measured={c_emp:.3f}")
m1 = np.ones(len(u), dtype=int)
def mean_edge_keep1(c): return c
print("  (low-and-slow: 1 event/edge) -> corrected threshold collapses to naive c* =", round(c_pred_naive, 3))

# ---------- CHECK 3: random vs hub-targeted loss ----------
print("\n[CHECK 3] random vs hub-targeted blinding (fraction of runs unobserved)")
def giant_after_removal(uu, vv, N, removed_mask):
    keep = ~removed_mask[uu] & ~removed_mask[vv]
    return comp_sizes(N, uu[keep], vv[keep])[0] / N

def kappa_after(uu, vv, N, removed_mask):
    keep = ~removed_mask[uu] & ~removed_mask[vv]
    dd = degs(N, uu[keep], vv[keep])
    alive = ~removed_mask
    dd = dd[alive & (dd > 0)].astype(float)
    return (dd * (dd - 1)).mean() / dd.mean() + 1 if len(dd) else 0.0   # kappa

def first_collapse(uu, vv, N, order, fgrid, thresh=0.01):
    for f in fgrid:
        rm = np.zeros(N, bool); rm[order[: int(f * N)]] = True
        if giant_after_removal(uu, vv, N, rm) < thresh: return f
    return None

fgrid = np.concatenate([np.linspace(0, 0.1, 51), np.linspace(0.11, 0.99, 89)])
for name, (uu, vv, R) in {"heavy-tail": (u, v, R_true), "ER": (ue, ve, R_er)}.items():
    dd = degs(N, uu, vv)
    order_deg = np.argsort(-dd)
    order_rand = rng.permutation(N)
    f_rand_pred = 1 - 1 / R
    f_rand_emp = first_collapse(uu, vv, N, order_rand, fgrid)
    f_tgt_emp = first_collapse(uu, vv, N, order_deg, fgrid)
    # predicted targeted collapse: first f where recomputed kappa <= 2 (Molloy-Reed)
    f_tgt_pred = None
    for f in fgrid:
        rm = np.zeros(N, bool); rm[order_deg[: int(f * N)]] = True
        if kappa_after(uu, vv, N, rm) <= 2.0: f_tgt_pred = f; break
    print(f"  {name:10s} random: predicted f_c={f_rand_pred:5.3f} measured={f_rand_emp}   |  hub-targeted: predicted f_c={f_tgt_pred} measured={f_tgt_emp}")

# ---------- CHECK 4: misattribution creates false giant components ----------
print("\n[CHECK 4] attribution errors add random edges; benign background goes critical when d_b + 2*(1-a)*e = 1")
Nb = 20000
d_b = 0.30
ub = rng.integers(0, Nb, rng.poisson(d_b * Nb / 2)); vb = rng.integers(0, Nb, len(ub))
kk = ub != vb; ub, vb = ub[kk], vb[kk]
print(f"  benign true-edge mean degree d_b={2*len(ub)/Nb:.2f}")
for x in (0.05, 0.15, 0.25, 0.30, 0.35, 0.40, 0.50, 0.80):   # x = (1-a)*e  (spurious events per run)
    ns = rng.poisson(x * Nb)
    us = rng.integers(0, Nb, ns); vs = rng.integers(0, Nb, ns)
    sz = comp_sizes(Nb, np.concatenate([ub, us]), np.concatenate([vb, vs]))
    pred = "subcritical" if (2*len(ub)/Nb + 2 * x) < 1 else "SUPERcritical"
    print(f"  (1-a)*e={x:4.2f}  largest benign component={sz[0]:6d} ({100*sz[0]/Nb:5.1f}% of runs)   theory: {pred}")

# ---------- CHECK 5: benign largest component grows ~ ln N ----------
print("\n[CHECK 5] subcritical benign coupling: largest component vs population size")
for dmean in (0.3, 0.6):
    print(f"  benign mean degree {dmean}")
    prev = None
    for Nn in (200, 500, 1000, 2000, 5000, 20000, 100000):
        vals = []
        for _ in range(30 if Nn <= 20000 else 8):
            mm = rng.poisson(dmean * Nn / 2)
            a = rng.integers(0, Nn, mm); b = rng.integers(0, Nn, mm); k = a != b
            vals.append(comp_sizes(Nn, a[k], b[k])[0])
        print(f"    N={Nn:6d}  mean largest component={np.mean(vals):6.1f}  (= {100*np.mean(vals)/Nn:5.2f}% of N)   ln N={np.log(Nn):5.2f}")

# ---------- CHECK 6: delay to alert vs observed branching ratio ----------
print("\n[CHECK 6] generations needed to reach s*=25 coupled runs vs observed branching ratio (Galton-Watson, Poisson offspring)")
def gens_to_reach(Rb, s_star=25, max_gen=400, trials=4000):
    out, surv = [], 0
    for _ in range(trials):
        pop, tot, gen = 1, 1, 0
        while pop > 0 and tot < s_star and gen < max_gen:
            pop = rng.poisson(Rb, pop).sum() if pop < 5000 else int(pop * Rb)
            tot += pop; gen += 1
        if tot >= s_star: out.append(gen)
    return (np.median(out) if out else float('nan')), len(out) / trials
for Rb in (1.02, 1.05, 1.1, 1.2, 1.5, 2.0, 3.0):
    med, ps = gens_to_reach(Rb)
    print(f"  R_obs={Rb:4.2f}: P(reach s*)={ps:5.2f}   median generations given success={med:6.1f}   (ln(s*)/ln R={np.log(25)/np.log(Rb):6.1f})")
