"""R2-7: per-session distributions, cluster-bootstrap CIs, paired tests.

Uses window-level predictions saved by r2_4_baselines.py (identical folds).
  - per-session accuracy for each detector
  - 95% CI on accuracy by resampling sessions (cluster bootstrap, 5000 reps)
  - paired window-level McNemar test, rule vs each learned model
  - paired session-level Wilcoxon signed-rank test, rule vs each learned model
  - CNN-BiLSTM vs rule at fold level (committed per-fold values; exact sign test)

usage: python r2_7_stats.py <out_dir>
"""
import json, sys
from pathlib import Path
import numpy as np
from scipy.stats import binomtest, wilcoxon

OUT = Path(sys.argv[1])
d = np.load(OUT / "r2_4_window_predictions.npz")
base = json.loads((OUT / "r2_4_baselines.json").read_text())
y, g = d["y"], d["groups"]
names = {
    "rule": "rule_threshold_60_plus_1_s_interval",
    "random_forest (30 feat)": "random_forest__engineered_30",
    "logistic_regression (30 feat)": "logistic_regression__engineered_30",
    "svm (30 feat)": "svm_rbf__engineered_30",
    "random_forest (band power only)": "random_forest__band_power_16",
    "majority": "majority_class",
}
rng = np.random.default_rng(42)
sessions = np.unique(g)
idx_by_s = {s: np.where(g == s)[0] for s in sessions}


def per_session_acc(p):
    return np.array([np.mean(p[idx_by_s[s]] == y[idx_by_s[s]]) for s in sessions])


def cluster_ci(p, reps=5000):
    correct = (p == y).astype(float)
    sums = np.array([correct[idx_by_s[s]].sum() for s in sessions])
    ns = np.array([len(idx_by_s[s]) for s in sessions])
    stats = []
    for _ in range(reps):
        pick = rng.integers(0, len(sessions), len(sessions))
        stats.append(sums[pick].sum() / ns[pick].sum())
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


res = {"sessions": int(len(sessions)), "windows": int(len(y)), "detectors": {}, "paired_vs_rule": {}}
rule = d[names["rule"]]
rule_ps = per_session_acc(rule)
for label, key in names.items():
    p = d[key]
    ps = per_session_acc(p)
    lo, hi = cluster_ci(p)
    res["detectors"][label] = {
        "pooled_accuracy": float(np.mean(p == y)), "ci95_session_bootstrap": [lo, hi],
        "per_session_accuracy": {"min": float(ps.min()), "p25": float(np.percentile(ps, 25)),
                                 "median": float(np.median(ps)), "p75": float(np.percentile(ps, 75)),
                                 "max": float(ps.max())},
    }
    if label != "rule":
        a = (rule == y); b = (p == y)
        n01, n10 = int(np.sum(a & ~b)), int(np.sum(~a & b))   # rule right/model wrong, and reverse
        mcn = binomtest(min(n01, n10), n01 + n10, 0.5).pvalue if n01 + n10 else 1.0
        diff = rule_ps - ps
        w = wilcoxon(diff).pvalue if np.any(diff != 0) else 1.0
        res["paired_vs_rule"][label] = {
            "windows_rule_right_model_wrong": n01, "windows_model_right_rule_wrong": n10,
            "mcnemar_exact_p": float(mcn),
            "sessions_rule_better": int(np.sum(diff > 0)), "sessions_model_better": int(np.sum(diff < 0)),
            "sessions_tied": int(np.sum(diff == 0)), "wilcoxon_p_sessions": float(w),
        }

cnn = base["cnn_bilstm_committed"]["fold_accuracy"]
rulef = base["variants"]["rule (threshold 60 + 1 s interval)"]["fold_accuracy"]
wins = sum(r > c for r, c in zip(rulef, cnn))
res["cnn_bilstm_vs_rule_fold_level"] = {
    "rule_folds": rulef, "cnn_folds": cnn, "folds_rule_better": wins,
    "exact_sign_test_two_sided_p": float(binomtest(wins, 5, 0.5).pvalue),
    "note": "window-level CNN predictions were not committed; fold-level only until the CNN is re-run",
}
(OUT / "r2_7_stats.json").write_text(json.dumps(res, indent=2))

print(f"{'detector':34s} {'pooled':>7s} {'95% CI (sessions)':>19s} {'session median [IQR]':>24s}")
for k, v in res["detectors"].items():
    ps = v["per_session_accuracy"]; lo, hi = v["ci95_session_bootstrap"]
    print(f"{k:34s} {100*v['pooled_accuracy']:6.1f}%  [{100*lo:5.1f}, {100*hi:5.1f}]   "
          f"{100*ps['median']:5.1f} [{100*ps['p25']:5.1f}-{100*ps['p75']:5.1f}]")
print("\npaired vs rule:")
for k, v in res["paired_vs_rule"].items():
    print(f"  {k:32s} rule-only-right {v['windows_rule_right_model_wrong']:4d} | model-only-right "
          f"{v['windows_model_right_rule_wrong']:4d} | McNemar p={v['mcnemar_exact_p']:.2g} | "
          f"sessions rule/model/tie {v['sessions_rule_better']}/{v['sessions_model_better']}/{v['sessions_tied']} "
          f"Wilcoxon p={v['wilcoxon_p_sessions']:.2g}")
c = res["cnn_bilstm_vs_rule_fold_level"]
print(f"\nCNN-BiLSTM vs rule: rule better in {c['folds_rule_better']}/5 folds, sign test p={c['exact_sign_test_two_sided_p']:.3f}")
