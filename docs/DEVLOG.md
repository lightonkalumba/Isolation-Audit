# DEVLOG (append-only). Design decisions made on CALIBRATION seeds (1000-1029) only.

1. Committed PREREG v1 (tag prereg-v1) before any code existed. Counting rules (section 2b) were added in that same first commit.
2. Discovery hazard fitted analytically (no seeds) to METR 53 agents @3h and 76 @6h (N=1000) and OpenAI's 93% stuck-share:
   hazard0=0.2524/h, sigma=2.037, ns_mult=0.00496. Check on calibration seeds 1000-1004: members 52 @3h, 76 @6h.
3. Swarm graph density tuned on calibration seeds 1000-1004 only. Final: read_rate=0.5, k_rand=1, p_extra=0.1, p_directed=0.3,
   coord_boost=2.5, assign_targets=2, pop_coord=1.5. Resulting graph: mean degree ~10, R ~ 22, top hub touches ~46% of the component.
   NOTE: METR's '9 of 30 sampled agents downstream of the top coordinator' is a 2-hop quantity, not direct degree, so the hub reach is not
   directly calibrated. We therefore run a sensitivity variant with a flat hub structure (no coordinators) and report both.
4. Baseline B1/B3 details: B3 = zz-named object creators; B1 = runs creating objects outside their private scratch and the allow-list.
   Both alert once per k newly flagged runs (re-arming), k calibrated to the same budget.
5. Event-loss experiments: 'reads' mode drops read events only (matches the theory's independent-edge assumption); 'all' mode drops every
   raw event (more realistic, creation events are single points of failure). 'reads' is compared with theory; 'all' is reported as-is.
