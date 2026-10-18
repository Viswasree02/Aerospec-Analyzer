import json
import os

import pandas as pd
import streamlit as st

from ai_layer import AIConfigurationError, is_ai_configured, run_ai_gap_analysis
from database import get_all_audits, init_db, save_audit
from logic_layer import analyze_spec_logic


st.set_page_config(
    page_title="Aerospec Analyzer",
    page_icon="✈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
      :root { color-scheme: dark; }
      .stApp {
        background:
          radial-gradient(ellipse at 12% 0%, rgba(30, 89, 121, .22), transparent 34%),
          #0b1118;
        color: #e9f0f5;
        font-family: 'Manrope', sans-serif;
      }
      [data-testid="stSidebar"] {
        background: #0e1720;
        border-right: 1px solid rgba(160, 190, 210, .12);
      }
      [data-testid="stSidebar"] * { font-family: 'Manrope', sans-serif; }
      [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] p,
      [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] li,
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li {
        color: #c6d3dc;
      }
      [data-testid="stWidgetLabel"] p,
      [data-testid="stWidgetLabel"] label,
      [data-testid="stWidgetLabel"] span {
        color: #d7e1e8 !important;
      }
      [data-testid="stCaptionContainer"] p { color: #9fb1bf !important; }
      [data-testid="stAlert"] p { color: #dce7ee !important; }
      .stTabs [data-baseweb="tab"] { color: #b3c2cd; }
      .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #64d8c3 !important;
      }
      .eyebrow {
        color: #64d8c3;
        font-family: 'DM Mono', monospace;
        font-size: .76rem;
        letter-spacing: .15em;
        text-transform: uppercase;
      }
      .hero-title {
        color: #f3f7fa;
        font-size: clamp(2rem, 4vw, 3.3rem);
        font-weight: 800;
        letter-spacing: -.055em;
        line-height: 1.06;
        margin: .25rem 0 .65rem;
      }
      .hero-copy { color: #9db0be; font-size: 1rem; max-width: 760px; }
      .section-label {
        color: #64d8c3;
        font-family: 'DM Mono', monospace;
        font-size: .75rem;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      div[data-testid="stMetric"] {
        background: rgba(20, 32, 43, .86);
        border: 1px solid rgba(153, 184, 204, .14);
        border-radius: 12px;
        padding: 16px 18px;
      }
      div[data-testid="stMetricLabel"] { color: #a9bac7; }
      div[data-testid="stMetricValue"] { color: #f3f7fa; }
      div[data-testid="stForm"] {
        background: rgba(16, 26, 36, .84);
        border: 1px solid rgba(153, 184, 204, .16);
        border-radius: 14px;
        padding: 20px;
      }
      [data-testid="stButton"] button[kind="primary"],
      [data-testid="stFormSubmitButton"] button[kind="primary"] {
        background: #64d8c3 !important;
        border: 0 !important;
        color: #071512 !important;
        font-weight: 800;
      }
      [data-testid="stButton"] button[kind="primary"]:hover,
      [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
        background: #82ead6 !important;
        color: #071512 !important;
      }
      code, .mono { font-family: 'DM Mono', monospace; }
      hr { border-color: rgba(153, 184, 204, .14); }
    </style>
    """,
    unsafe_allow_html=True,
)

init_db()


def risk_label(score: float) -> str:
    if score >= 60:
        return "High"
    if score >= 30:
        return "Moderate"
    return "Low"


def render_audit_results(audit: dict) -> None:
    logic = audit["logic"]
    ai = audit.get("ai")

    st.markdown('<p class="section-label">Deterministic pre-check</p>', unsafe_allow_html=True)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Ambiguity index", f'{logic["ambiguity_score"]}%')
    metric_cols[1].metric("Specification length", f'{logic["word_count"]} words')
    metric_cols[2].metric("Vague terms", len(logic["vague_words_found"]))
    metric_cols[3].metric("Numbers without units", len(logic["missing_unit_numbers"]))

    if not logic["is_valid_length"]:
        st.warning(
            "This specification is under 25 words. The pre-check still ran, "
            "but the result may not represent the full engineering scope."
        )
    if logic["vague_words_found"]:
        st.markdown(
            "**Vague language detected:** "
            + ", ".join(f"`{word}`" for word in logic["vague_words_found"])
        )
    else:
        st.success("No terms from the deterministic vague-language list were found.")

    if logic["missing_unit_numbers"]:
        st.markdown(
            "**Numbers needing units:** "
            + ", ".join(f"`{number}`" for number in logic["missing_unit_numbers"])
        )
    if logic["valid_unit_numbers"]:
        st.markdown(
            "**Recognized values:** "
            + ", ".join(f"`{value}`" for value in logic["valid_unit_numbers"])
        )
    st.markdown(
        f"**Requirement language:** "
        f'{"Imperative wording found" if logic["has_imperative"] else "No shall/must/required-to wording found"}'
    )

    if ai:
        st.divider()
        st.markdown('<p class="section-label">AI engineering review</p>', unsafe_allow_html=True)
        st.markdown(ai["summary"])
        ai_cols = st.columns([1, 1])
        with ai_cols[0]:
            st.metric("AI confidence", f'{ai["confidence_score"]:.0%}')
        with ai_cols[1]:
            st.metric("AI-identified gaps", len(ai["identified_gaps"]))

        for index, gap in enumerate(ai["identified_gaps"], start=1):
            with st.expander(f'{index:02d} · {gap["category"]}'):
                st.markdown(f'**Issue:** {gap["issue"]}')
                st.markdown(f'**Engineering impact:** {gap["engineering_impact"]}')

        st.markdown("#### Required Simulation Inputs Checklist")
        missing_parameters = ai.get("missing_parameters", [])
        if missing_parameters:
            checklist = pd.DataFrame(missing_parameters).rename(
                columns={
                    "parameter_name": "Parameter Name",
                    "symbol_and_unit": "Symbol & Unit",
                    "solver_necessity": "Solver Necessity",
                    "typical_source": "Source",
                }
            )
            st.dataframe(checklist, width="stretch", hide_index=True)
        else:
            st.success("No additional required simulation inputs were identified.")

        st.markdown("#### Questions for the simulation lead")
        for question in ai["clarifying_questions"]:
            st.markdown(f"- {question}")


def render_dashboard() -> None:
    st.markdown('<p class="section-label">Local SQLite records</p>', unsafe_allow_html=True)
    try:
        records = get_all_audits()
    except Exception:
        st.error("The audit database could not be read.")
        return

    if records.empty:
        st.info("No audits have been saved yet. Run an audit to populate this dashboard.")
        return

    records["ai_status"] = records["ai_confidence"].apply(
        lambda confidence: "Complete" if pd.notna(confidence) else "Logic only"
    )
    records["risk"] = records["ambiguity_score"].apply(risk_label)
    high_risk_count = int((records["risk"] == "High").sum())
    ai_count = int((records["ai_status"] == "Complete").sum())

    metric_cols = st.columns(4)
    metric_cols[0].metric("Total audits", len(records))
    metric_cols[1].metric("Average ambiguity", f'{records["ambiguity_score"].mean():.1f}%')
    metric_cols[2].metric("High ambiguity", high_risk_count)
    metric_cols[3].metric("AI-reviewed", f"{ai_count} / {len(records)}")

    st.divider()
    search_col, subsystem_col, risk_col = st.columns([2, 1, 1])
    search = search_col.text_input("Search title or specification", key="audit_search")
    subsystem_options = ["All subsystems", *sorted(records["subsystem"].dropna().unique())]
    selected_subsystem = subsystem_col.selectbox("Subsystem", subsystem_options)
    risk_options = ["All levels", "High", "Moderate", "Low"]
    selected_risk = risk_col.selectbox("Ambiguity level", risk_options)

    filtered = records.copy()
    if search:
        search_lower = search.lower()
        filtered = filtered[
            filtered["title"].str.lower().str.contains(search_lower, na=False)
            | filtered["raw_text"].str.lower().str.contains(search_lower, na=False)
        ]
    if selected_subsystem != "All subsystems":
        filtered = filtered[filtered["subsystem"] == selected_subsystem]
    if selected_risk != "All levels":
        filtered = filtered[filtered["risk"] == selected_risk]

    display_columns = [
        "timestamp",
        "title",
        "subsystem",
        "regime",
        "ambiguity_score",
        "risk",
        "missing_units_count",
        "ai_status",
        "ai_confidence",
    ]
    st.dataframe(
        filtered[display_columns],
        width="stretch",
        hide_index=True,
        column_config={
            "timestamp": st.column_config.TextColumn("UTC timestamp"),
            "ambiguity_score": st.column_config.NumberColumn(
                "Ambiguity", format="%.1f%%"
            ),
            "ai_confidence": st.column_config.NumberColumn(
                "AI confidence", format="%.0%%"
            ),
            "missing_units_count": st.column_config.NumberColumn("Missing units"),
        },
    )

    export_csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered audits (CSV)",
        data=export_csv,
        file_name="aerospec-audit-history.csv",
        mime="text/csv",
    )

    if not filtered.empty:
        st.divider()
        options = filtered["id"].tolist()
        selected_id = st.selectbox(
            "Inspect a saved audit",
            options,
            format_func=lambda record_id: (
                f'#{record_id} · {filtered.loc[filtered["id"] == record_id, "title"].iloc[0]}'
            ),
        )
        selected = filtered.loc[filtered["id"] == selected_id].iloc[0]
        st.markdown(
            f'**{selected["title"]}** · {selected["subsystem"]} · {selected["regime"]}'
        )
        with st.expander("Original specification"):
            st.text(selected["raw_text"])

        gaps = json.loads(selected["gaps_json"] or "[]")
        questions = json.loads(selected["questions_json"] or "[]")
        if gaps:
            st.markdown("**AI gaps**")
            for gap in gaps:
                st.markdown(
                    f'- **{gap.get("category", "Gap")}:** {gap.get("issue", "")} '
                    f'— {gap.get("engineering_impact", "")}'
                )
        if questions:
            st.markdown("**Clarifying questions**")
            for question in questions:
                st.markdown(f"- {question}")


with st.sidebar:
    st.markdown('<p class="eyebrow">AEROSPEC / ANALYZER</p>', unsafe_allow_html=True)
    st.markdown("### Review before simulation")
    if is_ai_configured():
        st.success("Gemini analysis · configured")
    else:
        st.warning("Gemini analysis · API key needed")
        st.caption(
            "Deterministic checks and the local audit dashboard work without an API key."
        )
    st.divider()
    st.caption("Audit records are stored in a local SQLite database for this project.")
    st.caption(
        "When AI review runs, the specification text and selected metadata are sent to Google Gemini."
    )

st.markdown('<p class="eyebrow">ENGINEERING REQUIREMENTS / REVIEW WORKSPACE</p>', unsafe_allow_html=True)
st.markdown('<h1 class="hero-title">Aerospace specification<br>audit</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-copy">Catch ambiguity, missing units, and simulation-critical '
    'gaps before a specification reaches the meshing queue.</p>',
    unsafe_allow_html=True,
)
st.write("")

workspace_tab, dashboard_tab = st.tabs(["New audit", "Audit dashboard"])

with workspace_tab:
    st.markdown('<p class="section-label">01 / Submit a specification</p>', unsafe_allow_html=True)
    st.info(
        "AI review sends the submitted specification to Google Gemini. Avoid entering "
        "confidential information unless your organization permits that use."
    )
    with st.form("specification_audit_form", clear_on_submit=False):
        title = st.text_input(
            "Audit title",
            placeholder="e.g. Nacelle inlet at cruise condition",
            max_chars=120,
        )
        subsystem_col, regime_col = st.columns(2)
        subsystem = subsystem_col.selectbox(
            "Subsystem",
            [
                "Aerodynamics",
                "Propulsion",
                "Structures",
                "Thermal",
                "Controls",
                "Other",
                "Intake & Propulsion Ducting",
                "Wing / Aerofoil High-Lift Devices",
                "Fuselage Fairings & Radomes",
                "Thermal Control / Cooling Circuit",
                "Pylon & Bracket Structural Mount",
            ],
        )
        regime = regime_col.selectbox(
            "Flow / operating regime",
            [
                "Not specified",
                "Subsonic",
                "Transonic",
                "Supersonic",
                "Hypersonic",
                "Other",
            ],
        )
        spec_text = st.text_area(
            "Simulation work request",
            placeholder=(
                "Describe the geometry, operating conditions, boundary conditions, "
                "targets, and acceptance criteria..."
            ),
            height=220,
            max_chars=20000,
        )
        submitted = st.form_submit_button("Run specification audit", type="primary")

    if submitted:
        if not title.strip():
            st.error("Add an audit title before submitting.")
        elif not spec_text.strip():
            st.error("Enter a simulation work request before submitting.")
        else:
            with st.spinner("Running deterministic checks and AI review..."):
                logic = analyze_spec_logic(spec_text)
                ai_results = None
                ai_error = None
                try:
                    ai_results = run_ai_gap_analysis(
                        spec_text=spec_text,
                        subsystem=subsystem,
                        regime=regime,
                        logic_summary=logic,
                    )
                except AIConfigurationError:
                    ai_error = (
                        "Gemini review was skipped because GEMINI_API_KEY is not "
                        "configured. The deterministic audit is still available."
                    )
                except Exception:
                    ai_error = (
                        "Gemini review could not be completed. The deterministic "
                        "audit is still available; check the API key and account access."
                    )

                try:
                    audit_id = save_audit(
                        title=title.strip(),
                        subsystem=subsystem,
                        regime=regime,
                        raw_text=spec_text.strip(),
                        logic_results=logic,
                        ai_results=ai_results,
                    )
                except Exception:
                    audit_id = None

            st.session_state["last_audit"] = {
                "id": audit_id,
                "title": title.strip(),
                "subsystem": subsystem,
                "regime": regime,
                "logic": logic,
                "ai": ai_results,
            }
            if ai_error:
                st.warning(ai_error)
            if audit_id is None:
                st.error("The audit ran, but it could not be saved to the local database.")
            else:
                st.success(f"Audit #{audit_id} saved to the local history.")

    last_audit = st.session_state.get("last_audit")
    if last_audit:
        st.divider()
        st.markdown(
            f'### Latest result · {last_audit["title"]} '
            f'{"· Audit #" + str(last_audit["id"]) if last_audit["id"] else ""}'
        )
        render_audit_results(last_audit)

with dashboard_tab:
    st.markdown('<p class="section-label">02 / Audit history</p>', unsafe_allow_html=True)
    render_dashboard()

st.markdown("---")
st.caption(
    "Aerospec Analyzer is a screening aid. Engineering review and approved "
    "simulation procedures remain the authority for sign-off."
)
