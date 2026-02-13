/**
 * Klasseneinteilung Web-App – Frontend
 *
 * Features:
 * - Upload mit intelligentem Spalten-Mapping
 * - Wunsch-/Trennungs-Zuordnung per Autocomplete
 * - Optimierung + Qualitätsprüfung
 * - Drag & Drop zwischen Klassen
 */

const API = "/api";

// --- Erlaubte Werte (synchron mit Backend) ---
const ERLAUBTE_AUFFAELLIGKEIT = [1, 2, 3, 5, 8, 13];
const ERLAUBTE_GESCHLECHT = ["m", "w"];
const ERLAUBTE_MIGRATION = ["Ja", "Nein"];

// --- App-State ---
let currentData = null;
let schuelerListe = [];   // Aktuelle Schülerliste aus dem Backend

// --- DOM-Elemente ---
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const fileName = document.getElementById("fileName");
const uploadInfo = document.getElementById("uploadInfo");
const anzahlKlassen = document.getElementById("anzahlKlassen");
const iterationen = document.getElementById("iterationen");
const startBtn = document.getElementById("startBtn");
const exportBtn = document.getElementById("exportBtn");
const progressContainer = document.getElementById("progressContainer");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const ampelBanner = document.getElementById("ampelBanner");
const ampelIcon = document.getElementById("ampelIcon");
const ampelText = document.getElementById("ampelText");
const dashboard = document.getElementById("dashboard");
const summaryCards = document.getElementById("summaryCards");
const pruefungTable = document.getElementById("pruefungTable");
const wuenscheCard = document.getElementById("wuenscheCard");
const wuenscheBadge = document.getElementById("wuenscheBadge");
const wuenscheTable = document.getElementById("wuenscheTable");
const klassenSection = document.getElementById("klassenSection");
const klassenGrid = document.getElementById("klassenGrid");

// Neue Elemente
const mappingSection = document.getElementById("mappingSection");
const mappingGrid = document.getElementById("mappingGrid");
const mappingConfirmBtn = document.getElementById("mappingConfirmBtn");
const schuelerEditSection = document.getElementById("schuelerEditSection");
const schuelerEditBody = document.getElementById("schuelerEditBody");
const schuelerAnzahlBadge = document.getElementById("schuelerAnzahlBadge");
const confirmDataBtn = document.getElementById("confirmDataBtn");


// ==========================================================
// Upload
// ==========================================================

uploadBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;

    fileName.textContent = file.name;
    const formData = new FormData();
    formData.append("file", file);

    // Bisherige Bereiche ausblenden
    mappingSection.classList.add("hidden");
    schuelerEditSection.classList.add("hidden");
    dashboard.classList.add("hidden");
    ampelBanner.classList.add("hidden");
    klassenSection.classList.add("hidden");
    startBtn.disabled = true;
    exportBtn.disabled = true;

    try {
        const res = await fetch(`${API}/upload`, { method: "POST", body: formData });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Upload fehlgeschlagen");
        }
        const data = await res.json();

        uploadInfo.textContent = `${data.anzahl_zeilen} Zeilen erkannt in "${data.dateiname}"`;
        uploadInfo.classList.remove("hidden");

        if (data.braucht_mapping) {
            // Mapping-UI anzeigen
            zeigeMapping(data.mapping, data.alle_spalten);
        } else {
            // Alle Spalten erkannt → direkt zur Schülerliste
            schuelerListe = data.schueler || [];
            zeigeSchuelerEditor(schuelerListe, data.validierung || []);
        }

    } catch (err) {
        alert("Fehler beim Upload: " + err.message);
    }
});


// ==========================================================
// Spalten-Mapping UI
// ==========================================================

let currentMappingData = null;

function zeigeMapping(mapping, alleSpalten) {
    currentMappingData = { mapping, alleSpalten };
    mappingGrid.innerHTML = "";

    // Pflichtspalten aus dem Mapping
    const pflichtSpalten = [
        "Vorname", "Name", "Geschlecht",
        "Auffaelligkeit_Score",
        "Migrationshintergrund / 2. Staatsangehörigkeit",
    ];

    for (const zielName of pflichtSpalten) {
        const info = mapping[zielName] || { spalte: null, confidence: "nicht_gefunden" };
        const row = document.createElement("div");
        row.className = "mapping-row";

        // Ampel-Indikator
        const ampelClass = info.confidence === "sicher" ? "gruen"
            : info.confidence === "vorschlag" ? "orange" : "rot";

        row.innerHTML = `
            <div class="mapping-ziel">
                <span class="mapping-ampel ${ampelClass}"></span>
                <strong>${zielName}</strong>
            </div>
            <div class="mapping-pfeil">→</div>
            <div class="mapping-auswahl">
                <select data-ziel="${zielName}">
                    <option value="">— nicht zugeordnet —</option>
                    ${alleSpalten.map(s =>
                        `<option value="${s}" ${s === info.spalte ? "selected" : ""}>${s}</option>`
                    ).join("")}
                </select>
            </div>
        `;
        mappingGrid.appendChild(row);
    }

    mappingSection.classList.remove("hidden");
}

mappingConfirmBtn.addEventListener("click", async () => {
    const selects = mappingGrid.querySelectorAll("select");
    const mapping = {};

    for (const sel of selects) {
        const ziel = sel.dataset.ziel;
        const wert = sel.value || null;
        mapping[ziel] = wert;
    }

    // Validierung: Alle Pflichtspalten zugeordnet?
    const pflichtFehlt = Object.entries(mapping)
        .filter(([_, v]) => v === null)
        .map(([k]) => k);

    if (pflichtFehlt.length > 0) {
        alert(`Bitte ordnen Sie alle Pflichtspalten zu:\n${pflichtFehlt.join("\n")}`);
        return;
    }

    try {
        const res = await fetch(`${API}/mapping-bestaetigen`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mapping }),
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Mapping-Bestätigung fehlgeschlagen");
        }
        const data = await res.json();
        schuelerListe = data.schueler || [];
        mappingSection.classList.add("hidden");
        zeigeSchuelerEditor(schuelerListe, data.validierung || []);
    } catch (err) {
        alert("Fehler: " + err.message);
    }
});


// ==========================================================
// Schüler-Editor (Wünsche / Trennungen)
// ==========================================================

function zeigeSchuelerEditor(schueler, validierung = []) {
    schuelerListe = schueler;
    schuelerAnzahlBadge.textContent = schueler.length;
    schuelerEditBody.innerHTML = "";

    // Validierungshinweise nach Schüler-ID gruppieren
    const hinweiseMap = {};
    for (const h of validierung) {
        if (!hinweiseMap[h.schueler_id]) hinweiseMap[h.schueler_id] = [];
        hinweiseMap[h.schueler_id].push(h);
    }

    // Validierungs-Banner anzeigen wenn es Hinweise gibt
    const existingBanner = document.getElementById("validierungBanner");
    if (existingBanner) existingBanner.remove();

    if (validierung.length > 0) {
        const banner = document.createElement("div");
        banner.id = "validierungBanner";
        banner.className = "validierung-banner";
        banner.innerHTML = `
            <span class="validierung-icon">⚠️</span>
            <div>
                <strong>${validierung.length} Hinweis${validierung.length > 1 ? "e" : ""} zu den Eingabedaten</strong>
                <p>Einige Werte entsprechen nicht den erlaubten Eingaben. Betroffene Zeilen sind markiert. Sie können die Werte direkt in den Dropdowns korrigieren.</p>
            </div>
        `;
        schuelerEditSection.querySelector(".schueler-edit-header").after(banner);
    }

    for (const s of schueler) {
        const tr = document.createElement("tr");
        tr.dataset.schuelerId = s.id;

        const hatHinweise = hinweiseMap[s.id] && hinweiseMap[s.id].length > 0;
        if (hatHinweise) tr.classList.add("validierung-fehler");

        // Geschlecht-Dropdown
        const geschlechtOptionen = ERLAUBTE_GESCHLECHT.map(g =>
            `<option value="${g}" ${g === s.geschlecht ? "selected" : ""}>${g.toUpperCase()}</option>`
        ).join("");
        const geschlechtInvalid = s.geschlecht && !ERLAUBTE_GESCHLECHT.includes(s.geschlecht);
        const geschlechtSelect = `<select class="edit-select edit-geschlecht" data-schueler-id="${s.id}">
            ${geschlechtInvalid ? `<option value="${s.geschlecht}" selected>${s.geschlecht}</option>` : ""}
            ${geschlechtOptionen}
        </select>`;

        // Auffälligkeits-Dropdown
        const auffWert = Math.round(s.auffaelligkeit);
        const auffOptionen = ERLAUBTE_AUFFAELLIGKEIT.map(a =>
            `<option value="${a}" ${a === auffWert ? "selected" : ""}>${a}</option>`
        ).join("");
        const auffInvalid = auffWert > 0 && !ERLAUBTE_AUFFAELLIGKEIT.includes(auffWert);
        const auffSelect = `<select class="edit-select edit-auff" data-schueler-id="${s.id}">
            <option value="0" ${auffWert === 0 ? "selected" : ""}>–</option>
            ${auffInvalid ? `<option value="${auffWert}" selected>${auffWert} ⚠</option>` : ""}
            ${auffOptionen}
        </select>`;

        // Migration-Dropdown
        const migWert = s.migration || "";
        const migOptionen = ERLAUBTE_MIGRATION.map(m =>
            `<option value="${m}" ${m === migWert ? "selected" : ""}>${m}</option>`
        ).join("");
        const migInvalid = migWert && !ERLAUBTE_MIGRATION.includes(migWert);
        const migSelect = `<select class="edit-select edit-migration" data-schueler-id="${s.id}">
            <option value="">–</option>
            ${migInvalid ? `<option value="${migWert}" selected>${migWert} ⚠</option>` : ""}
            ${migOptionen}
        </select>`;

        tr.innerHTML = `
            <td class="col-nr">${s.id}</td>
            <td class="col-name">${s.vorname} ${s.name}</td>
            <td class="col-geschlecht">${geschlechtSelect}</td>
            <td class="col-auff">${auffSelect}</td>
            <td class="col-migration">${migSelect}</td>
            <td class="col-wuensche">
                <div class="autocomplete-container" data-schueler-id="${s.id}" data-type="wuensche" data-max="4"></div>
            </td>
            <td class="col-trennung">
                <div class="autocomplete-container" data-schueler-id="${s.id}" data-type="trennung" data-max="4"></div>
            </td>
        `;
        schuelerEditBody.appendChild(tr);

        // Hinweis-Zeile unterhalb einfügen
        if (hatHinweise) {
            const hinweisTr = document.createElement("tr");
            hinweisTr.className = "validierung-hinweis-row";
            hinweisTr.innerHTML = `<td colspan="7">${hinweiseMap[s.id].map(h =>
                `<div class="validierung-hinweis-item">⚠ <strong>${h.spalte}</strong>: ${h.hinweis}</div>`
            ).join("")}</td>`;
            schuelerEditBody.appendChild(hinweisTr);
        }
    }

    // Autocomplete-Komponenten initialisieren
    document.querySelectorAll(".autocomplete-container").forEach(container => {
        const sid = parseInt(container.dataset.schuelerId);
        const type = container.dataset.type;
        const max = parseInt(container.dataset.max);

        const s = schueler.find(x => x.id === sid);
        const vorauswahl = type === "wuensche" ? (s.wuensche || []) : (s.trennen_von || []);

        initAutocomplete(container, sid, max, vorauswahl);
    });

    schuelerEditSection.classList.remove("hidden");
    startBtn.disabled = true;
}


// ==========================================================
// Autocomplete-Komponente
// ==========================================================

function initAutocomplete(container, eigeneId, maxAuswahl, vorauswahl) {
    container.innerHTML = "";

    const wrapper = document.createElement("div");
    wrapper.className = "ac-wrapper";

    const chipsDiv = document.createElement("div");
    chipsDiv.className = "ac-chips";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "ac-input";
    input.placeholder = "Name eingeben…";

    const dropdown = document.createElement("div");
    dropdown.className = "ac-dropdown hidden";

    wrapper.appendChild(chipsDiv);
    wrapper.appendChild(input);
    container.appendChild(wrapper);
    container.appendChild(dropdown);

    // State
    let ausgewaehlt = new Set();

    // Vorauswahl einfügen
    for (const id of vorauswahl) {
        const s = schuelerListe.find(x => x.id === id);
        if (s) {
            ausgewaehlt.add(id);
            chipsDiv.appendChild(erstelleChip(s, () => {
                ausgewaehlt.delete(id);
                renderChips();
            }));
        }
    }

    function renderChips() {
        chipsDiv.innerHTML = "";
        for (const id of ausgewaehlt) {
            const s = schuelerListe.find(x => x.id === id);
            if (s) {
                chipsDiv.appendChild(erstelleChip(s, () => {
                    ausgewaehlt.delete(id);
                    renderChips();
                }));
            }
        }
        // Input verstecken wenn Max erreicht
        input.style.display = ausgewaehlt.size >= maxAuswahl ? "none" : "";
    }

    function erstelleChip(s, onRemove) {
        const chip = document.createElement("span");
        chip.className = "ac-chip";
        chip.innerHTML = `${s.vorname} ${s.name} <button type="button" class="ac-chip-x">&times;</button>`;
        chip.querySelector(".ac-chip-x").addEventListener("click", (e) => {
            e.stopPropagation();
            onRemove();
        });
        return chip;
    }

    function zeigeDropdown(filter) {
        dropdown.innerHTML = "";
        const filterLower = filter.toLowerCase();

        const treffer = schuelerListe.filter(s =>
            s.id !== eigeneId &&
            !ausgewaehlt.has(s.id) &&
            (`${s.vorname} ${s.name}`).toLowerCase().includes(filterLower)
        ).slice(0, 8);

        if (treffer.length === 0) {
            dropdown.classList.add("hidden");
            return;
        }

        for (const s of treffer) {
            const item = document.createElement("div");
            item.className = "ac-item";
            item.innerHTML = `
                <span class="geschlecht-badge ${s.geschlecht}" style="width:18px;height:18px;line-height:18px;font-size:0.6rem">${s.geschlecht.toUpperCase()}</span>
                ${s.vorname} ${s.name}
            `;
            item.addEventListener("mousedown", (e) => {
                e.preventDefault(); // Verhindert blur
                if (ausgewaehlt.size < maxAuswahl) {
                    ausgewaehlt.add(s.id);
                    renderChips();
                    input.value = "";
                    dropdown.classList.add("hidden");
                }
            });
            dropdown.appendChild(item);
        }
        dropdown.classList.remove("hidden");
    }

    // Events
    input.addEventListener("input", () => {
        if (input.value.length >= 1) {
            zeigeDropdown(input.value);
        } else {
            dropdown.classList.add("hidden");
        }
    });

    input.addEventListener("focus", () => {
        if (input.value.length >= 1) {
            zeigeDropdown(input.value);
        }
    });

    input.addEventListener("blur", () => {
        // Kurze Verzögerung, damit mousedown auf Dropdown-Items noch feuert
        setTimeout(() => dropdown.classList.add("hidden"), 150);
    });

    input.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            dropdown.classList.add("hidden");
            input.blur();
        }
    });

    // Ausgewählte IDs abfragbar machen
    container._getAusgewaehlt = () => Array.from(ausgewaehlt);

    // Initial render
    renderChips();
}


// ==========================================================
// Daten bestätigen → Wünsche speichern
// ==========================================================

confirmDataBtn.addEventListener("click", async () => {
    // Zuordnungen + Korrekturen sammeln
    const zuordnungen = [];

    for (const s of schuelerListe) {
        const wuenscheContainer = document.querySelector(
            `.autocomplete-container[data-schueler-id="${s.id}"][data-type="wuensche"]`
        );
        const trennungContainer = document.querySelector(
            `.autocomplete-container[data-schueler-id="${s.id}"][data-type="trennung"]`
        );

        // Dropdown-Werte auslesen
        const geschlechtSel = document.querySelector(`.edit-geschlecht[data-schueler-id="${s.id}"]`);
        const auffSel = document.querySelector(`.edit-auff[data-schueler-id="${s.id}"]`);
        const migSel = document.querySelector(`.edit-migration[data-schueler-id="${s.id}"]`);

        zuordnungen.push({
            schueler_id: s.id,
            wuensche: wuenscheContainer?._getAusgewaehlt() || [],
            trennen_von: trennungContainer?._getAusgewaehlt() || [],
            geschlecht: geschlechtSel?.value || null,
            auffaelligkeit: auffSel ? parseInt(auffSel.value) : null,
            migration: migSel?.value || null,
        });
    }

    try {
        confirmDataBtn.disabled = true;
        confirmDataBtn.textContent = "Speichere…";

        const res = await fetch(`${API}/wuensche-speichern`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ zuordnungen }),
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Speichern fehlgeschlagen");
        }
        const data = await res.json();

        // Upload-Info aktualisieren
        uploadInfo.textContent = `${data.anzahl_schueler} Schüler | ${data.wunsch_spalten} Wunschspalten | Trennung: ${data.hat_trennung ? "Ja" : "Nein"} | ${data.schueler_mit_wuenschen} Schüler mit Wünschen`;
        uploadInfo.classList.remove("hidden");

        // Validierungshinweise entfernen wenn alles OK
        if (data.validierung && data.validierung.length === 0) {
            document.querySelectorAll(".validierung-fehler").forEach(el => el.classList.remove("validierung-fehler"));
            document.querySelectorAll(".validierung-hinweis-row").forEach(el => el.remove());
            const banner = document.getElementById("validierungBanner");
            if (banner) banner.remove();
        } else if (data.validierung && data.validierung.length > 0) {
            // Noch Fehler vorhanden → Schülerliste mit neuen Hinweisen neu laden
            const schuelerRes = await fetch(`${API}/schueler`);
            if (schuelerRes.ok) {
                const schuelerData = await schuelerRes.json();
                schuelerListe = schuelerData.schueler || [];
                zeigeSchuelerEditor(schuelerListe, data.validierung);
            }
        }

        // Start-Button aktivieren (auch mit Warnungen – die sind nur Hinweise)
        startBtn.disabled = false;

        // Visuelles Feedback
        confirmDataBtn.innerHTML = `<span class="icon">✓</span> Gespeichert!`;
        confirmDataBtn.classList.remove("btn-success");
        confirmDataBtn.classList.add("btn-secondary");

        setTimeout(() => {
            confirmDataBtn.innerHTML = `<span class="icon">✓</span> Daten bestätigen & weiter`;
            confirmDataBtn.classList.remove("btn-secondary");
            confirmDataBtn.classList.add("btn-success");
            confirmDataBtn.disabled = false;
        }, 2000);

    } catch (err) {
        alert("Fehler: " + err.message);
        confirmDataBtn.disabled = false;
        confirmDataBtn.innerHTML = `<span class="icon">✓</span> Daten bestätigen & weiter`;
    }
});


// ==========================================================
// Optimierung starten
// ==========================================================

startBtn.addEventListener("click", async () => {
    startBtn.disabled = true;
    exportBtn.disabled = true;
    dashboard.classList.add("hidden");
    ampelBanner.classList.add("hidden");
    klassenSection.classList.add("hidden");

    progressContainer.classList.remove("hidden");
    progressFill.style.width = "0%";
    progressText.textContent = "Optimierung läuft...";

    let progress = 0;
    const progressInterval = setInterval(() => {
        progress = Math.min(progress + Math.random() * 5, 90);
        progressFill.style.width = progress + "%";
    }, 300);

    try {
        const params = new URLSearchParams({
            anzahl_klassen: anzahlKlassen.value,
            iterationen: iterationen.value,
        });

        const res = await fetch(`${API}/optimierung?${params}`, { method: "POST" });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Optimierung fehlgeschlagen");
        }
        const data = await res.json();
        currentData = data;

        clearInterval(progressInterval);
        progressFill.style.width = "100%";
        progressText.textContent = `Fertig! Score: ${data.score}`;

        setTimeout(() => {
            progressContainer.classList.add("hidden");
            renderAlles(data);

            // Info über erzwungene Trennungs-Verschiebungen
            if (data.trennungen_erzwungen && data.trennungen_erzwungen.length > 0) {
                zeigeTrennungsInfo(data.trennungen_erzwungen);
            }
        }, 500);

    } catch (err) {
        clearInterval(progressInterval);
        progressContainer.classList.add("hidden");
        alert("Fehler: " + err.message);
    } finally {
        startBtn.disabled = false;
    }
});


// ==========================================================
// Export
// ==========================================================

exportBtn.addEventListener("click", () => {
    window.location.href = `${API}/export`;
});


// ==========================================================
// Rendering
// ==========================================================

function renderAlles(data) {
    renderAmpel(data.pruefung);
    renderSummary(data.pruefung);
    renderPruefungTabelle(data.pruefung);
    renderWuensche(data.pruefung);
    renderKlassen(data.klassen);

    dashboard.classList.remove("hidden");
    klassenSection.classList.remove("hidden");
    exportBtn.disabled = false;
}

function renderAmpel(pruefung) {
    ampelBanner.classList.remove("hidden", "gruen", "orange", "rot");
    ampelBanner.classList.add(pruefung.gesamt_ampel);

    const icons = { gruen: "✅", orange: "⚠️", rot: "❌" };
    const texte = {
        gruen: "Alle Kriterien erfüllt – gute Einteilung!",
        orange: "Einige Kriterien mit leichten Abweichungen",
        rot: "Achtung: Kritische Abweichungen bei der Einteilung",
    };
    ampelIcon.textContent = icons[pruefung.gesamt_ampel];
    ampelText.textContent = texte[pruefung.gesamt_ampel];
}

function renderSummary(pruefung) {
    const z = pruefung.zusammenfassung;
    summaryCards.innerHTML = `
        <div class="summary-card">
            <div class="value">${z.anzahl_schueler}</div>
            <div class="label">Schüler gesamt</div>
        </div>
        <div class="summary-card">
            <div class="value">${z.anzahl_klassen}</div>
            <div class="label">Klassen</div>
        </div>
        <div class="summary-card">
            <div class="value">${z.klassengroesse_min}–${z.klassengroesse_max}</div>
            <div class="label">Klassengröße (Ideal: ${z.klassengroesse_ideal})</div>
        </div>
        <div class="summary-card">
            <div class="value" style="color: var(--${z.wuensche_quote_pct >= 75 ? 'gruen' : z.wuensche_quote_pct >= 50 ? 'orange' : 'rot'})">${z.wuensche_quote_pct}%</div>
            <div class="label">Wünsche erfüllt (${z.wuensche_erfuellt}/${z.wuensche_gesamt})</div>
        </div>
        <div class="summary-card">
            <div class="value" style="color: var(--${z.trennungen_missachtet_gesamt === 0 ? 'gruen' : 'rot'})">${z.trennungen_missachtet_gesamt}</div>
            <div class="label">Trennungen missachtet</div>
        </div>
    `;
}

function renderPruefungTabelle(pruefung) {
    const thead = pruefungTable.querySelector("thead");
    const tbody = pruefungTable.querySelector("tbody");

    thead.innerHTML = `<tr>
        <th>Klasse</th>
        <th>Sch.</th>
        <th>M</th><th>W</th><th>Δ</th><th></th>
        <th>Auff. Σ</th><th>Auff. Ø</th><th></th>
        <th>Migr. %</th><th>Δ pp</th><th></th>
        <th>Wunsch %</th><th></th>
        <th>Trenn.</th><th></th>
    </tr>`;

    tbody.innerHTML = pruefung.klassen.map(kp => `<tr>
        <td><strong>Klasse ${kp.klasse_name}</strong></td>
        <td>${kp.anzahl_schueler}</td>
        <td>${kp.maennlich}</td>
        <td>${kp.weiblich}</td>
        <td>${kp.geschlecht_differenz}</td>
        <td><span class="ampel-cell ${kp.geschlecht_ampel}"></span></td>
        <td>${kp.auffaelligkeit_summe}</td>
        <td>${kp.auffaelligkeit_durchschnitt}</td>
        <td><span class="ampel-cell ${kp.auffaelligkeit_ampel}"></span></td>
        <td>${kp.migration_anteil_pct}%</td>
        <td>${kp.migration_abweichung_pp}</td>
        <td><span class="ampel-cell ${kp.migration_ampel}"></span></td>
        <td>${kp.wunsch_quote_pct}%</td>
        <td><span class="ampel-cell ${kp.wunsch_ampel}"></span></td>
        <td>${kp.trennungen_missachtet}</td>
        <td><span class="ampel-cell ${kp.trennungen_ampel}"></span></td>
    </tr>`).join("");
}

function renderWuensche(pruefung) {
    const alleWuensche = pruefung.klassen.flatMap(kp => kp.nicht_erfuellte_wuensche);

    if (alleWuensche.length > 0) {
        wuenscheCard.classList.remove("hidden");
        wuenscheBadge.textContent = alleWuensche.length;

        wuenscheTable.querySelector("tbody").innerHTML = alleWuensche.map(w => `<tr>
            <td>${w.schueler_name} <span style="color:var(--text-muted)">(${w.schueler_id})</span></td>
            <td><strong>${w.klasse}</strong></td>
            <td>${w.wunsch_name} <span style="color:var(--text-muted)">(${w.wunsch_id})</span></td>
            <td><strong>${w.wunsch_klasse || "?"}</strong></td>
        </tr>`).join("");
    } else {
        wuenscheCard.classList.add("hidden");
    }
}


// ==========================================================
// Klassenlisten mit Drag & Drop
// ==========================================================

function renderKlassen(klassen) {
    klassenGrid.innerHTML = klassen.map((klasse, klassenIdx) => `
        <div class="klasse-card" data-klasse-idx="${klassenIdx}">
            <div class="klasse-header">
                <span>Klasse ${klasse.name}</span>
                <span class="klasse-stats">${klasse.schueler.length} Schüler</span>
            </div>
            <div class="klasse-schueler-list" data-klasse-idx="${klassenIdx}">
                ${klasse.schueler.map(s => schuelerRowHtml(s)).join("")}
            </div>
        </div>
    `).join("");

    initDragAndDrop();
}

function schuelerRowHtml(s) {
    let auffTag = "auffaelligkeit-tag";
    if (s.auffaelligkeit >= 5) auffTag += " sehr-hoch";
    else if (s.auffaelligkeit >= 3) auffTag += " hoch";

    return `
        <div class="schueler-row" draggable="true" data-schueler-id="${s.id}">
            <span class="geschlecht-badge ${s.geschlecht}">${s.geschlecht.toUpperCase()}</span>
            <span class="schueler-name">${s.vorname} ${s.name}</span>
            <span class="${auffTag}">${s.auffaelligkeit}</span>
        </div>
    `;
}


// ==========================================================
// Drag & Drop Logik
// ==========================================================

let draggedElement = null;
let draggedSchuelerId = null;
let sourceKlasseIdx = null;

function initDragAndDrop() {
    const rows = document.querySelectorAll(".schueler-row");
    const dropZones = document.querySelectorAll(".klasse-schueler-list");

    rows.forEach(row => {
        row.addEventListener("dragstart", onDragStart);
        row.addEventListener("dragend", onDragEnd);
    });

    dropZones.forEach(zone => {
        zone.addEventListener("dragover", onDragOver);
        zone.addEventListener("dragenter", onDragEnter);
        zone.addEventListener("dragleave", onDragLeave);
        zone.addEventListener("drop", onDrop);
    });
}

function onDragStart(e) {
    draggedElement = e.target;
    draggedSchuelerId = parseInt(e.target.dataset.schuelerId);
    sourceKlasseIdx = parseInt(e.target.closest(".klasse-schueler-list").dataset.klasseIdx);

    e.target.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", draggedSchuelerId);
}

function onDragEnd(e) {
    e.target.classList.remove("dragging");
    document.querySelectorAll(".klasse-card.drag-over").forEach(el => el.classList.remove("drag-over"));
    draggedElement = null;
    draggedSchuelerId = null;
    sourceKlasseIdx = null;
}

function onDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
}

function onDragEnter(e) {
    e.preventDefault();
    const card = e.target.closest(".klasse-card");
    if (card) card.classList.add("drag-over");
}

function onDragLeave(e) {
    const card = e.target.closest(".klasse-card");
    if (card && !card.contains(e.relatedTarget)) {
        card.classList.remove("drag-over");
    }
}

async function onDrop(e) {
    e.preventDefault();
    const targetZone = e.target.closest(".klasse-schueler-list");
    if (!targetZone) return;

    const targetKlasseIdx = parseInt(targetZone.dataset.klasseIdx);
    const card = targetZone.closest(".klasse-card");
    if (card) card.classList.remove("drag-over");

    if (targetKlasseIdx === sourceKlasseIdx) return;

    if (draggedElement) {
        targetZone.appendChild(draggedElement);
        draggedElement.classList.remove("dragging");
    }

    const neueEinteilung = bauEinteilungAusDOM();
    await sendeVerschiebung(neueEinteilung);
}

function bauEinteilungAusDOM() {
    const klassen = [];
    const zones = document.querySelectorAll(".klasse-schueler-list");
    zones.forEach(zone => {
        const ids = [];
        zone.querySelectorAll(".schueler-row").forEach(row => {
            ids.push(parseInt(row.dataset.schuelerId));
        });
        klassen.push(ids);
    });
    return klassen;
}

async function sendeVerschiebung(neueEinteilung) {
    try {
        const res = await fetch(`${API}/verschieben`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(neueEinteilung),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Verschiebung fehlgeschlagen");
        }

        const data = await res.json();
        currentData = data;

        renderAmpel(data.pruefung);
        renderSummary(data.pruefung);
        renderPruefungTabelle(data.pruefung);
        renderWuensche(data.pruefung);

        data.klassen.forEach((klasse, idx) => {
            const card = document.querySelector(`.klasse-card[data-klasse-idx="${idx}"]`);
            if (card) {
                const stats = card.querySelector(".klasse-stats");
                if (stats) stats.textContent = `${klasse.schueler.length} Schüler`;
            }
        });

        // Warnung bei verletzten Trennungen
        if (data.trennungen_verletzt && data.trennungen_verletzt.length > 0) {
            zeigeTrennungsWarnung(data.trennungen_verletzt);
        } else {
            entferneTrennungsWarnung();
        }

    } catch (err) {
        console.error("Verschiebung fehlgeschlagen:", err);
        if (currentData) {
            renderKlassen(currentData.klassen);
        }
    }
}


// ==========================================================
// Trennungs-Warnungen und -Info
// ==========================================================

/**
 * Zeigt eine Warnung an, wenn Trennungen durch manuelle Verschiebung verletzt wurden.
 */
function zeigeTrennungsWarnung(verletzungen) {
    entferneTrennungsWarnung();

    const banner = document.createElement("div");
    banner.id = "trennungWarnung";
    banner.className = "trennung-warnung";

    const zeilen = verletzungen.map(v =>
        `<strong>${v.schueler_a.name}</strong> und <strong>${v.schueler_b.name}</strong> sind beide in Klasse ${v.klasse}`
    ).join("<br>");

    banner.innerHTML = `
        <span class="trennung-warnung-icon">⛔</span>
        <div>
            <strong>Trennungen verletzt!</strong>
            <p>Folgende Schüler sollten getrennt werden, sind aber in derselben Klasse:</p>
            <div class="trennung-warnung-details">${zeilen}</div>
            <p class="trennung-warnung-hint">Bitte verschieben Sie einen der Schüler in eine andere Klasse.</p>
        </div>
    `;

    // Vor den Klassen-Karten einfügen
    const klassenGrid = document.getElementById("klassenGrid");
    if (klassenGrid) {
        klassenGrid.parentNode.insertBefore(banner, klassenGrid);
    }
}

function entferneTrennungsWarnung() {
    const existing = document.getElementById("trennungWarnung");
    if (existing) existing.remove();
}

/**
 * Zeigt eine Info an, welche Schüler nach der Optimierung automatisch verschoben wurden,
 * um Trennungen zu erzwingen.
 */
function zeigeTrennungsInfo(log) {
    entferneTrennungsInfo();

    const banner = document.createElement("div");
    banner.id = "trennungInfo";
    banner.className = "trennung-info";

    const zeilen = log.map(e =>
        `<strong>${e.name}</strong>: Klasse ${e.von_klasse} → Klasse ${e.nach_klasse} (${e.grund})`
    ).join("<br>");

    banner.innerHTML = `
        <span class="trennung-info-icon">ℹ️</span>
        <div>
            <strong>${log.length} Schüler wurden nach der Optimierung verschoben</strong>
            <p>Um alle Trennungen einzuhalten, wurden folgende Anpassungen vorgenommen:</p>
            <div class="trennung-info-details">${zeilen}</div>
        </div>
        <button class="trennung-info-close" onclick="entferneTrennungsInfo()">✕</button>
    `;

    const klassenGrid = document.getElementById("klassenGrid");
    if (klassenGrid) {
        klassenGrid.parentNode.insertBefore(banner, klassenGrid);
    }
}

function entferneTrennungsInfo() {
    const existing = document.getElementById("trennungInfo");
    if (existing) existing.remove();
}
