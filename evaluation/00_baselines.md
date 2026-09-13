# Majority-class baselines

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
