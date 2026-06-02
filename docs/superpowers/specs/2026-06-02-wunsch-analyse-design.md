# Wunsch-Analyse: Erweiterte Übersicht über Wunsch-Erfüllung

**Datum:** 2026-06-02
**Status:** Design approved, ready for plan

## Ziel

Die aktuelle „Unerfüllte Wünsche"-Karte (`renderWuensche` in `frontend/app.js:897`) zeigt eine flache Tabelle „Wer wollte zu wem, ist es aber nicht?". Das reicht nicht:

- Ein Kind mit drei unerfüllten Wünschen erscheint dreimal — schwer zu sehen, **wer komplett leer ausgegangen ist**.
- Es ist nicht ersichtlich, ob ein nicht erfüllter Wunsch **gegenseitig** war (beide Kinder wollten zusammen) oder **einseitig** (nur eines wollte das andere). Beidseitige zerrissene Wünsche sind pädagogisch deutlich schwerwiegender.
- Es gibt keine **konkreten Handlungsvorschläge** für manuelle Nachjustierungen.

Use-Case-Mix: Manuelles Nachjustieren (Drag&Drop nach Optimierung) + Qualitäts-Dokumentation für später.

## Position im UI

Neue Karte „Wunsch-Analyse" **unter der Qualitätsprüfungs-Karte**. Ersetzt die bestehende `wuenscheCard` vollständig.

## Layout-Approach

Eine einzige Karte mit vier Sektionen vertikal untereinander (keine Tabs). Begründung: Doku-Export braucht alles auf einen Blick, und Tabs verstecken Inhalt vor dem Druck.

## Sektionen

### 1. Aggregation pro Klasse (oben)

Übersichts-Tabelle, eine Zeile pro Klasse:

| Klasse | SuS gesamt | Mit Wünschen | Leer ausgegangen | ↔ Zerrissen | Wunsch-Quote |
|---|---|---|---|---|---|

- **Leer ausgegangen** = Anzahl SuS mit ≥1 Wunsch, von denen *keiner* erfüllt wurde
- **↔ Zerrissen** = Anzahl beidseitiger Wünsche, die nicht erfüllt wurden (jedes Paar einmal gezählt, nicht doppelt)
- **Wunsch-Quote** = erfüllte / gesamte Wünsche dieser Klasse, in % (analog zur bestehenden `wunsch_quote_pct`)

### 2. Pro-Schüler-Tabelle (Hauptbereich)

Eine Zeile pro Schüler **mit ≥1 Wunsch**. Spalten:

| Schüler | Klasse | Erfüllt | Wünsche |
|---|---|---|---|

In der Spalte „Wünsche" wird jeder Wunsch als kleines Element mit Symbol angezeigt:
- `↔` = beidseitig (der Wunschpartner hatte mich auch auf seiner Liste)
- `→` = einseitig (ich wollte ihn, er hatte mich nicht in seinen Wünschen)
- `✓` = erfüllt (Wunschpartner in derselben Klasse)
- `✗` = nicht erfüllt

Format pro Wunsch: `↔ Lukas K. (1b) ✗`

**Sortierung (Default):** Schüler mit 0 erfüllten Wünschen zuerst, dann nach Anzahl unerfüllter Wünsche absteigend.

**Filter (optional):**
- „Nur leer ausgegangen" — zeigt nur Schüler mit 0/n Wünschen erfüllt
- „Nur beidseitige nicht erfüllt" — zeigt nur Schüler mit mindestens einem ↔✗

### 3. Zerrissene Wunsch-Cluster

Liste der „zerrissenen Cliquen". Definition eines Clusters:

- Bilde ungerichteten Graphen aus allen Wünschen (Kante zwischen A und B, wenn A→B *oder* B→A existiert)
- Finde zusammenhängende Komponenten
- Filtere: nur Komponenten mit **≥3 Knoten**, **mindestens 2 Schülerpaaren mit beidseitigem Wunsch** (A↔B und C↔D, also zwei distinkte gegenseitige Beziehungen innerhalb der Komponente), und **nicht alle Knoten in derselben Klasse**

Anzeige pro Cluster:
- Beteiligte Schüler mit ihrer aktuellen Klasse
- Wunsch-Beziehungen kompakt notiert: `Anna B. (1a) ↔ Bea L. (1b) ↔ Carl M. (1b) ↔ Carl ← Anna`
- Knappe Zusammenfassung: „3 Kinder, davon 2 in 1b zusammen, Anna alleine in 1a"

### 4. Tausch-Vorschläge (Top 10)

Konkrete Tauschpaare (A in Klasse X) ⇄ (B in Klasse Y), die durch einen einfachen Tausch zusätzliche Wünsche erfüllen würden.

**Berechnung:**
- Für jedes Paar (A, B) mit unterschiedlicher Klasse:
  - Score = Anzahl A's Wünsche in Y, die nach Tausch erfüllt wären, + Anzahl B's Wünsche in X, die nach Tausch erfüllt wären − Anzahl A's bisher erfüllter Wünsche, die durch Tausch verloren gingen − analog für B
  - Falls Score ≤ 0: verwerfen
- **Hart gefiltert:** Vorschläge, die nach dem Tausch eine `Trennen_Von`-Regel verletzen würden, werden vollständig ausgeschlossen
- Sortiert nach Score absteigend, dann Top 10

**Pro Vorschlag angezeigt:**
- Lukas K. (1a) ⇄ Mia M. (1b)
- „+2 Wünsche erfüllt"
- Kurze Auswirkung: Geschlechter-, Auffälligkeits-, Migrations-Verschiebung in den betroffenen Klassen (informativ, nicht blockierend)
- Sprengel-Hinweis, falls relevant
- Button **„Tausch durchführen"** → ändert die Einteilung im State analog zum Drag&Drop, triggert anschließend eine neue Qualitätsprüfung

## Backend-Änderungen

### `backend/pruefungen/qualitaet.py`

Erweitern um:

**a) Gegenseitigkeits-Lookup:**
```
wunsch_set: dict[int, set[int]] = { schueler_id: {wunsch_id, ...} }
ist_beidseitig(a, b) = b in wunsch_set[a] and a in wunsch_set[b]
```

**b) Pro-Schüler-Aggregation:** Neue Felder pro Schüler-Eintrag in der Pruefung:
- `wuensche_erfuellt_count`
- `wuensche_gesamt_count`
- `wuensche_details`: Liste von `{wunsch_id, wunsch_name, wunsch_klasse, ist_beidseitig, ist_erfuellt}`

**c) Klassen-Aggregation:** Auf `KlassenPruefung` neue Felder:
- `leer_ausgegangen` (int) — Schüler mit ≥1 Wunsch, 0 erfüllt
- `beidseitig_zerrissen` (int) — beidseitige Wünsche nicht erfüllt, jedes Paar einmal

**d) Cluster-Erkennung:** Neue Top-Level-Liste `pruefung.cluster`. Algorithmus: Union-Find auf dem ungerichteten Wunsch-Graphen, dann pro Komponente Filterung.

**e) Tausch-Vorschläge:** Neue Top-Level-Liste `pruefung.tausch_vorschlaege` (Top 10). Algorithmus: doppelte Schleife über (A in Klasse X, B in Klasse Y mit X≠Y), Score berechnen, Trennungs-Check, sortieren.

Performance-Note: Bei N Schülern ist die naive Tauschberechnung O(N²). Bei einer typischen Grundschulgröße (≤100 SuS) unproblematisch. Falls später nötig, kann auf „nur Paare mit mindestens einem unerfüllten Wunsch in die richtige Richtung" eingeschränkt werden.

### `backend/api/routes.py`

Die zusätzlichen Analyse-Daten kommen im bestehenden `pruefung`-JSON des Qualitäts-Endpunkts mit (keine Änderung am bestehenden Endpunkt-Vertrag, nur neue Felder).

**Neuer Endpunkt `POST /api/tausch`:** Body `{schueler_a_id: int, schueler_b_id: int}`. Verändert die aktuelle Einteilung im State (vertauscht die Klassenzuordnung der beiden), triggert eine Neuberechnung der Pruefung und gibt diese zurück. Logik analog zur bestehenden Drag&Drop-State-Mutation.

## Frontend-Änderungen

### `frontend/index.html`

`wuenscheCard` umbenennen/ersetzen durch `wunschAnalyseCard` mit vier Sub-Sektionen (`<div class="sub-sektion">` o. ä.).

### `frontend/app.js`

`renderWuensche()` ersetzen durch vier neue Render-Funktionen:
- `renderKlassenAggregation(pruefung)`
- `renderSchuelerWunschTabelle(pruefung)`
- `renderCluster(pruefung)`
- `renderTauschVorschlaege(pruefung)`

Plus Filter-Handler und Sortier-Logik für die Schüler-Tabelle.

Tausch-Button-Handler ruft `POST /api/tausch`, lädt die neue Pruefung, rendert neu.

### `frontend/style.css`

Neue Klassen für:
- Wunsch-Chip mit Symbol (↔/→ + ✓/✗ Farbcodierung)
- „Leer ausgegangen"-Markierung in der Schüler-Tabelle
- Cluster-Box
- Tausch-Karte mit Vorher/Nachher-Andeutung

## Out of Scope (bewusste Auslassungen)

- **Klassen-Paar-Heatmap-Matrix** — wäre eine n×n-Tabelle „Wünsche zwischen Klasse X und Y zerrissen". Nicht vom User priorisiert.
- **Live-Update beim Drag&Drop** — die Wunsch-Analyse wird nur nach „Optimieren" bzw. nach Tausch aktualisiert, nicht reaktiv bei jedem manuellen Verschieben.
- **Persistente Speicherung der Tausch-Historie** — Tausch ändert nur den State, keine Audit-Log.
- **Mehrfach-Tausch (3er-Rotation)** — nur Paar-Tausche werden vorgeschlagen.

## Risiken / offene Punkte

- **Performance Tausch-Berechnung:** bei sehr großen Klassen (>200 SuS) ggf. zu langsam. Erste Implementierung naiv, ggf. später optimieren.
- **Cluster-Heuristik:** „≥3 Knoten, ≥2 beidseitige Kanten, nicht alle in einer Klasse" könnte zu strikt oder zu locker sein. Schwellenwerte ggf. nach Praxiseinsatz justieren.
- **Tausch-Button und Drag&Drop-State:** muss exakt mit dem bestehenden Mechanismus konsistent bleiben, damit die anschließende SA-Optimierung wieder funktioniert.

## Akzeptanzkriterien

- [ ] Pro-Schüler-Tabelle zeigt für jeden Schüler mit Wunsch eine Zeile mit ✓/✗ und ↔/→ pro Wunsch
- [ ] Default-Sortierung: leer Ausgegangene zuerst
- [ ] Klassen-Aggregation oben zeigt korrekt „leer ausgegangen" und „beidseitig zerrissen" pro Klasse
- [ ] Cluster-Sektion zeigt zerrissene Cliquen mit ≥3 Schülern
- [ ] Tausch-Vorschläge (Top 10) sortiert nach Anzahl gelöster Wünsche, keine Trennungs-Verletzer
- [ ] „Tausch durchführen"-Button verschiebt beide Schüler und löst Neu-Berechnung der Pruefung aus
- [ ] Die alte `renderWuensche`-Tabelle ist entfernt
