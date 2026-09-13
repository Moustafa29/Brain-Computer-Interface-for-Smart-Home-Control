# MindAssist evaluation

An independent evaluation of the repository, run against its own protocol. The
repository was cloned read-only; nothing was committed, staged or pushed, and
every output is in this directory.

## Headline

**The blink result is largely the model recovering its own label function, and
it recovers it worse than the rule that produced the labels.**

`blinkType` is decided by a threshold on `blinkStrength`, a column the model is
given as an input. Blink versus no blink agrees with `blinkStrength >= 60` on
100% of samples, so the only part of the label not fixed by that threshold is
single versus double. Under the repository's own session-grouped protocol:

| variant | accuracy | macro F1 |
| --- | --- | --- |
| threshold rule alone, no training | **93.0% ± 1.0** | **0.925** |
| full model (repo) | 88.4% ± 1.7 | 0.864 |
| EEG only, blink strength removed | 65.4% ± 3.5 | 0.496 |
| majority class | 47.5% ± 2.7 | 0.214 |

The rule that generated the labels beats the trained model by 4.6 points. Strip
`blinkStrength` and its derived features, leaving band powers and the eSense
columns, and accuracy falls from 88.4% to 65.4% - still above the 47.5%
majority baseline, so there is some EEG signal, but most of the headline number
came from the label function being handed to the model as a feature.

This answers the question directly: the 88.4% is not a genuine EEG finding. It
is a supervised model reproducing a deterministic threshold, and the honest
comparison point for it is 93.0%, not 47.5%.

**A 20-sample window is 19.6 seconds.** The headset emits roughly one sample
per second (mean interval 0.9805 s, 1.02 Hz), so every model here classifies a
blink from about twenty seconds of once-per-second summaries, never a waveform.

## Corrections to my own earlier results

Two conclusions I reported before Phase 0 were wrong, both from one bug: I
scored the threshold rule over an entire window, when a window's label comes
from its last sample only. That understated the rule badly.

| claim | as reported | corrected |
| --- | --- | --- |
| rule accuracy, held-out sessions | 46.9% | 92.1% |
| "the model beats the rule everywhere" | model +40 points | rule beats the model in every condition |

The robustness table has been regenerated with the corrected rule. Everything
else - the architecture ablation, the multi-task ablation, the mind-state
evaluation - is unaffected and reproduced bit-for-bit on rerun.

## What does hold up

- **The published numbers are reproducible.** The harness reproduced the
  committed per-fold values exactly (0.8628, 0.8835, 0.8933, 0.8699, 0.9115),
  and the mind-state notebook protocol returned 90.0% and 90.4% against 92% and
  90% reported. Nothing is overstated in the repository's own reporting.
- **`session_cv.py` already evaluates by held-out session**, which is the right
  protocol and not common in student EEG work. This evaluation is built on it.
- **The labeling rule and the live controller agree exactly** - threshold 60 and
  a 1-second double window in both - so the deployed system and the training
  labels define a blink the same way.
- **Multi-task sharing costs nothing**: one backbone matches two independent
  models at 1.97x fewer parameters.
- **The architecture ablation is internally consistent**: CNN 68.2%, CNN+BiLSTM
  78.1%, full 88.4%. Read alongside the leakage result, the dense branch's 10.3
  points are mostly the blink-strength statistics, which is where the label
  lives.

## Where the evidence is negative

- The mind-state heads score 52.6% and 69.1% on held-out sessions against
  baselines of 56.4% and 71.6% - at or below predicting the majority class.
  Section 6 isolates the cause: the notebook's pipeline reproduces at ~90%, so
  neither the model nor this harness is at fault. The notebook's random split
  puts windows overlapping by 90% on both sides and reuses the test set for
  early stopping.
- The fuzzy gate cannot reject a real event. Confidence at strength 60 is
  0.560, and 60 is the threshold for an event to exist, so any gate below that
  is inert and gates above it cost accuracy.

## Method

5-fold cross-validation grouped by recording session and stratified by class,
the early-stopping validation set held out by session from each fold's training
sessions, scalers fitted on training windows only. No session contributes
windows to both training and test.

**Session ids for the mind-state data.** `all_data_labeled_att_Rel.csv` has no
session column. Every one of its 5,929 rows also appears in
`all_data_labeled_final6.csv`, so ids were recovered by matching the full
feature tuple and repaired against the time resets that mark session
boundaries: 37 segments, mean majority purity 0.998, 6 rows corrected. The
mapping is in `mind_state_session_ids.csv`.

**Deviations from the repository's code**, stated in full:

- The repository's `session_cv.py` was not executed, because it writes its
  results file into the working tree and the clone had to stay clean. The
  harness reruns the same protocol and reproduces its committed values exactly.
- Mind-state rolling statistics, deltas and windows are computed within a
  session; the notebook computed them across the concatenated file. Windows in
  my harness also restart the stride inside each session, giving 2,629 windows
  where a global stride gives 2,621.
- Mind-state inputs are standardised per fold on training windows; the notebook
  did not scale.
- `recurrent_dropout=0.1` is dropped from the mind-state LSTMs for CPU speed.
  Section 6 measures the cost at roughly 3 points of attention accuracy.
- The CNN-only ablation replaces the BiLSTM with global average pooling.
- The EEG-only variant drops `blinkStrength` from the windowed columns and the
  11 engineered features derived from it, keeping the 16 band-power statistics.
  It retains `time`, which encodes position within a session.

**Flagged as not reproducing:** nothing. Every experiment reran with identical
values; the only corrections were to my own rule implementation, described
above.


---

## 0. Phase 0 - sampling rate, window counts, rule check, gate sweep


## 0.1 Sampling rate and window duration

| quantity | value |
| --- | --- |
| intervals measured (within sessions) | 13,171 |
| mean inter-sample interval | 0.9805 s |
| standard deviation | 0.7121 s |
| median interval | 0.9736 s |
| min / max interval | 0.0000 s / 3.02 s |
| coefficient of variation | 0.73 |
| effective rate from mean | 1.02 Hz |
| effective rate from median | 1.03 Hz |
| **duration of a 20-sample window (mean)** | **19.6 s** |
| duration of a 20-sample window (median) | 19.5 s |

Interval distribution:

| percentile | 1 | 5 | 25 | 50 | 75 | 95 | 99 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| seconds | 0.000 | 0.003 | 0.368 | 0.974 | 1.486 | 2.310 | 2.467 |

## 0.2 Window counts

| dataset | samples | window | step | windows within sessions | windows across the file |
| --- | --- | --- | --- | --- | --- |
| blink (`all_data_labeled_final6.csv`) | 13,229 | 20 | 3 | 4,049 | 4,404 |
| mind state (`all_data_labeled_att_Rel.csv`) | 5,929 | 20 | 2 | 2,621 | 2,955 |

Window starts are multiples of the step across the whole file, so a stride that
restarts inside each session gives slightly different totals: 4,067 for blink and
2,629 for mind state.
`Blink_model.ipynb` builds windows across the file but skips any window spanning
two sessions, giving 4,049. `att_rel_model.ipynb` builds windows across the file with
no session check at all, giving 2,955; 20% of that is 591 test windows.
Confining mind-state windows to sessions gives 2,621 instead.

## 0.3 Does the labeling rule reproduce `blinkType`?

**Blink versus no blink is decided entirely by the threshold: `blinkStrength >= 60` agrees with `blinkType > 0` on 100.00% of samples.**
The residual error below is entirely single-versus-double.

| rule variant | accuracy vs blinkType |
| --- | --- |
| v1 event sample only, second of a pair is double | 0.9345 |
| v2 both samples of a pair are doubles | 0.8205 |
| v3 label held until the next event | 0.6985 |

Best variant: **v1 event sample only, second of a pair is double**, at 93.5%.

| class | precision | recall | F1 | support |
| --- | --- | --- | --- | --- |
| no blink | 1.000 | 1.000 | 1.000 | 4518 |
| single | 1.000 | 0.856 | 0.923 | 6030 |
| double | 0.756 | 1.000 | 0.861 | 2681 |

Diagnostics:

| quantity | value |
| --- | --- |
| samples | 13,229 |
| samples with blinkStrength >= 60 | 8,711 |
| samples labelled single or double | 8,711 |
| no-blink runs / median length | 925 / 1 |
| single runs / median length | 2282 / 1 |
| double runs / median length | 2098 / 1 |

## 0.4 Fuzzy confidence curve and gate sweep

Confidence at blink strength 60, the detection threshold: **0.560**.

| blink strength | 0 | 40 | 55 | 57 | 58 | 60 | 65 | 70 | 100 | 170 | 255 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| confidence | 0.170 | 0.200 | 0.460 | 0.510 | 0.530 | 0.560 | 0.620 | 0.670 | 0.660 | 0.900 | 1.000 |

Gate applied to the rule detector from 0.3, scored against `blinkType` on all
13,229 samples. Rejected events are detections downgraded to no blink.

| gate | accuracy | precision: no blink | precision: single | precision: double | events rejected |
| --- | --- | --- | --- | --- | --- |
| no gate | 0.9345 | 1.000 | 1.000 | 0.756 | 0 |
| 0.50 | 0.9345 | 1.000 | 1.000 | 0.756 | 0 |
| 0.55 | 0.9345 | 1.000 | 1.000 | 0.756 | 0 |
| 0.60 | 0.9255 | 0.971 | 1.000 | 0.756 | 134 |
| 0.65 | 0.9063 | 0.916 | 1.000 | 0.754 | 412 |
| 0.70 | 0.7097 | 0.578 | 1.000 | 0.748 | 3297 |

---

## 1. Harness validation and the leakage ablation


## 1.1 Harness validation

| fold | committed | reproduced | match |
| --- | --- | --- | --- |
| 1 | 0.8628 | 0.8628 | yes |
| 2 | 0.8835 | 0.8835 | yes |
| 3 | 0.8933 | 0.8933 | yes |
| 4 | 0.8699 | 0.8699 | yes |
| 5 | 0.9115 | 0.9115 | yes |

The repository's `session_cv.py` was not executed: it writes its results file
into the working tree, which has to stay clean. The harness reruns the same
protocol on the same data instead.

## 1.2 Leakage ablation

| variant | parameters | accuracy | macro F1 |
| --- | --- | --- | --- |
| A. full model (repo) | 68,467 | 88.4% ± 1.7 | 0.864 ± 0.021 |
| B. EEG only, no blink strength | 67,923 | 65.4% ± 3.5 | 0.496 ± 0.025 |
| C. threshold rule alone | - | 93.0% ± 1.0 | 0.925 ± 0.011 |
| majority class | - | 47.5% ± 2.7 | 0.214 ± 0.008 |

Per fold accuracy:

| variant | fold 1 | fold 2 | fold 3 | fold 4 | fold 5 |
| --- | --- | --- | --- | --- | --- |
| A. full model (repo) | 0.863 | 0.883 | 0.893 | 0.870 | 0.912 |
| B. EEG only, no blink strength | 0.599 | 0.694 | 0.655 | 0.687 | 0.635 |
| C. threshold rule alone | 0.916 | 0.928 | 0.943 | 0.922 | 0.941 |
| majority class | 0.432 | 0.472 | 0.478 | 0.518 | 0.472 |

### A. full model (repo), pooled over folds

| class | precision | recall | F1 |
| --- | --- | --- | --- |
| no blink | 0.986 | 0.964 | 0.975 |
| single | 0.870 | 0.910 | 0.890 |
| double | 0.756 | 0.702 | 0.728 |

| true \ predicted | no blink | single | double |
| --- | --- | --- | --- |
| **no blink** | 1239 | 21 | 25 |
| **single** | 10 | 1755 | 164 |
| **double** | 8 | 241 | 586 |

### B. EEG only, no blink strength, pooled over folds

| class | precision | recall | F1 |
| --- | --- | --- | --- |
| no blink | 0.811 | 0.640 | 0.715 |
| single | 0.613 | 0.941 | 0.742 |
| double | 0.236 | 0.020 | 0.037 |

| true \ predicted | no blink | single | double |
| --- | --- | --- | --- |
| **no blink** | 822 | 419 | 44 |
| **single** | 102 | 1816 | 11 |
| **double** | 90 | 728 | 17 |

### C. threshold rule alone, pooled over folds

| class | precision | recall | F1 |
| --- | --- | --- | --- |
| no blink | 1.000 | 1.000 | 1.000 |
| single | 1.000 | 0.853 | 0.921 |
| double | 0.747 | 1.000 | 0.855 |

| true \ predicted | no blink | single | double |
| --- | --- | --- | --- |
| **no blink** | 1285 | 0 | 0 |
| **single** | 0 | 1646 | 283 |
| **double** | 0 | 0 | 835 |

---

## 2. Majority-class baselines


Predicting each fold's most common training class, scored on the same
session-grouped test folds. Any model has to beat these to be doing
anything at all.

| task | class predicted | accuracy | macro F1 |
| --- | --- | --- | --- |
| blink type | single | 47.5% ± 2.7 | 0.214 |
| attention level | Medium | 56.4% ± 5.8 | 0.240 |
| relaxation level | Medium | 71.6% ± 2.8 | 0.278 |

Per fold accuracy:

| task | fold 1 | fold 2 | fold 3 | fold 4 | fold 5 |
| --- | --- | --- | --- | --- | --- |
| blink type | 0.432 | 0.472 | 0.478 | 0.518 | 0.472 |
| attention level | 0.616 | 0.466 | 0.599 | 0.529 | 0.609 |
| relaxation level | 0.714 | 0.734 | 0.664 | 0.742 | 0.727 |

---

## 3. Architecture ablation


Same windows, focal loss, optimiser, callbacks and folds throughout;
only the architecture changes. (c) is the model in the repository.

## Summary

| variant | parameters | accuracy | macro F1 |
| --- | --- | --- | --- |
| (a) CNN only | 10,243 | 68.2% ± 4.7 | 0.533 ± 0.026 |
| (b) CNN + BiLSTM | 66,051 | 78.1% ± 1.4 | 0.596 ± 0.009 |
| (c) CNN + BiLSTM + dense branch | 68,467 | 88.4% ± 1.7 | 0.864 ± 0.021 |

## Per fold accuracy

| variant | fold 1 | fold 2 | fold 3 | fold 4 | fold 5 |
| --- | --- | --- | --- | --- | --- |
| (a) CNN only | 0.592 | 0.693 | 0.730 | 0.697 | 0.695 |
| (b) CNN + BiLSTM | 0.765 | 0.784 | 0.763 | 0.798 | 0.794 |
| (c) CNN + BiLSTM + dense branch | 0.863 | 0.883 | 0.893 | 0.870 | 0.912 |

## (a) CNN only, pooled over folds

| class | precision | recall | F1 |
| --- | --- | --- | --- |
| no blink | 0.866 | 0.707 | 0.779 |
| single | 0.635 | 0.945 | 0.760 |
| double | 0.290 | 0.046 | 0.079 |

| true \ predicted | no blink | single | double |
| --- | --- | --- | --- |
| **no blink** | 909 | 310 | 66 |
| **single** | 80 | 1822 | 27 |
| **double** | 61 | 736 | 38 |

## (b) CNN + BiLSTM, pooled over folds

| class | precision | recall | F1 |
| --- | --- | --- | --- |
| no blink | 0.985 | 0.967 | 0.976 |
| single | 0.690 | 0.995 | 0.815 |
| double | 0.000 | 0.000 | 0.000 |

| true \ predicted | no blink | single | double |
| --- | --- | --- | --- |
| **no blink** | 1243 | 41 | 1 |
| **single** | 7 | 1919 | 3 |
| **double** | 12 | 823 | 0 |

## (c) CNN + BiLSTM + dense branch, pooled over folds

| class | precision | recall | F1 |
| --- | --- | --- | --- |
| no blink | 0.986 | 0.964 | 0.975 |
| single | 0.870 | 0.910 | 0.890 |
| double | 0.756 | 0.702 | 0.728 |

| true \ predicted | no blink | single | double |
| --- | --- | --- | --- |
| **no blink** | 1239 | 21 | 25 |
| **single** | 10 | 1755 | 164 |
| **double** | 8 | 241 | 586 |

---

## 4. Shared backbone vs independent single-task models


Same session-grouped folds, same backbone and schedule. The independent arm
trains one model per task, so it pays for two backbones.

| setup | parameters | attention accuracy | relaxation accuracy |  |
| --- | --- | --- | --- | --- |
| one shared backbone, two heads | 291,078 | 52.6% ± 9.4 | 69.1% ± 8.9 | single model |
| two independent single-task models | 573,446 | 52.7% ± 10.1 | 68.7% ± 9.4 | two models |

Parameter cost of the independent arm: 1.97x the shared model.

## Per fold accuracy

| fold | shared attention | shared relaxation | independent attention | independent relaxation |
| --- | --- | --- | --- | --- |
| 1 | 0.652 | 0.685 | 0.670 | 0.563 |
| 2 | 0.373 | 0.583 | 0.425 | 0.631 |
| 3 | 0.555 | 0.848 | 0.582 | 0.846 |
| 4 | 0.568 | 0.638 | 0.557 | 0.685 |
| 5 | 0.481 | 0.704 | 0.401 | 0.708 |

---

## 5. Robustness under noise and packet loss


Held-out sessions from fold 1 of the session-grouped split: 9 sessions, 738 windows.
Corruption is applied to raw samples before windowing, so both decision paths
see the same degraded stream. Labels stay clean. Delta is the change in accuracy
against the clean condition, in points. The fuzzy column uses a gate of 0.60.

## Clean baseline

| path | accuracy | macro F1 |
| --- | --- | --- |
| rule | 0.921 | 0.914 |
| model | 0.867 | 0.847 |
| model + fuzzy | 0.867 | 0.847 |

## Additive Gaussian noise

| condition | rule acc | model acc | model+fuzzy acc | rule delta | model delta | model+fuzzy delta |
| --- | --- | --- | --- | --- | --- | --- |
| SNR 40 dB | 0.921 | 0.797 | 0.799 | +0.0 | -7.0 | -6.8 |
| SNR 20 dB | 0.900 | 0.805 | 0.806 | -2.2 | -6.2 | -6.1 |
| SNR 10 dB | 0.862 | 0.770 | 0.770 | -6.0 | -9.8 | -9.8 |
| SNR 5 dB | 0.809 | 0.657 | 0.659 | -11.2 | -21.0 | -20.9 |
| SNR 0 dB | 0.709 | 0.606 | 0.606 | -21.3 | -26.2 | -26.2 |

## Random packet drops

| condition | rule acc | model acc | model+fuzzy acc | rule delta | model delta | model+fuzzy delta |
| --- | --- | --- | --- | --- | --- | --- |
| 0% dropped | 0.921 | 0.867 | 0.867 | +0.0 | +0.0 | +0.0 |
| 5% dropped | 0.886 | 0.837 | 0.837 | -3.5 | -3.0 | -3.0 |
| 10% dropped | 0.856 | 0.798 | 0.798 | -6.5 | -6.9 | -6.9 |
| 20% dropped | 0.813 | 0.752 | 0.752 | -10.8 | -11.5 | -11.5 |
| 40% dropped | 0.675 | 0.611 | 0.614 | -24.7 | -25.6 | -25.3 |

## Macro F1, same conditions

| condition | rule | model | model+fuzzy |
| --- | --- | --- | --- |
| clean | 0.914 | 0.847 | 0.847 |
| SNR 40 dB | 0.914 | 0.784 | 0.786 |
| SNR 20 dB | 0.892 | 0.789 | 0.791 |
| SNR 10 dB | 0.854 | 0.742 | 0.742 |
| SNR 5 dB | 0.801 | 0.596 | 0.597 |
| SNR 0 dB | 0.703 | 0.496 | 0.496 |
| 0% dropped | 0.914 | 0.847 | 0.847 |
| 5% dropped | 0.876 | 0.816 | 0.816 |
| 10% dropped | 0.845 | 0.775 | 0.775 |
| 20% dropped | 0.800 | 0.729 | 0.729 |
| 40% dropped | 0.664 | 0.604 | 0.607 |

## Fuzzy gate sensitivity

Accuracy when the model decision is downgraded to no blink below each gate.
A gate of 0.50 only reaches windows whose peak strength is below about 57 -- ones
the rule already calls no blink. Because strength 60 scores 0.56, no gate below that
can reject a genuine event, which is why the columns barely move.

| gate | clean | SNR 10 dB | 20% dropped | windows rejected (clean) |
| --- | --- | --- | --- | --- |
| 0.50 | 0.867 | 0.770 | 0.752 | 63 |
| 0.60 | 0.867 | 0.770 | 0.752 | 76 |
| 0.65 | 0.867 | 0.770 | 0.752 | 80 |
| 0.70 | 0.860 | 0.776 | 0.747 | 130 |

---

## 6. Mind-state verification


Each row changes one thing. A is the notebook's own pipeline; B, C and D are
session-grouped and differ only in the two choices I made when porting.
B, C and D use the first 2 folds, so compare them with each other.

| configuration | attention | relaxation | what it isolates |
| --- | --- | --- | --- |
| A. notebook protocol (random split) | 90.0% | 90.4% | reproduces the reported result |
| B. session-grouped + recurrent_dropout | 54.7% | 65.5% | tests the dropped regulariser |
| C. session-grouped, no scaling | 47.2% | 68.9% | tests the added scaling |
| D. session-grouped, as reported | 51.3% | 63.4% | the configuration in section 1 |

Per fold, session-grouped rows:

| configuration | fold 1 attention | fold 2 attention | fold 1 relaxation | fold 2 relaxation |
| --- | --- | --- | --- | --- |
| B. + recurrent_dropout | 0.748 | 0.347 | 0.717 | 0.593 |
| C. no scaling | 0.616 | 0.328 | 0.717 | 0.662 |
| D. as reported | 0.652 | 0.373 | 0.685 | 0.583 |

---

## 7. Mind-state under the session-grouped protocol


Shared CNN-BiLSTM backbone with one softmax head per task, evaluated with the
same 5-fold session-grouped split used for the blink model. No session
contributes windows to both training and test.

2629 windows over 66 features from 36 sessions.

## Summary

| head | accuracy | macro F1 |
| --- | --- | --- |
| attention | 52.6% ± 9.4 | 0.449 ± 0.099 |
| relaxation | 69.1% ± 8.9 | 0.386 ± 0.066 |

## Per fold

| fold | test windows | attention acc | attention F1 | relaxation acc | relaxation F1 |
| --- | --- | --- | --- | --- | --- |
| 1 | 515 | 0.652 | 0.624 | 0.685 | 0.314 |
| 2 | 616 | 0.373 | 0.360 | 0.583 | 0.397 |
| 3 | 479 | 0.555 | 0.406 | 0.848 | 0.389 |
| 4 | 533 | 0.568 | 0.365 | 0.638 | 0.328 |
| 5 | 486 | 0.481 | 0.489 | 0.704 | 0.501 |

## Attention head, pooled over folds

| class | precision | recall | F1 |
| --- | --- | --- | --- |
| High | 0.535 | 0.368 | 0.436 |
| Low | 0.288 | 0.360 | 0.320 |
| Medium | 0.601 | 0.644 | 0.622 |

| true \ predicted | High | Low | Medium |
| --- | --- | --- | --- |
| **High** | 257 | 107 | 335 |
| **Low** | 3 | 166 | 292 |
| **Medium** | 220 | 303 | 946 |

## Relaxation head, pooled over folds

| class | precision | recall | F1 |
| --- | --- | --- | --- |
| High | 0.406 | 0.279 | 0.331 |
| Low | 0.154 | 0.036 | 0.059 |
| Medium | 0.740 | 0.880 | 0.804 |

| true \ predicted | High | Low | Medium |
| --- | --- | --- | --- |
| **High** | 130 | 2 | 334 |
| **Low** | 16 | 10 | 250 |
| **Medium** | 174 | 53 | 1660 |
