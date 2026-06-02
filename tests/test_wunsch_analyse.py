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


from backend.pruefungen.wunsch_analyse import finde_tausch_vorschlaege


def test_tausch_win_win():
    """A in Klasse 0 will zu B (Klasse 1). B will zu A. Tausch erfüllt 2 Wünsche."""
    df = _baue_df(
        [
            {"vorname": "A", "name": "X"},  # id=1, Klasse 0
            {"vorname": "B", "name": "X"},  # id=2, Klasse 1
        ],
        wunsch_listen=[[2], [1]],
    )
    einteilung = [[1], [2]]
    vorschlaege = finde_tausch_vorschlaege(df, einteilung)
    # Mit nur 2 Schülern bringt der Tausch nichts (beide wollen den anderen,
    # tauschen aber die Klassen — danach sind sie immer noch getrennt).
    # → Score = 0 → kein Vorschlag.
    assert vorschlaege == []


def test_tausch_drei_schueler_konstellation():
    """
    Klasse 0: [1], Klasse 1: [2, 3]. 1 will 3, 2 will 1.
    Tausch 1↔2: Klasse 0 = [2], Klasse 1 = [1, 3].
    Nach Tausch: 1's Wunsch (3) ist erfüllt; 2's Wunsch (1) jetzt nicht mehr nötig (war auch vorher nicht erfüllt).
    Score: 1 erfüllt - 0 verloren = 1.
    """
    df = _baue_df(
        [
            {"vorname": "A", "name": "X"},   # id=1
            {"vorname": "B", "name": "X"},   # id=2
            {"vorname": "C", "name": "X"},   # id=3
        ],
        wunsch_listen=[[3], [1], []],
    )
    einteilung = [[1], [2, 3]]
    vorschlaege = finde_tausch_vorschlaege(df, einteilung)
    assert any({v["a"]["id"], v["b"]["id"]} == {1, 2} for v in vorschlaege)


def test_tausch_filtert_trennungs_verletzungen():
    """
    4 Schüler: 1↔2 wünschen sich gegenseitig, 1 und 4 müssen getrennt sein.
    Aktuell: Klasse 0 = [1, 3], Klasse 1 = [2, 4].
    Tausch 3↔2 würde 1 und 2 zusammenbringen (Wunsch-Gewinn),
    bringt aber 1 in Klasse 1 zusammen mit 4 → Trennung verletzt → muss
    aus den Vorschlägen rausgefiltert werden.

    Hinweis: Hier wird 3↔2 getauscht, was 1 nach Klasse 1 verschiebt — NEIN,
    Tausch betrifft nur 3 und 2. Korrigieren: Tausch 3↔2 → 3 nach Klasse 1,
    2 nach Klasse 0. Dann 1 + 2 in Klasse 0 zusammen (Wunsch erfüllt!),
    3 + 4 in Klasse 1. → KEINE Trennungs-Verletzung in dieser Konfiguration.

    Wir brauchen einen Tausch, der 1 verschiebt: Tausch 1↔4.
    Vorher: K0=[1,3], K1=[2,4]. Nachher: K0=[3,4], K1=[1,2].
    1 in K1 mit 2 → Wunsch erfüllt. 1 ist NICHT mit 4 zusammen.
    Auch keine Verletzung.

    Doch eine Konfiguration finden: 1 und 4 trennen, Tausch der sie zusammenbringt:
    K0=[1,2], K1=[3,4]. Tausch 2↔4: K0=[1,4], K1=[2,3]. Trennung 1↔4 verletzt!
    """
    df = _baue_df(
        [
            {"vorname": "A", "name": "X"},   # id=1
            {"vorname": "B", "name": "X"},   # id=2
            {"vorname": "C", "name": "X"},   # id=3
            {"vorname": "D", "name": "X"},   # id=4 (darf nicht zu 1)
        ],
        wunsch_listen=[[4], [], [], [1]],   # 1↔4 wünschen sich (aber dürfen nicht)
        trennen_listen=[[4], [], [], [1]],
    )
    einteilung = [[1, 2], [3, 4]]
    # Tausch 2↔4 würde 1 und 4 zusammenbringen → Trennung verletzt → muss raus.
    vorschlaege = finde_tausch_vorschlaege(df, einteilung)
    for v in vorschlaege:
        ids = {v["a"]["id"], v["b"]["id"]}
        assert ids != {2, 4}, f"Trennung 1↔4 hätte rausfiltern müssen, aber: {v}"


def test_tausch_limit_top_10():
    """Bei vielen Vorschlägen werden maximal 10 zurückgegeben."""
    daten = []
    wuensche = []
    einteilung = [[], []]
    # Wir brauchen 3er-Konstellationen damit Tausch was bringt.
    # Pattern: Triplets — für i in 0..11:
    #   3i+1 in Klasse 0 (will 3i+3 in Klasse 1)
    #   3i+2 in Klasse 0 (Füllmaterial)
    #   3i+3 in Klasse 1 (Füllmaterial / Wunsch-Target)
    # Tausch 3i+2 ↔ 3i+3 würde 3i+1 mit 3i+3 zusammenbringen.
    for i in range(12):
        a, b, c = 3 * i + 1, 3 * i + 2, 3 * i + 3
        daten.extend([
            {"vorname": f"A{i}", "name": "X"},
            {"vorname": f"B{i}", "name": "X"},
            {"vorname": f"C{i}", "name": "X"},
        ])
        wuensche.extend([[c], [], []])
        einteilung[0].extend([a, b])
        einteilung[1].append(c)
    df = _baue_df(daten, wunsch_listen=wuensche)
    vorschlaege = finde_tausch_vorschlaege(df, einteilung)
    assert len(vorschlaege) <= 10
