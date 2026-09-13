# Phase 0 - checks that need no TensorFlow

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

