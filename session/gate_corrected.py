"""Copy of blink_control/fuzzy_logic.py: the corrected gate."""
"""Blink-confidence gate (corrected; the original is kept in fuzzy_logic_original.py).

Same structure as the deployed gate: one input (blink strength 0-255), three
rules (weak -> low, medium -> mid, strong -> high), Mamdani min-max inference,
centroid defuzzification. Only the membership functions change:

  input   weak    trimf  [0, 0, 60]
          medium  trimf  [0, 60, 170]
          strong  trapmf [60, 170, 255, 255]
  output  low     trimf  [0.0, 0.2, 0.4]
          mid     trimf  [0.4, 0.6, 0.8]
          high    trimf  [0.8, 1.0, 1.2]

The input sets form a partition of unity anchored at the labelling threshold,
and the output sets do not overlap, so:
  - confidence(60) = 0.60, the controller's gate value: every event the
    labelling rule accepts passes the default gate
  - confidence never decreases as blink strength increases
  - confidence(170 and above) = 1.00

The deployed version scored 0.56 at strength 60 (so blinks of strength 60-62
were labelled genuine but rejected by the gate) and had six places where a
stronger blink scored lower than a weaker one.
"""
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl


class BlinkConfidenceSystem:
    def __init__(self):
        self.sim = self._build_system()

    def _build_system(self):
        strength = ctrl.Antecedent(np.arange(0, 256, 1), "blink_strength")
        confidence = ctrl.Consequent(np.arange(0, 1.2001, 0.001), "confidence")

        strength["weak"] = fuzz.trimf(strength.universe, [0, 0, 60])
        strength["medium"] = fuzz.trimf(strength.universe, [0, 60, 170])
        strength["strong"] = fuzz.trapmf(strength.universe, [60, 170, 255, 255])

        confidence["low"] = fuzz.trimf(confidence.universe, [0.0, 0.2, 0.4])
        confidence["mid"] = fuzz.trimf(confidence.universe, [0.4, 0.6, 0.8])
        confidence["high"] = fuzz.trimf(confidence.universe, [0.8, 1.0, 1.2])

        rules = [
            ctrl.Rule(strength["weak"], confidence["low"]),
            ctrl.Rule(strength["medium"], confidence["mid"]),
            ctrl.Rule(strength["strong"], confidence["high"]),
        ]
        return ctrl.ControlSystemSimulation(ctrl.ControlSystem(rules))

    def calculate_confidence(self, blink_strength):
        """Fuzzy confidence in [0.2, 1.0], rounded to 2 decimals."""
        self.sim.reset()
        self.sim.input["blink_strength"] = float(np.clip(blink_strength, 0, 255))
        self.sim.compute()
        return round(float(self.sim.output["confidence"]), 2)
