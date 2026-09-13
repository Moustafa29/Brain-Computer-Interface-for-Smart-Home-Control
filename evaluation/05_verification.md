# Verification of the mind-state result

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
