"""Section 7 — Price-to-Sale Explorer: illustrative relative marketability.

MANDATORY SAFEGUARDS (spec §11): no numerical probabilities of sale;
descriptive bands only; timeframe control changes guidance text only.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ...engine import marketability as mk
from ...models.assessment import SALE_TIMEFRAMES
from .. import state, theme
from ..edu import edu


def render(a, r) -> None:
    theme.header("Price-to-Sale Explorer", "Asking price vs. buyer interest")

    prim = r.valuations.get(a.valuation.primary_method)
    if not (prim and prim.runnable and prim.value_mid):
        st.warning("Complete **Valuation Results** first — this explorer works from your estimated value range.")
        return

    mid, lo, hi = prim.value_mid, prim.value_low, prim.value_high

    st.markdown(theme.badge(mk.ILLUSTRATIVE_LABEL), unsafe_allow_html=True)
    st.caption(
        "This chart shows a *conceptual* relationship between asking price "
        "and likely buyer interest. It is not a statistical prediction — "
        "no validated sale-probability data exists in this version."
    )

    state.seed("in_asking", a.asking_price if a.asking_price else mid)
    state.seed("in_timeframe", a.sale_timeframe_months)

    c1, c2 = st.columns([2, 1])
    with c1:
        slider_lo = max(1.0, lo * 0.5)
        slider_hi = hi * 1.8
        asking = st.slider(
            "Asking price ($)",
            min_value=float(slider_lo), max_value=float(slider_hi),
            step=max(1000.0, round(mid / 100, -3)),
            key="in_asking",
            format="$%d",
        )
        a.asking_price = asking
    with c2:
        st.radio("Desired sale timeframe", SALE_TIMEFRAMES, key="in_timeframe",
                 format_func=lambda m: f"{m} months", horizontal=True)
        a.sale_timeframe_months = int(state.pull("in_timeframe"))

    # Pricing presets — on_click callbacks set the slider's session value
    # BEFORE it instantiates on the rerun (assigning st.session_state for a
    # widget after instantiation raises StreamlitWidgetAlreadyInstantiatedError).
    def _apply_preset(ratio: float) -> None:
        st.session_state["in_asking"] = round(mid * ratio, 0)

    pc = st.columns(3)
    for col, (pid, p) in zip(pc, mk.PRICING_PRESETS.items()):
        with col:
            st.button(p["label"], width="stretch", help=p["note"],
                      on_click=_apply_preset, args=(p["ratio"],))

    asking = a.asking_price or mid
    pt = mk.point_for_price(asking, mid)

    c1, c2, c3 = st.columns(3)
    with c1:
        diff = asking - mid
        theme.kpi("Asking price", theme.money(asking),
                  f"{theme.money(diff)} vs midpoint ({'+' if diff>=0 else ''}{diff/mid*100:.0f}%)")
    with c2:
        theme.kpi("Estimated range", f"{theme.money(lo)} – {theme.money(hi)}",
                  "Your valuation indication")
    with c3:
        theme.kpi("Illustrative marketability", pt.band if pt else "—",
                  "Descriptive category — not a probability")

    # Curve
    pts = mk.curve(mid)
    if pts:
        df = pd.DataFrame({
            "Asking price": [p.price_ratio * mid for p in pts],
            "Index": [p.index for p in pts],
        })
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["Asking price"], y=df["Index"], mode="lines",
            line=dict(color="#C9A227", width=3), name="Illustrative index",
        ))
        fig.add_vrect(x0=lo, x1=hi, fillcolor="#3D5A80", opacity=0.25,
                      annotation_text="Estimated range", annotation_position="top left")
        fig.add_vline(x=asking, line_dash="dash", line_color="#FAFAFA",
                      annotation_text="Your ask")
        fig.update_layout(
            title=mk.ILLUSTRATIVE_LABEL,
            xaxis=dict(tickformat="$,.0f", title="Asking price"),
            yaxis=dict(title=mk.ILLUSTRATIVE_AXIS, range=[0, 1.05],
                       showticklabels=False),
            height=380, margin=dict(l=20, r=20, t=50, b=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#FAFAFA", showlegend=False,
        )
        st.plotly_chart(fig, width="stretch")

    if pt:
        st.info("🧭 " + mk.timeframe_guidance(a.sale_timeframe_months, pt.band))

    edu("Pricing a business for sale", {
        "what": "Asking price is what you advertise; selling price is what a buyer actually pays after diligence and negotiation — they're rarely the same number.",
        "why": [
            "Pricing far above the estimated range typically shrinks the buyer pool.",
            "Most buyers use financing — the price must be supportable by the business's cash flow.",
        ],
        "value": "Buyer interest depends on earnings quality, owner dependency, customer concentration, industry and local market conditions, and deal terms — not price alone.",
        "mistakes": [
            "Anchoring to what you 'need' rather than what the business supports.",
            "Ignoring transaction terms — seller financing, transition support, and what's included change what buyers will pay.",
        ],
        "next": "Discuss pricing with a broker or advisor before listing — this explorer is for education, not a pricing recommendation.",
    })
