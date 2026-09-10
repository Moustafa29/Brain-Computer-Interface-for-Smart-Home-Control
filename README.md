# Brain-Computer Interface for Smart Home Control

A real-time brain-computer interface that controls doors, windows and a fan
from single-channel EEG. A NeuroSky MindWave Mobile 2 headset streams band
powers, eye-blink strength and its own attention and meditation readings to a
PC, which sends commands over serial to an ESP32 that drives the servos and
fan. Two CNN-BiLSTM models were trained on recordings from the headset: one
classifies blink type, the other attention and relaxation level.

It is built for people with motor impairments, paralysis or neuromuscular
conditions — control that needs no hands.

Graduation project, Faculty of Computer and Data Science, Alexandria University,
2025.

---

## Results

| task                                       | classes               | test accuracy | macro F1 |
| ------------------------------------------ | --------------------- | ------------- | -------- |
| blink type                                 | none / single / double | **92%**      | —        |
| attention level                            | low / medium / high   | **92%**       | 0.91     |
| relaxation level                           | low / medium / high   | **90%**       | 0.85     |

The blink result — 92% across 36 recording sessions — is reported in the
project presentation. `blink_control/Blink_model.ipynb` is committed without its
outputs, so that figure is not reproduced in this repository. The attention and
relaxation figures are the saved outputs of
`mind_state_control/att_rel_model.ipynb`, on 591 test windows.

All three are within-session results on a random window-level split. Read the
evaluation protocol below before comparing them with published EEG work.

---

## Evaluation protocol

### Data

Both datasets come from the NeuroSky MindWave Mobile 2: one dry electrode on
the forehead, a reference clip on the ear. Each sample carries eight band
powers (delta through high gamma), the headset's eSense attention and
meditation values, and its blink-strength reading.

| dataset                             | samples | sessions       | labels                                             |
| ----------------------------------- | ------- | -------------- | -------------------------------------------------- |
| `data/all_data_labeled_final6.csv`  | 13,229  | 58 session IDs | blink type: 4,518 none, 6,030 single, 2,681 double |
| `data/all_data_labeled_att_Rel.csv` | 5,929   | not recorded   | attention and relaxation level                     |

The project presentation describes 36 sessions of about 120 seconds each. The
committed blink dataset contains 58 session IDs, with a median length of 119
seconds and 215 minutes of recording in total. Every row of the mind-state
dataset also appears in the blink dataset, so the two are drawn from the same
recordings.

**Number of subjects: not recorded.** Neither dataset has a subject or
participant column, and the presentation describes participants only as
varied in gender and age, without a count.

### Labels

Blink windows take the label of their last sample.

Attention and relaxation labels are bands of the headset's own eSense readings:
low is 0–30, medium 34–66 and high 67–100, applied to `attention` and to
`meditation` respectively. The class ranges do not overlap, so the labels are
exact thresholds. These models therefore learn to reproduce NeuroSky's
attention and meditation meters from band powers; there is no independent
ground truth for mental state, such as a task condition.

### Splits

| model       | input windows              | overlap | split                                         |
| ----------- | -------------------------- | ------- | --------------------------------------------- |
| blink       | 20 samples, step 3; 4,049 windows | 85% | random, stratified by class: 70% train / 15% validation / 15% test |
| mind state  | 20 samples, step 2         | 90%     | random, stratified by attention: 80% train / 20% test |

Blink windows never span two sessions. The mind-state dataset has no session
column, so its windows cannot respect session boundaries.

### Within-subject or cross-subject

**Within-session, and therefore within-subject. No cross-subject or
cross-session validation exists in this code.**

Both splits are random at the level of windows, not grouped by session or
subject. Every test window comes from a session that also contributed training
windows. Because consecutive windows overlap by 85% and 90%, most test windows
share the majority of their samples with windows in the training set.

Two further details affect how the numbers read:

- The blink feature scalers are fitted on all windows before the split.
- The mind-state model uses its test set as its validation set, so early
  stopping and the learning-rate schedule both see test data.

The reported accuracies measure how well the models fit recordings from people
and sessions they have already seen. Performance on a new user — the case an
assistive device actually faces — has not been measured. A session-grouped or
leave-one-subject-out split would answer that, and is the most important piece
of work this project lacks.

---

## How it works

```
NeuroSky headset ─▶ ThinkGear Connector ─▶ Python control ─▶ USB serial ─▶ ESP32 ─▶ servos, fan
                    (Telnet :13854)
```

### The live control path

**Blinks move the door and window** (`blink_control/main.py`). A blink
registers when the headset's blink-strength reading crosses a threshold. A
second blink inside a short interval makes it a double: a single blink opens
the door servo to 90°, a double opens the window.

**Mental state sets the fan speed** (`mind_state_control/main_att.py`). The
headset's attention and meditation readings are smoothed over 15 samples and
passed through a scikit-fuzzy controller, which weighs the two against each
other and steps the fan's PWM up or down.

### The trained models

Both models run inside the live loop, but **their predictions are logged, not
used to choose actions**. Device commands come from the headset's own blink
detection, the interval rule and its eSense readings, as described above.
Wiring the classifiers into the decision is the step that would make them part
of the control system rather than alongside it.

**Blink classifier** (`blink_control/`) labels each 20-sample window as no
blink, single or double. It has two branches: a CNN-BiLSTM over the window's 12
input columns, and a dense branch over 30 engineered statistics — blink-strength
summaries, blink intervals and per-band means and deviations. It is trained with
focal loss to handle the rarer double blinks. A fuzzy system also scores blink
confidence from blink strength; that score is logged too.

**Mind-state classifier** (`mind_state_control/`) predicts attention and
relaxation level together, with a CNN-BiLSTM and two softmax heads over 66
engineered features: band powers, band ratios such as theta/beta and
alpha/beta, rolling statistics, deltas and normalised power.

**ESP32 firmware** (`arduino/final_esp32.ino`) receives commands over serial
and drives the door and window servos and the PWM fan. It also runs a keypad
door lock, gas and flame alarms with a buzzer, and temperature and humidity
readings on an LCD, independently of the EEG path.

---

## Mobile app

`mobile_app/smart_home_app-main/` is a Flutter interface prototype, not yet
connected to the hardware. It has sign-in, room navigation, device toggles and
an environment panel, but:

- the Firebase packages are declared in `pubspec.yaml`, and Firebase is never
  initialised or called;
- sign-in is a local stub that accepts a fixed demo account;
- temperature, humidity and hazard readings are randomly generated;
- the ESP32 firmware has no Wi-Fi or network code, so nothing links the app to
  the devices.

All device control today runs from the PC over USB serial.

---

## Running

Requires the NeuroSky headset paired and the ThinkGear Connector running on
`localhost:13854`, with the ESP32 on a serial port — `COM4` is hard-coded in
both control scripts.

```bash
pip install -r requirements.txt
```

Then run one controller from its own directory — each loads its model and
preprocessing files by relative path:

```bash
cd blink_control
python main.py        # blinks control the door and window
```

```bash
cd mind_state_control
python main_att.py    # attention and meditation control the fan
```

Use Python 3.12 or earlier: the control scripts use `telnetlib`, which was
removed in Python 3.13.

The notebooks retrain both models from `data/`. They read their CSV from the
working directory, so run them with the dataset alongside.

---

## Repository layout

```
blink_control/
  Blink_model.ipynb              training and evaluation (committed without outputs)
  main.py                        real-time blink control
  fuzzy_logic.py                 blink confidence rules
  best_eeg_cnn_bilstm_focal.h5   trained blink model
  scaler_feats.pkl, scaler_seq.pkl, windowed_feature_cols.json,
  preprocessing_meta.json        preprocessing saved for inference
mind_state_control/
  att_rel_model.ipynb            training and evaluation, with outputs
  main_att.py                    real-time fan control
  fuzzy_logic_att.py             attention and relaxation to fan speed
  best_eeg_cnn_bilstm.h5         trained dual-output model
  feature_cols.json, le_att_classes.npy, le_rel_classes.npy
data/
  all_data_labeled_final6.csv    blink dataset
  all_data_labeled_att_Rel.csv   attention and relaxation dataset
arduino/
  final_esp32.ino                ESP32 firmware
  arduino.ino                    Arduino Uno LED test sketch
mobile_app/smart_home_app-main/  Flutter interface prototype
demo/
  BCI_For_SmartHome_Control_Presentation.pptx
  BCI for Smart Home control Demo.mp4
requirements.txt                 Python dependencies for the control scripts
LICENSE                          educational and research use
```

The graduation presentation and a demo video are in `demo/`:
[presentation](demo/BCI_For_SmartHome_Control_Presentation.pptx),
[demo video](demo/BCI%20for%20Smart%20Home%20control%20Demo.mp4).

---

## Credits

Developed by Moustafa Ahmed and team as a graduation project, Faculty of
Computer and Data Science, Alexandria University, 2025.

## License

Educational and non-commercial research use only; see [LICENSE](LICENSE).
Clinical or commercial use, including adaptation, requires written permission
from the authors. This is not a medical device.
