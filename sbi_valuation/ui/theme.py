"""Dark-theme CSS + header bar for the valuation app."""
import streamlit as st

from ..config.branding import get_brand


def apply() -> None:
    c = get_brand()["colors"]
    st.markdown(
        f"""
        <style>
        .sbv-header {{
            background: linear-gradient(90deg, #141A24 0%, #16324F 100%);
            border: 1px solid #2A3B4F;
            border-radius: 10px;
            padding: 1.1rem 1.4rem;
            margin-bottom: 1.2rem;
            display: flex; align-items: center; gap: 14px;
        }}
        .sbv-header-title {{ font-size: 1.35rem; font-weight: 700; color: {c['text']}; }}
        .sbv-header-sub {{ font-size: 0.85rem; color: {c['muted']}; }}
        .sbv-badge {{
            display: inline-block; padding: 1px 9px; border-radius: 10px;
            font-size: 0.72rem; font-weight: 600; margin-left: 6px;
            vertical-align: middle;
        }}
        .sbv-badge-illustrative {{ background: {c['accent_soft']}; color: {c['accent_on_dark']}; }}
        .sbv-badge-supported {{ background: #1E3D2F; color: #7BD6A4; }}
        .sbv-badge-provisional {{ background: #3D3420; color: #E8C96B; }}
        .sbv-kpi {{
            background: {c['surface']}; border: 1px solid #3A3B47;
            border-radius: 10px; padding: 0.9rem 1.1rem; margin-bottom: 0.6rem;
        }}
        .sbv-kpi-label {{ font-size: 0.78rem; color: {c['muted']}; text-transform: uppercase; letter-spacing: .04em; }}
        .sbv-kpi-value {{ font-size: 1.6rem; font-weight: 700; color: {c['text']}; }}
        .sbv-kpi-note {{ font-size: 0.78rem; color: {c['muted']}; }}
        .sbv-card {{
            background: {c['surface']}; border: 1px solid #3A3B47;
            border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 0.8rem;
        }}
        .sbv-section-intro {{ color: {c['muted']}; font-size: 0.95rem; margin-bottom: 0.8rem; }}
        section[data-testid="stSidebar"] > div {{ background-color: {c['sidebar_bg']}; }}
        .sbv-logo-title {{ font-weight: 700; font-size: 1.02rem; color: {c['text']}; margin-top: 4px; }}
        .sbv-logo-sub {{ font-size: 0.75rem; color: {c['muted']}; margin-bottom: 0.6rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def header(section_title: str = "", section_sub: str = "") -> None:
    b = get_brand()
    title = section_title or b["app_name"]
    sub = section_sub or b["tagline"]
    st.markdown(
        f'<div class="sbv-header">{b["logo_svg"]}'
        f'<div><div class="sbv-header-title">{title}</div>'
        f'<div class="sbv-header-sub">{b["org_name"]} · {b["product_family"]} — {sub}</div></div></div>',
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "illustrative") -> str:
    return f'<span class="sbv-badge sbv-badge-{kind}">{text}</span>'


def kpi(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f'<div class="sbv-kpi"><div class="sbv-kpi-label">{label}</div>'
        f'<div class="sbv-kpi-value">{value}</div>'
        f'<div class="sbv-kpi-note">{note}</div></div>',
        unsafe_allow_html=True,
    )


def money(v) -> str:
    if v is None:
        return "—"
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000:
        return f"{sign}${v/1_000_000:,.2f}M"
    if v >= 10_000:
        return f"{sign}${v:,.0f}"
    return f"{sign}${v:,.2f}"
