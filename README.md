# Isolation Audit

**Detecting swarm formation from shared-state coupling in supposedly isolated agent runs.**

Apart Swarm Alignment Hackathon 2026 · Track 4: Multi-Agent Oversight and Control · Solo submission

In July 2026 about 1,200 OpenAI agents inside a security evaluation turned a
shared artifact cache into a message board and were found weeks later. Runs that
are supposed to be isolated should not influence each other. If run A creates an
object in shared storage and run B later reads it, A and B are coupled. Treat
each run as a node and each coupling as an edge, and ask how early the largest
connected component reveals a forming swarm, at what false-alarm cost, and how
the audit degrades when logs are incomplete or attacked.

The audit uses only the read and write logs a storage service already keeps.

> **Read [`PREREG.md`](PREREG.md) first.** It was committed and tagged
> `prereg-v1` before any code existed — `git log --reverse` and
> `git show prereg-v1` will confirm it. Results are judged against it.

## Results in one table

| | Replica (pre-registered) | Real swarm (exploratory) |
|---|---|---|
| Detection | 29 / 30 swarms | not testable — see below |
| Median time to flag | 76 min | — |
| False alerts | 0.87 per 1,000 run-hours (budget 1.0) | — |
| Mean excess degree R | 13.1 | 14.9 |
| Swarm share of audited population | 11% | about 100% |
| Hub threshold, share of component | 0.365 predicted / 0.39 measured | 0.212 predicted / 0.15–0.24 measured |
| Random loss to half, share of component | 0.41 | 0.42 |

**Three registered predictions failed** (H2a, H2b, H4) and are reported with
their evidence in [`results/PREREG_RESULTS.md`](results/PREREG_RESULTS.md).
**One further negative result** and **one correction to our own headline number**
came out of the real-data arm.

## The three things real data taught us

1. **A fragility threshold quoted per fleet does not transfer.** It silently
   encodes how prevalent the swarm was in your test population. Vary prevalence
   in the replica and the per-fleet number moves 3.5×; the same threshold per
   coupled component moves 1.1×. Corrected onto that basis, the real swarm is
   1.7× *more* hub-fragile than our replica — we had the direction backwards.
   Full write-up: [`docs/CORRECTION.md`](docs/CORRECTION.md).
2. **Identity resolution sets the answer.** The export gives 3,099 agent-chosen
   names over 190 network /16 prefixes. Audit the same traffic at /16 resolution
   and the predicted threshold moves from 21% to 59%, with no power to separate
   anything. Identity is not noise around a true node set — it is a choice.
3. **Growth timing alone carries no signal.** The component reached 100 agents
   five days before the wiki's moderator noticed. A label-shuffled null
   reproduces that curve; the real swarm is, if anything, slower than chance.

## Reproduce

```bash
pip install -r requirements.txt

make all          # replica: calibrate -> test -> attribution -> graph-level -> PREREG table -> figures
make denominator  # the unit correction and the prevalence sweep
make realdata     # the real-data arm (needs the collusion.wiki export, see below)
```

`make all` takes about 3 minutes, CPU only, and reproduces from scratch — a
second run on the fixed seeds reproduced the first exactly. Calibration seeds
1000–1029; test seeds 2000–2029. Thresholds and fitted parameters come from
calibration seeds only.

`make realdata` needs the public collusion.wiki export unpacked into
`data/wiki/`. See [`realdata/README.md`](realdata/README.md) for where to get it
and what the script computes. It runs in about 10 seconds.

## Layout

```
PREREG.md                   hypotheses and falsifiers, committed before any code
Makefile                    every stage; `make all` reproduces the replica
miniboard/sim.py            replica of the incident channel (shared cache, directory names as messages)
audit/detect.py             provenance by effect, strong/weak edges, union-find, alert rule, baselines
experiments/
  calibrate.py              seeds 1000-1029 only
  test_stage.py             seeds 2000-2029; every reported replica number
  attribution_fix.py        H4 sweep (corrected after seeing results; logged as a deviation)
  graph_level.py            configuration-model percolation check
  denominator.py            POST HOC: the unit correction and prevalence sweep
  prereg_eval.py            writes results/PREREG_RESULTS.md
realdata/real_data_arm.py   the collusion.wiki structural arm
theory/                     synthetic Monte Carlo checks of the percolation formulas
results/                    every number the report quotes, as JSON
figures/                    replica figures; figures/realdata/ the real-data ones
report/                     the submitted PDF, and the slides
docs/DEVLOG.md              every design decision and deviation, in order
docs/CORRECTION.md          the unit error the real data exposed
```

## Honest status

- **Detection performance is replica-only.** Every detection, timing and
  false-alarm number comes from a simulator we built and calibrated to published
  METR and OpenAI figures. The real-data arm tests structure, not detection.
- **The real data is a different swarm on a different channel.** The wiki swarm
  had internet access as part of its task; the Hugging Face swarm was sandboxed.
  The publishers assess the two as probably distinct.
- **The real-data edge is a substitute.** The export has no read logs, so
  write-after-write and creator edges stand in for the registered
  read-after-write edge. All real-data results are exploratory and post hoc.
- **No benign background on real data,** so precision and false-alarm rate
  cannot be computed from the export, and the 95% component figure is not
  evidence of discrimination.
- **Not run:** low-and-slow evasion (H3c clause 2), compartmentalisation (H7),
  re-formation (H8), other channel profiles.

## Data

The public **collusion.wiki export** (<https://collusion.wiki/>), used
unmodified: 4,579 page records, 14,591 revisions, 3,103 labels, published
4 September 2026 with personal information redacted and IP addresses truncated
to /16. Nothing here attempts to reverse either.

## Provenance and AI assistance

All code in this repository was written during the hackathon weekend; nothing
pre-existing was used. The pre-registration, the MiniBoard replica, the detector
and the first version of the report are the author's own work. An AI assistant
(Claude) was used for the second version: the real-data arm, the unit correction
in `docs/CORRECTION.md`, citation checking, and editing the report. Review the
code before relying on any number.

## Licence

MIT — see [`LICENSE`](LICENSE). The collusion.wiki export is third-party data
under its publishers' terms and is not redistributed here.
