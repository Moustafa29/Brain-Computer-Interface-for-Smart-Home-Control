"""R1-6: specify, fix and characterise the blink fuzzy-confidence gate.

1. Characterise the deployed gate (blink_control/fuzzy_logic_original.py) exactly:
   membership functions, rule base, defuzzification, full 0-255 curve,
   monotonicity violations, confidence at the labelling threshold.
2. Define a corrected Mamdani gate with the same three rules and the same
   min-max inference and centroid defuzzification, but with input memberships
   that form a partition of unity anchored at the labelling threshold (60)
   and non-overlapping output sets, so that:
     - confidence(60) = 0.60, exactly the deployed gate value
     - confidence is non-decreasing in blink strength
3. Sweep both gates on the recorded data (rule detector + gate on event
   strength, scored against blinkType, as in evaluation/phase0 0.4).

usage: python r1_6_gate.py <repo_dir> <out_dir>
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import skfuzzy as fuzz
from skfuzzy import control as ctrl

REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(REPO / "blink_control"))
from fuzzy_logic_original import BlinkConfidenceSystem  # the gate as originally deployed


class CorrectedBlinkConfidence:
    """Same structure as the deployed gate: one input, three rules
    (weak->low, medium->mid, strong->high), Mamdani min-max, centroid."""

    SPEC = {
        "input_universe": [0, 255],
        "input_mf": {"weak": ["trimf", [0, 0, 60]],
                     "medium": ["trimf", [0, 60, 170]],
                     "strong": ["trapmf", [60, 170, 255, 255]]},
        "output_universe": [0.0, 1.2],
        "output_mf": {"low": ["trimf", [0.0, 0.2, 0.4]],
                      "mid": ["trimf", [0.4, 0.6, 0.8]],
                      "high": ["trimf", [0.8, 1.0, 1.2]]},
        "rules": ["weak -> low", "medium -> mid", "strong -> high"],
        "inference": "Mamdani, min implication, max aggregation",
        "defuzzification": "centroid",
    }

    def __init__(self):
        s = ctrl.Antecedent(np.arange(0, 256, 1), "blink_strength")
        c = ctrl.Consequent(np.arange(0, 1.2001, 0.001), "confidence")
        s["weak"] = fuzz.trimf(s.universe, [0, 0, 60])
        s["medium"] = fuzz.trimf(s.universe, [0, 60, 170])
        s["strong"] = fuzz.trapmf(s.universe, [60, 170, 255, 255])
        c["low"] = fuzz.trimf(c.universe, [0.0, 0.2, 0.4])
        c["mid"] = fuzz.trimf(c.universe, [0.4, 0.6, 0.8])
        c["high"] = fuzz.trimf(c.universe, [0.8, 1.0, 1.2])
        rules = [ctrl.Rule(s["weak"], c["low"]), ctrl.Rule(s["medium"], c["mid"]),
                 ctrl.Rule(s["strong"], c["high"])]
        self.sim = ctrl.ControlSystemSimulation(ctrl.ControlSystem(rules))

    def calculate_confidence(self, blink_strength):
        self.sim.reset()
        self.sim.input["blink_strength"] = float(np.clip(blink_strength, 0, 255))
        self.sim.compute()
        return round(float(self.sim.output["confidence"]), 2)


def curve(gate):
    return np.array([gate.calculate_confidence(s) for s in range(256)])


def violations(c):
    return [(i, float(c[i - 1]), float(c[i])) for i in range(1, len(c)) if c[i] < c[i - 1]]


def rule_rows(df, thr=60, interval=1.0):
    out = np.zeros(len(df), dtype=int); last_t, last_s = None, None
    for i, (s, t, sid) in enumerate(zip(df.blinkStrength.values, df.time.values, df.session_id.values)):
        if sid != last_s:
            last_t, last_s = None, sid
        if s >= thr:
            out[i] = 2 if (last_t is not None and 0 <= t - last_t <= interval) else 1
            last_t = t
    return out


def main():
    old, new = BlinkConfidenceSystem(), CorrectedBlinkConfidence()
    c_old, c_new = curve(old), curve(new)
    v_old, v_new = violations(c_old), violations(c_new)

    df = pd.read_csv(REPO / "data" / "all_data_labeled_final6.csv")
    y = df.blinkType.values
    det = rule_rows(df)
    strength = df.blinkStrength.clip(0, 255).astype(int).values
    ev = det > 0
    ev_strength = strength[ev]

    sweep = {}
    for name, c in (("deployed", c_old), ("corrected", c_new)):
        rows = []
        for g in (None, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90):
            p = det.copy()
            if g is not None:
                p[ev & (c[strength] < g)] = 0
            rows.append({"gate": g, "accuracy_vs_blinkType": float(np.mean(p == y)),
                         "events_rejected": int(np.sum(ev & (p == 0))),
                         "strength_threshold_implied": (int(np.argmax(c >= g)) if g is not None and np.any(c >= g) else None)})
        sweep[name] = rows

    pts = [0, 40, 55, 58, 59, 60, 61, 62, 63, 65, 70, 80, 90, 100, 110, 120, 140, 170, 200, 255]
    res = {
        "deployed_spec": {
            "input_mf": {"weak": ["trimf", [0, 0, 69]], "ramp": ["trimf", [50, 70, 170]], "strong": ["trimf", [120, 170, 200]]},
            "output_mf": {"low": ["trimf", [0, 0, 0.5]], "mid": ["trimf", [0.4, 0.7, 0.9]], "high": ["trimf", [0.7, 1.0, 1.0]]},
            "rules": ["weak -> low", "ramp -> mid", "strong -> high"],
            "inference": "Mamdani (scikit-fuzzy defaults: min implication, max aggregation)",
            "defuzzification": "centroid", "calibration": "none; breakpoints set by hand",
        },
        "corrected_spec": CorrectedBlinkConfidence.SPEC,
        "curve_points": {str(s): {"deployed": float(c_old[s]), "corrected": float(c_new[s])} for s in pts},
        "confidence_at_60": {"deployed": float(c_old[60]), "corrected": float(c_new[60])},
        "lowest_strength_passing_0.60": {"deployed": int(np.argmax(c_old >= 0.6)), "corrected": int(np.argmax(c_new >= 0.6))},
        "monotonicity_violations": {"deployed": len(v_old), "corrected": len(v_new),
                                    "deployed_examples": v_old[:10]},
        "event_strength_percentiles": {str(q): float(np.percentile(ev_strength, q)) for q in (1, 5, 10, 25, 50, 75, 90, 95, 99)},
        "events_total": int(ev.sum()),
        "events_with_strength_60_62": int(np.sum((ev_strength >= 60) & (ev_strength <= 62))),
        "sweep": sweep,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "r1_6_gate.json").write_text(json.dumps(res, indent=2))

    print("strength :", " ".join(f"{s:>5d}" for s in pts))
    print("deployed :", " ".join(f"{c_old[s]:5.2f}" for s in pts))
    print("corrected:", " ".join(f"{c_new[s]:5.2f}" for s in pts))
    print(f"\nmonotonicity violations: deployed {len(v_old)}, corrected {len(v_new)}")
    print("deployed drops (strength, before, after):", v_old[:8])
    print(f"lowest strength passing gate 0.60: deployed {res['lowest_strength_passing_0.60']['deployed']}, "
          f"corrected {res['lowest_strength_passing_0.60']['corrected']}")
    print(f"events in recordings: {ev.sum()}, of which strength 60-62 (wrongly rejected by deployed gate): "
          f"{res['events_with_strength_60_62']}")
    print("event strength percentiles:", {k: round(v) for k, v in res["event_strength_percentiles"].items()})
    print("\ngate   | deployed acc  rejected thr | corrected acc  rejected thr")
    for a, b in zip(sweep["deployed"], sweep["corrected"]):
        g = "none " if a["gate"] is None else f"{a['gate']:.2f} "
        print(f"{g}  | {100*a['accuracy_vs_blinkType']:6.2f}%  {a['events_rejected']:6d} {str(a['strength_threshold_implied']):>4s} "
              f"| {100*b['accuracy_vs_blinkType']:6.2f}%  {b['events_rejected']:6d} {str(b['strength_threshold_implied']):>4s}")


if __name__ == "__main__":
    main()
