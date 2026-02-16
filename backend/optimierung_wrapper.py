"""
Wrapper um den Optimierungsalgorithmus aus dem Submodul.

Erweitert die Bewertungsfunktion um das Laufpartner-Kriterium (Sprengel),
ohne das Submodul selbst zu verändern. Nutzt dafür Monkey-Patching:
Vor der Optimierung wird `algorithmus.bewerte_einteilung` temporär durch
eine erweiterte Version ersetzt und danach wiederhergestellt.

Unterstützt optional einen Fortschritts-Callback, der alle N Iterationen
aufgerufen wird (für Live-Fortschrittsanzeige im Frontend).
"""

from __future__ import annotations

from collections import Counter
from typing import Callable

import pandas as pd


def _sprengel_bonus(einteilung: list, df: pd.DataFrame, punkte_pro_schueler: float) -> float:
    """
    Berechnet den Sprengel-Laufpartner-Bonus.

    Für jeden Schüler, der mindestens einen anderen Schüler aus dem gleichen
    Sprengel in seiner Klasse hat, werden Bonuspunkte vergeben.

    Args:
        einteilung: Liste von Listen mit Schüler-IDs pro Klasse
        df: DataFrame mit Schülerdaten (muss Spalte 'Sprengel' enthalten)
        punkte_pro_schueler: Bonus-Punkte pro Schüler mit Laufpartner

    Returns:
        Bonus-Score (positiv)
    """
    if "Sprengel" not in df.columns:
        return 0.0

    bonus = 0.0

    for klasse_ids in einteilung:
        klassen_df = df.loc[klasse_ids]

        # Sprengel-Werte der Klasse zählen (leere/NaN ignorieren)
        sprengel_werte = (
            klassen_df["Sprengel"]
            .dropna()
            .astype(str)
            .str.strip()
        )
        sprengel_werte = sprengel_werte[sprengel_werte != ""]

        if sprengel_werte.empty:
            continue

        # Zähle wie oft jeder Sprengel in der Klasse vorkommt
        zaehler = Counter(sprengel_werte)

        # Jeder Schüler mit mind. einem Partner (Sprengel kommt >= 2x vor) bekommt Bonus
        for sprengel_val in sprengel_werte:
            if zaehler[sprengel_val] >= 2:
                bonus += punkte_pro_schueler

    return bonus


FORTSCHRITT_INTERVALL = 500


def optimiere_mit_sprengel(
    einteilung: list,
    df: pd.DataFrame,
    gesamt_stats: dict,
    anzahl_klassen: int,
    fortschritt_callback: Callable[[int, float, float], None] | None = None,
    **kwargs,
) -> tuple[list, float]:
    """
    Wrapper um `optimiere_einteilung` mit Sprengel-Laufpartner-Bewertung.

    Patcht temporär `algorithmus.bewerte_einteilung`, führt die Optimierung
    aus und stellt die Original-Funktion danach wieder her.

    Args:
        fortschritt_callback: Optional. Wird alle FORTSCHRITT_INTERVALL Iterationen
            aufgerufen mit (iteration, aktueller_score, bester_score).
    """
    import algorithmus
    from algorithmus import bewerte_einteilung as original_bewertung
    from algorithmus import optimiere_einteilung
    from config import PUNKTE_SPRENGEL_GLEICH

    hat_sprengel = "Sprengel" in df.columns and df["Sprengel"].notna().any()
    iterationen = kwargs.get("iterationen", 50000)

    # Zähler für Fortschritts-Callback (mutable Liste für Closure-Zugriff)
    zaehler = [0]
    letzter_score = [0.0]
    bester_score_tracker = [float("-inf")]

    def bewertung_mit_fortschritt(einteilung, df, gesamt_stats):
        if hat_sprengel:
            score = original_bewertung(einteilung, df, gesamt_stats)
            score += _sprengel_bonus(einteilung, df, PUNKTE_SPRENGEL_GLEICH)
        else:
            score = original_bewertung(einteilung, df, gesamt_stats)

        zaehler[0] += 1
        letzter_score[0] = score
        if score > bester_score_tracker[0]:
            bester_score_tracker[0] = score

        # Fortschritt melden (Zähler -1 wegen initialem Aufruf vor der Schleife)
        iteration = zaehler[0] - 1
        if fortschritt_callback and iteration > 0 and iteration % FORTSCHRITT_INTERVALL == 0:
            fortschritt_callback(iteration, score, bester_score_tracker[0])

        return score

    # Monkey-Patch: Bewertungsfunktion temporär ersetzen
    algorithmus.bewerte_einteilung = bewertung_mit_fortschritt
    try:
        ergebnis = optimiere_einteilung(
            einteilung, df, gesamt_stats, anzahl_klassen, **kwargs
        )
    finally:
        # Original wiederherstellen (auch bei Exceptions)
        algorithmus.bewerte_einteilung = original_bewertung

    return ergebnis
