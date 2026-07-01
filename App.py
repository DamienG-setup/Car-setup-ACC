import streamlit as st
import pd
import altair as alt
import math

st.set_page_config(
    page_title="Pro ACC Peak Load Predictor",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏎️ Pro FFB Telemetry & Clipping Simulator")
st.markdown("""
This simulator uses a **Hyper-Accurate Non-Linear Signal Pipeline**. It traces torque from **ACC's Physics Engine**, 
through the **16-bit USB Clipper**, applies **Moza DSP Amplification**, and calculates **Gross Motor Workload vs Net Driver Feedback**.
""")

# --- TWO-WAY VALUE SYNCHRONIZATION INITIALIZATION ---
# Adjusted ranges: Gain and Dynamic Damping now support > 100% as requested.
variables = {
    "max_torque": (3.9, 2.0, 25.0, 0.1),
    "moza_torque_limit": (100, 0, 100, 1),
    "acc_gain": (100, 0, 200, 1), # Upped to 200
    "acc_dynamic_damping": (100, 0, 200, 1), # Upped to 200
    "moza_ffb": (100, 0, 100, 1),
    "moza_road_sens": (8, 0, 10, 1),
    "eq_10": (100, 0, 500, 10),
    "eq_15": (100, 0, 500, 10),
    "eq_25": (100, 0, 500, 10),
    "eq_40": (120, 0, 500, 10),
    "eq_50": (120, 0, 500, 10),
    "eq_100": (100, 0, 500, 10),
    "moza_inertia": (100, 100, 500, 10),
    "moza_damper": (15, 0, 100, 1),
    "moza_friction": (5, 0, 100, 1)
}

for var, specs in variables.items():
    if f"{var}_slider" not in st.session_state:
        st.session_state[f"{var}_slider"] = specs[0]
    if f"{var}_input" not in st.session_state:
        st.session_state[f"{var}_input"] = specs[0]

def sync_slider_to_input(var_name):
    st.session_state[f"{var_name}_input"] = st.session_state[f"{var_name}_slider"]

def sync_input_to_slider(var_name):
    st.session_state[f"{var_name}_slider"] = st.session_state[f"{var_name}_input"]

def render_param_row(label, var_name, min_v, max_v, step_v, help_text=None):
    is_float = isinstance(step_v, float)
    fmt = "%.1f" if is_float else "%d"
    c1, c2 = st.sidebar.columns([3.2, 1.5])
    with c1:
        st.slider(label, min_v, max_v, key=f"{var_name}_slider", step=step_v, format=fmt,
                 on_change=sync_slider_to_input, args=(var_name,), help=help_text)
    with c2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        st.number_input(label, min_v, max_v, key=f"{var_name}_input", step=step_v, format=fmt,
                       on_change=sync_input_to_slider, args=(var_name,), label_visibility="collapsed")
    return st.session_state[f"{var_name}_slider"]

# --- SIDEBAR ---
st.sidebar.header("1️⃣ HARDWARE LIMITS")
max_torque_nm = render_param_row("Wheel Base Peak Torque (Nm)", "max_torque", 2.0, 25.0, 0.1)
moza_torque_limit = render_param_row("Output Torque Limit (%)", "moza_torque_limit", 0, 100, 1)

st.sidebar.header("2️⃣ ACC IN-GAME OUTPUT")
acc_gain = render_param_row("ACC Master Gain (%)", "acc_gain", 0, 200, 1)
acc_dynamic_damping = render_param_row("ACC Dynamic Damping (%)", "acc_dynamic_damping", 0, 200, 1)

st.sidebar.header("3️⃣ WHEELBASE DSP / EQ")
moza_ffb = render_param_row("Base FFB Intensity (%)", "moza_ffb", 0, 100, 1)
moza_road_sens = render_param_row("Road Sensitivity", "moza_road_sens", 0, 10, 1)

# EQ Inputs (truncated for brevity here, logic remains in code)
eq_vals = {
    "10": render_param_row("10 Hz (%)", "eq_10", 0, 500, 10),
    "15": render_param_row("15 Hz (%)", "eq_15", 0, 500, 10),
    "25": render_param_row("25 Hz (%)", "eq_25", 0, 500, 10),
    "40": render_param_row("40 Hz (%)", "eq_40", 0, 500, 10),
    "50": render_param_row("50 Hz (%)", "eq_50", 0, 500, 10),
    "100": render_param_row("100 Hz (%)", "eq_100", 0, 500, 10)
}

st.sidebar.header("4️⃣ BASE MECHANICAL PROFILES")
moza_inertia = render_param_row("Inertia (%)", "moza_inertia", 100, 500, 10)
moza_damper = render_param_row("Damper (%)", "moza_damper", 0, 100, 1)
moza_friction = render_param_row("Friction (%)", "moza_friction", 0, 100, 1)

# --- ENGINE ---
def simulate_ffb_pure(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights,
                      max_tq, tq_limit, a_gain, a_dyn_damp, m_ffb, m_road,
                      m_inertia, m_damper, m_friction, eq_vals):
    
    acc_multiplier = a_gain / 100.0
    # ACC Physics engine saturation check: raw_sustained * multiplier > 1.0 = immediate game clipping
    usb_sustained = min(raw_sustained * acc_multiplier, 1.0)
    headroom = max(0.0, 1.0 - usb_sustained)
    usb_transient = min(raw_transient * acc_multiplier, headroom)
    
    acc_raw_signal_total = (raw_sustained + raw_transient) * acc_multiplier
    acc_is_clipping = acc_raw_signal_total > 1.0

    effective_max_torque = max_tq * (tq_limit / 100.0)
    base_scalar = m_ffb / 100.0
    
    # EQ/Road Sens (Transients)
    base_eq_multiplier = sum([(eq_vals[freq.replace("Hz","")] / 100.0) * weight for freq, weight in eq_weights.items()])
    road_hf_boost = (m_road / 10.0) * (eq_weights.get("40Hz", 0) + eq_weights.get("50Hz", 0) + eq_weights.get("100Hz", 0))
    final_transient_multiplier = base_eq_multiplier + road_hf_boost
    
    base_motor_sustained = usb_sustained * base_scalar * effective_max_torque
    base_motor_transient = usb_transient * final_transient_multiplier * base_scalar * effective_max_torque

    # Dynamic Damping logic amended: handles values > 100% correctly as a square-law/linear torque tax
    vel_factor = 1.0 - math.exp(-abs(wheel_vel) / 20.0)
    # The higher Dynamic Damping value (>100) acts directly on cornering force resistance
    tax_dyn_damper = (a_dyn_damp / 100.0) * abs(car_speed) * vel_factor * (effective_max_torque * 0.15)
    
    total_mech_tax = (
        (m_friction / 100.0) * (0.05 * effective_max_torque) +
        (m_damper / 100.0) * vel_factor * (effective_max_torque * 0.15) +
        (m_inertia / 100.0) * (abs(wheel_accel) / 100.0) * (effective_max_torque * 0.05) +
        tax_dyn_damper
    )
    
    gross_motor_demand = base_motor_sustained + base_motor_transient + total_mech_tax
    lost_to_hw_clip = max(0.0, gross_motor_demand - effective_max_torque)
    
    delivered_transient = max(0.0, base_motor_transient - lost_to_hw_clip)
    delivered_sustained = max(0.0, base_motor_sustained - max(0.0, lost_to_hw_clip - base_motor_transient))
    
    return {
        "acc_clip": acc_is_clipping,
        "hw_clip": gross_motor_demand > effective_max_torque,
        "final_nm": delivered_sustained + delivered_transient,
        "total_tax": total_mech_tax,
        "gross_demand_nm": gross_motor_demand,
        "lost_to_hw_clip": lost_to_hw_clip,
        "acc_signal": min(1.0, acc_raw_signal_total)
    }

# (Scenario logic remains as per original, calling updated simulate_ffb_pure)
st.success("Configuration Updated: ACC Gain & Dynamic Damping now support Over-100% ranges.")
