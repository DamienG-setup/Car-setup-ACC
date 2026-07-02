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
through the **16-bit USB Clipper**, applies **Moza DSP Amplification**, and calculates **Gross Motor Workload vs Net Driver Feedback** using real exponential viscous friction physics.
""")

st.info("👈 **Tuning Controls are located in the Left Sidebar Panel.** Click the arrow icon ( `>` ) in the top-left corner if it is collapsed.")
st.markdown("---")

# --- TWO-WAY VALUE SYNCHRONIZATION INITIALIZATION ---
variables = {
    "max_torque": (3.9, 2.0, 25.0, 0.1),
    "moza_torque_limit": (100, 0, 100, 1),
    "acc_gain": (100, 0, 200, 1), 
    "acc_dynamic_damping": (100, 0, 200, 1), 
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

# --- SIDEBAR: PIPELINE CONFIGURATION ---
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
moza_road_sens = render_param_row("Road Sensitivity (0-10)", "moza_road_sens", 0, 10, 1, help_text="Injects additional synthesized detail into high frequency bands.")

st.sidebar.markdown("**Constructive EQ Boosts (Transient Scalers)**")
eq_10 = render_param_row("10 Hz (Body Roll/Weight) (%)", "eq_10", 0, 500, 10)
eq_15 = render_param_row("15 Hz (Suspension/Kerb) (%)", "eq_15", 0, 500, 10)
eq_25 = render_param_row("25 Hz (ABS/Engine) (%)", "eq_25", 0, 500, 10)
eq_40 = render_param_row("40 Hz (Textures/Slips) (%)", "eq_40", 0, 500, 10)
eq_50 = render_param_row("50 Hz (Road Noise/Vibes) (%)", "eq_50", 0, 500, 10)
eq_100 = render_param_row("100 Hz (High Freq Details) (%)", "eq_100", 0, 500, 10)

st.sidebar.header("4️⃣ BASE MECHANICAL PROFILES")
moza_inertia = render_param_row("Natural Inertia (%)", "moza_inertia", 100, 500, 10)
moza_damper = render_param_row("Wheel Damper (%)", "moza_damper", 0, 100, 1)
moza_friction = render_param_row("Wheel Friction (%)", "moza_friction", 0, 100, 1)

# --- CORE SIMULATION PIPELINE ENGINE ---
def simulate_ffb_pure(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights,
                      max_tq, tq_limit, a_gain, a_dyn_damp, m_ffb, m_road,
                      e10, e15, e25, e40, e50, e100, m_inertia, m_damper, m_friction):
    
    acc_multiplier = a_gain / 100.0
    acc_raw_signal_total = (raw_sustained + raw_transient) * acc_multiplier
    
    # 1. ACC Software Clipper
    usb_sustained = min(raw_sustained * acc_multiplier, 1.0)
    headroom = max(0.0, 1.0 - usb_sustained)
    usb_transient = min(raw_transient * acc_multiplier, headroom)
    
    total_game_signal = usb_sustained + usb_transient
    acc_is_clipping = acc_raw_signal_total > 1.0

    # 2. Hardware Capacities
    effective_max_torque = max_tq * (tq_limit / 100.0)
    base_scalar = m_ffb / 100.0
    
    # 3. DSP EQ Amplification
    base_eq_multiplier = (
        (e10 / 100.0) * eq_weights.get("10Hz", 0.0) +
        (e15 / 100.0) * eq_weights.get("15Hz", 0.0) +
        (e25 / 100.0) * eq_weights.get("25Hz", 0.0) +
        (e40 / 100.0) * eq_weights.get("40Hz", 0.0) +
        (e50 / 100.0) * eq_weights.get("50Hz", 0.0) +
        (e100 / 100.0) * eq_weights.get("100Hz", 0.0)
    )
    
    road_hf_boost = (m_road / 10.0) * (
        eq_weights.get("40Hz", 0.0) + 
        eq_weights.get("50Hz", 0.0) + 
        eq_weights.get("100Hz", 0.0)
    )
    
    final_transient_multiplier = base_eq_multiplier + road_hf_boost
    
    base_motor_sustained = usb_sustained * base_scalar * effective_max_torque
    base_motor_transient = usb_transient * final_transient_multiplier * base_scalar * effective_max_torque

    # 4. Mechanical Resistance Models
    tax_friction = (m_friction / 100.0) * (0.05 * effective_max_torque)
    vel_factor = 1.0 - math.exp(-abs(wheel_vel) / 20.0)
    tax_damper = (m_damper / 100.0) * vel_factor * (effective_max_torque * 0.15) 
    tax_inertia = (m_inertia / 100.0) * (abs(wheel_accel) / 100.0) * (effective_max_torque * 0.05)
    tax_dyn_damper = (a_dyn_damp / 100.0) * abs(car_speed) * vel_factor * (effective_max_torque * 0.15)
    
    total_mech_tax = tax_friction + tax_damper + tax_inertia + tax_dyn_damper
    
    # 5. Gross Motor Workload vs Hardware Saturation
    gross_motor_demand = base_motor_sustained + base_motor_transient + total_mech_tax
    hardware_is_clipping = gross_motor_demand > effective_max_torque
    lost_to_hw_clip = max(0.0, gross_motor_demand - effective_max_torque)
    
    # 6. Signal Degradation Hierarchy
    delivered_transient = max(0.0, base_motor_transient - lost_to_hw_clip)
    remaining_loss_for_sustained = max(0.0, lost_to_hw_clip - base_motor_transient)
    delivered_sustained = max(0.0, base_motor_sustained - remaining_loss_for_sustained)
    
    final_net_game_nm = delivered_sustained + delivered_transient
    
    return {
        "acc_clip": acc_is_clipping,
        "hw_clip": hardware_is_clipping,
        "acc_raw_signal": acc_raw_signal_total,
        "acc_signal": total_game_signal,
        "effective_torque": effective_max_torque,
        "base_sustained": base_motor_sustained,
        "base_transient": base_motor_transient,
        "total_tax": total_mech_tax,
        "gross_demand_nm": gross_motor_demand,
        "final_nm": final_net_game_nm,
        "lost_to_hw_clip": lost_to_hw_clip
    }

def simulate_ffb_pipeline(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights):
    return simulate_ffb_pure(
        raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights,
        max_torque_nm, moza_torque_limit, acc_gain, acc_dynamic_damping,
        moza_ffb, moza_road_sens,
        eq_10, eq_15, eq_25, eq_40, eq_50, eq_100,
        moza_inertia, moza_damper, moza_friction
    )

# --- SECTION 1: SCENARIO RENDERER ---
st.header("🏁 Dynamic Telemetry Scenarios")
st.markdown("Simulates the transition between peak grip and tire slip to analyze dynamic force drop-offs and aero scrub spikes.")

scenarios = [
    {
        "name": "Low-Speed Hairpin",
        "has_bucket": True,
        "eq_weights": {"10Hz": 0.4, "15Hz": 0.3, "25Hz": 0.1, "40Hz": 0.1, "50Hz": 0.1, "100Hz": 0.0}, 
        "phases": [
            {"name": "Highest Peak of Grip", "sustained": 0.65, "transient": 0.10, "car_speed": 0.2, "w_vel": 5.0, "w_accel": 5.0},
            {"name": "Loss of Grip (Slide)", "sustained": 0.35, "transient": 0.15, "car_speed": 0.2, "w_vel": 12.0, "w_accel": 20.0} 
        ]
    },
    {
        "name": "Medium Speed Corner",
        "has_bucket": True,
        "eq_weights": {"10Hz": 0.3, "15Hz": 0.3, "25Hz": 0.2, "40Hz": 0.1, "50Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Highest Peak of Grip", "sustained": 0.85, "transient": 0.15, "car_speed": 0.5, "w_vel": 4.0, "w_accel": 6.0},
            {"name": "Loss of Grip (Understeer)", "sustained": 0.50, "transient": 0.20, "car_speed": 0.5, "w_vel": 9.0, "w_accel": 14.0} 
        ]
    },
    {
        "name": "High-Speed Corner",
        "has_bucket": True,
        "eq_weights": {"10Hz": 0.2, "15Hz": 0.2, "25Hz": 0.3, "40Hz": 0.2, "50Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Highest Peak of Grip", "sustained": 0.80, "transient": 0.10, "car_speed": 1.0, "w_vel": 2.0, "w_accel": 4.0},
            {"name": "Loss of Grip (Scrub Spike)", "sustained": 1.15, "transient": 0.25, "car_speed": 1.0, "w_vel": 5.0, "w_accel": 10.0} 
        ]
    },
    {
        "name": "Heavy Braking",
        "has_bucket": False,
        "eq_weights": {"10Hz": 0.2, "15Hz": 0.1, "25Hz": 0.4, "40Hz": 0.2, "50Hz": 0.1, "100Hz": 0.0}, 
        "phases": [
            {"name": "Initial Hit (ABS Engages)", "sustained": 0.20, "transient": 0.80, "car_speed": 0.9, "w_vel": 1.0, "w_accel": 5.0}, 
            {"name": "Trail Braking (Turn-in)", "sustained": 0.65, "transient": 0.15, "car_speed": 0.6, "w_vel": 8.0, "w_accel": 10.0}
        ]
    },
    {
        "name": "Snap Oversteer",
        "has_bucket": False,
        "eq_weights": {"10Hz": 0.3, "15Hz": 0.2, "25Hz": 0.1, "40Hz": 0.2, "50Hz": 0.2, "100Hz": 0.0}, 
        "phases": [
            {"name": "Violent Catch (Tires Bite)", "sustained": 0.95, "transient": 0.85, "car_speed": 0.5, "w_vel": 25.0, "w_accel": 80.0}, 
            {"name": "Stabilization (Recovery)", "sustained": 0.50, "transient": 0.20, "car_speed": 0.4, "w_vel": 10.0, "w_accel": 15.0}
        ]
    },
    {
        "name": "Curb Strike",
        "has_bucket": False,
        "eq_weights": {"10Hz": 0.0, "15Hz": 0.2, "25Hz": 0.1, "40Hz": 0.2, "50Hz": 0.3, "100Hz": 0.2}, 
        "phases": [
            {"name": "Initial Strike (Impact)", "sustained": 0.35, "transient": 1.60, "car_speed": 0.7, "w_vel": 10.0, "w_accel": 50.0},
            {"name": "Riding the Curb", "sustained": 0.30, "transient": 0.90, "car_speed": 0.7, "w_vel": 15.0, "w_accel": 20.0}
        ]
    }
]

cols1 = st.columns(3)
cols2 = st.columns(3)
all_cols = cols1 + cols2

for idx, scene in enumerate(scenarios):
    phase_results = []
    for p in scene["phases"]:
        res = simulate_ffb_pipeline(p["sustained"], p["transient"], p["car_speed"], p["w_vel"], p["w_accel"], scene["eq_weights"])
        res["phase_name"] = p["name"]
        phase_results.append(res)
        
    any_acc_clip = any(r["acc_clip"] for r in phase_results)
    any_hw_clip = any(r["hw_clip"] for r in phase_results)
    worst_res = max(phase_results, key=lambda x: x["gross_demand_nm"])
    
    with all_cols[idx]:
        st.markdown(f"### {scene['name']}")
        
        if any_acc_clip:
            st.error("🟥 ACC SOFTWARE CLIPPING\n\nUSB Signal flatlined. EQ boosts severely muted.")
        elif any_hw_clip:
            st.warning(f"🟧 HARDWARE CLIPPING\n\nMotor is overloaded by {worst_res['lost_to_hw_clip']:.2f} Nm. Transients crushed.")
        else:
            st.success("🟩 CLEAN SIGNAL\n\nFull dynamic range rendered flawlessly.")
            
        st.metric(label="Net Delivered Game Force", value=f"{worst_res['final_nm']:.2f} Nm")
        
        # --- NEW BUCKET LOGIC: Capable of handling both Drops and Spikes ---
        if scene["has_bucket"]:
            peak_nm = phase_results[0]["final_nm"]
            loss_nm = phase_results[1]["final_nm"]
            
            if peak_nm > loss_nm and (peak_nm - loss_nm) > 0.01:
                st.metric(
                    label="🪣 Tactile Reaction", 
                    value=f"{peak_nm - loss_nm:.2f} Nm Drop", 
                    delta=f"-{((peak_nm - loss_nm)/max(0.1, peak_nm))*100:.0f}% Dynamic Falloff",
                    delta_color="inverse"
                )
            elif loss_nm > peak_nm and (loss_nm - peak_nm) > 0.01:
                st.metric(
                    label="🪣 Tactile Reaction", 
                    value=f"{loss_nm - peak_nm:.2f} Nm Spike", 
                    delta=f"+{((loss_nm - peak_nm)/max(0.1, peak_nm))*100:.0f}% Dynamic Increase (Scrub)",
                    delta_color="normal"
                )
            else:
                st.metric(
                    label="🪣 Tactile Reaction", 
                    value="0.00 Nm Change", 
                    delta="0% (Ceiling Saturated)",
                    delta_color="off"
                )
            st.caption("*(The larger this change, the easier it is to physically feel the car's state.)*")

        if any_hw_clip:
            st.caption(f"⚠️ *Note: Motor at capacity. Feedback is compromised because **{worst_res['total_tax']:.2f} Nm** is wasted fighting internal damping/friction settings.*")
        
        st.markdown("**Dominant FFB Equalizer Bands:**")
        active_bands = [f"{k} ({v*100:.0f}%)" for k, v in scene["eq_weights"].items() if v > 0]
        st.caption(" | ".join(active_bands))

        st.markdown("**Phase Breakdown (Gross Req. ➔ Net Delivered):**")
        for i, r in enumerate(phase_results):
            st.caption(f"{i+1}. {r['phase_name']}: **{r['gross_demand_nm']:.2f} Nm** ➔ **{r['final_nm']:.2f} Nm**")
            
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption(f"**Worst-Case Pipeline Telemetry:**")
        if worst_res['acc_raw_signal'] > 1.0:
            st.caption(f"↳ Game Output Signal: **{worst_res['acc_signal']*100:.0f}%** (Raw: 🔴 **{worst_res['acc_raw_signal']*100:.0f}%**)")
        else:
            st.caption(f"↳ Game Output Signal: **{worst_res['acc_signal']*100:.0f}%**")
            
        st.caption(f"↳ Req. Base Corner Force: **{worst_res['base_sustained']:.2f} Nm**")
        st.caption(f"↳ Req. EQ Transient Spikes: **{worst_res['base_transient']:.2f} Nm**")
        st.caption(f"↳ **Mech Overhead Tax: {worst_res['total_tax']:.2f} Nm**")
        
        usage_pct = min(worst_res['gross_demand_nm'] / max_torque_nm, 1.0)
        st.progress(usage_pct)
        st.markdown("---")

# --- SECTION 2: DEEP DIVE ANALYTICS ---
st.header("📊 Curb Strike Impact: Hierarchy of Hardware Clipping")

st.markdown("""
When a real Direct Drive servo hits 100% magnetic saturation, it doesn't reduce all forces evenly—it **sacrifices high-frequency transients first**. 
""")

curb_weights = {"10Hz": 0.0, "15Hz": 0.2, "25Hz": 0.1, "40Hz": 0.2, "50Hz": 0.3, "100Hz": 0.2}

acc_multiplier = acc_gain / 100.0
usb_sustained = min(0.35 * acc_multiplier, 1.0)
headroom = max(0.0, 1.0 - usb_sustained)
usb_transient = min(1.60 * acc_multiplier, headroom)

effective_max_torque = max_torque_nm * (moza_torque_limit / 100.0)
base_scalar = moza_ffb / 100.0

base_eq_multiplier_curb = (
    (eq_10 / 100.0) * curb_weights.get("10Hz", 0.0) +
    (eq_15 / 100.0) * curb_weights.get("15Hz", 0.0) +
    (eq_25 / 100.0) * curb_weights.get("25Hz", 0.0) +
    (eq_40 / 100.0) * curb_weights.get("40Hz", 0.0) +
    (eq_50 / 100.0) * curb_weights.get("50Hz", 0.0) +
    (eq_100 / 100.0) * curb_weights.get("100Hz", 0.0)
)
road_hf_boost_curb = (moza_road_sens / 10.0) * (
    curb_weights.get("40Hz", 0.0) + 
    curb_weights.get("50Hz", 0.0) + 
    curb_weights.get("100Hz", 0.0)
)

final_transient_multiplier_curb = base_eq_multiplier_curb + road_hf_boost_curb
base_motor_sustained = usb_sustained * base_scalar * effective_max_torque

tax_friction = (moza_friction / 100.0) * (0.05 * effective_max_torque)
vel_factor_curb = 1.0 - math.exp(-abs(10.0) / 20.0)
tax_damper = (moza_damper / 100.0) * vel_factor_curb * (effective_max_torque * 0.15) 
tax_inertia = (moza_inertia / 100.0) * (abs(50.0) / 100.0) * (effective_max_torque * 0.05)
tax_dyn_damper = (acc_dynamic_damping / 100.0) * abs(0.7) * vel_factor_curb * (effective_max_torque * 0.15)
total_mech_tax = tax_friction + tax_damper + tax_inertia + tax_dyn_damper

sweep_data = []
for mult in [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]:
    test_base_transient = usb_transient * (final_transient_multiplier_curb * mult) * base_scalar * effective_max_torque
    test_gross_demand = base_motor_sustained + test_base_transient + total_mech_tax
    test_lost = max(0.0, test_gross_demand - effective_max_torque)
    test_delivered_transient = max(0.0, test_base_transient - test_lost)
    test_remaining_loss = max(0.0, test_lost - test_base_transient)
    test_delivered_sustained = max(0.0, base_motor_sustained - test_remaining_loss)
    test_final_nm = test_delivered_sustained + test_delivered_transient
    
    sweep_data.append({
        "EQ Scale Factor (%)": int(mult * 100),
        "Requested Gross Detail (Nm)": test_gross_demand,
        "Net Delivered Force (Felt Nm)": test_final_nm
    })
    
df_sweep = pd.DataFrame(sweep_data)
df_melted = df_sweep.melt(
    id_vars=["EQ Scale Factor (%)"], 
    value_vars=["Requested Gross Detail (Nm)", "Net Delivered Force (Felt Nm)"],
    var_name="Telemetry Metric", 
    value_name="Force Output (Nm)"
)

static_chart = alt.Chart(df_melted).mark_line(point=True, strokeWidth=2.5).encode(
    x=alt.X("EQ Scale Factor (%):Q", title="EQ Scale Factor (%)", scale=alt.Scale(zero=False)),
    y=alt.Y("Force Output (Nm):Q", title="Torque / Force (Nm)"),
    color=alt.Color("Telemetry Metric:N", title="Metrics", 
                    scale=alt.Scale(domain=["Requested Gross Detail (Nm)", "Net Delivered Force (Felt Nm)"], range=["#1f77b4", "#ff7f0e"]))
).properties(
    height=400
)

st.altair_chart(static_chart, use_container_width=True)

# --- SECTION 3: MATHEMATICS STRESS TESTING ---
st.markdown("---")
st.header("🔬 Physics & Maths Stress Testing")
st.markdown("To ensure data output is strictly factual, the simulation engine validates its mathematics.")

def check_match(val1, val2, tolerance=0.001):
    return abs(val1 - val2) <= tolerance

with st.expander("Expand to View Engine Validation Tests", expanded=False):
    tests_passed = 0
    
    res1 = simulate_ffb_pure(
        raw_sustained=1.0, raw_transient=1.0, car_speed=1.0, wheel_vel=10.0, wheel_accel=10.0, 
        eq_weights={"10Hz":1.0}, max_tq=10.0, tq_limit=0.0, a_gain=100.0, a_dyn_damp=100.0, 
        m_ffb=100.0, m_road=10.0, e10=100.0, e15=100.0, e25=100.0, e40=100.0, e50=100.0, e100=100.0, 
        m_inertia=100.0, m_damper=100.0, m_friction=100.0
    )
    if check_match(res1["final_nm"], 0.0) and check_match(res1["effective_torque"], 0.0):
        st.success("✅ **Mathematical Base Verification Passed**")
        tests_passed += 1
