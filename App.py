import streamlit as st

# Configure the page properties
st.set_page_config(
    page_title="Moza R3 ACC Force Calculator",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App Titles and Descriptions
st.title("🏎️ Moza R3 & ACC Force Physics Calculator")
st.markdown("""
This application maps the hardware interaction between **Assetto Corsa Competizione (ACC)** telemetry forces 
and the **Moza Pit House** software profile running on the **Moza R3 3.9 Nm Wheelbase**.
""")
st.markdown("---")

# Define Hardware Max Constants
MAX_TORQUE_NM = 3.9

# Create Sidebar Layout for All Controls
st.sidebar.header("🔧 MOZA PIT HOUSE CONFIGURATION")

moza_ffb = st.sidebar.slider(
    "Game Force Feedback Intensity (%)", 
    min_value=0, max_value=100, value=100, step=1
)
moza_torque_limit = st.sidebar.slider(
    "Maximum Output Torque Limit (%)", 
    min_value=50, max_value=100, value=100, step=1
)
moza_inertia = st.sidebar.slider(
    "Natural Inertia (%)", 
    min_value=100, max_value=500, value=140, step=5
)

st.sidebar.markdown("### 🎚️ FFB Effect Equalizer")
eq_15hz = st.sidebar.slider("15 Hz (Body Bumps/Suspension) (%)", 0, 500, 100, 10)
eq_25hz = st.sidebar.slider("25 Hz (ABS / Heavy Curbs) (%)", 0, 500, 100, 10)
eq_40hz = st.sidebar.slider("40 Hz (Rumble Strips) (%)", 0, 500, 100, 10)
eq_60hz = st.sidebar.slider("60 Hz (Road Textures Low) (%)", 0, 500, 100, 10)
eq_100hz = st.sidebar.slider("100 Hz (Road Textures High) (%)", 0, 500, 100, 10)

st.sidebar.header("🎮 ACC IN-GAME CONFIGURATION")
acc_gain = st.sidebar.slider("Gain (%)", 0, 100, 80, 1)
acc_dynamic_damping = st.sidebar.slider("Dynamic Damping (%)", 0, 100, 100, 1)
acc_road_effects = st.sidebar.slider("Road Effects (%)", 0, 100, 20, 1)
acc_min_force = st.sidebar.slider("Minimum Force (%)", 0, 100, 0, 1)

# Core Mathematics / Calculations Engines
# Master scaling scalar passed through DirectInput constant force channels
base_signal_scalar = (acc_gain / 100.0) * (moza_ffb / 100.0) * (moza_torque_limit / 100.0)

# Define driving physics phases and their corresponding raw input scaling weights
driving_phases = {
    "Front Tire Grip (Peak Lateral Cornering)": {
        "factor": 1.0, "category": "physics", "desc": "Maximum continuous mechanical cornering force on the front steering rack."
    },
    "First Stage of Losing Front Tire Grip (Initial Understeer Slip)": {
        "factor": 0.80, "category": "physics", "desc": "Pneumatic trail decreases as front tires slip past optimal grip threshold."
    },
    "Second Stage of Losing Front Tire Grip (Severe Push Understeer)": {
        "factor": 0.45, "category": "physics", "desc": "Steering rack goes noticeably light as the front tires scrub and slide over the tarmac."
    },
    "Rear Tire Grip & Sliding Out (Oversteer Self-Centering)": {
        "factor": 0.70, "category": "physics", "desc": "Aligning torque forces the wheel to rapidly counter-steer into the direction of the rear slide."
    },
    "Road Textures (Fine Surface Details)": {
        "factor": 0.10, "category": "road", "eq": eq_100hz, "desc": "Micro-vibrations driven directly by road coarseness coefficients."
    },
    "Road Bumps (Suspension Travel / Expansion Joints)": {
        "factor": 0.25, "category": "road", "eq": eq_15hz, "desc": "Low-frequency displacement signals passing through the damper mechanics."
    },
    "Curbs (Apex / Exit Strike Transients)": {
        "factor": 0.50, "category": "road", "eq": eq_25hz, "desc": "Sudden vertical suspension compression forcing high amplitude feedback spikes."
    },
    "Rumble Strips (Corrugated Strip Ripples)": {
        "factor": 0.40, "category": "road", "eq": eq_40hz, "desc": "High frequency oscillating ripple frequency overlay."
    },
    "Straight-Line Braking (Forward Pitch Load + ABS Ripple)": {
        "factor": 0.35, "category": "braking", "eq": eq_25hz, "desc": "Combines forward weight transfer loading with high frequency brake pedal anti-lock pulses."
    }
}

# Display Calculated Metrics Output Page Layout
col_left, col_right = st.columns([2, 1])

with col_left:
    st.header("📊 Resulting Torque Force Analysis")
    st.write("Calculated real physical output mapping for each distinct phase based on current settings:")
    
    for phase_name, data in driving_phases.items():
        if data["category"] == "physics":
            calculated_nm = data["factor"] * base_signal_scalar * MAX_TORQUE_NM
        elif data["category"] == "road":
            calculated_nm = data["factor"] * (acc_road_effects / 100.0) * (data["eq"] / 100.0) * MAX_TORQUE_NM
        elif data["category"] == "braking":
            physics_load = data["factor"] * base_signal_scalar * MAX_TORQUE_NM
            abs_vibe = 0.15 * (acc_road_effects / 100.0) * (data["eq"] / 100.0) * MAX_TORQUE_NM
            calculated_nm = physics_load + abs_vibe
        
        # Hard cap at absolute hardware limits
        calculated_nm = min(calculated_nm, MAX_TORQUE_NM)
        percentage_of_motor = (calculated_nm / MAX_TORQUE_NM) * 100.0
        
        # Streamlit Card Layout for each metric
        with st.expander(f"**{phase_name}**: {calculated_nm:.3f} Nm", expanded=True):
            st.markdown(f"*{data['desc']}*")
            st.progress(calculated_nm / MAX_TORQUE_NM)
            st.caption(f"Utilizing **{percentage_of_motor:.1f}%** of total motor hardware dynamic range capacity.")

with col_right:
    st.header("📈 System Diagnostics")
    st.metric(label="Wheelbase Maximum Hardware Ceiling", value=f"{MAX_TORQUE_NM} Nm")
    
    calculated_peak = base_signal_scalar * MAX_TORQUE_NM
    st.metric(label="Calculated Clean Signal Peak Capacity", value=f"{calculated_peak:.2f} Nm")
    
    if calculated_peak > MAX_TORQUE_NM * 0.95:
        st.error("⚠️ HIGH RISK OF CLIPPING: High-load cornering phases will clip out detail at 3.9 Nm. Consider lowering in-game Gain.")
    elif calculated_peak < MAX_TORQUE_NM * 0.50:
        st.warning("ℹ️ Dynamic range under-utilized. Steering feel may feel overly light for a 3.9 Nm motor.")
    else:
        st.success("✅ Clean force mapping window optimized for entry-level Direct Drive physics accuracy.")
        
    st.info(f"**Dynamic Damping Effect:** Wheel resistance scaling weight is adjusted to **{acc_dynamic_damping}%** scaling with car speed vectors.")
