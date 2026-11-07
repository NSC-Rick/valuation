# SBI Business Valuation

*Understand what your business is worth — and why.*

An educational, self-service business valuation application for the
**North Star Consulting — Small Business Intelligence (SBI)** platform.
It guides owner-operated small businesses (generally under $5M revenue)
through an eight-section workflow: profile → financials → earnings
normalization (SDE) → value drivers → valuation → what-if exploration →
pricing/marketability → reports & action plan.

> **Educational tool — not a certified appraisal.** Estimates may use
> clearly-labeled illustrative assumptions. Marketability charts are
> educational simulations with no calibrated sale probabilities in V1.

## Quick start

```bash
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Run tests:

```bash
pytest
```

## Architecture

```
app.py                        # Streamlit entry: page config, sidebar, router
sbi_valuation/
├── config/branding.py        # ALL branding (org, colors, logos, disclaimers)
├── models/assessment.py      # Pure-python data model (schema v1)
├── engine/                   # Calculation engine — NO Streamlit imports
│   ├── normalization.py      # reported profit -> SDE reconciliation
│   ├── valuation.py          # SDE / EBITDA multiples, adjusted net assets
│   ├── drivers.py            # 24-question value-driver analysis
│   ├── evidence.py           # evidence-quality assessment (not a CI)
│   ├── scenarios.py          # Value Explorer scenario math
│   ├── marketability.py      # illustrative relative-marketability index
│   └── action_plan.py        # prioritized improvement recommendations
├── storage/
│   ├── crypto.py             # PBKDF2 -> Fernet passphrase encryption
│   └── portfolio.py          # .sbva export/import file format
├── report/pdf.py             # 3 PDF report types (reportlab)
└── ui/                       # theme, nav, state glue, education helper
    └── sections/s01..s08     # one module per sidebar section
tests/                        # 60+ engine/storage/report/integration tests
.streamlit/config.toml        # dark theme (FM-aligned, North Star gold accent)
render.yaml                   # Render service definition
```

The engine is fully importable and testable without Streamlit; the UI is
a thin presentation layer.

## Persistence & security model (V1)

**No server-side storage — by design.** Save = passphrase-encrypted
download (`.sbva`, Fernet AES + PBKDF2-HMAC-SHA256 480k iters); Resume =
upload + passphrase; Delete = clear the session. Confidential data at
rest only ever exists as files the user holds. This satisfies the
security requirements with zero infrastructure and cannot leak between
users. Trade-off: files are user-managed (losable, not centralized) —
documented and approved for V1.

## Financial methodology

- **SDE** is primary for owner-operated businesses: reported profit +
  interest + taxes + D&A + ONE working owner's compensation + supported
  discretionary/nonrecurring add-backs − required buyer costs.
- Add-back eligibility is enforced by declared profit basis (net income
  / operating income / EBITDA) — adding back what was never deducted is
  blocked as double-counting.
- **EBITDA method** applies to a derived buyer-EBITDA (SDE − owner
  replacement cost) or an explicitly entered figure — never to SDE.
- **Adjusted net asset method** for asset-intensive or low-earnings cases.
- Methods are never averaged. Multiples carry provenance: *illustrative*
  (default, clearly labeled — not market data) or *supported* (source +
  date recorded by the user).
- Price-to-Sale Explorer emits descriptive bands only
  ("higher/moderate/lower relative marketability"), labeled
  **Illustrative Relative Marketability — Educational Simulation**.

## Deployment

Render blueprint in `render.yaml` (single web service,
`streamlit run app.py`). See **docs/DEPLOYMENT.md** for service setup,
Hub linkage, and the persistence trade-offs.

## Rebranding

Edit `sbi_valuation/config/branding.py` (and `primaryColor` in
`.streamlit/config.toml`) — components read the config at render time.
Do not use VtSBDC marks without authorization.
