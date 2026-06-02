# Wunsch-Analyse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine erweiterte „Wunsch-Analyse"-Karte im Web-UI, die pro Schüler die Wunsch-Erfüllung mit Gegenseitigkeits-Markierung zeigt, pro Klasse aggregiert, zerrissene Wunsch-Cluster aufdeckt und konkrete Tausch-Vorschläge mit Trennungs-Filter macht.

**Architecture:** Neues Backend-Modul `backend/pruefungen/wunsch_analyse.py` für die reinen Analyse-Funktionen (Gegenseitigkeit, Cluster, Tausch). `qualitaet.py` ruft diese auf und liefert die Daten via bestehendem `pruefung`-JSON aus. Frontend ersetzt die bestehende `wuenscheCard` durch eine neue Karte mit vier vertikalen Sektionen. **Kein neuer Backend-Endpunkt:** der „Tausch durchführen"-Button verwendet die existierende `/api/verschieben`-Route mit getauschter Einteilung.

**Tech Stack:** Python 3.13, pandas, pytest, FastAPI, Vanilla-JS, HTML/CSS.

**Referenz:** Spec → `docs/superpowers/specs/2026-06-02-wunsch-analyse-design.md`

---

## File Structure

**Neu erstellt:**
- `backend/pruefungen/wunsch_analyse.py` — reine Analyse-Funktionen (Gegenseitigkeit, Schüler-Details, Cluster, Tausch-Vorschläge)
- `tests/test_wunsch_analyse.py` — Unit-Tests für die neuen Funktionen

**Modifiziert:**
- `backend/pruefungen/qualitaet.py` — `KlassenPruefung`/`GesamtPruefung` um neue Felder erweitern, Aufrufe der neuen Funktionen
- `frontend/index.html` — `wuenscheCard` durch `wunschAnalyseCard` ersetzen
- `frontend/app.js` — `renderWuensche` ersetzen durch vier neue Render-Funktionen + Tausch-Handler
- `frontend/style.css` — neue Klassen für Wunsch-Chips, Cluster-Box, Tausch-Karte

---

## Task 1: Test-Scaffolding und Hilfs-Fixtures

**Files:**
- Create: `tests/test_wunsch_analyse.py`

- [ ] **Step 1: Datei mit erster Smoke-Test-Struktur anlegen**

```python
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
```

- [ ] **Step 2: Test laufen lassen — sollte grün sein**

```bash
cd /Users/dedde/Projekte/Klasseneinteilung_Web
pytest tests/test_wunsch_analyse.py -v
```

Erwartet: `test_smoke PASSED`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_wunsch_analyse.py
git commit -m "test(wunsch-analyse): Test-Scaffold + DataFrame-Helper"
```

---

## Task 2: Gegenseitigkeits-Helper `_baue_wunsch_lookup`

**Files:**
- Create: `backend/pruefungen/wunsch_analyse.py`
- Modify: `tests/test_wunsch_analyse.py`

- [ ] **Step 1: Failing Test schreiben (an `tests/test_wunsch_analyse.py` anhängen)**

```python
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
```

- [ ] **Step 2: Test laufen lassen — soll fehlschlagen mit ImportError**

```bash
pytest tests/test_wunsch_analyse.py -v
```

Erwartet: `ModuleNotFoundError: No module named 'backend.pruefungen.wunsch_analyse'`.

- [ ] **Step 3: Modul mit minimaler Implementierung erstellen**

Datei `backend/pruefungen/wunsch_analyse.py`:

```python
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
```

- [ ] **Step 4: Tests laufen lassen — alle grün**

```bash
pytest tests/test_wunsch_analyse.py -v
```

Erwartet: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/pruefungen/wunsch_analyse.py tests/test_wunsch_analyse.py
git commit -m "feat(wunsch-analyse): baue_wunsch_lookup + Tests"
```

---

## Task 3: Pro-Schüler-Wunsch-Details mit Gegenseitigkeit und Erfüllt-Status

**Files:**
- Modify: `backend/pruefungen/wunsch_analyse.py`
- Modify: `tests/test_wunsch_analyse.py`

- [ ] **Step 1: Failing Tests anhängen**

```python
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
    assert details[2]["leer_ausgegangen"] is False  # hatte gar keinen Wunsch


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
```

- [ ] **Step 2: Tests laufen lassen — sollen fehlschlagen**

```bash
pytest tests/test_wunsch_analyse.py -v
```

Erwartet: `ImportError: cannot import name 'berechne_schueler_wunsch_details'`.

- [ ] **Step 3: Implementierung anhängen an `backend/pruefungen/wunsch_analyse.py`**

```python
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
```

- [ ] **Step 4: Tests laufen lassen — alle grün**

```bash
pytest tests/test_wunsch_analyse.py -v
```

Erwartet: 8 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/pruefungen/wunsch_analyse.py tests/test_wunsch_analyse.py
git commit -m "feat(wunsch-analyse): Pro-Schüler-Details mit Gegenseitigkeit"
```

---

## Task 4: Cluster-Erkennung (Union-Find)

**Files:**
- Modify: `backend/pruefungen/wunsch_analyse.py`
- Modify: `tests/test_wunsch_analyse.py`

- [ ] **Step 1: Failing Tests anhängen**

```python
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
```

- [ ] **Step 2: Tests laufen lassen — sollen fehlschlagen**

```bash
pytest tests/test_wunsch_analyse.py -v
```

Erwartet: ImportError.

- [ ] **Step 3: Implementierung anhängen an `backend/pruefungen/wunsch_analyse.py`**

```python
def _union_find_komponenten(knoten: set[int], kanten: list[tuple[int, int]]) -> list[set[int]]:
    """Union-Find: gibt Liste der zusammenhängenden Komponenten zurück."""
    parent = {n: n for n in knoten}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # Path compression
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in kanten:
        if a in parent and b in parent:
            union(a, b)

    komponenten: dict[int, set[int]] = {}
    for n in knoten:
        root = find(n)
        komponenten.setdefault(root, set()).add(n)
    return list(komponenten.values())


def finde_zerrissene_cluster(
    df: pd.DataFrame,
    einteilung: list[list[int]],
) -> list[dict]:
    """
    Findet zusammenhängende Wunsch-Komponenten, die:
    - ≥3 Schüler enthalten
    - ≥2 gegenseitige (beidseitige) Wunsch-Paare enthalten
    - nicht alle Schüler in derselben Klasse haben

    Returns:
        Liste von {
            "schueler": [{"id", "name", "klasse"}, ...],
            "beidseitige_paare": [(id_a, id_b), ...],   # sortiert, a < b
        }
    """
    wunsch_lookup = baue_wunsch_lookup(df)
    klasse_map = _baue_schueler_klasse_map(einteilung)

    # Ungerichtete Kanten aus Wünschen (egal ob ein- oder beidseitig)
    kanten: set[tuple[int, int]] = set()
    for a, ziele in wunsch_lookup.items():
        for b in ziele:
            kanten.add(tuple(sorted((a, b))))

    knoten = {sid for sid, w in wunsch_lookup.items() if w} | {b for _, ziele in wunsch_lookup.items() for b in ziele}
    komponenten = _union_find_komponenten(knoten, list(kanten))

    cluster_liste = []
    for komp in komponenten:
        if len(komp) < 3:
            continue
        # Beidseitige Paare in dieser Komponente
        beidseitig = [
            (a, b) for (a, b) in kanten
            if a in komp and b in komp and a in wunsch_lookup.get(b, set()) and b in wunsch_lookup.get(a, set())
        ]
        if len(beidseitig) < 2:
            continue
        # Auf mehrere Klassen verteilt?
        klassen_indizes = {klasse_map[s][0] for s in komp}
        if len(klassen_indizes) < 2:
            continue

        cluster_liste.append({
            "schueler": [
                {"id": s, "name": f"{df.at[s, 'Vorname']} {df.at[s, 'Name']}", "klasse": klasse_map[s][1]}
                for s in sorted(komp)
            ],
            "beidseitige_paare": sorted(beidseitig),
        })

    return cluster_liste
```

- [ ] **Step 4: Tests laufen lassen — alle grün**

```bash
pytest tests/test_wunsch_analyse.py -v
```

Erwartet: 12 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/pruefungen/wunsch_analyse.py tests/test_wunsch_analyse.py
git commit -m "feat(wunsch-analyse): Cluster-Erkennung (Union-Find)"
```

---

## Task 5: Tausch-Vorschläge mit Trennungs-Filter

**Files:**
- Modify: `backend/pruefungen/wunsch_analyse.py`
- Modify: `tests/test_wunsch_analyse.py`

- [ ] **Step 1: Failing Tests anhängen**

```python
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
    assert len(vorschlaege) == 1
    v = vorschlaege[0]
    assert {v["a"]["id"], v["b"]["id"]} == {1, 2}
    # Score: nach Tausch ist A in Klasse 1 (wo B war), aber B ist auch nicht mehr da.
    # Bei nur 2 Schülern und Tausch landen beide alleine in der jeweils anderen Klasse.
    # → 0 erfüllt. Daher prüfen wir mit drittem Schüler:


def test_tausch_drei_schueler_konstellation():
    """
    Klasse 0: [1 (will zu 3)], Klasse 1: [2 (will zu 1), 3].
    Tausch 1↔2: Klasse 0 = [2], Klasse 1 = [1, 3].
    Nach Tausch: 1's Wunsch (3) ist erfüllt (beide in Klasse 1), 2 ist allein.
    Vorher 0 Wünsche erfüllt, nachher 1.
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
    # Tausch 1↔2 erfüllt 1's Wunsch zu 3, kostet aber 2's Wunsch zu 1
    # → Score = 1 erfüllt - 1 verloren wäre 0 → ausgeschlossen
    # Aber 2 hatte Wunsch zu 1, und vorher waren sie nicht zusammen → 2's Wunsch war vorher nicht erfüllt
    # Also: Score = 1 (1's Wunsch wird erfüllt) - 0 (kein bisheriger Wunsch verloren) = 1
    assert any(set([v["a"]["id"], v["b"]["id"]]) == {1, 2} for v in vorschlaege)


def test_tausch_filtert_trennungs_verletzungen():
    """
    4 Schüler: 1↔2 wünschen sich gegenseitig, 1 und 4 müssen getrennt sein.
    Aktuell: Klasse 0 = [1, 3], Klasse 1 = [2, 4].
    Tausch 3↔2 würde 1 und 2 zusammenbringen (= Wunsch-Gewinn),
    bringt aber 1 und 4 in Klasse 1 (Wartezeit wäre falsch — eigentlich:
    bringt 1 in Klasse 1 wo 4 schon ist) → Trennung verletzt → muss
    aus den Vorschlägen rausgefiltert werden.
    """
    df = _baue_df(
        [
            {"vorname": "A", "name": "X"},   # id=1
            {"vorname": "B", "name": "X"},   # id=2
            {"vorname": "C", "name": "X"},   # id=3
            {"vorname": "D", "name": "X"},   # id=4 (darf nicht zu 1)
        ],
        wunsch_listen=[[2], [1], [], []],
        trennen_listen=[[4], [], [], [1]],
    )
    einteilung = [[1, 3], [2, 4]]
    vorschlaege = finde_tausch_vorschlaege(df, einteilung)
    for v in vorschlaege:
        ids = {v["a"]["id"], v["b"]["id"]}
        # Tausch zwischen 3 und 2 darf nicht vorgeschlagen werden, da er 1+4 verbinden würde
        assert ids != {2, 3}, f"Trennung 1↔4 hätte rausfiltern müssen, aber: {v}"


def test_tausch_limit_top_10():
    """Bei vielen Vorschlägen werden maximal 10 zurückgegeben."""
    # Konstruiere 12 Schüler-Paare mit jeweils win-win Tausch
    daten = []
    wuensche = []
    einteilung = [[], []]
    for i in range(12):
        # Paar (2i+1, 2i+2): 2i+1 in Klasse 0, 2i+2 in Klasse 1
        daten.append({"vorname": f"A{i}", "name": "X"})
        daten.append({"vorname": f"B{i}", "name": "X"})
        wuensche.append([2 * i + 2])  # A wünscht B
        wuensche.append([2 * i + 1])  # B wünscht A
        einteilung[0].append(2 * i + 1)
        einteilung[1].append(2 * i + 2)
    df = _baue_df(daten, wunsch_listen=wuensche)
    vorschlaege = finde_tausch_vorschlaege(df, einteilung)
    assert len(vorschlaege) <= 10
```

- [ ] **Step 2: Tests laufen lassen — sollen fehlschlagen**

```bash
pytest tests/test_wunsch_analyse.py -v
```

Erwartet: ImportError.

- [ ] **Step 3: Implementierung anhängen an `backend/pruefungen/wunsch_analyse.py`**

```python
def _baue_trennungs_set(df: pd.DataFrame) -> set[tuple[int, int]]:
    """Liefert die Menge der ungeordneten Paare {a, b}, die getrennt werden müssen."""
    trenn_spalten = [c for c in df.columns if str(c).startswith("Trennen_Von")]
    paare: set[tuple[int, int]] = set()
    gueltige = set(int(x) for x in df.index)
    for sid, row in df.iterrows():
        sid_int = int(sid)
        for tc in trenn_spalten:
            wert = pd.to_numeric(row.get(tc), errors="coerce")
            if pd.notna(wert):
                tid = int(wert)
                if tid != 0 and tid != sid_int and tid in gueltige:
                    paare.add(tuple(sorted((sid_int, tid))))
    return paare


def _zaehle_erfuellte_wuensche(
    sid: int,
    eigene_klasse: set[int],
    wunsch_lookup: dict[int, set[int]],
) -> int:
    """Wie viele Wünsche von sid sind erfüllt (Wunschpartner in eigener Klasse)?"""
    return sum(1 for wid in wunsch_lookup.get(sid, set()) if wid in eigene_klasse)


def finde_tausch_vorschlaege(
    df: pd.DataFrame,
    einteilung: list[list[int]],
    limit: int = 10,
) -> list[dict]:
    """
    Findet Paar-Tausche, die unterm Strich mehr Wünsche erfüllen als sie verlieren.
    Filtert Vorschläge raus, die Trennungsregeln verletzen würden.

    Returns: Liste sortiert nach Score absteigend, maximal `limit` Einträge.
    """
    wunsch_lookup = baue_wunsch_lookup(df)
    klasse_map = _baue_schueler_klasse_map(einteilung)
    trennungs_paare = _baue_trennungs_set(df)

    klassen_sets = [set(int(s) for s in ids) for ids in einteilung]

    vorschlaege = []
    schueler_ids = sorted(klasse_map.keys())

    for i, a in enumerate(schueler_ids):
        a_klasse_idx = klasse_map[a][0]
        for b in schueler_ids[i + 1:]:
            b_klasse_idx = klasse_map[b][0]
            if a_klasse_idx == b_klasse_idx:
                continue

            klasse_a_neu = (klassen_sets[a_klasse_idx] - {a}) | {b}
            klasse_b_neu = (klassen_sets[b_klasse_idx] - {b}) | {a}

            # Trennungs-Verletzung prüfen
            verletzt = False
            for p, q in trennungs_paare:
                if (p in klasse_a_neu and q in klasse_a_neu) or (p in klasse_b_neu and q in klasse_b_neu):
                    verletzt = True
                    break
            if verletzt:
                continue

            # Score: für alle betroffenen Schüler (a, b, andere Klassenmitglieder bleiben gleich)
            # neu_erfuellt für a in seiner neuen Klasse + b in seiner neuen Klasse
            # Wichtig: andere Schüler in Klasse A und B können auch Wünsche an a/b haben, die sich ändern
            vorher = (
                _zaehle_erfuellte_wuensche(a, klassen_sets[a_klasse_idx], wunsch_lookup)
                + _zaehle_erfuellte_wuensche(b, klassen_sets[b_klasse_idx], wunsch_lookup)
                + sum(
                    _zaehle_erfuellte_wuensche(s, klassen_sets[a_klasse_idx], wunsch_lookup)
                    for s in klassen_sets[a_klasse_idx] if s != a
                )
                + sum(
                    _zaehle_erfuellte_wuensche(s, klassen_sets[b_klasse_idx], wunsch_lookup)
                    for s in klassen_sets[b_klasse_idx] if s != b
                )
            )
            nachher = (
                _zaehle_erfuellte_wuensche(a, klasse_b_neu, wunsch_lookup)
                + _zaehle_erfuellte_wuensche(b, klasse_a_neu, wunsch_lookup)
                + sum(
                    _zaehle_erfuellte_wuensche(s, klasse_a_neu, wunsch_lookup)
                    for s in klasse_a_neu if s != b
                )
                + sum(
                    _zaehle_erfuellte_wuensche(s, klasse_b_neu, wunsch_lookup)
                    for s in klasse_b_neu if s != a
                )
            )
            delta = nachher - vorher
            if delta <= 0:
                continue

            # Balance-Auswirkungen knapp angeben (informativ)
            def auff(sid: int) -> float:
                return float(pd.to_numeric(df.at[sid, "Auffaelligkeit_Score"], errors="coerce") or 0)

            def mig(sid: int) -> int:
                return 1 if df.at[sid, "Migrationshintergrund / 2. Staatsangehörigkeit"] == "Ja" else 0

            balance = {
                "geschlecht_a_klasse_diff": int(
                    (df.at[b, "Geschlecht"] == "m") - (df.at[a, "Geschlecht"] == "m")
                ),
                "auff_a_klasse_diff": round(auff(b) - auff(a), 2),
                "migration_a_klasse_diff": mig(b) - mig(a),
            }

            vorschlaege.append({
                "a": {"id": a, "name": f"{df.at[a, 'Vorname']} {df.at[a, 'Name']}", "klasse": klasse_map[a][1]},
                "b": {"id": b, "name": f"{df.at[b, 'Vorname']} {df.at[b, 'Name']}", "klasse": klasse_map[b][1]},
                "wuensche_gewinn": delta,
                "balance_hinweis": balance,
            })

    vorschlaege.sort(key=lambda v: v["wuensche_gewinn"], reverse=True)
    return vorschlaege[:limit]
```

- [ ] **Step 4: Tests laufen lassen — alle grün**

```bash
pytest tests/test_wunsch_analyse.py -v
```

Erwartet: 16 PASSED. Falls Performance-Probleme: zuerst Korrektheit, später optimieren.

- [ ] **Step 5: Commit**

```bash
git add backend/pruefungen/wunsch_analyse.py tests/test_wunsch_analyse.py
git commit -m "feat(wunsch-analyse): Tausch-Vorschläge mit Trennungs-Filter"
```

---

## Task 6: Integration in `qualitaet.py` — neue Felder im Pruefung-Output

**Files:**
- Modify: `backend/pruefungen/qualitaet.py`
- Modify: `tests/test_wunsch_analyse.py` (Integrationstest)

- [ ] **Step 1: Failing Integrationstest anhängen**

```python
from backend.pruefungen.qualitaet import pruefe_einteilung


def test_integration_pruefung_enthaelt_wunsch_analyse():
    df = _baue_df(
        [
            {"vorname": "A", "name": "X"},
            {"vorname": "B", "name": "X"},
            {"vorname": "C", "name": "X"},
        ],
        wunsch_listen=[[2], [1], []],
    )
    einteilung = [[1], [2, 3]]
    ergebnis = pruefe_einteilung(einteilung, df)

    # Pro-Schüler-Details vorhanden
    assert hasattr(ergebnis, "wunsch_details")
    assert 1 in ergebnis.wunsch_details
    assert ergebnis.wunsch_details[1]["leer_ausgegangen"] is True

    # Cluster und Tausch im Top-Level
    assert hasattr(ergebnis, "wunsch_cluster")
    assert hasattr(ergebnis, "tausch_vorschlaege")

    # Klassen-Pruefung enthält "leer_ausgegangen" und "beidseitig_zerrissen"
    klasse_a = ergebnis.klassen[0]
    assert hasattr(klasse_a, "leer_ausgegangen")
    assert hasattr(klasse_a, "beidseitig_zerrissen")
```

- [ ] **Step 2: Test laufen lassen — soll fehlschlagen mit AttributeError**

```bash
pytest tests/test_wunsch_analyse.py::test_integration_pruefung_enthaelt_wunsch_analyse -v
```

- [ ] **Step 3: `KlassenPruefung` erweitern (in `backend/pruefungen/qualitaet.py`, nach Zeile ~109 wo `nicht_erfuellte_wuensche` definiert ist)**

```python
    # Erweiterte Wunsch-Analyse
    leer_ausgegangen: int = 0
    beidseitig_zerrissen: int = 0
```

- [ ] **Step 4: `GesamtPruefung` erweitern (in `backend/pruefungen/qualitaet.py`, nach Zeile ~118)**

```python
    wunsch_details: dict = field(default_factory=dict)
    wunsch_cluster: list = field(default_factory=list)
    tausch_vorschlaege: list = field(default_factory=list)
```

- [ ] **Step 5: Aufrufe der neuen Funktionen am Ende von `pruefe_einteilung` einbauen**

Vor dem `return GesamtPruefung(...)` am Funktionsende (Datei ansehen und passende Stelle finden — direkt nachdem die `klassen_pruefungen`-Schleife durch ist und die `gesamt_ampel` berechnet wurde).

Importzeile oben in `qualitaet.py` ergänzen:

```python
from backend.pruefungen.wunsch_analyse import (
    berechne_schueler_wunsch_details,
    finde_zerrissene_cluster,
    finde_tausch_vorschlaege,
    baue_wunsch_lookup,
)
```

Dann nach der Schleife, vor `return`:

```python
    # Erweiterte Wunsch-Analyse
    wunsch_details = berechne_schueler_wunsch_details(df, einteilung)
    wunsch_cluster = finde_zerrissene_cluster(df, einteilung)
    tausch_vorschlaege = finde_tausch_vorschlaege(df, einteilung)

    # Pro-Klasse-Aggregation aktualisieren
    wunsch_lookup = baue_wunsch_lookup(df)
    klasse_map = {int(s): i for i, ids in enumerate(einteilung) for s in ids}
    for i, kp in enumerate(klassen_pruefungen):
        klasse_set = set(int(s) for s in einteilung[i])

        # leer_ausgegangen: Schüler dieser Klasse mit ≥1 Wunsch, 0 erfüllt
        kp.leer_ausgegangen = sum(
            1
            for sid in klasse_set
            if sid in wunsch_details and wunsch_details[sid]["leer_ausgegangen"]
        )

        # beidseitig_zerrissen: beidseitige Wünsche eines Schülers dieser Klasse,
        # bei denen der Partner in einer ANDEREN Klasse ist.
        # Jedes Paar einmal zählen → Filter: sid < partner_id.
        kp.beidseitig_zerrissen = sum(
            1
            for sid in klasse_set
            for partner_id in wunsch_lookup.get(sid, set())
            if (
                sid < partner_id
                and sid in wunsch_lookup.get(partner_id, set())
                and klasse_map.get(partner_id) != i
            )
        )
```

Und am Ende `wunsch_details`, `wunsch_cluster`, `tausch_vorschlaege` in den `GesamtPruefung`-Konstruktor einfügen:

```python
    return GesamtPruefung(
        klassen=klassen_pruefungen,
        gesamt_ampel=gesamt_ampel,
        zusammenfassung=zusammenfassung,
        schulhund_klasse_index=schulhund_klasse,
        wunsch_details=wunsch_details,
        wunsch_cluster=wunsch_cluster,
        tausch_vorschlaege=tausch_vorschlaege,
    )
```

- [ ] **Step 6: Alle Tests laufen lassen (auch die bestehenden)**

```bash
pytest -v
```

Erwartet: alle PASSED (inkl. die bestehenden test_pruefungen.py, test_optimierung_wrapper.py, etc.).

- [ ] **Step 7: Commit**

```bash
git add backend/pruefungen/qualitaet.py tests/test_wunsch_analyse.py
git commit -m "feat(wunsch-analyse): Integration in GesamtPruefung"
```

---

## Task 7: Manuelle Backend-Smoke-Verification

**Files:**
- Verify only: keine Code-Änderungen

- [ ] **Step 1: Dev-Server starten und Pruefung gegen Test-Datei abrufen**

```bash
cd /Users/dedde/Projekte/Klasseneinteilung_Web
source .venv/bin/activate
uvicorn backend.app:app --port 8000 &
SERVER_PID=$!
sleep 3
```

- [ ] **Step 2: Mit `test_persistence.py` testen, dass nichts kaputt ist**

```bash
python test_persistence.py
```

Erwartet: alle Schritte grün. Falls fehlschlägt → letzten Commit prüfen.

- [ ] **Step 3: Server stoppen**

```bash
kill $SERVER_PID
```

Kein Commit — reine Verifikation.

---

## Task 8: Frontend HTML — `wunschAnalyseCard` ersetzt `wuenscheCard`

**Files:**
- Modify: `frontend/index.html:177-193`

- [ ] **Step 1: Den kompletten Block ersetzen**

Ersetze in `frontend/index.html` den Block von Zeile 177 (`<!-- Nicht erfüllte Wünsche -->`) bis 193 (`</div>` der `wuenscheCard`) durch:

```html
            <!-- Wunsch-Analyse -->
            <div class="card hidden" id="wunschAnalyseCard">
                <h3>Wunsch-Analyse <span class="badge" id="wunschAnalyseBadge"></span></h3>

                <!-- Sektion 1: Aggregation pro Klasse -->
                <div class="wa-section">
                    <h4>Pro Klasse</h4>
                    <div class="table-wrapper">
                        <table class="wa-klassen-table" id="waKlassenTable">
                            <thead>
                                <tr>
                                    <th>Klasse</th>
                                    <th>SuS</th>
                                    <th>Mit Wünschen</th>
                                    <th>Leer ausgegangen</th>
                                    <th>↔ Zerrissen</th>
                                    <th>Wunsch-Quote</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                    </div>
                </div>

                <!-- Sektion 2: Pro Schüler -->
                <div class="wa-section">
                    <h4>Pro Schüler <span class="hint">(↔ beidseitig · → einseitig · ✓ erfüllt · ✗ offen)</span></h4>
                    <div class="wa-filter">
                        <label><input type="checkbox" id="waFilterLeer"> Nur leer Ausgegangene</label>
                        <label><input type="checkbox" id="waFilterBeidseitig"> Nur beidseitige offen</label>
                    </div>
                    <div class="table-wrapper">
                        <table class="wa-schueler-table" id="waSchuelerTable">
                            <thead>
                                <tr>
                                    <th>Schüler</th>
                                    <th>Klasse</th>
                                    <th>Erfüllt</th>
                                    <th>Wünsche</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                    </div>
                </div>

                <!-- Sektion 3: Zerrissene Cluster -->
                <div class="wa-section hidden" id="waClusterSection">
                    <h4>Zerrissene Wunsch-Cluster</h4>
                    <div id="waClusterList"></div>
                </div>

                <!-- Sektion 4: Tausch-Vorschläge -->
                <div class="wa-section hidden" id="waTauschSection">
                    <h4>Tausch-Vorschläge (Top 10)</h4>
                    <div id="waTauschList"></div>
                </div>
            </div>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/index.html
git commit -m "feat(ui): wunschAnalyseCard ersetzt wuenscheCard im HTML"
```

---

## Task 9: Frontend JS — DOM-Referenzen + Hauptrender umschalten

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: DOM-Referenzen aktualisieren**

In `frontend/app.js` (etwa bei Zeile 84, wo `wuenscheBadge` definiert ist) den bestehenden Block

```javascript
const wuenscheBadge = document.getElementById("wuenscheBadge");
```

ersetzen durch:

```javascript
const wunschAnalyseCard = document.getElementById("wunschAnalyseCard");
const wunschAnalyseBadge = document.getElementById("wunschAnalyseBadge");
const waKlassenTable = document.getElementById("waKlassenTable");
const waSchuelerTable = document.getElementById("waSchuelerTable");
const waClusterSection = document.getElementById("waClusterSection");
const waClusterList = document.getElementById("waClusterList");
const waTauschSection = document.getElementById("waTauschSection");
const waTauschList = document.getElementById("waTauschList");
const waFilterLeer = document.getElementById("waFilterLeer");
const waFilterBeidseitig = document.getElementById("waFilterBeidseitig");
```

Auch die alte Referenz auf `wuenscheCard` und `wuenscheTable` (falls noch verwendet) entfernen — der Linter / Browser-Konsole zeigt entfernte Verwendungen.

- [ ] **Step 2: Globalen Zustand für die Daten anlegen**

Oben in `app.js` (bei den anderen `let`-Deklarationen) hinzufügen:

```javascript
let _wunschAnalyseDaten = null;  // wird in renderPruefung gesetzt, von Renderern gelesen
```

- [ ] **Step 3: Die bestehende `renderWuensche`-Funktion ersetzen**

In `frontend/app.js` die komplette Funktion `renderWuensche(pruefung)` (etwa Zeile 897–913) ersetzen durch:

```javascript
function renderWunschAnalyse(pruefung) {
    _wunschAnalyseDaten = pruefung;
    const hatDaten = Object.keys(pruefung.wunsch_details || {}).length > 0;

    if (!hatDaten) {
        wunschAnalyseCard.classList.add("hidden");
        return;
    }
    wunschAnalyseCard.classList.remove("hidden");

    const offene = Object.values(pruefung.wunsch_details).reduce(
        (acc, d) => acc + (d.wuensche_gesamt - d.wuensche_erfuellt),
        0
    );
    wunschAnalyseBadge.textContent = offene;

    renderWaKlassen(pruefung);
    renderWaSchueler(pruefung);
    renderWaCluster(pruefung);
    renderWaTausch(pruefung);
}
```

- [ ] **Step 4: Alle Aufrufe von `renderWuensche(pruefung)` durch `renderWunschAnalyse(pruefung)` ersetzen**

```bash
grep -n "renderWuensche" /Users/dedde/Projekte/Klasseneinteilung_Web/frontend/app.js
```

Jeden Treffer mit Edit auf `renderWunschAnalyse` ändern.

- [ ] **Step 5: Commit (noch nicht testbar — fehlende Sub-Renderer)**

```bash
git add frontend/app.js
git commit -m "feat(ui): renderWunschAnalyse Haupt-Renderer + DOM-Referenzen"
```

---

## Task 10: Frontend JS — `renderWaKlassen` (Pro-Klasse-Tabelle)

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: Funktion `renderWaKlassen` hinzufügen (an passender Stelle in `app.js`, z. B. direkt nach `renderWunschAnalyse`)**

```javascript
function renderWaKlassen(pruefung) {
    const rows = pruefung.klassen.map(kp => {
        const wunschAmpelClass = `ampel-${kp.wunsch_ampel}`;
        const mitWuenschen = Object.values(pruefung.wunsch_details).filter(
            d => d.klasse === kp.klasse_name
        ).length;
        return `<tr>
            <td><strong>${kp.klasse_name}</strong></td>
            <td>${kp.anzahl_schueler}</td>
            <td>${mitWuenschen}</td>
            <td class="${kp.leer_ausgegangen > 0 ? "text-red" : ""}">${kp.leer_ausgegangen}</td>
            <td>${kp.beidseitig_zerrissen}</td>
            <td><span class="${wunschAmpelClass}">${kp.wunsch_quote_pct}%</span></td>
        </tr>`;
    }).join("");
    waKlassenTable.querySelector("tbody").innerHTML = rows;
}
```

- [ ] **Step 2: Verifizieren im Browser**

Dev-Server starten (`./run.sh`), eine Datei hochladen, optimieren, prüfen — die Pro-Klasse-Tabelle muss erscheinen. **Hard-Refresh nicht vergessen** (Cmd+Shift+R).

- [ ] **Step 3: Commit**

```bash
git add frontend/app.js
git commit -m "feat(ui): renderWaKlassen — Pro-Klasse-Aggregation"
```

---

## Task 11: Frontend JS — `renderWaSchueler` mit Filter und Sortierung

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: Funktion + Filter-Handler hinzufügen**

```javascript
function renderWaSchueler(pruefung) {
    const details = Object.entries(pruefung.wunsch_details).map(([sid, d]) => ({
        id: parseInt(sid),
        ...d,
    }));

    const filterLeer = waFilterLeer.checked;
    const filterBeid = waFilterBeidseitig.checked;

    let gefiltert = details;
    if (filterLeer) gefiltert = gefiltert.filter(d => d.leer_ausgegangen);
    if (filterBeid) gefiltert = gefiltert.filter(
        d => d.wuensche.some(w => w.ist_beidseitig && !w.ist_erfuellt)
    );

    // Sortierung: leer_ausgegangen zuerst, dann nach Anzahl unerfüllter Wünsche absteigend
    gefiltert.sort((a, b) => {
        if (a.leer_ausgegangen !== b.leer_ausgegangen) return a.leer_ausgegangen ? -1 : 1;
        const offenA = a.wuensche_gesamt - a.wuensche_erfuellt;
        const offenB = b.wuensche_gesamt - b.wuensche_erfuellt;
        if (offenA !== offenB) return offenB - offenA;
        return a.schueler_name.localeCompare(b.schueler_name);
    });

    const rows = gefiltert.map(d => {
        const chips = d.wuensche.map(w => {
            const sym = w.ist_beidseitig ? "↔" : "→";
            const check = w.ist_erfuellt ? "✓" : "✗";
            const cls = w.ist_erfuellt ? "wa-chip wa-chip-erfuellt" : "wa-chip wa-chip-offen";
            return `<span class="${cls}">${sym} ${w.wunsch_name} (${w.wunsch_klasse}) ${check}</span>`;
        }).join(" ");

        const quoteHtml = d.leer_ausgegangen
            ? `<strong class="text-red">${d.wuensche_erfuellt}/${d.wuensche_gesamt}</strong>`
            : `${d.wuensche_erfuellt}/${d.wuensche_gesamt}`;

        return `<tr>
            <td>${d.schueler_name} <span class="muted">(${d.id})</span></td>
            <td><strong>${d.klasse}</strong></td>
            <td>${quoteHtml}</td>
            <td>${chips}</td>
        </tr>`;
    }).join("");

    waSchuelerTable.querySelector("tbody").innerHTML = rows;
}

// Filter-Listener einmalig registrieren (am Init-Ende der App, z. B. nach DOMContentLoaded)
waFilterLeer.addEventListener("change", () => {
    if (_wunschAnalyseDaten) renderWaSchueler(_wunschAnalyseDaten);
});
waFilterBeidseitig.addEventListener("change", () => {
    if (_wunschAnalyseDaten) renderWaSchueler(_wunschAnalyseDaten);
});
```

- [ ] **Step 2: Browser-Verifikation**

Dev-Server, Hard-Refresh, Datei laden, optimieren. Schüler-Tabelle muss mit Symbolen erscheinen. Filter testen.

- [ ] **Step 3: Commit**

```bash
git add frontend/app.js
git commit -m "feat(ui): renderWaSchueler mit Filter + Sortierung"
```

---

## Task 12: Frontend JS — `renderWaCluster`

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: Funktion hinzufügen**

```javascript
function renderWaCluster(pruefung) {
    const cluster = pruefung.wunsch_cluster || [];
    if (cluster.length === 0) {
        waClusterSection.classList.add("hidden");
        return;
    }
    waClusterSection.classList.remove("hidden");

    waClusterList.innerHTML = cluster.map(c => {
        const schuelerHtml = c.schueler.map(
            s => `<span class="wa-cluster-schueler">${s.name} <strong>(${s.klasse})</strong></span>`
        ).join(" · ");
        const klassen = [...new Set(c.schueler.map(s => s.klasse))].sort();
        return `<div class="wa-cluster">
            <div class="wa-cluster-header">Cluster auf ${klassen.join(" / ")} verteilt — ${c.schueler.length} Schüler, ${c.beidseitige_paare.length} gegenseitige Wünsche</div>
            <div class="wa-cluster-body">${schuelerHtml}</div>
        </div>`;
    }).join("");
}
```

- [ ] **Step 2: Browser-Verifikation**

Manuell: Lade Test-Daten mit zerrissenen Cluster-Konstellationen, prüfe Anzeige.

- [ ] **Step 3: Commit**

```bash
git add frontend/app.js
git commit -m "feat(ui): renderWaCluster — zerrissene Wunsch-Cluster"
```

---

## Task 13: Frontend JS — `renderWaTausch` + Tausch-Handler

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: Funktionen anhängen**

```javascript
function renderWaTausch(pruefung) {
    const vorschlaege = pruefung.tausch_vorschlaege || [];
    if (vorschlaege.length === 0) {
        waTauschSection.classList.add("hidden");
        return;
    }
    waTauschSection.classList.remove("hidden");

    waTauschList.innerHTML = vorschlaege.map((v, idx) => {
        const fmt = (x) => (x > 0 ? "+" : "") + x;
        const b = v.balance_hinweis;
        const balanceText = `Geschl.: ${fmt(b.geschlecht_a_klasse_diff)}, Auff.: ${fmt(b.auff_a_klasse_diff)}, Mig.: ${fmt(b.migration_a_klasse_diff)}`;
        return `<div class="wa-tausch">
            <div class="wa-tausch-paar"><strong>${v.a.name}</strong> (${v.a.klasse}) ⇄ <strong>${v.b.name}</strong> (${v.b.klasse})</div>
            <div class="wa-tausch-info">+${v.wuensche_gewinn} Wunsch-Treffer · <span class="muted">${balanceText}</span></div>
            <button class="btn btn-primary wa-tausch-btn" data-a="${v.a.id}" data-b="${v.b.id}">Tausch durchführen</button>
        </div>`;
    }).join("");

    // Buttons verkabeln
    waTauschList.querySelectorAll(".wa-tausch-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            const a = parseInt(btn.dataset.a);
            const b = parseInt(btn.dataset.b);
            await fuehreTauschDurch(a, b);
        });
    });
}

async function fuehreTauschDurch(aId, bId) {
    // Aktuelle Einteilung aus dem DOM rekonstruieren und A/B in ihren Klassen tauschen
    const einteilung = bauEinteilungAusDOM();
    let klasseA = -1, klasseB = -1;
    for (let i = 0; i < einteilung.length; i++) {
        if (einteilung[i].includes(aId)) klasseA = i;
        if (einteilung[i].includes(bId)) klasseB = i;
    }
    if (klasseA === -1 || klasseB === -1 || klasseA === klasseB) {
        alert("Konnte einen der beiden Schüler nicht zuordnen.");
        return;
    }
    einteilung[klasseA] = einteilung[klasseA].filter(s => s !== aId).concat(bId);
    einteilung[klasseB] = einteilung[klasseB].filter(s => s !== bId).concat(aId);
    await sendeVerschiebung(einteilung);
}
```

- [ ] **Step 2: Browser-Verifikation**

- Tausch-Vorschläge müssen erscheinen, wenn welche existieren
- Button-Klick muss Schüler tauschen und die Karte neu rendern

- [ ] **Step 3: Commit**

```bash
git add frontend/app.js
git commit -m "feat(ui): renderWaTausch + Tausch-Button"
```

---

## Task 14: CSS — Neue Komponenten stylen

**Files:**
- Modify: `frontend/style.css`

- [ ] **Step 1: Bestehende Styles begutachten**

```bash
grep -n "card\|wuensche\|table-wrapper\|ampel" /Users/dedde/Projekte/Klasseneinteilung_Web/frontend/style.css | head -30
```

Vorhandene Patterns (Card-Layout, Tabelle, Ampel-Farben) wiederverwenden.

- [ ] **Step 2: Neue Styles ans Ende von `frontend/style.css` anhängen**

```css
/* === Wunsch-Analyse-Karte === */

.wa-section {
    margin-top: 1.5rem;
}
.wa-section:first-of-type {
    margin-top: 0;
}
.wa-section h4 {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
    color: var(--text-secondary);
}
.wa-section h4 .hint {
    font-weight: normal;
    font-size: 0.85rem;
    color: var(--text-muted);
}

.wa-filter {
    display: flex;
    gap: 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
}
.wa-filter label {
    cursor: pointer;
}

.wa-chip {
    display: inline-block;
    padding: 2px 8px;
    margin: 2px 4px 2px 0;
    border-radius: 12px;
    font-size: 0.85rem;
    white-space: nowrap;
}
.wa-chip-erfuellt {
    background: var(--ampel-gruen-bg, #d4edda);
    color: var(--ampel-gruen-text, #155724);
}
.wa-chip-offen {
    background: var(--ampel-rot-bg, #f8d7da);
    color: var(--ampel-rot-text, #721c24);
}

.wa-cluster {
    border-left: 4px solid var(--accent, #f0ad4e);
    background: var(--bg-secondary, #fff8e1);
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.5rem;
    border-radius: 4px;
}
.wa-cluster-header {
    font-weight: 600;
    margin-bottom: 0.25rem;
    font-size: 0.95rem;
}
.wa-cluster-schueler {
    display: inline-block;
    margin-right: 0.5rem;
}

.wa-tausch {
    border: 1px solid var(--border, #ddd);
    border-radius: 6px;
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.5rem 1rem;
    align-items: center;
}
.wa-tausch-paar {
    font-size: 1rem;
}
.wa-tausch-info {
    font-size: 0.9rem;
    grid-column: 1;
}
.wa-tausch-btn {
    grid-column: 2;
    grid-row: 1 / span 2;
    align-self: center;
}

.text-red {
    color: var(--ampel-rot-text, #c0392b);
}
```

- [ ] **Step 3: Browser-Verifikation**

Hard-Refresh, alles muss ansehnlich aussehen — Dark Mode auch checken (Toggle oben rechts).

- [ ] **Step 4: Commit**

```bash
git add frontend/style.css
git commit -m "feat(ui): CSS für Wunsch-Analyse-Karte"
```

---

## Task 15: End-to-End-Verification

**Files:**
- Verify only

- [ ] **Step 1: Dev-Server starten**

```bash
cd /Users/dedde/Projekte/Klasseneinteilung_Web
source .venv/bin/activate
./run.sh
```

- [ ] **Step 2: Im Browser http://localhost:8000 öffnen und durchspielen**

- Test-Excel hochladen (vorhandene Testdatei verwenden)
- Mapping bestätigen, Wünsche/Trennungen ggf. anpassen
- Optimierung starten
- **Wunsch-Analyse-Karte erscheint** unter der Qualitätsprüfung
- Sektionen sichtbar: Pro Klasse · Pro Schüler · Cluster (falls vorhanden) · Tausch (falls vorhanden)
- Filter „Nur leer Ausgegangene" funktioniert
- Filter „Nur beidseitige offen" funktioniert
- Falls Tausch-Vorschläge da sind: einen ausführen → Pruefung wird neu geladen, Karte updates sich

- [ ] **Step 3: Pytest-Suite final**

```bash
pytest -v
```

Erwartet: alle PASSED.

- [ ] **Step 4: Falls alles grün — kein zusätzlicher Commit, fertig**

---

## Done-Definition

- [x] Backend-Modul `wunsch_analyse.py` mit 4 Hauptfunktionen + Tests
- [x] `GesamtPruefung` und `KlassenPruefung` um neue Felder erweitert
- [x] Frontend-Karte mit 4 Sektionen (Pro Klasse · Pro Schüler · Cluster · Tausch)
- [x] Filter und Sortierung in der Schüler-Tabelle
- [x] Tausch-Button löst `/api/verschieben` mit getauschter Einteilung aus
- [x] Trennungs-Verletzer aus Tausch-Vorschlägen rausgefiltert
- [x] Bestehende Tests (`test_pruefungen.py` etc.) weiterhin grün
- [x] Manueller End-to-End-Durchlauf im Browser erfolgreich
