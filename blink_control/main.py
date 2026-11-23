# +
import time
import json
import socket
import joblib
import serial
import numpy as np
import tensorflow as tf
from collections import deque
from fuzzy_logic import BlinkConfidenceSystem

THINKGEAR = ('localhost', 13854)
THINKGEAR_CONFIG = b'{"enableRawOutput": false,"format":"Json","enableBlinkDetection": true,"enableESense": true,"enableSpectra": true}\n'
BANDS = ['delta', 'theta', 'lowAlpha', 'highAlpha', 'lowBeta', 'highBeta', 'lowGamma', 'highGamma']


class BlinkDetector:
    def __init__(self):
        # Inference only, so the model is loaded without compiling it.
        self.model = tf.keras.models.load_model('best_eeg_cnn_bilstm_focal.h5', compile=False)
        self.window_scaler = joblib.load('scaler_seq.pkl')
        self.feats_scaler = joblib.load('scaler_feats.pkl')
        with open('windowed_feature_cols.json') as f:
            self.feature_cols = json.load(f)
        with open('preprocessing_meta.json') as f:
            meta = json.load(f)
        self.window_size = meta['window_size']

        self.esp32 = serial.Serial('COM4', 115200, timeout=1)
        # A plain socket instead of telnetlib (removed in Python 3.13). The
        # short timeout lets the loop run even when no packet arrives, so a
        # pending single blink is dispatched on time (see run()).
        self.sock = socket.create_connection(THINKGEAR, timeout=5)
        self.sock.sendall(THINKGEAR_CONFIG)
        self.sock.settimeout(0.02)
        self._rx = b''
        time.sleep(1)

        self.blink_threshold = 60
        self.double_blink_interval = 1.0
        self.min_blink_strength = 60
        # Minimum fuzzy confidence for a blink to count as intentional. Below
        # this the event is treated as noise and no servo command is sent.
        # The gate in fuzzy_logic.py scores exactly 0.60 at strength 60, so the
        # default lets through every event the labelling rule accepts; raising
        # it makes the system stricter, gradually.
        self.fuzzy_gate = 0.60

        # Model inputs must be built the way the training data was: `time` in
        # seconds since the start of the session (training sessions ran from 0
        # to ~700 s), and eSense / band powers carried forward from the last
        # packet that had them (blink-only packets carry neither).
        self.t0 = time.time()
        self.last_esense = {'attention': 50, 'meditation': 50}
        self.last_power = {}

        self.buf = np.zeros((self.window_size, len(self.feature_cols)), dtype=float)
        self.last_blink_time = 0
        self.pending_blink = None
        self.prediction_history = deque(maxlen=5)
        self.blink_strength_history = deque(maxlen=5)
        self.fuzzy = BlinkConfidenceSystem()

    def _read_line(self):
        """One ThinkGear JSON line, or None if nothing arrived within 20 ms."""
        while b'\r' not in self._rx:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                return None
            if not chunk:
                raise ConnectionError('ThinkGear Connector closed the connection')
            self._rx += chunk
        line, self._rx = self._rx.split(b'\r', 1)
        return line.decode('utf-8', errors='ignore').strip()

    def run(self):
        print("=== Advanced Blink Detector (With Fuzzy Confidence) Running ===")
        try:
            while True:
                # Dispatch a pending single blink once the double-blink window
                # has passed. _read_line() returns within 20 ms even when no
                # packet arrives, so this fires ~1.0 s after the blink rather
                # than whenever the next packet happens to come (up to ~2 s).
                if self.pending_blink:
                    elapsed = time.time() - self.pending_blink['time']
                    if elapsed > self.double_blink_interval:
                        self._trigger_single_blink(self.pending_blink)
                        self.pending_blink = None

                line = self._read_line()
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

                    # The model runs alongside the rule and is logged; the action
                    # itself is decided by the threshold, the fuzzy gate and the
                    # 1 s timing rule below.
                    cnn_proba = self.model.predict([window_scaled, feats_scaled], verbose=0)[0]
                    cnn_pred = int(np.argmax(cnn_proba))
                    self.prediction_history.append(cnn_pred)
                    smoothed_pred = self._get_smoothed_prediction()
                    fuzzy_conf = self.fuzzy.calculate_confidence(smoothed_strength)
                    
                    # Gate on fuzzy confidence: a weak or ambiguous blink is
                    # rejected here instead of being logged and acted on anyway.
                    if fuzzy_conf < self.fuzzy_gate:
                        print(f"[Rejected] strength={int(smoothed_strength)} | "
                              f"fuzzy={fuzzy_conf:.2f} < gate {self.fuzzy_gate:.2f}")
                        continue
                    
                    blink_record = {
                        'time': now,
                        'strength': smoothed_strength,
                        'raw_pred': cnn_pred,
                        'proba': cnn_proba,
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
            self.sock.close()
            self.esp32.close()

    def _get_smoothed_prediction(self):
        """Majority vote over the last five model predictions (0 = no blink,
        1 = single, 2 = double). Logged only."""
        if not self.prediction_history:
            return 0
        return int(np.argmax(np.bincount(list(self.prediction_history), minlength=3)))

    @staticmethod
    def _fmt_model(blink):
        p = blink['proba']
        return f"model={blink['raw_pred']} (p no/single/double = {p[0]:.2f}/{p[1]:.2f}/{p[2]:.2f})"

    def _trigger_single_blink(self, blink):
        self._send_servo('DOOR', 90)  # Door servo on pin 18
        print(f"[Single Blink] | strength={int(blink['strength'])} | {self._fmt_model(blink)} | fuzzy={blink['fuzzy_conf']:.2f} | Servo=DOOR:90°")

    def _trigger_double_blink(self, first, second):
        print(f"[Double Blink] | strengths=({int(first['strength'])},{int(second['strength'])}) | {self._fmt_model(second)} | fuzzy=({first['fuzzy_conf']:.2f},{second['fuzzy_conf']:.2f}) | Servo=WINDOW:90°")
        self._send_servo('WINDOW', 90)  # Window servo on pin 4

    def _send_servo(self, target, angle):
        # target is 'DOOR' or 'WINDOW'
        self.esp32.write(f"ServoAngle:{target}:{angle}\n".encode())

    def _extract_features(self, d):
        # Carry eSense and band powers forward: blink-only packets have neither,
        # and every row of the training data held real values for both.
        if d.get('eSense'):
            self.last_esense.update(d['eSense'])
        if d.get('eegPower'):
            self.last_power.update(d['eegPower'])
        return [
            self.last_esense.get('attention', 50),
            self.last_esense.get('meditation', 50),
            *[self.last_power.get(b, 0) for b in BANDS],
            d.get('blinkStrength', 0),
            time.time() - self.t0,   # seconds since start, as in training -- not the Unix clock
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






