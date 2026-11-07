"""Section 8 — Report & Action Plan."""
import streamlit as st

from ...engine.action_plan import generate_plan
from ...models.assessment import (
    ACTION_STATUS_LABELS,
    ACTION_STATUSES,
    VALUATION_METHOD_LABELS,
)
from ...report.pdf import COMPREHENSIVE_SECTIONS, REPORT_TYPES, build_report
from .. import theme
from ..edu import edu


def render(a, r) -> None:
    theme.header("Report & Action Plan", "Summary, improvement plan, and PDF reports")
    t1, t2, t3 = st.tabs(["📋 Valuation Summary", "🎯 Improvement Plan", "📄 PDF Reports"])

    with t1:
        prim = r.valuations.get(a.valuation.primary_method)
        if prim and prim.runnable:
            c1, c2 = st.columns(2)
            with c1:
                theme.kpi("Estimated range",
                          f"{theme.money(prim.value_low)} – {theme.money(prim.value_high)}")
                theme.kpi("Evidence quality", r.evidence.overall.capitalize())
            with c2:
                theme.kpi("Method", VALUATION_METHOD_LABELS[prim.method],
                          f"{prim.earnings_basis} basis"
                          + (" — illustrative" if prim.illustrative else ""))
                theme.kpi("Midpoint", theme.money(prim.value_mid),
                          "Reference point, not a guaranteed price")
        else:
            st.info("Complete earlier sections to produce a valuation summary.")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Principal strengths**")
            for s in r.drivers.all_strengths[:5] or ["None identified yet."]:
                st.markdown(f"- {s}")
        with c2:
            st.markdown("**Principal risks**")
            risk_texts = [text for text, _why in r.drivers.all_risks[:5]]
            for text in risk_texts or ["None identified yet."]:
                st.markdown(f"- {text}")
        st.markdown("**Recommended next steps**")
        for rec in r.evidence.all_recommendations[:6] or ["Complete the assessment sections."]:
            st.markdown(f"- {rec}")

    with t2:
        st.caption(
            "Generated from your assessment answers — refresh anytime; "
            "your progress tracking is preserved. Completing items improves "
            "readiness, not a guaranteed price increase."
        )
        if st.button("🔄 Generate / refresh recommendations"):
            res = generate_plan(a, r.evidence)
            a.action_items = res.items
            st.success(f"{res.generated} recommendations from your assessment"
                       + (f"; kept {res.kept_manual} manual item(s)." if res.kept_manual else "."))
            st.rerun()

        if not a.action_items:
            st.info("No recommendations yet — click generate after completing Business Value Drivers.")
        else:
            done = sum(1 for x in a.action_items if x.status == "done")
            st.progress(done / len(a.action_items),
                        text=f"{done}/{len(a.action_items)} complete")
            for it in a.action_items:
                icon = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(it.priority, "")
                with st.expander(f"{icon} {it.issue} — {it.category}", expanded=False):
                    st.markdown(f"**Why it matters:** {it.why}")
                    st.markdown(f"**Action:** {it.action}")
                    if it.timeframe:
                        st.caption(f"Suggested timeframe: {it.timeframe}")
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        new = st.selectbox(
                            "Status", ACTION_STATUSES,
                            index=ACTION_STATUSES.index(it.status),
                            key=f"in_ai_{it.id}",
                            format_func=lambda x: ACTION_STATUS_LABELS[x])
                        it.status = new
                    with c2:
                        if st.button("Remove", key=f"in_ai_del_{it.id}"):
                            a.action_items = [x for x in a.action_items if x.id != it.id]
                            st.rerun()

    with t3:
        st.caption("Reports include disclosures: educational assessment, not a certified appraisal.")
        rtype = st.radio("Report type", list(REPORT_TYPES.keys()),
                         format_func=lambda x: REPORT_TYPES[x], horizontal=True)
        chosen_sections = None
        if rtype == "comprehensive":
            chosen_sections = st.multiselect(
                "Include sections", [k for k, _ in COMPREHENSIVE_SECTIONS],
                default=[k for k, _ in COMPREHENSIVE_SECTIONS],
                format_func=lambda k: dict(COMPREHENSIVE_SECTIONS)[k])
        if st.button("Generate PDF", type="primary"):
            try:
                pdf = build_report(a, r, rtype, chosen_sections)
            except Exception as e:
                st.error(f"Report generation failed: {e}")
            else:
                fname = f"{(a.profile.business_name or 'business').strip() or 'business'}-{rtype}-report.pdf"
                st.download_button("⬇️ Download PDF", data=pdf, file_name=fname,
                                   mime="application/pdf", type="primary")

    edu("About reports", {
        "what": "Three report types: a one-page Executive Summary, a full Comprehensive Valuation Assessment, and the Improvement Plan.",
        "mistakes": "Sharing the report as proof of value — it's an educational document for planning and conversations with advisors, not an appraisal a lender or court would accept.",
        "next": "Bring the comprehensive report to a business broker, accountant, or SBDC advisor for a professional opinion.",
    })
