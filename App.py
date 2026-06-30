import streamlit as st
import plotly.graph_objects as go

# Initialize viewport configuration
st.set_page_config(
    page_title="GT3 Advanced Telemetry Sandbox",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom premium CSS layout injection
st.markdown("""
    <style>
    .main .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 550px; }
    h1 { text-align: center; font-family: 'Helvetica Neue', Arial, sans-serif; font-weight: 600; color: #111; margin-bottom: 0.1rem; font-size: 1.6rem; }
    .subtitle { text-align: center; font-family: monospace; color: #666; margin-bottom: 1.5rem; font-size: 0.8rem; letter-spacing: 1px; }
    
    /* THE SCROLL HIGHWAY: Reserves an 18% dead-zone on the right edge of sliders for safe mobile thumb swiping */
    div[data-testid="stSlider"] { 
        padding-right: 18% !important; 
        margin-bottom: 8px;
    }
    
    .status-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 14px;
        text-align: center;
        margin-top: 15px;
        margin-bottom: 15px;
        border: 1px solid #eaeaea;
    }
    .status-title { font-size: 0.7rem; color: #888; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 500; }
    .status-value { font-size: 1.1rem; font-weight: 400; color: #222; margin-top: 4px; font-family: monospace; }
    .section-header { font-size: 0.95rem; font-weight: 600; color: #111; margin-top: 20px; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 4px; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1>Car Setup Balance Simulator</h1>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>GT3 TELEMETRY CORE v3.5 (VALIDATED)</div>", unsafe_allow_html=True)

# --- VALIDATED ASYMMETRIC VEHICLE DYNAMICS ENGINE ---
def calculate_advanced_physics(setup):
    entry_rot = 0.0
    entry_stab = 0.0
    mid_und = 0.0
    mid_ove = 0.0
    exit_trac = 0.0
    brake_perf = 0.0
    straight_spd = 0.0
    hs_stab = 0.0
    aero_drag = 0.0

    # 1. Anti-Roll Bars (ARB)
    if setup["Front ARB"] >= 0:
        entry_rot -= setup["Front ARB"] * 3.5
        entry_stab += setup["Front ARB"] * 2.0
        mid_und += setup["Front ARB"] * 4.5
    else:
        entry_rot += abs(setup["Front ARB"]) * 4.0
        entry_stab -= abs(setup["Front ARB"]) * 3.0
        mid_und -= abs(setup["Front ARB"]) * 3.5

    if setup["Rear ARB"] >= 0:
        entry_rot += setup["Rear ARB"] * 4.0
        mid_ove += setup["Rear ARB"] * 5.0
        exit_trac -= setup["Rear ARB"] * 5.5
    else:
        entry_rot -= abs(setup["Rear ARB"]) * 2.5
        mid_ove -= abs(setup["Rear ARB"]) * 3.5
        exit_trac += abs(setup["Rear ARB"]) * 4.0

    # 2. Wheel Springs
    if setup["Front Springs"] >= 0:
        entry_stab += setup["Front Springs"] * 2.5
        mid_und += setup["Front Springs"] * 3.5
        hs_stab += setup["Front Springs"] * 3.0
    else:
        entry_stab -= abs(setup["Front Springs"]) * 4.5
        mid_und -= abs(setup["Front Springs"]) * 2.5
        hs_stab -= abs(setup["Front Springs"]) * 5.0

    if setup["Rear Springs"] >= 0:
        entry_rot += setup["Rear Springs"] * 3.0
        mid_ove += setup["Rear Springs"] * 4.0
        exit_trac -= setup["Rear Springs"] * 4.5
    else:
        entry_rot -= abs(setup["Rear Springs"]) * 1.5
        mid_ove -= abs(setup["Rear Springs"]) * 3.0
        exit_trac += abs(setup["Rear Springs"]) * 6.0

    # 3. Braking Parameters
    brake_perf += setup["Brake Pressure"] * 8.5
    if setup["Brake Pressure"] > 2:
        entry_stab -= (setup["Brake Pressure"] - 2) * 4.5

    if setup["Brake Bias"] >= 0:
        entry_rot -= setup["Brake Bias"] * 4.5
        entry_stab += setup["Brake Bias"] * 5.0
        mid_und += setup["Brake Bias"] * 2.0
        brake_perf += setup["Brake Bias"] * 1.5
    else:
        entry_rot += abs(setup["Brake Bias"]) * 8.0
        entry_stab -= abs(setup["Brake Bias"]) * 7.5
        mid_ove += abs(setup["Brake Bias"]) * 4.0

    # 4. Differential Preload
    if setup["Diff Preload"] >= 0:
        entry_rot -= setup["Diff Preload"] * 3.5
        entry_stab += setup["Diff Preload"] * 4.0
        mid_und += setup["Diff Preload"] * 2.5
        exit_trac += setup["Diff Preload"] * 3.5
    else:
        entry_rot += abs(setup["Diff Preload"]) * 5.0
        entry_stab -= abs(setup["Diff Preload"]) * 3.5
        exit_trac -= abs(setup["Diff Preload"]) * 5.0

    # 5. Rear Wing Aerodynamics
    if setup["Rear Wing"] >= 0:
        mid_und += setup["Rear Wing"] * 2.5
        mid_ove -= setup["Rear Wing"] * 4.0
        exit_trac += setup["Rear Wing"] * 3.0
        straight_spd -= setup["Rear Wing"] * 7.5
        hs_stab += setup["Rear Wing"] * 8.5
        aero_drag += setup["Rear Wing"] * 9.0
    else:
        mid_ove += abs(setup["Rear Wing"]) * 3.5
        exit_trac -= abs(setup["Rear Wing"]) * 5.0
        straight_spd += abs(setup["Rear Wing"]) * 6.0
        hs_stab -= abs(setup["Rear Wing"]) * 12.0
        aero_drag -= abs(setup["Rear Wing"]) * 8.0

    # 6. Alignment Wheel Geometry (Toe & Camber)
    if setup["Front Toe"] >= 0:  # Toe-Out
        entry_rot += setup["Front Toe"] * 4.0
        mid_und += setup["Front Toe"] * 1.5
        straight_spd -= setup["Front Toe"] * 2.5
        aero_drag += setup["Front Toe"] * 1.5
    else:  # Toe-In
        entry_rot -= abs(setup["Front Toe"]) * 2.5
        entry_stab += abs(setup["Front Toe"]) * 2.0
        straight_spd -= abs(setup["Front Toe"]) * 1.5

    if setup["Rear Toe"] >= 0:  # Toe-In
        entry_rot -= setup["Rear Toe"] * 3.0
        exit_trac += setup["Rear Toe"] * 4.5
        straight_spd -= setup["Rear Toe"] * 3.0
        aero_drag += setup["Rear Toe"] * 1.5
    else:  # Toe-Out (Volatile)
        entry_rot += abs(setup["Rear Toe"]) * 7.5
        exit_trac -= abs(setup["Rear Toe"]) * 8.0
        entry_stab -= abs(setup["Rear Toe"]) * 6.0

    if setup["Front Camber"] >= 0:
        entry_rot += setup["Front Camber"] * 3.5
        mid_und -= setup["Front Camber"] * 4.0
        brake_perf -= setup["Front Camber"] * 2.0
    else:
        mid_und += abs(setup["Front Camber"]) * 3.0

    if setup["Rear Camber"] >= 0:
        mid_ove -= setup["Rear Camber"] * 3.5
        exit_trac += setup["Rear Camber"] * 3.0
        straight_spd -= setup["Rear Camber"] * 1.5
    else:
        mid_ove += abs(setup["Rear Camber"]) * 4.0
        exit_trac -= abs(setup["Rear Camber"]) * 5.0

    # 7. Ride Heights & Aero Rake
    straight_spd -= setup["Ride Height"] * 2.0
    hs_stab -= setup["Ride Height"] * 3.5

    if setup["Rake"] >= 0:
        entry_rot += setup["Rake"] * 5.5
        entry_stab -= setup["Rake"] * 4.5
        mid_und -= setup["Rake"] * 4.0
        mid_ove += setup["Rake"] * 4.5
        straight_spd -= setup["Rake"] * 3.0
        aero_drag += setup["Rake"] * 4.0
    else:
        entry_rot -= abs(setup["Rake"]) * 3.5
        entry_stab += abs(setup["Rake"]) * 3.0
        mid_und += abs(setup["Rake"]) * 4.0
        hs_stab += abs(setup["Rake"]) * 4.0

    # 8. Dampers (Transient Load Control)
    if setup["Front Bump"] >= 0:
        entry_rot -= setup["Front Bump"] * 2.0
        entry_stab += setup["Front Bump"] * 3.0
    else:
        entry_rot += abs(setup["Front Bump"]) * 2.5
        entry_stab -= abs(setup["Front Bump"]) * 2.0

    if setup["Rear Rebound"] >= 0:
        entry_rot += setup["Rear Rebound"] * 4.0
        entry_stab -= setup["Rear Rebound"] * 3.5
    else:
        entry_rot -= abs(setup["Rear Rebound"]) * 3.0
        entry_stab += abs(setup["Rear Rebound"]) * 2.5

    if setup["Rear Bump"] >= 0:
        exit_trac -= setup["Rear Bump"] * 4.5
    else:
        exit_trac += abs(setup["Rear Bump"]) * 3.5

    if setup["Front Rebound"] >= 0:
        mid_und -= setup["Front Rebound"] * 3.0
    else:
        mid_und += abs(setup["Front Rebound"]) * 3.5

    # 9. Bumpstops
    if setup["Bumpstop Range"] < 0:
        mid_und += abs(setup["Bumpstop Range"]) * 3.5
        exit_trac -= abs(setup["Bumpstop Range"]) * 4.0
        hs_stab += abs(setup["Bumpstop Range"]) * 2.5
    
    mid_und += setup["Bumpstop Rate"] * 4.0
    exit_trac -= setup["Bumpstop Rate"] * 4.5

    return {
        "Corner Entry Rotation": max(min(int(entry_rot), 100), -100),
        "Corner Entry Stability": max(min(int(entry_stab), 100), -100),
        "Mid-Corner Understeer": max(min(int(mid_und), 100), -100),
        "Mid-Corner Oversteer": max(min(int(mid_ove), 100), -100),
        "Exit Traction": max(min(int(exit_trac), 100), -100),
        "Braking Performance": max(min(int(brake_perf), 100), -100),
        "Aerodynamic Drag": max(min(int(aero_drag), 100), -100),
        "Straight Line Speed": max(min(int(straight_spd), 100), -100),
        "High-Speed Stability": max(min(int(hs_stab), 100), -100),
    }

# --- CONTROL INTERFACE DISPLAY ---
sliders = {}

st.markdown("<div class='section-header'>1. Mechanical Roll & Stiffness</div>", unsafe_allow_html=True)
sliders["Front ARB"] = st.slider("Front ARB (Soft ↔ Stiff)", -5, 5, 0)
sliders["Rear ARB"] = st.slider("Rear ARB (Soft ↔ Stiff)", -5, 5, 0)
sliders["Front Springs"] = st.slider("Front Springs (Soft ↔ Stiff)", -5, 5, 0)
sliders["Rear Springs"] = st.slider("Rear Springs (Soft ↔ Stiff)", -5, 5, 0)

st.markdown("<div class='section-header'>2. Braking & Longitudinal Torque</div>", unsafe_allow_html=True)
sliders["Brake Pressure"] = st.slider("Brake Pressure (Low ↔ High Force)", -5, 5, 0)
sliders["Brake Bias"] = st.slider("Brake Bias (Rearward ↔ Forward)", -5, 5, 0)
sliders["Diff Preload"] = st.slider("Differential Preload (Low ↔ High)", -5, 5, 0)

st.markdown("<div class='section-header'>3. Aerodynamics & Geometry Platform</div>", unsafe_allow_html=True)
sliders["Rear Wing"] = st.slider("Rear Wing (Low ↔ High Downforce)", -5, 5, 0)
sliders["Ride Height"] = st.slider("Base Ride Height (Low ↔ High)", -5, 5, 0)
sliders["Rake"] = st.slider("Aero Rake Angle (Negative ↔ Positive)", -5, 5, 0)

st.markdown("<div class='section-header'>4. Wheel Alignment (Scrub Vectors)</div>", unsafe_allow_html=True)
sliders["Front Toe"] = st.slider("Front Toe (Toe-In ↔ Toe-Out)", -5, 5, 0)
sliders["Rear Toe"] = st.slider("Rear Toe (Toe-Out ↔ Toe-In)", -5, 5, 0)
sliders["Front Camber"] = st.slider("Front Camber (Standard ↔ Aggressive Negative)", -5, 5, 0)
sliders["Rear Camber"] = st.slider("Rear Camber (Standard ↔ Aggressive Negative)", -5, 5, 0)

st.markdown("<div class='section-header'>5. Hydraulic Dampers (Transient Weight Control)</div>", unsafe_allow_html=True)
sliders["Front Bump"] = st.slider("Front Bump / Compression (Soft ↔ Stiff)", -5, 5, 0)
sliders["Front Rebound"] = st.slider("Front Rebound / Extension (Soft ↔ Stiff)", -5, 5, 0)
sliders["Rear Bump"] = st.slider("Rear Bump / Compression (Soft ↔ Stiff)", -5, 5, 0)
sliders["Rear Rebound"] = st.slider("Rear Rebound / Extension (Soft ↔ Stiff)", -5, 5, 0)

st.markdown("<div class='section-header'>6. Travel Boundaries (Bumpstop Pack)</div>", unsafe_allow_html=True)
sliders["Bumpstop Range"] = st.slider("Bumpstop Clearance Range (Low ↔ High Clearance)", -5, 5, 0)
sliders["Bumpstop Rate"] = st.slider("Bumpstop Spring Rate Stiffness (Soft ↔ Stiff)", -5, 5, 0)

telemetry = calculate_advanced_physics(sliders)

# --- GRAPHICAL OUTPUT LAYOUT CONFIGURATION ---
st.markdown("---")
st.markdown("### Live Telemetry Output Analysis")

m_keys = list(telemetry.keys())
m_vals = list(telemetry.values())

bar_colors = ['#e63946' if val < 0 else '#2a9d8f' for val in m_vals]
text_labels = [f"{'+' if val > 0 else ''}{val}%" for val in m_vals]

fig = go.Figure()
fig.add_trace(go.Bar(
    y=m_keys,
    x=m_vals,
    orientation='h',
    text=text_labels,
    textposition='outside',
    marker_color=bar_colors,
    hoverinfo='none',
    textfont=dict(family="monospace", size=10, color="#222")
))

fig.update_layout(
    xaxis=dict(
        range=[-100, 100],
        tickvals=[-100, 0, 100],
        ticktext=["-100%", "0%", "100%"],
        fixedrange=True,
        gridcolor="#f3f3f3",
        zerolinecolor="#333333",
        zerolinewidth=1.5
    ),
    yaxis=dict(
        autorange="reversed",
        fixedrange=True,
        showgrid=False,
        tickfont=dict(family="Arial", size=11, color="#333")
    ),
    margin=dict(l=165, r=40, t=10, b=10),
    height=340,
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)"
)

st.markdown("<p style='text-align: right; font-size: 0.7rem; color: #555; margin-right: 15px; margin-bottom:-5px;'>Impact (%) →</p>", unsafe_allow_html=True)
st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# --- COMPREHENSIVE STATUS OUTPUT ANALYSIS MATRIX ---
mid_und_val = telemetry["Mid-Corner Understeer"]
mid_ove_val = telemetry["Mid-Corner Oversteer"]
entry_stab_val = telemetry["Corner Entry Stability"]
hs_stab_val = telemetry["High-Speed Stability"]

if hs_stab_val < -40:
    status_str = "💀 Aero Stall: Critical High-Speed Spin Risk!"
elif mid_und_val > 20:
    status_str = "Strong Understeer Balance"
elif mid_ove_val > 20:
    status_str = "Strong Oversteer Bias"
elif entry_stab_val < -15:
    status_str = "Unstable / Volatile Snap Oversteer Risk"
elif mid_und_val > 5:
    status_str = "Mild Understeer Character"
elif mid_ove_val > 5:
    status_str = "Mild Oversteer Character"
else:
    status_str = "Neutral Balance / Balanced Mechanical Tracking"

st.markdown(f"""
    <div class='status-card'>
        <div class='status-title'>Calculated Balance Status</div>
        <div class='status-value'>{status_str}</div>
    </div>
""", unsafe_allow_html=True)
