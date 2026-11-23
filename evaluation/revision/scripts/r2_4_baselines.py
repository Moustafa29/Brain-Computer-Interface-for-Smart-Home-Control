"""R2-4: classical baselines on the identical session-grouped folds.

Rebuilds the windows, engineered features and folds exactly as
blink_control/session_cv.py does (StratifiedGroupKFold, 5 folds,
shuffle=True, random_state=42), then scores:

  - the deterministic labelling rule (per window, on its last sample)
  - majority class
  - logistic regression, RBF SVM, random forest on the 30 engineered features
  - the same three on the 16 band-power features only (no blink strength,
    no time) -- what the EEG itself carries
  - the same three on flattened windows + engineered features

Scalers are fitted on each fold's training windows only. Hyperparameters
are fixed in advance (no tuning on test folds).

usage: python r2_4_baselines.py <repo_dir> <out_dir>
"""
import json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

SEED, N_FOLDS, W, STEP = 42, 5, 20, 3
FEATURE_COLS = ["attention", "meditation", "delta", "theta", "lowAlpha", "highAlpha",
                "lowBeta", "highBeta", "lowGamma", "highGamma", "blinkStrength", "time"]
BANDS = ["delta", "theta", "lowAlpha", "highAlpha", "lowBeta", "highBeta", "lowGamma", "highGamma"]
BI, TI = FEATURE_COLS.index("blinkStrength"), FEATURE_COLS.index("time")

# engineered feature names, in session_cv.py order
FEAT_NAMES = (["bs_mean", "bs_std", "bs_min", "bs_max", "bs_last", "bs_ptp",
               "bs_diff_mean", "bs_diff_std", "bs_count_gt60", "bs_count_zero",
               "t_min", "t_max", "t_ptp"]
              + [f"{b}_{s}" for b in BANDS for s in ("mean", "std")]
              + ["last_blink_interval"])
assert len(FEAT_NAMES) == 30
BAND_IDX = [FEAT_NAMES.index(f"{b}_{s}") for b in BANDS for s in ("mean", "std")]


def last_blink_interval(window, threshold=60):
    times = window[:, TI]
    bt = times[window[:, BI] >= threshold]
    return bt[-1] - bt[-2] if len(bt) > 1 else 0.0


def make_windows(df):
    X, y, sid = df[FEATURE_COLS].values, df["blinkType"].values, df["session_id"].values
    win, lab, feats, grp, last_row = [], [], [], [], []
    for start in range(0, len(X) - W + 1, STEP):
        end = start + W
        if len(np.unique(sid[start:end])) != 1:
            continue
        w = X[start:end]
        bv = w[:, BI]
        row = [np.mean(bv), np.std(bv), np.min(bv), np.max(bv), bv[-1], np.ptp(bv),
               np.mean(np.diff(bv)), np.std(np.diff(bv)), np.sum(bv > 60), np.sum(bv == 0),
               np.min(w[:, TI]), np.max(w[:, TI]), np.ptp(w[:, TI])]
        for b in BANDS:
            i = FEATURE_COLS.index(b)
            row += [np.mean(w[:, i]), np.std(w[:, i])]
        row.append(last_blink_interval(w))
        win.append(w); lab.append(y[end - 1]); feats.append(row)
        grp.append(sid[start]); last_row.append(end - 1)
    return (np.array(win), np.array(lab), np.array(feats), np.array(grp), np.array(last_row))


def rule_labels(df, thr=60, interval=1.0):
    """Row-level rule: an event is strength >= thr; it is a double if the previous
    event in the same session was <= interval seconds earlier, else single.
    (v1 in evaluation/phase0 -- 93.45% row agreement with blinkType.)"""
    out = np.zeros(len(df), dtype=int)
    last_t, last_s = None, None
    for i, (s, t, sid) in enumerate(zip(df.blinkStrength.values, df.time.values, df.session_id.values)):
        if sid != last_s:
            last_t, last_s = None, sid
        if s >= thr:
            out[i] = 2 if (last_t is not None and 0 <= t - last_t <= interval) else 1
            last_t = t
    return out


def score(y, p):
    return {"accuracy": float(accuracy_score(y, p)), "macro_f1": float(f1_score(y, p, average="macro")),
            "per_class_f1": [float(v) for v in f1_score(y, p, average=None, labels=[0, 1, 2])]}


def models():
    return {
        "logistic_regression": lambda: make_pipeline(StandardScaler(), LogisticRegression(
            max_iter=5000, class_weight="balanced")),
        "svm_rbf": lambda: make_pipeline(StandardScaler(), SVC(
            kernel="rbf", C=1.0, gamma="scale", class_weight="balanced")),
        "random_forest": lambda: RandomForestClassifier(
            n_estimators=300, min_samples_leaf=2, class_weight="balanced", n_jobs=-1, random_state=SEED),
    }


def main():
    df = pd.read_csv(REPO / "data" / "all_data_labeled_final6.csv")
    win, y, feats, grp, last_row = make_windows(df)
    rule_row = rule_labels(df)
    rule_win = rule_row[last_row]
    flat = np.hstack([win.reshape(len(win), -1), feats])
    print(f"{len(y)} windows, {len(np.unique(grp))} sessions")

    inputs = {
        "engineered_30": feats,
        "band_power_16": feats[:, BAND_IDX],
        "flat_window_plus_engineered": flat,
    }
    outer = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    splits = list(outer.split(win, y, grp))

    results = {"protocol": "5-fold StratifiedGroupKFold by session_id, shuffle=True, random_state=42 "
                           "(identical to blink_control/session_cv.py)",
               "windows": int(len(y)), "sessions": int(len(np.unique(grp))),
               "fold_test_windows": [int(len(te)) for _, te in splits],
               "variants": {}}
    preds = {}

    def run(name, fn):
        folds, allp = [], np.empty_like(y)
        t0 = time.time()
        for k, (tr, te) in enumerate(splits, 1):
            assert not set(grp[tr]) & set(grp[te])
            p = fn(tr, te)
            allp[te] = p
            folds.append(score(y[te], p))
        acc = np.array([f["accuracy"] for f in folds]); mf = np.array([f["macro_f1"] for f in folds])
        results["variants"][name] = {
            "accuracy_mean": float(acc.mean()), "accuracy_std": float(acc.std()),
            "macro_f1_mean": float(mf.mean()), "macro_f1_std": float(mf.std()),
            "fold_accuracy": acc.round(4).tolist(), "fold_macro_f1": mf.round(4).tolist(),
            "pooled": score(y, allp), "confusion_pooled": confusion_matrix(y, allp, labels=[0, 1, 2]).tolist(),
        }
        preds[name] = allp
        print(f"{name:52s} acc {100*acc.mean():5.1f} ± {100*acc.std():3.1f}  "
              f"macroF1 {mf.mean():.3f}  ({time.time()-t0:.0f}s)")

    run("rule (threshold 60 + 1 s interval)", lambda tr, te: rule_win[te])

    def majority(tr, te):
        vals, counts = np.unique(y[tr], return_counts=True)
        return np.full(len(te), vals[np.argmax(counts)])
    run("majority class", majority)

    for in_name, X in inputs.items():
        for m_name, make in models().items():
            def fit_pred(tr, te, X=X, make=make):
                m = make(); m.fit(X[tr], y[tr]); return m.predict(X[te])
            run(f"{m_name} | {in_name}", fit_pred)

    # reference: the repository's CNN-BiLSTM, per-fold values committed in session_cv_results.json
    committed = json.loads((REPO / "blink_control" / "session_cv_results.json").read_text())
    results["cnn_bilstm_committed"] = {
        "accuracy_mean": committed["accuracy_mean"], "accuracy_std": committed["accuracy_std"],
        "macro_f1_mean": committed["macro_f1_mean"], "macro_f1_std": committed["macro_f1_std"],
        "fold_accuracy": [round(f["accuracy"], 4) for f in committed["folds"]],
        "fold_test_windows": [f["test_windows"] for f in committed["folds"]],
    }
    assert results["cnn_bilstm_committed"]["fold_test_windows"] == results["fold_test_windows"], \
        "fold sizes differ from session_cv.py -- folds are not identical"

    (OUT / "r2_4_baselines.json").write_text(json.dumps(results, indent=2))
    np.savez(OUT / "r2_4_window_predictions.npz", y=y, groups=grp,
             **{k.replace(" ", "_").replace("|", "").replace("(", "").replace(")", "").replace("+", "plus"): v
                for k, v in preds.items()})
    print("fold sizes match session_cv.py:", results["fold_test_windows"])


if __name__ == "__main__":
    main()
