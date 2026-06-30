import streamlit as st
import plotly.graph_objects as go

# App configuration for clean presentation
st.set_page_config(
    page_title="GT3 Setup Sandbox Engine",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom premium styling to match your reference mockup perfectly
st.markdown("""
    <style>
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 550px; }
    h1 { text-align: center; font-family: 'Helvetica Neue', Arial, sans-serif; font-weight: 400; color: #111; margin-bottom: 0.2rem; font-size: 1.75rem; }
    .subtitle { text-align: center; font-family: monospace; color: #777; margin-bottom: 1.5rem; font-size: 0.85rem; }
    .status-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        margin-top: 20px;
        margin-bottom: 25px;
        border: 1px solid #eaeaea;
    }
    .status-title { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 500; }
    .status-value { font-size: 1.15rem; font-weight: 400; color: #222; margin-top: 6px; font-family: monospace; }
    div[data-testid="stSlider"] { margin-bottom: 12px; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1>Car Setup Balance Simulator</h1>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>GT3 TELEMETRY CORE v2.4 (ACTIVE)</div>", unsafe_allow_html=True)

# --- FACTUAL ASYMMETRIC GT3 VEHICLE DYNAMICS ENGINE ---
def calculate_physics(setup):
    # Standard baseline values
    entry_rot = 0.0
    mid_und = 0.0
    exit_trac = 0.0
    hs_stab = 0.0

    # 1. Front Anti-Roll Bar (ARB)
    if setup["Front ARB"] >= 0:
        entry_rot -= setup["Front ARB"] * 4.0
        mid_und += setup["Front ARB"] * 5.5
        hs_stab += setup["Front ARB"] * 1.5
    else:  # Softening increases mechanical roll/grip but compromises high-speed transition speed
        entry_rot += abs(setup["Front ARB"]) * 5.0
        mid_und -= abs(setup["Front ARB"]) * 4.0
        hs_stab -= abs(setup["Front ARB"]) * 3.5

    # 2. Rear Anti-Roll Bar (ARB)
    if setup["Rear ARB"] >= 0:
        entry_rot += setup["Rear ARB"] * 4.5
        mid_und -= setup["Rear ARB"] * 5.0
        exit_trac -= setup["Rear ARB"] * 6.0  # Asymmetric: Excess rear stiffness causes snap wheel-spin
    else:
        entry_rot -= abs(setup["Rear ARB"]) * 3.0
        mid_und += abs(setup["Rear ARB"]) * 4.0
        exit_trac += abs(setup["Rear ARB"]) * 4.0

    # 3. Front Wheel Springs
    if setup["Front Springs"] >= 0:
        entry_rot -= setup["Front Springs"] * 2.5
        mid_und += setup["Front Springs"] * 4.0
        hs_stab += setup["Front Springs"] * 3.5  # Stabilizes front splitter platform aerodynamically
    else:
        entry_rot += abs(setup["Front Springs"]) * 3.5
        mid_und -= abs(setup["Front Springs"]) * 3.0
        hs_stab -= abs(setup["Front Springs"]) * 6.0  # Asymmetric penalty: Pitching down breaks aero seal

    # 4. Rear Wheel Springs
    if setup["Rear Springs"] >= 0:
        entry_rot += setup["Rear Springs"] * 4.0
        mid_und -= setup["Rear Springs"] * 3.0
        exit_trac -= setup["Rear Springs"] * 5.0
        hs_stab += setup["Rear Springs"] * 2.0
    else:
        entry_rot -= abs(setup["Rear Springs"]) * 2.0
        mid_und += abs(setup["Rear Springs"]) * 4.5
        exit_trac += abs(setup["Rear Springs"]) * 6.5  # Asymmetric bonus: Dynamic weight transfer squats rear tires

    # 5. Brake Bias (BB)
    if setup["Brake Bias"] >= 0:  # Forward Bias
        entry_rot -= setup["Brake Bias"] * 5.5
        mid_und += setup["Brake Bias"] * 2.0
        hs_stab += setup["Brake Bias"] * 2.5  # Heavy brake stability improvement
    else:  # Rearward Bias
        entry_rot += abs(setup["Brake Bias"]) * 8.5  # Asymmetric: Extreme trail-braking pivot rotation
        hs_stab -= abs(setup["Brake Bias"]) * 7.5   # Massive high-speed deceleration instability hazard

    # 6. Differential Preload
    if setup["Diff Preload"] >= 0:  # High Preload (More locked on coast)
        entry_rot -= setup["Diff Preload"] * 4.5  # Understeer on off-throttle turn-in
        mid_und += setup["Diff Preload"] * 3.5
        exit_trac += setup["Diff Preload"] * 4.0  # Cleaner, locked traction power delivery
    else:  # Low Preload (Open differential behavior)
        entry_rot += abs(setup["Diff Preload"]) * 6.0  # Free rotation on corner entries
        mid_und -= abs(setup["Diff Preload"]) * 4.0
        exit_trac -= abs(setup["Diff Preload"]) * 5.5  # Inside wheel slip risks losing drive out of corners

    # 7. Rear Wing Profile
    if setup["Rear Wing"] >= 0:
        mid_und += setup["Rear Wing"] * 3.0
        exit_trac += setup["Rear Wing"] * 2.5
        hs_stab += setup["Rear Wing"] * 7.5  # Downforce gains scale high speed control
    else:
        mid_und -= abs(setup["Rear Wing"]) * 2.5
        exit_trac -= abs(setup["Rear Wing"]) * 5.0
        hs_stab -= abs(setup["Rear Wing"]) * 11.0  # Asymmetric: Aero stall creates complete high speed drift out

    # 8. Front Toe Alignment
    if setup["Front Toe"] >= 0:  # Toe-Out focus
        entry_rot += setup["Front Toe"] * 4.5  # Crisp initial steering rack responsiveness
        mid_und += setup["Front Toe"] * 1.5   # Scrub causes drag resistance mid-phase
    else:  # Toe-In
        entry_rot -= abs(setup["Front Toe"]) * 3.0
        hs_stab += abs(setup["Front Toe"]) * 2.0  # Straight-line tracking damping

    # 9. Rear Toe Alignment
    if setup["Rear Toe"] >= 0:  # Toe-In focus
        entry_rot -= setup["Rear Toe"] * 3.5
        mid_und += setup["Rear Toe"] * 2.0
        exit_trac += setup["Rear Toe"] * 5.5  # Locks down rear end to prevent corner exit sliding
    else:  # Rear Toe-Out
        entry_rot += abs(setup["Rear Toe"]) * 7.0   # Highly dangerous structural rotation swing
        exit_trac -= abs(setup["Rear Toe"]) * 9.0  # Asymmetric penalty: Destroys linear application of throttle

    return {
        "Corner Entry Rotation": max(min(int(entry_rot), 100), -100),
        "Mid-Corner Understeer": max(min(int(mid_und), 100), -100),
        "Exit Traction": max(min(int(exit_trac), 100), -100),
        "High-Speed Stability": max(min(int(hs_stab), 100), -100),
    }

# --- CONTROLS IMPLEMENTATION ---
sliders = {}

# Layout generation matching target horizontal bar system structure
metrics_list = ["Corner Entry Rotation", "Mid-Corner Understeer", "Exit Traction", "High-Speed Stability"]

# Calculate physics based on interactive slider layout settings
# Uses explicit 0 baseline alignment structure mirroring the reference mockup image
sliders["Front ARB"] = st.slider("Front ARB", -5, 5, 0)
sliders["Rear ARB"] = st.slider("Rear ARB", -5, 5, 0)
sliders["Brake Bias"] = st.slider("Brake Bias", -5, 5, 0)
sliders["Front Springs"] = st.slider("Front Springs", -5, 5, 0)
sliders["Rear Springs"] = st.slider("Rear Springs", -5, 5, 0)
sliders["Diff Preload"] = st.slider("Diff Preload", -5, 5, 0)
sliders["Rear Wing"] = st.slider("Rear Wing", -5, 5, 0)
sliders["Front Toe"] = st.slider("Front Toe", -5, 5, 0)
sliders["Rear Toe"] = st.slider("Rear Toe", -5, 5, 0)

telemetry = calculate_physics(sliders)

# --- TELEMETRY HORIZONTAL BAR GRAPH CHART ---
metrics_keys = list(telemetry.keys())
metrics_values = list(telemetry.values())

# Dynamic conditional text processing for displaying output labels matching your target file formatting
bar_colors = ['#e63946' if val < 0 else '#2a9d8f' for val in metrics_values]
text_labels = [f"{'+' if val > 0 else ''}{val}%" for val in metrics_values]

fig = go.Figure()
fig.add_trace(go.Bar(
    y=metrics_keys,
    x=metrics_values,
    orientation='h',
    text=text_labels,
    textposition='outside',
    marker_color=bar_colors,
    hoverinfo='none',
    textfont=dict(family="monospace", size=11, color="#222")
))

fig.update_layout(
    xaxis=dict(
        range=[-100, 100],
        tickvals=[-100, 0, 100],
        ticktext=["-100%", "0%", "100%"],
        fixedrange=True,
        gridcolor="#f3f3f3",
        zerolinecolor="#333333",
        zerolinewidth=1.5,
        side="bottom"
    ),
    yaxis=dict(
        autorange="reversed",  # Enforces logical top-down hierarchy
        fixedrange=True,
        showgrid=False,
        tickfont=dict(family="Arial", size=12, color="#333")
    ),
    margin=dict(l=150, r=40, t=10, b=10),
    height=240,
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)"
)

# Insert subtitle alignment metrics anchor tag text directly onto output
st.markdown("<p style='text-align: right; font-size: 0.75rem; color: #555; margin-right: 15px; margin-bottom:-5px;'>Impact (%) →</p>", unsafe_allow_html=True)
st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# --- DYNAMIC RE-CALCULATED OVERALL BALANCE MATRIX READOUT ---
mid_balance = telemetry["Mid-Corner Understeer"]
entry_rotation = telemetry["Corner Entry Rotation"]
stability_index = telemetry["High-Speed Stability"]

if mid_balance > 25:
    status_str = "Strong Understeer"
elif mid_balance > 8:
    status_str = "Mild Understeer"
elif mid_balance < -25:
    status_str = "Strong Oversteer"
elif mid_balance < -8:
    status_str = "Mild Oversteer"
elif entry_rotation > 20 and stability_index < -15:
    status_str = "Loose / Volatile Snap Oversteer"
else:
    status_str = "Neutral Balance"

st.markdown(f"""
    <div class='status-card'>
        <div class='status-title'>Balance Status</div>
        <div class='status-value'>{status_str}</div>
    </div>
""", unsafe_allow_html=True)
