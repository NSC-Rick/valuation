"""Section 2 — Financial Snapshot (up to 3 fiscal years + optional YTD)."""
import streamlit as st

from ...models.assessment import (
    FinancialPeriod,
    INFO_SOURCE_LABELS,
    INFO_SOURCES,
    PROFIT_BASE_LABELS,
    PROFIT_BASES,
)
from .. import state, theme
from ..edu import edu


def _period_form(idx: int, p: FinancialPeriod, primary_label: str) -> FinancialPeriod:
    pre = f"in_p{idx}_"
    state.seed(pre + "label", p.label)
    state.seed(pre + "months", p.months)
    state.seed(pre + "revenue", p.revenue)
    state.seed(pre + "profit", p.reported_profit)
    state.seed(pre + "basis", p.profit_basis)
    state.seed(pre + "comp", p.owner_compensation)
    state.seed(pre + "draws", p.owner_draws)
    state.seed(pre + "source", p.info_source)
    state.seed(pre + "stmts", p.statements_available)

    is_ytd = p.kind == "ytd"
    title = ("Year-to-date period" if is_ytd else f"Fiscal year {idx + 1}")
    if p.label:
        title += f" — {p.label}"
    if p.label == primary_label:
        title += "  ⭐ primary"
    with st.expander(title, expanded=(idx == 0 or not p.label)):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.text_input("Period label", key=pre + "label",
                          placeholder="e.g. FY 2024" if not is_ytd else "e.g. Jan–Sep 2025")
        with c2:
            if is_ytd:
                st.number_input("Months covered", min_value=1, max_value=11,
                                key=pre + "months")
        with c3:
            st.checkbox("Financial statements available", key=pre + "stmts")

        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Annual revenue ($)", min_value=0.0, step=1000.0,
                            key=pre + "revenue", format="%.2f",
                            help="Total sales for the period")
            st.number_input("Reported profit ($)", step=1000.0,
                            key=pre + "profit", format="%.2f",
                            help="May be negative — enter as a negative number")
            st.selectbox("That profit figure is…", PROFIT_BASES, key=pre + "basis",
                         format_func=lambda x: PROFIT_BASE_LABELS.get(x, x))
        with c2:
            st.number_input("Your compensation from the business ($)",
                            min_value=0.0, step=1000.0, key=pre + "comp",
                            format="%.2f",
                            help="Salary/wages/benefits the primary working "
                                 "owner received — deducted as an expense")
            st.number_input("Owner draws / distributions ($, optional)",
                            min_value=0.0, step=1000.0, key=pre + "draws",
                            format="%.2f",
                            help="Informational only — draws are not expenses "
                                 "and are never added back")
            st.selectbox("These figures come from…", INFO_SOURCES,
                         key=pre + "source",
                         format_func=lambda x: INFO_SOURCE_LABELS.get(x, "Select…") if x else "Select…")

        if state.pull(pre + "basis") == "unknown":
            st.warning("Identify the profit basis before earnings can be normalized — check your P&L or ask your accountant.")
        if state.pull(pre + "profit") is not None and state.pull(pre + "profit") < 0:
            st.info("Negative earnings are okay to enter — the app will flag what that means for valuation methods.")

    p.label = state.pull(pre + "label") or p.label
    if is_ytd:
        p.months = int(state.pull(pre + "months") or p.months)
    p.revenue = state.pull(pre + "revenue")
    p.reported_profit = state.pull(pre + "profit")
    p.profit_basis = state.pull(pre + "basis") or "unknown"
    p.owner_compensation = state.pull(pre + "comp")
    p.owner_draws = state.pull(pre + "draws")
    p.info_source = state.pull(pre + "source") or ""
    p.statements_available = bool(state.pull(pre + "stmts"))
    return p


def render(a, r) -> None:
    theme.header("Financial Snapshot", "Your most recent financial results")
    st.markdown(
        '<div class="sbv-section-intro">Enter results for your most recent '
        "completed fiscal year, plus up to two prior years and an optional "
        "year-to-date period. Estimates are fine to start — mark where the "
        "numbers come from.</div>",
        unsafe_allow_html=True,
    )

    edu("About this section", {
        "what": "A 'snapshot' is summary financial information for one period — revenue and profit, plus what kind of profit figure it is.",
        "why": [
            "The profit *basis* (net income vs. operating income vs. EBITDA) determines which adjustments are legitimate later.",
            "Owner compensation matters because SDE adds back what the working owner took out of the business.",
        ],
        "mistakes": [
            "Mixing periods (e.g. revenue from 2024, profit from 2023).",
            "Entering draws as if they were an expense — they're distributions of profit.",
            "Guessing the profit basis — 'not sure' pauses normalization until resolved.",
        ],
        "next": "After saving your snapshot, go to Adjusted Earnings.",
    })

    # Ensure at least one fiscal-year period exists
    if not a.financials:
        a.financials.append(FinancialPeriod(label="", kind="fiscal_year"))
    fy = [p for p in a.financials if p.kind == "fiscal_year"]
    ytd = [p for p in a.financials if p.kind == "ytd"]

    for i, p in enumerate(fy):
        _period_form(i, p, a.primary_period_label)
    for i, p in enumerate(ytd):
        _period_form(10 + i, p, a.primary_period_label)

    c1, c2 = st.columns(2)
    with c1:
        if len(fy) < 3 and st.button("＋ Add prior fiscal year"):
            a.financials.insert(len(fy), FinancialPeriod(kind="fiscal_year"))
            st.rerun()
        if not ytd and st.button("＋ Add year-to-date period"):
            a.financials.append(FinancialPeriod(kind="ytd", months=6))
            st.rerun()
    with c2:
        labels = [p.label or f"Period {i+1}" for i, p in enumerate(a.financials)]
        if labels:
            idx = labels.index(a.primary_period_label) if a.primary_period_label in labels else 0
            chosen = st.selectbox("Primary period for valuation",
                                  range(len(labels)), index=idx,
                                  format_func=lambda i: labels[i])
            a.primary_period_label = a.financials[chosen].label
            if len(fy) > 1 and st.button("Remove last fiscal year"):
                a.financials.remove(fy[-1])
                st.rerun()

    st.caption(
        "📄 Document upload & automatic extraction is **deferred** in this "
        "version — manual entry is the fully supported path. You can "
        "reference documents (e.g. '2024 tax return, Schedule C') as "
        "evidence in Adjusted Earnings."
    )
