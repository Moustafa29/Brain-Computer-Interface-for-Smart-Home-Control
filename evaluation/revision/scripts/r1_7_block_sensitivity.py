"""R1-7 sensitivity: does possible same-person overlap between folds inflate results?

Participant identity was not retained; some volunteers recorded more than once.
If repeat recordings were made close together, their session ids are adjacent.
This regroups sessions into blocks of k consecutive ids (k = 1, 2, 3, 5) and
reruns grouped 5-fold CV with blocks as the grouping unit, so neighbouring
sessions can never be split between training and test. Stable accuracy across
k means overlap between adjacent recordings is not what drives the results.

Also scores the rule, which has no trained parameters (unaffected by design).

usage: python r1_7_block_sensitivity.py <repo_dir> <out_dir>
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score

REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(Path(__file__).resolve().parent))
import r2_4_baselines as B  # identical windowing, features and rule

df = pd.read_csv(REPO / "data" / "all_data_labeled_final6.csv")
win, y, feats, grp, last_row = B.make_windows(df)
rule = B.rule_labels(df)[last_row]

res = {}
for k in (1, 2, 3, 5):
    blocks = grp // k
    folds = list(StratifiedGroupKFold(5, shuffle=True, random_state=42).split(win, y, blocks))
    row = {"blocks": int(len(np.unique(blocks)))}
    for name, make in {
        "rule": None,
        "random_forest": lambda: RandomForestClassifier(300, min_samples_leaf=2, class_weight="balanced",
                                                        n_jobs=-1, random_state=42),
        "logistic_regression": lambda: make_pipeline(StandardScaler(),
                                                     LogisticRegression(max_iter=5000, class_weight="balanced")),
        "rf_band_power_only": lambda: RandomForestClassifier(300, min_samples_leaf=2, class_weight="balanced",
                                                             n_jobs=-1, random_state=42),
    }.items():
        acc, mf1 = [], []
        for tr, te in folds:
            assert not set(blocks[tr]) & set(blocks[te])
            if make is None:
                p = rule[te]
            else:
                X = feats[:, B.BAND_IDX] if name == "rf_band_power_only" else feats
                m = make(); m.fit(X[tr], y[tr]); p = m.predict(X[te])
            acc.append(accuracy_score(y[te], p)); mf1.append(f1_score(y[te], p, average="macro"))
        row[name] = {"accuracy_mean": float(np.mean(acc)), "accuracy_std": float(np.std(acc)),
                     "macro_f1_mean": float(np.mean(mf1))}
    res[f"block_size_{k}"] = row
    print(f"k={k} ({row['blocks']:2d} groups): " + "  ".join(
        f"{n} {100*row[n]['accuracy_mean']:5.1f}±{100*row[n]['accuracy_std']:.1f}"
        for n in ("rule", "random_forest", "logistic_regression", "rf_band_power_only")))

(OUT / "r1_7_block_sensitivity.json").write_text(json.dumps(res, indent=2))
