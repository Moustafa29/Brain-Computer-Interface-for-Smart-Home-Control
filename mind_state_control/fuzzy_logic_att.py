import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

# +

class MindStateControlSystem:
    """Fuzzy system for attention/meditation control with conflict resolution"""

    def __init__(self):
        self.attention_sim = self._build_attention_system()
        self.meditation_sim = self._build_meditation_system()
        self.conflict_resolver = self._build_conflict_system()

    def _build_attention_system(self):
        attention = ctrl.Antecedent(np.arange(0, 101, 1), 'attention')
        effect = ctrl.Consequent(np.arange(-1, 1.01, 0.01), 'effect')

        # <34 = Low, <67 = Medium, else High
        attention['low'] = fuzz.trimf(attention.universe, [0, 0, 34])
        attention['medium'] = fuzz.trimf(attention.universe, [30, 50, 67])
        attention['high'] = fuzz.trimf(attention.universe, [60, 100, 100])

        effect['negative'] = fuzz.trimf(effect.universe, [-1, -1, 0])
        effect['neutral'] = fuzz.trimf(effect.universe, [-0.3, 0, 0.3])
        effect['positive'] = fuzz.trimf(effect.universe, [0, 1, 1])

        rules = [
            ctrl.Rule(attention['low'], effect['neutral']),
            ctrl.Rule(attention['medium'], effect['positive']),
            ctrl.Rule(attention['high'], effect['positive']),
        ]
        return ctrl.ControlSystemSimulation(ctrl.ControlSystem(rules))

    def _build_meditation_system(self):
        meditation = ctrl.Antecedent(np.arange(0, 101, 1), 'meditation')
        effect = ctrl.Consequent(np.arange(-1, 1.01, 0.01), 'effect')

        # <34 = Low, <67 = Medium, else High
        meditation['low'] = fuzz.trimf(meditation.universe, [0, 0, 34])
        meditation['medium'] = fuzz.trimf(meditation.universe, [30, 50, 67])
        meditation['high'] = fuzz.trimf(meditation.universe, [60, 100, 100])

        effect['negative'] = fuzz.trimf(effect.universe, [-1, -1, 0])
        effect['neutral'] = fuzz.trimf(effect.universe, [-0.3, 0, 0.3])
        effect['positive'] = fuzz.trimf(effect.universe, [0, 1, 1])

        rules = [
            ctrl.Rule(meditation['low'], effect['positive']),
            ctrl.Rule(meditation['medium'], effect['neutral']),
            ctrl.Rule(meditation['high'], effect['negative']),
        ]
        return ctrl.ControlSystemSimulation(ctrl.ControlSystem(rules))

    def _build_conflict_system(self):
        att_effect = ctrl.Antecedent(np.arange(-1, 1.01, 0.01), 'att_effect')
        med_effect = ctrl.Antecedent(np.arange(-1, 1.01, 0.01), 'med_effect')
        net_effect = ctrl.Consequent(np.arange(-2, 2.01, 0.01), 'net_effect')

        for var in [att_effect, med_effect]:
            var['neg'] = fuzz.trimf(var.universe, [-1, -1, 0])
            var['neutral'] = fuzz.trimf(var.universe, [-0.5, 0, 0.5])
            var['pos'] = fuzz.trimf(var.universe, [0, 1, 1])

        net_effect['strong_neg'] = fuzz.trimf(net_effect.universe, [-2, -2, -1])
        net_effect['neg'] = fuzz.trimf(net_effect.universe, [-1.5, -1, -0.5])
        net_effect['neutral'] = fuzz.trimf(net_effect.universe, [-0.7, 0, 0.7])
        net_effect['pos'] = fuzz.trimf(net_effect.universe, [0.5, 1, 1.5])
        net_effect['strong_pos'] = fuzz.trimf(net_effect.universe, [1, 2, 2])

        rules = [
            ctrl.Rule(att_effect['pos'] & med_effect['neg'], net_effect['strong_pos']),
            ctrl.Rule(att_effect['pos'] & med_effect['neutral'], net_effect['pos']),
            ctrl.Rule(att_effect['neutral'] & med_effect['neg'], net_effect['pos']),
            ctrl.Rule(att_effect['pos'] & med_effect['pos'], net_effect['neutral']),
            ctrl.Rule(att_effect['neg'] & med_effect['neg'], net_effect['neutral']),
            ctrl.Rule(att_effect['neg'] & med_effect['pos'], net_effect['strong_neg']),
            ctrl.Rule(att_effect['neutral'] & med_effect['pos'], net_effect['neg']),
            ctrl.Rule(att_effect['neg'] & med_effect['neutral'], net_effect['neg']),
        ]
        return ctrl.ControlSystemSimulation(ctrl.ControlSystem(rules))

    def calculate_effects(self, attention, meditation):
        """Calculate net effect considering potential conflicts"""
        self.attention_sim.reset()
        self.attention_sim.input['attention'] = attention
        self.attention_sim.compute()
        att_effect = self.attention_sim.output['effect']

        self.meditation_sim.reset()
        self.meditation_sim.input['meditation'] = meditation
        self.meditation_sim.compute()
        med_effect = self.meditation_sim.output['effect']

        self.conflict_resolver.reset()
        self.conflict_resolver.input['att_effect'] = att_effect
        self.conflict_resolver.input['med_effect'] = med_effect
        self.conflict_resolver.compute()

        return {
            'attention_effect': round(float(att_effect), 3),
            'meditation_effect': round(float(med_effect), 3),
            'net_effect': round(float(self.conflict_resolver.output['net_effect']), 3)
        }
# -


