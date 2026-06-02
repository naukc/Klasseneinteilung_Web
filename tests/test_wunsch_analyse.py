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


from backend.pruefungen.wunsch_analyse import baue_wunsch_lookup


def test_baue_wunsch_lookup_einfach():
    df = _baue_df(
        [{"vorname": "Anna", "name": "B"}, {"vorname": "Ben", "name": "C"}, {"vorname": "Carl", "name": "D"}],
        wunsch_listen=[[2, 3], [1], []],
    )
    lookup = baue_wunsch_lookup(df)
    assert lookup == {1: {2, 3}, 2: {1}, 3: set()}


def test_baue_wunsch_lookup_ignoriert_self_und_null():
    df = _baue_df(
        [{"vorname": "Anna", "name": "B"}, {"vorname": "Ben", "name": "C"}],
        wunsch_listen=[[1, 2, 0], [0]],   # Anna wünscht sich selbst (1) → ignorieren, 0 → ignorieren
    )
    lookup = baue_wunsch_lookup(df)
    assert lookup == {1: {2}, 2: set()}


def test_baue_wunsch_lookup_ignoriert_ungueltige_ids():
    df = _baue_df(
        [{"vorname": "Anna", "name": "B"}, {"vorname": "Ben", "name": "C"}],
        wunsch_listen=[[99], []],    # 99 existiert nicht
    )
    lookup = baue_wunsch_lookup(df)
    assert lookup == {1: set(), 2: set()}


from backend.pruefungen.wunsch_analyse import berechne_schueler_wunsch_details


def test_schueler_details_beidseitig_erfuellt():
    """Anna ↔ Ben, beide in Klasse 0 → beidseitig + erfüllt."""
    df = _baue_df(
        [{"vorname": "Anna", "name": "B"}, {"vorname": "Ben", "name": "C"}],
        wunsch_listen=[[2], [1]],
    )
    einteilung = [[1, 2]]
    details = berechne_schueler_wunsch_details(df, einteilung)
    assert details[1]["wuensche_gesamt"] == 1
    assert details[1]["wuensche_erfuellt"] == 1
    eintrag = details[1]["wuensche"][0]
    assert eintrag["wunsch_id"] == 2
    assert eintrag["ist_beidseitig"] is True
    assert eintrag["ist_erfuellt"] is True
    assert eintrag["wunsch_klasse"] == "A"


def test_schueler_details_einseitig_nicht_erfuellt():
    """Anna → Ben, Ben hat Anna nicht. Anna in Klasse 0, Ben in Klasse 1."""
    df = _baue_df(
        [{"vorname": "Anna", "name": "B"}, {"vorname": "Ben", "name": "C"}],
        wunsch_listen=[[2], []],
    )
    einteilung = [[1], [2]]
    details = berechne_schueler_wunsch_details(df, einteilung)
    assert details[1]["wuensche_erfuellt"] == 0
    eintrag = details[1]["wuensche"][0]
    assert eintrag["ist_beidseitig"] is False
    assert eintrag["ist_erfuellt"] is False
    assert eintrag["wunsch_klasse"] == "B"


def test_schueler_details_leer_ausgegangen_flag():
    """Schüler mit ≥1 Wunsch, aber 0 erfüllt → leer_ausgegangen=True."""
    df = _baue_df(
        [{"vorname": "Anna", "name": "B"}, {"vorname": "Ben", "name": "C"}],
        wunsch_listen=[[2], []],
    )
    einteilung = [[1], [2]]
    details = berechne_schueler_wunsch_details(df, einteilung)
    assert details[1]["leer_ausgegangen"] is True


def test_schueler_ohne_wuensche_nicht_im_dict():
    """Schüler ohne Wünsche tauchen gar nicht im Details-Dict auf (Tabelle bleibt schlank)."""
    df = _baue_df(
        [{"vorname": "Anna", "name": "B"}, {"vorname": "Ben", "name": "C"}],
        wunsch_listen=[[2], []],
    )
    einteilung = [[1, 2]]
    details = berechne_schueler_wunsch_details(df, einteilung)
    assert 1 in details
    assert 2 not in details


from backend.pruefungen.wunsch_analyse import finde_zerrissene_cluster


def test_cluster_dreier_gruppe_zerrissen():
    """A ↔ B ↔ C: drei Knoten, zwei beidseitige Paare, auf 2 Klassen verteilt."""
    df = _baue_df(
        [
            {"vorname": "A", "name": "X"},
            {"vorname": "B", "name": "X"},
            {"vorname": "C", "name": "X"},
        ],
        wunsch_listen=[[2], [1, 3], [2]],
    )
    einteilung = [[1], [2, 3]]
    cluster = finde_zerrissene_cluster(df, einteilung)
    assert len(cluster) == 1
    c = cluster[0]
    assert set(s["id"] for s in c["schueler"]) == {1, 2, 3}


def test_cluster_keine_wenn_alle_in_einer_klasse():
    """Selbe Wunsch-Beziehungen, aber alle in einer Klasse → kein Cluster."""
    df = _baue_df(
        [
            {"vorname": "A", "name": "X"},
            {"vorname": "B", "name": "X"},
            {"vorname": "C", "name": "X"},
        ],
        wunsch_listen=[[2], [1, 3], [2]],
    )
    einteilung = [[1, 2, 3]]
    assert finde_zerrissene_cluster(df, einteilung) == []


def test_cluster_zu_klein_wird_nicht_aufgenommen():
    """Nur 2 Schüler: kein Cluster (Mindestgröße 3)."""
    df = _baue_df(
        [{"vorname": "A", "name": "X"}, {"vorname": "B", "name": "X"}],
        wunsch_listen=[[2], [1]],
    )
    einteilung = [[1], [2]]
    assert finde_zerrissene_cluster(df, einteilung) == []


def test_cluster_braucht_zwei_beidseitige_paare():
    """3 Schüler, A↔B + C einseitig → nur 1 gegenseitiges Paar → kein Cluster."""
    df = _baue_df(
        [
            {"vorname": "A", "name": "X"},
            {"vorname": "B", "name": "X"},
            {"vorname": "C", "name": "X"},
        ],
        wunsch_listen=[[2], [1, 3], []],   # A↔B beidseitig, B→C einseitig
    )
    einteilung = [[1], [2], [3]]
    assert finde_zerrissene_cluster(df, einteilung) == []
