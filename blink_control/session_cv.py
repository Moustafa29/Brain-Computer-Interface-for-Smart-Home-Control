"""Cross-session evaluation of the blink classifier.

    python blink_control/session_cv.py

Answers the question an EEG reviewer asks first: does the model work on
recording sessions it has never seen?

The windowing, engineered features, architecture, focal loss and training
settings are identical to Blink_model.ipynb. Only the evaluation changes:

  - 5-fold cross-validation grouped by session_id, stratified by blink type,
    so every window of a session lands in exactly one fold. No session
    contributes windows to both training and test.
  - The early-stopping validation set is also held out by session, drawn from
    the training sessions of each fold.
  - Scalers are fitted on the training windows of each fold only.

Windows overlap heavily (20 samples, step 3), so a random window-level split
places near-identical windows on both sides of the split. Grouping by session
removes that overlap between training and test.

Writes blink_control/session_cv_results.json.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from tensorflow.keras import Input, Model, layers, regularizers
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.utils import to_categorical

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "all_data_labeled_final6.csv"
OUT = Path(__file__).resolve().parent / "session_cv_results.json"

SEED = 42
N_FOLDS = 5
WINDOW_SIZE = 20
STEP_SIZE = 3
CLASS_NAMES = ["no blink", "single", "double"]

FEATURE_COLS = [
    "attention", "meditation", "delta", "theta",
    "lowAlpha", "highAlpha", "lowBeta", "highBeta",
    "lowGamma", "highGamma", "blinkStrength", "time",
]
BANDS = ["delta", "theta", "lowAlpha", "highAlpha", "lowBeta", "highBeta", "lowGamma", "highGamma"]


def set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)


def last_blink_interval(window, blink_idx, time_idx, threshold=60):
    times = window[:, time_idx]
    blinks = window[:, blink_idx] >= threshold
    blink_times = times[blinks]
    if len(blink_times) > 1:
        return blink_times[-1] - blink_times[-2]
    return 0.0


def make_windows(X, y, session_ids):
    """Blink_model.ipynb's make_window_features, also returning each window's session."""
    blink_idx = FEATURE_COLS.index("blinkStrength")
    time_idx = FEATURE_COLS.index("time")
    windows, labels, feats, groups = [], [], [], []
    for start in range(0, len(X) - WINDOW_SIZE + 1, STEP_SIZE):
        end = start + WINDOW_SIZE
        if len(np.unique(session_ids[start:end])) != 1:
            continue
        window = X[start:end]
        blink_vals = window[:, blink_idx]
        row = [
            np.mean(blink_vals), np.std(blink_vals), np.min(blink_vals), np.max(blink_vals),
            blink_vals[-1], np.ptp(blink_vals),
            np.mean(np.diff(blink_vals)), np.std(np.diff(blink_vals)),
            np.sum(blink_vals > 60),
            np.sum(blink_vals == 0),
            np.min(window[:, time_idx]), np.max(window[:, time_idx]), np.ptp(window[:, time_idx]),
        ]
        for band in BANDS:
            idx = FEATURE_COLS.index(band)
            row += [np.mean(window[:, idx]), np.std(window[:, idx])]
        row.append(last_blink_interval(window, blink_idx, time_idx))
        windows.append(window)
        labels.append(y[end - 1])
        feats.append(row)
        groups.append(session_ids[start])
    return np.array(windows), np.array(labels), np.array(feats), np.array(groups)


def focal_loss(alpha, gamma=2.0):
    alpha = tf.constant(alpha, dtype=tf.float32)

    def loss(y_true, y_pred):
        y_true = tf.cast(y_true, tf.float32)
        y_pred = tf.clip_by_value(y_pred, tf.keras.backend.epsilon(), 1.0 - tf.keras.backend.epsilon())
        ce = -y_true * tf.math.log(y_pred)
        return tf.reduce_sum(alpha * tf.pow(1 - y_pred, gamma) * ce, axis=-1)

    return loss


def build_model(n_channels: int, n_feats: int) -> Model:
    """The CNN-BiLSTM + engineered-feature network from Blink_model.ipynb."""
    seq_input = Input(shape=(WINDOW_SIZE, n_channels), name="windowed_input")
    x = layers.Conv1D(32, kernel_size=3, activation="relu", padding="same")(seq_input)
    x = layers.BatchNormalization()(x)
    x = layers.Conv1D(32, kernel_size=3, activation="relu", padding="same")(x)
    x = layers.MaxPooling1D(2)(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Bidirectional(layers.LSTM(64, return_sequences=False, dropout=0.3))(x)
    x = layers.Dense(64, activation="relu", kernel_regularizer=regularizers.l2(1e-4))(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)

    feat_input = Input(shape=(n_feats,), name="features_input")
    f = layers.Dense(32, activation="relu", kernel_regularizer=regularizers.l2(1e-4))(feat_input)
    f = layers.BatchNormalization()(f)
    f = layers.Dense(16, activation="relu")(f)

    z = layers.concatenate([x, f])
    z = layers.Dense(48, activation="relu", kernel_regularizer=regularizers.l2(1e-4))(z)
    z = layers.BatchNormalization()(z)
    z = layers.Dropout(0.2)(z)
    output = layers.Dense(3, activation="softmax")(z)

    model = Model(inputs=[seq_input, feat_input], outputs=output)
    model.compile(optimizer="adam", loss=focal_loss([0.3, 1.0, 0.7], gamma=2), metrics=["accuracy"])
    return model


def scale(train_w, train_f, other_w, other_f):
    """Fit both scalers on training windows only, then apply to the rest."""
    seq = StandardScaler().fit(train_w.reshape(-1, train_w.shape[-1]))
    feats = StandardScaler().fit(train_f)
    sw = lambda w: seq.transform(w.reshape(-1, w.shape[-1])).reshape(w.shape)
    return sw(train_w), feats.transform(train_f), [sw(w) for w in other_w], [feats.transform(f) for f in other_f]


def main() -> None:
    set_seeds(SEED)
    df = pd.read_csv(DATA)
    X_win, y_win, X_feats, groups = make_windows(
        df[FEATURE_COLS].values, df["blinkType"].values, df["session_id"].values
    )
    print(f"{len(y_win)} windows")

    outer = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    folds, all_true, all_pred = [], [], []

    for k, (train_idx, test_idx) in enumerate(outer.split(X_win, y_win, groups), start=1):
        assert not set(groups[train_idx]) & set(groups[test_idx]), "session leaked across the split"

        # Early-stopping validation, held out by session from the training sessions.
        inner = GroupShuffleSplit(n_splits=1, test_size=0.18, random_state=SEED)
        fit_rel, val_rel = next(inner.split(train_idx, y_win[train_idx], groups[train_idx]))
        fit_idx, val_idx = train_idx[fit_rel], train_idx[val_rel]

        tr_w, tr_f, (va_w, te_w), (va_f, te_f) = scale(
            X_win[fit_idx], X_feats[fit_idx], [X_win[val_idx], X_win[test_idx]], [X_feats[val_idx], X_feats[test_idx]]
        )

        set_seeds(SEED + k)
        model = build_model(X_win.shape[2], X_feats.shape[1])
        model.fit(
            [tr_w, tr_f], to_categorical(y_win[fit_idx], 3),
            validation_data=([va_w, va_f], to_categorical(y_win[val_idx], 3)),
            epochs=100, batch_size=96, verbose=0,
            callbacks=[
                EarlyStopping(monitor="val_loss", patience=7, restore_best_weights=True),
                ReduceLROnPlateau(monitor="val_loss", patience=3, factor=0.6, min_lr=1e-5),
            ],
        )

        pred = np.argmax(model.predict([te_w, te_f], verbose=0), axis=1)
        true = y_win[test_idx]
        fold = {
            "fold": k,
            "test_windows": int(len(test_idx)),
            "accuracy": float(accuracy_score(true, pred)),
            "macro_f1": float(f1_score(true, pred, average="macro")),
        }
        folds.append(fold)
        all_true.extend(true.tolist())
        all_pred.extend(pred.tolist())
        print(f"fold {k}: {fold['test_windows']} test windows, "
              f"accuracy {fold['accuracy']:.4f}, macro F1 {fold['macro_f1']:.4f}")

    acc = np.array([f["accuracy"] for f in folds])
    mf1 = np.array([f["macro_f1"] for f in folds])
    report = classification_report(all_true, all_pred, target_names=CLASS_NAMES, digits=4, output_dict=True)
    results = {
        "protocol": f"{N_FOLDS}-fold cross-validation grouped by session_id, stratified by blink type",
        "windows": int(len(y_win)),
        "accuracy_mean": float(acc.mean()),
        "accuracy_std": float(acc.std()),
        "macro_f1_mean": float(mf1.mean()),
        "macro_f1_std": float(mf1.std()),
        "per_class_pooled": {c: {m: float(report[c][m]) for m in ("precision", "recall", "f1-score")} for c in CLASS_NAMES},
        "confusion_matrix_pooled": confusion_matrix(all_true, all_pred).tolist(),
        "folds": folds,
        "tensorflow": tf.__version__,
    }
    OUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    print(f"\naccuracy  {100 * acc.mean():.1f}% ± {100 * acc.std():.1f}")
    print(f"macro F1  {mf1.mean():.3f} ± {mf1.std():.3f}")
    print(classification_report(all_true, all_pred, target_names=CLASS_NAMES, digits=4))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
