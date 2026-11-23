"""Train/deploy input mismatch in blink_control/main.py, measured on recorded data.

Runs the committed blink model (best_eeg_cnn_bilstm_focal.h5, with its saved
scalers) on every window of all_data_labeled_final6.csv three ways:

  A. inputs as in training: `time` = seconds since session start
  B. main.py's time base: `time` = Unix clock (time.time()), here session time
     + a fixed 2026 epoch offset
  C. B plus main.py's handling of blink-only packets: eSense 50/50 and band
     powers 0 on rows that carry a blink (approximation of live packets)

Note: the committed model was trained on a random split of these same windows,
so A is optimistic. The point is the contrast between A and B/C.

usage: python model_input_mismatch.py <repo_dir> <out_dir>
"""
import json, os, sys
from pathlib import Path
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import numpy as np
import pandas as pd
import joblib
import tensorflow as tf
from sklearn.metrics import accuracy_score, f1_score

REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(Path(__file__).resolve().parent))
import r2_4_baselines as B

M = REPO / "blink_control"
model = tf.keras.models.load_model(M / "best_eeg_cnn_bilstm_focal.h5", compile=False)
s_seq, s_feat = joblib.load(M / "scaler_seq.pkl"), joblib.load(M / "scaler_feats.pkl")
df = pd.read_csv(REPO / "data" / "all_data_labeled_final6.csv")
EPOCH = 1_790_000_000.0  # a late-2026 Unix time

variants = {}
d_b = df.copy(); d_b["time"] = d_b["time"] + EPOCH
d_c = d_b.copy()
blink = d_c.blinkStrength > 0
d_c.loc[blink, ["attention", "meditation"]] = 50
d_c.loc[blink, B.BANDS] = 0
for name, d in {"A_training_inputs": df, "B_unix_time": d_b, "C_unix_time_and_live_packets": d_c}.items():
    win, y, feats, grp, _ = B.make_windows(d)
    ws = s_seq.transform(win.reshape(-1, win.shape[-1])).reshape(win.shape).astype("float32")
    fs = s_feat.transform(feats).astype("float32")
    p = model.predict([ws, fs], batch_size=512, verbose=0)
    pred = p.argmax(1)
    is_blink = y > 0
    variants[name] = {
        "windows": int(len(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, average="macro")),
        "blink_windows_predicted_no_blink": float(np.mean(pred[is_blink] == 0)),
        "mean_p_noblink_on_blink_windows": float(p[is_blink, 0].mean()),
        "max_abs_scaled_time_feature": float(np.abs(ws[..., B.TI]).max()),
    }
    v = variants[name]
    print(f"{name:32s} acc {100*v['accuracy']:5.1f}%  blink windows called 'no blink': "
          f"{100*v['blink_windows_predicted_no_blink']:5.1f}%  mean p(no blink) {v['mean_p_noblink_on_blink_windows']:.3f}  "
          f"max |scaled time| {v['max_abs_scaled_time_feature']:.3g}")
(OUT / "model_input_mismatch.json").write_text(json.dumps(variants, indent=2))
