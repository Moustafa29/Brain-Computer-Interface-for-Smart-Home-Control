# Multi-task vs independent single-task models

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
