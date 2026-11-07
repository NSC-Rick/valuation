"""Section 5 — Valuation Results dashboard."""
import plotly.graph_objects as go
import streamlit as st

from ...engine.valuation import reconcile_equity
from ...models.assessment import (
    MULTIPLE_KIND_LABELS,
    MULTIPLE_KINDS,
    VALUATION_METHOD_LABELS,
    VALUATION_METHODS,
)
from .. import state, theme
from ..edu import edu


def _multiple_editor(m, key_prefix: str, label: str) -> None:
    state.seed(key_prefix + "kind", m.kind)
    state.seed(key_prefix + "low", m.low)
    state.seed(key_prefix + "mid", m.mid)
    state.seed(key_prefix + "high", m.high)
    state.seed(key_prefix + "src", m.source)
    state.seed(key_prefix + "srcdate", m.source_date)

    with st.expander(f"⚙️ {label} multiple assumptions", expanded=False):
        kind = st.radio("Assumption type", MULTIPLE_KINDS, key=key_prefix + "kind",
                        format_func=lambda x: MULTIPLE_KIND_LABELS[x], horizontal=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input("Low", min_value=0.0, step=0.25, key=key_prefix + "low", format="%.2f")
        with c2:
            st.number_input("Mid", min_value=0.0, step=0.25, key=key_prefix + "mid", format="%.2f")
        with c3:
            st.number_input("High", min_value=0.0, step=0.25, key=key_prefix + "high", format="%.2f")
        if kind == "supported":
            st.text_input("Source (required for supported)", key=key_prefix + "src",
                          placeholder="e.g. Business broker opinion, published transaction data")
            st.text_input("Source date", key=key_prefix + "srcdate", placeholder="e.g. 2025-06")
        else:
            st.caption("Illustrative multiples are educational placeholders — not market benchmarks.")

        m.kind = state.pull(key_prefix + "kind")
        m.low = float(state.pull(key_prefix + "low") or 0)
        m.mid = float(state.pull(key_prefix + "mid") or 0)
        m.high = float(state.pull(key_prefix + "high") or 0)
        m.source = state.pull(key_prefix + "src") or ""
        m.source_date = state.pull(key_prefix + "srcdate") or ""


def _range_chart(lo, hi, mid, title):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[hi - lo], y=[title], base=[lo], orientation="h",
        marker_color="#3D5A80", name="Estimated range",
    ))
    fig.add_trace(go.Scatter(
        x=[mid], y=[title], mode="markers",
        marker=dict(size=16, color="#C9A227", symbol="diamond"),
        name="Illustrative midpoint",
    ))
    fig.update_layout(
        height=160, margin=dict(l=10, r=10, t=10, b=30),
        xaxis=dict(tickformat="$,.0f", title=""),
        yaxis=dict(showticklabels=False),
        showlegend=True, legend=dict(orientation="h", y=-0.4),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
    )
    return fig


def render(a, r) -> None:
    theme.header("Valuation Results", "What your business may be worth")
    vi = a.valuation

    if r.sde is None:
        st.warning("Complete **Financial Snapshot** and **Adjusted Earnings** to unlock valuation methods.")
        return

    # Method inputs
    tabs = st.tabs(["SDE multiple", "EBITDA multiple", "Net assets", "Transaction assumptions"])
    with tabs[0]:
        _multiple_editor(vi.sde_multiple, "in_msde_", "SDE")
    with tabs[1]:
        _multiple_editor(vi.ebitda_multiple, "in_mebitda_", "EBITDA")
        state.seed("in_repl_cost", vi.owner_replacement_cost)
        st.number_input(
            "Cost to hire a manager to replace you ($/yr)", min_value=0.0,
            step=5000.0, key="in_repl_cost", format="%.0f",
            help="SDE includes your compensation. A buyer who must hire a "
                 "manager keeps only what remains — this converts SDE to an "
                 "EBITDA-like basis.",
        )
        vi.owner_replacement_cost = state.pull("in_repl_cost")
        state.seed("in_ebitda_override", vi.ebitda_override)
        ov = st.number_input(
            "…or enter normalized EBITDA directly (optional)", min_value=0.0,
            step=5000.0, key="in_ebitda_override", format="%.0f",
            help="Leave at 0 to use SDE minus replacement cost.",
        )
        vi.ebitda_override = ov or None
    with tabs[2]:
        ai = vi.asset_inputs
        c1, c2 = st.columns(2)
        with c1:
            state.seed("in_as_ffe", ai.equipment_ffe)
            state.seed("in_as_inv", ai.inventory)
            state.seed("in_as_ar", ai.receivables)
            st.number_input("Equipment, furniture & fixtures (FMV $)", min_value=0.0, step=1000.0, key="in_as_ffe")
            st.number_input("Inventory (FMV $)", min_value=0.0, step=1000.0, key="in_as_inv")
            st.number_input("Accounts receivable ($)", min_value=0.0, step=1000.0, key="in_as_ar")
        with c2:
            state.seed("in_as_re", ai.real_estate)
            state.seed("in_as_oth", ai.other_assets)
            state.seed("in_as_liab", ai.liabilities_transferred)
            state.seed("in_as_incre", ai.include_real_estate)
            st.number_input("Real estate (FMV $)", min_value=0.0, step=1000.0, key="in_as_re")
            st.number_input("Other assets ($)", min_value=0.0, step=1000.0, key="in_as_oth")
            st.number_input("Liabilities a buyer would assume ($)", min_value=0.0, step=1000.0, key="in_as_liab")
            st.checkbox("Include real estate in business value", key="in_as_incre")
        ai.equipment_ffe = state.pull("in_as_ffe")
        ai.inventory = state.pull("in_as_inv")
        ai.receivables = state.pull("in_as_ar")
        ai.real_estate = state.pull("in_as_re")
        ai.other_assets = state.pull("in_as_oth")
        ai.liabilities_transferred = state.pull("in_as_liab")
        ai.include_real_estate = bool(state.pull("in_as_incre"))
    with tabs[3]:
        state.seed("in_ex_cash", vi.excess_cash)
        state.seed("in_debt", vi.debt_assumed)
        st.number_input("Excess cash included in sale ($)", min_value=0.0, step=1000.0, key="in_ex_cash")
        st.number_input("Business debt to pay off at closing ($)", min_value=0.0, step=1000.0, key="in_debt")
        st.caption(vi.transaction_note)
        vi.excess_cash = state.pull("in_ex_cash")
        vi.debt_assumed = state.pull("in_debt")

    # Recompute after input writes
    r = state.results()
    inds = r.valuations
    st.divider()

    runnable = {k: v for k, v in inds.items() if v.runnable}
    if not runnable:
        st.info("No valuation method can run yet — usually because earnings are missing or negative.")
    else:
        state.seed("in_primary_method", vi.primary_method)
        choices = list(runnable.keys())
        vi.primary_method = st.selectbox(
            "Primary method", choices,
            index=choices.index(vi.primary_method) if vi.primary_method in choices else 0,
            format_func=lambda x: VALUATION_METHOD_LABELS[x],
        )
        prim = inds[vi.primary_method]

        c1, c2, c3 = st.columns(3)
        with c1:
            theme.kpi("Estimated range",
                      f"{theme.money(prim.value_low)} – {theme.money(prim.value_high)}",
                      "Not a guaranteed selling price")
        with c2:
            ill = " (illustrative)" if prim.illustrative else ""
            theme.kpi(f"Midpoint{ill}", theme.money(prim.value_mid),
                      f"{VALUATION_METHOD_LABELS[prim.method]}")
        with c3:
            theme.kpi("Earnings basis", theme.money(prim.earnings),
                      prim.earnings_basis)

        if prim.illustrative:
            st.markdown(theme.badge("ILLUSTRATIVE ASSUMPTIONS — NOT A MARKET BENCHMARK"), unsafe_allow_html=True)
        st.plotly_chart(_range_chart(prim.value_low, prim.value_high, prim.value_mid,
                                     "Indication"), width="stretch")

        for n in prim.notes:
            st.caption(f"• {n}")

        # Equity reconciliation when the primary method is earnings-based
        if prim.method in ("sde_multiple", "ebitda_multiple") and (vi.excess_cash or vi.debt_assumed):
            eq = reconcile_equity(prim.value_mid, vi.excess_cash, vi.debt_assumed, vi.transaction_note)
            with st.expander("Enterprise → equity value bridge", expanded=True):
                st.markdown(f"Business value (mid): **{theme.money(eq.enterprise_value)}**")
                st.markdown(f"+ excess cash: {theme.money(eq.plus_cash)}")
                st.markdown(f"− debt payoff: {theme.money(eq.less_debt)}")
                st.markdown(f"**Indicative equity value: {theme.money(eq.equity_value)}**")
                st.caption(eq.note)

        # Other methods as secondary indications
        others = [v for k, v in inds.items() if k != vi.primary_method and v.runnable]
        if others:
            st.markdown("**Other indications (shown separately — never averaged):**")
            for o in others:
                st.markdown(
                    f"- {o.method_label}: {theme.money(o.value_low)} – "
                    f"{theme.money(o.value_high)}"
                    + (" *(illustrative multiple)*" if o.illustrative else "")
                )
        for o in inds.values():
            for w in o.warnings:
                st.warning(w)

    # Evidence quality
    st.divider()
    st.subheader("How reliable is this estimate?")
    ev = r.evidence
    cols = st.columns(len(ev.dimensions))
    rating_icon = {"strong": "🟢", "moderate": "🟡", "limited": "🟠", "insufficient": "🔴"}
    for col, d in zip(cols, ev.dimensions):
        with col:
            st.markdown(f"{rating_icon[d.rating]} **{d.name}**")
            st.caption(d.reasons[0] if d.reasons else "")
    with st.expander("Ways to improve estimate reliability"):
        for rec in ev.all_recommendations:
            st.markdown(f"- {rec}")

    edu("Reading this dashboard", {
        "what": "Each method produces an independent value *indication* — a range, not a point. Methods are never averaged together.",
        "why": "SDE multiple fits most owner-operated businesses; EBITDA multiple fits larger or manager-run operations; net assets fits asset-heavy or low-earnings businesses.",
        "value": "The multiple is the most sensitive assumption. Small multiple changes move value a lot — which is why supported multiples with recorded sources matter.",
        "mistakes": "Treating the midpoint as a guaranteed price — it's a reference point inside a range shaped by assumptions.",
    })
