# AI DeskMate — Pitch, Interview Guide & Demo Video Blueprint

---

## ⏱️ 1-Minute Elevator Pitch

> *"Most desktop break reminders fail for one simple reason: they interrupt you at the worst possible time. If you're heads-down writing code or in the zone, a rigid 20-minute popup breaks your flow, so you dismiss it—and after three days, you uninstall it.*
>
> *I built **AI DeskMate**, an offline, privacy-first desktop companion that actually understands your work state. It passively tracks keystroke velocity and active streaks, delays non-critical nudges when you're in deep flow, and overrides only when an unhealthy unbroken streak demands a break. More importantly, it bootstraps its own labeled dataset from your daily energy check-ins, trains a personalized machine learning model to predict fatigue before you burn out, and dynamically tunes its nudge frequency based on how often you accept or dismiss them.*
>
> *It runs 100% locally with zero telemetry, compiles to a native single-file Windows installer, and includes a full Streamlit analytics dashboard with auto-generated behavioral insights."*

---

## 🎙️ 5-Minute Technical Deep-Dive Outline

### Minute 1: The Ergonomic Dilemma & Core Loop
- Traditional tools use static timers that cause notification habituation.
- The AI DeskMate closed loop:
  `Passive Telemetry (pynput) → SQLite Aggregation → Flow Evaluation → Corner Avatar Overlay → User Response → Nudge Log → Adaptive Multiplier`.

### Minute 2: Privacy Architecture & Flow-State Detection
- Keystrokes are counted, never recorded (`keys_per_min`). Zero telemetry leaves the machine.
- Flow-State Engine: When typing velocity stays above a moving threshold (e.g. >120 keys/min for 5 min), non-critical nudges (water, posture, eye rest) are delayed, not dropped.
- Safety Override: Hard 90-minute unbroken activity override interrupts unhealthy streaks regardless of flow state.

### Minute 3: Feature Engineering & Dataset Preparation
- Contiguous 10-minute non-overlapping windowing across historical activity logs.
- 9-dimensional physical feature vector: circadian hours, day of week, key/mouse rates, idle times, continuous streaks, time since break, app switching, and flow prevalence.
- Leakage Prevention: Nearest energy label matching strictly within $\pm 15$ minutes; time-based chronological 80/20 train/test split.

### Minute 4: Machine Learning & Closed-Loop Adaptation
- Benchmarked Multinomial Logistic Regression and Decision Tree against a domain-specific rule-based heuristic baseline.
- Decision Tree captured non-linear interactions (e.g. continuous work duration $\times$ afternoon circadian dip).
- Adaptive Frequency Layer: Computes exponential decay weighted acceptance rates per hour, clamping nudge multipliers between $0.5\times$ and $2.0\times$ to prevent notification fatigue.

### Minute 5: Production Engineering & Packaging
- Sleep/wake gap detection with 3-minute post-resume grace period.
- Atomic PID lockfile and JSON heartbeat for clean crash recovery.
- Packaging: PyInstaller windowed executable (`WS_EX_NOACTIVATE`), dedicated Streamlit launcher on an ephemeral localhost port, and Inno Setup installer.

---

## 🎯 Technical Interview Questions & Answers

### Q1: Why bootstrap your own dataset instead of using an existing public dataset?
> **Answer**:  
> *"Existing public ergonomic and fatigue datasets either rely on synthetic lab environments, eye-tracking webcams, or wearable EEG/ECG sensors that normal desk workers don't use. Desktop behavior—such as typing cadence, window switching, and break habits—is deeply idiosyncratic to an individual's operating system, software tools, and role. By bootstrapping a lightweight 1-to-5 energy check-in prompt into the companion itself, AI DeskMate collects ecological, in-situ ground-truth labels directly in the user's natural workflow without invasive hardware."*

---

### Q2: Why use a time-based train/test split instead of standard random `train_test_split`?
> **Answer**:  
> *"In time-series behavioral data, consecutive 10-minute windows exhibit strong autocorrelation—yesterday's 2:00 PM session is closely related to 2:10 PM. If we applied a random split, past and future observations would be mixed across training and testing sets, causing temporal data leakage and artificially inflated accuracy. A strict chronological split (first 80% train, final 20% test) mirrors real-world deployment: predicting future fatigue using only historical observations."*

---

### Q3: Why keep the rule-based fallback instead of relying 100% on the ML model?
> **Answer**:  
> *"In production systems, machine learning models face edge cases: fresh installs with zero collected data, corrupted model files, or low inference confidence scores. A pure ML system would either fail silently or make reckless guesses. Keeping a deterministic, battle-tested rule-based heuristic provides defensive fallback: if the model is absent, corrupted, or has low confidence (<0.6), the app continues functioning seamlessly. Machine learning enhances the heuristic rather than creating a fragile single point of failure."*

---

### Q4: How does the adaptive frequency algorithm prevent a 'death spiral' of zero notifications?
> **Answer**:  
> *"If a user dismisses multiple nudges in a row, an unconstrained algorithm might continuously widen the reminder interval until reminders effectively stop forever. AI DeskMate prevents this in two ways:  
> 1. Hard Clamping: The frequency multiplier is bounded to $[0.5, 2.0]$. Even during prolonged dismissal, intervals cannot widen beyond $2.0\times$ baseline.  
> 2. Safety Overrides: The 90-minute break reminder is a hard override that ignores frequency multipliers and flow suppression entirely, ensuring physical health invariants are always enforced."*

---

## 🎬 2–3 Minute Demo-Video Shot List

| Timecode | Visual Frame | Audio / Narration |
| :---: | :--- | :--- |
| **0:00 – 0:25** | Start with Desktop corner. Show floating animated avatar (Mochi the Cat). | *"Meet AI DeskMate: an adaptive desktop companion designed to prevent computer fatigue without interrupting your focus."* |
| **0:25 – 0:50** | Open VS Code / IDE. Type rapidly. Show system tray menu and live status. | *"Notice how DeskMate monitors keystroke cadence without recording text. When you're in deep flow, it suppresses non-critical popups so your concentration isn't broken."* |
| **0:50 – 1:15** | Trigger Demo Mode via tray: `🎭 Trigger Sample Nudge`. | *"Using Demo Mode, we can cue sample nudges across four distinct personality tones—from chill and gentle to witty and sarcastic."* |
| **1:15 – 1:45** | Click `📊 Open Dashboard` in tray. Show Streamlit app opening on localhost. | *"Clicking 'Open Dashboard' launches our local Streamlit analytics app on an available port, displaying screentime trends, adherence rates, and circadian heatmaps."* |
| **1:45 – 2:15** | Scroll down to the **Insights Cards** and **Hourly Effectiveness** chart. | *"Here are auto-generated behavioral insights with strict minimum-data guards, comparing this week's acceptance rates with last week to tune notification frequency."* |
| **2:15 – 2:40** | Show `AIDeskMate.exe` running without Python on a fresh machine. | *"Everything runs 100% locally with zero cloud telemetry, packaged into a single Windows installer."* |
