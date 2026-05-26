"""Unit-Tests für backend/schulhund.py."""

import pandas as pd
import pytest

from backend.schulhund import (
    normalisiere_allergie_wert,
    darf_in_schulhund_klasse,
    zaehle_allergiker_in_klasse,
)
from backend.schulhund import erzwinge_schulhund_klasse


class TestNormalisierung:
    @pytest.mark.parametrize("eingabe,erwartet", [
        ("ja", "ja"),
        ("Ja", "ja"),
        ("JA", "ja"),
        ("j", "ja"),
        ("yes", "ja"),
        ("y", "ja"),
        ("1", "ja"),
        ("true", "ja"),
        ("x", "ja"),
        ("X", "ja"),
        ("  ja  ", "ja"),
    ])
    def test_ja_varianten(self, eingabe, erwartet):
        assert normalisiere_allergie_wert(eingabe) == erwartet

    @pytest.mark.parametrize("eingabe,erwartet", [
        ("nein", "nein"),
        ("Nein", "nein"),
        ("n", "nein"),
        ("no", "nein"),
        ("0", "nein"),
        ("false", "nein"),
        ("-", "nein"),
    ])
    def test_nein_varianten(self, eingabe, erwartet):
        assert normalisiere_allergie_wert(eingabe) == erwartet

    @pytest.mark.parametrize("eingabe", [
        "",
        "   ",
        None,
        float("nan"),
        "vielleicht",
        "unbekannt",
        "k.A.",
    ])
    def test_leer_und_unbekannt(self, eingabe):
        assert normalisiere_allergie_wert(eingabe) == ""


class TestDarfInSchulhundKlasse:
    def test_nein_erlaubt(self):
        assert darf_in_schulhund_klasse("nein") is True

    def test_ja_verboten(self):
        assert darf_in_schulhund_klasse("ja") is False

    def test_leer_verboten(self):
        assert darf_in_schulhund_klasse("") is False

    def test_none_verboten(self):
        assert darf_in_schulhund_klasse(None) is False


class TestZaehleAllergiker:
    def test_ohne_spalte(self):
        df = pd.DataFrame({"Vorname": ["A", "B"]}, index=[1, 2])
        allergiker, unbekannt = zaehle_allergiker_in_klasse([1, 2], df)
        assert allergiker == 0
        assert unbekannt == 0

    def test_gemischt(self):
        df = pd.DataFrame({
            "Hundehaarallergie": ["ja", "nein", "", "ja", "nein"],
        }, index=[1, 2, 3, 4, 5])
        allergiker, unbekannt = zaehle_allergiker_in_klasse([1, 2, 3, 4, 5], df)
        assert allergiker == 2
        assert unbekannt == 1

    def test_nur_teilmenge(self):
        df = pd.DataFrame({
            "Hundehaarallergie": ["ja", "nein", "", "nein"],
        }, index=[1, 2, 3, 4])
        allergiker, unbekannt = zaehle_allergiker_in_klasse([2, 4], df)
        assert allergiker == 0
        assert unbekannt == 0


class TestErzwingeSchulhundKlasse:
    def test_keine_aenderung_wenn_klasse_sauber(self):
        df = pd.DataFrame({
            "Hundehaarallergie": ["nein", "nein", "ja", "ja"],
        }, index=[1, 2, 3, 4])
        einteilung = [[1, 2], [3, 4]]
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, set())
        assert neu == [[1, 2], [3, 4]]
        assert log == []

    def test_tauscht_allergiker_raus(self):
        df = pd.DataFrame({
            "Vorname": ["A", "B", "C", "D"],
            "Name": ["x", "x", "x", "x"],
            "Hundehaarallergie": ["ja", "nein", "nein", "nein"],
        }, index=[1, 2, 3, 4])
        einteilung = [[1, 2], [3, 4]]  # Klasse 0 (Schulhund): hat Allergiker 1
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, set())
        # Klasse 0 darf keinen Allergiker mehr haben
        klasse_0 = neu[0]
        for sid in klasse_0:
            assert df.at[sid, "Hundehaarallergie"] != "ja"
            assert df.at[sid, "Hundehaarallergie"] != ""
        # Klassengrößen erhalten
        assert sorted(len(k) for k in neu) == [2, 2]
        # Log enthält einen Tausch-Eintrag
        assert len(log) == 1
        assert log[0]["status"] == "ok"

    def test_tauscht_unbekannte_raus(self):
        df = pd.DataFrame({
            "Vorname": ["A", "B", "C", "D"],
            "Name": ["x", "x", "x", "x"],
            "Hundehaarallergie": ["", "nein", "nein", "nein"],
        }, index=[1, 2, 3, 4])
        einteilung = [[1, 2], [3, 4]]
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, set())
        for sid in neu[0]:
            assert df.at[sid, "Hundehaarallergie"] == "nein"
        assert len(log) == 1

    def test_respektiert_trennungen(self):
        df = pd.DataFrame({
            "Vorname": ["A", "B", "C", "D"],
            "Name": ["x", "x", "x", "x"],
            "Hundehaarallergie": ["ja", "nein", "nein", "nein"],
        }, index=[1, 2, 3, 4])
        einteilung = [[1, 2], [3, 4]]
        trennungspaare = {frozenset({2, 3})}
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, trennungspaare)
        for sid in neu[0]:
            assert df.at[sid, "Hundehaarallergie"] == "nein"
        # Trennung muss eingehalten bleiben
        for paar in trennungspaare:
            a, b = sorted(paar)
            klasse_a = next(i for i, k in enumerate(neu) if a in k)
            klasse_b = next(i for i, k in enumerate(neu) if b in k)
            assert klasse_a != klasse_b

    def test_fehler_wenn_kein_partner_verfuegbar(self):
        df = pd.DataFrame({
            "Vorname": ["A", "B", "C", "D"],
            "Name": ["x", "x", "x", "x"],
            "Hundehaarallergie": ["ja", "ja", "ja", "ja"],
        }, index=[1, 2, 3, 4])
        einteilung = [[1, 2], [3, 4]]
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, set())
        # Keine Tausch-Partner verfügbar → Allergiker bleiben, Log mit Fehler
        assert any(eintrag["status"] == "fehler" for eintrag in log)

    def test_keine_aenderung_wenn_klasse_none(self):
        df = pd.DataFrame({"Hundehaarallergie": ["ja"]}, index=[1])
        einteilung = [[1]]
        neu, log = erzwinge_schulhund_klasse(einteilung, df, None, set())
        assert neu == [[1]]
        assert log == []

    def test_keine_aenderung_wenn_spalte_fehlt(self):
        df = pd.DataFrame({"Vorname": ["A"]}, index=[1])
        einteilung = [[1]]
        neu, log = erzwinge_schulhund_klasse(einteilung, df, 0, set())
        assert neu == [[1]]
        assert log == []
