"""Sidebar workflow navigation with completion indicators."""
import streamlit as st

from ..engine.drivers import CATEGORIES
from . import state

SECTIONS = [
    ("profile", "Business Profile"),
    ("financials", "Financial Snapshot"),
    ("earnings", "Adjusted Earnings"),
    ("drivers", "Business Value Drivers"),
    ("results", "Valuation Results"),
    ("explorer", "Value Explorer"),
    ("pricing", "Price-to-Sale Explorer"),
    ("report", "Report & Action Plan"),
]


def completion(section_id: str, a, r) -> str:
    """Return 'done' | 'partial' | 'empty' for a section."""
    if section_id == "profile":
        p = a.profile
        filled = [p.business_name, p.industry, p.owner_involvement,
                  p.legal_structure, p.purposes]
        n = sum(bool(x) for x in filled)
        return "done" if n >= 4 else ("partial" if n else "empty")
    if section_id == "financials":
        if not a.financials:
            return "empty"
        prim = a.primary_period()
        if prim and prim.reported_profit is not None and prim.profit_basis != "unknown":
            return "done"
        return "partial"
    if section_id == "earnings":
        if r.normalization is None or r.normalization.reported_profit is None:
            return "empty"
        if r.normalization.basis_established and not r.normalization.flags:
            return "done"
        return "partial" if not a.adjustments else "partial"
    if section_id == "drivers":
        total = sum(len(c["questions"]) for c in CATEGORIES)
        n = len([v for v in a.driver_answers.values() if v])
        if n >= total:
            return "done"
        return "partial" if n else "empty"
    if section_id == "results":
        runnable = any(i.runnable for i in r.valuations.values())
        return "done" if runnable else ("partial" if a.financials else "empty")
    if section_id == "explorer":
        return "done" if a.scenarios else ("partial" if r.sde is not None else "empty")
    if section_id == "pricing":
        return "done" if a.asking_price else ("partial" if any(
            i.runnable for i in r.valuations.values()) else "empty")
    if section_id == "report":
        return "done" if a.action_items else ("partial" if any(
            i.runnable for i in r.valuations.values()) else "empty")
    return "empty"


_ICON = {"done": "●", "partial": "◐", "empty": "○"}


def render_sidebar(a, r) -> str:
    if "active_section" not in st.session_state:
        st.session_state.active_section = "profile"
    active = st.session_state.active_section

    st.sidebar.markdown("**Workflow**")
    for i, (sid, label) in enumerate(SECTIONS, start=1):
        status = completion(sid, a, r)
        btn_label = f"{_ICON[status]}  {i}. {label}"
        if st.sidebar.button(
            btn_label,
            key=f"nav_{sid}",
            type="primary" if sid == active else "secondary",
            width="stretch",
        ):
            st.session_state.active_section = sid
            st.rerun()

    st.sidebar.caption("● complete  ◐ in progress  ○ not started")
    return active
