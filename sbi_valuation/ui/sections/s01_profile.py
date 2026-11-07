"""Section 1 — Business Profile."""
import streamlit as st

from ...models.assessment import (
    LEGAL_STRUCTURE_LABELS,
    LEGAL_STRUCTURES,
    OWNER_INVOLVEMENT_LABELS,
    OWNER_INVOLVEMENT,
    PURPOSE_LABELS,
    PURPOSES,
)
from .. import state, theme
from ..edu import edu

INDUSTRIES = [
    "", "Retail", "Food service / restaurant", "Construction & trades",
    "Manufacturing", "Wholesale & distribution", "Professional services",
    "Health & personal services", "Automotive", "Agriculture",
    "Hospitality & lodging", "Transportation & logistics",
    "Technology / software", "Real estate & property services",
    "Education & childcare", "Arts & recreation", "Other",
]


def render(a, r) -> None:
    theme.header("Business Profile", "Tell us about the business")
    st.markdown(
        '<div class="sbv-section-intro">A short profile tailors the '
        "guidance and helps determine which valuation methods fit. None of "
        "this changes the math directly — it shapes the explanation.</div>",
        unsafe_allow_html=True,
    )

    p = a.profile
    state.seed("in_business_name", p.business_name)
    state.seed("in_industry", p.industry)
    state.seed("in_specialization", p.specialization)
    state.seed("in_years", p.years_operating)
    state.seed("in_structure", p.legal_structure)
    state.seed("in_city", p.city)
    state.seed("in_state", p.state)
    state.seed("in_involvement", p.owner_involvement)
    state.seed("in_employees", p.employee_count)
    state.seed("in_owners", p.working_owners)
    state.seed("in_purposes", p.purposes)

    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Business name", key="in_business_name",
                      placeholder="Optional — helps label reports")
        st.selectbox("Primary industry", INDUSTRIES, key="in_industry",
                     format_func=lambda x: x or "Select…")
        st.text_input("What does the business do specifically?",
                      key="in_specialization",
                      placeholder="e.g. residential HVAC repair, specialty bakery")
        st.number_input("Years operating", min_value=0.0, max_value=200.0,
                        step=0.5, key="in_years",
                        format="%.1f")
        st.selectbox("Legal structure", LEGAL_STRUCTURES, key="in_structure",
                     format_func=lambda x: LEGAL_STRUCTURE_LABELS.get(x, "Select…") if x else "Select…")
    with col2:
        st.text_input("City", key="in_city")
        st.text_input("State", key="in_state")
        st.selectbox("Your involvement in day-to-day operations",
                     OWNER_INVOLVEMENT, key="in_involvement",
                     format_func=lambda x: OWNER_INVOLVEMENT_LABELS.get(x) if x else "Select…")
        st.number_input("Number of employees (excluding owners)",
                        min_value=0, max_value=100000, step=1, key="in_employees")
        st.number_input("Owners who work in the business",
                        min_value=1, max_value=20, step=1, key="in_owners")

    st.multiselect(
        "Why are you doing this valuation? (choose any)",
        PURPOSES,
        key="in_purposes",
        format_func=lambda x: PURPOSE_LABELS.get(x, x),
    )

    # write back
    p.business_name = state.pull("in_business_name") or ""
    p.industry = state.pull("in_industry") or ""
    p.specialization = state.pull("in_specialization") or ""
    p.years_operating = state.pull("in_years")
    p.legal_structure = state.pull("in_structure") or ""
    p.city = state.pull("in_city") or ""
    p.state = state.pull("in_state") or ""
    p.owner_involvement = state.pull("in_involvement") or ""
    p.employee_count = state.pull("in_employees")
    p.working_owners = int(state.pull("in_owners") or 1)
    p.purposes = state.pull("in_purposes") or []
    a.label = p.business_name

    edu("About this section", {
        "what": "The profile describes the business in plain terms. Only a few fields are required for a valuation — industry, a financial period, and your earnings basis matter most.",
        "why": [
            "Owner involvement and working-owner count affect how earnings are normalized (SDE).",
            "Purpose shapes which outputs are emphasized (sale planning vs. improvement).",
        ],
        "value": "The profile itself never adds or subtracts value — it ensures the right method and the right questions are applied.",
        "mistakes": "Leaving owner involvement blank when the business depends on you — it drives important risk questions later.",
    })

    if p.working_owners > 1:
        st.info(
            "Note: with more than one working owner, SDE normally adds back "
            "only ONE owner's compensation. You'll review this in Adjusted "
            "Earnings."
        )
