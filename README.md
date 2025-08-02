# 🧠 BCI-Based Smart Home Control System

A real-time Brain-Computer Interface (BCI) system that enables users to control smart home devices using brainwave signals from the NeuroSky MindWave Mobile 2 headset.

> Designed to support individuals with **motor impairments**, **paralysis**, or **neuromuscular disabilities**, this system empowers them to control doors, windows, and fans using only eye blinks and mental focus — hands-free.

---

## 🎯 Objective

To develop an affordable, non-invasive smart home solution that interprets **EEG signals** — such as eye blinks and mental states — and translates them into physical control of home devices, improving independence for people with limited mobility.

---

## 🧠 System Architecture

```plaintext
NeuroSky EEG ➜ Deep Learning + Fuzzy Logic ➜ Hardware Control (Servo, Fan)
````

* Real-time EEG via Telnet
* CNN-BiLSTM model classifies blinks and mental state
* Fuzzy logic enhances reliability of predictions
* Arduino Uno / ESP32 receives control signals and actuates devices

---

## ⚙️ Technologies Used

* **EEG Input**: NeuroSky MindWave Mobile 2
* **Deep Learning**: TensorFlow (CNN-BiLSTM models)
* **Fuzzy Logic**: scikit-fuzzy for confidence & control smoothing
* **Hardware**: Arduino Uno & ESP32, Servo motors, PWM fan
* **App (WIP)**: Flutter + Firebase Realtime Database (for remote control)

---

## 📁 Project Structure

```plaintext
BCI-Smart-Home-Control/
│
├── requirements.txt              # Python dependencies
│
├── blink_control/                # Eye blink detection system
│   ├── main.py
│   ├── fuzzy_logic.py
│   ├── best_eeg_cnn_bilstm_focal.h5
│   ├── scaler_feats.pkl
│   ├── scaler_seq.pkl
│   ├── windowed_feature_cols.json
│   ├── preprocessing_meta.json
│
├── mind_state_control/           # Attention & meditation system
│   ├── main_att.py
│   ├── fuzzy_logic_att.py
│   ├── best_eeg_cnn_bilstm.h5
│   ├── le_att_classes.npy
│   ├── le_rel_classes.npy
│   ├── feature_cols.json
│
├── data/                         # EEG training datasets
│   ├── all_data_labeled_final6.csv
│   ├── all_data_labeled_att_Rel.csv
│
├── arduino/                      # Microcontroller code
│   ├── arduino.ino               # Arduino Uno version
│   ├── final_esp32.ino           # ESP32 version
│
├── mobile_app/                   # Flutter app (WIP)
│   └── smart_home_app-main/
│
└── demo/                         # Presentation and demo video
    ├── BCI for Smart Home Control Demo.mp4
    └── BCI_For_SmartHome_Control_Presentation.pptx
```

---

## 🖥️ How to Run

### 🔹 Blink-Based Control

```bash
cd blink_control
python main.py
```

### 🔹 Mind-State (Fan) Control

```bash
cd mind_state_control
python main_att.py
```

> ✅ Make sure your **NeuroSky headset** is connected via Telnet (`localhost:13854`)
> ✅ Ensure **Arduino Uno / ESP32** is available on the correct serial port (e.g. `COM4`)

---

## 🧪 Models & Data

| File                           | Description                                  |
| ------------------------------ | -------------------------------------------- |
| `best_eeg_cnn_bilstm_focal.h5` | Blink detection model with focal loss        |
| `best_eeg_cnn_bilstm.h5`       | Dual-output model for attention & relaxation |
| `all_data_labeled_final6.csv`  | Labeled blink training data                  |
| `all_data_labeled_att_Rel.csv` | Attention & meditation training data         |

---

## 📱 Mobile App (In Progress)

A Flutter app is currently being built to provide remote access to the smart home system.

Planned features include:

* Manual control of devices
* Real-time system feedback
* Firebase integration for cloud-based communication

Source: `mobile_app/smart_home_app-main/`

---

## 🎓 Project Presentation

The official graduation slides are available here:
[`BCI_For_SmartHome_Control_Presentation.pptx`](demo/BCI_For_SmartHome_Control_Presentation.pptx)

---

## 🎥 Demo Video

Watch the live demo:
[`BCI for Smart Home Control Demo.mp4`](demo/BCI%20for%20Smart%20Home%20control%20Demo.mp4)
---

## ✅ Requirements

Install dependencies with:

```bash
pip install -r requirements.txt
```

Required packages include:

* `tensorflow`
* `numpy`
* `joblib`
* `scikit-fuzzy`
* `pyserial`

---

## 👥 Credits

Developed by **Moustafa Ahmed** and team
Graduation Project – 2025
**Faculty of Computer and Data Science – Alexandria University**

---

## 📌 License

This project is licensed for **educational and research use** only.
Contact the authors for permission regarding reuse or adaptation in clinical or commercial settings.

```

```
