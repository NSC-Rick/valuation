"""
SBI Business Valuation — brand configuration.

All sponsor/organization branding lives in this single file: logo art,
names, colors, report header/footer, contact details, and disclaimer
text. To rebrand (e.g. to VtSBDC, with authorization), update ``BRAND``
and ``primaryColor`` in .streamlit/config.toml — no component changes
required.
"""

_STAR_LOGO_SVG = (
    '<svg width="30" height="30" viewBox="0 0 30 30" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<path d="M15 1 L18 12 L29 15 L18 18 L15 29 L12 18 L1 15 L12 12 Z" '
    'fill="#C9A227"/>'
    '<circle cx="15" cy="15" r="2.2" fill="#F0D878"/>'
    '<circle cx="24" cy="6" r="1.1" fill="#F0D878"/>'
    '<circle cx="6" cy="24" r="1.1" fill="#F0D878"/>'
    "</svg>"
)

BRAND = {
    # ---- Sponsor / organization identity ----
    "org_name": "North Star Consulting",
    "org_subtitle": "Small Business Intelligence",
    "logo_svg": _STAR_LOGO_SVG,
    # ---- Product identity ----
    "product_family": "Small Business Intelligence (SBI)",
    "app_name": "Business Valuation",
    "app_title": "Business Valuation — North Star Consulting",
    "page_icon": "📊",
    "tagline": "Understand what your business is worth — and why.",
    # ---- Palette (dark theme; mirrors Financial Modeler structure) ----
    "colors": {
        "accent": "#C9A227",           # North Star gold
        "accent_dark": "#8F7115",
        "accent_soft": "#3A3220",      # badge bg on dark
        "accent_on_dark": "#F0D878",
        "bg": "#0E1117",               # Financial Modeler dark background
        "surface": "#262730",          # secondary background
        "text": "#FAFAFA",
        "muted": "#9AA0A6",
        "sidebar_bg": "#141A24",
        "positive": "#4CAF7D",
        "warning": "#E0A93E",
        "risk": "#E06C5B",
    },
    # ---- Report header / footer ----
    "report_header": "North Star Consulting — Small Business Intelligence",
    "report_footer": "Business Valuation | Educational assessment",
    "contact": {
        "organization": "North Star Consulting",
        "email": "",
        "phone": "",
        "website": "",
    },
    # ---- Disclosures (shown in app + embedded in every PDF report) ----
    "disclaimer": (
        "This assessment is informational and educational only. It is not "
        "a certified business appraisal, not a fairness opinion, and not "
        "tax, legal, or investment advice. It does not guarantee any "
        "transaction price or outcome. Results depend on the accuracy and "
        "completeness of information you provide and may include "
        "clearly-labeled illustrative assumptions. Marketability "
        "visualizations are educational simulations — Version 1 does not "
        "provide empirically calibrated probabilities of sale. Consult a "
        "qualified business appraiser, broker, or advisor before making "
        "transaction decisions."
    ),
}


def get_brand() -> dict:
    """Return the active brand dictionary."""
    return BRAND
