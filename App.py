import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(
    page_title="Pro ACC Peak Load Predictor",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏎️ Pro FFB Telemetry & Clipping Simulator")
st.markdown("""
This simulator uses an updated **Dynamic Signal Pipeline Model**. It traces torque from **ACC's Physics Engine**, 
through the **Game's Software Clipper**, applies **Weighted DSP Frequency Bands**, and factors in the **Physical Motor Hardware Budget**.
""")

# Prominent alert to make the control panel location immediately obvious
st.info("👈 **Tuning Controls are located in the Left Sidebar Panel.** Click the arrow icon ( `>` ) in the top-left corner if it is collapsed.")
st.markdown("---")

# --- TWO-WAY VALUE SYNCHRONIZATION INITIALIZATION ---
# Format: { var_name: (default, min, max, step) }
variables = {
    "max_torque": (3.9, 2.0, 25.0, 0.1),
    "moza_torque_limit": (100, 0, 100, 1),
    "acc_gain": (95, 0, 100, 1),
    "acc_dynamic_damping": (100, 0, 100, 1),
    "moza_ffb": (100, 0, 100, 1),
    "moza_road_sens": (10, 0, 10, 1),
    "eq_10": (100, 0, 500, 10),
    "eq_15": (150, 0, 500, 10),
    "eq_25": (100, 0, 500, 10),
    "eq_40": (100, 0, 500, 10),
    "eq_60": (100, 0, 500, 10),
    "eq_100": (100, 0, 500, 10),
    "moza_inertia": (200, 100, 500, 10),
    "moza_damper": (40, 0, 100, 1),
    "moza_friction": (15, 0, 100, 1)
}

# Pre-populate session state keys to avoid cross-talk drift
for var, specs in variables.items():
    if f"{var}_slider" not in st.session_state:
        st.session_state[f"{var}_slider"] = specs[0]
    if f"{var}_input" not in st.session_state:
        st.session_state[f"{var}_input"] = specs[0]

# Callbacks for instantaneous bidirectional sync
def sync_slider_to_input(var_name):
    st.session_state[f"{var_name}_input"] = st.session_state[f"{var_name}_slider"]

def sync_input_to_slider(var_name):
    st.session_state[f"{var_name}_slider"] = st.session_state[f"{var_name}_input"]

def render_param_row(label, var_name, min_v, max_v, step_v, help_text=None):
    c1, c2 = st.sidebar.columns([3.2, 1.5])
    with c1:
        val_from_slider = st.slider(
            label, min_v, max_v, 
            key=f"{var_name}_slider", 
            step=step_v, 
            on_change=sync_slider_to_input, 
            args=(var_name,), 
            help=help_text
        )
    with c2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        val_from_input = st.number_input(
            label, min_v, max_v, 
            key=f"{var_name}_input", 
            step=step_v, 
            on_change=sync_input_to_slider, 
            args=(var_name,), 
            label_visibility="collapsed"
        )
    return val_from_slider

# --- SIDEBAR: PIPELINE CONFIGURATION ---
st.sidebar.markdown("""
<div style="background-color: #ff4b4b22; padding: 12px; border-radius: 6px; border-left: 5px solid #ff4b4b; margin-bottom: 20px;">
    <span style="font-size: 16px;"><strong>⚙️ TUNING CONTROL PANEL</strong></span><br>
    <small>Adjust parameters instantly using either the sliders or input boxes side-by-side.</small>
</div>
""", unsafe_allow_html=True)

st.sidebar.header("1️⃣ HARDWARE LIMITS")
max_torque_nm = render_param_row("Wheel Base Peak Torque (Nm)", "max_torque", 2.0, 25.0, 0.1, help_text="The absolute maximum physical rating of your wheelbase.")
moza_torque_limit = render_param_row("Maximum Output Torque Limit (%)", "moza_torque_limit", 0, 100, 1, help_text="The software torque cap (e.g., Moza Pit House limiter).")

st.sidebar.header("2️⃣ ACC IN-GAME OUTPUT")
acc_gain = render_param_row("ACC Master Gain (%)", "acc_gain", 0, 100, 1, help_text="Higher gain causes Kunos physics to clip before reaching the wheelbase.")
acc_dynamic_damping = render_param_row("ACC Dynamic Damping (%)", "acc_dynamic_damping", 0, 100, 1, help_text="Gyroscopic damping at high speeds.")

st.sidebar.header("3️⃣ WHEELBASE DSP / EQ")
moza_ffb = render_param_row("Base FFB Intensity (%)", "moza_ffb", 0, 100, 1)
moza_road_sens = render_param_row("Road Sensitivity (0-10)", "moza_road_sens", 0, 10, 1, help_text="Master multiplier for high-frequency bands.")

st.sidebar.markdown("**Constructive EQ Boosts (Transient Scalers)**")
eq_10 = render_param_row("10 Hz (Body Roll/Weight) (%)", "eq_10", 0, 500, 10)
eq_15 = render_param_row("15 Hz (Suspension/Kerb) (%)", "eq_15", 0, 500, 10)
eq_25 = render_param_row("25 Hz (ABS/Engine) (%)", "eq_25", 0, 500, 10)
eq_40 = render_param_row("40 Hz (Textures/Slips) (%)", "eq_40", 0, 500, 10)
eq_60 = render_param_row("60 Hz (Road Noise/Vibes) (%)", "eq_60", 0, 500, 10)
eq_100 = render_param_row("100 Hz (High Freq Details) (%)", "eq_100", 0, 500, 10)

st.sidebar.header("4️⃣ BASE MECHANICAL PROFILES")
st.sidebar.markdown("*Set the base resistance percentages of your wheelbase software.*")
moza_inertia = render_param_row("Natural Inertia (%)", "moza_inertia", 100, 500, 10, help_text="Min is 100% (Base hardware weight).")
moza_damper = render_param_row("Wheel Damper (%)", "moza_damper", 0, 100, 1)
moza_friction = render_param_row("Wheel Friction (%)", "moza_friction", 0, 100, 1)


# --- CORE SIMULATION PIPELINE ENGINE (PURE MATHS) ---
def simulate_ffb_pure(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights,
                      max_tq, tq_limit, a_gain, a_dyn_damp, m_ffb, m_road,
                      e10, e15, e25, e40, e60, e100, m_inertia, m_damper, m_friction):
    
    acc_multiplier = a_gain / 100.0
    sustained_game_signal = raw_sustained * acc_multiplier
    
    game_clip_sustained = min(sustained_game_signal, 1.0)
    headroom = max(0.0, 1.0 - game_clip_sustained)
    
    transient_game_signal = min(raw_transient * acc_multiplier, headroom)
    total_game_signal = game_clip_sustained + transient_game_signal
    
    acc_raw_signal_total = (raw_sustained + raw_transient) * acc_multiplier
    acc_is_clipping = acc_raw_signal_total >= 1.0

    effective_max_torque = max_tq * (tq_limit / 100.0)

    base_scalar = m_ffb / 100.0
    road_sens_scalar = m_road / 10.0
    
    weighted_eq = (
        (e10 / 100.0) * eq_weights.get("10Hz", 0.0) +
        (e15 / 100.0) * eq_weights.get("15Hz", 0.0) +
        (e25 / 100.0) * eq_weights.get("25Hz", 0.0) +
        (e40 / 100.0) * eq_weights.get("40Hz", 0.0) +
        (e60 / 100.0) * eq_weights.get("60Hz", 0.0) +
        (e100 / 100.0) * eq_weights.get("100Hz", 0.0)
    ) * road_sens_scalar
    
    dsp_sustained_nm = game_clip_sustained * base_scalar * effective_max_torque
    dsp_transient_nm = (transient_game_signal * weighted_eq) * base_scalar * effective_max_torque

    # Applied abs() to all dynamic elements guaranteeing the conservation of energy laws
    tax_friction = (m_friction / 100.0) * (0.02 * effective_max_torque)
    tax_damper = (m_damper / 100.0) * (abs(wheel_vel) / 25.0) * (effective_max_torque * 0.15) 
    tax_inertia = (m_inertia / 100.0) * (abs(wheel_accel) / 80.0) * (effective_max_torque * 0.20)
    active_dyn_damper = (a_dyn_damp / 100.0) * abs(car_speed) * (abs(wheel_vel) / 25.0) * (effective_max_torque * 0.15)
    
    total_mech_tax = tax_friction + tax_damper + tax_inertia + active_dyn_damper
    
    # Safe division fallback preventing division by zero constraints
    safe_div = max(0.0001, effective_max_torque)
    damping_ratio = max(0.05, 1.0 - (total_mech_tax / safe_div))
    
    dampened_transients = dsp_transient_nm * damping_ratio
    adjusted_requested_nm = dsp_sustained_nm + dampened_transients

    final_output_nm = min(adjusted_requested_nm, effective_max_torque)
    hardware_is_clipping = adjusted_requested_nm > effective_max_torque
    
    return {
        "acc_clip": acc_is_clipping,
        "hw_clip": hardware_is_clipping,
        "acc_raw_signal": acc_raw_signal_total,
        "acc_signal": total_game_signal,
        "effective_torque": effective_max_torque,
        "dsp_sustained": dsp_sustained_nm,
        "dsp_transient": dsp_transient_nm,
        "total_tax": total_mech_tax,
        "tax_friction": tax_friction,
        "tax_damper": tax_damper,
        "tax_inertia": tax_inertia,
        "dyn_damp_tax": active_dyn_damper,
        "requested_nm": adjusted_requested_nm,
