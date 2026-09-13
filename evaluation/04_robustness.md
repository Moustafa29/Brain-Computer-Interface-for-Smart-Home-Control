# Robustness of the threshold rule vs the trained model

Held-out sessions from fold 1 of the session-grouped split: 9 sessions, 738 windows.
Corruption is applied to raw samples before windowing, so both decision paths
see the same degraded stream. Labels stay clean. Delta is the change in accuracy
against the clean condition, in points. The fuzzy column uses a gate of 0.60.

## Clean baseline

| path | accuracy | macro F1 |
| --- | --- | --- |
| rule | 0.921 | 0.914 |
| model | 0.867 | 0.847 |
| model + fuzzy | 0.867 | 0.847 |

## Additive Gaussian noise

| condition | rule acc | model acc | model+fuzzy acc | rule delta | model delta | model+fuzzy delta |
| --- | --- | --- | --- | --- | --- | --- |
| SNR 40 dB | 0.921 | 0.797 | 0.799 | +0.0 | -7.0 | -6.8 |
| SNR 20 dB | 0.900 | 0.805 | 0.806 | -2.2 | -6.2 | -6.1 |
| SNR 10 dB | 0.862 | 0.770 | 0.770 | -6.0 | -9.8 | -9.8 |
| SNR 5 dB | 0.809 | 0.657 | 0.659 | -11.2 | -21.0 | -20.9 |
| SNR 0 dB | 0.709 | 0.606 | 0.606 | -21.3 | -26.2 | -26.2 |

## Random packet drops

| condition | rule acc | model acc | model+fuzzy acc | rule delta | model delta | model+fuzzy delta |
| --- | --- | --- | --- | --- | --- | --- |
| 0% dropped | 0.921 | 0.867 | 0.867 | +0.0 | +0.0 | +0.0 |
| 5% dropped | 0.886 | 0.837 | 0.837 | -3.5 | -3.0 | -3.0 |
| 10% dropped | 0.856 | 0.798 | 0.798 | -6.5 | -6.9 | -6.9 |
| 20% dropped | 0.813 | 0.752 | 0.752 | -10.8 | -11.5 | -11.5 |
| 40% dropped | 0.675 | 0.611 | 0.614 | -24.7 | -25.6 | -25.3 |

## Macro F1, same conditions

| condition | rule | model | model+fuzzy |
| --- | --- | --- | --- |
| clean | 0.914 | 0.847 | 0.847 |
| SNR 40 dB | 0.914 | 0.784 | 0.786 |
| SNR 20 dB | 0.892 | 0.789 | 0.791 |
| SNR 10 dB | 0.854 | 0.742 | 0.742 |
| SNR 5 dB | 0.801 | 0.596 | 0.597 |
| SNR 0 dB | 0.703 | 0.496 | 0.496 |
| 0% dropped | 0.914 | 0.847 | 0.847 |
| 5% dropped | 0.876 | 0.816 | 0.816 |
| 10% dropped | 0.845 | 0.775 | 0.775 |
| 20% dropped | 0.800 | 0.729 | 0.729 |
| 40% dropped | 0.664 | 0.604 | 0.607 |

## Fuzzy gate sensitivity

Accuracy when the model decision is downgraded to no blink below each gate.
A gate of 0.50 only reaches windows whose peak strength is below about 57 -- ones
the rule already calls no blink. Because strength 60 scores 0.56, no gate below that
can reject a genuine event, which is why the columns barely move.

| gate | clean | SNR 10 dB | 20% dropped | windows rejected (clean) |
| --- | --- | --- | --- | --- |
| 0.50 | 0.867 | 0.770 | 0.752 | 63 |
| 0.60 | 0.867 | 0.770 | 0.752 | 76 |
| 0.65 | 0.867 | 0.770 | 0.752 | 80 |
| 0.70 | 0.860 | 0.776 | 0.747 | 130 |
