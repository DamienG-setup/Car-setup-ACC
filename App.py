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
This simulator uses a **Dynamic Signal Pipeline Model**. It accurately traces torque from **ACC's Physics Engine**, 
through the **Game's Software Clipper**, into the **Wheelbase DSP (Equalizer)**, and finally against the **Physical Motor Hardware Budget** dynamically based on telemetry phases.
""")
st.markdown("---")

# --- SIDEBAR: PIPELINE CONFIGURATION ---
st.sidebar.header("1️⃣ HARDWARE LIMITS")
max_torque_nm = st.sidebar.slider("Wheel Base Peak Torque (Nm)", 2.0, 25.0, 9.0, 0.1, help="e.g., R5=5.5, R9=9.0, Simucube Sport=17.0")

st.sidebar.header("2️⃣ ACC IN-GAME OUTPUT")
acc_gain = st.sidebar.slider("ACC Master Gain (%)", 0, 100, 70, help="Higher gain causes Kunos physics to clip before reaching the wheelbase.")
acc_dynamic_damping = st.sidebar.slider("ACC Dynamic Damping (%)", 0, 100, 100, help="Gyroscopic damping at high speeds.")

st.sidebar.header("3️⃣ WHEELBASE DSP / EQ")
moza_ffb = st.sidebar.slider("Base FFB Intensity (%)", 0, 100, 100)
moza_road_sens = st.sidebar.slider("Road Sensitivity (0-10)", 0, 10, 8, help="Master multiplier for high-frequency bands.")
st.sidebar.markdown("**Constructive EQ Boosts (Transient Scalers)**")
eq_15_hz = st.sidebar.slider("15 Hz (Body/Suspension) (%)", 0, 500, 120, 10)
eq_25_hz = st.sidebar.slider("25 Hz (Bumps/Engine) (%)", 0, 500, 120, 10)
eq_40_hz = st.sidebar.slider("40 Hz (Textures/Slips) (%)", 0, 500, 130, 10)
eq_100_hz = st.sidebar.slider("100 Hz (High Freq Details) (%)", 0, 500, 130, 10)

st.sidebar.header("4️⃣ BASE MECHANICAL PROFILES")
st.sidebar.markdown("*Set the base resistance percentages of your wheelbase software.*")
moza_inertia = st.sidebar.slider("Natural Inertia (%)", 0, 500, 100, 10)
moza_damper = st.sidebar.slider("Wheel Damper (%)", 0, 100, 20)
moza_friction = st.sidebar.slider("Wheel Friction (%)", 0, 100, 10)

# --- CORE SIMULATION PIPELINE FUNCTION ---
def simulate_ffb_pipeline(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel):
    """
    Simulates the true signal path from game to hardware using phase-specific kinematics.
    """
    # STEP 1: ACC Game Signal Processing (Soft Clipping)
    acc_multiplier = acc_gain / 100.0
    sustained_game_signal = raw_sustained * acc_multiplier
    
    # If sustained signal clips in-game, there is NO headroom for transients (flatlined)
    game_clip_sustained = min(sustained_game_signal, 1.0)
    headroom = max(0.0, 1.0 - game_clip_sustained)
    
    transient_game_signal = min(raw_transient * acc_multiplier, headroom)
    total_game_signal = game_clip_sustained + transient_game_signal
    acc_is_clipping = (sustained_game_signal + raw_transient * acc_multiplier) >= 1.0

    # STEP 2: Wheelbase DSP & Equalizer Application
    base_scalar = moza_ffb / 100.0
    road_sens_scalar = moza_road_sens / 10.0
    
    # EQ only amplifies the TRANSIENT part of the signal (AC wave), not the sustained part (DC wave)
    eq_15_mult = eq_15_hz / 100.0
    eq_25_mult = eq_25_hz / 100.0
    eq_40_mult = eq_40_hz / 100.0
    eq_100_mult = eq_100_hz / 100.0
    
    # Average out the distinct frequency bands for the transient simulation
    avg_eq_boost = ((eq_15_mult + eq_25_mult + eq_40_mult + eq_100_mult) / 4.0) * road_sens_scalar
    
    dsp_sustained_nm = game_clip_sustained * base_scalar * max_torque_nm
    dsp_transient_nm = (transient_game_signal * avg_eq_boost) * base_scalar * max_torque_nm
    requested_total_nm = dsp_sustained_nm + dsp_transient_nm

    # STEP 3: Mechanical Torque Tax (Overhead) - Calculated Dynamically per Scenario!
    # Max theoretical limits used for scaling: 25 rad/s vel, 80 rad/s^2 accel
    tax_friction = (moza_friction / 100.0) * (0.02 * max_torque_nm)
    tax_damper = (moza_damper / 100.0) * (wheel_vel / 25.0) * (max_torque_nm * 0.15) 
    tax_inertia = (moza_inertia / 100.0) * (wheel_accel / 80.0) * (max_torque_nm * 0.20)
    active_dyn_damper = (acc_dynamic_damping / 100.0) * car_speed * (wheel_vel / 25.0) * (max_torque_nm * 0.15)
    
    total_mech_tax = tax_friction + tax_damper + tax_inertia + active_dyn_damper
    
    # Motor's remaining capacity after fighting its own mechanics
    current_budget = max(0.0, max_torque_nm - total_mech_tax)

    # STEP 4: Motor Hardware Output & Clipping
    final_output_nm = min(requested_total_nm, current_budget)
    hardware_is_clipping = requested_total_nm > current_budget
    
    return {
        "acc_clip": acc_is_clipping,
        "hw_clip": hardware_is_clipping,
        "acc_signal": total_game_signal,
        "dsp_sustained": dsp_sustained_nm,
        "dsp_transient": dsp_transient_nm,
        "total_tax": total_mech_tax,
        "tax_friction": tax_friction,
        "tax_damper": tax_damper,
        "tax_inertia": tax_inertia,
        "dyn_damp_tax": active_dyn_damper,
        "requested_nm": requested_total_nm,
        "final_nm": final_output_nm,
        "lost_to_hw_clip": max(0.0, requested_total_nm - current_budget)
    }

# --- SECTION 1: SCENARIO RENDERER ---
st.header("🏁 Dynamic Telemetry Scenarios")
st.markdown("Each scenario injects completely different wheel velocity, wheel acceleration, and car speed telemetry to determine the worst-case mechanical tax at that exact moment.")

# Updated Phases with specialized kinematic telemetry metrics
scenarios = [
    {"name": "Low-Speed Hairpin", "sustained": 0.50, "transient": 0.15, "car_speed": 0.2, "w_vel": 12.0, "w_accel": 15.0},
    {"name": "Medium Speed Corner", "sustained": 0.75, "transient": 0.25, "car_speed": 0.6, "w_vel": 6.0, "w_accel": 10.0},
    {"name": "High-Speed Corner", "sustained": 1.15, "transient": 0.30, "car_speed": 1.0, "w_vel": 2.0, "w_accel": 5.0},
    {"name": "Heavy Braking", "sustained": 0.20, "transient": 0.80, "car_speed": 0.8, "w_vel": 1.0, "w_accel": 15.0},
    {"name": "Snap Oversteer", "sustained": 0.10, "transient": 1.00, "car_speed": 0.5, "w_vel": 25.0, "w_accel": 80.0},
    {"name": "Curb Strike", "sustained": 0.40, "transient": 1.50, "car_speed": 0.7, "w_vel": 15.0, "w_accel": 50.0}
]

# Create a 2x3 Grid for better layout scaling
cols1 = st.columns(3)
cols2 = st.columns(3)
all_cols = cols1 + cols2

for idx, scene in enumerate(scenarios):
    res = simulate_ffb_pipeline(scene["sustained"], scene["transient"], scene["car_speed"], scene["w_vel"], scene["w_accel"])
    
    with all_cols[idx]:
        st.markdown(f"### {scene['name']}")
        
        # Display Status
        if res["acc_clip"]:
            st.error("🟥 ACC SOFTWARE CLIPPING\n\nSignal flatlined in game. EQ boosts severely muted.")
        elif res["hw_clip"]:
            st.warning(f"🟧 HARDWARE CLIPPING\n\nMotor lacks {res['lost_to_hw_clip']:.2f} Nm to render details.")
        else:
            st.success("🟩 CLEAN SIGNAL\n\nFull dynamic range rendered.")
            
        # Final Force Metric
        st.metric(label="Delivered Feedback", value=f"{res['final_nm']:.2f} Nm")
        
        # Breakdown
        st.caption(f"**Requested Pipeline Telemetry (Pre-Clip):**")
        
        # Dynamic warning to explain the math discrepancy during clipping
        if res["hw_clip"]:
            st.caption("*Note: The requested forces below exceed the motor's budget. The delivered feedback metric above is capped.*")
            
        st.caption(f"↳ Game Output Signal: **{res['acc_signal']*100:.0f}%**")
        st.caption(f"↳ Req. Base Corner Force: **{res['dsp_sustained']:.2f} Nm**")
        st.caption(f"↳ Req. EQ Transient Spikes: **{res['dsp_transient']:.2f} Nm**")
        st.caption(f"↳ **Mech + Damper Tax: {res['total_tax']:.2f} Nm**")
        
        # Visual Progress Bar for Motor Capacity
        usage_pct = min(res['final_nm'] / max_torque_nm, 1.0)
        st.progress(usage_pct)
        st.markdown("---")

# --- SECTION 2: DEEP DIVE ANALYTICS ---
st.header("📊 Worst-Case Constructive Interference (Curb Strike Insight)")

st.markdown("""
This chart visualizes what happens during the **Curb Strike** scenario. 
Notice how dynamic mechanical overhead (inertia/damper reacting to violent wheel movement) and ACC's software limits interact with the equalizer. 
If ACC clips at the software level, the blue "EQ Transients" bar will disappear, simulating a muddy, flatlined FFB feeling.
""")

# Fetching the Curb Strike data specifically for visualization
# sustained=0.40, transient=1.50, car_speed=0.7, w_vel=15.0, w_accel=50.0
curb_data = simulate_ffb_pipeline(0.40, 1.50, 0.7, 15.0, 50.0)

chart_data = pd.DataFrame({
    "Torque Allocation": [
        "Base Mech Tax (Friction/Damper/Inertia)", 
        "ACC Dynamic Damper Tax",
        "Sustained Physics Force", 
        "EQ Transient Spikes", 
        "Lost to Hardware Clipping"
    ],
    "Nm": [
        curb_data["tax_friction"] + curb_data["tax_damper"] + curb_data["tax_inertia"],
        curb_data["dyn_damp_tax"],
        curb_data["dsp_sustained"],
        curb_data["dsp_transient"] if not curb_data["acc_clip"] else 0.0,
        curb_data["lost_to_hw_clip"]
    ]
})

st.bar_chart(chart_data.set_index("Torque Allocation"))
