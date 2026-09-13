# Blink model ablation, session-grouped protocol

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
