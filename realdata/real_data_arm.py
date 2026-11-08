#!/usr/bin/env python3
"""
Isolation Audit - real-data arm (H6).

Reproduces every real-data number and figure in Sections 4.4-4.6 of the report
from the public collusion.wiki export.

Usage
-----
    unzip full-wiki-logs.zip -d data/
    python real_data_arm.py data/ out/

Inputs expected in <data>/: revisions.jsonl, labels.jsonl
Outputs written to <out>/: results.json, fig_real_coverage.png,
                           fig_real_identity_timing.png

Written during the Apart Swarm Alignment Hackathon, November 2026.
No pre-existing code was used. Runtime about 10 seconds, CPU only.
Dependencies: numpy, pandas, scipy, matplotlib.
"""
import json, sys, os
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

SEED_PERC, SEED_NULL, SEED_CREATE = 11, 7, 3
N_NULL_SHUFFLES = 40
T0 = pd.Timestamp('2026-05-24', tz='UTC')      # first successful write to DSEWiki
SIZES = (4, 8, 16, 32, 64, 128, 256, 500, 1000)

TEAL, AMBER, GRAY, INK = '#0f766e', '#b45309', '#6b7785', '#1f2937'


# --------------------------------------------------------------- loading
def load(data_dir):
    """Agent revisions only: drop unlabelled rows and publisher-flagged humans."""
    revs = [json.loads(l) for l in open(os.path.join(data_dir, 'revisions.jsonl'))]
    lab = pd.read_json(os.path.join(data_dir, 'labels.jsonl'), lines=True)
    human = set(lab[lab.is_human_handle].label)
    df = pd.DataFrame(
        [(r['page_key'], r['seq'], r['label'], r['ip16'], r['time']) for r in revs],
        columns=['page', 'seq', 'label', 'ip16', 'time'])
    df['t'] = pd.to_datetime(df.time, utc=True)
    n_total, n_unlabelled = len(df), int((df.label == '').sum())
    df = df[(df.label != '') & (~df.label.isin(human))].copy()
    meta = dict(revisions_total=n_total, revisions_used=len(df),
                unlabelled_dropped=n_unlabelled, labels=int(df.label.nunique()),
                ip16=int(df.ip16.nunique()), pages=int(df.page.nunique()),
                first=str(df.t.min())[:16], last=str(df.t.max())[:16])
    return df, meta


# --------------------------------------------------------------- graphs
def edge_list(df, node='label'):
    """Write-after-write edge: B edits a page that A previously edited.
    Substitute for the registered read-after-write edge (no read logs exist)."""
    x = df.sort_values(['page', 't', 'seq']).copy()
    x['prev'] = x.groupby('page')[node].shift(1)
    e = x[x.prev.notna() & (x.prev != x[node])][['prev', node, 't', 'page']]
    e.columns = ['a', 'b', 't', 'page']
    return e.sort_values('t')


def creator_edge_list(df):
    """Creator edge: page creator -> every later editor. Closer to the
    registered shape, so creation-record loss removes a page's whole star."""
    rows = []
    for page, g in df.groupby('page'):
        g = g.sort_values(['t', 'seq'])
        c = g.iloc[0].label
        for l in g.iloc[1:].label.unique():
            if l != c:
                rows.append((c, l, page))
    return pd.DataFrame(rows, columns=['a', 'b', 'page'])


def to_matrix(e):
    nodes = pd.Index(sorted(set(e.a) | set(e.b)))
    ix = {n: i for i, n in enumerate(nodes)}
    pairs = {(min(ix[a], ix[b]), max(ix[a], ix[b])) for a, b in zip(e.a, e.b)}
    return len(nodes), np.array(sorted(pairs))


def giant(N, P, keep):
    if len(P) == 0:
        return 0
    Q = P[keep[P[:, 0]] & keep[P[:, 1]]]
    if len(Q) == 0:
        return int(keep.sum() > 0)
    A = coo_matrix((np.ones(len(Q)), (Q[:, 0], Q[:, 1])), shape=(N, N))
    _, l = connected_components(A, directed=False)
    l = l[keep]
    return int(np.bincount(l).max()) if len(l) else 0


# --------------------------------------------------------------- percolation
def molloy_reed_hub_threshold(deg):
    """Smallest removed top-degree fraction m/N with (1-p)*<k(k-1)>/<k> <= 1,
    where p is the removed share of edge endpoints (Callaway et al.)."""
    order = np.argsort(-deg)
    ds, tot = deg[order], deg.sum()
    cs_d, cs_a = np.cumsum(ds), np.cumsum(ds * (ds - 1))
    N = len(deg)
    for m in range(N):
        p = cs_d[m - 1] / tot if m else 0.0
        A = (ds * (ds - 1)).sum() - (cs_a[m - 1] if m else 0)
        B = tot - (cs_d[m - 1] if m else 0)
        if B <= 0 or (1 - p) * A / B <= 1:
            return m / N
    return None


def percolation(N, P, name, fmax=0.31, verbose=True):
    deg = np.bincount(P.ravel(), minlength=N).astype(float)
    R = (deg * (deg - 1)).sum() / deg.sum()
    G0 = giant(N, P, np.ones(N, bool))
    order = np.argsort(-deg)
    rng = np.random.default_rng(SEED_PERC)

    qs = np.round(np.arange(0, 1.0, 0.02), 2)
    rnd = np.array([np.mean([giant(N, P, rng.random(N) >= q) / N for _ in range(20)])
                    for q in qs])
    fs = np.round(np.arange(0, fmax, 0.005), 3)
    tgt = []
    for f in fs:
        v = []
        for _ in range(5):
            jit = deg + rng.random(N) * 0.01          # break degree ties
            keep = np.ones(N, bool)
            keep[np.argsort(-jit)[:int(round(f * N))]] = False
            v.append(giant(N, P, keep) / N)
        tgt.append(np.mean(v))
    tgt = np.array(tgt)

    def first_below(grid, vals, thr):
        return float(grid[np.argmax(vals < thr)]) if (vals < thr).any() else None

    out = dict(N=int(N), edges=int(len(P)), mean_degree=float(deg.mean()),
               max_degree=int(deg.max()), giant_n=int(G0), giant_frac=float(G0 / N),
               R=float(R),
               top4pct_edge_share=float(deg[order[:max(1, int(round(.04 * N)))]].sum()
                                        / deg.sum()),
               random_theory=float(1 - 1 / R),
               random_half=first_below(qs, rnd, G0 / N / 2),
               random_dead=first_below(qs, rnd, 0.02),
               hub_theory=molloy_reed_hub_threshold(deg),
               hub_half=first_below(fs, tgt, G0 / N / 2),
               hub_dead=first_below(fs, tgt, 0.02))
    if verbose:
        print(f"\n== {name}: N={N:,} edges={len(P):,} giant={G0:,} ({G0/N:.0%}) R={R:.1f}")
        print(f"   random loss : theory {out['random_theory']:.2f} | "
              f"half {out['random_half']} | dead {out['random_dead']}")
        print(f"   hub blinding: theory {out['hub_theory']:.3f} | "
              f"half {out['hub_half']} | dead {out['hub_dead']}")
    return out, (qs, rnd, fs, tgt)


# --------------------------------------------------------------- growth
def growth(e, sizes=SIZES):
    """Streaming union-find; record when the largest component first reaches
    each size. Mirrors the detector's own incremental merge."""
    par, mem, cross, best = {}, {}, {}, 0

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for a, b, t in zip(e.a, e.b, e.t):
        for n in (a, b):
            if n not in par:
                par[n] = n
                mem[n] = 1
        ra, rb = find(a), find(b)
        if ra != rb:
            if mem[ra] < mem[rb]:
                ra, rb = rb, ra
            par[rb] = ra
            mem[ra] += mem[rb]
            del mem[rb]
        best = max(best, mem[ra])
        for s in sizes:
            if best >= s and s not in cross:
                cross[s] = t
    return cross, best


# --------------------------------------------------------------- figures
def make_figures(R, curves, creation, out_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 8, 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.edgecolor': '#9ca3af',
                         'xtick.color': GRAY, 'ytick.color': GRAY,
                         'axes.labelcolor': INK, 'axes.titlecolor': INK})
    (qs, rnd, fs, tgt) = curves['primary']
    (_, _, fs2, tgt2) = curves['ip16']
    keeps, curve = creation
    P, I = R['primary'], R['ip16']

    # Figure 2 in the report: coverage on the real graph
    fig, ax = plt.subplots(1, 3, figsize=(9.6, 2.9))
    ax[0].plot(qs, rnd, color=TEAL, lw=2)
    ax[0].axvline(P['random_theory'], color=TEAL, ls=':', lw=1)
    ax[0].text(P['random_theory'] - .025, .55, f"theory 1-1/R = {P['random_theory']:.2f}",
               rotation=90, fontsize=6.5, color=TEAL, ha='right', va='center')
    ax[0].set_title('Random loss of runs', fontsize=8.5, loc='left')
    ax[0].set_xlabel('fraction of runs unobserved')
    ax[0].set_ylabel('largest component (share of nodes)')
    ax[1].plot(fs, tgt, color=AMBER, lw=2)
    ax[1].axvline(P['hub_theory'], color=AMBER, ls=':', lw=1)
    ax[1].text(P['hub_theory'] - .008, .55, f"theory {P['hub_theory']:.2f}", rotation=90,
               fontsize=6.5, color=AMBER, ha='right', va='center')
    ax[1].axvline(0.043, color=GRAY, ls='--', lw=.9)
    ax[1].text(0.049, .30, 'replica collapse\n(4.3%)', fontsize=6.5, color=GRAY, va='center')
    ax[1].set_title('Highest-degree runs blinded first', fontsize=8.5, loc='left')
    ax[1].set_xlabel('fraction of top-degree runs blinded')
    ax[2].plot(keeps, curve, color=TEAL, lw=2)
    ax[2].axhline(P['giant_frac'] / 2, color=GRAY, ls=':', lw=.9)
    ax[2].text(0.52, P['giant_frac'] / 2 + .03, 'half of initial size', fontsize=6.5, color=GRAY)
    ax[2].set_title('Creation events lost', fontsize=8.5, loc='left')
    ax[2].set_xlabel('fraction of creation events retained')
    for a in ax:
        a.set_ylim(0, 1.0)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'fig_real_coverage.png'), dpi=200)
    plt.close()

    # Figure 3 in the report: identity resolution and the growth null
    fig, ax = plt.subplots(1, 2, figsize=(9.6, 3.1))
    ax[0].plot(fs, tgt / P['giant_frac'], color=TEAL, lw=2,
               label=f"agent-chosen names ({P['N']:,} nodes, R={P['R']:.0f})")
    ax[0].plot(fs2, tgt2 / I['giant_frac'], color=AMBER, lw=2,
               label=f"network /16 prefix ({I['N']} nodes, R={I['R']:.0f})")
    ax[0].axvline(P['hub_theory'], color=TEAL, ls=':', lw=1)
    ax[0].axvline(I['hub_theory'], color=AMBER, ls=':', lw=1)
    ax[0].axvline(0.043, color=GRAY, ls='--', lw=.9)
    ax[0].text(0.05, .42, 'replica\n(4.3%)', fontsize=6.5, color=GRAY)
    ax[0].text(P['hub_theory'] + .012, .88, f"theory {P['hub_theory']:.0%}",
               fontsize=6.5, color=TEAL)
    ax[0].text(I['hub_theory'] + .012, .88, f"theory {I['hub_theory']:.0%}",
               fontsize=6.5, color=AMBER)
    ax[0].set_xlim(0, 0.85)
    ax[0].set_ylim(0, 1.05)
    ax[0].set_xlabel('fraction of top-degree nodes blinded')
    ax[0].set_ylabel('largest component (share of initial)')
    ax[0].legend(fontsize=6.6, frameon=False, loc='upper right', bbox_to_anchor=(1.02, 0.72))
    ax[0].set_title('How fragile the audit looks depends on the identity layer',
                    fontsize=8.5, loc='left')

    sizes = [4, 8, 16, 32, 64, 128, 256, 500]
    real = [R['growth_real_days'][str(s)] for s in sizes]
    nul = R['growth_null_days']
    ax[1].fill_between(sizes, [nul[str(s)]['lo'] for s in sizes],
                       [nul[str(s)]['hi'] for s in sizes],
                       color=GRAY, alpha=.22, label='shuffled labels (95% band)')
    ax[1].plot(sizes, [nul[str(s)]['median'] for s in sizes], color=GRAY, lw=1.6, ls='--',
               label='shuffled labels (median)')
    ax[1].plot(sizes, real, color=TEAL, lw=2, marker='o', ms=3.5, label='real swarm')
    ax[1].set_xscale('log', base=2)
    ax[1].set_xticks(sizes)
    ax[1].set_xticklabels([str(s) for s in sizes], fontsize=7)
    ax[1].set_xlabel('component size reached')
    ax[1].set_ylabel('days after first coupling')
    ax[1].legend(fontsize=6.8, frameon=False, loc='upper left')
    ax[1].set_title('Growth timing carries no signal on its own', fontsize=8.5, loc='left')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'fig_real_identity_timing.png'), dpi=200)
    plt.close()


# --------------------------------------------------------------- main
def main(data_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    df, meta = load(data_dir)
    RES, curves = {'data': meta}, {}
    print(f"loaded {meta['revisions_used']:,} agent revisions, "
          f"{meta['labels']:,} labels, {meta['ip16']} /16 prefixes")

    # 4.4 primary graph
    E = edge_list(df)
    N, P = to_matrix(E)
    RES['primary'], curves['primary'] = percolation(N, P, 'primary (agent-chosen names)')

    # 4.5 identity: same traffic at network resolution
    Eip = edge_list(df, node='ip16')
    Nip, Pip = to_matrix(Eip)
    RES['ip16'], curves['ip16'] = percolation(Nip, Pip, 'network /16 prefix', fmax=0.86)
    multi = df.groupby('label').ip16.nunique()
    RES['identity'] = dict(
        labels=int(df.label.nunique()), ip16=int(df.ip16.nunique()),
        ratio=float(df.label.nunique() / df.ip16.nunique()),
        labels_used_once=float((df.label.value_counts() == 1).mean()),
        labels_on_multiple_ip16=float((multi > 1).mean()),
        mean_labels_per_ip16=float(df.groupby('ip16').label.nunique().mean()))
    print(f"\n== identity: {RES['identity']['labels']:,} labels / "
          f"{RES['identity']['ip16']} prefixes = {RES['identity']['ratio']:.1f}x; "
          f"{RES['identity']['labels_used_once']:.0%} of labels used once")

    # 4.4 robustness: drop the wiki's own landing pages (allow-list analogue)
    pc = E.page.value_counts()
    RES['top_pages'] = {str(k): int(v) for k, v in pc.head(5).items()}
    RES['drop_top_pages'] = {}
    for k in (1, 3, 10):
        Ek = E[~E.page.isin(set(pc.head(k).index))]
        Nk, Pk = to_matrix(Ek)
        RES['drop_top_pages'][str(k)] = dict(N=int(Nk), giant=giant(Nk, Pk, np.ones(Nk, bool)))
        print(f"   drop top {k:2d} pages -> N={Nk:,} giant={RES['drop_top_pages'][str(k)]['giant']:,}")
    cnt = df.label.value_counts()
    keep = set(cnt[cnt >= 2].index)
    E2 = E[E.a.isin(keep) & E.b.isin(keep)]
    N2, P2 = to_matrix(E2)
    RES['min2_edits'], _ = percolation(N2, P2, 'labels with >=2 edits')

    # 4.4 creation-event loss, on the creator edge
    Ecre = creator_edge_list(df)
    Nc, Pc = to_matrix(Ecre)
    Gc = giant(Nc, Pc, np.ones(Nc, bool))
    RES['creator_edges'] = dict(N=int(Nc), edges=int(len(Ecre)), giant=int(Gc),
                                giant_frac=float(Gc / Nc))
    pages = np.array(sorted(df.page.unique()))
    keeps = np.round(np.arange(0.02, 1.01, 0.04), 2)
    curve = []
    rng = np.random.default_rng(SEED_CREATE)
    for k in keeps:
        v = []
        for _ in range(10):
            kept = set(pages[rng.random(len(pages)) < k])
            e = Ecre[Ecre.page.isin(kept)]
            if len(e) == 0:
                v.append(0.0)
                continue
            n, p = to_matrix(e)
            v.append(giant(n, p, np.ones(n, bool)) / Nc)
        curve.append(float(np.mean(v)))
    curve = np.array(curve)
    idx = np.where(curve >= Gc / Nc / 2)[0]
    idx2 = np.where(curve >= 0.02)[0]
    RES['creation_loss'] = dict(keeps=[float(x) for x in keeps],
                                giant=[float(x) for x in curve],
                                half_at=float(keeps[idx[0]]) if len(idx) else None,
                                dead_below=float(keeps[idx2[0]]) if len(idx2) else None)
    print(f"\n== creation loss: component halves at "
          f"{RES['creation_loss']['half_at']:.0%} of creation records retained; "
          f"gone below {RES['creation_loss']['dead_below']:.0%}")

    # 4.6 growth timing vs a label-shuffled null
    cross, best = growth(E)
    RES['growth_real'] = {str(s): str(t)[:16] for s, t in cross.items()}
    RES['growth_real_days'] = {str(s): float((t - T0).total_seconds() / 86400)
                               for s, t in cross.items()}
    rng = np.random.default_rng(SEED_NULL)
    null = {s: [] for s in SIZES}
    for _ in range(N_NULL_SHUFFLES):
        x = df.copy()
        x['label'] = rng.permutation(x.label.values)   # keep page, time, volume fixed
        c, _ = growth(edge_list(x))
        for s in SIZES:
            if s in c:
                null[s].append((c[s] - T0).total_seconds() / 86400)
    RES['growth_null_days'] = {str(s): dict(median=float(np.median(v)),
                                            lo=float(np.percentile(v, 2.5)),
                                            hi=float(np.percentile(v, 97.5)), n=len(v))
                               for s, v in null.items() if v}
    print("\n== growth, days after first coupling (real vs shuffled median):")
    for s in (64, 128, 256, 500):
        if str(s) in RES['growth_real_days'] and str(s) in RES['growth_null_days']:
            print(f"   size {s:4d}: real {RES['growth_real_days'][str(s)]:5.1f}   "
                  f"null {RES['growth_null_days'][str(s)]['median']:5.1f}")

    make_figures(RES, curves, (keeps, curve), out_dir)
    with open(os.path.join(out_dir, 'results.json'), 'w') as f:
        json.dump(RES, f, indent=1)
    print(f"\nwrote {out_dir}/results.json and two figures")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data',
         sys.argv[2] if len(sys.argv) > 2 else 'out')
