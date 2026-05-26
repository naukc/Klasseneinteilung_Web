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


def erzwinge_schulhund_klasse(
    einteilung: list[list[int]],
    df: pd.DataFrame,
    schulhund_klasse: int | None,
    trennungspaare: set,
) -> tuple[list[list[int]], list[dict]]:
    """
    Tauscht Allergiker/Unbekannte aus der Schulhund-Klasse mit
    Nicht-Allergikern aus anderen Klassen.

    Args:
        einteilung: Liste von Listen mit Schüler-IDs pro Klasse.
        df: DataFrame mit Schülerdaten (mit 'Hundehaarallergie'-Spalte).
        schulhund_klasse: 0-basierter Index der Schulhund-Klasse oder None.
        trennungspaare: Set von frozensets — bei Tausch darf kein Paar
            zusammen landen.

    Returns:
        (neue_einteilung, log) — log ist eine Liste von dicts mit Feldern
        'schueler_id', 'name', 'von_klasse', 'nach_klasse', 'grund', 'status'.
        status ist 'ok' (Tausch erfolgreich) oder 'fehler' (kein Partner).
    """
    if schulhund_klasse is None:
        return einteilung, []
    if SPALTE not in df.columns:
        return einteilung, []
    if schulhund_klasse < 0 or schulhund_klasse >= len(einteilung):
        return einteilung, []

    klassen = [list(k) for k in einteilung]
    log: list[dict] = []

    def name_von(sid: int) -> str:
        if sid not in df.index:
            return str(sid)
        v = df.at[sid, "Vorname"] if "Vorname" in df.columns else ""
        n = df.at[sid, "Name"] if "Name" in df.columns else ""
        return f"{v} {n}".strip() or str(sid)

    def tausch_verletzt_trennung(sid_a: int, sid_b: int, ziel_a: int, ziel_b: int) -> bool:
        """Prüft, ob nach dem Tausch eines der Trennungspaare zusammen landet."""
        sim = [list(k) for k in klassen]
        sim[ziel_a].remove(sid_a)
        sim[ziel_b].remove(sid_b)
        sim[ziel_a].append(sid_b)
        sim[ziel_b].append(sid_a)
        for paar in trennungspaare:
            a, b = tuple(paar)
            ka = next((i for i, k in enumerate(sim) if a in k), None)
            kb = next((i for i, k in enumerate(sim) if b in k), None)
            if ka is not None and ka == kb:
                return True
        return False

    # Wiederhole, bis kein Allergiker/Unbekannter mehr in der Schulhund-Klasse ist
    while True:
        kandidaten = [
            sid for sid in klassen[schulhund_klasse]
            if not darf_in_schulhund_klasse(df.at[sid, SPALTE] if sid in df.index else "")
        ]
        if not kandidaten:
            break

        sid_raus = kandidaten[0]

        # Tausch-Partner suchen: Nicht-Allergiker in anderer Klasse, bevorzugt aus kleinster
        andere_klassen = sorted(
            (i for i in range(len(klassen)) if i != schulhund_klasse),
            key=lambda i: len(klassen[i]),
        )

        partner_gefunden = None
        partner_klasse_idx = None

        for kidx in andere_klassen:
            for sid_rein in klassen[kidx]:
                if sid_rein not in df.index:
                    continue
                if not darf_in_schulhund_klasse(df.at[sid_rein, SPALTE]):
                    continue
                if tausch_verletzt_trennung(sid_raus, sid_rein, schulhund_klasse, kidx):
                    continue
                partner_gefunden = sid_rein
                partner_klasse_idx = kidx
                break
            if partner_gefunden is not None:
                break

        if partner_gefunden is None:
            log.append({
                "schueler_id": sid_raus,
                "name": name_von(sid_raus),
                "von_klasse": schulhund_klasse + 1,
                "nach_klasse": None,
                "grund": "kein gültiger Tausch-Partner verfügbar",
                "status": "fehler",
            })
            # Diesen Allergiker überspringen — wir können nichts tun
            klassen[schulhund_klasse].remove(sid_raus)
            klassen[schulhund_klasse].append(sid_raus)  # Reihenfolge ändern, damit Loop terminiert
            # Wenn alle in der Klasse Allergiker/Unbekannte sind → fertig (sonst Endlosschleife)
            if all(not darf_in_schulhund_klasse(
                df.at[s, SPALTE] if s in df.index else ""
            ) for s in klassen[schulhund_klasse]):
                break
            continue

        # Tausch durchführen
        klassen[schulhund_klasse].remove(sid_raus)
        klassen[partner_klasse_idx].remove(partner_gefunden)
        klassen[schulhund_klasse].append(partner_gefunden)
        klassen[partner_klasse_idx].append(sid_raus)

        log.append({
            "schueler_id": sid_raus,
            "name": name_von(sid_raus),
            "von_klasse": schulhund_klasse + 1,
            "nach_klasse": partner_klasse_idx + 1,
            "grund": (
                "Hundehaarallergie" if normalisiere_allergie_wert(df.at[sid_raus, SPALTE]) == "ja"
                else "Allergie-Status unbekannt"
            ),
            "status": "ok",
        })

    return klassen, log
