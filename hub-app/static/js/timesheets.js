// Section "Suivi de temps" du hub — SPA vanilla JS consommant /api/timesheets
// et /api/admin/users, mêmes conventions que app.js (pas de framework, pas de
// build step). Monté dans #suiviTempsPlaceholder par app.js::setActiveSection.

window.TimesheetsUI = (() => {
  let stRoot = null;
  let stView = "weeks"; // "weeks" | "detail" | "weekly-summary" | "admin"
  let stCurrentId = null; // id de la feuille de temps en édition, null = création

  function mount(root) {
    stRoot = root;
    render();
  }

  function render() {
    if (!stRoot) return;
    let p;
    try {
      if (stView === "weeks") p = renderWeeks();
      else if (stView === "detail") p = renderDetail(stCurrentId);
      else if (stView === "weekly-summary") p = renderWeeklySummary();
      else if (stView === "admin") p = renderAdmin();
    } catch (err) {
      showError(err);
      return;
    }
    if (p && typeof p.catch === "function") p.catch(showError);
  }

  function showError(err) {
    console.error("TimesheetsUI:", err);
    if (stRoot) {
      stRoot.innerHTML = `<div class="empty-hint">Erreur d'affichage : ${escapeHtml(String((err && err.message) || err))}</div>`;
    }
  }

  function goTo(view, id = null) {
    stView = view;
    stCurrentId = id;
    render();
  }

  function fmtDate(iso) {
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
  }

  function fmtHM(h, m) {
    return m > 0 ? `${h}h ${m}min` : `${h}h`;
  }

  // ---------- Toolbar commune ----------

  function renderToolbar() {
    const isSuperuser = !!(window.currentUser && window.currentUser.is_superuser);
    return `
      <div class="st-toolbar">
        <button class="ghost-btn" id="stNewBtn">+ Nouvelle feuille de temps</button>
        <button class="ghost-btn" id="stSummaryBtn">Résumé hebdomadaire</button>
        <span class="spacer"></span>
        ${isSuperuser ? `<button class="ghost-btn" id="stAdminBtn">Administration</button>` : ""}
      </div>
    `;
  }

  function wireToolbar() {
    stRoot.querySelector("#stNewBtn")?.addEventListener("click", () => goTo("detail", null));
    stRoot.querySelector("#stSummaryBtn")?.addEventListener("click", () => goTo("weekly-summary"));
    stRoot.querySelector("#stAdminBtn")?.addEventListener("click", () => goTo("admin"));
  }

  // ---------- Vue liste (semaines) ----------

  async function renderWeeks() {
    stRoot.innerHTML = renderToolbar() + `<div id="stWeeksList"></div>`;
    wireToolbar();

    const listEl = stRoot.querySelector("#stWeeksList");
    let data;
    try {
      data = await api("/api/timesheets");
    } catch {
      listEl.innerHTML = `<div class="empty-hint">Impossible de charger les feuilles de temps.</div>`;
      return;
    }

    if (!data.weeks.length) {
      listEl.innerHTML = `<div class="empty-hint">Aucune feuille de temps pour l'instant. Clique sur "+ Nouvelle feuille de temps" pour commencer.</div>`;
      return;
    }

    listEl.innerHTML = data.weeks.map((week) => `
      <div class="week-card">
        <div class="week-card-header">
          <span class="week-range">Semaine du ${fmtDate(week.monday)} au ${fmtDate(week.sunday)}</span>
          <span class="week-total">${fmtHM(week.total_hours, week.total_minutes)}</span>
          <a class="ghost-btn" href="/api/timesheets/report/pdf/${week.monday}">PDF</a>
          <a class="ghost-btn" href="/api/timesheets/report/word/${week.monday}">Word</a>
        </div>
        <div class="week-card-body">
          ${week.timesheets.map((ts) => `
            <div class="timesheet-row" data-id="${ts.id}">
              <span class="ts-date">${fmtDate(ts.date)}</span>
              <span class="ts-meta">${ts.entries.length} entrée${ts.entries.length > 1 ? "s" : ""}</span>
              <span class="ts-total">${fmtHM(ts.total_hours, ts.total_minutes)}</span>
            </div>
          `).join("")}
        </div>
      </div>
    `).join("");

    listEl.querySelectorAll(".timesheet-row").forEach((row) => {
      row.addEventListener("click", () => goTo("detail", Number(row.dataset.id)));
    });
  }

  // ---------- Vue détail / édition ----------

  async function renderDetail(id) {
    let ts = null;
    if (id) {
      try {
        ts = await api(`/api/timesheets/${id}`);
      } catch {
        stRoot.innerHTML = `<div class="empty-hint">Feuille de temps introuvable.</div>`;
        return;
      }
    }

    const today = new Date().toISOString().slice(0, 10);

    stRoot.innerHTML = `
      <div class="st-toolbar">
        <button class="ghost-btn" id="stBackBtn">&larr; Retour</button>
      </div>
      <h3>${id ? "Modifier la feuille de temps" : "Nouvelle feuille de temps"}</h3>
      <div class="st-form-row">
        <label>Date <input type="date" id="stDate" value="${ts ? ts.date : today}" /></label>
      </div>
      <div class="st-form-row">
        <label style="flex:1">Résumé <textarea id="stSummary" rows="3">${ts ? escapeHtml(ts.summary) : ""}</textarea></label>
      </div>
      <div id="stEntries" class="entries-list"></div>
      <button class="add-task-btn" id="stAddEntryBtn">+ Ajouter une entrée</button>
      <div class="st-toolbar" style="margin-top:18px">
        <button class="primary-btn" id="stSaveBtn">Enregistrer</button>
        ${id ? `<button class="danger-btn" id="stDeleteBtn">Supprimer</button>` : ""}
      </div>
    `;

    const entriesEl = stRoot.querySelector("#stEntries");

    function addEntryRow(entryId, startTime, endTime) {
      const row = document.createElement("div");
      row.className = "entry-row";
      if (entryId) row.dataset.entryId = entryId;
      row.innerHTML = `
        <input type="time" class="entry-start" value="${startTime || ""}" />
        <span>&ndash;</span>
        <input type="time" class="entry-end" value="${endTime || ""}" />
        <button class="remove-entry-btn" title="Supprimer">🗑</button>
      `;
      row.querySelector(".remove-entry-btn").addEventListener("click", () => {
        if (row.dataset.entryId) {
          row.dataset.deleted = "true";
          row.hidden = true;
        } else {
          row.remove();
        }
      });
      entriesEl.appendChild(row);
    }

    if (ts) {
      for (const entry of ts.entries) addEntryRow(entry.id, entry.start_time, entry.end_time);
    }
    if (!ts) addEntryRow(null, "", "");

    stRoot.querySelector("#stAddEntryBtn").addEventListener("click", () => addEntryRow(null, "", ""));
    stRoot.querySelector("#stBackBtn").addEventListener("click", () => goTo("weeks"));

    stRoot.querySelector("#stSaveBtn").addEventListener("click", async () => {
      const date = stRoot.querySelector("#stDate").value;
      const summary = stRoot.querySelector("#stSummary").value;
      if (!date) return;

      const rows = [...entriesEl.querySelectorAll(".entry-row")];
      const entries = [];
      for (const row of rows) {
        const start = row.querySelector(".entry-start").value;
        const end = row.querySelector(".entry-end").value;
        if (row.dataset.entryId) {
          if (row.dataset.deleted === "true") {
            entries.push({ id: Number(row.dataset.entryId), delete: true });
          } else if (start && end) {
            entries.push({ id: Number(row.dataset.entryId), start_time: start, end_time: end });
          }
        } else if (start && end) {
          entries.push({ start_time: start, end_time: end });
        }
      }

      try {
        if (id) {
          await api(`/api/timesheets/${id}`, {
            method: "PATCH",
            body: JSON.stringify({ date, summary, entries }),
          });
        } else {
          await api("/api/timesheets", {
            method: "POST",
            body: JSON.stringify({ date, summary, entries }),
          });
        }
        goTo("weeks");
      } catch (e) {
        alert("Erreur lors de l'enregistrement — vérifie qu'il n'existe pas déjà une feuille de temps pour cette date.");
      }
    });

    stRoot.querySelector("#stDeleteBtn")?.addEventListener("click", async () => {
      if (!confirm("Supprimer cette feuille de temps ?")) return;
      await api(`/api/timesheets/${id}`, { method: "DELETE" });
      goTo("weeks");
    });
  }

  // ---------- Vue résumé hebdomadaire ----------

  async function renderWeeklySummary() {
    stRoot.innerHTML = `
      <div class="st-toolbar">
        <button class="ghost-btn" id="stBackBtn">&larr; Retour</button>
      </div>
      <div id="stSummaryTable"></div>
    `;
    stRoot.querySelector("#stBackBtn").addEventListener("click", () => goTo("weeks"));

    const { summaries } = await api("/api/timesheets/weekly-summary");
    const tableEl = stRoot.querySelector("#stSummaryTable");

    if (!summaries.length) {
      tableEl.innerHTML = `<div class="empty-hint">Aucune donnée pour l'instant.</div>`;
      return;
    }

    tableEl.innerHTML = `
      <table class="summary-table">
        <thead><tr><th>Semaine</th><th>Jours</th><th>Total</th></tr></thead>
        <tbody>
          ${summaries.map((s) => `
            <tr>
              <td>${fmtDate(s.monday_date)} &ndash; ${fmtDate(s.sunday_date)}</td>
              <td>${s.timesheet_count}</td>
              <td>${fmtHM(s.total_hours, s.total_minutes)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  // ---------- Vue admin (superuser) ----------

  async function renderAdmin() {
    stRoot.innerHTML = `
      <div class="st-toolbar">
        <button class="ghost-btn" id="stBackBtn">&larr; Retour</button>
        <span class="spacer"></span>
        <button class="ghost-btn" id="stNewUserBtn">+ Nouvel utilisateur</button>
      </div>
      <div id="stUsersTable"></div>
    `;
    stRoot.querySelector("#stBackBtn").addEventListener("click", () => goTo("weeks"));
    stRoot.querySelector("#stNewUserBtn").addEventListener("click", openUserModal);

    await loadUsersTable();
  }

  async function loadUsersTable() {
    const tableEl = stRoot.querySelector("#stUsersTable");
    let users;
    try {
      users = await api("/api/admin/users");
    } catch {
      tableEl.innerHTML = `<div class="empty-hint">Accès refusé ou erreur de chargement.</div>`;
      return;
    }

    tableEl.innerHTML = `
      <table class="summary-table">
        <thead><tr><th>Email</th><th>Nom</th><th>Admin</th></tr></thead>
        <tbody>
          ${users.map((u) => `
            <tr>
              <td>${escapeHtml(u.email)}</td>
              <td>${escapeHtml(u.first_name)} ${escapeHtml(u.last_name)}</td>
              <td>${u.is_superuser ? "✓" : ""}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  function openUserModal() {
    modalRoot.innerHTML = `
      <div class="modal-overlay">
        <div class="modal">
          <h2>Nouvel utilisateur</h2>
          <input id="uEmail" placeholder="Email" type="email" />
          <input id="uFirstName" placeholder="Prénom" />
          <input id="uLastName" placeholder="Nom" />
          <label style="display:flex;align-items:center;gap:8px;font-size:0.85rem;color:var(--muted);">
            <input id="uSuperuser" type="checkbox" style="width:auto;" /> Administrateur
          </label>
          <div class="modal-actions">
            <button class="cancel-btn" id="uCancel">Annuler</button>
            <button class="primary-btn" id="uSave">Créer</button>
          </div>
        </div>
      </div>
    `;
    document.getElementById("uCancel").onclick = closeModal;
    document.getElementById("uSave").onclick = async () => {
      const email = document.getElementById("uEmail").value.trim();
      if (!email) return;
      try {
        await api("/api/admin/users", {
          method: "POST",
          body: JSON.stringify({
            email,
            first_name: document.getElementById("uFirstName").value.trim(),
            last_name: document.getElementById("uLastName").value.trim(),
            is_superuser: document.getElementById("uSuperuser").checked,
          }),
        });
        closeModal();
        loadUsersTable();
      } catch {
        alert("Erreur — un compte existe peut-être déjà avec cet email.");
      }
    };
  }

  return { mount };
})();
