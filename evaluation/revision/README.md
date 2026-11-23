# Revision evaluation (IJIES paper 20266758)

Analyses added to answer the reviewers' comments. Every number below comes
from a script in `scripts/` and is stored in `results/`; rerunning any script
reproduces its results file byte for byte. All learned-model comparisons use
the same 5-fold cross-validation grouped by session as
`blink_control/session_cv.py` (`StratifiedGroupKFold`, `shuffle=True`,
`random_state=42`): 4,049 windows, 57 sessions, fold sizes 736 / 781 / 853 /
899 / 780.

Run from the repository root, for example:

```
python evaluation/revision/scripts/r2_4_baselines.py . evaluation/revision/results
python evaluation/revision/scripts/r2_7_stats.py evaluation/revision/results
```

## Classical baselines (R2-4) — `r2_4_baselines.py`

| detector | inputs | accuracy | macro F1 |
|---|---|---|---|
| threshold rule (60, 1 s pairing) | — | 93.0% ± 1.0 | 0.925 |
| random forest | 30 engineered features | 92.8% ± 1.3 | 0.922 |
| logistic regression | 30 engineered features | 91.5% ± 1.3 | 0.908 |
| RBF SVM | 30 engineered features | 89.6% ± 1.6 | 0.889 |
| CNN-BiLSTM (repository) | window + 30 features | 88.4% ± 1.7 | 0.864 |
| random forest | 16 band-power statistics only | 69.9% ± 3.0 | 0.559 |
| majority class | — | 47.5% ± 2.7 | 0.214 |

Because the labels are produced by the threshold rule, no learner can exceed
it on these labels; a random forest recovers it almost exactly. The band
powers alone carry blink information independent of the headset's
blink-strength channel (70% against 47.5%).

## Statistics (R2-7) — `r2_7_stats.py`

95% intervals by resampling sessions (cluster bootstrap, 5,000 draws):
rule 91.4–94.8%, random forest 91.0–94.6%. Paired against the rule:
random forest not different (McNemar p = 0.17); logistic regression and SVM
below it (p < 1e-7). CNN-BiLSTM below the rule in 5 of 5 folds (exact sign
test p = 0.06; fold level only).

## Same-person overlap (R1-7) — `r1_7_block_sensitivity.py`

Participant identity was not retained. Locking neighbouring sessions
together in groups of 2, 3 and 5 leaves every result unchanged (rule
92.9–93.0%, random forest 92.8–92.9%), so overlap between recordings made
close in time does not drive the results. The deployed detector has no
trained parameters and cannot benefit from overlap at all.

## Fuzzy gate (R1-6) — `r1_6_gate.py`

| | original gate | corrected gate |
|---|---|---|
| confidence at strength 60 | 0.56 | 0.60 |
| lowest strength passing the 0.60 gate | 63 | 60 |
| labelled events rejected at the default gate | 134 of 8,711 | 0 |
| places where confidence falls as strength rises | 6 | 0 |
| events rejected at gate 0.65 / 0.70 / 0.75 | 412 / 3,297 / 3,808 | 412 / 941 / 1,616 |

The original is `blink_control/fuzzy_logic_original.py`; the corrected gate
is `blink_control/fuzzy_logic.py`. Same rules, inference and defuzzification;
only the membership functions differ.

## Model inputs in the live controller — `model_input_mismatch.py`

The committed model run on all recorded windows:

| inputs | accuracy | blink windows called "no blink" |
|---|---|---|
| as in training (`time` = seconds since session start) | 91.4% | 0.2% |
| as the original `main.py` built them (`time` = Unix clock) | 31.7% | 100% |

(The model was trained on a random split of these windows, so the first row is
optimistic; the point is the contrast.) Fixed in `blink_control/main.py`.

## Already in `evaluation/` from September

Majority baselines, architecture ablation, leakage ablation, multi-task
ablation, robustness under noise and packet loss, and the leakage-free
session-grouped attention/relaxation evaluation. See `evaluation/REPORT.md`.
