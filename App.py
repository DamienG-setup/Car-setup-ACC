import streamlit as st

st.set_page_config(
    page_title="Universal ACC Peak Load Predictor",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏎️ Universal FFB Peak Load & Clipping Predictor")
st.markdown("""
This model simulates the **absolute worst-case physical scenarios** across different motor strengths. 
It calculates the peak torque required when telemetry spikes, EQ bands hit constructive interference, and maximum wheel velocity/acceleration trigger heavy mechanical resistance.
""")
st.markdown("---")

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("🏎️ HARDWARE CONFIGURATION")
# Allows scaling from entry-level options up to heavy-duty direct drive bases
max_torque_nm = st.sidebar.slider("Wheel Base Peak Torque (Nm)", 2.0, 25.0, 3.9, 0.1, help="Set this to match your specific wheel base rating (e.g., R3=3.9, R5=5.5, R9=9.0, R12=12.0)")

st.sidebar.header("🔧 PIT HOUSE / BASE BASIC SETTINGS")
moza_ffb = st.sidebar.slider("Game FFB Intensity (%)", 0, 100, 100)
moza_torque_limit = st.sidebar.slider("Max Output Torque Limit (%)", 50, 100, 100)
moza_road_sens = st.sidebar.slider("Road Sensitivity (Master EQ Control) (0-10)", 0, 10, 8)

st.sidebar.header("⚠️ WORST-CASE KINEMATICS")
st.sidebar.markdown("*Simulate violent wheel movements to calculate dynamic mechanical resistance.*")
wheel_velocity = st.sidebar.slider("Peak Wheel Velocity (rad/s)", 0.0, 20.0, 15.0, help="Drives Damper resistance")
wheel_acceleration = st.sidebar.slider("Peak Wheel Acceleration (rad/s²)", 0.0, 60.0, 45.0, help="Drives Inertia resistance")

st.sidebar.header("⚙️ ADVANCED MECHANICAL SETTINGS")
moza_inertia = st.sidebar.slider("Natural Inertia (%)", 100, 500, 150, 10)
moza_damper = st.sidebar.slider("Wheel Damper (%)", 0, 100, 20)
moza_friction = st.sidebar.slider("Wheel Friction (%)", 0, 100, 10)
moza_speed_damp = st.sidebar.slider("Speed-dependent Damping (%)", 0, 100, 25)

st.sidebar.header("🎚️ FFB EFFECT EQUALIZER (Hz)")
eq_15hz = st.sidebar.slider("15 Hz (Weight Transfer / Body Move) (%)", 0, 500, 120, 10)
eq_25hz = st.sidebar.slider("25 Hz (Suspension Bumps / ABS) (%)", 0, 500, 100, 10)
eq_40hz = st.sidebar.slider("40 Hz (Curbs / Surface Effects) (%)", 0, 500, 100, 10)
eq_60hz = st.sidebar.slider("60 Hz (Asphalt Grain / Road Texture) (%)", 0, 500, 110, 10)
eq_100hz = st.sidebar.slider("100 Hz (Tire Slip Detail / Micro-Vibrations) (%)", 0, 500, 130, 10)

st.sidebar.header("🎮 ACC IN-GAME SETTINGS")
acc_gain = st.sidebar.slider("Gain (%)", 0, 100, 85)
acc_dynamic_damping = st.sidebar.slider("Dynamic Damping (%)", 0, 100, 100)

# --- ENGINE MATHEMATICAL SCALARS ---
base_scalar = (acc_gain / 100.0) * (moza_ffb / 100.0) * (moza_torque_limit / 100.0)
road_sens_master = moza_road_sens / 10.0

# Worst-Case Constructive Interference (All EQ frequencies hit peak amplitude simultaneously)
hz_15_force = (eq_15hz / 100.0) * road_sens_master * 0.15 * max_torque_nm * base_scalar
hz_25_force = (eq_25hz / 100.0) * road_sens_master * 0.12 * max_torque_nm * base_scalar
hz_40_force = (eq_40hz / 100.0) * road_sens_master * 0.10 * max_torque_nm * base_scalar
hz_60_force = (eq_60hz / 100.0) * road_sens_master * 0.08 * max_torque_nm * base_scalar
hz_100_force = (eq_100hz / 100.0) * road_sens_master * 0.14 * max_torque_nm * base_scalar

# --- PEAK DYNAMIC RESISTANCE CALCULATION ---
peak_friction_nm = 0.05 * (moza_friction / 100.0) * max_torque_nm
peak_damper_nm = 0.015 * (moza_damper / 100.0) * wheel_velocity
peak_inertia_nm = 0.008 * (moza_inertia / 100.0) * wheel_acceleration

peak_mechanical_resistance = peak_friction_nm + peak_damper_nm + peak_inertia_nm

st.header("⚙️ Worst-Case Mechanical Overhead")
st.info(f"During maximum wheel snap, the motor uses **{peak_mechanical_resistance:.2f} Nm** just to overcome internal mechanical processing limits before it can deliver game FFB.")

# --- SECTION 1: ISOLATED TRACK SURFACE TRANSIENT POOL ---
st.header("🪨 Isolated Track Surface Transient Pool")
transient_cols = st.columns(4)

curb_strike_nm = (0.60 * base_scalar * max_torque_nm) + hz_25_force + hz_40_force + peak_mechanical_resistance
med_curb_nm = (0.35 * base_scalar * max_torque_nm) + hz_25_force + peak_mechanical_resistance
sausage_curb_nm = (0.85 * base_scalar * max_torque_nm) + (hz_25_force * 1.5) + peak_mechanical_resistance
rumble_strip_nm = (0.20 * base_scalar * max_torque_nm) + hz_40_force + hz_60_force + peak_mechanical_resistance

def display_metric(col, label, val):
    if val >= max_torque_nm:
        col.error(f"{label}\n\n💥 {max_torque_nm:.2f} Nm (CLIPPED)")
    else:
        col.success(f"{label}\n\n⚖️ {val:.2f} Nm")

display_metric(transient_cols[0], "Severe Curb Strike", curb_strike_nm)
display_metric(transient_cols[1], "Medium Curb Passage", med_curb_nm)
display_metric(transient_cols[2], "Sausage Curb Impact", sausage_curb_nm)
display_metric(transient_cols[3], "Rumble Strip Vibration", rumble_strip_nm)

# --- SECTION 2: CORE CORNERING SPEEDS & PHASES ---
scenarios = {
    "Slow Speed Corners": {"speed_factor": 0.25, "telemetry": [0.45, 0.38, 0.55, 0.28]},
    "Medium Speed Corners": {"speed_factor": 0.65, "telemetry": [0.75, 0.60, 0.88, 0.48]},
    "High Speed Corners": {"speed_factor": 1.00, "telemetry": [0.95, 0.72, 1.10, 0.60]}
}

phase_definitions = [
    {"name": "Max front tire grip", "hz_components": ["15Hz"], "hz_val": lambda: hz_15_force},
    {"name": "First stage of losing front grip", "hz_components": ["15Hz", "100Hz"], "hz_val": lambda: (hz_15_force * 0.7) + hz_100_force},
    {"name": "Just before loss of front tire grip", "hz_components": ["15Hz", "60Hz"], "hz_val": lambda: hz_15_force + hz_60_force},
    {"name": "Losing rear tire grip (Snap Oversteer)", "hz_components": ["60Hz", "100Hz"], "hz_val": lambda: hz_60_force + (hz_100_force * 1.3)}
]

for speed_zone, zone_data in scenarios.items():
    st.markdown("---")
    st.header(f"🏁 {speed_zone} (Worst-Case Load)")
    v_scale = zone_data["speed_factor"]
    
    dyn_damping_nm = 0.15 * (acc_dynamic_damping / 100.0) * v_scale * (wheel_velocity / 5.0)
    speed_damping_nm = 0.10 * (moza_speed_damp / 100.0) * v_scale * (wheel_velocity / 5.0)
    
    cols = st.columns(4)
    for idx, phase in enumerate(phase_definitions):
        with cols[idx]:
            raw_tel_pct = zone_data["telemetry"][idx]
            base_active_nm = raw_tel_pct * base_scalar * max_torque_nm
            hz_addition = phase["hz_val"]()
            
            if "Oversteer" in phase['name']:
                total_res_nm = peak_mechanical_resistance + dyn_damping_nm + speed_damping_nm
            else:
                total_res_nm = peak_friction_nm + (peak_damper_nm * 0.2) + dyn_damping_nm + speed_damping_nm

            combined_nm = base_active_nm + hz_addition + total_res_nm
            clipped = combined_nm >= max_torque_nm
            final_output_nm = min(combined_nm, max_torque_nm)
            
            st.markdown(f"**{phase['name']}**")
            if clipped:
                st.error(f"💥 OVERALL FORCE: {final_output_nm:.3f} Nm (CLIPPING)")
                st.caption(f"↳ Raw Requirement: {combined_nm:.2f} Nm")
            else:
                st.success(f"⚖️ OVERALL FORCE: {final_output_nm:.3f} Nm")
                
            st.caption(f"↳ Base Telemetry: {base_active_nm:.2f} Nm")
            st.caption(f"↳ Active EQ Spikes: {hz_addition:.2f} Nm")
            st.caption(f"↳ Mech. Resistance: {total_res_nm:.2f} Nm")
            st.progress(final_output_nm / max_torque_nm)

# --- SECTION 3: STRAIGHT LINE STATES (RESTORED) ---
st.markdown("---")
st.header("🛑 Straight-Line / Transition States")
col_straight = st.columns(2)

with col_straight[0]:
    brake_base_nm = 0.35 * base_scalar * max_torque_nm
    # Forward weight transfer creates resistance to rapid initial wheel movement
    brake_res_nm = peak_friction_nm + (peak_damper_nm * 0.3) + (0.05 * max_torque_nm)
    total_brake_nm = min(brake_base_nm + hz_15_force + brake_res_nm, max_torque_nm)
    
    st.markdown("**Braking Weight Transfer (15Hz Load)**")
    if total_brake_nm >= max_torque_nm:
        st.error(f"💥 OVERALL FORCE: {total_brake_nm:.3f} Nm (CLIPPING)")
    else:
        st.info(f"⚡ OVERALL FORCE: {total_brake_nm:.3f} Nm")
    st.caption(f"↳ Active Telemetry & 15Hz: {brake_base_nm + hz_15_force:.2f} Nm | Resistance: {brake_res_nm:.2f} Nm")
    st.progress(total_brake_nm / max_torque_nm)

with col_straight[1]:
    bump_base_nm = 0.30 * base_scalar * max_torque_nm
    # Sudden suspension deflections heavily spike wheel acceleration, maximizing inertia resistance
    bump_res_nm = peak_friction_nm + peak_inertia_nm + (0.10 * max_torque_nm)
    total_bump_nm = min(bump_base_nm + hz_25_force + bump_res_nm, max_torque_nm)
    
    st.markdown("**Suspension Bumps / Dips (25Hz Load)**")
    if total_bump_nm >= max_torque_nm:
        st.error(f"💥 OVERALL FORCE: {total_bump_nm:.3f} Nm (CLIPPING)")
    else:
        st.info(f"⚡ OVERALL FORCE: {total_bump_nm:.3f} Nm")
    st.caption(f"↳ Active Telemetry & 25Hz: {bump_base_nm + hz_25_force:.2f} Nm | Resistance: {bump_res_nm:.2f} Nm")
    st.progress(total_bump_nm / max_torque_nm)
