/**
 * Klasseneinteilung Web-App – Frontend mit Drag & Drop
 */

const API = "/api";

// --- Aktueller App-State ---
let currentData = null; // Komplette Antwort von /optimierung oder /verschieben

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

// --- Upload ---
uploadBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;

    fileName.textContent = file.name;
    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch(`${API}/upload`, { method: "POST", body: formData });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Upload fehlgeschlagen");
        }
        const data = await res.json();
        uploadInfo.textContent = `${data.anzahl_schueler} Schüler eingelesen | ${data.wunsch_spalten} Wunschspalten | Trennung: ${data.hat_trennung ? "Ja" : "Nein"}`;
        uploadInfo.classList.remove("hidden");
        startBtn.disabled = false;
    } catch (err) {
        alert("Fehler beim Upload: " + err.message);
    }
});

// --- Optimierung starten ---
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
        }, 500);

    } catch (err) {
        clearInterval(progressInterval);
        progressContainer.classList.add("hidden");
        alert("Fehler: " + err.message);
    } finally {
        startBtn.disabled = false;
    }
});

// --- Export ---
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

    // Drag & Drop Events registrieren
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

    // Gleiche Klasse = nichts tun
    if (targetKlasseIdx === sourceKlasseIdx) return;

    // Sofort im UI verschieben (optimistisch)
    if (draggedElement) {
        targetZone.appendChild(draggedElement);
        draggedElement.classList.remove("dragging");
    }

    // Neue Einteilung aus dem DOM auslesen
    const neueEinteilung = bauEinteilungAusDOM();

    // An Backend senden und Prüfung aktualisieren
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

        // Dashboard aktualisieren (ohne Klassen neu zu rendern – die sind ja schon verschoben)
        renderAmpel(data.pruefung);
        renderSummary(data.pruefung);
        renderPruefungTabelle(data.pruefung);
        renderWuensche(data.pruefung);

        // Klassen-Header aktualisieren (Schüleranzahl)
        data.klassen.forEach((klasse, idx) => {
            const card = document.querySelector(`.klasse-card[data-klasse-idx="${idx}"]`);
            if (card) {
                const stats = card.querySelector(".klasse-stats");
                if (stats) stats.textContent = `${klasse.schueler.length} Schüler`;
            }
        });

    } catch (err) {
        console.error("Verschiebung fehlgeschlagen:", err);
        // Bei Fehler: komplett neu rendern aus letztem guten State
        if (currentData) {
            renderKlassen(currentData.klassen);
        }
    }
}
