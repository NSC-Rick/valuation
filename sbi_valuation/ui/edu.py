"""Contextual education helpers — concise, not textbook-length."""
import streamlit as st


def edu(title: str, points: dict, expanded: bool = False) -> None:
    """Render a "Learn more" expander.

    ``points`` keys (all optional): what, why, value, mistakes, example,
    next — each a str or list[str].
    """
    icons = {
        "what": "📘 What this means",
        "why": "🎯 Why it matters",
        "value": "💰 How it affects value",
        "mistakes": "⚠️ Common mistakes",
        "example": "🔍 Example",
        "next": "➡️ Suggested next steps",
    }
    with st.expander(f"ℹ️ {title}", expanded=expanded):
        for key, heading in icons.items():
            content = points.get(key)
            if not content:
                continue
            st.markdown(f"**{heading}**")
            if isinstance(content, (list, tuple)):
                for item in content:
                    st.markdown(f"- {item}")
            else:
                st.markdown(content)
            st.markdown("")
