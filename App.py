import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(
    page_title="Pro ACC Peak Load Predictor",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏎️ Pro FFB Telemetry & Clipping Simulator")
st.markdown("""
This simulator uses an updated **Dynamic Signal Pipeline Model**. It traces torque from **ACC's Physics Engine**, 
through the **Game's Software Clipper**, applies **Weighted DSP Frequency Bands**, and factors in the **Physical Motor Hardware Budget**.
""")
st.markdown("---")

# --- SIDEBAR: PIPELINE CONFIGURATION ---
st.sidebar.header("1️⃣ HARDWARE LIMITS")
max_torque_nm = st.sidebar.slider("Wheel Base Peak Torque (Nm)", 2.0, 25.0, 9.0, 0.1, help="The absolute maximum physical rating of your wheelbase.")
moza_torque_limit = st.sidebar.slider("Maximum Output Torque Limit (%)", 0, 100, 100, help="The software torque cap (e.g., Moza Pit House limiter).")

st.sidebar.header("2️⃣ ACC IN-GAME OUTPUT")
acc_gain = st.sidebar.slider("ACC Master Gain (%)", 0, 100, 70, help="Higher gain causes Kunos physics to clip before reaching the wheelbase.")
acc_dynamic_damping = st.sidebar.slider("ACC Dynamic Damping (%)", 0, 100, 100, help="Gyroscopic damping at high speeds.")

st.sidebar.header("3️⃣ WHEELBASE DSP / EQ")
moza_ffb = st.sidebar.slider("Base FFB Intensity (%)", 0, 100, 100)
moza_road_sens = st.sidebar.slider("Road Sensitivity (0-10)", 0, 10, 8, help="Master multiplier for high-frequency bands.")

st.sidebar.markdown("**Constructive EQ Boosts (Transient Scalers)**")
eq_15 = st.sidebar.slider("15 Hz (Body/Suspension) (%)", 0, 500, 120, 10)
eq_25 = st.sidebar.slider("25 Hz (Bumps/Engine) (%)", 0, 500, 120, 10)
eq_40 = st.sidebar.slider("40 Hz (Textures/Slips) (%)", 0, 500, 130, 10)
eq_60 = st.sidebar.slider("60 Hz (Road Noise/Vibrations) (%)", 0, 500, 130, 10)
eq_100 = st.sidebar.slider("100 Hz (High Freq Details) (%)", 0, 500, 130, 10)

st.sidebar.header("4️⃣ BASE MECHANICAL PROFILES")
st.sidebar.markdown("*Set the base resistance percentages of your wheelbase software.*")
moza_inertia = st.sidebar.slider("Natural Inertia (%)", 100, 500, 100, 10, help="Min is 100% (Base hardware weight).")
moza_damper = st.sidebar.slider("Wheel Damper (%)", 0, 100, 20)
moza_friction = st.sidebar.slider("Wheel Friction (%)", 0, 100, 10)

# --- CORE SIMULATION PIPELINE FUNCTION ---
def simulate_ffb_pipeline(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights):
    """
    Simulates the true signal path using scenario-specific EQ band weights.
    eq_weights: dict containing mapping multipliers for [15hz, 25hz, 40hz, 60hz, 100hz]
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

    # STEP 2: Calculate Effective Motor Capability
    effective_max_torque = max_torque_nm * (moza_torque_limit / 100.0)

    # STEP 3: Wheelbase DSP & Equalizer Application
    base_scalar = moza_ffb / 100.0
    road_sens_scalar = moza_road_sens / 10.0
    
    # Calculate weighted EQ impact for this specific phase
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

    # STEP 4: Mechanical Torque Tax (Overhead) - Calculated Dynamically per Scenario!
    tax_friction = (moza_friction / 100.0) * (0.02 * effective_max_torque)
    tax_damper = (moza_damper / 100.0) * (wheel_vel / 25.0) * (effective_max_torque * 0.15) 
    tax_inertia = (moza_inertia / 100.0) * (wheel_accel / 80.0) * (effective_max_torque * 0.20)
    active_dyn_damper = (acc_dynamic_damping / 100.0) * car_speed * (wheel_vel / 25.0) * (effective_max_torque * 0.15)
    
    total_mech_tax = tax_friction + tax_damper + tax_inertia + active_dyn_damper
    
    # STEP 5: Motor Hardware Output & Clipping (Proportional Damping Model)
    # Replaced hard subtraction wall with a dynamic attenuation ratio.
    # High mechanical taxes reduce transient clarity percentage-wise, ensuring Hz boosts always pass through.
    damping_ratio = max(0.05, 1.0 - (total_mech_tax / max(0.1, effective_max_torque)))
    dampened_transients = dsp_transient_nm * damping_ratio
    adjusted_requested_nm = dsp_sustained_nm + dampened_transients

    final_output_nm = min(adjusted_requested_nm, effective_max_torque)
    hardware_is_clipping = adjusted_requested_nm > effective_max_torque
    
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
        "lost_to_hw_clip": max(0.0, adjusted_requested_nm - effective_max_torque)
    }

# --- SECTION 1: SCENARIO RENDERER ---
st.header("🏁 Dynamic Telemetry Scenarios")
st.markdown("Each scenario simulates 3 chronological phases, calculating exactly how alignment torque and transients evolve dynamically through the corner.")

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

# Create a 2x3 Grid for better layout scaling
cols1 = st.columns(3)
cols2 = st.columns(3)
all_cols = cols1 + cols2

for idx, scene in enumerate(scenarios):
    
    # Simulate all 3 phases
    phase_results = []
    for p in scene["phases"]:
        res = simulate_ffb_pipeline(p["sustained"], p["transient"], p["car_speed"], p["w_vel"], p["w_accel"], scene["eq_weights"])
        res["phase_name"] = p["name"]
        phase_results.append(res)
        
    # Determine the "Worst Case" phase for the main metrics (Fixed: Based on highest delivered torque)
    worst_res = max(phase_results, key=lambda x: x["final_nm"])
    
    with all_cols[idx]:
        st.markdown(f"### {scene['name']}")
        
        # Display Status for the worst phase
        if worst_res["acc_clip"]:
            st.error("🟥 ACC SOFTWARE CLIPPING\n\nSignal flatlined in game. EQ boosts severely muted.")
        elif worst_res["hw_clip"]:
            st.warning(f"🟧 HARDWARE CLIPPING\n\nMotor lacks {worst_res['lost_to_hw_clip']:.2f} Nm to render details.")
        else:
            st.success("🟩 CLEAN SIGNAL\n\nFull dynamic range rendered.")
            
        # Final Force Metric
        st.metric(label="Overall Delivered Feedback", value=f"{worst_res['final_nm']:.2f} Nm")
        
        # REACTION BUCKET METRIC DISPLAY
        if scene["has_bucket"]:
            edge_nm = phase_results[1]["final_nm"]
            loss_nm = phase_results[2]["final_nm"]
            bucket_delta = edge_nm - loss_nm
            
            st.metric(
                label="🪣 Tactile Reaction Bucket", 
                value=f"{bucket_delta:.2f} Nm Drop", 
                delta=f"-{((bucket_delta)/max(0.1, edge_nm))*100:.0f}% Dynamic Falloff",
                delta_color="inverse"
            )
            st.caption("*(The higher this drop-off, the easier it is to physically feel and catch the slide.)*")

        # DYNAMIC WARNING EXPLAINING MECHANICAL OVERHEAD
        if worst_res["hw_clip"]:
            st.caption(f"⚠️ *Note: The motor is operating at 100% capacity. The overall delivered feedback is what is left over after {worst_res['total_tax']:.2f} Nm is consumed by internal resistance (damping, friction, and inertia).*")
        
        # Active EQ Bands Breakdown
        st.markdown("**Dominant FFB Equalizer Bands:**")
        active_bands = [f"{k} ({v*100:.0f}%)" for k, v in scene["eq_weights"].items() if v > 0]
        st.caption(" | ".join(active_bands))

        # Phase Progression Breakdown
        st.markdown("**Phase Breakdown (Req. ➔ Delivered):**")
        for i, r in enumerate(phase_results):
            st.caption(f"{i+1}. {r['phase_name']}: **{r['requested_nm']:.2f} Nm** ➔ **{r['final_nm']:.2f} Nm**")
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Original Detailed Breakdown (Mapped to Worst Phase)
        st.caption(f"**Worst-Case Pipeline Telemetry (Pre-Clip):**")
        st.caption(f"↳ Game Output Signal: **{worst_res['acc_signal']*100:.0f}%**")
        st.caption(f"↳ Req. Base Corner Force: **{worst_res['dsp_sustained']:.2f} Nm**")
        st.caption(f"↳ Req. EQ Transient Spikes: **{worst_res['dsp_transient']:.2f} Nm**")
        st.caption(f"↳ **Mech + Damper Tax: {worst_res['total_tax']:.2f} Nm**")
        
        # Visual Progress Bar for Motor Capacity
        usage_pct = min(worst_res['final_nm'] / max_torque_nm, 1.0)
        st.progress(usage_pct)
        st.markdown("---")

# --- SECTION 2: DEEP DIVE ANALYTICS ---
st.header("📊 Curb Strike Impact: Hardware Clipping & Tactile Numbness")

st.markdown("""
When you hit a harsh curb, the physics engine generates a massive, violent transient force. If your current settings cause this demand to exceed your wheelbase's peak torque capacity, the motor hits an absolute electronic ceiling and triggers Hardware Clipping.

Similarily, when the game demands a high self-aligning torque (primarily cornering grip) this clipping can occur. 

Below is a live volume sweep of your current EQ configuration during a curb strike impact (scaled from 50% up to 250%):
""")

# Extract current baseline pipeline parameters for a curb strike to sweep dynamically
curb_weights = {"15Hz": 0.0, "25Hz": 0.1, "40Hz": 0.2, "60Hz": 0.4, "100Hz": 0.3}

acc_multiplier = acc_gain / 100.0
sustained_game_signal = 0.30 * acc_multiplier
game_clip_sustained = min(sustained_game_signal, 1.0)
headroom = max(0.0, 1.0 - game_clip_sustained)
transient_game_signal = min(1.50 * acc_multiplier, headroom)

effective_max_torque = max_torque_nm * (moza_torque_limit / 100.0)
base_scalar = moza_ffb / 100.0
road_sens_scalar = moza_road_sens / 10.0

base_weighted_eq = (
    (eq_15 / 100.0) * curb_weights.get("15Hz", 0.0) +
    (eq_25 / 100.0) * curb_weights.get("25Hz", 0.1) +
    (eq_40 / 100.0) * curb_weights.get("40Hz", 0.2) +
    (eq_60 / 100.0) * curb_weights.get("60Hz", 0.4) +
    (eq_100 / 100.0) * curb_weights.get("100Hz", 0.3)
) * road_sens_scalar

dsp_sustained_nm = game_clip_sustained * base_scalar * effective_max_torque

tax_friction = (moza_friction / 100.0) * (0.02 * effective_max_torque)
tax_damper = (moza_damper / 100.0) * (10.0 / 25.0) * (effective_max_torque * 0.15) 
tax_inertia = (moza_inertia / 100.0) * (50.0 / 80.0) * (effective_max_torque * 0.20)
active_dyn_damper = (acc_dynamic_damping / 100.0) * 0.7 * (10.0 / 25.0) * (effective_max_torque * 0.15)
total_mech_tax = tax_friction + tax_damper + tax_inertia + active_dyn_damper

# Sweep across numeric values
sweep_data = []
for mult in [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]:
    test_dsp_transient_nm = (transient_game_signal * (base_weighted_eq * mult)) * base_scalar * effective_max_torque
    test_requested_total_nm = dsp_sustained_nm + test_dsp_transient_nm
    
    test_clipped_motor_output = min(test_requested_total_nm, effective_max_torque)
    test_final_output_nm = max(0.0, test_clipped_motor_output - total_mech_tax)
    
    sweep_data.append({
        "EQ Scale Factor (%)": int(mult * 100),
        "Requested Detail (Nm)": test_requested_total_nm,
        "Delivered Force (Felt Nm)": test_final_output_nm
    })
    
df_sweep = pd.DataFrame(sweep_data)

# Melt the dataframe into long-form formatting for an unmovable Altair chart layout
df_melted = df_sweep.melt(
    id_vars=["EQ Scale Factor (%)"], 
    value_vars=["Requested Detail (Nm)", "Delivered Force (Felt Nm)"],
    var_name="Telemetry Metric", 
    value_name="Force Output (Nm)"
)

# Render a completely static line graph using native Altair profiles (omitting selection bindings)
static_chart = alt.Chart(df_melted).mark_line(point=True, strokeWidth=2.5).encode(
    x=alt.X("EQ Scale Factor (%):Q", title="Horizontal Legend: EQ Scale Factor (%)", scale=alt.Scale(zero=False)),
    y=alt.Y("Force Output (Nm):Q", title="Vertical Legend: Torque / Force (Nm)"),
    color=alt.Color("Telemetry Metric:N", title="Vertical and Horizontal Legend", 
                    scale=alt.Scale(domain=["Requested Detail (Nm)", "Delivered Force (Felt Nm)"], range=["#1f77b4", "#ff7f0e"]))
).properties(
    height=400
)

st.altair_chart(static_chart, use_container_width=True)

st.markdown("""
💡 **Visualizing Numbness on the Chart:**
* **The Blue Line (Requested Detail):** Represents what your audio-frequency EQ sliders are trying to demand as you push them higher.
* **The Orange Line (Delivered Force):** Represents what actually reaches your hands. If this line goes **completely flat and horizontal**, your wheelbase has hit its physical output ceiling. Adjusting the EQ sliders up or down in this zone changes absolutely nothing on the track—the wheel has gone completely numb.
""")
