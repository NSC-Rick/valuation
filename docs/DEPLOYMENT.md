# Deployment & Operations

## Render service

The repository ships a `render.yaml` blueprint:

```yaml
services:
  - type: web
    name: sbi-business-valuation
    runtime: python
    plan: free
    envVars:
      - key: PYTHON_VERSION
        value: "3.11.9"
    buildCommand: python -m pip install --upgrade pip && python -m pip install -r requirements.txt
    startCommand: streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --server.fileWatcherType none
```

If the Render service already exists, connect it to this repository and
branch — no blueprint import needed. Verify:

1. **Build** — `pip install -r requirements.txt` succeeds.
2. **Start** — service log shows Streamlit boot; health check passes.
   Streamlit responds on `/healthz` (returns 200) and `/`.
3. **Healthy** — visit the app URL; the Business Profile section renders.

Free-plan services sleep after inactivity — first load after idle takes
~30s; that's normal, not a failure.

## Persistence trade-offs (approved V1 decision)

The app keeps **no server-side storage**. Assessments persist as
user-held `.sbva` files: passphrase-encrypted download ("Save") and
upload ("Resume"). Rationale:

- Render's filesystem is ephemeral and the free plan has no disk —
  server-side data wouldn't survive restarts anyway.
- Nothing confidential ever touches the service's disk, logs, or a
  shared store — the strongest isolation available without auth infra.

Consequences: users must keep their export files (losing one loses the
saved copy); there is no cross-device sync; advisors can't see a user's
saved assessments. If durable server-side persistence is needed later,
the smallest upgrade is a Render Disk + SQLite store (the
`storage/` module isolates this change) — the file format is already
schema-versioned for migration.

## Data security rules (enforced in code)

- Financial data never logged (no `print`/`logging` of assessment data).
- `.sbva` exports and any `data/` dir are git-ignored — nothing
  confidential is committed.
- Exported payloads are ciphertext; the envelope carries only the
  assessment label, format tag, and KDF metadata.
- Streamlit session state holds the *working copy only* — no durability
  is claimed from it.

## SBI Hub linkage

The Hub's module registry (`sbihub` repo) lists "Business Valuation &
Succession" as `coming_soon`. To link it once this service is deployed:
set the module's `status` to `"active"` and `launch_url` to this app's
public URL — it opens in a new tab with its own session, matching the
Financial Modeler pattern. That change belongs to the `sbi-hub`
repository, not this one.

## Environment

- Python 3.11.9 (`runtime.txt`, `PYTHON_VERSION` env var)
- No required secrets or environment variables for V1.
- `cryptography` is used only for export-file encryption — no keys to
  manage (keys derive from user passphrases).
