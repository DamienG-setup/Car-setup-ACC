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
This simulator uses a **Signal Pipeline Model**. It accurately traces torque from **ACC's Physics Engine**, 
through the **Game's Software Clipper**, into the **Wheelbase DSP (Equalizer)**, and finally against the **Physical Motor Hardware Budget**.
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
eq_low_hz = st.sidebar.slider("15-25 Hz (Body/Bumps) (%)", 0, 500, 120, 10)
eq_high_hz = st.sidebar.slider("40-100 Hz (Textures/Slips) (%)", 0, 500, 130, 10)

st.sidebar.header("4️⃣ KINEMATICS & OVERHEAD")
st.sidebar.markdown("*Mechanical resistance eats into your motor's maximum torque budget.*")
wheel_velocity = st.sidebar.slider("Peak Wheel Velocity (rad/s)", 0.0, 25.0, 15.0)
wheel_acceleration = st.sidebar.slider("Peak Wheel Acceleration (rad/s²)", 0.0, 80.0, 50.0)
moza_inertia = st.sidebar.slider("Natural Inertia (%)", 0, 500, 100, 10)
moza_damper = st.sidebar.slider("Wheel Damper (%)", 0, 100, 20)
moza_friction = st.sidebar.slider("Wheel Friction (%)", 0, 100, 10)

# --- MATHEMATICAL ENGINE: THE TORQUE BUDGET ---
# 1. Calculate Mechanical Torque Tax (Overhead)
# Friction is static. Damper scales with velocity. Inertia scales with acceleration.
tax_friction = (moza_friction / 100.0) * (0.02 * max_torque_nm)
tax_damper = (moza_damper / 100.0) * (0.015 * wheel_velocity) * (max_torque_nm * 0.5) 
tax_inertia = (moza_inertia / 100.0) * (0.005 * wheel_acceleration) * (max_torque_nm * 0.5)

total_mech_tax = tax_friction + tax_damper + tax_inertia
available_ffb_budget = max(0.0, max_torque_nm - total_mech_tax)

st.header("⚙️ Hardware Torque Budget")
st.info(f"**Mechanical Overhead:** Your motor spends **{total_mech_tax:.2f} Nm** fighting its own friction, damper, and inertia during violent movements. "
        f"This leaves a maximum of **{available_ffb_budget:.2f} Nm** available to render actual ACC Force Feedback.")

# --- CORE SIMULATION PIPELINE FUNCTION ---
def simulate_ffb_pipeline(raw_sustained, raw_transient, speed_factor=1.0):
    """
    Simulates the true signal path from game to hardware.
    raw_sustained: ACC's raw physics torque for cornering (0.0 to 1.5+)
    raw_transient: ACC's raw physics torque for bumps/curbs (0.0 to 1.5+)
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
    eq_low_multiplier = (eq_low_hz / 100.0)
    eq_high_multiplier = (eq_high_hz / 100.0)
    avg_eq_boost = ((eq_low_multiplier + eq_high_multiplier) / 2.0) * road_sens_scalar
    
    dsp_sustained_nm = game_clip_sustained * base_scalar * max_torque_nm
    dsp_transient_nm = (transient_game_signal * avg_eq_boost) * base_scalar * max_torque_nm
    requested_total_nm = dsp_sustained_nm + dsp_transient_nm

    # STEP 3: ACC Dynamic Damping (High speed adds damper tax)
    active_dyn_damper = (acc_dynamic_damping / 100.0) * (0.02 * wheel_velocity * speed_factor) * max_torque_nm
    current_budget = max(0.0, available_ffb_budget - active_dyn_damper)

    # STEP 4: Motor Hardware Output & Clipping
    final_output_nm = min(requested_total_nm, current_budget)
    hardware_is_clipping = requested_total_nm > current_budget
    
    return {
        "acc_clip": acc_is_clipping,
        "hw_clip": hardware_is_clipping,
        "acc_signal": total_game_signal,
        "dsp_sustained": dsp_sustained_nm,
        "dsp_transient": dsp_transient_nm,
        "dyn_damp_tax": active_dyn_damper,
        "requested_nm": requested_total_nm,
        "final_nm": final_output_nm,
        "lost_to_hw_clip": max(0.0, requested_total_nm - current_budget)
    }

# --- SECTION 1: SCENARIO RENDERER ---
st.markdown("---")
st.header("🏁 Dynamic Telemetry Scenarios")

scenarios = [
    {"name": "High-Speed Corner (Pouhon)", "sustained": 1.10, "transient": 0.20, "speed": 1.0},
    {"name": "Low-Speed Hairpin", "sustained": 0.45, "transient": 0.10, "speed": 0.2},
    {"name": "Sausage Curb Strike", "sustained": 0.30, "transient": 1.40, "speed": 0.6},
    {"name": "Snap Oversteer (Violent Catch)", "sustained": 0.15, "transient": 0.90, "speed": 0.5}
]

cols = st.columns(4)

for idx, scene in enumerate(scenarios):
    res = simulate_ffb_pipeline(scene["sustained"], scene["transient"], scene["speed"])
    
    with cols[idx]:
        st.markdown(f"**{scene['name']}**")
        
        # Display Status
        if res["acc_clip"]:
            st.error("🟥 ACC SOFTWARE CLIPPING\n\nSignal flatlined in game. No EQ boosts possible.")
        elif res["hw_clip"]:
            st.warning(f"🟧 BASE HARDWARE CLIPPING\n\nMotor lacks {res['lost_to_hw_clip']:.2f} Nm to render details.")
        else:
            st.success("🟩 CLEAN SIGNAL\n\nFull dynamic range rendered.")
            
        # Final Force Metric
        st.metric(label="Delivered Feedback", value=f"{res['final_nm']:.2f} Nm")
        
        # Breakdown
        st.caption(f"**Signal Pipeline Data:**")
        st.caption(f"↳ Game Output Signal: **{res['acc_signal']*100:.0f}%**")
        st.caption(f"↳ Base Corner Force: **{res['dsp_sustained']:.2f} Nm**")
        st.caption(f"↳ EQ Transient Spikes: **{res['dsp_transient']:.2f} Nm**")
        st.caption(f"↳ Dyn. Damper Tax: **{res['dyn_damp_tax']:.2f} Nm**")
        
        # Visual Progress Bar for Motor Capacity
        usage_pct = min(res['final_nm'] / max_torque_nm, 1.0)
        st.progress(usage_pct)

# --- SECTION 2: DEEP DIVE ANALYTICS ---
st.markdown("---")
st.header("📊 Worst-Case Constructive Interference (Telemetry Insight)")

st.markdown("""
This chart visualizes what happens during the **Sausage Curb Strike** scenario. 
Notice how mechanical overhead and ACC's software limit interact with the equalizer. If ACC clips at the software level, the blue "EQ Transients" bar will disappear, simulating a muddy, flatlined FFB feeling.
""")

# Fetching the Sausage Curb data for visualization
curb_data = simulate_ffb_pipeline(0.30, 1.40, 0.6)

chart_data = pd.DataFrame({
    "Torque Allocation": [
        "Mechanical Tax (Friction/Inertia)", 
        "Dynamic Damper Tax",
        "Sustained Physics Force", 
        "EQ Transient Spikes", 
        "Lost to Hardware Clipping"
    ],
    "Nm": [
        total_mech_tax,
        curb_data["dyn_damp_tax"],
        curb_data["dsp_sustained"],
        curb_data["dsp_transient"] if not curb_data["acc_clip"] else 0.0,
        curb_data["lost_to_hw_clip"]
    ]
})

st.bar_chart(chart_data.set_index("Torque Allocation"))
