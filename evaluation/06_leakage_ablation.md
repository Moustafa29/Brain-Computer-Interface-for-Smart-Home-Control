# Phase 1 - harness validation and the leakage ablation

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
