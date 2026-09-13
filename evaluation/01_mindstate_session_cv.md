# Multi-task mind-state model, session-grouped protocol

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
