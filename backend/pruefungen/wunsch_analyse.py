"""
Wunsch-Analyse: Berechnet Gegenseitigkeits-Lookups, pro-Schüler-Wunsch-Details,
zerrissene Wunsch-Cluster und Tausch-Vorschläge für die Wunsch-Analyse-Karte
im Frontend.

Wird von qualitaet.pruefe_einteilung aufgerufen und liefert reine Daten
(keine UI-Logik).
"""

from __future__ import annotations

import pandas as pd


def baue_wunsch_lookup(df: pd.DataFrame) -> dict[int, set[int]]:
    """
    Liefert für jeden Schüler die Menge seiner gewünschten Schüler-IDs.

    Filtert:
    - Selbst-Wünsche (id == schueler_id)
    - 0 / NaN (= „kein Wunsch")
    - IDs, die nicht im DataFrame existieren
    """
    gueltige_ids = set(int(x) for x in df.index)
    wunsch_spalten = [c for c in df.columns if str(c).startswith("Wunsch_")]

    lookup: dict[int, set[int]] = {}
    for schueler_id, row in df.iterrows():
        sid = int(schueler_id)
        wuensche: set[int] = set()
        for wcol in wunsch_spalten:
            wert = pd.to_numeric(row.get(wcol), errors="coerce")
            if pd.notna(wert):
                wid = int(wert)
                if wid != 0 and wid != sid and wid in gueltige_ids:
                    wuensche.add(wid)
        lookup[sid] = wuensche
    return lookup


def _klassen_name(index: int) -> str:
    """0 → 'A', 1 → 'B', ..., 26 → 'AA'."""
    result = ""
    while index >= 0:
        result = chr(ord('A') + (index % 26)) + result
        index = (index // 26) - 1
    return result


def _baue_schueler_klasse_map(einteilung: list[list[int]]) -> dict[int, tuple[int, str]]:
    """Schüler-ID → (Klassen-Index, Klassenname)."""
    return {
        int(sid): (i, _klassen_name(i))
        for i, klasse_ids in enumerate(einteilung)
        for sid in klasse_ids
    }


def berechne_schueler_wunsch_details(
    df: pd.DataFrame,
    einteilung: list[list[int]],
) -> dict[int, dict]:
    """
    Liefert pro Schüler mit ≥1 Wunsch ein Dict mit den Wunsch-Details.

    Returns:
        {
            schueler_id: {
                "schueler_name": str,
                "klasse": str,
                "wuensche_gesamt": int,
                "wuensche_erfuellt": int,
                "leer_ausgegangen": bool,
                "wuensche": [
                    {
                        "wunsch_id": int,
                        "wunsch_name": str,
                        "wunsch_klasse": str,
                        "ist_beidseitig": bool,
                        "ist_erfuellt": bool,
                    },
                    ...
                ],
            },
            ...
        }
    """
    wunsch_lookup = baue_wunsch_lookup(df)
    klasse_map = _baue_schueler_klasse_map(einteilung)

    details: dict[int, dict] = {}
    for sid, wuensche in wunsch_lookup.items():
        if not wuensche:
            continue

        eigene_klasse_idx, eigene_klasse_name = klasse_map[sid]
        eintraege = []
        erfuellt_count = 0

        for wid in sorted(wuensche):
            wunsch_klasse_idx, wunsch_klasse_name = klasse_map[wid]
            ist_erfuellt = wunsch_klasse_idx == eigene_klasse_idx
            ist_beidseitig = sid in wunsch_lookup.get(wid, set())
            if ist_erfuellt:
                erfuellt_count += 1
            eintraege.append({
                "wunsch_id": wid,
                "wunsch_name": f"{df.at[wid, 'Vorname']} {df.at[wid, 'Name']}",
                "wunsch_klasse": wunsch_klasse_name,
                "ist_beidseitig": ist_beidseitig,
                "ist_erfuellt": ist_erfuellt,
            })

        details[sid] = {
            "schueler_name": f"{df.at[sid, 'Vorname']} {df.at[sid, 'Name']}",
            "klasse": eigene_klasse_name,
            "wuensche_gesamt": len(eintraege),
            "wuensche_erfuellt": erfuellt_count,
            "leer_ausgegangen": erfuellt_count == 0,
            "wuensche": eintraege,
        }

    return details
