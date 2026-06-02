"""Unit-Tests für die Wunsch-Analyse-Funktionen."""

import pandas as pd
import pytest


def _baue_df(daten: list[dict], wunsch_listen: list[list[int]] | None = None, trennen_listen: list[list[int]] | None = None) -> pd.DataFrame:
    """
    Baut einen Test-DataFrame mit Schüler-IDs als Index.
    daten: [{vorname, name, geschlecht}, ...] in Reihenfolge der IDs
    wunsch_listen: Liste pro Schüler: [[id1, id2], ...] → wird zu Wunsch_1, Wunsch_2, ...
    trennen_listen: Liste pro Schüler: [[id1], ...] → wird zu Trennen_Von_1, Trennen_Von_2, ...
    """
    n = len(daten)
    df = pd.DataFrame({
        "Vorname": [d["vorname"] for d in daten],
        "Name": [d["name"] for d in daten],
        "Geschlecht": [d.get("geschlecht", "m") for d in daten],
        "Auffaelligkeit_Score": [d.get("auff", 0) for d in daten],
        "Migrationshintergrund / 2. Staatsangehörigkeit": [d.get("migration", "Nein") for d in daten],
    }, index=list(range(1, n + 1)))

    if wunsch_listen:
        max_w = max(len(w) for w in wunsch_listen) if wunsch_listen else 0
        for i in range(max_w):
            df[f"Wunsch_{i+1}"] = [w[i] if i < len(w) else 0 for w in wunsch_listen]

    if trennen_listen:
        max_t = max(len(t) for t in trennen_listen) if trennen_listen else 0
        for i in range(max_t):
            df[f"Trennen_Von_{i+1}"] = [t[i] if i < len(t) else 0 for t in trennen_listen]

    return df


def test_smoke():
    """Smoke-Test: Test-Helper produziert validen DataFrame."""
    df = _baue_df(
        [{"vorname": "Anna", "name": "B"}, {"vorname": "Ben", "name": "C"}],
        wunsch_listen=[[2], [1]],
    )
    assert len(df) == 2
    assert df.loc[1, "Wunsch_1"] == 2
    assert df.loc[2, "Wunsch_1"] == 1
