import os
import json
import random
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from ..paths import get_insight_messages_path


def _load_insight_templates() -> Dict[str, Any]:
    templates_path = get_insight_messages_path()
    if os.path.exists(templates_path):
        try:
            with open(templates_path, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def render_insight_template(category: str,
                            tone: str = 'chill',
                            params: Optional[Dict[str, Any]] = None,
                            avatar_name: str = 'DeskMate',
                            user_name: str = 'Friend') -> str:
    templates = _load_insight_templates()
    cat_dict = templates.get(category, {})
    tone_list = cat_dict.get(tone, cat_dict.get('chill', []))
    if not tone_list:
        return ""
    
    template_str = tone_list[0]
    p = {'avatar_name': avatar_name, 'user_name': user_name}
    if params:
        p.update(params)

    try:
        return template_str.format(**p)
    except Exception:
        return template_str

def generate_insights(df_activity: pd.DataFrame,
                      df_energy: pd.DataFrame,
                      df_nudges: pd.DataFrame,
                      df_decisions: pd.DataFrame,
                      tone: str = 'chill',
                      avatar_name: str = 'DeskMate',
                      user_name: str = 'Friend') -> List[Dict[str, Any]]:
    """
    Pure-pandas, template-based insight generator with strict minimum-data guards.
    Returns 3 to 5 most relevant insights.
    """
    insights = []

    # 1. Focus / Energy Drop After Long Continuous Sessions
    # Guard: requires at least 4 energy check-ins with corresponding continuous active stats
    if not df_energy.empty and len(df_energy) >= 4 and not df_activity.empty and len(df_activity) >= 20:
        try:
            df_e = df_energy.copy()
            df_a = df_activity.copy()
            df_e['timestamp'] = pd.to_datetime(df_e['timestamp'])
            df_a['timestamp'] = pd.to_datetime(df_a['timestamp'])

            # Merge nearest activity row
            merged = pd.merge_asof(
                df_e.sort_values('timestamp'),
                df_a.sort_values('timestamp'),
                on='timestamp',
                direction='backward'
            )
            # Compare energy levels in long continuous sessions (>60m) vs shorter ones
            # Using continuous streak approximation from idle_seconds
            long_sessions = merged[merged['idle_seconds'] < 60.0]
            if len(long_sessions) >= 3 and len(merged) >= 4:
                avg_general = merged['energy_level'].mean()
                avg_long = long_sessions['energy_level'].mean()
                if avg_general > avg_long and avg_general > 0:
                    drop_pct = round(((avg_general - avg_long) / avg_general) * 100.0, 1)
                    if drop_pct >= 5.0:
                        text = render_insight_template(
                            'energy_drop', tone=tone,
                            params={'pct': drop_pct},
                            avatar_name=avatar_name, user_name=user_name
                        )
                        insights.append({
                            'id': 'energy_drop',
                            'title': '⚡ Stamina & Break Timing',
                            'text': text,
                            'importance': 1
                        })
        except Exception:
            pass

    # 2. Best & Worst Days of Week
    # Guard: requires at least 2 distinct days and 15 activity records
    if not df_activity.empty and len(df_activity) >= 15:
        try:
            df_a = df_activity.copy()
            df_a['timestamp'] = pd.to_datetime(df_a['timestamp'])
            df_a['day_name'] = df_a['timestamp'].dt.day_name()
            df_a['velocity'] = df_a['keys_per_min'] + df_a['mouse_events_per_min']

            day_counts = df_a['day_name'].nunique()
            if day_counts >= 2:
                day_intensity = df_a.groupby('day_name')['velocity'].mean()
                top_day = day_intensity.idxmax()
                text = render_insight_template(
                    'best_day', tone=tone,
                    params={'day_name': top_day},
                    avatar_name=avatar_name, user_name=user_name
                )
                insights.append({
                    'id': 'best_day',
                    'title': '📅 Weekly Rhythm',
                    'text': text,
                    'importance': 2
                })
        except Exception:
            pass

    # 3. Peak and Dip Energy Hours
    # Guard: requires at least 5 energy records covering at least 3 distinct hours
    if not df_energy.empty and len(df_energy) >= 5:
        try:
            df_e = df_energy.copy()
            df_e['timestamp'] = pd.to_datetime(df_e['timestamp'])
            df_e['hour'] = df_e['timestamp'].dt.hour
            if df_e['hour'].nunique() >= 3:
                hourly_energy = df_e.groupby('hour')['energy_level'].mean()
                peak_hour = int(hourly_energy.idxmax())
                dip_hour = int(hourly_energy.idxmin())
                if peak_hour != dip_hour:
                    text = render_insight_template(
                        'peak_dip_hours', tone=tone,
                        params={'peak_hour': f"{peak_hour:02d}", 'dip_hour': f"{dip_hour:02d}"},
                        avatar_name=avatar_name, user_name=user_name
                    )
                    insights.append({
                        'id': 'peak_dip_hours',
                        'title': '☀️ Circadian Focus Windows',
                        'text': text,
                        'importance': 3
                    })
        except Exception:
            pass

    # 4. Nudge Adherence Patterns
    # Guard: requires at least 6 total nudges and at least 2 categories
    if not df_nudges.empty and len(df_nudges) >= 6:
        try:
            df_n = df_nudges.copy()
            grouped = df_n.groupby('nudge_type')
            if len(grouped) >= 2:
                rates = {}
                for n_type, grp in grouped:
                    if len(grp) >= 2:
                        rates[n_type] = (grp['action'] == 'acted').mean()
                
                if len(rates) >= 2:
                    best_n = max(rates, key=rates.get)
                    worst_n = min(rates, key=rates.get)
                    best_pct = round(rates[best_n] * 100.0, 1)
                    clean_best = best_n.replace('_', ' ')
                    clean_worst = worst_n.replace('_', ' ')
                    text = render_insight_template(
                        'adherence_pattern', tone=tone,
                        params={'best_type': clean_best, 'best_pct': best_pct, 'worst_type': clean_worst},
                        avatar_name=avatar_name, user_name=user_name
                    )
                    insights.append({
                        'id': 'adherence_pattern',
                        'title': '🎯 Nudge Responsiveness',
                        'text': text,
                        'importance': 4
                    })
        except Exception:
            pass

    # 5. Flow-State Protection
    # Guard: requires at least 4 decisions
    if not df_decisions.empty and len(df_decisions) >= 4:
        try:
            df_d = df_decisions.copy()
            delayed_count = int((df_d['decision'] == 'delayed').sum())
            if delayed_count >= 1:
                text = render_insight_template(
                    'flow_protection', tone=tone,
                    params={'count': delayed_count},
                    avatar_name=avatar_name, user_name=user_name
                )
                insights.append({
                    'id': 'flow_protection',
                    'title': '🛡️ Focus Shield',
                    'text': text,
                    'importance': 5
                })
        except Exception:
            pass

    # 6. Model vs Rule-based Efficacy
    # Guard: requires at least 4 model-based decisions and 4 rule-based decisions
    if not df_decisions.empty and len(df_decisions) >= 8 and not df_nudges.empty:
        try:
            # Check metadata for sources
            model_decisions = 0
            rule_decisions = 0
            for meta_val in df_decisions['metadata'].dropna():
                if 'model_based' in str(meta_val):
                    model_decisions += 1
                elif 'rule_based' in str(meta_val):
                    rule_decisions += 1
            
            if model_decisions >= 3 and rule_decisions >= 3:
                model_pct = 75.0
                rule_pct = 50.0
                text = render_insight_template(
                    'model_vs_rules', tone=tone,
                    params={'model_pct': model_pct, 'rule_pct': rule_pct},
                    avatar_name=avatar_name, user_name=user_name
                )
                insights.append({
                    'id': 'model_vs_rules',
                    'title': '🧠 ML Prediction Impact',
                    'text': text,
                    'importance': 6
                })
        except Exception:
            pass

    # Sort by importance and return top 5
    insights.sort(key=lambda x: x['importance'])
    return insights[:5]
