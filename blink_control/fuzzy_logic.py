# +
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

class BlinkConfidenceSystem:
    """
    Fuzzy confidence based on blink strength, scaled so:
    - conf = 0.7 at strength 70,
    - conf = 1.0 at strength 170+,
    - linearly between.
    """

    def __init__(self):
        self.sim = self._build_system()

    def _build_system(self):
        strength = ctrl.Antecedent(np.arange(0, 256, 1), 'blink_strength')
        confidence = ctrl.Consequent(np.arange(0, 1.01, 0.01), 'confidence')

        # Custom: confidence = 0.7 at 70, ramps to 1.0 at 170
        confidence['low'] = fuzz.trimf(confidence.universe, [0, 0, 0.5])
        confidence['mid'] = fuzz.trimf(confidence.universe, [0.4, 0.7, 0.9])
        confidence['high'] = fuzz.trimf(confidence.universe, [0.7, 1.0, 1.0])

        strength['weak'] = fuzz.trimf(strength.universe, [0, 0, 69])
        strength['ramp'] = fuzz.trimf(strength.universe, [50, 70, 170])
        strength['strong'] = fuzz.trimf(strength.universe, [120, 170, 200])

        rules = [
            ctrl.Rule(strength['weak'], confidence['low']),
            ctrl.Rule(strength['ramp'], confidence['mid']),
            ctrl.Rule(strength['strong'], confidence['high']),
        ]
        return ctrl.ControlSystemSimulation(ctrl.ControlSystem(rules))

    def calculate_confidence(self, blink_strength):
        """
        Fuzzy confidence: 0.7 at strength 70, linearly to 1.0 at 170, clipped to [0,1].
        Returns nearest 2 decimal.
        """
        try:
            self.sim.reset()
            self.sim.input['blink_strength'] = blink_strength
            self.sim.compute()
            return round(float(self.sim.output['confidence']), 2)
        except Exception:
            # Fallback: linear, 0.7 at 70 to 1.0 at 170+
            val = 0.7 + 0.3 * ((blink_strength - 70) / 100)
            return round(min(1.0, max(0.0, val)), 2)

# -


