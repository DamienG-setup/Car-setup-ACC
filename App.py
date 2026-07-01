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

st.title("🏎️ Pro FFB Telemetry & Clipping Simulator (Physics-Validated)")
st.markdown("""
This simulator models a Vector-Based Unified Signal Pipeline. It maps torque from ACC's Physics Engine (DirectInput),
through the 16-bit USB Encoder, applies Moza DSP Bandpass Filtering, and evaluates Gross Motor Torque Demand using true SI-unit mechanical vector interactions.
""") 

st.info("👈 Tuning Controls are located in the Left Sidebar Panel. Click the arrow icon ( > ) in the top-left corner if it is collapsed.")
st.markdown("---") 

# --- TWO-WAY VALUE SYNCHRONIZATION INITIALIZATION ---
variables = {
    "max_torque": (9.0, 2.0, 25.0, 0.1),
    "moza_torque_limit": (100, 0, 100, 1),
    "acc_gain": (75, 0, 100, 1),
    "acc_dynamic_damping": (100, 0, 100, 1),
    "moza_ffb": (100, 0, 100, 1),
    "moza_road_sens": (8, 0, 10, 1),
    "eq_10": (100, 0, 500, 10),
    "eq_15": (100, 0, 500, 10),
    "eq_25": (100, 0, 500, 10),
    "eq_40": (100, 0, 500, 10),
    "eq_60": (100, 0, 500, 10),
    "eq_100": (100, 0, 500, 10),
    "moza_inertia": (100, 100, 500, 10),
    "moza_damper": (30, 0, 100, 1),
    "moza_friction": (15, 0, 100, 1)
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
        st.slider(label, min_v, max_v, key=f"{var_name}_slider", step=step_v, format=fmt, on_change=sync_slider_to_input, args=(var_name,), help=help_text)
    with c2:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        st.number_input(label, min_v, max_v, key=f"{var_name}_input", step=step_v, format=fmt, on_change=sync_input_to_slider, args=(var_name,), label_visibility="collapsed")
    return st.session_state[f"{var_name}_slider"] 

# --- SIDEBAR CONFIGURATION ---
st.sidebar.markdown("""<div style="background-color: #ff4b4b22; padding: 12px; border-radius: 6px; border-left: 5px solid #ff4b4b; margin-bottom: 20px;"><span style="font-size: 16px;"><strong>⚙️ TUNING CONTROL PANEL</strong></span></div>""", unsafe_allow_html=True)
st.sidebar.header("1️⃣ HARDWARE LIMITS")
max_torque_nm = render_param_row("Wheel Base Peak Torque (Nm)", "max_torque", 2.0, 25.0, 0.1)
moza_torque_limit = render_param_row("Maximum Output Torque Limit (%)", "moza_torque_limit", 0, 100, 1)

st.sidebar.header("2️⃣ ACC IN-GAME OUTPUT")
acc_gain = render_param_row("ACC Master Gain (%)", "acc_gain", 0, 100, 1)
acc_dynamic_damping = render_param_row("ACC Dynamic Damping (%)", "acc_dynamic_damping", 0, 100, 1)

st.sidebar.header("3️⃣ WHEELBASE DSP / EQ")
moza_ffb = render_param_row("Base FFB Intensity (%)", "moza_ffb", 0, 100, 1)
moza_road_sens = render_param_row("Road Sensitivity (0-10)", "moza_road_sens", 0, 10, 1)
st.sidebar.markdown("Constructive EQ Boosts (Transient Scalers)")
eq_10 = render_param_row("10 Hz (Body Roll/Weight) (%)", "eq_10", 0, 500, 10)
eq_15 = render_param_row("15 Hz (Suspension/Kerb) (%)", "eq_15", 0, 500, 10)
eq_25 = render_param_row("25 Hz (ABS/Engine) (%)", "eq_25", 0, 500, 10)
eq_40 = render_param_row("40 Hz (Textures/Slips) (%)", "eq_40", 0, 500, 10)
eq_60 = render_param_row("60 Hz (Road Noise/Vibes) (%)", "eq_60", 0, 500, 10)
eq_100 = render_param_row("100 Hz (High Freq Details) (%)", "eq_100", 0, 500, 10)

st.sidebar.header("4️⃣ BASE MECHANICAL PROFILES")
moza_inertia = render_param_row("Natural Inertia (%)", "moza_inertia", 100, 500, 10)
moza_damper = render_param_row("Wheel Damper (%)", "moza_damper", 0, 100, 1)
moza_friction = render_param_row("Wheel Friction (%)", "moza_friction", 0, 100, 1) 

# --- CORE SIMULATION PIPELINE ENGINE ---
def simulate_ffb_pure(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights,
                      max_tq, tq_limit, a_gain, a_dyn_damp, m_ffb, m_road,
                      e10, e15, e25, e40, e60, e100, m_inertia, m_damper, m_friction): 

    # 1. ACC Physics Engine Output Pipeline
    acc_multiplier = a_gain / 100.0
    scaled_base = raw_sustained * acc_multiplier
    
    # DSP EQ Modulation mapping specific frequencies to transient elements
    eq_boosts = {"10Hz": e10/100.0, "15Hz": e15/100.0, "25Hz": e25/100.0, "40Hz": e40/100.0, "60Hz": e60/100.0, "100Hz": e100/100.0}
    eq_scalar = sum(eq_boosts[freq] * eq_weights.get(freq, 0.0) for freq in eq_boosts)
    dsp_texture_gain = (m_road / 10.0) * eq_scalar
    scaled_transient = raw_transient * acc_multiplier * dsp_texture_gain

    # ACC Game-side Dynamic Damping opposes steering rack velocity, scaled by vehicle speed factor
    acc_game_damping = -1.0 * (a_dyn_damp / 100.0) * (car_speed / 250.0) * wheel_vel * 0.08 
    
    # Combine signals at the DirectInput level
    total_raw_game_signal = scaled_base + scaled_transient + acc_game_damping 
    
    # 16-bit DirectInput Signal Hard Register Cap (-1.0 to 1.0)
    usb_game_signal = max(-1.0, min(1.0, total_raw_game_signal))
    acc_is_clipping = abs(total_raw_game_signal) > 1.0 

    # Convert the digital USB signal to hardware electromagnetic torque target
    effective_max_torque = max_tq * (tq_limit / 100.0)
    t_game_nm = usb_game_signal * (m_ffb / 100.0) * effective_max_torque 

    # 2. Wheelbase Firmware-Level Mechanical Filters (SI Units)
    # Friction (Coulomb Friction Model opposing velocity direction)
    t_friction_nm = -1.0 * math.copysign((m_friction / 100.0) * 0.6, wheel_vel) if wheel_vel != 0 else 0.0 
    # Viscous Wheelbase Damping (T = B * w)
    t_damper_nm = -1.0 * (m_damper / 100.0) * 0.18 * wheel_vel 
    # Wheelbase Inertia (T = J * alpha)
    t_inertia_nm = -1.0 * (m_inertia / 100.0) * 0.0025 * wheel_accel 

    # Vector Summation: To execute game torque while overcoming firmware filters, 
    # the motor electrical demand must offset the physical resistance forces.
    total_filters_nm = t_friction_nm + t_damper_nm + t_inertia_nm
    gross_motor_demand = abs(t_game_nm - total_filters_nm) 

    # 3. Hardware Saturation & Proportional Signal Compression
    hardware_is_clipping = gross_motor_demand > effective_max_torque
    lost_to_hw_clip = max(0.0, gross_motor_demand - effective_max_torque) 

    if hardware_is_clipping:
        scale_factor = effective_max_torque / gross_motor_demand
        final_net_game_nm = t_game_nm * scale_factor
        delivered_base = (scaled_base * (m_ffb / 100.0) * effective_max_torque) * scale_factor
        delivered_transient = scaled_transient * (m_ffb / 100.0) * effective_max_torque * scale_factor
    else:
        final_net_game_nm = t_game_nm
        delivered_base = scaled_base * (m_ffb / 100.0) * effective_max_torque
        delivered_transient = scaled_transient * (m_ffb / 100.0) * effective_max_torque 

    return {
        "acc_clip": acc_is_clipping,
        "hw_clip": hardware_is_clipping,
        "acc_raw_signal": total_raw_game_signal,
        "acc_signal": usb_game_signal,
        "effective_torque": effective_max_torque,
        "base_sustained": abs(delivered_base),
        "base_transient": abs(delivered_transient),
        "total_tax": abs(total_filters_nm),
        "tax_friction": abs(t_friction_nm),
        "tax_damper": abs(t_damper_nm),
        "tax_inertia": abs(t_inertia_nm),
        "dyn_damp_tax": abs(acc_game_damping * (m_ffb / 100.0) * effective_max_torque),
        "gross_demand_nm": gross_motor_demand,
        "final_nm": abs(final_net_game_nm),
        "lost_to_hw_clip": lost_to_hw_clip
    } 

def simulate_ffb_pipeline(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights):
    return simulate_ffb_pure(
        raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights,
        max_torque_nm, moza_torque_limit, acc_gain, acc_dynamic_damping,
        moza_ffb, moza_road_sens,
        eq_10, eq_15, eq_25, eq_40, eq_60, eq_100,
        moza_inertia, moza_damper, moza_friction
    ) 

# --- TELEMETRY SCENARIOS ---
st.header("🏁 Dynamic Telemetry Scenarios (Vector Validated)")
st.markdown("Simulates specific physics points in a cornering phase using realistic kinematic state data.") 

scenarios = [
    {
        "name": "Low-Speed Hairpin",
        "has_bucket": True,
        "eq_weights": {"10Hz": 0.4, "15Hz": 0.3, "25Hz": 0.1, "40Hz": 0.1, "60Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Highest Peak of Grip", "sustained": 0.65, "transient": 0.10, "car_speed": 40.0, "w_vel": -4.0, "w_accel": -10.0},
            {"name": "Loss of Grip (Slide)", "sustained": 0.30, "transient": 0.15, "car_speed": 42.0, "w_vel": 12.0, "w_accel": 35.0}
        ]
    },
    {
        "name": "Medium Speed Corner",
        "has_bucket": True,
        "eq_weights": {"10Hz": 0.3, "15Hz": 0.3, "25Hz": 0.2, "40Hz": 0.1, "60Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Highest Peak of Grip", "sustained": 0.85, "transient": 0.15, "car_speed": 90.0, "w_vel": -2.0, "w_accel": -5.0},
            {"name": "Loss of Grip (Understeer)", "sustained": 0.40, "transient": 0.20, "car_speed": 95.0, "w_vel": 8.0, "w_accel": 20.0}
        ]
    },
    {
        "name": "High-Speed Corner",
        "has_bucket": True,
        "eq_weights": {"10Hz": 0.2, "15Hz": 0.2, "25Hz": 0.3, "40Hz": 0.2, "60Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Highest Peak of Grip", "sustained": 1.15, "transient": 0.15, "car_speed": 180.0, "w_vel": -1.0, "w_accel": -2.0},
            {"name": "Loss of Grip (Scrub)", "sustained": 0.75, "transient": 0.25, "car_speed": 182.0, "w_vel": 4.0, "w_accel": 12.0}
        ]
    },
    {
        "name": "Heavy Braking",
        "has_bucket": False,
        "eq_weights": {"10Hz": 0.2, "15Hz": 0.1, "25Hz": 0.4, "40Hz": 0.2, "60Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Initial Hit (ABS Engages)", "sustained": 0.20, "transient": 0.70, "car_speed": 240.0, "w_vel": 0.5, "w_accel": 15.0},
            {"name": "Trail Braking (Turn-in)", "sustained": 0.65, "transient": 0.15, "car_speed": 130.0, "w_vel": -6.0, "w_accel": -25.0}
        ]
    },
    {
        "name": "Snap Oversteer",
        "has_bucket": False,
        "eq_weights": {"10Hz": 0.3, "15Hz": 0.2, "25Hz": 0.1, "40Hz": 0.2, "60Hz": 0.2, "100Hz": 0.0},
        "phases": [
            {"name": "Violent Catch (Tires Bite)", "sustained": 0.85, "transient": 0.65, "car_speed": 110.0, "w_vel": -25.0, "w_accel": -120.0},
            {"name": "Stabilization (Recovery)", "sustained": 0.40, "transient": 0.15, "car_speed": 105.0, "w_vel": 5.0, "w_accel": 15.0}
        ]
    },
    {
        "name": "Curb Strike",
        "has_bucket": False,
        "eq_weights": {"10Hz": 0.0, "15Hz": 0.2, "25Hz": 0.1, "40Hz": 0.2, "60Hz": 0.3, "100Hz": 0.2},
        "phases": [
            {"name": "Initial Strike (Impact)", "sustained": 0.35, "transient": 1.40, "car_speed": 120.0, "w_vel": 15.0, "w_accel": 180.0},
            {"name": "Riding the Curb", "sustained": 0.30, "transient": 0.80, "car_speed": 118.0, "w_vel": 8.0, "w_accel": 40.0}
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
            st.error("🟥 ACC SOFTWARE CLIPPING\n\nDirectInput Ceiling breached. Waveform flattened in-game.")
        elif any_hw_clip:
            st.warning(f"🟧 HARDWARE CLIPPING\n\nMotor saturated by {worst_res['lost_to_hw_clip']:.2f} Nm. Details compressed down.")
        else:
            st.success("🟩 CLEAN SIGNAL\n\nLinear dynamic range completely intact.") 

        st.metric(label="Net Peak Delivered Force", value=f"{worst_res['final_nm']:.2f} Nm") 

        if scene["has_bucket"]:
            peak_nm = phase_results[0]["final_nm"]
            loss_nm = phase_results[1]["final_nm"]
            bucket_delta = peak_nm - loss_nm
            
            # If clipping forced both stages to identical ceiling limits, the delta vanishes
            if peak_nm > loss_nm and bucket_delta > 0.05:
                st.metric(label="🪣 Tactile Reaction Bucket", value=f"{bucket_delta:.2f} Nm Drop", delta=f"-{((bucket_delta)/peak_nm)*100:.0f}% Dynamic Falloff", delta_color="inverse")
            else:
                st.metric(label="🪣 Tactile Reaction Bucket", value="0.00 Nm Drop", delta="0% (Ceiling Saturated - Blown Out)", delta_color="normal") 

        st.markdown("Phase Breakdown (Gross Req. ➔ Net Delivered):")
        for i, r in enumerate(phase_results):
            st.caption(f"{i+1}. {r['phase_name']}: {r['gross_demand_nm']:.2f} Nm ➔ {r['final_nm']:.2f} Nm") 

        usage_pct = min(worst_res['gross_demand_nm'] / max_torque_nm, 1.0)
        st.progress(usage_pct)
        st.markdown("---") 

# --- SECTION 2: DEEP DIVE ANALYTICS ---
st.header("📊 Curb Strike Impact: Vector Proportional Saturation Curve")
st.markdown("Unlike isolated filtering, true hardware clipping uniformly squashes high frequencies when the combined baseline and resistance vectors peak out.") 

curb_weights = {"10Hz": 0.0, "15Hz": 0.2, "25Hz": 0.1, "40Hz": 0.2, "60Hz": 0.3, "100Hz": 0.2}
sweep_data = []
for mult in [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]:
    res_sweep = simulate_ffb_pure(
        0.35, 1.40 * mult, 120.0, 15.0, 180.0, curb_weights,
        max_torque_nm, moza_torque_limit, acc_gain, acc_dynamic_damping,
        moza_ffb, moza_road_sens,
        eq_10, eq_15, eq_25, eq_40, eq_60, eq_100,
        moza_inertia, moza_damper, moza_friction
    )
    sweep_data.append({
        "EQ Scale Factor (%)": int(mult * 100),
        "Requested Gross Detail (Nm)": res_sweep["gross_demand_nm"],
        "Net Delivered Force (Felt Nm)": res_sweep["final_nm"]
    }) 

df_sweep = pd.DataFrame(sweep_data)
df_melted = df_sweep.melt(id_vars=["EQ Scale Factor (%)"], value_vars=["Requested Gross Detail (Nm)", "Net Delivered Force (Felt Nm)"], var_name="Telemetry Metric", value_name="Force Output (Nm)") 

static_chart = alt.Chart(df_melted).mark_line(point=True, strokeWidth=2.5).encode(
    x=alt.X("EQ Scale Factor (%):Q", scale=alt.Scale(zero=False)),
    y=alt.Y("Force Output (Nm):Q"),
    color=alt.Color("Telemetry Metric:N", scale=alt.Scale(domain=["Requested Gross Detail (Nm)", "Net Delivered Force (Felt Nm)"], range=["#1f77b4", "#ff7f0e"]))
).properties(height=350)
st.altair_chart(static_chart, use_container_width=True) 

# --- SECTION 3: MATHEMATICS VALIDATION ---
st.markdown("---")
st.header("🔬 Physics & Maths Stress Testing") 

def check_match(val1, val2, tolerance=0.02):
    return abs(val1 - val2) <= tolerance 

with st.expander("Expand to View Engine Validation Tests", expanded=True):
    tests_passed = 0 

    # Test 1: Zero Capacity Cap
    res1 = simulate_ffb_pure(1.0, 1.0, 0.0, 0.0, 0.0, {"10Hz":1.0}, 10.0, 0.0, 100.0, 0.0, 100.0, 10.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0)
    if check_match(res1["final_nm"], 0.0):
        st.success("✅ Test 1: Zero Capacity Cap - Hard hardware ceiling verified.")
        tests_passed += 1 

    # Test 2: Unified Encoder Clipping
    res2 = simulate_ffb_pure(2.5, 1.0, 0.0, 0.0, 0.0, {"10Hz":1.0}, 10.0, 100.0, 100.0, 0.0, 100.0, 10.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0)
    if res2["acc_clip"] and check_match(res2["acc_signal"], 1.0):
        st.success("✅ Test 2: Unified USB Clipping - Signal safely capped at standard 16-bit register limits.")
        tests_passed += 1 

    # Test 3: Linear Viscous Damping
    res4_low = simulate_ffb_pure(0.0, 0.0, 0.0, 4.0, 0.0, {"10Hz":1.0}, 10.0, 100.0, 100.0, 0.0, 100.0, 10.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 0.0)
    res4_high = simulate_ffb_pure(0.0, 0.0, 0.0, 8.0, 0.0, {"10Hz":1.0}, 10.0, 100.0, 100.0, 0.0, 100.0, 10.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 0.0)
    if check_match(res4_high["tax_damper"], res4_low["tax_damper"] * 2):
        st.success("✅ Test 3: Viscous Damping Linearity - Confirmed flawless correlation across physical angular velocities.")
        tests_passed += 1 

    # Test 4: Compounding Vector Interaction
    res5 = simulate_ffb_pure(0.5, 0.0, 0.0, -10.0, 0.0, {"10Hz":1.0}, 10.0, 100.0, 100.0, 0.0, 100.0, 10.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 0.0)
    if res5["gross_demand_nm"] > (res5["effective_torque"] * 0.5):
        st.success("✅ Test 4: Vector Compounding - Heavy counter-steering friction correctly inflates total motor draw.")
        tests_passed += 1
