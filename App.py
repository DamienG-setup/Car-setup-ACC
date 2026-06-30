import streamlit as st

st.set_page_config(
    page_title="Moza R3 ACC Matrix Engine",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏎️ Moza R3 & ACC Simultaneous Force Matrix Engine")
st.markdown("""
This model calculates total combined motor loads across specific racing line phases. 
Active telemetry and internal motor resistance are combined and capped at the hardware's physical **3.9 Nm ceiling**.
""")
st.markdown("---")

MAX_TORQUE_NM = 3.9

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("🔧 MOZA PIT HOUSE SETTINGS")
moza_ffb = st.sidebar.slider("Game FFB Intensity (%)", 0, 100, 100)
moza_torque_limit = st.sidebar.slider("Max Output Torque Limit (%)", 50, 100, 100)
moza_road_sens = st.sidebar.slider("Road Sensitivity (0-10)", 0, 10, 8)
moza_damper = st.sidebar.slider("Wheel Damper (%)", 0, 100, 25)
moza_friction = st.sidebar.slider("Wheel Friction (%)", 0, 100, 10)
moza_speed_damp = st.sidebar.slider("Speed-dependent Damping (%)", 0, 100, 30)
moza_max_speed = st.sidebar.slider("Maximum Wheel Speed (%)", 10, 140, 100)

st.sidebar.subheader("🎚️ FFB Equalizer Bands")
eq_15hz = st.sidebar.slider("15 Hz (Bumps & Dips) (%)", 0, 500, 100, 10)
eq_25hz = st.sidebar.slider("25 Hz (Curbs & ABS) (%)", 0, 500, 100, 10)
eq_40hz = st.sidebar.slider("40 Hz (Rumble Strips) (%)", 0, 500, 100, 10)

st.sidebar.header("🎮 ACC IN-GAME SETTINGS")
acc_gain = st.sidebar.slider("Gain (%)", 0, 100, 85)
acc_dynamic_damping = st.sidebar.slider("Dynamic Damping (%)", 0, 100, 100)

# --- GLOBAL MATH SCALARS ---
base_scalar = (acc_gain / 100.0) * (moza_ffb / 100.0) * (moza_torque_limit / 100.0)
road_sens_scalar = moza_road_sens / 10.0

# Base constant resistive values independent of velocity
base_friction_nm = 0.04 * (moza_friction / 100.0) * MAX_TORQUE_NM
base_damper_nm = 0.08 * (moza_damper / 100.0) * MAX_TORQUE_NM

# --- TRACK SURFACE TRANSIENT POOL (SEPARATE OUTPUT SECTION) ---
st.header("🪨 Isolated Track Surface Transient Pool")
st.markdown("*These localized transients map onto the base cornering forces. Use these values to manually calculate severe overlay impacts.*")

transient_cols = st.columns(4)
curb_strike_nm = 0.65 * base_scalar * (eq_25hz / 100.0) * MAX_TORQUE_NM
med_curb_nm = 0.40 * base_scalar * (eq_25hz / 100.0) * MAX_TORQUE_NM
sausage_curb_nm = 0.90 * base_scalar * (eq_25hz / 100.0) * MAX_TORQUE_NM
rumble_strip_nm = 0.30 * base_scalar * (eq_40hz / 100.0) * road_sens_scalar * MAX_TORQUE_NM

transient_cols[0].metric("Severe Curb Strike", f"{min(curb_strike_nm, MAX_TORQUE_NM):.2f} Nm")
transient_cols[1].metric("Medium Curb Passage", f"{min(med_curb_nm, MAX_TORQUE_NM):.2f} Nm")
transient_cols[2].metric("Sausage Curb Impact", f"{min(sausage_curb_nm, MAX_TORQUE_NM):.2f} Nm")
transient_cols[3].metric("Rumble Strip Vibration", f"{min(rumble_strip_nm, MAX_TORQUE_NM):.2f} Nm")
st.markdown("---")

# --- CORE DRIVING MATRIX SCENARIOS ---
# Structured data format: { Scenario Name: (Telemetry Physics Scalar, Velocity Scale Factor [0.0 - 1.0]) }
scenarios = {
    "Slow Speed Corners": {
        "speed_factor": 0.25,
        "phases": {
            "Max front tire grip": 0.45,
            "First stage of losing front grip": 0.35,
            "Just before loss of front tire grip (Peak Slip Angle)": 0.52,
            "Losing rear tire grip (Oversteer Catch)": 0.30
        }
    },
    "Medium Speed Corners": {
        "speed_factor": 0.65,
        "phases": {
            "Max front tire grip": 0.75,
            "First stage of losing front grip": 0.58,
            "Just before loss of front tire grip (Peak Slip Angle)": 0.82,
            "Losing rear tire grip (Oversteer Catch)": 0.50
        }
    },
    "High Speed Corners": {
        "speed_factor": 1.00,
        "phases": {
            "Max front tire grip": 0.95,
            "First stage of losing front grip": 0.72,
            "Just before loss of front tire grip (Peak Slip Angle)": 1.05,
            "Losing rear tire grip (Oversteer Catch)": 0.65
        }
    }
}

# Render Layout for Cornering Blocks
for speed_zone, zone_data in scenarios.items():
    st.header(f"🏁 {speed_zone}")
    v_scale = zone_data["speed_factor"]
    
    # Calculate speed dependent dampening resistance for this specific speed zone
    dyn_damping_nm = 0.16 * (acc_dynamic_damping / 100.0) * v_scale * MAX_TORQUE_NM
    speed_damping_nm = 0.10 * (moza_speed_damp / 100.0) * v_scale * MAX_TORQUE_NM
    total_res_nm = base_friction_nm + base_damper_nm + dyn_damping_nm + speed_damping_nm
    
    cols = st.columns(4)
    for idx, (phase_name, raw_physics) in enumerate(zone_data["phases"].items()):
        with cols[idx]:
            # Scale active telemetry force
            active_nm = raw_physics * base_scalar * MAX_TORQUE_NM
            combined_nm = active_nm + total_res_nm
            clipped = combined_nm >= MAX_TORQUE_NM
            final_output_nm = min(combined_nm, MAX_TORQUE_NM)
            
            # UI Card Container
            st.markdown(f"**{phase_name}**")
            if clipped:
                st.error(f"💥 OVERALL FORCE: {final_output_nm:.3f} Nm (CLIPPING)")
            else:
                st.success(f"⚖️ OVERALL FORCE: {final_output_nm:.3f} Nm")
                
            # Breakdown Sub-metrics
            st.caption(f"↳ Active Telemetry: {active_nm:.2f} Nm")
            st.caption(f"↳ Motor Internal Resistance: {total_res_nm:.2f} Nm")
            st.progress(final_output_nm / MAX_TORQUE_NM)

st.markdown("---")
st.header("🛑 Straight-Line / Transition States")
col_straight = st.columns(2)

# Straight line braking
with col_straight[0]:
    brake_active_nm = 0.35 * base_scalar * MAX_TORQUE_NM
    # Low speed resistance profile on straight line
    brake_res_nm = base_friction_nm + base_damper_nm + (0.05 * MAX_TORQUE_NM) 
    total_brake_nm = min(brake_active_nm + brake_res_nm, MAX_TORQUE_NM)
    st.markdown("**Braking Weight Transfer (Straight Line Deceleration)**")
    st.info(f"⚡ OVERALL FORCE: {total_brake_nm:.3f} Nm")
    st.caption(f"↳ Active Load: {brake_active_nm:.2f} Nm | Resistance Weight: {brake_res_nm:.2f} Nm")
    st.progress(total_brake_nm / MAX_TORQUE_NM)

# Suspension Bumps / Dips
with col_straight[1]:
    bump_active_nm = 0.40 * base_scalar * (eq_15hz / 100.0) * MAX_TORQUE_NM
    # Mid speed resistance baseline
    bump_res_nm = base_friction_nm + base_damper_nm + (0.10 * MAX_TORQUE_NM)
    total_bump_nm = min(bump_active_nm + bump_res_nm, MAX_TORQUE_NM)
    st.markdown("**Suspension Bumps / Track Dips Response**")
    st.info(f"⚡ OVERALL FORCE: {total_bump_nm:.3f} Nm")
    st.caption(f"↳ Transient Bounce: {bump_active_nm:.2f} Nm | Resistance Weight: {bump_res_nm:.2f} Nm")
    st.progress(total_bump_nm / MAX_TORQUE_NM)
