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

    def auff(sid: int) -> float:
        return float(pd.to_numeric(df.at[sid, "Auffaelligkeit_Score"], errors="coerce") or 0)

    def mig(sid: int) -> int:
        return 1 if df.at[sid, "Migrationshintergrund / 2. Staatsangehörigkeit"] == "Ja" else 0

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
