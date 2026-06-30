import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Race Car Setup Engine", layout="wide")

st.title("🏁 Race Car Setup Sandbox")
st.markdown("Adjust your setup. Every change has a mechanical trade-off.")

# --- THE MASTER TRADE-OFF MATRIX ---
# Format: { 'Metric': [Entry, Mid, Exit, Aero] }
adjustments = {
    "Front ARB Stiffer": {"Entry": 2.0, "Mid": -1.5, "Exit": 0.0, "Aero": 1.5},
    "Rear ARB Softer": {"Entry": -1.0, "Mid": 0.5, "Exit": 2.0, "Aero": -1.0},
    "Front Springs Stiffer": {"Entry": 1.5, "Mid": -1.5, "Exit": 0.0, "Aero": 1.0},
    "Rear Springs Softer": {"Entry": 0.0, "Mid": -1.0, "Exit": 2.5, "Aero": -1.5},
    "Rear Wing Increase": {"Entry": 0.0, "Mid": 0.0, "Exit": -0.5, "Aero": 3.0},
    "Front Toe-Out": {"Entry": 2.5, "Mid": -0.5, "Exit": 0.0, "Aero": 0.0},
    "Diff Preload Increase": {"Entry": -1.0, "Mid": 1.5, "Exit": 2.0, "Aero": 0.0},
}

# Sidebar inputs
st.sidebar.header("Tuning Parameters")
results = {"Entry": 0.0, "Mid": 0.0, "Exit": 0.0, "Aero": 0.0}

for name, impacts in adjustments.items():
    val = st.sidebar.slider(name, 0, 10, 5) # Default to 5
    # Calculate impact relative to baseline 5
    delta = val - 5
    for metric, impact in impacts.items():
        results[metric] += (delta * impact)

# --- VISUALIZATION ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Telemetry Balance")
    st.write(results)

with col2:
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
          r=list(results.values()),
          theta=['Entry', 'Mid', 'Exit', 'Aero'],
          fill='toself',
          line_color='#005088'
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[-15, 15])),
        showlegend=False,
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)
