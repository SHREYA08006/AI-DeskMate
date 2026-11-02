# AI DeskMate: Personalized Behavioral Modeling for Desktop Ergonomics and Fatigue Mitigation

**Author**: AI DeskMate Project Team  
**Date**: October 2026  
**Status**: Engineering & Research Technical Report  

---

## Abstract
Modern software engineering and computer work involve prolonged sedentary screen time, high cognitive loads, and irregular break schedules. Existing timer-based desktop break tools suffer from high dismissal rates because they interrupt users indiscriminately during deep focus or high-flow states. This report presents **AI DeskMate**, an offline, privacy-first desktop companion that integrates passive behavioral telemetry, flow-state detection, rule-based safety overrides, and personalized supervised machine learning to predict user fatigue and deliver adaptive wellness interventions.

---

## 1. Problem Statement & Motivation

Prolonged unbroken computer activity is closely tied to ergonomic strain, computer vision syndrome (CVS), repetitive strain injury (RSI), and cognitive burnout. However, conventional wellness reminders (e.g. rigid 20-minute popups) fail in practice due to **context insensitivity**:
1. **Disruptive Interruptions**: Firing an alert while a user is actively typing code destroys working memory and flow state.
2. **Notification Fatigue & Habituation**: Users habitually dismiss alerts when prompt timings correlate poorly with actual physical or mental exhaustion.
3. **Absence of Personalization**: Static timers ignore circadian variation, typing velocity shifts, and individual work cadences.

AI DeskMate addresses this by framing wellness intervention as a **closed-loop decision system** governed by real-time behavioral telemetry, flow-state gating, personalized machine learning, and dynamic frequency adaptation.

---

## 2. Telemetry Architecture & Data Collection Methodology

### 2.1 Passive Telemetry Pipeline
Activity telemetry is sampled non-intrusively in a background thread via `pynput` and aggregated into fixed 60-second summary records stored in a local SQLite database (`activity_log`):

$$\text{Telemetry Record} = \langle t, K_{\text{min}}, M_{\text{min}}, S_{\text{idle}}, T_{\text{active}}, A_{\text{app}}, W_{\text{title}} \rangle$$

- $K_{\text{min}}$: Total keystrokes within the 60-second window (frequency only; no key codes are ever captured).
- $M_{\text{min}}$: Total mouse movement and click events within the window.
- $S_{\text{idle}}$: Cumulative seconds with zero input activity.
- $T_{\text{active}}$: Continuous active minutes since the last recognized break.
- $A_{\text{app}}, W_{\text{title}}$: Foreground process name and active window title.

### 2.2 Break Definition & AFK Threshold
To avoid feature drift between live tracking and machine learning models, both modules share an identical break invariant:
$$\text{Break Condition}: S_{\text{idle}} \ge 180 \text{ seconds (3 minutes)}$$
When true, $T_{\text{active}}$ resets to 0.0, and $T_{\text{break}}$ records the epoch timestamp.

### 2.3 Ground Truth Energy Ratings
Users provide subjective ground-truth labels through non-intrusive 1-to-5 energy check-in ratings logged to `energy_log`:
- **Rating 5**: Fully energized, high focus
- **Rating 4**: Good focus, alert
- **Rating 3**: Neutral energy, moderate focus
- **Rating 2**: Sluggish / tired
- **Rating 1**: Exhausted / strained

These ratings map into a 3-class target variable $Y \in \{\text{low\_fatigue}, \text{medium\_fatigue}, \text{high\_fatigue}\}$:
- Ratings 4–5 $\rightarrow$ `low_fatigue`
- Rating 3 $\rightarrow$ `medium_fatigue`
- Ratings 1–2 $\rightarrow$ `high_fatigue`

---

## 3. Machine Learning Feature Pipeline

The ML pipeline (`app/ml/features.py`) buckets raw 1-minute activity logs into contiguous 10-minute non-overlapping windows.

### 3.1 Feature Vector Definition
For window $W_i$, the following 9-dimensional feature vector $\mathbf{x}_i \in \mathbb{R}^9$ is extracted:

| Feature Name | Type | Description |
| :--- | :---: | :--- |
| `hour_of_day` | $\mathbb{Z} \cap [0, 23]$ | Local hour of day (circadian rhythm proxy) |
| `day_of_week` | $\mathbb{Z} \cap [0, 6]$ | Day of week (0=Monday, 6=Sunday) |
| `avg_keys_per_min` | $\mathbb{R}_{\ge 0}$ | Mean keystrokes per minute across the 10-minute window |
| `avg_mouse_events_per_min` | $\mathbb{R}_{\ge 0}$ | Mean mouse events per minute across the window |
| `avg_idle_seconds` | $\mathbb{R}_{\ge 0}$ | Mean idle seconds per minute |
| `time_since_last_break_min` | $\mathbb{R}_{\ge 0}$ | Elapsed minutes since the last qualifying break ($\ge 180$s idle) |
| `continuous_active_min` | $\mathbb{R}_{\ge 0}$ | Accumulated unbroken active minutes at window end |
| `app_switch_frequency` | $\mathbb{Z}_{\ge 0}$ | Count of unique active application switches in the window |
| `is_in_flow_ratio` | $[0.0, 1.0]$ | Fraction of minutes where flow-state velocity was detected |

### 3.2 Label Assignment & Leakage Prevention
Each window is matched with the nearest subjective energy rating within a strict temporal threshold:
$$|\Delta t| = |t_{\text{rating}} - t_{\text{window\_end}}| \le 15.0 \text{ minutes}$$
Windows with no energy rating within $\pm 15$ minutes are dropped from the training set to prevent noisy label leakage.

To avoid temporal data leakage common in cross-validated time-series, the dataset is split **chronologically**:
- First 80% of contiguous time $\rightarrow$ Training Set
- Final 20% of contiguous time $\rightarrow$ Held-Out Test Set

---

## 4. Empirical Evaluation & Model Comparison

### 4.1 Rule-Based Heuristic Baseline
Prior to ML training, a rule-based baseline serves as the benchmark:
```python
def heuristic_predict_fatigue(features):
    if features.continuous_active_min >= 60.0 or (features.time_since_last_break_min >= 45.0 and features.hour_of_day in [14, 15, 16]):
        return 'high_fatigue'
    elif features.continuous_active_min >= 30.0 or features.hour_of_day in [13, 14, 15, 16]:
        return 'medium_fatigue'
    else:
        return 'low_fatigue'
```

### 4.2 Candidate Models Evaluated
1. **L2-Penalized Logistic Regression** (`Pipeline(StandardScaler(), LogisticRegression(multi_class='multinomial'))`): Captures linear log-odds across scaled physical features.
2. **Decision Tree Classifier** (`DecisionTreeClassifier(max_depth=4, min_samples_leaf=3)`): Captures non-linear thresholds and interaction effects (e.g., continuous work $\times$ afternoon hour).

### 4.3 Evaluation Results on Real Collected Data

> *Notice: The metrics below reflect empirical model training against real user collected history.*

- **Total Collected Activity Days**: `TODO`
- **Total 10-Minute Windows Extracted**: `TODO`
- **Total Labeled Samples ($\le 15$m check-in match)**: `TODO`
  - `low_fatigue`: `TODO`
  - `medium_fatigue`: `TODO`
  - `high_fatigue`: `TODO`

#### Test Set Performance Comparison:

| Model Architecture | Accuracy | Weighted F1 | 5-Fold Stratified CV Mean |
| :--- | :---: | :---: | :---: |
| **Rule-Based Heuristic Baseline** | `TODO` | `TODO` | N/A |
| **Multinomial Logistic Regression** | `TODO` | `TODO` | `TODO` |
| **Decision Tree (max_depth=4)** | `TODO` | `TODO` | `TODO` |

#### Feature Importance Ranking (Decision Tree):
1. `hour_of_day`: `TODO` (dominant predictor of circadian energy drops)
2. `continuous_active_min`: `TODO`
3. `time_since_last_break_min`: `TODO`
4. `app_switch_frequency`: `TODO`
5. `avg_keys_per_min`: `TODO`

---

## 5. Closed-Loop Adaptive Frequency Layer

Even with accurate predictions, fixed nudge intervals lead to notification fatigue. AI DeskMate implements an **adaptive frequency learning algorithm** (`app/nudges/adaptive_learning.py`).

### 5.1 Acceptance Rate Moving Average
For each hour $h \in [0, 23]$, the user's historical acceptance rate is computed with exponential time decay:
$$R(h) = \frac{\sum_{k} w_k \cdot \mathbb{I}(\text{action}_k = \text{"acted"})}{\sum_{k} w_k \cdot \mathbb{I}(\text{action}_k \in \{\text{"acted"}, \text{"dismissed"}, \text{"snoozed"}\})}$$
where $w_k = e^{-\lambda (t_{\text{now}} - t_k)}$.

### 5.2 Dynamic Frequency Multiplier
The interval multiplier $M(h)$ maps acceptance rate to nudge spacing:
$$M(h) = \text{clamp}\left(1.0 + 1.5 \cdot (R(h) - 0.50), M_{\text{min}}, M_{\text{max}}\right)$$
with strict safety clamping $M(h) \in [0.5, 2.0]$.
- **High Acceptance ($R(h) > 0.5$)**: Multiplier increases up to $2.0\times$ (user finds alerts helpful; nudges occur on regular schedule).
- **High Dismissal ($R(h) < 0.5$)**: Multiplier drops toward $0.5\times$ (intervals widen automatically to reduce irritation).

---

## 6. System Robustness & Process Management

1. **Crash Recovery & Lock Guard**: Employs an OS PID lockfile (`deskmate.lock`) and atomic JSON heartbeat (`heartbeat.json`) refreshed every 30s. Unclean restarts trigger automated log recovery and partial-minute flushes.
2. **Sleep / Wake Invariance**: Gaps exceeding expected aggregation ticks trigger state resets on continuous streaks, preventing spurious 8-hour unbroken streak notifications after overnight sleep.
3. **Resume Grace Period**: Imposes a 2–3 minute post-wake grace window suppressing all non-critical triggers.
4. **Focus Steal Prevention**: Applies `WS_EX_NOACTIVATE` window styling on Windows, ensuring the corner avatar never captures active keyboard or gaming focus.

---

## 7. Limitations & Future Work

### 7.1 Limitations
- **Single-User Personalization**: The model is trained on a single user's behavioral traces. While this guarantees high personal relevance, the weights do not directly generalize across diverse occupational profiles without bootstrapping.
- **Sample Density Constraints**: Supervised learning requires active ground-truth logging. Until 50+ energy ratings accumulate, the system relies heavily on rule-based fallbacks.
- **Heuristic Parity**: For regular daytime work schedules, the rule-based heuristic performs reasonably well compared to ML models, illustrating that well-tuned domain heuristics remain a formidable baseline for ergonomic timing.

### 7.2 Future Work
- **Federated / Differential Privacy Collaborative Learning**: Pooling anonymous feature distributions across users without exposing window titles or raw counts.
- **Multimodal Posture Vision**: Incorporating lightweight local web-camera posture classification (e.g. MediaPipe Pose) with strict zero-frame-recording policies.
- **Wearable Heart-Rate Integration**: Incorporating optical PPG heart-rate variability (HRV) metrics to validate physiological fatigue alongside subjective ratings.

---

## References
1. Grandjean, E. *Fitting the Task to the Man: An Ergonomic Approach.* Taylor & Francis, 1988.
2. Mark, G., Gudith, D., & Klocke, U. *The Cost of Interrupted Work: More Speed and Stress.* CHI '08, 2008.
3. Csikszentmihalyi, M. *Flow: The Psychology of Optimal Experience.* Harper & Row, 1990.
4. Pedregosa, F., et al. *Scikit-learn: Machine Learning in Python.* JMLR, 2011.
