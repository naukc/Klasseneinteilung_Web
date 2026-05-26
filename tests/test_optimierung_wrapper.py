"""Unit-Tests für Schulhund-Strafe im Optimierungs-Wrapper."""

import pandas as pd

from backend.optimierung_wrapper import _schulhund_strafe, STRAFE_SCHULHUND_VERLETZUNG


def test_keine_strafe_wenn_klasse_sauber():
    df = pd.DataFrame({
        "Hundehaarallergie": ["nein", "nein", "ja", "ja"],
    }, index=[1, 2, 3, 4])
    einteilung = [[1, 2], [3, 4]]  # Klasse 0 = Schulhund, alle nein → 0 Strafe
    assert _schulhund_strafe(einteilung, df, 0, STRAFE_SCHULHUND_VERLETZUNG) == 0.0


def test_strafe_pro_allergiker():
    df = pd.DataFrame({
        "Hundehaarallergie": ["ja", "nein", "ja", "nein"],
    }, index=[1, 2, 3, 4])
    einteilung = [[1, 3], [2, 4]]  # Klasse 0 = Schulhund, 2 Allergiker
    erwartet = 2 * STRAFE_SCHULHUND_VERLETZUNG
    assert _schulhund_strafe(einteilung, df, 0, STRAFE_SCHULHUND_VERLETZUNG) == erwartet


def test_strafe_pro_unbekannt():
    df = pd.DataFrame({
        "Hundehaarallergie": ["", "nein", "", "nein"],
    }, index=[1, 2, 3, 4])
    einteilung = [[1, 3], [2, 4]]  # Klasse 0 = Schulhund, 2 Unbekannte
    erwartet = 2 * STRAFE_SCHULHUND_VERLETZUNG
    assert _schulhund_strafe(einteilung, df, 0, STRAFE_SCHULHUND_VERLETZUNG) == erwartet


def test_keine_strafe_wenn_spalte_fehlt():
    df = pd.DataFrame({"Vorname": ["A", "B"]}, index=[1, 2])
    einteilung = [[1], [2]]
    assert _schulhund_strafe(einteilung, df, 0, STRAFE_SCHULHUND_VERLETZUNG) == 0.0


def test_keine_strafe_wenn_klasse_none():
    df = pd.DataFrame({
        "Hundehaarallergie": ["ja", "ja"],
    }, index=[1, 2])
    einteilung = [[1, 2]]
    assert _schulhund_strafe(einteilung, df, None, STRAFE_SCHULHUND_VERLETZUNG) == 0.0
