# Real-data arm (H6)

Runs the audit's structural claims against the logs of a real agent swarm.
Reproduces every number in Sections 4.2–4.4 of the report.

## Get the data

The public **collusion.wiki export** — <https://collusion.wiki/> — published by
the investigation into agents that used a set of public wikis as a message board
between 24 May and 2 July 2026. Download `full-wiki-logs.zip` and unpack it:

```bash
unzip full-wiki-logs.zip -d data/wiki/
```

It holds `pages.jsonl`, `revisions.jsonl`, `events.jsonl`, `labels.jsonl`, a
manifest with source hashes and self-checks, and `SHA256SUMS`. It is used
**unmodified**; only `revisions.jsonl` and `labels.jsonl` are read.

The publishers released it with personal information redacted and IP addresses
truncated to a /16 prefix. Nothing here attempts to reverse either, and the
identity analysis is reported in aggregate for that reason.

## Run

```bash
pip install numpy pandas scipy matplotlib
python realdata/real_data_arm.py data/wiki/ results/realdata/
```

About 10 seconds, CPU only. Writes `results.json` and two figures.

## What it computes

| Output | Report section |
|---|---|
| Percolation on the agent-label graph: random loss, hub blinding, Molloy–Reed thresholds | 4.2 |
| Robustness: dropping the wiki's landing pages, restricting to labels with ≥2 edits | 4.2 |
| Creation-event loss on the creator edge | 4.2 |
| The same graph rebuilt at /16 network resolution | 4.3 |
| Component growth against a 40-shuffle label-permuted null | 4.4 |

## Expected output

```
loaded 13,661 agent revisions, 3,099 labels, 190 /16 prefixes
== primary (agent-chosen names): N=2,584 edges=6,345 giant=2,462 (95%) R=14.9
   random loss : theory 0.93 | half 0.4  | dead 0.88
   hub blinding: theory 0.202 | half 0.145 | dead 0.23
== network /16 prefix: N=186 edges=3,657 giant=186 (100%) R=67.0
   hub blinding: theory 0.591 | half 0.39 | dead 0.82
== identity: 3,099 labels / 190 prefixes = 16.3x; 43% of labels used once
== creation loss: component halves at 38% of creation records retained
== growth: size 256 real 23.5 days vs shuffled null 18.6 days
```

Seeds are fixed at the top of the file: `SEED_PERC = 11`, `SEED_NULL = 7`,
`SEED_CREATE = 3`.

## Read the headline number correctly

The 95% giant component is **not** evidence that the audit discriminates. The
export is filtered to traffic the publishers attribute to agents, so it carries
no benign background: precision and false-alarm rate cannot be computed from it.
This arm tests structure only.

The export also has no read logs, so the registered read-after-write edge cannot
be built. Two substitutes are used — a write-after-write edge (B edits a page A
edited) for the structural analyses, and a creator edge (page creator → every
later editor) for the creation-loss test. Every real-data result is therefore
**exploratory and post hoc**, and labelled as such in the report.

## Why this arm matters

It caught an error in our own replica results. See `docs/CORRECTION.md`.
