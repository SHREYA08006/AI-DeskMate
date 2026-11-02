# AI DeskMate — Resume Bullet Points

Select the variant that best aligns with the role you are targeting (Full-Stack / Systems / Applied ML / Software Engineering). Fill in the `TODO` markers once you have run `prepare_dataset` and `train_model` against your collected dataset.

---

### Variant 1: Applied Machine Learning & Data Systems Focus
> **AI DeskMate — Personalized Desktop Wellness & Ergonomics Platform**  
> *Python, Scikit-Learn, Pandas, SQLite, Streamlit, PyInstaller, Inno Setup*  
> • Architected an offline, privacy-first desktop application aggregating passive keystroke and mouse telemetry across fixed 60-second intervals to model ergonomic strain and cognitive fatigue.  
> • Engineered a 9-dimensional temporal feature pipeline across 10-minute sliding windows, bootstrapping ground-truth labels from subjective energy ratings with strict $\pm 15$-minute leakage boundaries and chronological train/test splits.  
> • Trained and benchmarked Multinomial Logistic Regression and Decision Tree classifiers, achieving **TODO** test accuracy and outperforming a domain heuristic baseline by **TODO**.  
> • Designed an exponential-decay adaptive frequency algorithm mapping historical hourly acceptance rates to bounded nudge multipliers ($[0.5\times, 2.0\times]$) to eliminate notification habituation.

---

### Variant 2: Full-Stack & Desktop Systems Engineering Focus
> **AI DeskMate — Adaptive Desktop Ergonomic Companion**  
> *Python, CustomTkinter, Pynput, PyTTSx3, SQLite, Streamlit, Plotly, Windows Registry*  
> • Built an autonomous desktop companion featuring non-activating floating UI overlays (`WS_EX_NOACTIVATE`), offline speech synthesis, and flow-state suppression that delays non-critical alerts during high typing velocity.  
> • Engineered resilient background process management with atomic JSON heartbeats, single-instance PID locking, OS sleep/wake gap recovery, and SQLite exponential-backoff lock retries.  
> • Developed a localized Streamlit analytics dashboard displaying screentime trends, circadian adherence heatmaps, and rule-based template insights with strict minimum-data guards.  
> • Packaged the full pipeline into a zero-dependency Windows installer (`.iss`) with automated per-user data isolation (`%APPDATA%`), Start Menu shortcuts, and Windows sign-in autostart toggles.

---

### Variant 3: Concise 2-Bullet Engineering Variant
> • **AI DeskMate (Personalized Ergonomic Assistant)**: Engineered an offline desktop companion in Python and SQLite that monitors typing velocity and streak durations to deliver flow-aware wellness interventions with offline TTS and animated overlays.  
> • **Adaptive Learning & Packaging**: Implemented a supervised ML fatigue pipeline with chronological leak protection that achieved **TODO** accuracy, integrated an adaptive hourly frequency feedback loop, and deployed via a native Windows Inno Setup installer.
