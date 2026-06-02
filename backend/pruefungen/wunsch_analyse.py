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
