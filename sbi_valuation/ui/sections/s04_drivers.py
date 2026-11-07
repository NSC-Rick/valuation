"""Section 4 — Business Value Drivers questionnaire."""
import streamlit as st

from ...engine.drivers import CATEGORIES
from ...models.assessment import DRIVER_ANSWER_LABELS, DRIVER_ANSWERS
from .. import state, theme
from ..edu import edu


def render(a, r) -> None:
    theme.header("Business Value Drivers", "What strengthens or weakens value")
    st.markdown(
        '<div class="sbv-section-intro">Answer honestly — "Not sure" is a '
        "valid answer and flags something worth investigating, not a black "
        "mark. These answers are your own assessment, not verified facts, "
        "and they don't change the math directly.</div>",
        unsafe_allow_html=True,
    )

    analysis = r.drivers
    st.progress(analysis.completion, text=f"{int(analysis.completion*100)}% complete")

    for ci, cat in enumerate(CATEGORIES):
        ca = next(c for c in analysis.categories if c.id == cat["id"])
        # Expand/collapse only via explicit user interaction: the `expanded`
        # argument must stay constant across reruns (Streamlit resets the
        # expander whenever it changes) and the label must be static (a
        # changing label recreates the widget and drops its open state).
        exp_key = f"in_exp_{cat['id']}"
        state.seed(exp_key, ca.answered == 0 and ci == 0)
        with st.expander(
            f"{ci+1}. {cat['name']}",
            expanded=st.session_state[exp_key],
        ):
            st.caption(
                f"{ca.answered}/{len(cat['questions'])} answered — {cat['intro']}"
            )
            for qid, text, why in cat["questions"]:
                cur = a.driver_answers.get(qid)
                key = f"in_q_{qid}"
                state.seed(key, cur)
                cols = st.columns([3, 2])
                with cols[0]:
                    st.markdown(f"**{text}**")
                    with st.popover("Why this matters"):
                        st.caption(why)
                with cols[1]:
                    choice = st.radio(
                        text, ["—"] + list(DRIVER_ANSWERS),
                        key=key, horizontal=True, label_visibility="collapsed",
                        format_func=lambda x: "Answer…" if x == "—" else DRIVER_ANSWER_LABELS[x],
                    )
                if choice and choice != "—":
                    a.driver_answers[qid] = choice
                elif qid in a.driver_answers:
                    del a.driver_answers[qid]

    st.divider()
    analysis = r.drivers  # recompute after writes
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**💪 Strengths**")
        for s in analysis.all_strengths[:8]:
            st.markdown(f"- {s}")
        if not analysis.all_strengths:
            st.caption("None identified yet.")
    with c2:
        st.markdown("**⚠️ Risks**")
        for text, why in analysis.all_risks[:8]:
            st.markdown(f"- {text}")
        if not analysis.all_risks:
            st.caption("None identified yet.")
    with c3:
        st.markdown("**❓ Information gaps**")
        for g in analysis.all_gaps[:8]:
            st.markdown(f"- {g}")
        if not analysis.all_gaps:
            st.caption("None — great coverage.")

    edu("How drivers relate to value", {
        "what": "Value drivers are the qualitative factors buyers weigh alongside earnings — owner dependency, customer stability, management depth, market position, transition risk.",
        "why": "Two businesses with identical earnings can sell for very different prices because of these factors.",
        "value": "This assessment does NOT change your multiple automatically. It shows where your business is strong or risky so you can make informed judgments — any multiple change is yours to make and document in Valuation Results.",
        "next": "Identified risks feed directly into your Action Plan in Section 8.",
    })
