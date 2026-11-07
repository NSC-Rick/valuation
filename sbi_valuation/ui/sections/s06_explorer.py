"""Section 6 — Value Explorer: hypothetical what-if scenarios.

Scenarios are strictly sandboxed — they never write back to Financial
Snapshot, Adjusted Earnings, or Valuation Results assumptions.
"""
import pandas as pd
import streamlit as st

from ...engine.scenarios import evaluate_scenario, preset_scenarios
from ...models.assessment import Scenario
from .. import state, theme
from ..edu import edu


def _baseline(a, r):
    vi = a.valuation
    prim = r.valuations.get(vi.primary_method)
    if prim and prim.runnable and prim.method == "sde_multiple":
        return r.sde, vi.sde_multiple.mid
    if r.sde is not None and r.sde >= 0:
        return r.sde, vi.sde_multiple.mid
    return None, None


def render(a, r) -> None:
    theme.header("Value Explorer", "What-if scenarios (hypothetical)")
    st.markdown(
        '<div class="sbv-section-intro">Experiment freely — scenarios here '
        "are <strong>hypothetical</strong> and never change your official "
        "inputs or valuation.</div>",
        unsafe_allow_html=True,
    )

    base_sde, base_mult = _baseline(a, r)
    if base_sde is None or base_sde < 0:
        st.warning("A positive SDE is needed for scenarios — complete Adjusted Earnings first.")
        return
    base_value = base_sde * base_mult

    theme.kpi("Baseline (from Valuation Results)",
              theme.money(base_value),
              f"SDE {theme.money(base_sde)} × {base_mult:.2f}")

    # Presets
    c1, c2 = st.columns([3, 1])
    with c1:
        st.caption("Presets:")
        pc = st.columns(3)
        presets = preset_scenarios()
        if pc[0].button("Current Business", width="stretch"):
            s = presets[0]
            a.scenarios.append(s)
            st.rerun()
        if pc[1].button("Improve Earnings", width="stretch",
                        help="Hypothetical +20% earnings"):
            s = presets[1]
            s.earnings = round(base_sde * 1.2, 2)
            a.scenarios.append(s)
            st.rerun()
        if pc[2].button("Reduce Business Risk", width="stretch",
                        help="Hypothetical stronger driver profile → higher multiple"):
            s = presets[2]
            s.multiple = round(base_mult + 0.5, 2)
            a.scenarios.append(s)
            st.rerun()
    with c2:
        st.caption("Actions:")
        if st.button("↺ Reset to baseline", width="stretch"):
            a.scenarios.clear()
            st.rerun()

    # Existing scenarios
    rows = []
    for s in a.scenarios:
        res = evaluate_scenario(s, base_sde, base_mult)
        with st.expander(f"📊 {s.name}", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                ek = f"in_sc_e_{s.id}"
                mk = f"in_sc_m_{s.id}"
                state.seed(ek, s.earnings if s.earnings is not None else base_sde)
                state.seed(mk, s.multiple if s.multiple is not None else base_mult)
                st.number_input("Normalized earnings ($)", min_value=0.0,
                                step=5000.0, key=ek, format="%.0f")
                st.number_input("Valuation multiple (×)", min_value=0.0,
                                step=0.25, key=mk, format="%.2f")
                s.earnings = state.pull(ek)
                s.multiple = state.pull(mk)
            with c2:
                res = evaluate_scenario(s, base_sde, base_mult)
                if res:
                    delta = res.delta_abs
                    pct = f" ({res.delta_pct:+.0f}%)" if res.delta_pct is not None else ""
                    theme.kpi("Scenario value", theme.money(res.value),
                              f"{theme.money(delta)}{pct} vs baseline")
                cA, cB = st.columns(2)
                with cA:
                    nn = st.text_input("Rename", value=s.name, key=f"in_sc_n_{s.id}",
                                       label_visibility="collapsed")
                    s.name = nn or s.name
                with cB:
                    if st.button("Delete scenario", key=f"in_sc_d_{s.id}"):
                        a.scenarios = [x for x in a.scenarios if x.id != s.id]
                        st.rerun()
        if res:
            rows.append({
                "Scenario": s.name,
                "Earnings": theme.money(res.earnings),
                "Multiple": f"{res.multiple:.2f}×",
                "Value": theme.money(res.value),
                "Δ vs baseline": f"{theme.money(res.delta_abs)}"
                + (f" ({res.delta_pct:+.0f}%)" if res.delta_pct is not None else ""),
            })

    if st.button("＋ New custom scenario"):
        a.scenarios.append(Scenario(name=f"Custom scenario {len(a.scenarios)+1}"))
        st.rerun()

    if rows:
        st.divider()
        st.subheader("Scenario comparison")
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    edu("How to think about scenarios", {
        "what": "A scenario varies two levers: normalized earnings and the valuation multiple.",
        "value": [
            "Earnings improvements flow ~1:1 through the multiple — growing SDE 20% grows the estimate ~20%.",
            "Multiple changes reflect risk/desirability — a stronger driver profile CAN support a higher multiple, but improvement doesn't guarantee one.",
        ],
        "mistakes": "Assuming an operational fix automatically raises your multiple — buyers decide that. Use scenarios to explore, not to promise.",
        "next": "Connect what you learned in Business Value Drivers to earnings assumptions — e.g., what would reducing owner dependency do to earnings durability?",
    })
