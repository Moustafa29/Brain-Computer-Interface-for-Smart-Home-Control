"""MindAssist revision session: cued trials, live control, full logging.

One program, one clock. It shows cues on screen, reads the NeuroSky headset
through the ThinkGear Connector, runs the same blink decision logic as
blink_control/main.py, drives the ESP32 servos, and logs everything needed to
answer the reviewers afterwards:

  cues.csv     every cue: type and on-screen onset/offset times (ground truth
               that owes nothing to the headset's blink detector)
  packets.csv  every headset packet as it arrived
  events.csv   every blink packet with strength >= 60: smoothed strength,
               deployed and corrected gate confidences, model probabilities on
               corrected inputs and on the inputs the original main.py built
  actions.csv  every servo command the session sent, with decision and write
               times
  acks.csv     acknowledgments from the ESP32 (needs the 3-line firmware patch)
  meta.json    settings, versions, participant code

Decision logic is blink_control/main.py's, line for line: strength >= 60 enters a 5-deep
history, smoothed strength is the mean of the last 3, an event needs
smoothed > 60, a second event within 1.0 s makes a double. Two deliberate
differences, both logged:
  - the pending single blink is dispatched by a 10 ms timer, not only when the
    next packet happens to arrive (the original main.py could wait 1-2 s; fixed
    in main.py on this branch)
  - the gate used to drive the servos is chosen with --gate; every event is
    scored under all gates regardless, so all decision paths are compared on
    the same blinks

usage (Windows, ThinkGear Connector running, headset paired):
  python mindassist_session.py --participant P01 --block detection --run 1 --gate corrected --com COM4
  python mindassist_session.py --participant P01 --block task --gate off --com COM4
test without hardware:
  python mindassist_session.py --participant TEST --block detection --simulate synthetic --com none --no-gui --trials 12
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import queue
import random
import socket
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True  # keep blink_control/ free of __pycache__
HERE = Path(__file__).resolve().parent
DEFAULT_MODEL_DIR = HERE.parent / "blink_control"

T0 = time.perf_counter()


def now() -> float:
    """Seconds since program start, monotonic. The one clock for every log."""
    return time.perf_counter() - T0


# --------------------------------------------------------------------- logging
class CsvLog:
    def __init__(self, path: Path, header: list[str]):
        self.f = open(path, "w", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        self.w.writerow(header)
        self.lock = threading.Lock()

    def row(self, *vals):
        with self.lock:
            self.w.writerow(vals)
            self.f.flush()

    def close(self):
        with self.lock:
            self.f.close()


# ----------------------------------------------------------------- cue schedule
CUE_TEXT = {
    "SINGLE": "BLINK ONCE",
    "DOUBLE": "BLINK TWICE",
    "REST": "KEEP STILL\n(don't blink on purpose)",
    "FROWN": "FROWN",
    "EYEBROWS": "RAISE YOUR EYEBROWS",
    "LOOK_LEFT": "LOOK LEFT",
    "LOOK_RIGHT": "LOOK RIGHT",
    "JAW": "CLENCH YOUR JAW",
    "DOOR": "OPEN THE DOOR\n(blink once)",
    "WINDOW": "OPEN THE WINDOW\n(blink twice)",
}
EXPECTED = {"SINGLE": "single", "DOUBLE": "double", "DOOR": "single", "WINDOW": "double"}
CONFOUNDERS = ["FROWN", "EYEBROWS", "LOOK_LEFT", "LOOK_RIGHT", "JAW"]


def build_schedule(block: str, run: int, trials: int | None, seed: int) -> list[str]:
    if block == "detection":
        # per run: 10 single, 10 double, 10 rest, 4 of each confounder = 50
        per = {"SINGLE": 10, "DOUBLE": 10, "REST": 10, **{c: 4 for c in CONFOUNDERS}}
    elif block == "task":
        per = {"DOOR": 20, "WINDOW": 20}
    else:
        raise ValueError(block)
    items = [k for k, n in per.items() for _ in range(n)]
    if trials:  # proportional cut for quick tests
        rng = random.Random(seed)
        rng.shuffle(items)
        items = items[:trials]
    rng = random.Random(seed * 100 + run)
    for _ in range(1000):  # shuffle with no more than two identical cues in a row
        rng.shuffle(items)
        if all(not (items[i] == items[i - 1] == items[i - 2]) for i in range(2, len(items))):
            break
    return items


class CueBus:
    """Current cue, shared with the synthetic headset so it can respond."""
    def __init__(self):
        self.lock = threading.Lock()
        self.current = None  # (trial, cue, onset)

    def set(self, v):
        with self.lock:
            self.current = v

    def get(self):
        with self.lock:
            return self.current


# -------------------------------------------------------------- headset sources
THINKGEAR_CONFIG = (b'{"enableRawOutput": false,"format":"Json",'
                    b'"enableBlinkDetection": true,"enableESense": true,"enableSpectra": true}\n')


class ThinkGearSource(threading.Thread):
    """Reads JSON packets from the ThinkGear Connector (as main.py does, via a
    plain socket so it works on any Python version)."""
    def __init__(self, out_q: queue.Queue, stop: threading.Event, host="127.0.0.1", port=13854):
        super().__init__(daemon=True)
        self.q, self.stop, self.addr = out_q, stop, (host, port)

    def run(self):
        try:
            s = socket.create_connection(self.addr, timeout=5)
        except OSError as e:
            self.q.put(("error", f"Cannot reach ThinkGear Connector at {self.addr}: {e}. "
                                 "Is it running and is the headset paired?"))
            return
        s.sendall(THINKGEAR_CONFIG)
        s.settimeout(0.5)
        buf = b""
        while not self.stop.is_set():
            try:
                chunk = s.recv(4096)
            except socket.timeout:
                continue
            except OSError as e:
                self.q.put(("error", f"ThinkGear connection lost: {e}"))
                return
            if not chunk:
                self.q.put(("error", "ThinkGear connection closed"))
                return
            buf += chunk
            while b"\r" in buf:
                line, buf = buf.split(b"\r", 1)
                line = line.strip()
                if not line:
                    continue
                t = now()
                try:
                    d = json.loads(line.decode("utf-8", errors="ignore"))
                except ValueError:
                    continue
                if isinstance(d, dict):
                    self.q.put(("packet", (t, d)))
        s.close()


class SyntheticSource(threading.Thread):
    """Fake headset for testing the pipeline. Emits ~1 Hz eSense/eegPower
    packets and blink packets that respond to the current cue with known
    ground truth (and occasional spontaneous or confounder-driven blinks)."""
    def __init__(self, out_q, stop, cues: CueBus, seed=7):
        super().__init__(daemon=True)
        self.q, self.stop, self.cues = out_q, stop, cues
        self.rng = np.random.default_rng(seed)

    def _band_packet(self):
        r = self.rng
        return {"eSense": {"attention": int(r.integers(20, 90)), "meditation": int(r.integers(20, 90))},
                "eegPower": {k: int(r.lognormal(m, 1.0)) for k, m in
                             [("delta", 12), ("theta", 11), ("lowAlpha", 9), ("highAlpha", 9),
                              ("lowBeta", 9), ("highBeta", 9), ("lowGamma", 8), ("highGamma", 8)]},
                "poorSignalLevel": 0}

    def run(self):
        r = self.rng
        next_band = now() + 0.5
        handled = set()
        pending = []  # (time, strength)
        while not self.stop.is_set():
            t = now()
            cur = self.cues.get()
            if cur and cur[0] not in handled:
                trial, cue, onset = cur
                handled.add(trial)
                start = onset + r.uniform(0.35, 0.8)
                if cue in ("SINGLE", "DOOR") and r.random() < 0.92:
                    pending.append((start, r.normal(130, 40)))
                elif cue in ("DOUBLE", "WINDOW") and r.random() < 0.88:
                    gap = r.uniform(0.3, 0.7)
                    pending += [(start, r.normal(120, 35)), (start + gap, r.normal(115, 35))]
                elif cue in CONFOUNDERS and r.random() < 0.35:
                    pending.append((start, r.normal(78, 15)))
                elif cue == "REST" and r.random() < 0.15:
                    pending.append((start + r.uniform(0, 2), r.normal(70, 8)))
            due = [p for p in pending if p[0] <= t]
            for p in due:
                pending.remove(p)
                self.q.put(("packet", (now(), {"blinkStrength": int(np.clip(p[1], 1, 255))})))
            if t >= next_band:
                self.q.put(("packet", (now(), self._band_packet())))
                next_band = t + r.uniform(0.7, 1.3)
            time.sleep(0.005)


class ReplaySource(threading.Thread):
    """Replays one recorded session from all_data_labeled_final6.csv in real time."""
    def __init__(self, out_q, stop, csv_path: Path, session_id: int):
        super().__init__(daemon=True)
        import pandas as pd
        df = pd.read_csv(csv_path)
        self.rows = df[df.session_id == session_id].to_dict("records")
        self.q, self.stop = out_q, stop

    def run(self):
        bands = ["delta", "theta", "lowAlpha", "highAlpha", "lowBeta", "highBeta", "lowGamma", "highGamma"]
        start, t_first = now(), self.rows[0]["time"]
        for r in self.rows:
            while now() - start < r["time"] - t_first:
                if self.stop.is_set():
                    return
                time.sleep(0.002)
            d = {"eSense": {"attention": r["attention"], "meditation": r["meditation"]},
                 "eegPower": {b: r[b] for b in bands}, "poorSignalLevel": 0}
            if r["blinkStrength"] > 0:
                d["blinkStrength"] = r["blinkStrength"]
            self.q.put(("packet", (now(), d)))


# ----------------------------------------------------------------------- ESP32
class ESP32:
    def __init__(self, port: str, acks: CsvLog, stop: threading.Event):
        import serial  # pyserial
        self.ser = serial.Serial(port, 115200, timeout=0.05)
        self.acks, self.stop = acks, stop
        time.sleep(3.0)              # opening the port resets the ESP32; wait for boot
        self.ser.reset_input_buffer()
        self.lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()

    def write(self, cmd: str) -> float:
        with self.lock:
            self.ser.write((cmd + "\n").encode())
            self.ser.flush()
            return now()

    def _reader(self):
        buf = b""
        while not self.stop.is_set():
            try:
                chunk = self.ser.read(256)
            except Exception:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode("utf-8", errors="ignore").strip()
                if text:
                    self.acks.row(f"{now():.4f}", text)

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


class FakeESP32:
    def __init__(self, acks: CsvLog):
        self.acks = acks

    def write(self, cmd: str) -> float:
        t = now()
        target = cmd.split(":")[1] if ":" in cmd else cmd
        threading.Timer(0.008, lambda: self.acks.row(f"{now():.4f}", f"ACK:{target}")).start()
        return t

    def close(self):
        pass


class NoESP32:
    def write(self, cmd: str) -> float:
        return now()

    def close(self):
        pass


# ------------------------------------------------------------------ the model
class BlinkModel:
    """The repository's CNN-BiLSTM with its saved scalers and feature list."""
    def __init__(self, model_dir: Path):
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
        import joblib
        import tensorflow as tf
        self.model = tf.keras.models.load_model(model_dir / "best_eeg_cnn_bilstm_focal.h5", compile=False)
        self.seq_scaler = joblib.load(model_dir / "scaler_seq.pkl")
        self.feat_scaler = joblib.load(model_dir / "scaler_feats.pkl")
        self.cols = json.loads((model_dir / "windowed_feature_cols.json").read_text())
        self.window = json.loads((model_dir / "preprocessing_meta.json").read_text())["window_size"]
        self.bi, self.ti = self.cols.index("blinkStrength"), self.cols.index("time")
        self.band_idx = [self.cols.index(b) for b in
                         ["delta", "theta", "lowAlpha", "highAlpha", "lowBeta", "highBeta", "lowGamma", "highGamma"]]
        self.predict(np.zeros((self.window, len(self.cols))))  # warm-up

    def engineered(self, w: np.ndarray, thr=60):
        """main.py _compute_engineered_features, verbatim."""
        bv = w[:, self.bi]
        f = [np.mean(bv), np.std(bv), np.min(bv), np.max(bv), bv[-1], np.ptp(bv),
             np.mean(np.diff(bv)), np.std(np.diff(bv)), np.sum(bv > thr), np.sum(bv == 0),
             np.min(w[:, self.ti]), np.max(w[:, self.ti]), np.ptp(w[:, self.ti])]
        for i in self.band_idx:
            f += [np.mean(w[:, i]), np.std(w[:, i])]
        bt = w[:, self.ti][bv >= thr]
        f.append((bt[-1] - bt[-2]) if len(bt) > 1 else 0.0)
        return f

    def predict(self, w: np.ndarray):
        ws = self.seq_scaler.transform(w).reshape(1, self.window, len(self.cols)).astype("float32")
        fs = self.feat_scaler.transform([self.engineered(w)]).astype("float32")
        return self.model([ws, fs], training=False).numpy()[0]


# ------------------------------------------------------------------ controller
class Controller:
    THRESHOLD, MIN_STRENGTH, DOUBLE_INTERVAL, GATE = 60, 60, 1.0, 0.60

    def __init__(self, gate_mode, model, esp, logs, deployed_gate, corrected_gate):
        self.gate_mode, self.model, self.esp, self.logs = gate_mode, model, esp, logs
        self.g_dep, self.g_cor = deployed_gate, corrected_gate
        self.hist = deque(maxlen=5)
        self.pending = None
        self.lock = threading.Lock()
        n = len(model.cols) if model else 12
        w = model.window if model else 20
        self.buf_fixed = np.zeros((w, n))     # features as the training data had them
        self.buf_legacy = np.zeros((w, n))    # features exactly as the original main.py built them
        self.packets_seen = 0
        self.last_es = {"attention": 50, "meditation": 50}
        self.last_bp = {}
        self.event_id = 0
        self.last_action = ""

    # features ---------------------------------------------------------------
    BANDS = ["delta", "theta", "lowAlpha", "highAlpha", "lowBeta", "highBeta", "lowGamma", "highGamma"]

    def _rows(self, t, d):
        es, bp = d.get("eSense"), d.get("eegPower")
        if es:
            self.last_es = {**self.last_es, **es}
        if bp:
            self.last_bp = {**self.last_bp, **bp}
        blink = d.get("blinkStrength", 0)
        fixed = ([self.last_es.get("attention", 50), self.last_es.get("meditation", 50)]
                 + [self.last_bp.get(b, 0) for b in self.BANDS] + [blink, t])
        es_raw, bp_raw = d.get("eSense", {}), d.get("eegPower", {})
        legacy = ([es_raw.get("attention", 50), es_raw.get("meditation", 50)]
                  + [bp_raw.get(b, 0) for b in self.BANDS] + [blink, time.time()])
        return fixed, legacy

    @staticmethod
    def _roll(buf, row):
        buf[:] = np.roll(buf, -1, axis=0)
        buf[-1] = row

    # decisions --------------------------------------------------------------
    def _fire(self, kind, events, reason):
        target = "DOOR" if kind == "single" else "WINDOW"
        t_dec = now()
        t_write = self.esp.write(f"ServoAngle:{target}:90")
        self.logs["actions"].row(f"{t_dec:.4f}", f"{t_write:.4f}", kind, target, self.gate_mode, reason,
                                 ";".join(str(e["id"]) for e in events),
                                 f"{events[-1]['t']:.4f}")
        self.last_action = f"{kind} -> {target}"

    def tick(self):
        """Dispatch a pending single blink once the double-blink window has passed."""
        with self.lock:
            if self.pending and now() - self.pending["t"] > self.DOUBLE_INTERVAL:
                p, self.pending = self.pending, None
                self._fire("single", [p], "timer")

    def on_packet(self, t, d):
        with self.lock:
            fixed, legacy = self._rows(t, d)
            self._roll(self.buf_fixed, fixed)
            self._roll(self.buf_legacy, legacy)
            self.packets_seen += 1
            es, bp = d.get("eSense", {}), d.get("eegPower", {})
            self.logs["packets"].row(f"{t:.4f}", d.get("poorSignalLevel", ""), es.get("attention", ""),
                                     es.get("meditation", ""), *[bp.get(b, "") for b in self.BANDS],
                                     d.get("blinkStrength", ""))

            raw = d.get("blinkStrength", 0)
            if self.pending and t - self.pending["t"] > self.DOUBLE_INTERVAL:  # also checked per packet, as main.py does
                p, self.pending = self.pending, None
                self._fire("single", [p], "packet")
            if raw < self.MIN_STRENGTH:
                return
            self.hist.append(raw)
            smoothed = float(np.mean(list(self.hist)[-3:]))
            c_dep = self.g_dep.calculate_confidence(smoothed)
            c_cor = self.g_cor.calculate_confidence(smoothed)
            rule_pass = smoothed > self.THRESHOLD

            p_fix = p_leg = (np.nan, np.nan, np.nan)
            m_ms = np.nan
            if self.model is not None and rule_pass:
                t_m = now()
                p_fix = self.model.predict(self.buf_fixed)
                m_ms = (now() - t_m) * 1000
            self.event_id += 1
            ev = {"id": self.event_id, "t": t, "raw": raw, "smoothed": smoothed}

            if rule_pass:
                conf = {"deployed": c_dep, "corrected": c_cor, "off": 1.0}[self.gate_mode]
                if conf < self.GATE:
                    decision = "gate_rejected"
                elif self.pending and t - self.pending["t"] <= self.DOUBLE_INTERVAL:
                    first, self.pending = self.pending, None
                    self._fire("double", [first, ev], "pair")
                    decision = "double_second"
                else:
                    if self.pending:
                        p, self.pending = self.pending, None
                        self._fire("single", [p], "superseded")
                    self.pending = ev
                    decision = "pending"
            else:
                decision = "below_threshold"

            if self.model is not None and rule_pass:
                p_leg = self.model.predict(self.buf_legacy)  # after the decision: logged only
            self.logs["events"].row(
                self.event_id, f"{t:.4f}", raw, f"{smoothed:.2f}", int(rule_pass), f"{c_dep:.2f}", f"{c_cor:.2f}",
                self.gate_mode, decision, *[f"{v:.4f}" for v in p_fix], f"{m_ms:.1f}",
                *[f"{v:.4f}" for v in p_leg], self.packets_seen)


# ------------------------------------------------------------------ the runner
FIXATION_S, CUE_S, ITI_RANGE = 1.0, 3.0, (2.0, 3.0)
TASK_CUE_S, TASK_ITI = 4.0, (2.5, 3.5)
WARMUP_S = 30


class Session:
    def __init__(self, args):
        self.args = args
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{args.participant}_{args.block}{'_run' + str(args.run) if args.block == 'detection' else ''}_{args.gate}_{stamp}"
        self.out = Path(args.out) / name
        self.out.mkdir(parents=True, exist_ok=True)
        self.stop = threading.Event()
        self.q: queue.Queue = queue.Queue()
        self.cues = CueBus()
        self.logs = {
            "cues": CsvLog(self.out / "cues.csv", ["trial", "cue", "expected", "t_fixation", "t_onset", "t_offset"]),
            "packets": CsvLog(self.out / "packets.csv", ["t", "poorSignal", "attention", "meditation",
                                                          *Controller.BANDS, "blinkStrength"]),
            "events": CsvLog(self.out / "events.csv", [
                "event_id", "t", "raw_strength", "smoothed_strength", "rule_pass", "conf_deployed",
                "conf_corrected", "gate_mode", "decision", "p_noblink", "p_single", "p_double", "model_ms",
                "legacy_p_noblink", "legacy_p_single", "legacy_p_double", "packets_seen"]),
            "actions": CsvLog(self.out / "actions.csv", ["t_decision", "t_serial_write", "kind", "target",
                                                          "gate_mode", "dispatch", "event_ids", "t_last_event"]),
            "acks": CsvLog(self.out / "acks.csv", ["t", "line"]),
        }
        self.schedule = build_schedule(args.block, args.run, args.trials, seed=hash(args.participant) % 10000)

    def setup(self):
        a = self.args
        # Both gates ship with the kit, so the comparison is the same whichever
        # version of blink_control/fuzzy_logic.py is checked out.
        sys.path.insert(0, str(HERE))
        import importlib
        deployed = importlib.import_module("gate_original").BlinkConfidenceSystem()
        corrected = importlib.import_module("gate_corrected").BlinkConfidenceSystem()
        print("loading model ...", flush=True)
        model = None if a.no_model else BlinkModel(Path(a.model_dir))
        if a.com.lower() == "none":
            esp = FakeESP32(self.logs["acks"]) if a.simulate else NoESP32()
        else:
            print(f"opening {a.com} (the ESP32 restarts; ~3 s) ...", flush=True)
            esp = ESP32(a.com, self.logs["acks"], self.stop)
        self.esp = esp
        self.ctl = Controller(a.gate, model, esp, self.logs, deployed, corrected)
        if a.simulate == "synthetic":
            src = SyntheticSource(self.q, self.stop, self.cues)
        elif a.simulate:
            src = ReplaySource(self.q, self.stop, Path(a.simulate), a.replay_session)
        else:
            src = ThinkGearSource(self.q, self.stop)
        src.start()
        threading.Thread(target=self._consume, daemon=True).start()
        meta = {"participant": a.participant, "block": a.block, "run": a.run, "gate": a.gate,
                "started": datetime.now().isoformat(timespec="seconds"), "simulate": a.simulate,
                "schedule": self.schedule, "fixation_s": FIXATION_S,
                "cue_s": CUE_S if a.block == "detection" else TASK_CUE_S,
                "iti_range_s": ITI_RANGE if a.block == "detection" else TASK_ITI,
                "warmup_s": a.warmup, "python": platform.python_version(), "platform": platform.platform(),
                "model_dir": str(a.model_dir), "model_loaded": model is not None, "com": a.com}
        (self.out / "meta.json").write_text(json.dumps(meta, indent=2))

    def _consume(self):
        last_tick = 0.0
        while not self.stop.is_set():
            try:
                kind, payload = self.q.get(timeout=0.01)
                if kind == "error":
                    print("\n!!", payload, flush=True)
                    self.error = payload
                    self.stop.set()
                    return
                self.ctl.on_packet(*payload)
            except queue.Empty:
                pass
            if now() - last_tick >= 0.01:
                self.ctl.tick()
                last_tick = now()

    # trial timeline, shared by GUI and console -----------------------------
    def timeline(self):
        """Yields (what, payload, duration_s)."""
        rng = random.Random(7)
        cue_s = CUE_S if self.args.block == "detection" else TASK_CUE_S
        iti = ITI_RANGE if self.args.block == "detection" else TASK_ITI
        yield ("text", "RELAX\nsettling the headset", self.args.warmup)
        for i, cue in enumerate(self.schedule, 1):
            yield ("fixation", (i, cue), FIXATION_S)
            yield ("cue", (i, cue), cue_s)
            yield ("blank", (i, cue), rng.uniform(*iti))
        yield ("text", "DONE\nthank you", 2.0)

    def mark(self, what, payload, t):
        if what == "fixation":
            self._fix_t = t
        elif what == "cue":
            i, cue = payload
            self._onset = t
            self.cues.set((i, cue, t))
        elif what == "blank":
            i, cue = payload
            self.cues.set(None)
            self.logs["cues"].row(i, cue, EXPECTED.get(cue, "none"), f"{self._fix_t:.4f}",
                                  f"{self._onset:.4f}", f"{t:.4f}")

    def run_console(self):
        for what, payload, dur in self.timeline():
            if self.stop.is_set():
                break
            t = now()
            self.mark(what, payload, t)
            if what == "cue":
                print(f"[{t:7.2f}] trial {payload[0]:3d}/{len(self.schedule)}  {payload[1]:10s}  "
                      f"last action: {self.ctl.last_action}", flush=True)
            end = t + dur
            while now() < end and not self.stop.is_set():
                time.sleep(0.01)

    def run_gui(self):
        import tkinter as tk
        root = tk.Tk()
        root.title("MindAssist session")
        root.configure(bg="black")
        root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
        root.attributes("-fullscreen", True)
        big = tk.Label(root, text="Press SPACE to start\n(Esc to stop at any time)", fg="white", bg="black",
                       font=("Arial", 64, "bold"), justify="center")
        big.pack(expand=True)
        info = tk.Label(root, text="", fg="#777777", bg="black", font=("Arial", 14))
        info.pack(side="bottom", pady=10)
        steps = iter(self.timeline())
        state = {"started": False, "end": 0.0}

        def finish(*_):
            self.stop.set()
            root.after(200, root.destroy)

        def step():
            if self.stop.is_set():
                return finish()
            if now() < state["end"]:
                sig = self._signal_text()
                info.config(text=f"{self.args.participant} | {self.args.block} | gate {self.args.gate} | {sig} | "
                                 f"last action: {self.ctl.last_action}")
                root.after(10, step)
                return
            try:
                what, payload, dur = next(steps)
            except StopIteration:
                return finish()
            if what == "fixation":
                big.config(text="+", fg="white")
            elif what == "cue":
                big.config(text=CUE_TEXT[payload[1]], fg="#ffd34d")
            elif what == "blank":
                big.config(text="")
            else:
                big.config(text=payload, fg="white")
            root.update_idletasks()
            t = now()                    # logged after the screen has been updated
            self.mark(what, payload, t)
            state["end"] = t + dur
            root.after(5, step)

        def start(*_):
            if not state["started"]:
                state["started"] = True
                step()

        root.bind("<space>", start)
        root.bind("<Escape>", finish)
        if self.args.autostart:
            root.after(500, start)
        root.mainloop()

    def _signal_text(self):
        try:
            with open(self.out / "packets.csv", "rb") as f:
                f.seek(max(0, os.path.getsize(self.out / "packets.csv") - 400))
                lines = f.read().decode(errors="ignore").strip().splitlines()
            vals = [l.split(",")[1] for l in lines[1:] if l.split(",")[1] not in ("",)]
            return f"signal {vals[-1]} (0 = good, 200 = no contact)" if vals else "signal ?"
        except Exception:
            return "signal ?"

    def close(self):
        self.stop.set()
        time.sleep(0.3)
        self.esp.close()
        for l in self.logs.values():
            l.close()
        print(f"\nsaved to {self.out}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--participant", required=True, help="a code such as P01 (keep a private list of who is who)")
    ap.add_argument("--block", choices=["detection", "task"], required=True)
    ap.add_argument("--run", type=int, default=1, help="detection block run number (1 or 2)")
    ap.add_argument("--gate", choices=["corrected", "deployed", "off"], default="corrected",
                    help="which gate drives the servos (all gates are logged regardless)")
    ap.add_argument("--com", default="COM4", help="ESP32 serial port, or 'none'")
    ap.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    ap.add_argument("--out", default=str(HERE / "sessions"))
    ap.add_argument("--trials", type=int, default=None, help="cut the schedule (testing only)")
    ap.add_argument("--warmup", type=float, default=WARMUP_S)
    ap.add_argument("--no-gui", action="store_true")
    ap.add_argument("--autostart", action="store_true", help="start without waiting for SPACE (testing)")
    ap.add_argument("--no-model", action="store_true")
    ap.add_argument("--simulate", default=None, help="'synthetic' or a path to all_data_labeled_final6.csv")
    ap.add_argument("--replay-session", type=int, default=3)
    args = ap.parse_args()

    s = Session(args)
    s.setup()
    print(f"{len(s.schedule)} trials -> {s.out}", flush=True)
    try:
        s.run_console() if args.no_gui else s.run_gui()
    except KeyboardInterrupt:
        pass
    finally:
        s.close()


if __name__ == "__main__":
    main()
