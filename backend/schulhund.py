"""
Single Source of Truth für die Schulhund-Allergie-Logik.

- Normalisierung der Allergie-Werte aus dem Excel-Import und der UI-Eingabe.
- Helper für die Pruefung (Zählung pro Klasse).
- Score-Strafe für den Optimierungs-Wrapper.
- Hard-Rule Post-Processing (Tausch-Algorithmus).

Werte:
- "ja"   → Allergiker (darf NICHT in Schulhund-Klasse)
- "nein" → kein Allergiker (darf in Schulhund-Klasse)
- ""     → unbekannt / fehlende Angabe (darf NICHT in Schulhund-Klasse)
"""

from __future__ import annotations

import pandas as pd

SPALTE = "Hundehaarallergie"

_JA_VARIANTEN = {"ja", "j", "yes", "y", "1", "true", "x"}
_NEIN_VARIANTEN = {"nein", "n", "no", "0", "false", "-"}


def normalisiere_allergie_wert(wert) -> str:
    """Normalisiert einen Eingabewert zu 'ja', 'nein' oder ''."""
    if wert is None:
        return ""
    if isinstance(wert, float) and pd.isna(wert):
        return ""
    s = str(wert).strip().lower()
    if s == "" or s == "nan":
        return ""
    if s in _JA_VARIANTEN:
        return "ja"
    if s in _NEIN_VARIANTEN:
        return "nein"
    return ""  # Unbekannte Strings → wie "leer" behandeln


def darf_in_schulhund_klasse(wert) -> bool:
    """True genau dann, wenn der normalisierte Wert 'nein' ist."""
    return normalisiere_allergie_wert(wert) == "nein"


def zaehle_allergiker_in_klasse(
    klasse_ids: list[int], df: pd.DataFrame
) -> tuple[int, int]:
    """
    Zählt Allergiker und Unbekannte in einer Klasse.

    Returns: (anzahl_allergiker, anzahl_unbekannt)
    """
    if SPALTE not in df.columns:
        return 0, 0
    allergiker = 0
    unbekannt = 0
    for sid in klasse_ids:
        if sid not in df.index:
            continue
        wert = normalisiere_allergie_wert(df.at[sid, SPALTE])
        if wert == "ja":
            allergiker += 1
        elif wert == "":
            unbekannt += 1
    return allergiker, unbekannt
