import os, sys
import sqlite3
import json
from datetime import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from app.dashboard.analytics import (
    filter_by_date_range,
    get_daily_screentime_trend,
    get_break_adherence_rate,
    get_energy_rating_trend,
    get_hourly_activity_heatmap,
    get_work_block_aggregations,
    get_flow_vs_nudge_behavior,
    get_hourly_effectiveness_comparison
)
from app.dashboard.insights import generate_insights

# Page configuration
st.set_page_config(
    page_title="AI DeskMate — Analytics & Insights",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    .metric-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .metric-label {
        font-size: 13px;
        font-weight: 600;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #38BDF8;
        margin-top: 4px;
    }
    .metric-sub {
        font-size: 12px;
        color: #64748B;
        margin-top: 2px;
    }
    .avatar-header {
        background: linear-gradient(90deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 24px;
    }
    .empty-state {
        background: #1E293B;
        border: 1px dashed #475569;
        border-radius: 16px;
        padding: 40px;
        text-align: center;
        margin: 40px 0;
    }
</style>
""", unsafe_allow_html=True)

AVATAR_EMOJIS = {
    'cat': '🐱',
    'dog': '🐶',
    'hamster': '🐹',
    'human': '🧑',
    'robot': '🤖'
}

try:
    from app.paths import get_db_path, get_config_path
except (ImportError, ValueError):
    from ..paths import get_db_path, get_config_path

is_demo_mode = os.environ.get("DESKMATE_DEMO_MODE") == "1" or "--demo" in sys.argv

@st.cache_data(ttl=5)
def load_data():
    db_path = get_db_path(demo=is_demo_mode)
    config_path = get_config_path()

    # Load config
    config = {
        'user_name': 'Friend',
        'avatar_name': 'Mochi',
        'avatar_type': 'cat',
        'personality_tone': 'chill'
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config.update(json.load(f))
        except Exception:
            pass

    # Read DB data
    df_activity = pd.DataFrame()
    df_energy = pd.DataFrame()
    df_nudges = pd.DataFrame()
    df_decisions = pd.DataFrame()

    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            df_activity = pd.read_sql_query("SELECT * FROM activity_log ORDER BY timestamp ASC", conn)
            df_energy = pd.read_sql_query("SELECT * FROM energy_log ORDER BY timestamp ASC", conn)
            df_nudges = pd.read_sql_query("SELECT * FROM nudge_log ORDER BY timestamp ASC", conn)
            df_decisions = pd.read_sql_query("SELECT * FROM nudge_decision_log ORDER BY timestamp ASC", conn)
            conn.close()
        except Exception:
            try:
                conn = sqlite3.connect(db_path)
                df_activity = pd.read_sql_query("SELECT * FROM activity_log ORDER BY timestamp ASC", conn)
                df_energy = pd.read_sql_query("SELECT * FROM energy_log ORDER BY timestamp ASC", conn)
                df_nudges = pd.read_sql_query("SELECT * FROM nudge_log ORDER BY timestamp ASC", conn)
                df_decisions = pd.read_sql_query("SELECT * FROM nudge_decision_log ORDER BY timestamp ASC", conn)
                conn.close()
            except Exception:
                pass

    return config, df_activity, df_energy, df_nudges, df_decisions

config, raw_activity, raw_energy, raw_nudges, raw_decisions = load_data()

if is_demo_mode:
    st.info("🧪 **Demo Mode (Synthetic Data)** — All displayed metrics and logs are generated from realistic synthetic patterns. Real data is safely isolated.")

# Header
avatar_emoji = AVATAR_EMOJIS.get(config.get('avatar_type', 'cat'), '🐱')
avatar_name = config.get('avatar_name', 'Mochi')
user_name = config.get('user_name', 'Friend')
tone = config.get('personality_tone', 'chill').capitalize()

st.sidebar.markdown(f"### {avatar_emoji} {avatar_name}")
st.sidebar.markdown(f"**Companion Tone:** `{tone}`")
st.sidebar.markdown(f"**User:** `{user_name}`")
st.sidebar.markdown("---")

date_filter = st.sidebar.radio(
    "📅 Date Range Filter",
    options=['today', 'week', 'month', 'all'],
    format_func=lambda x: {
        'today': '☀️ Today',
        'week': '📅 This Week (7 Days)',
        'month': '🗓️ This Month (30 Days)',
        'all': '♾️ All Time'
    }[x],
    index=3
)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# Apply filter
df_activity = filter_by_date_range(raw_activity, date_filter)
df_energy = filter_by_date_range(raw_energy, date_filter)
df_nudges = filter_by_date_range(raw_nudges, date_filter)
df_decisions = filter_by_date_range(raw_decisions, date_filter)

# Branded Banner
st.markdown(f"""
<div class="avatar-header">
    <h2 style="margin: 0; color: #F8FAFC; display: flex; align-items: center; gap: 12px;">
        <span>{avatar_emoji}</span> {avatar_name}'s Productivity & Wellness Command Center
    </h2>
    <p style="margin: 6px 0 0 0; color: #94A3B8; font-size: 14px;">
        Tracking focus streaks, break adherence, fatigue rhythms, and flow-state dynamics for <strong>{user_name}</strong>.
    </p>
</div>
""", unsafe_allow_html=True)

# Empty state check
if df_activity.empty and df_energy.empty and df_nudges.empty:
    st.markdown(f"""
    <div class="empty-state">
        <h1 style="font-size: 48px; margin: 0;">{avatar_emoji}</h1>
        <h3 style="color: #F8FAFC; margin-top: 12px;">{avatar_name} is quietly gathering your rhythm!</h3>
        <p style="color: #94A3B8; max-width: 500px; margin: 8px auto 0 auto; font-size: 15px;">
            No logged activity in this date range yet. As you type, move your mouse, and respond to companion check-ins, real-time analytics will populate here automatically.
        </p>
    </div>
    """, unsafe_allow_html=True)
else:
    # Calculations
    screentime_df = get_daily_screentime_trend(df_activity)
    adherence_data = get_break_adherence_rate(df_nudges)
    energy_data = get_energy_rating_trend(df_energy)
    heatmap_df = get_hourly_activity_heatmap(df_activity)
    work_blocks = get_work_block_aggregations(df_activity, df_energy)
    flow_behavior = get_flow_vs_nudge_behavior(df_decisions)

    total_active_mins = int(screentime_df['active_minutes'].sum()) if not screentime_df.empty else 0
    total_active_hours = round(total_active_mins / 60.0, 1)
    adh_rate = adherence_data['overall_rate']
    avg_energy = energy_data['avg_energy']
    longest_streak = work_blocks['longest_streak_minutes']

    # 0. AI Companion Insights
    insights_list = generate_insights(
        df_activity=df_activity,
        df_energy=df_energy,
        df_nudges=df_nudges,
        df_decisions=df_decisions,
        tone=tone,
        avatar_name=avatar_name,
        user_name=user_name
    )

    if insights_list:
        st.markdown(f"### 💡 {avatar_name}'s Key Insights & Behavioral Trends")
        cols = st.columns(min(len(insights_list), 3))
        for idx, ins in enumerate(insights_list[:3]):
            with cols[idx % len(cols)]:
                st.markdown(f"""
                <div class="metric-card" style="border-left: 4px solid #38BDF8; margin-bottom: 14px;">
                    <div style="font-weight: bold; color: #38BDF8; font-size: 13px; margin-bottom: 4px;">{ins['title']}</div>
                    <div style="font-size: 14px; color: #F1F5F9; line-height: 1.4;">{ins['text']}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background-color: #1E293B; border-radius: 8px; padding: 12px 18px; margin-bottom: 18px; border: 1px dashed #475569;">
            <span style="color: #94A3B8; font-size: 14px;">🌱 <strong>{avatar_name} is still learning your patterns:</strong> Log a few more sessions and check-ins to unlock personalized productivity insights.</span>
        </div>
        """, unsafe_allow_html=True)

    # 1. KPI Cards Row
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">⏱️ Total Active Screen Time</div>
            <div class="metric-value">{total_active_hours}h <span style="font-size:16px; color:#94A3B8;">({total_active_mins}m)</span></div>
            <div class="metric-sub">Across filtered period</div>
        </div>
        """, unsafe_allow_html=True)

    with kpi2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">🎯 Nudge Adherence Rate</div>
            <div class="metric-value">{adh_rate}%</div>
            <div class="metric-sub">{adherence_data['acted_count']} of {adherence_data['total_nudges']} nudges acted on</div>
        </div>
        """, unsafe_allow_html=True)

    with kpi3:
        energy_color = "#10B981" if avg_energy >= 3.5 else ("#F59E0B" if avg_energy >= 2.5 else "#EF4444")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">⚡ Avg Energy Level</div>
            <div class="metric-value" style="color:{energy_color};">{avg_energy} <span style="font-size:16px; color:#94A3B8;">/ 5.0</span></div>
            <div class="metric-sub">{energy_data['total_ratings']} check-ins recorded</div>
        </div>
        """, unsafe_allow_html=True)

    with kpi4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">🔥 Longest Work Streak</div>
            <div class="metric-value">{longest_streak}m</div>
            <div class="metric-sub">Continuous active session</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # 2. Hourly Activity Heatmap (Prominent Hero Chart)
    st.markdown("### 📊 Hourly Activity & Focus Heatmap")
    st.caption("Typing and mouse event density by hour of day across the week (00:00 to 23:00).")

    fig_heat = px.imshow(
        heatmap_df.values,
        labels=dict(x="Hour of Day", y="Day of Week", color="Activity Velocity"),
        x=[f"{h:02d}:00" for h in range(24)],
        y=heatmap_df.index.tolist(),
        color_continuous_scale="Viridis",
        aspect="auto"
    )
    fig_heat.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94A3B8'),
        margin=dict(l=40, r=20, t=20, b=30),
        height=320,
        coloraxis_colorbar=dict(
            title="Events/Min",
            thickness=14,
            len=0.8
        )
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    # 3. Two Column Charts: Screen Time Trend & Break Adherence
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### 📈 Daily Active Screen Time Trend")
        if not screentime_df.empty:
            fig_screen = px.bar(
                screentime_df,
                x='date',
                y='active_hours',
                labels={'date': 'Date', 'active_hours': 'Active Hours'},
                title="Active Screen Time (Hours/Day)",
                color_discrete_sequence=['#38BDF8']
            )
            fig_screen.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#94A3B8'),
                margin=dict(l=20, r=20, t=40, b=20),
                height=320,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#334155')
            )
            st.plotly_chart(fig_screen, use_container_width=True)
        else:
            st.info("No screen time activity records in this timeframe.")

    with col_right:
        st.markdown("### 🎯 Break Adherence by Nudge Type")
        adh_by_type = adherence_data['by_type']
        if not adh_by_type.empty:
            fig_adh = px.bar(
                adh_by_type,
                x='adherence_pct',
                y='nudge_type',
                orientation='h',
                labels={'adherence_pct': 'Adherence Rate (%)', 'nudge_type': 'Nudge Category'},
                title="Action Rate (% Acted)",
                color='adherence_pct',
                color_continuous_scale='Tealgrn',
                range_x=[0, 100]
            )
            fig_adh.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#94A3B8'),
                margin=dict(l=20, r=20, t=40, b=20),
                height=320,
                xaxis=dict(showgrid=True, gridcolor='#334155'),
                yaxis=dict(showgrid=False)
            )
            st.plotly_chart(fig_adh, use_container_width=True)
        else:
            st.info("No nudges triggered yet in this timeframe.")

    # 4. Energy Trend & Flow State Behavior
    col_en, col_flow = st.columns(2)

    with col_en:
        st.markdown("### ⚡ Energy Rating Time Series")
        df_en_trend = energy_data['trend_df']
        if not df_en_trend.empty:
            fig_en = go.Figure()
            fig_en.add_trace(go.Scatter(
                x=df_en_trend['timestamp'],
                y=df_en_trend['energy_level'],
                mode='markers',
                name='Energy Check-in',
                marker=dict(size=9, color='#F59E0B')
            ))
            fig_en.add_trace(go.Scatter(
                x=df_en_trend['timestamp'],
                y=df_en_trend['rolling_avg'],
                mode='lines',
                name='Rolling Trend',
                line=dict(color='#10B981', width=3)
            ))
            fig_en.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#94A3B8'),
                margin=dict(l=20, r=20, t=40, b=20),
                height=320,
                yaxis=dict(range=[0.5, 5.5], tickvals=[1, 2, 3, 4, 5], gridcolor='#334155'),
                xaxis=dict(showgrid=False)
            )
            st.plotly_chart(fig_en, use_container_width=True)
        else:
            st.info("No energy check-ins logged yet.")

    with col_flow:
        st.markdown("### 🌊 Flow State & Nudge Decision Breakdown")
        dec_breakdown = flow_behavior['decision_breakdown']
        if not dec_breakdown.empty:
            fig_pie = px.pie(
                dec_breakdown,
                names='decision',
                values='count',
                title=f"Decisions Breakdown (Flow Delay Rate: {flow_behavior['flow_delay_rate_pct']}%)",
                hole=0.45,
                color_discrete_map={
                    'fired': '#10B981',
                    'delayed': '#38BDF8',
                    'suppressed': '#F43F5E',
                    'not_due': '#475569'
                }
            )
            fig_pie.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#94A3B8'),
                margin=dict(l=20, r=20, t=40, b=20),
                height=320
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No trigger decisions logged yet.")

    # 5. Adaptive Nudge Effectiveness: This Week vs Last Week
    st.markdown("### 📈 Nudge Effectiveness by Hour (This Week vs. Last Week)")
    st.caption("Tracks how your nudge acceptance rate (% acted on) adapts across each hour of the day over time.")
    
    eff_data = get_hourly_effectiveness_comparison(raw_nudges)
    comp_df = eff_data['comparison_df']

    fig_eff = go.Figure()
    fig_eff.add_trace(go.Bar(
        x=[f"{h:02d}:00" for h in comp_df['hour']],
        y=comp_df['this_week_rate'],
        name='This Week',
        marker_color='#10B981'
    ))
    fig_eff.add_trace(go.Bar(
        x=[f"{h:02d}:00" for h in comp_df['hour']],
        y=comp_df['last_week_rate'],
        name='Last Week',
        marker_color='#64748B'
    ))
    fig_eff.update_layout(
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#94A3B8'),
        margin=dict(l=20, r=20, t=30, b=20),
        height=320,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='#334155', range=[0, 100], title="Acceptance Rate (%)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_eff, use_container_width=True)

    # 6. Key Work Block Insights
    st.markdown("### 🏆 Work Rhythm & Focus Insights")
    ins1, ins2, ins3 = st.columns(3)

    with ins1:
        st.markdown("##### 🚀 Busiest Peak Hours")
        b_blocks = work_blocks['busiest_blocks']
        if b_blocks:
            for b in b_blocks:
                st.markdown(f"- **{b['block']}**: `{b['avg_intensity']} avg events/min`")
        else:
            st.caption("Gathering hourly intensity patterns...")

    with ins2:
        st.markdown("##### ⚡ Energy Rhythm")
        e_hour = work_blocks['energy_by_hour']
        if e_hour:
            best_hour = max(e_hour, key=e_hour.get)
            lowest_hour = min(e_hour, key=e_hour.get)
            st.markdown(f"- **Peak Energy Window**: `{best_hour:02d}:00` ({e_hour[best_hour]}/5)")
            st.markdown(f"- **Fatigue Dip Window**: `{lowest_hour:02d}:00` ({e_hour[lowest_hour]}/5)")
        else:
            st.caption("Record periodic check-ins to unlock fatigue pattern detection.")

    with ins3:
        st.markdown("##### 🛡️ Flow-State Protection")
        st.markdown(f"- **Nudges Delayed in Flow**: `{flow_behavior['delayed_count']}`")
        st.markdown(f"- **Suppressed (Idle/DND/Snooze)**: `{flow_behavior['suppressed_count']}`")
        st.markdown(f"- **Direct Popups Fired**: `{flow_behavior['fired_count']}`")

