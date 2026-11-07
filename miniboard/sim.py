"""MiniBoard: incident replica, Tier 0 channel profile = cache directory names.

Produces one episode = a time-ordered log of operations in the contract format
(episode_id, run_id, sandbox_id, t, op, path, actor, status) plus a truth record.
Everything is a pure function of (seed, kind, N, params): no unseeded randomness.
"""
import heapq
import json
import re
from dataclasses import dataclass, field

import numpy as np

GET, LIST, PUT, MKCOL = 0, 1, 2, 3
OPNAME = ["GET", "LIST", "PUT", "MKCOL"]
ACT_RUN, ACT_UP = 0, 1
UP = -1                       # run index used for the upstream actor (cache fills)
KIND_CODE = {"benign": 1, "swarm": 2}

DEFAULTS = dict(
    T=43200.0,                                   # 12 simulated hours
    # ---- benign background (every run) ----
    K_pkg=500, pkg_rate=6.0, pkg_zipf=1.0,       # package GETs per run-hour (upstream-originated objects)
    scratch_rate=3.0,                            # private scratch ops per run-hour (self coupling only)
    tmp_rate=0.10, tmp_pool=3000, tmp_zipf=0.7, tmp_mkcol_frac=0.3,   # accidental name collisions in /tmp
    collab_frac=0.05, collab_rate=4.0, collab_pool=60,                # sanctioned sharing under /shared/ (allow-list)
    # ---- swarm process ----
    p_stuck=0.22, ns_mult=0.00496,               # 22% of tasks never solved; fitted so 93% of board members come from them (OpenAI)
    hazard0=0.2524, hazard_sigma=2.037,          # discovery hazard per hour: fitted jointly to METR 53@3h, 76@6h (N=1000)
    t_first_mean=5400.0, probe_rate=1.0,
    post_rate=2.0, read_rate=0.5, act_sigma=0.8,
    coord_frac=0.03, coord_boost=2.5, assign_targets=2, pop_coord=1.5,
    p_directed=0.30, p_reply=0.5,
    p_bundle=0.05, bundle_min=8, bundle_max=24, p_bundle_read=0.5,
    k_rand=1, p_extra=0.10, window_L=150,
    zz=True,                                     # naming habit (E1 switches it off)
)


@dataclass
class Episode:
    N: int
    T: float
    t: np.ndarray
    run: np.ndarray
    op: np.ndarray
    path: np.ndarray
    actor: np.ndarray
    status: np.ndarray
    paths: list
    path_allow: np.ndarray
    path_dir: np.ndarray
    path_zz: np.ndarray
    path_private: np.ndarray
    truth: dict = field(default_factory=dict)
    episode_id: str = ""


def _zipf(K, s):
    w = 1.0 / np.arange(1, K + 1) ** s
    return w / w.sum()


def _background(rng, N, p):
    T = p["T"]; Th = T / 3600.0
    out = []
    n = rng.poisson(p["pkg_rate"] * Th, N)
    runs = np.repeat(np.arange(N), n); t = rng.uniform(0, T, len(runs))
    idx = rng.choice(p["K_pkg"], size=len(runs), p=_zipf(p["K_pkg"], p["pkg_zipf"]))
    out += [(a, b, GET, "/pkg/p%d" % c, ACT_RUN, 0) for a, b, c in zip(t.tolist(), runs.tolist(), idx.tolist())]
    n = rng.poisson(p["scratch_rate"] / 2 * Th, N)
    runs = np.repeat(np.arange(N), n); t = rng.uniform(0, T, len(runs))
    dt = rng.uniform(60, 3600, len(runs)); j = rng.integers(0, 10 ** 6, len(runs))
    for a, b, d, k in zip(t.tolist(), runs.tolist(), dt.tolist(), j.tolist()):
        path = "/scratch/r%d/f%d" % (b, k)
        out.append((a, b, PUT, path, ACT_RUN, 0))
        if a + d < T:
            out.append((a + d, b, GET, path, ACT_RUN, 0))
    n = rng.poisson(p["tmp_rate"] * Th, N)
    runs = np.repeat(np.arange(N), n); t = rng.uniform(0, T, len(runs))
    idx = rng.choice(p["tmp_pool"], size=len(runs), p=_zipf(p["tmp_pool"], p["tmp_zipf"]))
    u = rng.random(len(runs))
    for a, b, c, uu in zip(t.tolist(), runs.tolist(), idx.tolist(), u.tolist()):
        if uu < 0.5:
            op = GET
        elif uu < 0.5 + 0.5 * p["tmp_mkcol_frac"]:
            op = MKCOL
        else:
            op = PUT
        out.append((a, b, op, "/tmp/n%d" % c, ACT_RUN, 0))
    collab = np.flatnonzero(rng.random(N) < p["collab_frac"])
    for r in collab.tolist():
        k = rng.poisson(p["collab_rate"] * Th)
        for a in rng.uniform(0, T, k).tolist():
            op = PUT if rng.random() < 0.5 else GET
            out.append((a, r, op, "/shared/artifacts/a%d" % rng.integers(0, p["collab_pool"]), ACT_RUN, 0))
    return out


def _swarm(rng, N, p):
    """Cache-directory-names board. Returns (events, truth)."""
    T = p["T"]; Th = T / 3600.0
    n_stuck = int(round(p["p_stuck"] * N))
    stuck = np.zeros(N, bool); stuck[rng.choice(N, n_stuck, replace=False)] = True
    sig = p["hazard_sigma"]
    hz = p["hazard0"] * np.exp(sig * rng.standard_normal(N) - sig ** 2 / 2) * np.where(stuck, 1.0, p["ns_mult"]) / 3600.0
    orig = int(rng.choice(np.flatnonzero(stuck)))
    t_first = 900.0 + min(rng.exponential(p["t_first_mean"]), 0.4 * T)
    disc = t_first + rng.exponential(1.0 / np.maximum(hz, 1e-12))
    disc[orig] = t_first - 60.0
    members = sorted(int(i) for i in np.flatnonzero(disc < T))
    ev = []
    handle = {i: "%06x" % rng.integers(0, 16 ** 6) for i in members}
    zz = p["zz"]
    # originator's test entries (first agent-originated writes)
    n_test = int(rng.integers(1, 4))
    test_t = sorted((t_first - rng.uniform(200, 1500, n_test)).tolist())
    for k, tt in enumerate(test_t):
        ev.append((tt, orig, MKCOL, ("/cache/zzTEST_%s_%d" if zz else "/cache/%s%d") % (handle[orig], k), ACT_RUN, 0))
    t0 = test_t[0]
    # probing by stuck runs before they discover the board
    probe = []
    for i in np.flatnonzero(stuck).tolist():
        end = disc[i] if i in handle else T
        k = rng.poisson(p["probe_rate"] * (end - 0.0) / 3600.0)
        for a in rng.uniform(0, end, k).tolist():
            ev.append((a, i, LIST, "/cache", ACT_RUN, 0))
    # member activity multipliers, coordinators
    act = {i: float(np.exp(p["act_sigma"] * rng.standard_normal() - p["act_sigma"] ** 2 / 2)) for i in members}
    order = sorted(members, key=lambda i: disc[i])
    cand = [i for i in order[1:40]]
    n_coord = max(2, int(round(p["coord_frac"] * len(members))))
    coords = set(rng.choice(cand, size=min(n_coord, len(cand)), replace=False).tolist()) if cand else set()
    # event-driven board dynamics
    heap = []; seq = 0
    def push(t, kind, r):
        nonlocal seq
        seq += 1
        heapq.heappush(heap, (t, seq, kind, r))
    for i in members:
        start = max(disc[i], t_first)
        pr = p["post_rate"] * act[i] * (p["coord_boost"] if i in coords else 1.0) / 3600.0
        rr = p["read_rate"] * act[i] / 3600.0
        for a in start + np.cumsum(rng.exponential(1.0 / pr, int(pr * (T - start) * 1.5) + 3)):
            if a < T: push(float(a), "post", i)
        for a in start + 30 + np.cumsum(rng.exponential(1.0 / rr, int(rr * (T - start) * 1.5) + 3)):
            if a < T: push(float(a), "read", i)
    entries = []                      # dict per entry
    known = []                        # members already active (by discovery order)
    inbox = {i: [] for i in members}
    read_by = {i: set() for i in members}
    seqn = {i: 0 for i in members}
    activated = set()
    def new_name(i, kind):
        seqn[i] += 1
        return ("/cache/zz%s_%s_%d" % (kind, handle[i], seqn[i])) if zz else ("/cache/%s%03d" % (handle[i], seqn[i]))
    def do_post(t, i, kind=None, target=None):
        if kind is None:
            if i in coords:
                kind = "ASSIGN"
            else:
                u = rng.random()
                kind = "ASK" if u < 0.3 else ("INFO" if u < 0.7 else "IDEA")
        bundle = (kind not in ("ASSIGN", "ANSWER")) and rng.random() < p["p_bundle"]
        path = new_name(i, "FILE" if bundle else kind)
        ev.append((t, i, MKCOL, path, ACT_RUN, 0))
        chunks = []
        if bundle:
            for k in range(int(rng.integers(p["bundle_min"], p["bundle_max"] + 1))):
                cp = "%s/%04d" % (path, k)
                chunks.append(cp); ev.append((t + 0.3 * (k + 1), i, MKCOL, cp, ACT_RUN, 0))
        addr = []
        if target is not None:
            addr = [target]
        elif kind == "ASSIGN":
            pool = [x for x in known if x != i]
            if pool:
                addr = rng.choice(pool, size=min(len(pool), 2 + int(rng.poisson(p["assign_targets"]))), replace=False).tolist()
        elif rng.random() < p["p_directed"]:
            pool = [x for x in known if x != i]
            if pool: addr = [int(rng.choice(pool))]
        eid = len(entries)
        entries.append(dict(path=path, author=i, kind=kind, addr=addr, chunks=chunks,
                            w=p["pop_coord"] if i in coords else 1.0))
        for a in addr: inbox[a].append(eid)
    while heap:
        t, _, kind, i = heapq.heappop(heap)
        if i not in activated:
            activated.add(i); known.append(i)
        if kind == "post":
            do_post(t, i)
        elif kind == "read":
            ev.append((t, i, LIST, "/cache", ACT_RUN, 0))
            picks = [e for e in inbox[i] if e not in read_by[i] and rng.random() < 0.9]
            inbox[i] = []
            recent = [e for e in range(max(0, len(entries) - p["window_L"]), len(entries))
                      if entries[e]["author"] != i and e not in read_by[i] and e not in picks]
            nr = p["k_rand"] + (1 if rng.random() < p["p_extra"] else 0)
            if recent:
                w = np.array([entries[e]["w"] for e in recent], float)
                k = min(nr, len(recent))
                picks += [recent[j] for j in rng.choice(len(recent), size=k, replace=False, p=w / w.sum()).tolist()]
            tt = t
            for e in picks:
                tt += float(rng.uniform(0.5, 3.0))
                read_by[i].add(e); en = entries[e]
                ev.append((tt, i, GET, en["path"], ACT_RUN, 0))
                if en["chunks"] and rng.random() < p["p_bundle_read"]:
                    for cp in en["chunks"]:
                        tt += float(rng.uniform(0.2, 0.8)); ev.append((tt, i, GET, cp, ACT_RUN, 0))
                if en["kind"] in ("ASK", "ASSIGN") and (i in en["addr"] or rng.random() < 0.1) and rng.random() < p["p_reply"]:
                    # reply: an ANSWER entry addressed to the asker, posted shortly after
                    rt = tt + float(rng.uniform(30, 600))
                    if rt < T:
                        seq += 1
                        heapq.heappush(heap, (rt, seq, "ans:%d:%d" % (i, en["author"]), i))
        elif kind.startswith("ans:"):
            _, me, asker = kind.split(":")
            do_post(t, int(me), kind="ANSWER", target=int(asker))
    truth = dict(members=members, t_first_write=float(t0), t_first_msg=float(t_first), originator=orig,
                 coordinators=sorted(int(c) for c in coords), n_stuck=int(n_stuck), disc=[float(disc[i]) for i in members])
    return ev, truth


def _finalize(ev, N, T, truth, eid):
    ev.sort(key=lambda e: e[0])
    exists = set(); out = []
    for (t, r, op, path, actor, st) in ev:
        if t >= T:
            continue
        if op == GET:
            if path.startswith("/pkg/"):
                if path not in exists:
                    exists.add(path); out.append((t - 1e-3, UP, GET, path, ACT_UP, 200))
                out.append((t, r, GET, path, ACT_RUN, 200))
            else:
                out.append((t, r, GET, path, ACT_RUN, 200 if path in exists else 404))
        elif op == LIST:
            out.append((t, r, LIST, path, ACT_RUN, 200))
        else:
            if path in exists:
                out.append((t, r, op, path, ACT_RUN, 405 if op == MKCOL else 200))
            else:
                exists.add(path); out.append((t, r, op, path, ACT_RUN, 201))
    out.sort(key=lambda e: e[0])
    ids = {}; plist = []
    def pid(s):
        j = ids.get(s)
        if j is None:
            j = len(plist); ids[s] = j; plist.append(s)
        return j
    t_a = np.array([e[0] for e in out], float)
    run_a = np.array([e[1] for e in out], np.int32)
    op_a = np.array([e[2] for e in out], np.int8)
    path_a = np.array([pid(e[3]) for e in out], np.int32)
    act_a = np.array([e[4] for e in out], np.int8)
    st_a = np.array([e[5] for e in out], np.int16)
    base = len(plist)
    parent = np.full(base, -1, np.int32)
    for j in range(base):
        s = plist[j]
        par = s.rsplit("/", 1)[0] or "/"
        parent[j] = pid(par) if par != s else -1
    M = len(plist)
    parent = np.concatenate([parent, np.full(M - base, -1, np.int32)])
    allow = np.array([s.startswith("/shared/") for s in plist])
    zzf = np.array([bool(re.search(r"/zz", s.lower())) for s in plist])
    priv = np.full(M, -1, np.int32)
    for j, s in enumerate(plist):
        m = re.match(r"/scratch/r(\d+)/", s)
        if m: priv[j] = int(m.group(1))
    return Episode(N, T, t_a, run_a, op_a, path_a, act_a, st_a, plist, allow, parent, zzf, priv, truth, eid)


def make_episode(N, seed, kind="swarm", **over):
    p = dict(DEFAULTS); p.update(over)
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), KIND_CODE[kind], int(N)]))
    ev = _background(rng, N, p)
    truth = dict(members=[], t_first_write=None)
    if kind == "swarm":
        sev, truth = _swarm(rng, N, p)
        ev += sev
    truth["params"] = {k: v for k, v in p.items()}
    return _finalize(ev, N, p["T"], truth, "%s_N%d_s%d" % (kind, N, seed))


def write_jsonl(ep, path):
    with open(path, "w") as f:
        for t, r, op, pa, ac, st in zip(ep.t.tolist(), ep.run.tolist(), ep.op.tolist(), ep.path.tolist(), ep.actor.tolist(), ep.status.tolist()):
            f.write(json.dumps({"episode_id": ep.episode_id, "run_id": "upstream" if r < 0 else "r%d" % r,
                                "sandbox_id": "upstream" if r < 0 else "sb%d" % r, "t": round(t, 3), "op": OPNAME[op],
                                "path": ep.paths[pa], "actor": "upstream" if ac else "run", "status": st}) + "\n")
    with open(path.replace(".jsonl", ".truth.json"), "w") as f:
        json.dump(ep.truth, f)


def read_jsonl(path):
    """Rebuild an Episode from the contract JSONL only (no truth needed)."""
    rows = [json.loads(l) for l in open(path)]
    N = max(int(r["run_id"][1:]) for r in rows if r["run_id"] != "upstream") + 1
    T = max(r["t"] for r in rows) + 1
    opi = {n: i for i, n in enumerate(OPNAME)}
    ev = [(r["t"], -1 if r["run_id"] == "upstream" else int(r["run_id"][1:]), opi[r["op"]], r["path"],
           ACT_UP if r["actor"] == "upstream" else ACT_RUN, r["status"]) for r in rows]
    ids = {}; plist = []
    def pid(s):
        j = ids.get(s)
        if j is None: j = len(plist); ids[s] = j; plist.append(s)
        return j
    t_a = np.array([e[0] for e in ev]); run_a = np.array([e[1] for e in ev], np.int32)
    op_a = np.array([e[2] for e in ev], np.int8); path_a = np.array([pid(e[3]) for e in ev], np.int32)
    act_a = np.array([e[4] for e in ev], np.int8); st_a = np.array([e[5] for e in ev], np.int16)
    base = len(plist); parent = []
    for j in range(base):
        s = plist[j]; par = s.rsplit("/", 1)[0] or "/"
        parent.append(pid(par) if par != s else -1)
    M = len(plist); parent += [-1] * (M - base)
    allow = np.array([s.startswith("/shared/") for s in plist]); zzf = np.array([bool(re.search(r"/zz", s.lower())) for s in plist])
    priv = np.full(M, -1, np.int32)
    for j, s in enumerate(plist):
        m = re.match(r"/scratch/r(\d+)/", s)
        if m: priv[j] = int(m.group(1))
    return Episode(N, T, t_a, run_a, op_a, path_a, act_a, st_a, plist, allow, np.array(parent, np.int32), zzf, priv, {}, rows[0]["episode_id"])
