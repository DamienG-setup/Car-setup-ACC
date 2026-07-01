import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Pro ACC Peak Load Predictor",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏎️ Pro FFB Telemetry & Clipping Simulator")
st.markdown("""
This simulator uses a **Physical Counter-Torque Vector Subtraction Model**. It traces torque from **ACC's Physics Engine**, 
through the **Game's Software Clipper**, applies **Weighted DSP Frequency Bands**, and factors in the **Physical Motor Hardware Budget**.
""")
st.markdown("---")

# --- SIDEBAR: PIPELINE CONFIGURATION ---
st.sidebar.header("1️⃣ HARDWARE LIMITS")
max_torque_nm = st.sidebar.slider("Wheel Base Peak Torque (Nm)", 2.0, 25.0, 9.0, 0.1)
moza_torque_limit = st.sidebar.slider("Maximum Output Torque Limit (%)", 0, 100, 100)

st.sidebar.header("2️⃣ ACC IN-GAME OUTPUT")
acc_gain = st.sidebar.slider("ACC Master Gain (%)", 0, 100, 70)
acc_dynamic_damping = st.sidebar.slider("ACC Dynamic Damping (%)", 0, 100, 100)

st.sidebar.header("3️⃣ WHEELBASE DSP / EQ")
moza_ffb = st.sidebar.slider("Base FFB Intensity (%)", 0, 100, 100)
moza_road_sens = st.sidebar.slider("Road Sensitivity (0-10)", 0, 10, 8)

st.sidebar.markdown("**Constructive EQ Boosts (Transient Scalers)**")
eq_15 = st.sidebar.slider("15 Hz (Body/Suspension) (%)", 0, 500, 120, 10)
eq_25 = st.sidebar.slider("25 Hz (Bumps/Engine) (%)", 0, 500, 120, 10)
eq_40 = st.sidebar.slider("40 Hz (Textures/Slips) (%)", 0, 500, 130, 10)
eq_60 = st.sidebar.slider("60 Hz (Road Noise/Vibrations) (%)", 0, 500, 130, 10)
eq_100 = st.sidebar.slider("100 Hz (High Freq Details) (%)", 0, 500, 130, 10)

st.sidebar.header("4️⃣ BASE MECHANICAL PROFILES")
st.sidebar.markdown("*Set the base resistance percentages of your wheelbase software.*")
# RESTORED: Moza Pit House hard floor of 100% for physical core mass
moza_inertia = st.sidebar.slider("Natural Inertia (%)", 100, 500, 100, 10, help="Moza Pit House floor is 100% due to the physical weight of the direct-drive rotor.")
moza_damper = st.sidebar.slider("Wheel Damper (%)", 0, 100, 20)
moza_friction = st.sidebar.slider("Wheel Friction (%)", 0, 100, 10)

# --- CORE SIMULATION PIPELINE FUNCTION ---
def simulate_ffb_pipeline(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights):
    # STEP 1: ACC Game Signal Processing
    acc_multiplier = acc_gain / 100.0
    sustained_game_signal = raw_sustained * acc_multiplier
    
    game_clip_sustained = min(sustained_game_signal, 1.0)
    headroom = max(0.0, 1.0 - game_clip_sustained)
    
    transient_game_signal = min(raw_transient * acc_multiplier, headroom)
    total_game_signal = game_clip_sustained + transient_game_signal
    acc_is_clipping = (sustained_game_signal + raw_transient * acc_multiplier) >= 1.0

    # STEP 2: Effective Motor Capability
    effective_max_torque = max_torque_nm * (moza_torque_limit / 100.0)

    # STEP 3: Wheelbase DSP & Equalizer Application
    base_scalar = moza_ffb / 100.0
    road_sens_scalar = moza_road_sens / 10.0
    
    weighted_eq = (
        (eq_15 / 100.0) * eq_weights.get("15Hz", 0.2) +
        (eq_25 / 100.0) * eq_weights.get("25Hz", 0.2) +
        (eq_40 / 100.0) * eq_weights.get("40Hz", 0.2) +
        (eq_60 / 100.0) * eq_weights.get("60Hz", 0.2) +
        (eq_100 / 100.0) * eq_weights.get("100Hz", 0.2)
    ) * road_sens_scalar
    
    dsp_sustained_nm = game_clip_sustained * base_scalar * effective_max_torque
    dsp_transient_nm = (transient_game_signal * weighted_eq) * base_scalar * effective_max_torque
    requested_total_nm = dsp_sustained_nm + dsp_transient_nm

    # STEP 4: Mechanical Torque Tax (Counter-Torque Vectors)
    tax_friction = (moza_friction / 100.0) * (0.02 * effective_max_torque)
    tax_damper = (moza_damper / 100.0) * (wheel_vel / 25.0) * (effective_max_torque * 0.15) 
    tax_inertia = (moza_inertia / 100.0) * (wheel_accel / 80.0) * (effective_max_torque * 0.20)
    active_dyn_damper = (acc_dynamic_damping / 100.0) * car_speed * (wheel_vel / 25.0) * (effective_max_torque * 0.15)
    
    total_mech_tax = tax_friction + tax_damper + tax_inertia + active_dyn_damper
    
    # STEP 5: Motor Hardware Output & True Mechanical Subtraction
    clipped_motor_output = min(requested_total_nm, effective_max_torque)
    hardware_is_clipping = requested_total_nm > effective_max_torque
    
    # Internal physical resistances subtract mechanical energy from the column
    final_output_nm = max(0.0, clipped_motor_output - total_mech_tax)
    
    return {
        "acc_clip": acc_is_clipping,
        "hw_clip": hardware_is_clipping,
        "acc_signal": total_game_signal,
        "effective_torque": effective_max_torque,
        "dsp_sustained": dsp_sustained_nm,
        "dsp_transient": dsp_transient_nm,
        "total_tax": total_mech_tax,
        "tax_friction": tax_friction,
        "tax_damper": tax_damper,
        "tax_inertia": tax_inertia,
        "dyn_damp_tax": active_dyn_damper,
        "requested_nm": requested_total_nm,
        "final_nm": final_output_nm,
        "lost_to_hw_clip": max(0.0, requested_total_nm - effective_max_torque)
    }

# --- SECTION 1: SCENARIO RENDERER ---
st.header("🏁 Dynamic Telemetry Scenarios")

scenarios = [
    {
        "name": "Low-Speed Hairpin",
        "has_bucket": True,
        "eq_weights": {"15Hz": 0.6, "25Hz": 0.2, "40Hz": 0.1, "60Hz": 0.1, "100Hz": 0.0}, 
        "phases": [
            {"name": "Peak Grip", "sustained": 0.55, "transient": 0.05, "car_speed": 0.2, "w_vel": 5.0, "w_accel": 5.0},
            {"name": "Edge of Losing Grip", "sustained": 0.60, "transient": 0.15, "car_speed": 0.2, "w_vel": 8.0, "w_accel": 10.0},
            {"name": "Losing Grip (Slide)", "sustained": 0.35, "transient": 0.25, "car_speed": 0.2, "w_vel": 12.0, "w_accel": 20.0} 
        ]
    },
    {
        "name": "Medium Speed Corner",
        "has_bucket": True,
        "eq_weights": {"15Hz": 0.4, "25Hz": 0.3, "40Hz": 0.2, "60Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Peak Grip", "sustained": 0.85, "transient": 0.10, "car_speed": 0.6, "w_vel": 3.0, "w_accel": 5.0},
            {"name": "Edge of Losing Grip", "sustained": 0.90, "transient": 0.20, "car_speed": 0.6, "w_vel": 6.0, "w_accel": 12.0},
            {"name": "Losing Grip (Understeer)", "sustained": 0.45, "transient": 0.35, "car_speed": 0.6, "w_vel": 8.0, "w_accel": 15.0} 
        ]
    },
    {
        "name": "High-Speed Corner",
        "has_bucket": True,
        "eq_weights": {"15Hz": 0.3, "25Hz": 0.4, "40Hz": 0.2, "60Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Peak Grip", "sustained": 1.15, "transient": 0.15, "car_speed": 1.0, "w_vel": 1.0, "w_accel": 2.0},
            {"name": "Edge of Losing Grip", "sustained": 1.25, "transient": 0.25, "car_speed": 1.0, "w_vel": 3.0, "w_accel": 8.0},
            {"name": "Losing Grip (Scrub)", "sustained": 0.60, "transient": 0.45, "car_speed": 1.0, "w_vel": 6.0, "w_accel": 15.0} 
        ]
    },
    {
        "name": "Heavy Braking",
        "has_bucket": False,
        "eq_weights": {"15Hz": 0.1, "25Hz": 0.2, "40Hz": 0.5, "60Hz": 0.1, "100Hz": 0.1}, 
        "phases": [
            {"name": "Initial Hit (ABS Engages)", "sustained": 0.15, "transient": 0.70, "car_speed": 0.9, "w_vel": 1.0, "w_accel": 5.0}, 
            {"name": "Trail Braking (Turn-in)", "sustained": 0.45, "transient": 0.30, "car_speed": 0.6, "w_vel": 8.0, "w_accel": 10.0}, 
            {"name": "Brake Release (Mid-Corner)", "sustained": 0.65, "transient": 0.10, "car_speed": 0.5, "w_vel": 3.0, "w_accel": 5.0}
        ]
    },
    {
        "name": "Snap Oversteer",
        "has_bucket": False,
        "eq_weights": {"15Hz": 0.2, "25Hz": 0.2, "40Hz": 0.4, "60Hz": 0.2, "100Hz": 0.0}, 
        "phases": [
            {"name": "Initial Snap (Rear Lets Go)", "sustained": 0.10, "transient": 0.40, "car_speed": 0.6, "w_vel": 8.0, "w_accel": 30.0}, 
            {"name": "Violent Catch (Tires Bite)", "sustained": 0.90, "transient": 0.80, "car_speed": 0.5, "w_vel": 25.0, "w_accel": 80.0}, 
            {"name": "Stabilization (Recovery)", "sustained": 0.50, "transient": 0.20, "car_speed": 0.4, "w_vel": 10.0, "w_accel": 15.0}
        ]
    },
    {
        "name": "Curb Strike",
        "has_bucket": False,
        "eq_weights": {"15Hz": 0.0, "25Hz": 0.1, "40Hz": 0.2, "60Hz": 0.4, "100Hz": 0.3}, 
        "phases": [
            {"name": "Initial Strike (Impact)", "sustained": 0.30, "transient": 1.50, "car_speed": 0.7, "w_vel": 10.0, "w_accel": 50.0},
            {"name": "Riding the Curb", "sustained": 0.25, "transient": 0.90, "car_speed": 0.7, "w_vel": 15.0, "w_accel": 20.0},
            {"name": "Dropping Off", "sustained": 0.40, "transient": 1.20, "car_speed": 0.7, "w_vel": 12.0, "w_accel": 40.0}
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
        
    worst_res = max(phase_results, key=lambda x: x["final_nm"])
    
    with all_cols[idx]:
        st.markdown(f"### {scene['name']}")
        
        if worst_res["acc_clip"]:
            st.error("🟥 ACC SOFTWARE CLIPPING")
        elif worst_res["hw_clip"]:
            st.warning(f"🟧 HARDWARE CLIPPING\n\nLacking {worst_res['lost_to_hw_clip']:.2f} Nm")
        else:
            st.success("🟩 CLEAN SIGNAL")
            
        st.metric(label="Overall Delivered Feedback", value=f"{worst_res['final_nm']:.2f} Nm")
        
        if scene["has_bucket"]:
            edge_nm = phase_results[1]["final_nm"]
            loss_nm = phase_results[2]["final_nm"]
            bucket_delta = edge_nm - loss_nm
            st.metric(label="🪣 Tactile Reaction Bucket", value=f"{bucket_delta:.2f} Nm Drop")

        st.markdown("**Phase Breakdown (Req. ➔ Delivered):**")
        for i, r in enumerate(phase_results):
            st.caption(f"{i+1}. {r['phase_name']}: **{r['requested_nm']:.2f} Nm** ➔ **{r['final_nm']:.2f} Nm**")
            
        st.progress(min(worst_res['final_nm'] / max_torque_nm, 1.0))
        st.markdown("---")
