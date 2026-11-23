# `ijies-revision` branch

Work for the resubmission of IJIES paper 20266758 (*MindAssist*), answering
the two reviewers' comments. `master` is unchanged; everything is here.

## What changed

| Where | Change | Reviewer comment |
|---|---|---|
| `blink_control/fuzzy_logic.py` | Corrected gate: confidence 0.60 at strength 60, never decreasing. The original is kept as `fuzzy_logic_original.py` | R1-6 |
| `blink_control/main.py` | Model inputs built as in training; single blink dispatched 1.0 s after it; real model predictions in the log. Decision logic unchanged | R1-5, R1-6 |
| `arduino/final_esp32.ino` | Prints `ACK:DOOR` / `ACK:WINDOW` when a servo moves | R1-5 |
| `evaluation/revision/` | Classical baselines, statistics, gate analysis, same-person overlap check, model input check. See its README | R1-6, R1-7, R2-4, R2-7 |
| `session/` | Kit for the single-operator headset session. See `session/PROTOCOL.md` | R1-2, R1-5, R1-6, R2-1, R2-3 |

## Findings the paper must reflect

1. **What drives the actuators.** Door and window are decided by the
   blink-strength threshold (60), the fuzzy gate and the 1 s pairing rule.
   The fan is driven by the fuzzy controller on the headset's eSense values.
   The CNN-BiLSTM models run alongside and are logged; neither drives an
   actuator.
2. **Rule against learned models.** Blink labels are produced by the
   threshold rule, so on these labels nothing can beat it: rule 93.0%,
   random forest 92.8%, CNN-BiLSTM 88.4% (session-grouped). Under noise and
   packet loss the rule also degrades less (`evaluation/04_robustness.md`).
3. **Model inputs in the original controller.** `time` was the Unix clock,
   not seconds since start; on recorded data this makes the model answer
   "no blink" on 100% of blinks (accuracy 91.4% → 31.7%). Fixed here.
4. **Single-blink latency.** A single blink cannot be dispatched before the
   1 s double-blink window closes. The original loop added up to another
   second; the fixed loop dispatches at 1.0 s. Doubles are dispatched about
   60 ms after the second blink (bench test, fake headset).
5. **Dataset structure.** `all_data_labeled_final6.csv` holds 58 session ids:
   36 recordings of 1-2 minutes (the attention/relaxation data,
   5,929 rows), one 4-second fragment (id 16) and 21 blink-only recordings
   of 5-12 minutes (ids 37-57, 7,300 rows). 5,929 + 7,300 = 13,229.
6. **Participants.** Identity was not retained and some volunteers recorded
   more than once. The deployed detector has no trained parameters; for the
   learned models, grouping neighbouring sessions changes nothing
   (`evaluation/revision`).

## Known issues not changed here

- `mind_state_control/main_att.py` builds its model features from every
  packet, inserting zeros on packets without band powers, and uses
  `np.std` (ddof 0) where training used pandas (ddof 1). Its model does not
  drive the fan, so the fan's behaviour is unaffected.
- The blink-strength history used for smoothing is not time-limited: a weak
  blink shortly after strong ones is averaged upward. This is the behaviour
  the data and the paper describe, so it is left as is.
- The model's `time` feature encodes position within a session (training
  sessions ran 0-729 s). In live runs much longer than that it leaves the
  training range.

## Still to come on this branch

- Results of the headset session (`session/sessions/`, `session/report_*/`)
- The revised manuscript and the point-by-point response letter
