# +
import time
import json
import serial
import numpy as np
from telnetlib import Telnet
from collections import deque, defaultdict
from fuzzy_logic_att import MindStateControlSystem

import tensorflow as tf

# Load label encoder classes
le_att_classes = np.load("le_att_classes.npy", allow_pickle=True)
le_rel_classes = np.load("le_rel_classes.npy", allow_pickle=True)

# Load feature columns order
with open("feature_cols.json") as f:
    feature_cols = json.load(f)

# Identify bands, ratios, rolling, delta, norm
bands = ['delta', 'theta', 'lowAlpha', 'highAlpha', 'lowBeta', 'highBeta', 'lowGamma', 'highGamma']
ratios = [
    'theta_beta', 'alpha_beta', 'lowHigh_alpha', 'lowHigh_beta', 'gamma_beta',
    'alpha_theta', 'beta_theta', 'alpha_theta_beta', 'theta_alpha', 'gamma_alpha'
]
rolling_stats = [f"{b}_{stat}" for b in bands for stat in ['mean', 'std', 'min', 'max']]
deltas = [f"{b}_delta" for b in bands]
norms = [f"{b}_norm" for b in bands]

class MindStateController:
    def __init__(self):
        # Hardware setup
        self.esp32 = serial.Serial('COM4', 115200, timeout=1)
        self.tn = Telnet('localhost', 13854)
        self.tn.write(b'{"enableRawOutput":false,"format":"Json"}\n')
        time.sleep(1)

        # Control systems
        self.mind_control = MindStateControlSystem()
        
        # Mind state tracking for console output
        self.attention_history = deque(maxlen=15)
        self.meditation_history = deque(maxlen=15)
        self.last_control_update = 0
        self.control_update_interval = 1.0  # seconds
        self.last_attention = 50
        self.last_meditation = 50

        self.pwm_min = 100
        self.pwm_max = 255
        self.last_pwm = 140
        self.pwm_step = 5

        # ===== Model and feature tracking =====
        self.model = tf.keras.models.load_model("best_eeg_cnn_bilstm.h5")
        self.window_size = 20  # Should match model training
        self.seq_buffer = deque(maxlen=self.window_size)

        # Real-time tracking for engineered features
        self.rolling_size = 10  # Window for rolling/delta stats
        self.band_buffers = {band: deque(maxlen=self.rolling_size) for band in bands}
        self.band_history = defaultdict(list)  # For delta calc

    def run(self):
        print("=== Mind Controlled System Active ===")
        print("Format: [State] Att:Val(Δ)[Level] | Med:Val(Δ)[Level] | Net:Val")
        try:
            while True:
                # Read data
                line = self.tn.read_until(b'\r').decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                try:
                    data_dict = json.loads(line)
                except Exception:
                    continue

                # --- Feature extraction for the model ---
                feat_row = self._extract_features(data_dict)
                if feat_row is not None:
                    self.seq_buffer.append(feat_row)

                now = time.time()
                if now - self.last_control_update >= self.control_update_interval:
                    self._process_mind_state(data_dict)
                    self._predict_eeg_labels()
                    self.last_control_update = now

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self._send_fan_pwm(0)
            self.tn.close()
            self.esp32.close()

    def _extract_features(self, d):
        try:
            es, bp = d.get('eSense', {}), d.get('eegPower', {})
            band_vals = [bp.get(band, 0) for band in bands]
            for i, band in enumerate(bands):
                self.band_buffers[band].append(band_vals[i])
                self.band_history[band].append(band_vals[i])

            # Ratios (match training)
            alpha_sum = band_vals[2] + band_vals[3]
            beta_sum = band_vals[4] + band_vals[5]
            theta_beta = band_vals[1] / (beta_sum + 1e-6)
            alpha_beta = alpha_sum / (beta_sum + 1e-6)
            lowHigh_alpha = band_vals[2] / (band_vals[3] + 1e-6)
            lowHigh_beta = band_vals[4] / (band_vals[5] + 1e-6)
            gamma_beta = (band_vals[6] + band_vals[7]) / (beta_sum + 1e-6)
            alpha_theta = alpha_sum / (band_vals[1] + 1e-6)
            beta_theta = beta_sum / (band_vals[1] + 1e-6)
            alpha_theta_beta = alpha_sum / (band_vals[1] + beta_sum + 1e-6)
            theta_alpha = band_vals[1] / (alpha_sum + 1e-6)
            gamma_alpha = (band_vals[6] + band_vals[7]) / (alpha_sum + 1e-6)
            ratio_vals = [
                theta_beta, alpha_beta, lowHigh_alpha, lowHigh_beta, gamma_beta,
                alpha_theta, beta_theta, alpha_theta_beta, theta_alpha, gamma_alpha
            ]

            # Rolling stats (mean, std, min, max) for each band
            rollings = []
            for band in bands:
                buf = self.band_buffers[band]
                arr = np.array(buf) if buf else np.zeros(1)
                rollings += [
                    np.mean(arr), np.std(arr), np.min(arr), np.max(arr)
                ]

            # Deltas over last 10
            deltas_ = []
            for band in bands:
                hist = self.band_history[band]
                curr = hist[-1]
                prev = hist[-self.rolling_size] if len(hist) >= self.rolling_size else hist[0]
                deltas_.append(curr - prev)

            # Normalized band power
            total_power = sum(band_vals) + 1e-6
            norms_ = [val / total_power for val in band_vals]

            # Final feature vector (order: bands, ratios, rollings, deltas, norms)
            feat_vec = (
                band_vals + ratio_vals + rollings + deltas_ + norms_
            )
            # Ensure the length matches feature_cols
            if len(feat_vec) != len(feature_cols):
                print(f"Feature count mismatch: got {len(feat_vec)}, expected {len(feature_cols)}")
                return None
            return feat_vec
        except Exception as e:
            print(f"Feature extraction error: {e}")
            return None

    def _get_attention_level(self, value):
        if value < 40:
            return "LOW"
        elif 40 <= value < 70:
            return "MEDIUM"
        else:
            return "HIGH"

    def _get_meditation_level(self, value):
        if value < 40:
            return "LOW"
        elif 40 <= value < 70:
            return "MEDIUM"
        else:
            return "HIGH"

    def _send_fan_pwm(self, pwm):
        try:
            self.esp32.write(f'FAN:{pwm}\n'.encode())
            print(f"[DEBUG] Sent PWM: {pwm}")
        except Exception as e:
            print(f"Error sending PWM to ESP32: {e}")

    def _process_mind_state(self, data_dict):
        esense = data_dict.get('eSense', {})
        current_att = esense.get('attention', 50)
        current_med = esense.get('meditation', 50)
        
        # Update history
        self.attention_history.append(current_att)
        self.meditation_history.append(current_med)
        
        # Calculate smoothed values
        smooth_att = np.mean(self.attention_history)
        smooth_med = np.mean(self.meditation_history)
        
        # Calculate changes
        delta_att = smooth_att - self.last_attention
        delta_med = smooth_med - self.last_meditation
        
        # Get levels
        att_level = self._get_attention_level(smooth_att)
        med_level = self._get_meditation_level(smooth_med)
        
        # Get fuzzy effects
        effects = self.mind_control.calculate_effects(smooth_att, smooth_med)
        
        # Print colored output
        att_color = "\033[92m" if delta_att >= 0 else "\033[91m"
        med_color = "\033[92m" if delta_med < 0 else "\033[91m"  # Inverse for meditation
        net_color = "\033[92m" if effects['net_effect'] >= 0 else "\033[91m"
        reset_color = "\033[0m"
        
        print(f"[Mind State] {att_color}Att:{smooth_att:.0f}(Δ{delta_att:+.1f})[{att_level}]{reset_color} | "
              f"{med_color}Med:{smooth_med:.0f}(Δ{delta_med:+.1f})[{med_level}]{reset_color} | "
              f"{net_color}Net:{effects['net_effect']:+.2f}{reset_color}")

        # ===== Fan Speed Stepwise Logic =====
        if (att_color == "\033[92m" and med_color == "\033[91m") or (att_color == "\033[92m" and med_color == "\033[92m"):
            # Going more focused: speed up
            print("\033[92m[Focus ↑, Relax ↓ or Both ↑] Fan: FASTER\033[0m")
            self.last_pwm = min(self.pwm_max, self.last_pwm + self.pwm_step)
        elif (att_color == "\033[91m" and med_color == "\033[92m") or (att_color == "\033[91m" and med_color == "\033[91m"):
            # Going more relaxed: slow down
            print("\033[91m[Focus ↓, Relax ↑ or Both ↓] Fan: SLOWER\033[0m")
            self.last_pwm = max(self.pwm_min, self.last_pwm - self.pwm_step)
        else:
            print("\033[93m[Mixed State] Fan: MODERATE\033[0m")
            # No change

        self._send_fan_pwm(self.last_pwm)
        self.last_attention = smooth_att
        self.last_meditation = smooth_med

    def _predict_eeg_labels(self):
        if len(self.seq_buffer) < self.window_size:
            print("Waiting for full EEG sequence window...")
            return

        seq = np.array(self.seq_buffer)[-self.window_size:]
        seq = seq.reshape(1, self.window_size, len(feature_cols))
        try:
            att_pred_prob, rel_pred_prob = self.model.predict(seq, verbose=0)
            att_pred_class = np.argmax(att_pred_prob, axis=1)[0]
            rel_pred_class = np.argmax(rel_pred_prob, axis=1)[0]
            att_label = le_att_classes[att_pred_class]
            rel_label = le_rel_classes[rel_pred_class]
            print(f"\033[94m[EEG Model] Attention Prediction: {att_label}, Relaxation Prediction: {rel_label}\033[0m")
        except Exception as e:
            print(f"EEG prediction error: {e}")

if __name__ == "__main__":
    MindStateController().run()

# -




