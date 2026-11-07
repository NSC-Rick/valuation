"""
Assessment export/import (save/resume) — file format and validation.

File format (.sbva JSON download):

    {
      "format": "sbi-valuation-assessment",
      "version": 1,
      "encrypted": true,
      "label": "...",
      "saved_at": "...",
      "payload": {"salt": ..., "iterations": ..., "ciphertext": ...}   # encrypted
                | <assessment dict>                                    # plaintext
    }

Plaintext export is supported (clearly labeled in the UI) but the
encrypted path is the default and recommended one.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..models.assessment import SCHEMA_VERSION, Assessment
from .crypto import DecryptionError, decrypt, encrypt

FORMAT_ID = "sbi-valuation-assessment"


class ImportError_(ValueError):
    """Raised for malformed or unsupported import files."""


def export_assessment(assessment: Assessment, passphrase: str = "") -> bytes:
    """Serialize an assessment to downloadable bytes.

    With a passphrase the payload is Fernet-encrypted; without one the
    payload is plaintext JSON (UI warns about confidentiality).
    """
    inner = json.dumps(assessment.to_dict(), indent=1).encode("utf-8")
    if passphrase:
        envelope = {
            "format": FORMAT_ID,
            "version": SCHEMA_VERSION,
            "encrypted": True,
            "label": assessment.label or assessment.profile.business_name,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "payload": encrypt(inner, passphrase),
        }
    else:
        envelope = {
            "format": FORMAT_ID,
            "version": SCHEMA_VERSION,
            "encrypted": False,
            "label": assessment.label or assessment.profile.business_name,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "payload": json.loads(inner),
        }
    return json.dumps(envelope, indent=1).encode("utf-8")


def import_assessment(data: bytes, passphrase: str = "") -> Assessment:
    """Load an assessment from export bytes.

    Raises ImportError_ for wrong file types and DecryptionError for
    decryption failures.
    """
    try:
        envelope = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportError_(
            "This file isn't a recognizable assessment export (not valid JSON)."
        ) from exc

    if not isinstance(envelope, dict) or envelope.get("format") != FORMAT_ID:
        raise ImportError_(
            "This file doesn't look like an SBI Business Valuation "
            "assessment export."
        )
    if int(envelope.get("version", 0)) > SCHEMA_VERSION:
        raise ImportError_(
            "This export was created by a newer version of the application "
            "and can't be opened here."
        )

    payload = envelope.get("payload")
    if envelope.get("encrypted"):
        if not passphrase:
            raise DecryptionError(
                "This assessment is passphrase-protected — enter the "
                "passphrase used when it was saved."
            )
        inner = decrypt(payload, passphrase)
        try:
            payload = json.loads(inner.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ImportError_("Decrypted payload was not valid assessment data.") from exc

    if not isinstance(payload, dict):
        raise ImportError_("Export payload is malformed.")

    try:
        return Assessment.from_dict(payload)
    except TypeError as exc:
        raise ImportError_(f"Assessment data failed validation: {exc}") from exc
