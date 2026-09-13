# Evaluation

These files were produced by an independent harness that re-ran this
repository's own protocol. Nothing here was regenerated for this commit; the
files are as the harness wrote them.

`REPORT.md` assembles the rest. The per-experiment `.md` files hold the tables,
the matching `.json` files hold the raw numbers, and
`mind_state_session_ids.csv` holds the recovered session ids described below.

## Validation

The harness reproduced the per-fold values committed in
`blink_control/session_cv_results.json` exactly:

| fold | committed | reproduced |
| ---- | --------- | ---------- |
| 1 | 0.8628 | 0.8628 |
| 2 | 0.8835 | 0.8835 |
| 3 | 0.8933 | 0.8933 |
| 4 | 0.8699 | 0.8699 |
| 5 | 0.9115 | 0.9115 |

It also reproduced the mind-state notebook's protocol at 90.0% and 90.4%,
against the 92% and 90% reported. `session_cv.py` itself was not executed,
because it writes its results file into the working tree.

## Deviations from the notebooks

Documented in full in `REPORT.md`; in short:

- **Session-confined windowing.** Rolling statistics, deltas and windows for the
  mind-state model are computed within a session, so no feature or window
  reaches across a session boundary. The notebook computed them across the
  concatenated file.
- **Per-fold standardisation.** Mind-state inputs are standardised with a scaler
  fitted on each fold's training windows. The notebook did not scale.
- **`recurrent_dropout` dropped.** The mind-state LSTMs run without
  `recurrent_dropout=0.1`, which disables the fused kernel and was too slow for
  the number of CPU trainings involved. `05_verification.md` measures the cost
  at roughly 3 points of attention accuracy.

## Session ids for the mind-state data

`data/all_data_labeled_att_Rel.csv` has no session column. Every one of its
5,929 rows also appears in `data/all_data_labeled_final6.csv`, so ids were
recovered by matching the full feature tuple and repaired against the time
resets that mark session boundaries: 37 segments, mean majority purity 0.998,
6 rows corrected.
