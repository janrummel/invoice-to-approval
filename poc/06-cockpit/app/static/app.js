/* Freigabe-Cockpit Stufe B — Vanilla-JS-Frontend gegen den FastAPI-Proxy. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const state = {
  view: "posteingang",
  queue: null,          // null = lädt noch (Skeleton), [] = leer
  history: null,
  mining: null,
  error: null,
  search: "",
  segment: "ALLE",      // ALLE | SACHBEARBEITER | TEAMLEITUNG
  sort: "erstellt",     // erstellt | brutto | risk
  activeRow: -1,        // Tastatur-Cursor in der aktuellen Liste
  drawer: null,         // { item, mode: "queue"|"history", tab }
};

/* ── Formatierung ──────────────────────────────────────────────────────── */

const deBetrag = (v, dec = 2) =>
  Number(v).toLocaleString("de-DE", { minimumFractionDigits: dec, maximumFractionDigits: dec });

function relTime(iso) {
  if (!iso) return "—";
  const s = Math.round((Date.now() - new Date(iso)) / 1000);
  if (s < 60) return "gerade eben";
  if (s < 3600) return `vor ${Math.floor(s / 60)} min`;
  if (s < 86400) return `vor ${Math.floor(s / 3600)} h`;
  return `vor ${Math.floor(s / 86400)} d`;
}
const absTime = (iso) => iso ? new Date(iso).toLocaleString("de-DE") : "—";

const STATUS_CHIP = {
  gebucht:   ["good", "✓", "gebucht"],
  abgelehnt: ["critical", "✕", "abgelehnt"],
  offen:     ["warning", "⚠", "offen"],
  beendet:   ["neutral", "·", "beendet"],
};
const ROUTE_CHIP = {
  AUTO_POST: ["good", "✓", "Auto-gebucht"],
  REVIEW:    ["warning", "⚠", "Prüfung"],
  REJECT:    ["critical", "✕", "Abgewiesen"],
};
const chip = ([role, icon, label]) =>
  `<span class="chip chip-${role}"><span aria-hidden="true">${icon}</span>${esc(label)}</span>`;

const copyBtn = (text) =>
  `<button class="copy-btn" data-copy="${esc(text)}" title="Kopieren" aria-label="„${esc(text)}“ kopieren">⧉</button>`;

/* ── API ───────────────────────────────────────────────────────────────── */

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

async function loadData() {
  state.error = null;
  try {
    const [queue, history] = await Promise.all([api("/api/queue"), api("/api/history")]);
    state.queue = queue;
    state.history = history;
    if (!state.mining) state.mining = await api("/api/mining");
    $("#engine-dot").dataset.state = "ok";
  } catch (e) {
    state.error = e.message;
    $("#engine-dot").dataset.state = "down";
  }
  render();
}

/* ── Navigation / Shell ────────────────────────────────────────────────── */

const TITLES = {
  posteingang: "Posteingang", freigaben: "Freigaben",
  auswertung: "Auswertung", audit: "Audit",
};

function navigate() {
  const view = (location.hash.replace("#/", "") || "posteingang");
  state.view = TITLES[view] ? view : "posteingang";
  state.activeRow = -1;
  closeDrawer();
  render();
}

function render() {
  $("#view-title").textContent = TITLES[state.view];
  document.querySelectorAll(".nav-item").forEach((a) =>
    a.dataset.view === state.view
      ? a.setAttribute("aria-current", "page")
      : a.removeAttribute("aria-current"));
  const n = state.queue?.length ?? 0;
  const badge = $("#badge-queue");
  badge.hidden = n === 0;
  badge.textContent = n;

  const main = $("#main");
  if (state.error) { main.innerHTML = errorView(); return; }
  main.innerHTML = { posteingang: inboxView, freigaben: decidedView,
                     auswertung: statsView, audit: auditView }[state.view]();
  highlightActiveRow();
}

function errorView() {
  return `<div class="error-card">
    <b>Engine nicht erreichbar</b>
    <p>${esc(state.error)}</p>
    <button class="btn" onclick="reload()">Erneut versuchen</button>
  </div>`;
}

function skeleton(cols) {
  return Array.from({ length: 4 }, () =>
    `<tr class="skeleton-row">${'<td><div class="skeleton-bar"></div></td>'.repeat(cols)}</tr>`).join("");
}

function emptyState(glyph, text, hint = "") {
  return `<div class="empty"><span class="glyph" aria-hidden="true">${glyph}</span>
    ${esc(text)}${hint ? `<div class="hint">${esc(hint)}</div>` : ""}</div>`;
}

/* ── Posteingang (Arbeitsliste) ────────────────────────────────────────── */

function filteredQueue() {
  let rows = state.queue ?? [];
  if (state.segment !== "ALLE") rows = rows.filter((r) => r.stufe === state.segment);
  if (state.search) {
    const q = state.search.toLowerCase();
    rows = rows.filter((r) =>
      [r.rechnung, r.beleg, ...(r.gruende || [])].join(" ").toLowerCase().includes(q));
  }
  const key = { erstellt: (r) => r.erstellt, brutto: (r) => -r.brutto, risk: (r) => -r.riskScore }[state.sort];
  return [...rows].sort((a, b) => (key(a) > key(b) ? 1 : -1));
}

function inboxView() {
  const loading = state.queue === null;
  const rows = filteredQueue();
  const counts = (s) => (state.queue ?? []).filter((r) => s === "ALLE" || r.stufe === s).length;
  const seg = (val, label) =>
    `<button aria-pressed="${state.segment === val}" data-segment="${val}">${label} (${counts(val)})</button>`;

  const body = loading ? skeleton(6)
    : rows.length === 0
      ? `<tr><td colspan="6">${state.queue.length === 0
          ? emptyState("✓", "Posteingang leer — alle Freigaben erledigt.",
                       "Neuer Demo-Lauf: uv run seed.py")
          : emptyState("⌕", "Keine Treffer für diese Ansicht.",
                       "Filter oder Suche zurücksetzen.")}</td></tr>`
      : rows.map((r, i) => `
        <tr class="row" data-idx="${i}" data-kind="queue" tabindex="0" role="button"
            aria-label="Beleg ${esc(r.rechnung)} öffnen">
          <td><span class="mono">${esc(r.rechnung)}</span>${copyBtn(r.rechnung)}
              <span class="row-sub mono">${esc(r.beleg)}</span></td>
          <td class="num">${deBetrag(r.brutto)}&nbsp;€</td>
          <td class="num">${r.riskScore}</td>
          <td>${chip(r.stufe === "TEAMLEITUNG"
                ? ["warning", "▲", "Teamleitung"] : ["neutral", "●", "Sachbearbeiter"])}</td>
          <td title="${absTime(r.erstellt)}">${relTime(r.erstellt)}</td>
          <td class="row-action">Enter ↵ öffnen</td>
        </tr>`).join("");

  return `
  <div class="toolbar">
    <div class="search"><input id="search" type="search" placeholder="Beleg, Datei oder Grund suchen"
         value="${esc(state.search)}" aria-label="Suche"><kbd>/</kbd></div>
    <div class="segments" role="group" aria-label="Nach Freigabestufe filtern">
      ${seg("ALLE", "Alle")}${seg("SACHBEARBEITER", "Sachbearbeiter")}${seg("TEAMLEITUNG", "Teamleitung")}
    </div>
    <select id="sort" aria-label="Sortierung">
      <option value="erstellt"${state.sort === "erstellt" ? " selected" : ""}>Eingang (älteste zuerst)</option>
      <option value="brutto"${state.sort === "brutto" ? " selected" : ""}>Betrag (höchste zuerst)</option>
      <option value="risk"${state.sort === "risk" ? " selected" : ""}>Risk (höchste zuerst)</option>
    </select>
  </div>
  <section class="card">
    <table>
      <thead><tr><th>Beleg</th><th class="num">Brutto</th><th class="num">Risk</th>
        <th>Stufe</th><th>Eingang</th><th></th></tr></thead>
      <tbody>${body}</tbody>
    </table>
  </section>`;
}

/* ── Freigaben (entschiedene Vorgänge) ─────────────────────────────────── */

function decidedList() {
  return (state.history ?? []).filter((h) => h.status === "gebucht" || h.status === "abgelehnt");
}

function decidedView() {
  const loading = state.history === null;
  const rows = decidedList();
  const body = loading ? skeleton(6)
    : rows.length === 0
      ? `<tr><td colspan="6">${emptyState("···", "Noch keine Entscheidungen in diesem Lauf.")}</td></tr>`
      : rows.map((h, i) => `
        <tr class="row" data-idx="${i}" data-kind="history" tabindex="0" role="button"
            aria-label="Vorgang ${esc(h.rechnung)} öffnen">
          <td><span class="mono">${esc(h.rechnung)}</span>${copyBtn(h.rechnung)}</td>
          <td class="num">${deBetrag(h.brutto)}&nbsp;€</td>
          <td>${esc(h.stufe ?? "—")}</td>
          <td>${h.entschiedenVon ? esc(h.entschiedenVon) : "— <span class='row-sub'>(automatisch)</span>"}</td>
          <td>${chip(STATUS_CHIP[h.status])}</td>
          <td title="${absTime(h.beendet)}">${relTime(h.beendet)}</td>
        </tr>`).join("");

  return `<section class="card">
    <table>
      <thead><tr><th>Beleg</th><th class="num">Brutto</th><th>DMN-Stufe</th>
        <th>Entscheider</th><th>Ergebnis</th><th>Abgeschlossen</th></tr></thead>
      <tbody>${body}</tbody>
    </table>
  </section>`;
}

/* ── Auswertung (Live-KPIs + Mining) ───────────────────────────────────── */

function statsView() {
  const h = state.history ?? [];
  const done = h.filter((x) => x.status !== "offen");
  const auto = done.filter((x) => !x.entschiedenVon).length;
  const offen = state.queue?.length ?? 0;
  const summe = h.reduce((s, x) => s + (x.brutto || 0), 0);
  const m = state.mining;

  const bars = (items, valueKey, unit, max) => items.map((v) => `
    <div class="bar-row" title="${esc(v.name)}: ${v[valueKey]} ${unit}">
      <span class="bar-label">${esc(v.name)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${(v[valueKey] / max) * 100}%"></span></span>
      <span class="bar-value">${String(v[valueKey]).replace(".", ",")}&nbsp;${unit}</span>
    </div>`).join("");

  const mining = !m ? "" : `
  <section class="card">
    <h2>Warum automatisieren? Befunde aus dem Process Mining (POC 01)</h2>
    <div class="mining-grid">
      <div>
        <p class="chart-sub">Ø Durchlaufzeit je Prozessvariante</p>
        ${bars([...m.varianten].sort((a, b) => b.dauer - a.dauer), "dauer", "d",
               Math.max(...m.varianten.map((v) => v.dauer)))}
        <p class="befund">Abweichungsfälle laufen <strong>${m.kpi.faktor.replace(".", ",")}× länger</strong>
          als der Happy Path — die Liegezeiten entstehen vor manuellen Klärungs- und Freigabeschritten.</p>
      </div>
      <div>
        <p class="chart-sub">Manuelle Touches — gebundene Stunden/Monat</p>
        ${bars([...m.touches].sort((a, b) => b.stunden - a.stunden), "stunden", "h/M",
               Math.max(...m.touches.map((t) => t.stunden)))}
        <p class="befund">Datenbasis: ${m.kpi.events} Events, ${m.kpi.cases} Vorgänge (synthetisch).
          Top-Hebel: Rechnungserfassung (E-Rechnung/IDP) und Abweichungsklärung (Assistent + HITL, POC 05).</p>
      </div>
    </div>
  </section>`;

  return `
  <div class="kpis">
    <div class="kpi"><b>${h.length}</b><span>Belege im Lauf (${deBetrag(summe, 0)} € brutto)</span></div>
    <div class="kpi"><b>${offen}</b><span>offene Freigabe-Tasks in der Flowable-Queue</span></div>
    <div class="kpi"><b>${auto} von ${done.length || "–"}</b><span>abgeschlossen ohne menschlichen Touch</span></div>
    <div class="kpi"><b>~${m ? m.kpi.fte.replace(".", ",") : "–"} FTE</b><span>gebundene Kapazität laut Mining (${m ? m.kpi.touchAnteil : "–"} % manuelle Touches)</span></div>
  </div>
  ${mining}`;
}

/* ── Audit (alle Instanzen mit Prozesspfad) ────────────────────────────── */

function auditView() {
  const loading = state.history === null;
  const rows = state.history ?? [];
  const body = loading ? skeleton(6)
    : rows.length === 0
      ? `<tr><td colspan="6">${emptyState("≡", "Keine Prozessinstanzen — Demo-Lauf starten.",
                                          "uv run seed.py")}</td></tr>`
      : rows.map((h, i) => `
        <tr class="row" data-idx="${i}" data-kind="audit" tabindex="0" role="button"
            aria-label="Audit-Trail ${esc(h.rechnung)} öffnen">
          <td><span class="mono">${esc(h.rechnung)}</span>
              <span class="row-sub mono">${esc(h.beleg)}</span></td>
          <td>${chip(ROUTE_CHIP[h.route] ?? ["neutral", "·", h.route])}</td>
          <td>${chip(STATUS_CHIP[h.status])}</td>
          <td class="num">${h.pfad.length}</td>
          <td title="${absTime(h.gestartet)}">${relTime(h.gestartet)}</td>
          <td class="row-action">Enter ↵ Audit-Trail</td>
        </tr>`).join("");

  return `<section class="card">
    <table>
      <thead><tr><th>Beleg</th><th>Pipeline-Routing</th><th>Status</th>
        <th class="num">Schritte</th><th>Gestartet</th><th></th></tr></thead>
      <tbody>${body}</tbody>
    </table>
  </section>`;
}

/* ── Drawer ────────────────────────────────────────────────────────────── */

function listForKind(kind) {
  return { queue: filteredQueue(), history: decidedList(), audit: state.history ?? [] }[kind];
}

function openDrawer(kind, idx, tab) {
  const item = listForKind(kind)[idx];
  if (!item) return;
  state.drawer = { kind, item, tab: tab ?? (kind === "audit" ? "prozess" : "beleg") };
  renderDrawer();
}

function closeDrawer(refocus = false) {
  if (!state.drawer) return;
  state.drawer = null;
  $("#drawer").hidden = true;
  $("#drawer").classList.remove("open");
  $("#drawer-backdrop").hidden = true;
  if (refocus) highlightActiveRow(true);
}

function historyOf(item) {
  return (state.history ?? []).find((h) => h.beleg === item.beleg);
}

function renderDrawer() {
  const { kind, item, tab } = state.drawer;
  const isTask = kind === "queue";
  const hist = historyOf(item);

  const tabBtn = (id, label) =>
    `<button role="tab" aria-selected="${tab === id}" data-tab="${id}">${label}</button>`;

  const beleg = `<dl class="field">
      <dt>Belegnummer</dt><dd><span class="mono">${esc(item.rechnung)}</span>${copyBtn(item.rechnung)}</dd>
      <dt>Quelldatei</dt><dd><span class="mono">${esc(item.beleg)}</span>${copyBtn(item.beleg)}</dd>
      <dt>Brutto</dt><dd>${deBetrag(item.brutto)} ${esc(item.waehrung)}</dd>
      <dt>Pipeline-Routing</dt><dd>${chip(ROUTE_CHIP[item.route] ?? ["neutral", "·", item.route])}</dd>
      <dt>Risk-Score</dt><dd>${item.riskScore}</dd>
      <dt>DMN-Stufe</dt><dd>${esc(item.stufe ?? "—")}${isTask ? ` <span class="row-sub">zuständig: ${esc(item.rolle)}</span>` : ""}</dd>
    </dl>`;

  const pruefungen = `
    ${(item.gruende ?? []).map((g) => `<div class="finding"><b>Routing-Grund:</b> ${esc(g)}</div>`).join("")}
    ${(item.findings ?? []).map((f) => `
      <div class="finding" data-severity="${esc(f.severity)}">
        <span class="mono">${esc(f.code)} · ${esc(f.severity)}</span><br>${esc(f.message)}
      </div>`).join("")}
    ${!(item.gruende?.length || item.findings?.length)
      ? emptyState("✓", "Keine Auffälligkeiten — alle Prüfungen bestanden.") : ""}`;

  const steps = hist?.pfad ?? [];
  const prozess = steps.length === 0
    ? emptyState("···", "Noch kein Audit-Trail verfügbar.")
    : steps.map((s, i) => `
      <div class="step">
        <div class="dot-col"><span class="dot"></span>${i < steps.length - 1 ? '<span class="stem"></span>' : ""}</div>
        <div class="body"><b>${esc(s.schritt)}</b> <span class="row-sub">${esc(s.typ)}</span>
          <div class="when">${absTime(s.start)}${s.bearbeiter ? ` · ${esc(s.bearbeiter)}` : ""}</div>
        </div>
      </div>`).join("")
      + (hist?.kommentar ? `<div class="kommentar-box"><b>Entscheidung
          ${hist.entschiedenVon ? `(${esc(hist.entschiedenVon)})` : ""}:</b> ${esc(hist.kommentar)}</div>` : "");

  const foot = isTask ? `
    <div class="drawer-foot">
      <textarea id="comment" placeholder="Kommentar zur Entscheidung (bei Ablehnung Pflicht — Audit-Trail)"
        aria-label="Kommentar zur Entscheidung"></textarea>
      <div class="actions">
        <button class="btn btn-critical" data-decide="reject">✕ Ablehnen</button>
        <button class="btn btn-good" data-decide="approve">✓ Freigeben</button>
      </div>
    </div>` : "";

  const el = $("#drawer");
  el.innerHTML = `
    <div class="drawer-head">
      <div class="top">
        <h2 id="drawer-title"><span class="mono">${esc(item.rechnung)}</span></h2>
        ${chip(isTask ? ["warning", "⚠", "wartet auf Freigabe"] : STATUS_CHIP[item.status] ?? ["neutral", "·", "—"])}
        <button class="icon-btn" data-close title="Schließen (Esc)" aria-label="Schließen">✕</button>
      </div>
      <p class="sub">${deBetrag(item.brutto)} € · ${esc(item.beleg)}</p>
      <div class="tabs" role="tablist">
        ${tabBtn("beleg", "Beleg")}${tabBtn("pruefungen", "Prüfungen")}${tabBtn("prozess", "Prozess / Audit")}
      </div>
    </div>
    <div class="drawer-body" role="tabpanel">
      ${{ beleg, pruefungen, prozess }[tab]}
    </div>
    ${foot}`;

  el.hidden = false;
  $("#drawer-backdrop").hidden = false;
  requestAnimationFrame(() => el.classList.add("open"));
  el.querySelector("[data-tab][aria-selected='true']")?.focus();
}

/* ── Entscheidung (Freigeben / Ablehnen) ───────────────────────────────── */

async function decide(approved) {
  const { item } = state.drawer;
  const comment = $("#comment").value.trim();
  if (!approved && !comment) {
    toast("Ablehnung braucht einen Kommentar (Audit-Pflicht).", "critical");
    $("#comment").focus();
    return;
  }
  try {
    const res = await api(`/api/tasks/${item.taskId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved, comment }),
    });
    toast(`${res.rechnung} ${approved ? "freigegeben" : "abgelehnt"} (${res.entschiedenVon})`);
    closeDrawer();
    await loadData();
  } catch (e) {
    toast(e.message, "critical");
  }
}

function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  $("#toast-wrap").append(el);
  setTimeout(() => el.remove(), 3200);
}

/* ── Tastatur + Events ─────────────────────────────────────────────────── */

function visibleRows() {
  return [...document.querySelectorAll("#main tr.row")];
}

function highlightActiveRow(focus = false) {
  const rows = visibleRows();
  rows.forEach((r, i) => r.classList.toggle("is-active", i === state.activeRow));
  if (focus && rows[state.activeRow]) rows[state.activeRow].focus();
}

function moveCursor(delta) {
  const rows = visibleRows();
  if (!rows.length) return;
  state.activeRow = Math.min(rows.length - 1, Math.max(0, state.activeRow + delta));
  rows[state.activeRow].scrollIntoView({ block: "nearest" });
  highlightActiveRow(true);
}

document.addEventListener("keydown", (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
  if (e.key === "Escape") { closeDrawer(true); return; }
  if (state.drawer || typing) return;
  if (e.key === "/") { e.preventDefault(); $("#search")?.focus(); }
  else if (e.key === "ArrowDown") { e.preventDefault(); moveCursor(1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); moveCursor(-1); }
  else if (e.key === "Enter") {
    const row = visibleRows()[state.activeRow];
    if (row) openDrawer(row.dataset.kind, Number(row.dataset.idx));
  }
});

document.addEventListener("click", (e) => {
  const t = e.target;
  const copy = t.closest("[data-copy]");
  if (copy) {
    navigator.clipboard.writeText(copy.dataset.copy).then(() => toast(`„${copy.dataset.copy}“ kopiert`));
    e.stopPropagation();
    return;
  }
  const row = t.closest("tr.row");
  if (row) {
    state.activeRow = visibleRows().indexOf(row);
    highlightActiveRow();
    openDrawer(row.dataset.kind, Number(row.dataset.idx));
    return;
  }
  if (t.closest("[data-close]") || t.id === "drawer-backdrop") { closeDrawer(true); return; }
  const tab = t.closest("[data-tab]");
  if (tab && state.drawer) { state.drawer.tab = tab.dataset.tab; renderDrawer(); return; }
  const decideBtn = t.closest("[data-decide]");
  if (decideBtn) { decide(decideBtn.dataset.decide === "approve"); return; }
  const seg = t.closest("[data-segment]");
  if (seg) { state.segment = seg.dataset.segment; state.activeRow = -1; render(); }
});

document.addEventListener("input", (e) => {
  if (e.target.id === "search") {
    state.search = e.target.value;
    state.activeRow = -1;
    const pos = e.target.selectionStart;
    render();
    const input = $("#search");
    input.focus();
    input.setSelectionRange(pos, pos);
  }
});
document.addEventListener("change", (e) => {
  if (e.target.id === "sort") { state.sort = e.target.value; render(); }
});

/* ── Theme ─────────────────────────────────────────────────────────────── */

$("#theme-toggle").addEventListener("click", () => {
  const cur = document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("cockpit-theme", next);
});
const savedTheme = localStorage.getItem("cockpit-theme");
if (savedTheme) document.documentElement.dataset.theme = savedTheme;

/* ── Start ─────────────────────────────────────────────────────────────── */

function reload() { state.queue = state.history = null; render(); loadData(); }
window.reload = reload;

window.addEventListener("hashchange", navigate);
navigate();
loadData();
setInterval(() => { if (!state.drawer && !state.error) loadData(); }, 15000);
