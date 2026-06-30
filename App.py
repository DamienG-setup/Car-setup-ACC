import streamlit as st

st.set_page_config(
    page_title="Moza R3 ACC Master Engine",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏎️ Moza R3 Master FFB Engine (Restored Hz & Inertia Matrix)")
st.markdown("""
This model links **Road Sensitivity** as the absolute master multiplier for the frequency equalizer bands.
Internal steering assembly momentum (**Natural Inertia**) is factored directly into the dynamic motor resistance pool.
""")
st.markdown("---")

MAX_TORQUE_NM = 3.9

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("🔧 MOZA PIT HOUSE BASIC SETTINGS")
moza_ffb = st.sidebar.slider("Game FFB Intensity (%)", 0, 100, 100)
moza_torque_limit = st.sidebar.slider("Max Output Torque Limit (%)", 50, 100, 100)
moza_road_sens = st.sidebar.slider("Road Sensitivity (Master EQ Control) (0-10)", 0, 10, 8)

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

# Master Road Sensitivity Multiplier (0.0 at 0, 1.0 at 10)
road_sens_master = moza_road_sens / 10.0

# Calculate Effective Hz Telemetry Forces (Gated by Master Road Sensitivity)
hz_15_force = (eq_15hz / 100.0) * road_sens_master * 0.15 * MAX_TORQUE_NM * base_scalar
hz_25_force = (eq_25hz / 100.0) * road_sens_master * 0.12 * MAX_TORQUE_NM * base_scalar
hz_40_force = (eq_40hz / 100.0) * road_sens_master * 0.10 * MAX_TORQUE_NM * base_scalar
hz_60_force = (eq_60hz / 100.0) * road_sens_master * 0.08 * MAX_TORQUE_NM * base_scalar
hz_100_force = (eq_100hz / 100.0) * road_sens_master * 0.14 * MAX_TORQUE_NM * base_scalar

# Baseline Passive Resistive Forces
base_friction_nm = 0.05 * (moza_friction / 100.0) * MAX_TORQUE_NM
base_damper_nm = 0.08 * (moza_damper / 100.0) * MAX_TORQUE_NM
# Natural Inertia adds resistance against rapid directional alterations based on steering mass
base_inertia_nm = 0.06 * (moza_inertia / 100.0) * MAX_TORQUE_NM
static_resistance_pool = base_friction_nm + base_damper_nm + base_inertia_nm

# --- SECTION 1: ISOLATED TRACK SURFACE TRANSIENT POOL ---
st.header("🪨 Isolated Track Surface Transient Pool")
st.markdown("*Use these independent values to manually overlay severe surface transitions onto any phase below.*")
transient_cols = st.columns(4)

curb_strike_nm = (0.60 * base_scalar * MAX_TORQUE_NM) + hz_25_force + hz_40_force
med_curb_nm = (0.35 * base_scalar * MAX_TORQUE_NM) + hz_25_force
sausage_curb_nm = (0.85 * base_scalar * MAX_TORQUE_NM) + (hz_25_force * 1.5)
rumble_strip_nm = (0.20 * base_scalar * MAX_TORQUE_NM) + hz_40_force + hz_60_force

transient_cols[0].metric("Severe Curb Strike", f"{min(curb_strike_nm, MAX_TORQUE_NM):.2f} Nm")
transient_cols[1].metric("Medium Curb Passage", f"{min(med_curb_nm, MAX_TORQUE_NM):.2f} Nm")
transient_cols[2].metric("Sausage Curb Impact", f"{min(sausage_curb_nm, MAX_TORQUE_NM):.2f} Nm")
transient_cols[3].metric("Rumble Strip Vibration", f"{min(rumble_strip_nm, MAX_TORQUE_NM):.2f} Nm")

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
    {"name": "Losing rear tire grip", "hz_components": ["60Hz", "100Hz"], "hz_val": lambda: hz_60_force + (hz_100_force * 1.3)}
]

for speed_zone, zone_data in scenarios.items():
    st.markdown("---")
    st.header(f"🏁 {speed_zone}")
    v_scale = zone_data["speed_factor"]
    
    # Speed dependent dynamic resistance
    dyn_damping_nm = 0.15 * (acc_dynamic_damping / 100.0) * v_scale * MAX_TORQUE_NM
    speed_damping_nm = 0.10 * (moza_speed_damp / 100.0) * v_scale * MAX_TORQUE_NM
    total_res_nm = static_resistance_pool + dyn_damping_nm + speed_damping_nm
    
    cols = st.columns(4)
    for idx, phase in enumerate(phase_definitions):
        with cols[idx]:
            raw_tel_pct = zone_data["telemetry"][idx]
            base_active_nm = raw_tel_pct * base_scalar * MAX_TORQUE_NM
            hz_addition = phase["hz_val"]()
            
            combined_nm = base_active_nm + hz_addition + total_res_nm
            clipped = combined_nm >= MAX_TORQUE_NM
            final_output_nm = min(combined_nm, MAX_TORQUE_NM)
            
            st.markdown(f"**{phase['name']}**")
            if clipped:
                st.error(f"💥 OVERALL FORCE: {final_output_nm:.3f} Nm (CLIPPING)")
            else:
                st.success(f"⚖️ OVERALL FORCE: {final_output_nm:.3f} Nm")
                
            st.caption(f"↳ Base Telemetry: {base_active_nm:.2f} Nm")
            st.caption(f"↳ Active EQ ({', '.join(phase['hz_components'])}): {hz_addition:.2f} Nm")
            st.caption(f"↳ Resistance (Inertia Inc.): {total_res_nm:.2f} Nm")
            st.progress(final_output_nm / MAX_TORQUE_NM)

# --- SECTION 3: STRAIGHT LINE STATES ---
st.markdown("---")
st.header("🛑 Straight-Line / Transition States")
col_straight = st.columns(2)

with col_straight[0]:
    brake_base_nm = 0.35 * base_scalar * MAX_TORQUE_NM
    brake_res_nm = static_resistance_pool + (0.05 * MAX_TORQUE_NM)
    # Forward weight transfer heavily loads the 15Hz frequency band
    total_brake_nm = min(brake_base_nm + hz_15_force + brake_res_nm, MAX_TORQUE_NM)
    st.markdown("**Braking Weight Transfer (15Hz Load)**")
    st.info(f"⚡ OVERALL FORCE: {total_brake_nm:.3f} Nm")
    st.caption(f"↳ Active Telemetry & 15Hz: {brake_base_nm + hz_15_force:.2f} Nm | Resistance: {brake_res_nm:.2f} Nm")
    st.progress(total_brake_nm / MAX_TORQUE_NM)

with col_straight[1]:
    bump_base_nm = 0.30 * base_scalar * MAX_TORQUE_NM
    bump_res_nm = static_resistance_pool + (0.10 * MAX_TORQUE_NM)
    # Suspension deflections process through the 25Hz channel
    total_bump_nm = min(bump_base_nm + hz_25_force + bump_res_nm, MAX_TORQUE_NM)
    st.markdown("**Suspension Bumps / Dips (25Hz Load)**")
    st.info(f"⚡ OVERALL FORCE: {total_bump_nm:.3f} Nm")
    st.caption(f"↳ Active Telemetry & 25Hz: {bump_base_nm + hz_25_force:.2f} Nm | Resistance: {bump_res_nm:.2f} Nm")
    st.progress(total_bump_nm / MAX_TORQUE_NM)
