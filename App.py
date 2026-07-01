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

# Prominent alert to make the control panel location immediately obvious
st.info("👈 **Tuning Controls are located in the Left Sidebar Panel.** Click the arrow icon ( `>` ) in the top-left corner if it is collapsed.")
st.markdown("---")

# --- TWO-WAY VALUE SYNCHRONIZATION INITIALIZATION ---
# Format: { var_name: (default, min, max, step) }
variables = {
    "max_torque": (3.9, 2.0, 25.0, 0.1),
    "moza_torque_limit": (100, 0, 100, 1),
    "acc_gain": (95, 0, 100, 1),
    "acc_dynamic_damping": (100, 0, 100, 1),
    "moza_ffb": (100, 0, 100, 1),
    "moza_road_sens": (10, 0, 10, 1),
    "eq_10": (100, 0, 500, 10),
    "eq_15": (150, 0, 500, 10),
    "eq_25": (100, 0, 500, 10),
    "eq_40": (100, 0, 500, 10),
    "eq_60": (100, 0, 500, 10),
    "eq_100": (100, 0, 500, 10),
    "moza_inertia": (200, 100, 500, 10),
    "moza_damper": (40, 0, 100, 1),
    "moza_friction": (15, 0, 100, 1)
}

# Pre-populate session state keys to avoid cross-talk drift
for var, specs in variables.items():
    if f"{var}_slider" not in st.session_state:
        st.session_state[f"{var}_slider"] = specs[0]
    if f"{var}_input" not in st.session_state:
        st.session_state[f"{var}_input"] = specs[0]

# Callbacks for instantaneous bidirectional sync
def sync_slider_to_input(var_name):
    st.session_state[f"{var_name}_input"] = st.session_state[f"{var_name}_slider"]

def sync_input_to_slider(var_name):
    st.session_state[f"{var_name}_slider"] = st.session_state[f"{var_name}_input"]

def render_param_row(label, var_name, min_v, max_v, step_v, help_text=None):
    c1, c2 = st.sidebar.columns([3.2, 1.5])
    with c1:
        val_from_slider = st.slider(
            label, min_v, max_v, 
            key=f"{var_name}_slider", 
            step=step_v, 
            on_change=sync_slider_to_input, 
            args=(var_name,), 
            help=help_text
        )
    with c2:
        # Pushes input field down to align perfectly alongside the slider label
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        val_from_input = st.number_input(
            label, min_v, max_v, 
            key=f"{var_name}_input", 
            step=step_v, 
            on_change=sync_input_to_slider, 
            args=(var_name,), 
            label_visibility="collapsed"
        )
    return val_from_slider

# --- SIDEBAR: PIPELINE CONFIGURATION ---
st.sidebar.markdown("""
<div style="background-color: #ff4b4b22; padding: 12px; border-radius: 6px; border-left: 5px solid #ff4b4b; margin-bottom: 20px;">
    <span style="font-size: 16px;"><strong>⚙️ TUNING CONTROL PANEL</strong></span><br>
    <small>Adjust parameters instantly using either the sliders or input boxes side-by-side.</small>
</div>
""", unsafe_allow_html=True)

st.sidebar.header("1️⃣ HARDWARE LIMITS")
max_torque_nm = render_param_row("Wheel Base Peak Torque (Nm)", "max_torque", 2.0, 25.0, 0.1, help_text="The absolute maximum physical rating of your wheelbase.")
moza_torque_limit = render_param_row("Maximum Output Torque Limit (%)", "moza_torque_limit", 0, 100, 1, help_text="The software torque cap (e.g., Moza Pit House limiter).")

st.sidebar.header("2️⃣ ACC IN-GAME OUTPUT")
acc_gain = render_param_row("ACC Master Gain (%)", "acc_gain", 0, 100, 1, help_text="Higher gain causes Kunos physics to clip before reaching the wheelbase.")
acc_dynamic_damping = render_param_row("ACC Dynamic Damping (%)", "acc_dynamic_damping", 0, 100, 1, help_text="Gyroscopic damping at high speeds.")

st.sidebar.header("3️⃣ WHEELBASE DSP / EQ")
moza_ffb = render_param_row("Base FFB Intensity (%)", "moza_ffb", 0, 100, 1)
moza_road_sens = render_param_row("Road Sensitivity (0-10)", "moza_road_sens", 0, 10, 1, help_text="Master multiplier for high-frequency bands.")

st.sidebar.markdown("**Constructive EQ Boosts (Transient Scalers)**")
eq_10 = render_param_row("10 Hz (Body Roll/Weight) (%)", "eq_10", 0, 500, 10)
eq_15 = render_param_row("15 Hz (Suspension/Kerb) (%)", "eq_15", 0, 500, 10)
eq_25 = render_param_row("25 Hz (ABS/Engine) (%)", "eq_25", 0, 500, 10)
eq_40 = render_param_row("40 Hz (Textures/Slips) (%)", "eq_40", 0, 500, 10)
eq_60 = render_param_row("60 Hz (Road Noise/Vibes) (%)", "eq_60", 0, 500, 10)
eq_100 = render_param_row("100 Hz (High Freq Details) (%)", "eq_100", 0, 500, 10)

st.sidebar.header("4️⃣ BASE MECHANICAL PROFILES")
st.sidebar.markdown("*Set the base resistance percentages of your wheelbase software.*")
moza_inertia = render_param_row("Natural Inertia (%)", "moza_inertia", 100, 500, 10, help_text="Min is 100% (Base hardware weight).")
moza_damper = render_param_row("Wheel Damper (%)", "moza_damper", 0, 100, 1)
moza_friction = render_param_row("Wheel Friction (%)", "moza_friction", 0, 100, 1)


# --- CORE SIMULATION PIPELINE ENGINE (PURE MATHS) ---
def simulate_ffb_pure(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights,
                      max_tq, tq_limit, a_gain, a_dyn_damp, m_ffb, m_road,
                      e10, e15, e25, e40, e60, e100, m_inertia, m_damper, m_friction):
    
    acc_multiplier = a_gain / 100.0
    sustained_game_signal = raw_sustained * acc_multiplier
    
    game_clip_sustained = min(sustained_game_signal, 1.0)
    headroom = max(0.0, 1.0 - game_clip_sustained)
    
    transient_game_signal = min(raw_transient * acc_multiplier, headroom)
    total_game_signal = game_clip_sustained + transient_game_signal
    
    # Calculate pre-clip raw signal to show users how far over 100% they are going
    acc_raw_signal_total = (raw_sustained + raw_transient) * acc_multiplier
    acc_is_clipping = acc_raw_signal_total >= 1.0

    effective_max_torque = max_tq * (tq_limit / 100.0)

    base_scalar = m_ffb / 100.0
    road_sens_scalar = m_road / 10.0
    
    # Fully integrates 10Hz into the EQ array logic
    weighted_eq = (
        (e10 / 100.0) * eq_weights.get("10Hz", 0.0) +
        (e15 / 100.0) * eq_weights.get("15Hz", 0.0) +
        (e25 / 100.0) * eq_weights.get("25Hz", 0.0) +
        (e40 / 100.0) * eq_weights.get("40Hz", 0.0) +
        (e60 / 100.0) * eq_weights.get("60Hz", 0.0) +
        (e100 / 100.0) * eq_weights.get("100Hz", 0.0)
    ) * road_sens_scalar
    
    dsp_sustained_nm = game_clip_sustained * base_scalar * effective_max_torque
    dsp_transient_nm = (transient_game_signal * weighted_eq) * base_scalar * effective_max_torque

    tax_friction = (m_friction / 100.0) * (0.02 * effective_max_torque)
    tax_damper = (m_damper / 100.0) * (abs(wheel_vel) / 25.0) * (effective_max_torque * 0.15) 
    tax_inertia = (m_inertia / 100.0) * (abs(wheel_accel) / 80.0) * (effective_max_torque * 0.20)
    active_dyn_damper = (a_dyn_damp / 100.0) * abs(car_speed) * (abs(wheel_vel) / 25.0) * (effective_max_torque * 0.15)
    
    total_mech_tax = tax_friction + tax_damper + tax_inertia + active_dyn_damper
    
    # Added safe_div fallback preventing division by zero constraints in the physics engine
    safe_div = max(0.0001, effective_max_torque)
    damping_ratio = max(0.05, 1.0 - (total_mech_tax / safe_div))
    
    dampened_transients = dsp_transient_nm * damping_ratio
    adjusted_requested_nm = dsp_sustained_nm + dampened_transients

    final_output_nm = min(adjusted_requested_nm, effective_max_torque)
    hardware_is_clipping = adjusted_requested_nm > effective_max_torque
    
    return {
        "acc_clip": acc_is_clipping,
        "hw_clip": hardware_is_clipping,
        "acc_raw_signal": acc_raw_signal_total,
        "acc_signal": total_game_signal,
        "effective_torque": effective_max_torque,
        "dsp_sustained": dsp_sustained_nm,
        "dsp_transient": dsp_transient_nm,
        "total_tax": total_mech_tax,
        "tax_friction": tax_friction,
        "tax_damper": tax_damper,
        "tax_inertia": tax_inertia,
        "dyn_damp_tax": active_dyn_damper,
        "requested_nm": adjusted_requested_nm,
        "final_nm": final_output_nm,
        "lost_to_hw_clip": max(0.0, adjusted_requested_nm - effective_max_torque)
    }

# Wrapper to seamlessly inject the sidebar UI bindings into the pure maths engine
def simulate_ffb_pipeline(raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights):
    return simulate_ffb_pure(
        raw_sustained, raw_transient, car_speed, wheel_vel, wheel_accel, eq_weights,
        max_torque_nm, moza_torque_limit, acc_gain, acc_dynamic_damping,
        moza_ffb, moza_road_sens,
        eq_10, eq_15, eq_25, eq_40, eq_60, eq_100,
        moza_inertia, moza_damper, moza_friction
    )

# --- SECTION 1: SCENARIO RENDERER ---
st.header("🏁 Dynamic Telemetry Scenarios")
st.markdown("Each scenario simulates 3 chronological phases, calculating exactly how alignment torque and transients evolve dynamically through the corner.")

# Weights comprehensively re-balanced across all bands to securely integrate 10Hz impacts.
scenarios = [
    {
        "name": "Low-Speed Hairpin",
        "has_bucket": True,
        "eq_weights": {"10Hz": 0.4, "15Hz": 0.3, "25Hz": 0.1, "40Hz": 0.1, "60Hz": 0.1, "100Hz": 0.0}, 
        "phases": [
            {"name": "Peak Grip", "sustained": 0.55, "transient": 0.05, "car_speed": 0.2, "w_vel": 5.0, "w_accel": 5.0},
            {"name": "Edge of Losing Grip", "sustained": 0.60, "transient": 0.15, "car_speed": 0.2, "w_vel": 8.0, "w_accel": 10.0},
            {"name": "Losing Grip (Slide)", "sustained": 0.35, "transient": 0.25, "car_speed": 0.2, "w_vel": 12.0, "w_accel": 20.0} 
        ]
    },
    {
        "name": "Medium Speed Corner",
        "has_bucket": True,
        "eq_weights": {"10Hz": 0.3, "15Hz": 0.3, "25Hz": 0.2, "40Hz": 0.1, "60Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Peak Grip", "sustained": 0.85, "transient": 0.10, "car_speed": 0.6, "w_vel": 3.0, "w_accel": 5.0},
            {"name": "Edge of Losing Grip", "sustained": 0.90, "transient": 0.20, "car_speed": 0.6, "w_vel": 6.0, "w_accel": 12.0},
            {"name": "Losing Grip (Understeer)", "sustained": 0.45, "transient": 0.35, "car_speed": 0.6, "w_vel": 8.0, "w_accel": 15.0} 
        ]
    },
    {
        "name": "High-Speed Corner",
        "has_bucket": True,
        "eq_weights": {"10Hz": 0.2, "15Hz": 0.2, "25Hz": 0.3, "40Hz": 0.2, "60Hz": 0.1, "100Hz": 0.0},
        "phases": [
            {"name": "Peak Grip", "sustained": 1.15, "transient": 0.15, "car_speed": 1.0, "w_vel": 1.0, "w_accel": 2.0},
            {"name": "Edge of Losing Grip", "sustained": 1.25, "transient": 0.25, "car_speed": 1.0, "w_vel": 3.0, "w_accel": 8.0},
            {"name": "Losing Grip (Scrub)", "sustained": 0.60, "transient": 0.45, "car_speed": 1.0, "w_vel": 6.0, "w_accel": 15.0} 
        ]
    },
    {
        "name": "Heavy Braking",
        "has_bucket": False,
        "eq_weights": {"10Hz": 0.2, "15Hz": 0.1, "25Hz": 0.4, "40Hz": 0.2, "60Hz": 0.1, "100Hz": 0.0}, 
        "phases": [
            {"name": "Initial Hit (ABS Engages)", "sustained": 0.15, "transient": 0.70, "car_speed": 0.9, "w_vel": 1.0, "w_accel": 5.0}, 
            {"name": "Trail Braking (Turn-in)", "sustained": 0.45, "transient": 0.30, "car_speed": 0.6, "w_vel": 8.0, "w_accel": 10.0}, 
            {"name": "Brake Release (Mid-Corner)", "sustained": 0.65, "transient": 0.10, "car_speed": 0.5, "w_vel": 3.0, "w_accel": 5.0}
        ]
    },
    {
        "name": "Snap Oversteer",
        "has_bucket": False,
        "eq_weights": {"10Hz": 0.3, "15Hz": 0.2, "25Hz": 0.1, "40Hz": 0.2, "60Hz": 0.2, "100Hz": 0.0}, 
        "phases": [
            {"name": "Initial Snap (Rear Lets Go)", "sustained": 0.10, "transient": 0.40, "car_speed": 0.6, "w_vel": 8.0, "w_accel": 30.0}, 
            {"name": "Violent Catch (Tires Bite)", "sustained": 0.90, "transient": 0.80, "car_speed": 0.5, "w_vel": 25.0, "w_accel": 80.0}, 
            {"name": "Stabilization (Recovery)", "sustained": 0.50, "transient": 0.20, "car_speed": 0.4, "w_vel": 10.0, "w_accel": 15.0}
        ]
    },
    {
        "name": "Curb Strike",
        "has_bucket": False,
        "eq_weights": {"10Hz": 0.0, "15Hz": 0.2, "25Hz": 0.1, "40Hz": 0.2, "60Hz": 0.3, "100Hz": 0.2}, 
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
            st.error("🟥 ACC SOFTWARE CLIPPING\n\nSignal flatlined in game. EQ boosts severely muted.")
        elif worst_res["hw_clip"]:
            st.warning(f"🟧 HARDWARE CLIPPING\n\nMotor lacks {worst_res['lost_to_hw_clip']:.2f} Nm to render details.")
        else:
            st.success("🟩 CLEAN SIGNAL\n\nFull dynamic range rendered.")
            
        st.metric(label="Overall Delivered Feedback", value=f"{worst_res['final_nm']:.2f} Nm")
        
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

        if worst_res["hw_clip"]:
            st.caption(f"⚠️ *Note: The motor is operating at 100% capacity. The overall delivered feedback is what is left over after {worst_res['total_tax']:.2f} Nm is consumed by internal resistance (damping, friction, and inertia).*")
        
        st.markdown("**Dominant FFB Equalizer Bands:**")
        active_bands = [f"{k} ({v*100:.0f}%)" for k, v in scene["eq_weights"].items() if v > 0]
        st.caption(" | ".join(active_bands))

        st.markdown("**Phase Breakdown (Req. ➔ Delivered):**")
        for i, r in enumerate(phase_results):
            st.caption(f"{i+1}. {r['phase_name']}: **{r['requested_nm']:.2f} Nm** ➔ **{r['final_nm']:.2f} Nm**")
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.caption(f"**Worst-Case Pipeline Telemetry (Pre-Clip):**")
        
        if worst_res['acc_raw_signal'] > 1.0:
            st.caption(f"↳ Game Output Signal: **{worst_res['acc_signal']*100:.0f}%** (Raw: 🔴 **{worst_res['acc_raw_signal']*100:.0f}%**)")
        else:
            st.caption(f"↳ Game Output Signal: **{worst_res['acc_signal']*100:.0f}%**")
            
        st.caption(f"↳ Req. Base Corner Force: **{worst_res['dsp_sustained']:.2f} Nm**")
        st.caption(f"↳ Req. EQ Transient Spikes: **{worst_res['dsp_transient']:.2f} Nm**")
        st.caption(f"↳ **Mech + Damper Tax: {worst_res['total_tax']:.2f} Nm**")
        
        usage_pct = min(worst_res['final_nm'] / max_torque_nm, 1.0)
        st.progress(usage_pct)
        st.markdown("---")


# --- SECTION 2: DEEP DIVE ANALYTICS ---
st.header("📊 Curb Strike Impact: Hardware Clipping & Tactile Numbness")

st.markdown("""
When cornering, the physics engine calculates **Self-Aligning Torque**—the heavy, sustained baseline force that wants to snap the steering wheel back straight when front tires are loaded up. Because high cornering loads or overly high in-game master gains consume a huge chunk of your wheelbase's physical energy capacity, self-aligning torque serves as the main instigator for systemic hardware clipping. 

If your motor is already working near its limit just holding the steering wheel steady through a fast corner, slamming into a harsh curb generates a violent extra spike of motion. This unexpected demand instantly slams into the wheelbase's absolute ceiling. 

Because the motor cannot produce more than 100% of its physical capacity, the fine tactile vibrations and road textures provided by your **wheelbase EQ sliders get flattened down against this electronic ceiling**. No matter how high you crank your high-frequency sliders, the output cannot change—causing the wheel to feel completely numb right when you need detail the most.

Below is a live volume sweep of your current EQ configuration during a curb strike impact (scaled from 50% up to 250%):
""")

# Extract current baseline pipeline parameters for a curb strike to sweep dynamically
curb_weights = {"10Hz": 0.0, "15Hz": 0.2, "25Hz": 0.1, "40Hz": 0.2, "60Hz": 0.3, "100Hz": 0.2}

acc_multiplier = acc_gain / 100.0
sustained_game_signal = 0.30 * acc_multiplier
game_clip_sustained = min(sustained_game_signal, 1.0)
headroom = max(0.0, 1.0 - game_clip_sustained)
transient_game_signal = min(1.50 * acc_multiplier, headroom)

effective_max_torque = max_torque_nm * (moza_torque_limit / 100.0)
base_scalar = moza_ffb / 100.0
road_sens_scalar = moza_road_sens / 10.0

base_weighted_eq = (
    (eq_10 / 100.0) * curb_weights.get("10Hz", 0.0) +
    (eq_15 / 100.0) * curb_weights.get("15Hz", 0.0) +
    (eq_25 / 100.0) * curb_weights.get("25Hz", 0.0) +
    (eq_40 / 100.0) * curb_weights.get("40Hz", 0.0) +
    (eq_60 / 100.0) * curb_weights.get("60Hz", 0.0) +
    (eq_100 / 100.0) * curb_weights.get("100Hz", 0.0)
) * road_sens_scalar

dsp_sustained_nm = game_clip_sustained * base_scalar * effective_max_torque

tax_friction = (moza_friction / 100.0) * (0.02 * effective_max_torque)
tax_damper = (moza_damper / 100.0) * (abs(10.0) / 25.0) * (effective_max_torque * 0.15) 
tax_inertia = (moza_inertia / 100.0) * (abs(50.0) / 80.0) * (effective_max_torque * 0.20)
active_dyn_damper = (acc_dynamic_damping / 100.0) * abs(0.7) * (abs(10.0) / 25.0) * (effective_max_torque * 0.15)
total_mech_tax = tax_friction + tax_damper + tax_inertia + active_dyn_damper

# Sweep across numeric values
sweep_data = []
for mult in [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]:
    test_dsp_transient_nm = (transient_game_signal * (base_weighted_eq * mult)) * base_scalar * effective_max_torque
    test_requested_total_nm = dsp_sustained_nm + test_dsp_transient_nm
    
    safe_div = max(0.001, effective_max_torque)
    damping_ratio_loop = max(0.05, 1.0 - (total_mech_tax / safe_div))
    
    test_adjusted_requested_nm = dsp_sustained_nm + (test_dsp_transient_nm * damping_ratio_loop)
    test_final_output_nm = min(test_adjusted_requested_nm, effective_max_torque)
    
    sweep_data.append({
        "EQ Scale Factor (%)": int(mult * 100),
        "Requested Detail (Nm)": test_adjusted_requested_nm,
        "Delivered Force (Felt Nm)": test_final_output_nm
    })
    
df_sweep = pd.DataFrame(sweep_data)

df_melted = df_sweep.melt(
    id_vars=["EQ Scale Factor (%)"], 
    value_vars=["Requested Detail (Nm)", "Delivered Force (Felt Nm)"],
    var_name="Telemetry Metric", 
    value_name="Force Output (Nm)"
)

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


# --- SECTION 3: MATHEMATICS STRESS TESTING ---
st.markdown("---")
st.header("🔬 Physics & Maths Stress Testing")
st.markdown("To ensure data output is rigidly factual and aligned with hardware limitations, the underlying mathematical engine is continuously verified against extreme physical edge-cases below in real-time.")

with st.expander("Expand to View Engine Validation Tests", expanded=False):
    tests_passed = 0
    total_tests = 4
    
    # Test 1: Zero Torque Limit (Dead Motor / No Output)
    res1 = simulate_ffb_pure(
        raw_sustained=1.0, raw_transient=1.0, car_speed=1.0, wheel_vel=10.0, wheel_accel=10.0, 
        eq_weights={"10Hz":1.0}, max_tq=10.0, tq_limit=0.0, a_gain=100.0, a_dyn_damp=100.0, 
        m_ffb=100.0, m_road=10.0, e10=100.0, e15=100.0, e25=100.0, e40=100.0, e60=100.0, e100=100.0, 
        m_inertia=100.0, m_damper=100.0, m_friction=100.0
    )
    if res1["final_nm"] == 0.0 and res1["effective_torque"] == 0.0:
        st.success("✅ **Test 1: Zero Capacity Cap** - Motor limits successfully handled by preventing division-by-zero errors. Output reads strictly 0.0 Nm regardless of external inbound forces.")
        tests_passed += 1
    else:
        st.error("❌ **Test 1 Failed** - Motor output non-zero when capacity limit is 0.")
        
    # Test 2: ACC Software Clipping Integrity
    res2 = simulate_ffb_pure(
        raw_sustained=2.0, raw_transient=2.0, car_speed=1.0, wheel_vel=0.0, wheel_accel=0.0, 
        eq_weights={"10Hz":1.0}, max_tq=10.0, tq_limit=100.0, a_gain=100.0, a_dyn_damp=0.0, 
        m_ffb=100.0, m_road=10.0, e10=100.0, e15=100.0, e25=100.0, e40=100.0, e60=100.0, e100=100.0, 
        m_inertia=100.0, m_damper=0.0, m_friction=0.0
    )
    if res2["acc_clip"] == True and res2["acc_signal"] == 1.0:
        st.success("✅ **Test 2: ACC Signal Integrity** - Signal caps immaculately at 100% telemetry ceiling despite receiving a severely volatile 400% raw data spike.")
        tests_passed += 1
    else:
        st.error(f"❌ **Test 2 Failed** - Signal integrity compromised (acc_signal={res2['acc_signal']}).")

    # Test 3: Hardware Clipping Envelope Checks
    res3 = simulate_ffb_pure(
        raw_sustained=1.0, raw_transient=1.0, car_speed=1.0, wheel_vel=0.0, wheel_accel=0.0, 
        eq_weights={"10Hz":1.0}, max_tq=5.0, tq_limit=100.0, a_gain=100.0, a_dyn_damp=0.0, 
        m_ffb=100.0, m_road=10.0, e10=500.0, e15=100.0, e25=100.0, e40=100.0, e60=100.0, e100=100.0, 
        m_inertia=100.0, m_damper=0.0, m_friction=0.0
    )
    if res3["hw_clip"] == True and res3["final_nm"] == 5.0 and res3["requested_nm"] > 5.0:
        st.success("✅ **Test 3: HW Physical Clipping Limits** - Requested outputs correctly identified hardware boundaries and restricted structural peaks to wheelbase capacity (5.0 Nm).")
        tests_passed += 1
    else:
        st.error("❌ **Test 3 Failed** - Hardware limitation laws not enforced.")
        
    # Test 4: Extreme Mechanical Tax Floor
    res4 = simulate_ffb_pure(
        raw_sustained=0.0, raw_transient=1.0, car_speed=10.0, wheel_vel=100.0, wheel_accel=1000.0, 
        eq_weights={"10Hz":1.0}, max_tq=10.0, tq_limit=100.0, a_gain=100.0, a_dyn_damp=100.0, 
        m_ffb=100.0, m_road=10.0, e10=100.0, e15=100.0, e25=100.0, e40=100.0, e60=100.0, e100=100.0, 
        m_inertia=500.0, m_damper=100.0, m_friction=100.0
    )
    # Validate dampening behavior bottoms out at 0.05 instead of going negative
    expected_dampening_floor_reached = res4["total_tax"] > 10.0  
    dampened_ratio = res4["requested_nm"] / max(0.0001, res4["dsp_transient"])
    if expected_dampening_floor_reached and abs(dampened_ratio - 0.05) < 0.01:
        st.success("✅ **Test 4: Budget Deterioration Fallbacks** - Extreme mechanical tax constraints heavily dampen transients appropriately without mathematically resulting in an impossible negative force output.")
        tests_passed += 1
    else:
        st.error(f"❌ **Test 4 Failed** - Dampening logic generated anomalous figures. Ratio: {dampened_ratio:.3f}")
        
    if tests_passed == total_tests:
        st.info("🎯 **STATUS:** All underlying physics models and mathematical constraints successfully validated and factual.")
