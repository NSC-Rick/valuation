"""
SBI Business Valuation — Streamlit entry point.

Eight-section guided workflow (sidebar navigation):

    1. Business Profile      5. Valuation Results
    2. Financial Snapshot    6. Value Explorer
    3. Adjusted Earnings     7. Price-to-Sale Explorer
    4. Business Value        8. Report & Action Plan
       Drivers

Persistence model: no server-side storage. Save = passphrase-encrypted
download; Resume = upload + passphrase; Delete = clear the working
session. Data at rest only ever exists as files the user holds.
"""
import os

import streamlit as st

from sbi_valuation.config.branding import get_brand
from sbi_valuation.storage.crypto import DecryptionError
from sbi_valuation.storage.portfolio import (
    ImportError_,
    export_assessment,
    import_assessment,
)
from sbi_valuation.ui import nav, state, theme
from sbi_valuation.ui.sections import (
    s01_profile,
    s02_financials,
    s03_earnings,
    s04_drivers,
    s05_results,
    s06_explorer,
    s07_pricing,
    s08_report,
)

BRAND = get_brand()

st.set_page_config(
    page_title=BRAND["app_title"],
    page_icon=BRAND["page_icon"],
    layout="wide",
    initial_sidebar_state="expanded",
)

theme.apply()

RENDERERS = {
    "profile": s01_profile.render,
    "financials": s02_financials.render,
    "earnings": s03_earnings.render,
    "drivers": s04_drivers.render,
    "results": s05_results.render,
    "explorer": s06_explorer.render,
    "pricing": s07_pricing.render,
    "report": s08_report.render,
}


def _workspace() -> None:
    """Sidebar: assessment file management (encrypted export/import)."""
    a = state.get_assessment()
    st.sidebar.markdown("**Assessment**")
    name = a.profile.business_name or a.label or "Untitled assessment"
    st.sidebar.caption(f"Working on: {name}")

    with st.sidebar.expander("Save / Resume / Export", expanded=False):
        st.caption(
            "Nothing is stored on the server. **Save** downloads an "
            "encrypted file; **Resume** uploads it with your passphrase."
        )
        pw = st.text_input(
            "Workspace passphrase",
            type="password",
            key="in_passphrase",
            help="Encrypts your saved file. Required to resume later. "
                 "Leave blank to export unencrypted (not recommended for "
                 "confidential data).",
        )

        col1, col2 = st.columns(2)
        with col1:
            data = export_assessment(a, passphrase=pw or "")
            st.download_button(
                "💾 Save / Export",
                data=data,
                file_name=f"{(a.profile.business_name or 'business').strip() or 'business'}-assessment.sbva",
                mime="application/json",
                width="stretch",
            )
        with col2:
            if st.button("🗑 Delete", width="stretch"):
                state.clear_session()
                st.rerun()
        if not pw:
            st.caption("⚠️ No passphrase set — export is unencrypted.")

        st.divider()
        # Dynamic key: bumping in_upload_n recreates the uploader (file
        # uploader values can't be cleared programmatically), so each file
        # is processed exactly once.
        state.seed("in_upload_n", 0)
        uploaded = st.file_uploader(
            "Resume assessment (.sbva)",
            type=["sbva", "json"],
            key=f"in_upload_{st.session_state.in_upload_n}",
        )
        if uploaded is not None:
            st.session_state["in_upload_n"] += 1
            try:
                loaded = import_assessment(
                    uploaded.getvalue(), passphrase=pw or ""
                )
            except (DecryptionError, ImportError_) as e:
                st.session_state["in_upload_err"] = str(e)
            else:
                state.set_assessment(loaded)
                st.session_state["in_upload_ok"] = (
                    loaded.profile.business_name or "assessment"
                )
            st.rerun()
        if err := st.session_state.pop("in_upload_err", None):
            st.error(err)
        if ok := st.session_state.pop("in_upload_ok", None):
            st.success(f"Resumed: {ok}")

    col_a, col_b = st.sidebar.columns(2)
    with col_a:
        if st.button("✚ New", width="stretch", help="Start a new assessment"):
            state.new_assessment()
            st.session_state.active_section = "profile"
            st.rerun()


def main() -> None:
    a = state.get_assessment()
    r = state.results()

    _workspace()
    st.sidebar.divider()
    active = nav.render_sidebar(a, r)

    with st.sidebar.expander("About & disclosures", expanded=False):
        st.caption(BRAND["disclaimer"])
        commit = os.environ.get("RENDER_GIT_COMMIT", "")[:7]
        branch = os.environ.get("RENDER_GIT_BRANCH", "")
        build = f"{commit} ({branch})" if commit else "local development"
        st.caption(f"Build: `{build}`")

    RENDERERS.get(active, s01_profile.render)(a, r)


if __name__ == "__main__":
    main()
