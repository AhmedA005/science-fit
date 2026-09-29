"""
Science-Fit Web Application.

Design: ENERGY 2 / RHYTHM 2 / MOTION 1 — clean and direct.
Theme colours live in .streamlit/config.toml (amber primary, warm off-white base).
IBM Plex Sans loaded via font import only; all layout uses native Streamlit components.

Usage:
    streamlit run app.py
"""

import asyncio
import uuid
import yaml
import streamlit as st
import pandas as pd
from langchain_core.messages import HumanMessage

from src.agent.graph import fitness_agent_app
from src.config import Config
from src.schemas import FullUserContext, UserPreferencesSchema, UserProfileSchema
from src.services.training_engine import TrainingEngine

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Science-Fit",
    page_icon="⚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Font import only — no colour overrides (those live in config.toml) ────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', system-ui, sans-serif !important;
}

/* Monospace only on metric values — keeps numbers feeling like data */
[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 1.4rem !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.78rem !important;
}

/* Tighter main column */
.block-container {
    padding-top: 28px;
    padding-bottom: 60px;
    max-width: 960px;
}

/* Tabs */
[data-testid="stTabs"] button {
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
}

/* Section divider label */
.sf-section {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: #8B909F;
    margin: 8px 0 4px 0;
}

/* Rule card */
.sf-card {
    background: #FFFFFF;
    border: 1px solid #E4E2DC;
    border-radius: 6px;
    padding: 14px 16px;
    margin-bottom: 2px;
    height: 100%;
}
.sf-card h4 {
    font-size: 0.78rem;
    font-weight: 600;
    color: #5C6070;
    margin: 0 0 5px 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.sf-card p {
    font-size: 0.875rem;
    color: #1A1E26;
    margin: 0 0 4px 0;
    line-height: 1.5;
}
.sf-card .note {
    font-size: 0.8rem;
    color: #5C6070;
    line-height: 1.5;
}
.sf-card .cite {
    font-size: 0.72rem;
    color: #8B909F;
    margin-top: 8px;
    display: block;
}

/* Split day pill */
.sf-day {
    background: #FFFFFF;
    border: 1px solid #E4E2DC;
    border-radius: 5px;
    padding: 10px 14px;
    font-size: 0.85rem;
    color: #1A1E26;
    display: inline-block;
    margin: 0 6px 6px 0;
    line-height: 1.4;
}
.sf-day b {
    display: block;
    font-size: 0.72rem;
    color: #8B909F;
    font-weight: 500;
    margin-bottom: 1px;
}

/* Limitation box */
.sf-limit {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-radius: 5px;
    padding: 11px 15px;
    font-size: 0.82rem;
    color: #92400E;
    line-height: 1.55;
    margin-top: 6px;
}

/* Chat meta tags */
.sf-meta-tag {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: #5C6070;
    background: #EEECEA;
    border: 1px solid #E4E2DC;
    border-radius: 3px;
    padding: 2px 6px;
    margin-right: 4px;
    margin-bottom: 4px;
}
.sf-meta-tag.intent {
    color: #059669;
    background: #ECFDF5;
    border-color: #A7F3D0;
}

/* Hide avatars in chat for a cleaner look */
[data-testid="chatAvatarIcon-user"],
[data-testid="chatAvatarIcon-assistant"] {
    display: none !important;
}

/* Error block */
.sf-error {
    background: #FEF2F2;
    border: 1px solid #FECACA;
    border-radius: 6px;
    padding: 12px 16px;
    color: #DC2626;
    font-size: 0.875rem;
}

/* Sidebar label */
.sf-sidebar-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: #8B909F;
    margin: 18px 0 6px 0;
    display: block;
}
</style>
""", unsafe_allow_html=True)


# ── Config loaders ────────────────────────────────────────────────────────────
@st.cache_data
def load_training_config() -> dict:
    with open(Config.TRAINING_CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Session state ─────────────────────────────────────────────────────────────
if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"web-{str(uuid.uuid4())[:8]}"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# ── Sidebar: profile inputs ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<span class="sf-sidebar-label">Profile</span>', unsafe_allow_html=True)

    name = st.text_input("Name", value="Alex")
    c1, c2 = st.columns(2)
    with c1:
        age = st.number_input("Age", min_value=16, max_value=90, value=25, step=1)
        height_cm = st.number_input("Height (cm)", min_value=120.0, max_value=230.0, value=178.0, step=0.5)
    with c2:
        gender = st.selectbox("Gender", options=["male", "female"])
        weight_kg = st.number_input("Weight (kg)", min_value=40.0, max_value=220.0, value=80.0, step=0.5)

    st.markdown('<span class="sf-sidebar-label">Training</span>', unsafe_allow_html=True)

    experience_level = st.selectbox(
        "Experience",
        options=["beginner", "intermediate", "advanced"],
        index=1,
        help="Determines your MEV and MRV thresholds.",
    )
    goal = st.selectbox(
        "Goal",
        options=["muscle_gain", "fat_loss", "maintenance", "general_fitness"],
    )
    training_days = st.slider("Days / week", min_value=2, max_value=6, value=4)
    duration_min = st.number_input("Session length (min)", min_value=30, max_value=150, value=60, step=5)
    activity_level = st.selectbox(
        "Daily activity (outside gym)",
        options=["sedentary", "lightly_active", "moderately_active", "very_active", "extremely_active"],
        index=2,
    )

    st.divider()
    if st.button("Reset conversation", use_container_width=True):
        st.session_state.thread_id = f"web-{str(uuid.uuid4())[:8]}"
        st.session_state.chat_history = []
        st.rerun()


# ── Build deterministic plan ──────────────────────────────────────────────────
user_profile = UserProfileSchema(
    id=1,
    name=name,
    age=int(age),
    gender=gender,
    height_cm=float(height_cm),
    weight_kg=float(weight_kg),
    experience_level=experience_level,
    goal=goal,
    training_days_per_week=int(training_days),
    session_duration_minutes=int(duration_min),
)
user_context_obj = TrainingEngine.build_custom_context(user_profile, activity_level=activity_level)
nutrition = user_context_obj.nutrition
engine_context_text = TrainingEngine.format_context_for_llm(user_context_obj)
training_cfg = load_training_config()

# Derived values
p_per_kg = round(nutrition.protein_target_g / max(user_profile.weight_kg, 1.0), 1)
adj = nutrition.goal_adjustment_kcal
if adj > 0:
    adj_label = f"+{adj:.0f} kcal surplus"
elif adj < 0:
    adj_label = f"{adj:.0f} kcal deficit"
else:
    adj_label = "0 kcal (maintenance)"

GOAL_LABELS = {
    "muscle_gain": "Muscle Gain",
    "fat_loss": "Fat Loss",
    "maintenance": "Maintenance",
    "general_fitness": "General Fitness",
}

# Training split
SPLIT_TEMPLATES = {
    "full_body": ("Full Body", [
        ("Full Body A", "Squat, horizontal push/pull, core"),
        ("Full Body B", "Hinge, vertical push/pull, accessories"),
        ("Full Body C", "Squat variation, arms, core"),
        ("Full Body D", "Upper emphasis, isolation"),
        ("Full Body E", "Lower emphasis, conditioning"),
        ("Full Body F", "Full body volume"),
    ]),
    "upper_lower": ("Upper / Lower", [
        ("Upper A", "Horizontal push + pull, shoulders"),
        ("Lower A", "Squat + hinge, quads, hamstrings"),
        ("Upper B", "Vertical push + pull, arms"),
        ("Lower B", "Posterior chain, glutes, calves"),
        ("Upper C", "Volume upper, isolation"),
        ("Lower C", "Volume lower, accessories"),
    ]),
    "upper_lower_pull_push_legs": ("Upper / Lower / Push / Pull / Legs", [
        ("Upper", "Horizontal + vertical push/pull"),
        ("Lower", "Squat + hinge balance"),
        ("Pull", "Back, biceps, rear delts"),
        ("Push", "Chest, shoulders, triceps"),
        ("Legs", "Quads, hamstrings, glutes, calves"),
    ]),
    "push_pull_legs": ("Push / Pull / Legs (PPL)", [
        ("Push A", "Chest, shoulders, triceps"),
        ("Pull A", "Back, biceps, rear delts"),
        ("Legs A", "Quads, hamstrings, glutes, calves"),
        ("Push B", "Chest, shoulders, triceps"),
        ("Pull B", "Back, biceps, rear delts"),
        ("Legs B", "Quads, hamstrings, glutes, calves"),
    ]),
}
split_key = training_cfg["frequency_guidelines"]["schedule_templates"].get(
    f"{int(training_days)}_days", "full_body"
)
split_name, split_all_days = SPLIT_TEMPLATES.get(split_key, SPLIT_TEMPLATES["full_body"])
split_days = split_all_days[:int(training_days)]

# Volume landmarks
vol_cfg = training_cfg["volume_guidelines"].get(experience_level, {})
mev = vol_cfg.get("minimum_effective", 6)
mrv = vol_cfg.get("maximum_recoverable", 20)
rec_lo, rec_hi = vol_cfg.get("recommended_range", [8, 15])

MUSCLES = [
    "Chest", "Back", "Quads", "Hamstrings",
    "Shoulders", "Biceps", "Triceps", "Glutes",
]

# Rep/RIR
rep_cfg = training_cfg["rep_ranges"]
if goal in ("muscle_gain", "fat_loss", "general_fitness"):
    rep_lo, rep_hi = rep_cfg["hypertrophy"]["typical_range"]
else:
    rep_lo, rep_hi = rep_cfg["strength"]["primary_range"]

rir_cfg = training_cfg["rir_guidelines"]["hypertrophy"]
rir_compound = rir_cfg["compound_exercises"]["typical_range"]
rir_iso = rir_cfg["isolation_exercises"]["typical_range"]

load_incr = training_cfg["progression"]["load_increments"]
deload_min = training_cfg["recovery_rules"]["deload"]["frequency_weeks_min"]
deload_max = training_cfg["recovery_rules"]["deload"]["frequency_weeks_max"]


# ── Main layout ───────────────────────────────────────────────────────────────
st.subheader(f"Science-Fit — {name}")
st.caption(
    f"{GOAL_LABELS.get(goal, goal)} · {int(training_days)}×/week · "
    f"{experience_level.capitalize()} · "
    "Numbers from peer-reviewed physiology, not estimated by the AI."
)
st.divider()

tab_plan, tab_chat = st.tabs(["Your Plan", "Ask the Coach"])


# ══ PLAN TAB ═════════════════════════════════════════════════════════════════
with tab_plan:

    # ── Nutrition ─────────────────────────────────────────────────────────────
    st.markdown('<p class="sf-section">Nutrition</p>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Daily Calories", f"{nutrition.calorie_target:,.0f} kcal", delta=adj_label)
    c2.metric("Protein", f"{nutrition.protein_target_g:.0f} g", delta=f"{p_per_kg} g/kg · Morton 2018")
    c3.metric("Carbohydrates", f"{nutrition.carb_target_g:.0f} g", delta="Fills remaining calories")
    c4.metric("Fats", f"{nutrition.fat_target_g:.0f} g", delta="Min 20% · Iraki 2019")

    st.caption(
        f"BMR {nutrition.bmr:,.0f} kcal (Mifflin-St Jeor) "
        f"× {nutrition.activity_factor} activity factor "
        f"= TDEE {nutrition.tdee:,.0f} kcal · then {adj_label}"
    )

    st.markdown('<div class="sf-limit">Calorie estimates carry an inherent ±10–15% error. '
                'Mifflin-St Jeor is a population average, not individual physiology. '
                'Treat these as starting points and adjust after 2–4 weeks of observed weight change.</div>',
                unsafe_allow_html=True)

    st.divider()

    # ── Training Split ────────────────────────────────────────────────────────
    st.markdown('<p class="sf-section">Training Split</p>', unsafe_allow_html=True)
    st.write(f"**{split_name}** — {int(training_days)} training days")

    days_html = " ".join(
        f'<span class="sf-day"><b>Day {i+1}</b>{label}<br>'
        f'<span style="font-size:0.75rem;color:#8B909F;">{focus}</span></span>'
        for i, (label, focus) in enumerate(split_days)
    )
    st.markdown(days_html, unsafe_allow_html=True)
    st.caption("Source: Schoenfeld 2019, ACSM frequency guidelines.")

    st.divider()

    # ── Volume Landmarks ──────────────────────────────────────────────────────
    st.markdown('<p class="sf-section">Weekly Volume — Sets per Muscle Group</p>', unsafe_allow_html=True)
    st.write(
        f"For **{experience_level}** trainees: "
        f"MEV {mev} sets · Recommended {rec_lo}–{rec_hi} sets · MRV {mrv} sets"
    )

    vol_data = {
        "Muscle": MUSCLES,
        "MEV (min)": [mev] * len(MUSCLES),
        "Recommended": [f"{rec_lo}–{rec_hi}"] * len(MUSCLES),
        "MRV (max)": [mrv] * len(MUSCLES),
    }
    vol_df = pd.DataFrame(vol_data)
    st.dataframe(
        vol_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Muscle": st.column_config.TextColumn("Muscle Group", width="medium"),
            "MEV (min)": st.column_config.NumberColumn("MEV — Min Effective", width="small"),
            "Recommended": st.column_config.TextColumn("Recommended Range", width="medium"),
            "MRV (max)": st.column_config.NumberColumn("MRV — Max Recoverable", width="small"),
        },
    )
    st.caption("MEV = Minimum Effective Volume · MRV = Maximum Recoverable Volume · Source: Schoenfeld 2017, ACSM 2009")

    st.divider()

    # ── Training Rules ────────────────────────────────────────────────────────
    st.markdown('<p class="sf-section">Training Rules</p>', unsafe_allow_html=True)

    r1, r2, r3 = st.columns(3)
    with r1:
        st.markdown(f"""
<div class="sf-card">
    <h4>Rep Range</h4>
    <p>{rep_lo}–{rep_hi} reps per working set</p>
    <p class="note">Hypertrophy occurs across 5–30 reps when taken close to failure. Pick weights you can control.</p>
    <span class="cite">Schoenfeld 2021 · Refalo 2023</span>
</div>""", unsafe_allow_html=True)

    with r2:
        st.markdown(f"""
<div class="sf-card">
    <h4>Reps in Reserve (RIR)</h4>
    <p>Compounds: {rir_compound[0]}–{rir_compound[1]} RIR</p>
    <p>Isolations: {rir_iso[0]}–{rir_iso[1]} RIR</p>
    <p class="note">Stop before form breaks down. Failure reserved for isolation work only — max 2 failure sets per session.</p>
    <span class="cite">Refalo 2023</span>
</div>""", unsafe_allow_html=True)

    with r3:
        st.markdown(f"""
<div class="sf-card">
    <h4>Progression — Double Progression</h4>
    <p>Add reps each session. When all sets hit the top of your range at target RIR, add weight:</p>
    <p>Upper body +{load_incr["upper_body_kg"]} kg &nbsp;·&nbsp; Lower +{load_incr["lower_body_kg"]} kg &nbsp;·&nbsp; Isolation +{load_incr["isolation_kg"]} kg</p>
    <span class="cite">ACSM 2009</span>
</div>""", unsafe_allow_html=True)

    r4, r5, r6 = st.columns(3)
    with r4:
        st.markdown(f"""
<div class="sf-card">
    <h4>Session Volume Cap</h4>
    <p>Max 10 working sets per muscle per session</p>
    <p class="note">Spread volume across the week instead. Sets beyond this accumulate fatigue without additional stimulus.</p>
    <span class="cite">Nippard Fundamentals</span>
</div>""", unsafe_allow_html=True)

    with r5:
        st.markdown(f"""
<div class="sf-card">
    <h4>Deload — Every {deload_min}–{deload_max} Weeks</h4>
    <p>Cut volume by 50%. Keep load and RIR the same.</p>
    <p class="note">Deloads restore recovery capacity without losing fitness. Do not skip them when feeling good — that is when they matter most.</p>
    <span class="cite">ACSM 2009</span>
</div>""", unsafe_allow_html=True)

    with r6:
        st.markdown(f"""
<div class="sf-card">
    <h4>Frequency</h4>
    <p>Each muscle: 2× per week recommended</p>
    <p class="note">Frequency does not drive hypertrophy when weekly volume is equated — but splitting across 2 sessions reduces per-session fatigue.</p>
    <span class="cite">Schoenfeld 2019 · Grgic 2018</span>
</div>""", unsafe_allow_html=True)


# ══ CHAT TAB ═════════════════════════════════════════════════════════════════
with tab_chat:

    if not st.session_state.chat_history:
        st.caption(
            "Your full plan is on the first tab. "
            "Use this for anything that needs more context — exercise selection, "
            "substitutions, what the volume numbers mean for your specific situation, "
            "or what-if scenarios."
        )

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                tags = ""
                if msg.get("intent"):
                    tags += f'<span class="sf-meta-tag intent">{msg["intent"]}</span>'
                for tool in msg.get("tools", []):
                    tags += f'<span class="sf-meta-tag">{tool}</span>'
                if tags:
                    st.markdown(tags, unsafe_allow_html=True)
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask about your plan...")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Consulting physiology literature..."):
                config = {"configurable": {"thread_id": st.session_state.thread_id}}
                state_input = {
                    "messages": [HumanMessage(content=user_input)],
                    "user_id": user_profile.id,
                    "user_context": FullUserContext(
                        profile=user_profile,
                        preferences=UserPreferencesSchema(),
                    ),
                    "nutrition_targets": nutrition,
                    "engine_context_text": engine_context_text,
                }
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(
                        fitness_agent_app.ainvoke(state_input, config=config)
                    )
                    loop.close()

                    intent = result.get("intent", "general")
                    messages = result.get("messages", [])

                    tools_used = []
                    for m in messages:
                        if hasattr(m, "tool_calls") and m.tool_calls:
                            for tc in m.tool_calls:
                                tools_used.append(tc["name"])

                    tags = f'<span class="sf-meta-tag intent">{intent}</span>'
                    for tool_name in tools_used:
                        tags += f'<span class="sf-meta-tag">{tool_name}</span>'
                    st.markdown(tags, unsafe_allow_html=True)

                    last_msg = messages[-1] if messages else None
                    response_text = last_msg.content if last_msg else "No response generated."
                    st.markdown(response_text)

                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response_text,
                        "intent": intent,
                        "tools": tools_used,
                    })

                except Exception as e:
                    st.markdown(
                        f'<div class="sf-error">Error: {e}</div>',
                        unsafe_allow_html=True,
                    )
