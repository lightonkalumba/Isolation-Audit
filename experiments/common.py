"""Shared helpers: seeds, graph statistics, theory predictions, log thinning, calibration."""
import numpy as np
from scipy.optimize import brentq
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from audit.detect import audit, first_good_alert, flagged_runs, baseline_alert_times

CAL = list(range(1000, 1030))        # calibration seeds (PREREG section 3)
TEST = list(range(2000, 2030))       # test seeds
BUDGETS = [10.0, 1.0, 0.1, 0.01]
PRIMARY = 1.0


def run_hours(ep):
    return ep.N * ep.T / 3600.0


# ---------------- graph statistics and theory predictions ----------------
def graph_info(edges, N):
    a = np.array([k[0] for k in edges]); b = np.array([k[1] for k in edges]); m = np.array([v[0] for v in edges.values()])
    g = coo_matrix((np.ones(len(a)), (a, b)), shape=(N, N))
    n, lab = connected_components(g, directed=False)
    big = np.argmax(np.bincount(lab)); nodes = np.flatnonzero(lab == big)
    inb = np.zeros(N, bool); inb[nodes] = True
    keep = inb[a] & inb[b]
    a2, b2, m2 = a[keep], b[keep], m[keep]
    deg = np.bincount(np.concatenate([a2, b2]), minlength=N)
    d = deg[nodes].astype(float)
    R = float((d * (d - 1)).mean() / d.mean())
    return dict(a=a2, b=b2, m=m2, nodes=nodes, deg=deg, R=R, comp=int(len(nodes)),
                meandeg=float(d.mean()), maxdeg_frac=float(d.max() / len(nodes)))


def pred_random_nodes(R):
    return 1 - 1 / R if R > 1 else 0.0


def pred_events(m, R, q=1.0):
    f = lambda c: q * np.mean(1 - (1 - c) ** m) * R - 1
    if f(1.0) <= 0:
        return None
    return float(brentq(f, 1e-9, 1.0))


def pred_targeted(gi, N):
    """Delete top-degree runs one at a time, recomputing R = sum k(k-1)/sum k; collapse when R <= 1."""
    deg = gi["deg"].astype(float).copy(); nodes = gi["nodes"]
    adj = {int(v): [] for v in nodes}
    for x, y in zip(gi["a"].tolist(), gi["b"].tolist()):
        adj[x].append(y); adj[y].append(x)
    order = sorted(nodes.tolist(), key=lambda v: -deg[v])
    S1 = float(deg[nodes].sum()); S2 = float((deg[nodes] * (deg[nodes] - 1)).sum())
    removed = set(); k = 0
    for u in order:
        if S1 <= 0 or S2 / S1 <= 1.0:
            break
        du = deg[u]; S1 -= du; S2 -= du * (du - 1)
        removed.add(u); deg[u] = 0; k += 1
        for v in adj[u]:
            if v not in removed:
                dv = deg[v]; S1 -= 1; S2 -= 2 * (dv - 1); deg[v] = dv - 1
    return k, k / N


# ---------------- thinning ----------------
def hub_order(gi, N):
    """Runs ranked by full-log degree (highest first); runs outside the swarm component have degree from gi."""
    return np.argsort(-gi["deg"], kind="stable")


def make_view(ep, rng, mode, level, order=None, dedupe_mask=None):
    n = len(ep.t); mask = np.ones(n, bool) if dedupe_mask is None else dedupe_mask.copy(); run = None
    isrun = ep.run >= 0; safe = np.where(isrun, ep.run, 0)
    if mode == "runs":
        unobs = rng.random(ep.N) < level; mask &= ~(isrun & unobs[safe])
    elif mode == "reads":
        isread = isrun & ((ep.op == 0) | (ep.op == 1)); mask &= ~(isread & (rng.random(n) > level))
    elif mode == "all":
        mask &= ~(isrun & (rng.random(n) > level))
    elif mode == "hubs":
        k = int(round(level * ep.N)); bl = np.zeros(ep.N, bool); bl[order[:k]] = True
        mask &= ~(isrun & bl[safe])
    elif mode == "attrib":
        mis = isrun & (rng.random(n) > level)
        run = ep.run.copy(); run[mis] = rng.integers(0, ep.N, int(mis.sum()))
    return mask, run


# ---------------- calibration ----------------
def fpr_table(eps, s_list, **kw):
    tot = {s: 0 for s in s_list}; rh = 0.0
    for ep in eps:
        res = audit(ep, s_stars=s_list, **kw)
        for s in s_list:
            tot[s] += len(res["alerts"][s])
        rh += run_hours(ep)
    return {s: tot[s] / (rh / 1000.0) for s in s_list}


def pick_s(table, budget):
    ok = [s for s in sorted(table) if table[s] <= budget]
    return ok[0] if ok else None


def boot_ci(x, rng, B=10000):
    x = np.asarray(x, float)
    if len(x) == 0:
        return (float("nan"), float("nan"))
    bs = rng.choice(x, size=(B, len(x)), replace=True).mean(1)
    return float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def contour(grid, prob, level=0.5, increasing=True):
    """Interpolated crossing of prob over `level` along `grid` (grid sorted ascending)."""
    grid = np.asarray(grid, float); prob = np.asarray(prob, float)
    if increasing:      # detection rises with the grid value (coverage)
        for i in range(len(grid)):
            if prob[i] >= level:
                if i == 0: return float(grid[0])
                x0, x1, y0, y1 = grid[i - 1], grid[i], prob[i - 1], prob[i]
                return float(x0 + (level - y0) * (x1 - x0) / (y1 - y0)) if y1 > y0 else float(x1)
        return None
    else:               # detection falls with the grid value (loss)
        for i in range(len(grid)):
            if prob[i] < level:
                if i == 0: return float(grid[0])
                x0, x1, y0, y1 = grid[i - 1], grid[i], prob[i - 1], prob[i]
                return float(x0 + (y0 - level) * (x1 - x0) / (y0 - y1)) if y0 > y1 else float(x1)
        return None
