import json
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
R = json.load(open("results/results.json")); A = json.load(open("results/attribution_fix.json")); RAW = json.load(open("results/raw.json")); TH = json.load(open("results/thresholds.json"))
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
NAVY, TEAL, ORG, GREY = "#14233c", "#127a82", "#d9622b", "#777777"
S = R["T4_sweeps"]; P = R["T4_predictions"]
fig, ax = plt.subplots(1, 3, figsize=(11, 3.3))
def band(a, d, color, label, x=None):
    x = d["grid"] if x is None else x
    a.plot(x, d["prob"], "-o", color=color, ms=3, label=label); a.fill_between(x, d["lo"], d["hi"], color=color, alpha=0.18)
band(ax[0], S["runs"], TEAL, "audit (measured)"); ax[0].axvline(P["random_runs_median"], ls=":", color=GREY); ax[0].text(P["random_runs_median"] - 0.02, 0.05, "theory 1-1/R", rotation=90, ha="right", color=GREY, fontsize=8)
ax[0].set_xlabel("fraction of runs unobserved (random)"); ax[0].set_ylabel("detection probability")
band(ax[1], S["hubs"], ORG, "audit (measured)"); ax[1].axvline(P["targeted_median"], ls=":", color=GREY); ax[1].text(P["targeted_median"] + 0.003, 0.05, "theory", color=GREY, fontsize=8)
ax[1].set_xlabel("fraction of runs blinded (top-degree hubs)")
for m, c, l in (("reads", TEAL, "read events lost"), ("all", ORG, "all events lost")):
    ax[2].plot(S[m]["grid"], S[m]["prob"], "-o", color=c, ms=3, label=l); ax[2].fill_between(S[m]["grid"], S[m]["lo"], S[m]["hi"], color=c, alpha=0.15)
ax[2].axvline(P["reads_median"], ls=":", color=GREY); ax[2].set_xscale("log"); ax[2].invert_xaxis(); ax[2].set_xlabel("fraction of events retained"); ax[2].legend(frameon=False, fontsize=8, loc="lower left")
for a in ax: a.set_ylim(-0.03, 1.05)
ax[0].set_title("Random loss", fontsize=9); ax[1].set_title("Targeted loss", fontsize=9); ax[2].set_title("Event loss", fontsize=9)
plt.tight_layout(); plt.savefig("figures/fig_hero.png", dpi=200); plt.close()
fig, a = plt.subplots(figsize=(5.4, 3.2))
for i in range(3):
    t0 = RAW["Shist"]["t_first_write"][i]
    xs, ys = zip(*RAW["Shist"]["swarm"][i]); a.step((np.array(xs)) / 3600, ys, where="post", color=TEAL, alpha=0.8, label="swarm" if i == 0 else None)
    xs, ys = zip(*RAW["Shist"]["benign"][i]); a.step((np.array(xs)) / 3600, ys, where="post", color=GREY, alpha=0.8, label="benign" if i == 0 else None)
    if RAW["Shist"]["alert_t"][i]: a.plot(RAW["Shist"]["alert_t"][i] / 3600, TH["s_star"]["500"]["1.0"], "v", color=ORG, ms=6, label="alert" if i == 0 else None)
a.set_yscale("log"); a.set_xlabel("simulated hours"); a.set_ylabel("largest component (runs)"); a.legend(frameon=False); plt.tight_layout(); plt.savefig("figures/fig_growth.png", dpi=200); plt.close()
fig, ax = plt.subplots(1, 2, figsize=(8.2, 3.0))
B = R["T3_baselines"]; E = R["H5_E1"]; d = R["T2_detection"]["500"]["1.0"]
names = ["audit", "zz-regex\n(zz present)", "audit\n(no zz)", "zz-regex\n(no zz)", "op-anomaly", "naive graph\n(no provenance)"]
vals = [d["detected"], B["zz_regex"]["detected"], E["audit_detected_nozz"], 0.0, B["op_anomaly"]["detected"], B["B6_naive"]["detected"]]
ax[0].bar(range(6), vals, color=[TEAL, GREY, TEAL, GREY, GREY, GREY]); ax[0].set_xticks(range(6)); ax[0].set_xticklabels(names, fontsize=6.5); ax[0].set_ylabel("detection probability"); ax[0].set_ylim(0, 1.05)
tl = [d["t_flag_median_min"], B["zz_regex"]["t_flag_median_min"], E["audit_t_nozz"]]
ax[1].bar(range(3), tl, color=[TEAL, GREY, TEAL]); ax[1].set_xticks(range(3)); ax[1].set_xticklabels(["audit", "zz-regex\n(zz present)", "audit\n(no zz)"], fontsize=7); ax[1].set_ylabel("median minutes to flag")
for a in ax: a.spines["top"].set_visible(False)
plt.tight_layout(); plt.savefig("figures/fig_methods.png", dpi=200); plt.close()
fig, a = plt.subplots(figsize=(5.4, 3.0))
g = [float(k) for k in A["table"]]; xs = [1 - x for x in g]
a.plot(xs, [A["table"][str(k)]["fpr"] for k in g], "-o", color=ORG, ms=3, label="false alarms /1,000 run-h")
a2 = a.twinx(); a2.plot(xs, [A["table"][str(k)]["detect"] for k in g], "-s", color=TEAL, ms=3, label="detection"); a.set_xscale("symlog", linthresh=1e-3)
a.set_xlabel("misattributed share of events (1 - a)"); a.set_ylabel("false alarms /1,000 run-h", color=ORG); a2.set_ylabel("detection probability", color=TEAL); a.axhline(1.0, ls=":", color=GREY)
plt.tight_layout(); plt.savefig("figures/fig_attr.png", dpi=200); plt.close()
print("figures ok")
