import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.title("🏁 Race Car Setup Simulator")

# Define the trade-off matrix
adjustments = {
    "Front ARB Stiffer": {"Entry": 20, "Mid": -20, "Exit": 0, "Aero": 20},
    "Rear ARB Stiffer": {"Entry": 0, "Mid": 25, "Exit": -25, "Aero": 15},
    "Front Springs Stiffer": {"Entry": 20, "Mid": -20, "Exit": 0, "Aero": 20},
    "Rear Springs Softer": {"Entry": 0, "Mid": -20, "Exit": 30, "Aero": -20},
}

# Initialize session state for total impact
if 'total_impact' not in st.session_state:
    st.session_state.total_impact = {"Entry": 0, "Mid": 0, "Exit": 0, "Aero": 0}

st.sidebar.header("Adjustments")

# Create Sliders
results = {"Entry": 0, "Mid": 0, "Exit": 0, "Aero": 0}
for name, impacts in adjustments.items():
    val = st.sidebar.slider(name, 0, 10, 0)
    for metric, impact in impacts.items():
        results[metric] += (val * impact) / 10

# Plotly Radar Chart
fig = go.Figure()
fig.add_trace(go.Scatterpolar(
      r=list(results.values()),
      theta=['Entry', 'Mid', 'Exit', 'Aero'],
      fill='toself'
))
fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[-100, 100])), showlegend=False)

st.plotly_chart(fig)
st.write("Current Net Telemetry:", results)
