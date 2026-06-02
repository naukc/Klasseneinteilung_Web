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

// ==========================================================
// Heartbeat (für Auto-Shutdown der Desktop-App)
// ==========================================================

setInterval(() => {
    fetch(`${API}/heartbeat`, { method: "POST" }).catch(() => { });
}, 3000);

// ==========================================================
// Dark Mode Toggle
// ==========================================================

(function initTheme() {
    const toggle = document.getElementById("themeToggle");
    const gespeichertesTheme = localStorage.getItem("theme");

    // System-Präferenz prüfen, falls nichts gespeichert
    const bevorzugtDunkel = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = gespeichertesTheme || (bevorzugtDunkel ? "dark" : "light");

    if (theme === "dark") {
        document.documentElement.setAttribute("data-theme", "dark");
        toggle.checked = true;
    }

    toggle.addEventListener("change", () => {
        if (toggle.checked) {
            document.documentElement.setAttribute("data-theme", "dark");
            localStorage.setItem("theme", "dark");
        } else {
            document.documentElement.removeAttribute("data-theme");
            localStorage.setItem("theme", "light");
        }
    });
})();

// --- Erlaubte Werte (synchron mit Backend) ---
const ERLAUBTE_AUFFAELLIGKEIT = [1, 2, 3, 5, 8, 13, 21];
const ERLAUBTE_GESCHLECHT = ["m", "w"];
const ERLAUBTE_MIGRATION = ["Ja", "Nein"];

// --- App-State ---
let currentData = null;
let schuelerListe = [];   // Aktuelle Schülerliste aus dem Backend
let _wunschAnalyseDaten = null;  // wird in renderWunschAnalyse gesetzt, von Sub-Renderern gelesen

// --- DOM-Elemente ---
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const fileName = document.getElementById("fileName");
const uploadInfo = document.getElementById("uploadInfo");
const anzahlKlassen = document.getElementById("anzahlKlassen");
const iterationen = document.getElementById("iterationen");
const startBtn = document.getElementById("startBtn");
const exportBtn = document.getElementById("exportBtn");
const saveAssignmentBtn = document.getElementById("saveAssignmentBtn");
const savedAssignmentsSection = document.getElementById("savedAssignmentsSection");
const savedAssignmentsBody = document.getElementById("savedAssignmentsBody");
const saveModal = document.getElementById("saveModal");
const assignmentNameInput = document.getElementById("assignmentName");
const cancelSaveBtn = document.getElementById("cancelSaveBtn");
const confirmSaveBtn = document.getElementById("confirmSaveBtn");
const progressContainer = document.getElementById("progressContainer");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const ampelBanner = document.getElementById("ampelBanner");
const ampelIcon = document.getElementById("ampelIcon");
const ampelText = document.getElementById("ampelText");
const dashboard = document.getElementById("dashboard");
const summaryCards = document.getElementById("summaryCards");
const pruefungTable = document.getElementById("pruefungTable");
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
const exportSchuelerlisteBtn = document.getElementById("exportSchuelerlisteBtn");
const schulhundKlasse = document.getElementById("schulhundKlasse");

function aktualisiereSchulhundDropdown() {
    const anzahl = parseInt(anzahlKlassen.value, 10) || 0;
    schulhundKlasse.innerHTML = '<option value="">— keine —</option>';
    for (let i = 0; i < anzahl; i++) {
        const buchstabe = String.fromCharCode(65 + i);
        const opt = document.createElement("option");
        opt.value = String(i);
        opt.textContent = buchstabe;
        schulhundKlasse.appendChild(opt);
    }
    schulhundKlasse.value = "";
}

anzahlKlassen.addEventListener("change", aktualisiereSchulhundDropdown);
aktualisiereSchulhundDropdown();


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
    saveAssignmentBtn.disabled = true;

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

        const sprengelWert = s.sprengel || "";

        const allergieWert = s.hundehaarallergie || "";
        const allergieSelect = `<select class="edit-select edit-allergie" data-schueler-id="${s.id}">
            <option value="" ${allergieWert === "" ? "selected" : ""}>?</option>
            <option value="nein" ${allergieWert === "nein" ? "selected" : ""}>nein</option>
            <option value="ja" ${allergieWert === "ja" ? "selected" : ""}>ja</option>
        </select>`;

        tr.innerHTML = `
            <td class="col-nr">${s.id}</td>
            <td class="col-name">${s.vorname} ${s.name}</td>
            <td class="col-geschlecht">${geschlechtSelect}</td>
            <td class="col-auff">${auffSelect}</td>
            <td class="col-migration">${migSelect}</td>
            <td class="col-sprengel">${sprengelWert ? `<span class="sprengel-tag">${sprengelWert}</span>` : '<span class="text-muted">–</span>'}</td>
            <td class="col-allergie">${allergieSelect}</td>
            <td class="col-wuensche">
                <div class="autocomplete-container" data-schueler-id="${s.id}" data-type="wuensche"></div>
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
            hinweisTr.innerHTML = `<td colspan="9">${hinweiseMap[s.id].map(h =>
                `<div class="validierung-hinweis-item">⚠ <strong>${h.spalte}</strong>: ${h.hinweis}</div>`
            ).join("")}</td>`;
            schuelerEditBody.appendChild(hinweisTr);
        }
    }

    // Autocomplete-Komponenten initialisieren
    document.querySelectorAll(".autocomplete-container").forEach(container => {
        const sid = parseInt(container.dataset.schuelerId);
        const type = container.dataset.type;
        const max = parseInt(container.dataset.max) || Infinity;

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
        chip.innerHTML = `${s.vorname} ${s.name} <span class="ac-id-badge">#${s.id}</span> <button type="button" class="ac-chip-x">&times;</button>`;
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
            (`${s.vorname} ${s.name} ${s.id}`).toLowerCase().includes(filterLower)
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
                ${s.vorname} ${s.name} <span class="ac-id-badge">#${s.id}</span>
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

function sammleZuordnungenAusDOM() {
    const zuordnungen = [];
    for (const s of schuelerListe) {
        const wuenscheContainer = document.querySelector(
            `.autocomplete-container[data-schueler-id="${s.id}"][data-type="wuensche"]`
        );
        const trennungContainer = document.querySelector(
            `.autocomplete-container[data-schueler-id="${s.id}"][data-type="trennung"]`
        );
        const geschlechtSel = document.querySelector(`.edit-geschlecht[data-schueler-id="${s.id}"]`);
        const auffSel = document.querySelector(`.edit-auff[data-schueler-id="${s.id}"]`);
        const migSel = document.querySelector(`.edit-migration[data-schueler-id="${s.id}"]`);
        const allergieSel = document.querySelector(`.edit-allergie[data-schueler-id="${s.id}"]`);

        zuordnungen.push({
            schueler_id: s.id,
            wuensche: wuenscheContainer?._getAusgewaehlt() || [],
            trennen_von: trennungContainer?._getAusgewaehlt() || [],
            geschlecht: geschlechtSel?.value || null,
            auffaelligkeit: auffSel ? parseInt(auffSel.value) : null,
            migration: migSel?.value || null,
            hundehaarallergie: allergieSel ? allergieSel.value : null,
        });
    }
    return zuordnungen;
}

async function postZuordnungen(zuordnungen) {
    const res = await fetch(`${API}/wuensche-speichern`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ zuordnungen }),
    });
    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Speichern fehlgeschlagen");
    }
    return res.json();
}

// Wird vor Optimierung aufgerufen — sorgt dafür, dass im Editor eingetragene
// Wünsche/Trennungen/Korrekturen sicher im Backend sind, auch wenn der User
// nicht explizit auf "Daten bestätigen" geklickt hat.
async function autoSpeichereEditor() {
    if (schuelerEditSection.classList.contains("hidden")) return;
    if (!schuelerListe || schuelerListe.length === 0) return;
    const zuordnungen = sammleZuordnungenAusDOM();
    if (zuordnungen.length === 0) return;
    await postZuordnungen(zuordnungen);
}

confirmDataBtn.addEventListener("click", async () => {
    const zuordnungen = sammleZuordnungenAusDOM();

    try {
        confirmDataBtn.disabled = true;
        confirmDataBtn.textContent = "Speichere…";

        const data = await postZuordnungen(zuordnungen);

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

        // Neu: Speichern-Button auch aktivieren, da wir nun vor Optimierung speichern können
        saveAssignmentBtn.disabled = false;

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
// Schülerliste als Excel exportieren (Backup mit Wünschen/Trennungen)
// ==========================================================

exportSchuelerlisteBtn.addEventListener("click", async () => {
    const origLabel = exportSchuelerlisteBtn.innerHTML;
    try {
        exportSchuelerlisteBtn.disabled = true;
        exportSchuelerlisteBtn.innerHTML = `<span class="icon">⏳</span> Speichere…`;

        // Erst die aktuelle DOM-Eingabe ans Backend übertragen, damit
        // der Export auch wirklich enthält, was der Nutzer gerade getippt hat
        await autoSpeichereEditor();

        // Download via Browser-Navigation triggern
        window.location.href = `${API}/schuelerliste-export`;
    } catch (err) {
        alert("Export fehlgeschlagen: " + err.message);
    } finally {
        setTimeout(() => {
            exportSchuelerlisteBtn.innerHTML = origLabel;
            exportSchuelerlisteBtn.disabled = false;
        }, 1500);
    }
});


// ==========================================================
// Optimierung starten
// ==========================================================

startBtn.addEventListener("click", async () => {
    startBtn.disabled = true;
    exportBtn.disabled = true;
    saveAssignmentBtn.disabled = true;
    dashboard.classList.add("hidden");
    ampelBanner.classList.add("hidden");
    klassenSection.classList.add("hidden");

    progressContainer.classList.remove("hidden");
    progressFill.style.width = "0%";
    progressText.textContent = "Optimierung wird gestartet...";

    try {
        // Wünsche/Trennungen/Stammdaten-Korrekturen sicher ans Backend übertragen,
        // falls der Editor offen ist und der User nicht explizit "Daten bestätigen" geklickt hat.
        progressText.textContent = "Daten speichern...";
        await autoSpeichereEditor();

        const paramsObj = {
            anzahl_klassen: anzahlKlassen.value,
            iterationen: iterationen.value,
        };
        if (schulhundKlasse.value !== "") {
            paramsObj.schulhund_klasse = schulhundKlasse.value;
        }
        const params = new URLSearchParams(paramsObj);

        const res = await fetch(`${API}/optimierung?${params}`, { method: "POST" });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Optimierung fehlgeschlagen");
        }

        // SSE-Stream lesen
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let ergebnis = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // SSE-Events parsen (getrennt durch doppelte Newlines)
            const teile = buffer.split("\n\n");
            buffer = teile.pop(); // Unvollständiges Event behalten

            for (const teil of teile) {
                const zeile = teil.trim();
                if (!zeile.startsWith("data: ")) continue;

                let event;
                try {
                    event = JSON.parse(zeile.slice(6));
                } catch { continue; }

                if (event.type === "fortschritt") {
                    progressFill.style.width = event.prozent + "%";
                    progressText.textContent =
                        `Iteration ${event.iteration.toLocaleString("de-DE")} / ${event.iterationen_gesamt.toLocaleString("de-DE")}` +
                        ` — Score: ${event.bester_score}`;
                } else if (event.type === "ergebnis") {
                    ergebnis = event;
                } else if (event.type === "fehler") {
                    throw new Error(event.detail || "Optimierung fehlgeschlagen");
                }
            }
        }

        if (!ergebnis) {
            throw new Error("Keine Ergebnisse vom Server erhalten");
        }

        currentData = ergebnis;
        progressFill.style.width = "100%";
        progressText.textContent = `Fertig! Score: ${ergebnis.score}`;

        setTimeout(() => {
            progressContainer.classList.add("hidden");
            renderAlles(ergebnis);

            if (ergebnis.trennungen_erzwungen && ergebnis.trennungen_erzwungen.length > 0) {
                zeigeTrennungsInfo(ergebnis.trennungen_erzwungen);
            }
        }, 500);

    } catch (err) {
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
    renderWunschAnalyse(data.pruefung);
    renderKlassen(data.klassen, data.pruefung);

    dashboard.classList.remove("hidden");
    klassenSection.classList.remove("hidden");
    exportBtn.disabled = false;
    saveAssignmentBtn.disabled = false;
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
    let html = `
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

    if (z.hat_sprengel) {
        const lpFarbe = z.ohne_laufpartner_gesamt === 0 ? "gruen"
            : z.ohne_laufpartner_gesamt <= 2 * z.anzahl_klassen ? "orange" : "rot";
        html += `
            <div class="summary-card">
                <div class="value" style="color: var(--${lpFarbe})">${z.ohne_laufpartner_gesamt}</div>
                <div class="label">Ohne Laufpartner</div>
            </div>
        `;
    }

    summaryCards.innerHTML = html;
}

function renderPruefungTabelle(pruefung) {
    const thead = pruefungTable.querySelector("thead");
    const tbody = pruefungTable.querySelector("tbody");
    const hatSprengel = pruefung.zusammenfassung.hat_sprengel;
    const hatSchulhund = pruefung.schulhund_klasse_index !== null
        && pruefung.schulhund_klasse_index !== undefined;

    let headerHtml = `<tr>
        <th>Klasse</th>
        <th>Sch.</th>
        <th>M</th><th>W</th><th>Δ</th><th></th>
        <th>Auff. Σ</th><th>Auff. Ø</th><th></th>
        <th>Migr. %</th><th>Δ pp</th><th></th>
        <th>Wunsch %</th><th></th>
        <th>Trenn.</th><th></th>`;
    if (hatSprengel) headerHtml += `<th title="Kinder ohne Laufpartner (gleicher Sprengel)">Ohne LP</th><th></th>`;
    if (hatSchulhund) headerHtml += `<th title="🐕 Schulhund-Klasse">🐕</th><th></th>`;
    headerHtml += `</tr>`;
    thead.innerHTML = headerHtml;

    tbody.innerHTML = pruefung.klassen.map(kp => {
        let rowHtml = `<tr>
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
            <td><span class="ampel-cell ${kp.trennungen_ampel}"></span></td>`;
        if (hatSprengel) {
            const lpTitle = kp.ohne_laufpartner_details && kp.ohne_laufpartner_details.length > 0
                ? kp.ohne_laufpartner_details.map(d => `${d.schueler_name} (${d.sprengel})`).join("\n")
                : "";
            rowHtml += `<td title="${lpTitle}">${kp.ohne_laufpartner}</td>`;
            rowHtml += `<td><span class="ampel-cell ${kp.laufpartner_ampel}"></span></td>`;
        }
        if (hatSchulhund) {
            if (kp.ist_schulhund_klasse) {
                const tooltip = `Allergiker: ${kp.schulhund_allergiker}, Unbekannt: ${kp.schulhund_unbekannt}`;
                rowHtml += `<td title="${tooltip}">${kp.schulhund_allergiker + kp.schulhund_unbekannt}</td>`;
                rowHtml += `<td><span class="ampel-cell ${kp.schulhund_ampel}"></span></td>`;
            } else {
                rowHtml += `<td class="text-muted">–</td><td></td>`;
            }
        }
        rowHtml += `</tr>`;
        return rowHtml;
    }).join("");
}

function renderWunschAnalyse(pruefung) {
    _wunschAnalyseDaten = pruefung;
    const wunschDetails = pruefung.wunsch_details || {};
    const hatDaten = Object.keys(wunschDetails).length > 0;

    if (!hatDaten) {
        wunschAnalyseCard.classList.add("hidden");
        return;
    }
    wunschAnalyseCard.classList.remove("hidden");

    const offene = Object.values(wunschDetails).reduce(
        (acc, d) => acc + (d.wuensche_gesamt - d.wuensche_erfuellt),
        0
    );
    wunschAnalyseBadge.textContent = offene;

    renderWaKlassen(pruefung);
    renderWaSchueler(pruefung);
    renderWaCluster(pruefung);
    renderWaTausch(pruefung);
}

function renderWaKlassen(pruefung) {
    const wunschDetails = pruefung.wunsch_details || {};
    const rows = pruefung.klassen.map(kp => {
        const wunschAmpelClass = `ampel-${kp.wunsch_ampel}`;
        const mitWuenschen = Object.values(wunschDetails).filter(
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

function renderWaSchueler(pruefung) {
    const wunschDetails = pruefung.wunsch_details || {};
    const details = Object.entries(wunschDetails).map(([sid, d]) => ({
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

waFilterLeer.addEventListener("change", () => {
    if (_wunschAnalyseDaten) renderWaSchueler(_wunschAnalyseDaten);
});
waFilterBeidseitig.addEventListener("change", () => {
    if (_wunschAnalyseDaten) renderWaSchueler(_wunschAnalyseDaten);
});

// ==========================================================
// Wunsch-Analyse: Cluster-Ansicht
// ==========================================================

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


// ==========================================================
// Klassenlisten mit Drag & Drop
// ==========================================================

function renderKlassen(klassen, pruefung) {
    const schulhundIdx = pruefung && pruefung.schulhund_klasse_index != null
        ? pruefung.schulhund_klasse_index : null;
    const markierUnbekannte = schulhundIdx !== null;
    klassenGrid.innerHTML = klassen.map((klasse, klassenIdx) => {
        const istSchulhund = schulhundIdx === klassenIdx;
        const klasseCls = istSchulhund ? "klasse-card klasse-schulhund" : "klasse-card";
        const header = istSchulhund
            ? `<span>🐕 Klasse ${klasse.name} <small>(Schulhund)</small></span>`
            : `<span>Klasse ${klasse.name}</span>`;
        return `
        <div class="${klasseCls}" data-klasse-idx="${klassenIdx}">
            <div class="klasse-header">
                ${header}
                <span class="klasse-stats">${klasse.schueler.length} Schüler</span>
            </div>
            <div class="klasse-schueler-list" data-klasse-idx="${klassenIdx}">
                ${klasse.schueler.map(s => schuelerRowHtml(s, markierUnbekannte)).join("")}
            </div>
        </div>
        `;
    }).join("");

    initDragAndDrop();
}

function schuelerRowHtml(s, markierUnbekannte = false) {
    let auffTag = "auffaelligkeit-tag";
    if (s.auffaelligkeit >= 5) auffTag += " sehr-hoch";
    else if (s.auffaelligkeit >= 3) auffTag += " hoch";

    const sprengelHtml = s.sprengel
        ? `<span class="sprengel-badge" title="Sprengel: ${s.sprengel}">${s.sprengel}</span>`
        : "";

    let rowCls = "schueler-row";
    let allergieIcon = "";
    if (s.hundehaarallergie === "ja") {
        rowCls += " schueler-allergie";
        allergieIcon = `<span class="allergie-icon" title="Hundehaarallergie">🐕</span>`;
    } else if (s.hundehaarallergie === "" && markierUnbekannte) {
        rowCls += " schueler-allergie-unbekannt";
        allergieIcon = `<span class="allergie-icon" title="Allergie-Status unbekannt — wird wie Allergie behandelt">🐕❓</span>`;
    }

    return `
        <div class="${rowCls}" draggable="true" data-schueler-id="${s.id}">
            <span class="geschlecht-badge ${s.geschlecht}">${s.geschlecht.toUpperCase()}</span>
            <span class="schueler-name">${s.vorname} ${s.name}</span>
            ${sprengelHtml}
            ${allergieIcon}
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
        renderWunschAnalyse(data.pruefung);

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

        // Warnung bei Schulhund-Verletzungen
        if (data.schulhund_verletzt && data.schulhund_verletzt.length > 0) {
            const namen = data.schulhund_verletzt
                .map(v => `${v.schueler.name} (${v.status === "ja" ? "Allergie" : "ohne Angabe"})`)
                .join(", ");
            alert(
                "⚠️ Schulhund-Klasse:\n\n" + namen +
                "\n\nDiese Schüler sollten nicht in der Schulhund-Klasse sein."
            );
        }

    } catch (err) {
        console.error("Verschiebung fehlgeschlagen:", err);
        if (currentData) {
            renderKlassen(currentData.klassen, currentData.pruefung);
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


// ==========================================================
// Persistenz (Laden, Speichern, Löschen)
// ==========================================================

async function loadAssignments() {
    try {
        const res = await fetch(`${API}/assignments`);
        if (!res.ok) throw new Error("Fehler beim Laden der Einteilungen");

        const data = await res.json();

        if (data.assignments && data.assignments.length > 0) {
            savedAssignmentsSection.classList.remove("hidden");
            savedAssignmentsBody.innerHTML = data.assignments.map(a => {
                const date = new Date(a.timestamp * 1000);
                const dateString = date.toLocaleDateString("de-DE") + " " + date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
                return `
                    <tr>
                        <td><strong>${a.name}</strong></td>
                        <td>${dateString}</td>
                        <td>
                            <div style="display: flex; gap: 5px;">
                                <button class="btn btn-primary" onclick="loadSingleAssignment('${a.id}')" style="padding: 4px 8px; font-size: 0.8rem;">Laden</button>
                                <button class="btn btn-secondary" onclick="deleteAssignment('${a.id}')" style="padding: 4px 8px; font-size: 0.8rem;">Löschen</button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join("");
        } else {
            savedAssignmentsSection.classList.add("hidden");
        }
    } catch (err) {
        console.error("Fehler beim Laden der Einteilungen:", err);
    }
}

// Global verfügbar machen für inline onclick
window.loadSingleAssignment = async function (id) {
    try {
        startBtn.disabled = true;
        exportBtn.disabled = true;
        saveAssignmentBtn.disabled = true;
        dashboard.classList.add("hidden");
        ampelBanner.classList.add("hidden");
        klassenSection.classList.add("hidden");

        const res = await fetch(`${API}/assignments/${id}`);
        if (!res.ok) throw new Error("Fehler beim Laden der Einteilung");

        const data = await res.json();
        currentData = data;

        // Schulhund-Klasse aus gespeichertem Assignment vorbelegen
        aktualisiereSchulhundDropdown();
        if (data.schulhund_klasse !== null && data.schulhund_klasse !== undefined) {
            schulhundKlasse.value = String(data.schulhund_klasse);
        } else {
            schulhundKlasse.value = "";
        }

        if (data.hat_einteilung) {
            renderAlles(data);

            // Verstecke Upload-Feedback
            uploadInfo.classList.add("hidden");
            document.getElementById("mappingSection").classList.add("hidden");
            document.getElementById("schuelerEditSection").classList.add("hidden");

            window.scrollTo({ top: dashboard.offsetTop - 50, behavior: 'smooth' });
        } else {
            // Nur Schülerdaten geladen - zeige den Editor und reaktiviere Start-Button
            schuelerListe = data.schueler || [];
            zeigeSchuelerEditor(schuelerListe, []);

            uploadInfo.classList.add("hidden");
            document.getElementById("mappingSection").classList.add("hidden");
            document.getElementById("schuelerEditSection").classList.remove("hidden");

            startBtn.disabled = false;
            saveAssignmentBtn.disabled = false;

            window.scrollTo({ top: document.getElementById("schuelerEditSection").offsetTop - 50, behavior: 'smooth' });
        }

    } catch (err) {
        alert("Einteilung konnte nicht geladen werden.");
        console.error(err);
    }
};

window.deleteAssignment = async function (id) {
    if (!confirm("Möchten Sie diese Einteilung wirklich löschen?")) return;
    try {
        const res = await fetch(`${API}/assignments/${id}`, { method: "DELETE" });
        if (!res.ok) throw new Error("Fehler beim Löschen");
        loadAssignments();
    } catch (err) {
        alert(err.message);
    }
};

if (saveAssignmentBtn) {
    saveAssignmentBtn.addEventListener("click", () => {
        saveModal.classList.remove("hidden");
        assignmentNameInput.value = "";
        setTimeout(() => assignmentNameInput.focus(), 50);
    });
}

if (cancelSaveBtn) {
    cancelSaveBtn.addEventListener("click", () => {
        saveModal.classList.add("hidden");
    });
}

if (confirmSaveBtn) {
    confirmSaveBtn.addEventListener("click", async () => {
        const name = assignmentNameInput.value.trim();
        if (!name) {
            alert("Bitte einen Namen für die Einteilung eingeben.");
            return;
        }

        try {
            confirmSaveBtn.disabled = true;
            confirmSaveBtn.textContent = "Speichere...";

            const res = await fetch(`${API}/assignments`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name })
            });

            if (!res.ok) throw new Error("Speichern fehlgeschlagen");

            saveModal.classList.add("hidden");
            loadAssignments();

            // UI Feedback
            const originalText = saveAssignmentBtn.innerHTML;
            saveAssignmentBtn.innerHTML = `<span class="icon">✓</span> Gespeichert`;
            saveAssignmentBtn.classList.remove("btn-info");
            saveAssignmentBtn.classList.add("btn-success");
            setTimeout(() => {
                saveAssignmentBtn.innerHTML = originalText;
                saveAssignmentBtn.classList.remove("btn-success");
                saveAssignmentBtn.classList.add("btn-info");
            }, 2000);

        } catch (err) {
            alert(err.message);
        } finally {
            confirmSaveBtn.disabled = false;
            confirmSaveBtn.textContent = "Speichern";
        }
    });
}

// Lade Einteilungen beim Start
document.addEventListener("DOMContentLoaded", loadAssignments);
