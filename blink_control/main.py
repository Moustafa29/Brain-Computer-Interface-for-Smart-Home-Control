# +
import time
import json
import joblib
import serial
import numpy as np
import tensorflow as tf
from telnetlib import Telnet
from collections import deque
from fuzzy_logic import BlinkConfidenceSystem

class BlinkDetector:
    def __init__(self):
        self.model = tf.keras.models.load_model(
            'best_eeg_cnn_bilstm_focal.h5',
            custom_objects={'loss': self._custom_focal_loss([0.3, 1.0, 0.7], 2)}
        )
        self.window_scaler = joblib.load('scaler_seq.pkl')
        self.feats_scaler = joblib.load('scaler_feats.pkl')
        with open('windowed_feature_cols.json') as f:
            self.feature_cols = json.load(f)
        with open('preprocessing_meta.json') as f:
            meta = json.load(f)
        self.window_size = meta['window_size']

        self.esp32 = serial.Serial('COM4', 115200, timeout=1)
        self.tn = Telnet('localhost', 13854)
        self.tn.write(b'{"enableRawOutput": false,"format":"Json","enableBlinkDetection": true,"enableESense": true,"enableSpectra": true}\n')
        time.sleep(1)

        self.blink_threshold = 60
        self.double_blink_interval = 1.0
        self.min_blink_strength = 60
        
        self.buf = np.zeros((self.window_size, len(self.feature_cols)), dtype=float)
        self.last_blink_time = 0
        self.pending_blink = None
        self.prediction_history = deque(maxlen=5)
        self.blink_strength_history = deque(maxlen=5)
        self.fuzzy = BlinkConfidenceSystem()

    def _custom_focal_loss(self, alpha, gamma):
        alpha = tf.constant(alpha, dtype=tf.float32)
        def loss(y_true, y_pred):
            y_true = tf.cast(y_true, tf.float32)
            y_pred = tf.clip_by_value(y_pred, 1e-7, 1 - 1e-7)
            ce = -y_true * tf.math.log(y_pred)
            weight = alpha * tf.pow(1 - y_pred, gamma)
            loss = weight * ce
            return tf.reduce_sum(loss, axis=-1)
        return loss

    def run(self):
        print("=== Advanced Blink Detector (With Fuzzy Confidence) Running ===")
        try:
            while True:
                # Handle pending single blink timeout at the **start of each loop**
                if self.pending_blink:
                    elapsed = time.time() - self.pending_blink['time']
                    if elapsed > self.double_blink_interval:
                        self._trigger_single_blink(self.pending_blink)
                        self.pending_blink = None

                # Read data and ALWAYS update buffer to avoid zeros!
                line = self.tn.read_until(b'\r').decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                try:
                    data_dict = json.loads(line)
                except Exception:
                    continue

                feats = self._extract_features(data_dict)
                self._roll_buffer(feats)  # Always keep buffer live

                raw_blink_strength = data_dict.get("blinkStrength", 0)
                now = time.time()
                if raw_blink_strength < self.min_blink_strength:
                    continue

                self.blink_strength_history.append(raw_blink_strength)
                smoothed_strength = np.mean(list(self.blink_strength_history)[-3:]) if self.blink_strength_history else raw_blink_strength

                if smoothed_strength > self.blink_threshold:
                    # Model inference
                    window_scaled = self.window_scaler.transform(self.buf).reshape(
                        1, self.window_size, len(self.feature_cols))
                    engineered_feats = self._compute_engineered_features(self.buf)
                    feats_scaled = self.feats_scaler.transform([engineered_feats])

                    cnn_proba = self.model.predict([window_scaled, feats_scaled], verbose=0)[0]
                    cnn_pred = int(np.argmax(cnn_proba))

                    # Ensure only class 1 or 2 ("no blink" is class 0)
                    if cnn_pred == 0:
                        nonzero_preds = [p for p in self.prediction_history if p in [1,2]]
                        cnn_pred = nonzero_preds[-1] if nonzero_preds else 1

                    self.prediction_history.append(cnn_pred)
                    smoothed_pred = self._get_smoothed_prediction()
                    fuzzy_conf = self.fuzzy.calculate_confidence(smoothed_strength)
                    
                    blink_record = {
                        'time': now,
                        'strength': smoothed_strength,
                        'raw_pred': cnn_pred,
                        'smoothed_pred': smoothed_pred,
                        'fuzzy_conf': fuzzy_conf
                    }

                    if self.pending_blink and (now - self.pending_blink['time']) <= self.double_blink_interval:
                        self._trigger_double_blink(self.pending_blink, blink_record)
                        self.pending_blink = None
                    else:
                        # If there is already a pending blink but the window expired, print it as single
                        if self.pending_blink:
                            self._trigger_single_blink(self.pending_blink)
                        self.pending_blink = blink_record

        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            self.tn.close()
            self.esp32.close()

    def _get_smoothed_prediction(self):
        if not self.prediction_history:
            return 1
        preds = [p if p in [1,2] else 1 for p in self.prediction_history]
        counts = np.bincount(preds+[0])
        return np.argmax(counts) if np.argmax(counts) != 0 else 1

    def _trigger_single_blink(self, blink):
        log_pred = 1 if blink['smoothed_pred'] in [1,2] else 1
        self._send_servo('DOOR', 90)  # Door servo on pin 18
        print(f"[Single Blink] | strength={int(blink['strength'])} | model={log_pred} | fuzzy={blink['fuzzy_conf']:.2f} | Servo=DOOR:90°")

    def _trigger_double_blink(self, first, second):
        log_pred1 = 1 if first['smoothed_pred'] in [1,2] else 1
        log_pred2 = 2 if second['smoothed_pred'] in [1,2] else 2
        print(f"[Double Blink] | strengths=({int(first['strength'])},{int(second['strength'])}) | models=({log_pred1},{log_pred2}) | fuzzy=({first['fuzzy_conf']:.2f},{second['fuzzy_conf']:.2f}) | Servo=WINDOW:90°")
        self._send_servo('WINDOW', 90)  # Window servo on pin 4

    def _send_servo(self, target, angle):
        # target is 'DOOR' or 'WINDOW'
        self.esp32.write(f"ServoAngle:{target}:{angle}\n".encode())

    def _extract_features(self, d):
        es, bp = d.get('eSense', {}), d.get('eegPower', {})
        return [
            es.get('attention', 50),
            es.get('meditation', 50),
            bp.get('delta', 0),
            bp.get('theta', 0),
            bp.get('lowAlpha', 0),
            bp.get('highAlpha', 0),
            bp.get('lowBeta', 0),
            bp.get('highBeta', 0),
            bp.get('lowGamma', 0),
            bp.get('highGamma', 0),
            d.get('blinkStrength', 0),
            time.time()
        ]

    def _roll_buffer(self, feats):
        self.buf = np.roll(self.buf, -1, axis=0)
        self.buf[-1] = feats

    def _compute_engineered_features(self, window):
        blink_idx = self.feature_cols.index('blinkStrength')
        time_idx = self.feature_cols.index('time')
        blink_vals = window[:, blink_idx]
        feats = [
            np.mean(blink_vals), np.std(blink_vals), np.min(blink_vals), np.max(blink_vals),
            blink_vals[-1], np.ptp(blink_vals),
            np.mean(np.diff(blink_vals)), np.std(np.diff(blink_vals)),
            np.sum(blink_vals > self.blink_threshold),
            np.sum(blink_vals == 0),
            np.min(window[:, time_idx]), np.max(window[:, time_idx]), np.ptp(window[:, time_idx])
        ]
        for band in ['delta','theta','lowAlpha','highAlpha','lowBeta','highBeta','lowGamma','highGamma']:
            idx = self.feature_cols.index(band)
            feats += [np.mean(window[:, idx]), np.std(window[:, idx])]
        blinks = blink_vals >= self.blink_threshold
        blink_times = window[:, time_idx][blinks]
        feats.append((blink_times[-1] - blink_times[-2]) if len(blink_times) > 1 else 0.0)
        return feats

if __name__ == "__main__":
    BlinkDetector().run()

# -






