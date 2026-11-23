# MindAssist revision session: step by step

One person (you), one afternoon. About 50 minutes of recording plus setup and
breaks. Everything is logged automatically; you only follow the screen.

What it answers: R1-2 and R2-1 (cue-based ground truth), R1-5 (real latency),
R1-6 (false activations and missed commands with and without the gate), and
R2-3 (a single-operator task pilot, gate on against gate off).

---

## A. Once, before the day

1. **Get the branch.** Open Command Prompt in `D:\mindassist_work\bci\`:

   ```
   git fetch origin
   git checkout ijies-revision
   ```

   The kit is then in `D:\mindassist_work\bci\session\`, `blink_control\`
   has the fixed `main.py` and corrected gate, and `arduino\final_esp32.ino`
   already has the acknowledgment lines. If git refuses because of local
   changes, stop and tell me; don't force anything.

2. **Python packages.** Open Command Prompt in `D:\mindassist_work\bci\session\`:

   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Upload the firmware.** `arduino\final_esp32.ino` on this branch already
   has the 4 acknowledgment lines (see `ESP32_PATCH.md`). Upload it from the
   Arduino IDE and check that `ACK:DOOR` appears in the Serial Monitor.

4. **Dry run, no hardware at all.** It opens the full-screen cue window with a
   simulated headset. Press SPACE to start, Esc to stop:

   ```
   python mindassist_session.py --participant TEST --block detection --simulate synthetic --com none --trials 10 --warmup 10
   python analyze_session.py sessions\TEST_* --out report_test
   ```

   Open `report_test\report.md`. If you see tables, the software is ready.
   Delete the `sessions\TEST_*` folders afterwards.

5. **Check the COM port** of the ESP32 in Windows Device Manager (Ports). The
   commands below use `COM4`; change it if yours differs.

---

## B. On the day: setup (15 min)

- Quiet room, normal light, sit comfortably about 60 cm from the screen.
- Clean your forehead with an alcohol wipe where the sensor sits. Ear clip on.
- Start the **ThinkGear Connector**, pair the headset.
- Plug in the ESP32. Close the Arduino Serial Monitor if it is open.
- The grey line at the bottom of the cue screen shows the signal:
  **0 = good contact, 200 = no contact.** Do not start a run until it shows 0.
  If it rises during a run, press Esc, fix the headset, and restart that run.

---

## C. The runs (in this order)

Every run starts with 30 s of "RELAX" while the headset settles, then the
trials. Press SPACE to start each run.

| # | Command | Time |
|---|---|---|
| 1 | `python mindassist_session.py --participant P01 --block detection --run 1 --gate corrected --com COM4` | ~6 min |
|   | *break, 2-3 minutes, headset stays on* | |
| 2 | `python mindassist_session.py --participant P01 --block detection --run 2 --gate corrected --com COM4` | ~6 min |
|   | *break* | |
| 3 | `python mindassist_session.py --participant P01 --block task --gate off --com COM4` | ~6 min |
| 4 | `python mindassist_session.py --participant P01 --block task --gate corrected --com COM4` | ~6 min |
|   | *break* | |
| 5 | `python mindassist_session.py --participant P01 --block task --gate corrected --com COM4` | ~6 min |
| 6 | `python mindassist_session.py --participant P01 --block task --gate off --com COM4` | ~6 min |

Runs 3-6 alternate off / on / on / off so that tiredness affects both gate
settings equally.

---

## D. What to do for each cue

The screen shows "+" for one second, then the cue for three seconds.

| Cue on screen | What you do |
|---|---|
| BLINK ONCE | one deliberate blink |
| BLINK TWICE | two quick deliberate blinks |
| KEEP STILL | look at the screen, don't blink on purpose. A natural blink is fine and is part of what we measure |
| FROWN | frown once, no blink |
| RAISE YOUR EYEBROWS | raise them once, no blink |
| LOOK LEFT / LOOK RIGHT | move your eyes, not your head, then back |
| CLENCH YOUR JAW | clench once, then relax |
| OPEN THE DOOR | blink once |
| OPEN THE WINDOW | blink twice |

**Use your normal blink**, the way a real user would, as when the dataset was
recorded. Don't blink extra hard, and don't suppress natural blinks. The
numbers are only worth something if they reflect normal use. If you make a
mistake, just carry on; do not repeat the trial.

---

## E. Afterwards

```
python analyze_session.py sessions\P01_* --out report_P01
```

Then zip the whole `sessions` folder and `report_P01` and send them to me.

The session folders hold only a participant code (P01), timestamps and
headset values. No names.
