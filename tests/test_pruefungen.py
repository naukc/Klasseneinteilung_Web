"""Unit-Tests für das Schulhund-Kriterium in der Qualitätsprüfung."""

import pandas as pd

from backend.pruefungen.qualitaet import pruefe_einteilung


def _mini_df(allergien: list[str]) -> pd.DataFrame:
    n = len(allergien)
    return pd.DataFrame({
        "Vorname": [f"V{i}" for i in range(n)],
        "Name": [f"N{i}" for i in range(n)],
        "Geschlecht": ["m" if i % 2 == 0 else "w" for i in range(n)],
        "Auffaelligkeit_Score": [0] * n,
        "Migrationshintergrund / 2. Staatsangehörigkeit": ["Nein"] * n,
        "Hundehaarallergie": allergien,
    }, index=list(range(1, n + 1)))


def test_ampel_na_wenn_klasse_none():
    df = _mini_df(["nein", "nein", "ja", "ja"])
    einteilung = [[1, 2], [3, 4]]
    ergebnis = pruefe_einteilung(einteilung, df, schulhund_klasse=None)
    for kp in ergebnis.klassen:
        assert kp.schulhund_ampel == "n/a"
    assert ergebnis.schulhund_klasse_index is None


def test_ampel_na_wenn_spalte_fehlt():
    df = _mini_df(["nein", "nein", "ja", "ja"]).drop(columns=["Hundehaarallergie"])
    einteilung = [[1, 2], [3, 4]]
    ergebnis = pruefe_einteilung(einteilung, df, schulhund_klasse=0)
    for kp in ergebnis.klassen:
        assert kp.schulhund_ampel == "n/a"


def test_ampel_gruen_wenn_klasse_sauber():
    df = _mini_df(["nein", "nein", "ja", "ja"])
    einteilung = [[1, 2], [3, 4]]
    ergebnis = pruefe_einteilung(einteilung, df, schulhund_klasse=0)
    assert ergebnis.klassen[0].schulhund_ampel == "gruen"
    assert ergebnis.klassen[0].schulhund_allergiker == 0
    assert ergebnis.klassen[0].schulhund_unbekannt == 0
    assert ergebnis.klassen[0].ist_schulhund_klasse is True
    assert ergebnis.klassen[1].schulhund_ampel == "gruen"
    assert ergebnis.klassen[1].ist_schulhund_klasse is False
    assert ergebnis.schulhund_klasse_index == 0


def test_ampel_rot_wenn_allergiker_drin():
    df = _mini_df(["ja", "nein", "nein", "nein"])
    einteilung = [[1, 2], [3, 4]]
    ergebnis = pruefe_einteilung(einteilung, df, schulhund_klasse=0)
    assert ergebnis.klassen[0].schulhund_ampel == "rot"
    assert ergebnis.klassen[0].schulhund_allergiker == 1


def test_ampel_rot_wenn_unbekannt_drin():
    df = _mini_df(["", "nein", "nein", "nein"])
    einteilung = [[1, 2], [3, 4]]
    ergebnis = pruefe_einteilung(einteilung, df, schulhund_klasse=0)
    assert ergebnis.klassen[0].schulhund_ampel == "rot"
    assert ergebnis.klassen[0].schulhund_unbekannt == 1
