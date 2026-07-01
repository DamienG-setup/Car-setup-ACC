import streamlit as st
import pandas as pd
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

st.info("👈 **Tuning Controls are in the Sidebar.** Update ranges now allow ACC Gain and Damping up to 200%.")
st.markdown("---")

# --- TWO-WAY VALUE SYNCHRONIZATION INITIALIZATION ---
# Preset defaults optimized for a 3.9Nm Wheelbase
variables = {
    "max_torque": (3.9, 2.0, 25.0, 0.1),
    "moza_torque_limit": (100, 0, 100, 1),
    "acc_gain": (100, 0, 200, 1), # Support for higher percentages
    "acc_dynamic_damping": (100, 0, 200, 1), # Support for higher percentages
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
        st.slider(
            label, min_v, max_v, 
            key=f"{var_name}_slider", step=step_v, format=fmt,
            on_change=sync_slider_to_input, args=(var_name,), help=help_text
        )
    with c2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        st.number_input(
            label, min_v, max_v, 
            key=f"{var_name}_input", step=step_v, format=fmt,
            on_change=sync_input_to_slider, args=(var_name,), label_visibility="collapsed"
        )
    return st.session_state[f"{var_name}_slider"]

# --- SIDEBAR CONFIGURATION ---
st.sidebar.markdown("""
<div style="background-color: #ff4b4b22; padding: 12px; border-radius: 6px; border-left: 5px solid #ff4b4b; margin-bottom: 20px;">
    <span style="font-size: 16px;"><strong>⚙️ TUNING CONTROL PANEL</strong></span>
</div>
""", unsafe_allow_html=True)

st.sidebar.header("1️⃣ HARDWARE LIMITS")
max_torque_nm = render_param_row("Wheel Base Peak Torque (Nm)", "max_torque", 2.0, 25.0, 0.1)
moza_torque_limit = render_param_row("Maximum Output Torque Limit (%)", "moza_torque_limit", 0, 100, 1)

st.sidebar.header("2️⃣ ACC IN-GAME OUTPUT")
acc_gain = render_param_row("ACC Master Gain (%)", "acc_gain", 0, 200, 1)
acc_dynamic_damping = render_param_row("ACC Dynamic Damping (%)", "acc_dynamic_damping", 0, 200, 1)

st.sidebar.header("3️⃣ WHEELBASE DSP / EQ")
moza_ffb = render_param_row("Base FFB Intensity (%)", "moza_ffb", 0, 100, 1)
moza_road_sens = render_param_row("Road Sensitivity (0-10)", "moza_road_sens", 0, 10, 1)

st.sidebar.markdown("**Constructive EQ Boosts**")
eq_10 = render_param_row("10 Hz (%)", "eq_10", 0, 500, 10)
eq_15 = render_param_row("15 Hz (%)", "eq_15", 0, 500, 10)
eq_25 = render_param_row("25 Hz (%)", "eq_25", 0, 500, 10)
eq_40 = render_param_row("40 Hz (%)", "eq_40", 0, 500, 10)
eq_50 = render_param_row("50 Hz (%)", "eq_50", 0, 500, 10)
eq_100 = render_param_row("100 Hz (%)", "eq_100", 0, 500, 10)

st.sidebar.header("4️⃣ BASE MECHANICAL PROFILES")
moza_inertia = render_param_row("Natural Inertia (%)", "moza_inertia", 100, 500, 10)
moza_damper = render_param_row("Wheel Damper (%)", "moza_damper", 0, 100, 1)
moza_friction = render_param_row("Wheel Friction (%)", "moza_friction", 0, 100, 1)

# --- ENGINE ---
def simulate_ffb_pure(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights,
                      max_tq, tq_limit, a_gain, a_dyn_damp, m_ffb, m_road,
                      e10, e15, e25, e40, e50, e100, m_inertia, m_damper, m_friction):
    
    acc_multiplier = a_gain / 100.0
    
    # 1. ACC Software Clipper (Accurate 16-bit USB protocol limit)
    # Even if Gain is 200%, the USB packet signal is capped at 1.0 (100% capacity)
    usb_sustained = min(raw_sustained * acc_multiplier, 1.0)
    headroom = max(0.0, 1.0 - usb_sustained)
    usb_transient = min(raw_transient * acc_multiplier, headroom)
    
    total_game_signal = usb_sustained + usb_transient
    acc_raw_signal_total = (raw_sustained + raw_transient) * acc_multiplier
    acc_is_clipping = acc_raw_signal_total > 1.0

    # 2. Hardware Scaling
    effective_max_torque = max_tq * (tq_limit / 100.0)
    base_scalar = m_ffb / 100.0
    
    # 3. Transient Processing
    base_eq_multiplier = (
        (e10 / 100.0) * eq_weights.get("10Hz", 0.0) +
        (e15 / 100.0) * eq_weights.get("15Hz", 0.0) +
        (e25 / 100.0) * eq_weights.get("25Hz", 0.0) +
        (e40 / 100.0) * eq_weights.get("40Hz", 0.0) +
        (e50 / 100.0) * eq_weights.get("50Hz", 0.0) +
        (e100 / 100.0) * eq_weights.get("100Hz", 0.0)
    )
    road_hf_boost = (m_road / 10.0) * (eq_weights.get("40Hz", 0.0) + eq_weights.get("50Hz", 0.0) + eq_weights.get("100Hz", 0.0))
    final_transient_multiplier = base_eq_multiplier + road_hf_boost
    
    base_motor_sustained = usb_sustained * base_scalar * effective_max_torque
    base_motor_transient = usb_transient * final_transient_multiplier * base_scalar * effective_max_torque

    # 4. Dynamic Damping Mechanical Tax
    vel_factor = 1.0 - math.exp(-abs(wheel_vel) / 20.0)
    # Up to 200% Dynamic Damping creates double the potential resistance compared to stock
    tax_dyn_damper = (a_dyn_damp / 100.0) * abs(car_speed) * vel_factor * (effective_max_torque * 0.15)
    
    total_mech_tax = (
        (m_friction / 100.0) * (0.05 * effective_max_torque) +
        (m_damper / 100.0) * vel_factor * (effective_max_torque * 0.15) +
        (m_inertia / 100.0) * (abs(wheel_accel) / 100.0) * (effective_max_torque * 0.05) +
        tax_dyn_damper
    )
    
    # 5. Hardware Limitation Math
    gross_motor_demand = base_motor_sustained + base_motor_transient + total_mech_tax
    lost_to_hw_clip = max(0.0, gross_motor_demand - effective_max_torque)
    
    delivered_transient = max(0.0, base_motor_transient - lost_to_hw_clip)
    remaining_loss = max(0.0, lost_to_hw_clip - base_motor_transient)
    delivered_sustained = max(0.0, base_motor_sustained - remaining_loss)
    
    return {
        "acc_clip": acc_is_clipping,
        "hw_clip": gross_motor_demand > effective_max_torque,
        "acc_raw_signal": acc_raw_signal_total,
        "acc_signal": total_game_signal,
        "final_nm": delivered_sustained + delivered_transient,
        "total_tax": total_mech_tax,
        "gross_demand_nm": gross_motor_demand,
        "lost_to_hw_clip": lost_to_hw_clip,
        "base_sustained": base_motor_sustained,
        "base_transient": base_motor_transient
    }

def simulate_ffb_pipeline(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights):
    return simulate_ffb_pure(
        raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights,
        max_torque_nm, moza_torque_limit, acc_gain, acc_dynamic_damping,
        moza_ffb, moza_road_sens,
        eq_10, eq_15, eq_25, eq_40, eq_50, eq_100,
        moza_inertia, moza_damper, moza_friction
    )

# --- UI SCENARIOS ---
st.header("🏁 Dynamic Telemetry Scenarios")

scenarios = [
    {
        "name": "Medium Speed Corner",
        "has_bucket": True,
        "eq_weights": {"10Hz": 0.3, "15Hz": 0.3, "25Hz": 0.2, "40Hz": 0.1, "50Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Highest Peak Grip", "sustained": 0.85, "transient": 0.15, "car_speed": 0.5, "w_vel": 4.0, "w_accel": 6.0},
            {"name": "Understeer Slip", "sustained": 0.50, "transient": 0.20, "car_speed": 0.5, "w_vel": 9.0, "w_accel": 14.0} 
        ]
    },
    {
        "name": "High-Speed Scrub",
        "has_bucket": True,
        "eq_weights": {"10Hz": 0.2, "15Hz": 0.2, "25Hz": 0.3, "40Hz": 0.2, "50Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Corner Peak", "sustained": 1.10, "transient": 0.20, "car_speed": 1.0, "w_vel": 2.0, "w_accel": 4.0},
            {"name": "Heavy Scrub", "sustained": 1.00, "transient": 0.25, "car_speed": 1.0, "w_vel": 5.0, "w_accel": 10.0} 
        ]
    },
    {
        "name": "Curb Strike",
        "has_bucket": False,
        "eq_weights": {"15Hz": 0.2, "40Hz": 0.2, "50Hz": 0.3, "100Hz": 0.3}, 
        "phases": [
            {"name": "Impact", "sustained": 0.35, "transient": 1.60, "car_speed": 0.7, "w_vel": 10.0, "w_accel": 50.0},
            {"name": "Post-Curb", "sustained": 0.30, "transient": 0.90, "car_speed": 0.7, "w_vel": 15.0, "w_accel": 20.0}
        ]
    }
]

cols = st.columns(3)
for idx, scene in enumerate(scenarios):
    phase_results = []
    for p in scene["phases"]:
        res = simulate_ffb_pipeline(p["sustained"], p["transient"], p["car_speed"], p["w_vel"], p["w_accel"], scene["eq_weights"])
        res["phase_name"] = p["name"]
        phase_results.append(res)
        
    worst_res = max(phase_results, key=lambda x: x["gross_demand_nm"])
    
    with cols[idx]:
        st.markdown(f"### {scene['name']}")
        if worst_res["acc_clip"]:
            st.error("🟥 ACC CLIPPING")
        elif worst_res["hw_clip"]:
            st.warning("🟧 HW CLIPPING")
        else:
            st.success("🟩 CLEAN")
            
        st.metric("Net Force", f"{worst_res['final_nm']:.2f} Nm")
        st.caption(f"Gross Request: {worst_res['gross_demand_nm']:.2f} Nm")
        st.progress(min(1.0, worst_res['gross_demand_nm']/max_torque_nm))
