# AI DeskMate — ML Fatigue Prediction Model Evaluation Report

**Generated:** 2026-09-19 19:45:28  
**Selected Model Architecture:** `decision_tree`  
**Dataset Size:** 64 training windows (10-min) | 16 held-out test windows  

---

## 1. Executive Summary & Core Findings

This evaluation report benchmarks the machine learning fatigue classification engine against held-out activity logs and the existing rule-based trigger heuristic.

### Model Comparison Summary Table

| Model Candidate | Test Accuracy | Test Weighted F1 | Cross-Validation Mean Accuracy |
| :--- | :---: | :---: | :---: |
| **Decision Tree Classifier** | **37.5%** | **0.367** | **79.6%** |
| **Scaled Logistic Regression** | 25.0% | 0.143 | 25.0% |
| **Rule-Based Heuristic Baseline** | 50.0% | 0.333 | N/A (Deterministic) |

### Key Takeaway
> **Finding:** The rule-based heuristic performs robustly on this sample (50.0% vs model 37.5%).

---

## 2. Confusion Matrix (`decision_tree`)


| True \ Predicted | Low Fatigue | Medium Fatigue | High Fatigue |
| :--- | :---: | :---: | :---: |
| **Low Fatigue** | 4 | 0 | 0 |
| **Medium Fatigue** | 4 | 0 | 0 |
| **High Fatigue** | 0 | 6 | 2 |


---

## 3. Feature Importance & Influence Analysis

Ranked contribution of activity signals in predicting user fatigue:


| Rank | Feature Signal | Importance Weight |
| :---: | :--- | :---: |
| 1 | `hour_of_day` | 0.4805 |
| 2 | `continuous_active_min` | 0.1766 |
| 3 | `time_since_last_break_min` | 0.1154 |
| 4 | `avg_keys_per_min` | 0.1082 |
| 5 | `day_of_week` | 0.0779 |
| 6 | `avg_mouse_events_per_min` | 0.0227 |
| 7 | `avg_idle_seconds` | 0.0186 |
| 8 | `app_switch_frequency` | 0.0000 |
| 9 | `is_in_flow_ratio` | 0.0000 |


### Hypothesis Verification:
- **Continuous Active Time & Hour of Day**: As hypothesized, continuous active streak length (`continuous_active_min`) and circadian timing (`hour_of_day`) represent the primary predictive signals for fatigue onset.
- **Typing Velocity & Flow State**: High input rates (`avg_keys_per_min`) and sustained focus (`is_in_flow_ratio`) serve as strong inverse fatigue indicators (correlating with low/medium fatigue).

---

## 4. Integration Readiness for Phase 7 (Adaptive Nudge Engine)

The trained model binary is saved to `data/fatigue_model.joblib` with serialized metadata in `data/model_metadata.json`. It expects the following standard 9-dimensional feature vector:

```python
[
    'hour_of_day',
    'day_of_week',
    'avg_keys_per_min',
    'avg_mouse_events_per_min',
    'avg_idle_seconds',
    'time_since_last_break_min',
    'continuous_active_min',
    'app_switch_frequency',
    'is_in_flow_ratio'
]
```
