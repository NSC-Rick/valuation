"""Section 3 — Adjusted Earnings: guided SDE normalization."""
import streamlit as st

from ...models.assessment import (
    ADJUSTMENT_CATEGORY_LABELS,
    ADJUSTMENT_CATEGORIES,
    ADJUSTMENT_STATUS_LABELS,
    ADJUSTMENT_STATUSES,
    Adjustment,
)
from .. import state, theme
from ..edu import edu

_STATUS_ICON = {
    "supported": "✅",
    "proposed": "📝",
    "needs_review": "🔍",
    "rejected": "🚫",
}


def _add_adjustment_form(a, period_label: str) -> None:
    with st.expander("➕ Add an adjustment", expanded=False):
        state.seed("in_adj_cat", "interest")
        state.seed("in_adj_desc", "")
        state.seed("in_adj_amount", 0.0)
        state.seed("in_adj_expl", "")
        state.seed("in_adj_evid", "")
        st.selectbox("Adjustment type", ADJUSTMENT_CATEGORIES, key="in_adj_cat",
                     format_func=lambda x: ADJUSTMENT_CATEGORY_LABELS.get(x, x))
        st.text_input("Description", key="in_adj_desc",
                      placeholder="e.g. Business credit card interest")
        st.number_input(
            "Amount ($)", step=500.0, key="in_adj_amount", format="%.2f",
            help="Positive = add back to earnings. Negative = a cost a "
                 "buyer would have to pay (e.g. replacement labor).",
        )
        st.text_input("Why does this qualify?", key="in_adj_expl",
                      placeholder="e.g. Interest on a loan a buyer wouldn't assume")
        st.text_input("Evidence reference (optional)", key="in_adj_evid",
                      placeholder="e.g. 2024 tax return line 16; P&L 'Interest'")
        if st.button("Add to register"):
            cat = state.pull("in_adj_cat")
            amt = float(state.pull("in_adj_amount") or 0.0)
            if cat == "normalization_deduction" and amt > 0:
                amt = -amt
            a.adjustments.append(Adjustment(
                period_label=period_label,
                description=state.pull("in_adj_desc") or "",
                amount=amt,
                category=cat,
                explanation=state.pull("in_adj_expl") or "",
                evidence_ref=state.pull("in_adj_evid") or "",
                status="proposed",
            ))
            for k in ("in_adj_desc", "in_adj_amount", "in_adj_expl", "in_adj_evid"):
                del st.session_state[k]
            st.rerun()


def _register(a, norm) -> None:
    if not a.adjustments:
        return
    st.markdown("**Adjustment register**")
    verdict_by_id = {v.adjustment_id: v for v in norm.verdicts} if norm else {}
    for adj in a.adjustments:
        icon = _STATUS_ICON.get(adj.status, "")
        title = (f"{icon} {adj.description or ADJUSTMENT_CATEGORY_LABELS.get(adj.category)} "
                 f"— {theme.money(adj.amount)} · {ADJUSTMENT_STATUS_LABELS.get(adj.status)}")
        with st.expander(title, expanded=False):
            v = verdict_by_id.get(adj.id)
            if v and not v.eligible:
                st.error(v.reason)
            if adj.explanation:
                st.caption(f"Reason: {adj.explanation}")
            if adj.evidence_ref:
                st.caption(f"Evidence: {adj.evidence_ref}")
            c1, c2 = st.columns([2, 1])
            with c1:
                new_status = st.selectbox(
                    "Review status", ADJUSTMENT_STATUSES,
                    index=ADJUSTMENT_STATUSES.index(adj.status),
                    key=f"in_status_{adj.id}",
                    format_func=lambda x: ADJUSTMENT_STATUS_LABELS.get(x, x),
                )
                adj.status = new_status
            with c2:
                if st.button("Delete", key=f"in_del_{adj.id}"):
                    a.adjustments = [x for x in a.adjustments if x.id != adj.id]
                    st.rerun()


def render(a, r) -> None:
    theme.header("Adjusted Earnings", "From reported profit to SDE")
    period = a.primary_period()
    norm = r.normalization

    if period is None or period.reported_profit is None:
        st.warning("Enter your financial results in **Financial Snapshot** first.")
        edu("Why earnings get adjusted", {
            "what": "SDE (Seller's Discretionary Earnings) estimates the total financial benefit a full-time owner-operator would receive.",
        })
        return

    st.markdown(
        f'<div class="sbv-section-intro">Starting point: '
        f"<strong>{period.label or 'primary period'}</strong> — "
        f"{theme.money(period.reported_profit)} reported as "
        f"<strong>{period.profit_basis.replace('_', ' ')}</strong>.</div>",
        unsafe_allow_html=True,
    )

    if not norm.basis_established:
        st.error(
            "Your profit basis is **unknown**. Normalization can't be "
            "verified until you identify it in the Financial Snapshot — "
            "every add-back depends on knowing what was already deducted."
        )

    # Quick owner-comp add-back helper
    if period.owner_compensation:
        has_comp_adj = any(
            x.category == "owner_compensation" and x.status != "rejected"
            for x in a.adjustments
        )
        if not has_comp_adj:
            st.info(
                f"💡 You reported {theme.money(period.owner_compensation)} of "
                "owner compensation. SDE normally adds this back —",
            )
            if st.button("Add owner compensation add-back", type="primary"):
                a.adjustments.append(Adjustment(
                    period_label=period.label,
                    description="Primary working-owner compensation",
                    amount=period.owner_compensation,
                    category="owner_compensation",
                    explanation="Compensation paid to the working owner — "
                                "added back per SDE convention.",
                    status="proposed",
                ))
                st.rerun()

    _add_adjustment_form(a, period.label)
    _register(a, norm)

    st.divider()
    st.subheader("Reconciliation — reported profit to SDE")
    for line in norm.lines:
        if line.kind == "start":
            st.markdown(f"**{line.label}:** {theme.money(line.amount)}")
        elif line.kind == "subtotal":
            badge = " provisional" if "Provisional" in line.label else ""
            st.markdown(
                f"**{line.label}:** **{theme.money(line.amount)}**"
                + (theme.badge("PROVISIONAL", "provisional") if badge else ""),
                unsafe_allow_html=True,
            )
        else:
            note = f" — {line.note}" if line.note else ""
            sign = "+" if line.amount >= 0 else "−"
            st.markdown(
                f"&nbsp;&nbsp;&nbsp;{sign} {theme.money(abs(line.amount))} "
                f"{line.label}{note}"
            )

    for f in norm.flags:
        st.warning(f)

    edu("Understanding SDE", {
        "what": "SDE = reported profit + interest + taxes + depreciation + amortization + one working owner's compensation + legitimate discretionary/one-time expenses − costs a buyer must still pay.",
        "why": [
            "Small-business buyers evaluate the total owner benefit, not the accounting bottom line.",
            "Normalization makes your earnings comparable to how brokers price similar businesses.",
        ],
        "value": "SDE is the number the primary valuation method multiplies — supportable add-backs directly raise the estimate; unsupportable ones get rejected in due diligence anyway.",
        "mistakes": [
            "Adding back interest/taxes to an EBITDA figure (already excluded — double-count).",
            "Adding back draws or distributions (they're profit taken out, not expenses).",
            "Adding back every owner's pay when several owners work in the business.",
            "Forgetting replacement-labor costs a buyer would have to hire for.",
        ],
        "next": "Mark each adjustment 'Supported' once verified, then see Valuation Results.",
    })
