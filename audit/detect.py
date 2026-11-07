"""Isolation audit detector: provenance by effect, strong/weak coupling edges, streaming
union-find, per-component alert rule. Reads only the contract log; never truth, never names.
"""
import numpy as np

GET, LIST, PUT, MKCOL = 0, 1, 2, 3
ACT_UP = 1


def audit(ep, mask=None, run=None, s_stars=(6,), g_star=0.2, W=1800.0, provenance=True,
          use_weak=False, collect=False, use_allow=True):
    """Run the audit over an Episode (optionally a thinned view).

    s_stars: sizes to alert at (one independent alert stream per value, for calibration sweeps).
    provenance=False is the naive first-toucher ablation (B6): no provenance, no direction.
    Returns dict(alerts={s: [(t, size, members)]}, Shist=[(t, S)], edges={(a,b): [count, first_t]}, weak=int).
    """
    idx = np.arange(len(ep.t)) if mask is None else np.flatnonzero(mask)
    r_arr = ep.run if run is None else run
    T = ep.t[idx].tolist(); R = r_arr[idx].tolist(); OP = ep.op[idx].tolist()
    P = ep.path[idx].tolist(); AC = ep.actor[idx].tolist(); ST = ep.status[idx].tolist()
    allow = ep.path_allow.tolist() if use_allow else [False] * len(ep.paths)
    pdir = ep.path_dir.tolist()
    N = ep.N
    parent = list(range(N)); size = [1] * N
    hist = {}; al = {}
    s_list = sorted(set(int(s) for s in s_stars)); s_min = s_list[0]
    alerts = {s: [] for s in s_list}
    Shist = [(0.0, 1)]; smax = 1
    edges = {}; weak_edges = 0; edge_events = []
    kind = {}; lastw = {}; owner = {}
    dir_writers = {}; seen_weak = set()
    first_write = None

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def size_at(h, t0):
        for k in range(len(h) - 1, -1, -1):
            if h[k][0] <= t0:
                return h[k][1]
        return 1

    def union(a, b, t):
        nonlocal smax
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if size[ra] < size[rb]:
            ra, rb = rb, ra
        ha = hist.get(ra, [(-1.0, size[ra])])
        parent[rb] = ra
        size[ra] += size[rb]
        n = size[ra]
        h = ha + [(t, n)]
        hist[ra] = h[-40:]
        hist.pop(rb, None)
        sa = al.get(ra); sb = al.pop(rb, None)
        if sb:
            sa = (sa or set()) | sb
            al[ra] = sa
        if n > smax:
            smax = n; Shist.append((t, n))
        if n >= s_min:
            before = size_at(h, t - W)
            growth = (n - before) / max(before, 1)
            if growth >= g_star:
                done = al.setdefault(ra, set())
                for s in s_list:
                    if s <= n and s not in done:
                        done.add(s)
                        mem = [x for x in range(N) if find(x) == ra]
                        alerts[s].append((t, n, mem))

    for j, (t, r, op, p, ac, st) in enumerate(zip(T, R, OP, P, AC, ST)):
        if ac == ACT_UP:
            if provenance and p not in kind:
                kind[p] = 0                                  # cache fill = upstream-originated
            continue
        if r < 0 or allow[p]:
            continue
        if not provenance:                                   # naive first-toucher graph
            if op == LIST or st >= 400:
                continue
            w = owner.setdefault(p, r)
            if w != r:
                union(w, r, t)
                if collect:
                    e = edges.setdefault((min(w, r), max(w, r)), [0, t]); e[0] += 1
            continue
        if op in (PUT, MKCOL):
            if st in (200, 201):
                if p not in kind:
                    kind[p] = 1                              # agent-originated by effect (first creation by a run)
                    if first_write is None:
                        first_write = t
                if kind[p] == 1:
                    lastw[p] = r
                    d = pdir[p]
                    if d >= 0:
                        dir_writers.setdefault(d, set()).add(r)
        elif op == GET and st == 200:
            if kind.get(p) == 1:
                w = lastw[p]
                if w != r:
                    union(w, r, t)
                    if collect:
                        key = (min(w, r), max(w, r))
                        e = edges.setdefault(key, [0, t]); e[0] += 1
                        edge_events.append((int(idx[j]), key))
        elif op == LIST and use_weak:
            for w in dir_writers.get(p, ()):
                if w != r and (r, w) not in seen_weak:
                    seen_weak.add((r, w)); union(r, w, t); weak_edges += 1
    roots = {}
    for x in range(N):
        roots.setdefault(find(x), []).append(x)
    final = max(roots.values(), key=len)
    return dict(alerts=alerts, Shist=Shist, edges=edges, weak=weak_edges, first_write=first_write, smax=smax, final=final, edge_events=edge_events)


def time_to_reach(Shist, s, t0):
    for t, S in Shist:
        if S >= s:
            return t - t0
    return None


def score_alert(alert, truth):
    t, n, mem = alert
    M = set(truth["members"])
    inter = len(M.intersection(mem))
    return dict(t=t, size=n, precision=inter / max(len(mem), 1), recall=inter / max(len(M), 1), coupled=inter)


def first_good_alert(alerts, truth, min_precision=0.8):
    for a in alerts:
        sc = score_alert(a, truth)
        if sc["precision"] >= min_precision:
            return sc
    return None


# ---- simple baselines on the same logs ----
def flagged_runs(ep, mask, run, which):
    """B3 'zz': runs that created a zz-named object; B1 'op': runs that created objects outside
    their private scratch and outside the allow-list. Returns [(t, run)] first flag per run."""
    op = ep.op; ok = ((op == PUT) | (op == MKCOL)) & ((ep.status == 201) | (ep.status == 200)) & (ep.actor == 0) & (ep.run >= 0)
    if which == "zz":
        ok &= ep.path_zz[ep.path]
    else:
        ok &= ~ep.path_allow[ep.path] & (ep.path_private[ep.path] != ep.run)
    if mask is not None:
        ok &= mask
    r = (ep.run if run is None else run)
    seen = {}; out = []
    for t, x in zip(ep.t[ok].tolist(), r[ok].tolist()):
        if x not in seen:
            seen[x] = t; out.append((t, x))
    return out


def baseline_alert_times(flagged, k):
    """One alert each time k new runs have been flagged (re-arming); returns alert times."""
    return [flagged[j * k - 1][0] for j in range(1, len(flagged) // k + 1)]
