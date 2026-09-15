// Section "Recette" du hub — SPA vanilla JS consommant /api/recipes, mêmes
// conventions que app.js/timesheets.js. Monté dans #recipesPlaceholder par
// app.js::setActiveSection.

window.RecipesUI = (() => {
  let rRoot = null;
  let rView = "list"; // "list" | "detail" | "form" | "paste" | "revisions" | "revision"
  let rCurrentId = null;
  let rCurrentRevisionId = null;
  let rAllRecipes = []; // cache pour le filtre de recherche côté client
  let rSearchTerm = "";

  function mount(root) {
    rRoot = root;
    render();
  }

  function render() {
    if (!rRoot) return;
    let p;
    try {
      if (rView === "list") p = renderList();
      else if (rView === "detail") p = renderDetail(rCurrentId);
      else if (rView === "form") p = renderForm(rCurrentId);
      else if (rView === "paste") p = renderPaste();
      else if (rView === "revisions") p = renderRevisions(rCurrentId);
      else if (rView === "revision") p = renderRevisionDetail(rCurrentId, rCurrentRevisionId);
    } catch (err) {
      showError(err);
      return;
    }
    if (p && typeof p.catch === "function") p.catch(showError);
  }

  function goTo(view, id = null, revisionId = null) {
    rView = view;
    rCurrentId = id;
    rCurrentRevisionId = revisionId;
    render();
  }

  function showError(err) {
    console.error("RecipesUI:", err);
    if (rRoot) {
      rRoot.innerHTML = `<div class="empty-hint">Erreur d'affichage : ${escapeHtml(String((err && err.message) || err))}</div>`;
    }
  }

  function toolbar() {
    return `
      <div class="st-toolbar">
        <button class="ghost-btn" id="rNewBtn">+ Nouvelle recette</button>
        <button class="ghost-btn" id="rPasteBtn">Coller une recette</button>
        <span class="spacer"></span>
        <input id="rSearch" class="search-input" placeholder="Rechercher (titre, tags)…" value="${escapeAttr(rSearchTerm)}" />
      </div>
    `;
  }

  function wireToolbar() {
    rRoot.querySelector("#rNewBtn")?.addEventListener("click", () => goTo("form", null));
    rRoot.querySelector("#rPasteBtn")?.addEventListener("click", () => goTo("paste"));
    rRoot.querySelector("#rSearch")?.addEventListener("input", (e) => {
      rSearchTerm = e.target.value;
      renderGrid();
    });
  }

  function tagChips(tags) {
    const list = (tags || "").split(",").map((t) => t.trim()).filter(Boolean);
    return list.length
      ? `<div class="task-tags">${list.map((t) => `<span class="tag-chip">${escapeHtml(t)}</span>`).join("")}</div>`
      : "";
  }

  // ---------- Vue liste ----------

  async function renderList() {
    rRoot.innerHTML = toolbar() + `<div id="rGrid"></div>`;
    wireToolbar();

    try {
      rAllRecipes = await api("/api/recipes");
    } catch (e) {
      rRoot.querySelector("#rGrid").innerHTML = `<div class="empty-hint">Impossible de charger les recettes : ${escapeHtml(e.message)}</div>`;
      return;
    }
    renderGrid();
  }

  function renderGrid() {
    const gridEl = rRoot.querySelector("#rGrid");
    if (!gridEl) return;

    if (!rAllRecipes.length) {
      gridEl.innerHTML = `<div class="empty-hint">Aucune recette pour l'instant. Colle une recette depuis un site, ou ajoute-la manuellement.</div>`;
      return;
    }

    const term = rSearchTerm.trim().toLowerCase();
    const recipes = term
      ? rAllRecipes.filter((r) => r.title.toLowerCase().includes(term) || (r.tags || "").toLowerCase().includes(term))
      : rAllRecipes;

    if (!recipes.length) {
      gridEl.className = "";
      gridEl.innerHTML = `<div class="empty-hint">Aucune recette ne correspond à "${escapeHtml(rSearchTerm)}".</div>`;
      return;
    }

    gridEl.className = "recipe-grid";
    gridEl.innerHTML = recipes.map((r) => `
      <div class="recipe-card" data-id="${r.id}">
        ${r.image_url ? `<img class="recipe-card-img" src="${escapeAttr(r.image_url)}" alt="" />` : `<div class="recipe-card-img recipe-card-img-empty">🍲</div>`}
        <div class="recipe-card-body">
          <div class="recipe-card-title">${escapeHtml(r.title)}</div>
          <div class="recipe-card-meta">${recipeMeta(r)}</div>
          ${tagChips(r.tags)}
        </div>
      </div>
    `).join("");

    gridEl.querySelectorAll(".recipe-card").forEach((card) => {
      card.addEventListener("click", () => goTo("detail", Number(card.dataset.id)));
    });
  }

  function recipeMeta(r) {
    const parts = [];
    if (r.prep_minutes) parts.push(`Prépa ${r.prep_minutes}min`);
    if (r.cook_minutes) parts.push(`Cuisson ${r.cook_minutes}min`);
    if (r.servings) parts.push(`${r.servings} portions`);
    return parts.join(" · ");
  }

  // ---------- Vue détail ----------

  async function renderDetail(id) {
    rRoot.innerHTML = `<div class="st-toolbar"><button class="ghost-btn" id="rBackBtn">&larr; Retour</button></div><div id="rDetailBody"></div>`;
    rRoot.querySelector("#rBackBtn").addEventListener("click", () => goTo("list"));

    const bodyEl = rRoot.querySelector("#rDetailBody");
    let r;
    try {
      r = await api(`/api/recipes/${id}`);
    } catch {
      bodyEl.innerHTML = `<div class="empty-hint">Recette introuvable.</div>`;
      return;
    }

    const ingredients = r.ingredients.split("\n").filter((l) => l.trim());
    const steps = r.steps.split("\n").filter((l) => l.trim());

    bodyEl.innerHTML = `
      <h3>${escapeHtml(r.title)}</h3>
      <div class="recipe-detail-meta">${recipeMeta(r)}</div>
      ${tagChips(r.tags)}
      ${r.image_url ? `<img class="recipe-detail-img" src="${escapeAttr(r.image_url)}" alt="" />` : ""}
      ${r.source_url ? `<p><a href="${escapeAttr(r.source_url)}" target="_blank" rel="noopener">Source</a></p>` : ""}
      <h4>Ingrédients</h4>
      <ul>${ingredients.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>
      <h4>Étapes</h4>
      <ol>${steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ol>
      <div class="st-toolbar">
        <button class="ghost-btn" id="rEditBtn">Modifier</button>
        <button class="ghost-btn" id="rHistoryBtn">Historique</button>
        <button class="danger-btn" id="rDeleteBtn">Supprimer</button>
      </div>
      <h4>Commentaires</h4>
      <div id="rComments"></div>
      <div class="st-form-row">
        <label style="flex:1">Ajouter un commentaire <textarea id="rCommentBody" rows="2"></textarea></label>
      </div>
      <button class="primary-btn" id="rCommentBtn">Publier</button>
    `;

    const commentsEl = bodyEl.querySelector("#rComments");
    commentsEl.innerHTML = r.comments.length
      ? r.comments.map((c) => `
          <div class="entry-row" style="align-items:flex-start;flex-direction:column;gap:4px;">
            <strong>${escapeHtml(c.author_name)}</strong>
            <span>${escapeHtml(c.body)}</span>
          </div>
        `).join("")
      : `<div class="empty-hint">Aucun commentaire.</div>`;

    bodyEl.querySelector("#rEditBtn").addEventListener("click", () => goTo("form", id));
    bodyEl.querySelector("#rHistoryBtn").addEventListener("click", () => goTo("revisions", id));
    bodyEl.querySelector("#rDeleteBtn").addEventListener("click", async () => {
      if (!confirm(`Supprimer la recette "${r.title}" ?`)) return;
      await api(`/api/recipes/${id}`, { method: "DELETE" });
      goTo("list");
    });
    bodyEl.querySelector("#rCommentBtn").addEventListener("click", async () => {
      const body = bodyEl.querySelector("#rCommentBody").value.trim();
      if (!body) return;
      await api(`/api/recipes/${id}/comments`, { method: "POST", body: JSON.stringify({ body }) });
      goTo("detail", id);
    });
  }

  // ---------- Vue formulaire (création/édition manuelle) ----------

  async function renderForm(id) {
    let r = null;
    if (id) {
      try {
        r = await api(`/api/recipes/${id}`);
      } catch {
        rRoot.innerHTML = `<div class="empty-hint">Recette introuvable.</div>`;
        return;
      }
    }

    rRoot.innerHTML = `
      <div class="st-toolbar"><button class="ghost-btn" id="rBackBtn">&larr; Retour</button></div>
      <h3>${id ? "Modifier la recette" : "Nouvelle recette"}</h3>
      <div class="st-form-row">
        <label style="flex:1">Titre <input id="fTitle" value="${escapeAttr(r ? r.title : "")}" /></label>
      </div>
      <div class="st-form-row">
        <label>Prépa (min) <input id="fPrep" type="number" min="0" value="${r && r.prep_minutes != null ? r.prep_minutes : ""}" /></label>
        <label>Cuisson (min) <input id="fCook" type="number" min="0" value="${r && r.cook_minutes != null ? r.cook_minutes : ""}" /></label>
        <label>Portions <input id="fServings" type="number" min="0" value="${r && r.servings != null ? r.servings : ""}" /></label>
      </div>
      <div class="st-form-row">
        <label style="flex:1">Tags (séparés par des virgules) <input id="fTags" value="${escapeAttr(r ? (r.tags || "") : "")}" placeholder="dessert, végétarien, italien" /></label>
      </div>
      <div class="st-form-row">
        <label style="flex:1">URL source <input id="fSourceUrl" value="${escapeAttr(r ? (r.source_url || "") : "")}" /></label>
      </div>
      <div class="st-form-row">
        <label style="flex:1">URL image <input id="fImageUrl" value="${escapeAttr(r ? (r.image_url || "") : "")}" /></label>
      </div>
      <div class="st-form-row">
        <label style="flex:1">Ingrédients (un par ligne) <textarea id="fIngredients" rows="8">${escapeHtml(r ? r.ingredients : "")}</textarea></label>
      </div>
      <div class="st-form-row">
        <label style="flex:1">Étapes (une par ligne) <textarea id="fSteps" rows="8">${escapeHtml(r ? r.steps : "")}</textarea></label>
      </div>
      <button class="primary-btn" id="fSaveBtn">Enregistrer</button>
    `;

    rRoot.querySelector("#rBackBtn").addEventListener("click", () => goTo(id ? "detail" : "list", id));
    rRoot.querySelector("#fSaveBtn").addEventListener("click", async () => {
      const title = rRoot.querySelector("#fTitle").value.trim();
      if (!title) return;
      const payload = {
        title,
        ingredients: rRoot.querySelector("#fIngredients").value,
        steps: rRoot.querySelector("#fSteps").value,
        prep_minutes: numOrNull(rRoot.querySelector("#fPrep").value),
        cook_minutes: numOrNull(rRoot.querySelector("#fCook").value),
        servings: numOrNull(rRoot.querySelector("#fServings").value),
        tags: rRoot.querySelector("#fTags").value.trim(),
        source_url: rRoot.querySelector("#fSourceUrl").value.trim() || null,
        image_url: rRoot.querySelector("#fImageUrl").value.trim() || null,
      };
      try {
        if (id) {
          await api(`/api/recipes/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
          goTo("detail", id);
        } else {
          const created = await api("/api/recipes", { method: "POST", body: JSON.stringify(payload) });
          goTo("detail", created.id);
        }
      } catch (e) {
        alert(`Erreur lors de l'enregistrement : ${e.message}`);
      }
    });
  }

  function numOrNull(v) {
    const n = parseInt(v, 10);
    return Number.isFinite(n) ? n : null;
  }

  function fmtDateTime(iso) {
    const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    return d.toLocaleString("fr-CA", { dateStyle: "medium", timeStyle: "short" });
  }

  // ---------- Vue historique (liste des versions précédentes) ----------

  async function renderRevisions(id) {
    rRoot.innerHTML = `<div class="st-toolbar"><button class="ghost-btn" id="rBackBtn">&larr; Retour</button></div><h3>Historique des modifications</h3><div id="rRevList"></div>`;
    rRoot.querySelector("#rBackBtn").addEventListener("click", () => goTo("detail", id));

    const listEl = rRoot.querySelector("#rRevList");
    let revisions;
    try {
      revisions = await api(`/api/recipes/${id}/revisions`);
    } catch {
      listEl.innerHTML = `<div class="empty-hint">Impossible de charger l'historique.</div>`;
      return;
    }

    if (!revisions.length) {
      listEl.innerHTML = `<div class="empty-hint">Aucune modification enregistrée pour l'instant — l'historique se remplit à chaque édition.</div>`;
      return;
    }

    listEl.innerHTML = revisions.map((rev) => `
      <div class="timesheet-row" data-id="${rev.id}">
        <span class="ts-date">${fmtDateTime(rev.snapshotted_at)}</span>
        <span class="ts-meta">Modifié par ${escapeHtml(rev.edited_by_email || "?")}</span>
      </div>
    `).join("");

    listEl.querySelectorAll(".timesheet-row").forEach((row) => {
      row.addEventListener("click", () => goTo("revision", id, Number(row.dataset.id)));
    });
  }

  async function renderRevisionDetail(id, revisionId) {
    rRoot.innerHTML = `<div class="st-toolbar"><button class="ghost-btn" id="rBackBtn">&larr; Retour à l'historique</button></div><div id="rRevBody"></div>`;
    rRoot.querySelector("#rBackBtn").addEventListener("click", () => goTo("revisions", id));

    const bodyEl = rRoot.querySelector("#rRevBody");
    let revisions;
    try {
      revisions = await api(`/api/recipes/${id}/revisions`);
    } catch {
      bodyEl.innerHTML = `<div class="empty-hint">Impossible de charger cette version.</div>`;
      return;
    }
    const rev = revisions.find((r) => r.id === revisionId);
    if (!rev) {
      bodyEl.innerHTML = `<div class="empty-hint">Version introuvable.</div>`;
      return;
    }

    const ingredients = rev.ingredients.split("\n").filter((l) => l.trim());
    const steps = rev.steps.split("\n").filter((l) => l.trim());

    bodyEl.innerHTML = `
      <p style="color:var(--muted);font-size:0.82rem;">Version du ${fmtDateTime(rev.snapshotted_at)}, modifiée par ${escapeHtml(rev.edited_by_email || "?")} — lecture seule.</p>
      <h3>${escapeHtml(rev.title)}</h3>
      <div class="recipe-detail-meta">${recipeMeta(rev)}</div>
      ${tagChips(rev.tags)}
      <h4>Ingrédients</h4>
      <ul>${ingredients.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>
      <h4>Étapes</h4>
      <ol>${steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ol>
    `;
  }

  // ---------- Vue "Coller une recette" (extraction Claude) ----------

  function renderPaste() {
    rRoot.innerHTML = `
      <div class="st-toolbar"><button class="ghost-btn" id="rBackBtn">&larr; Retour</button></div>
      <h3>Coller une recette</h3>
      <p style="color:var(--muted);font-size:0.85rem;">Colle le texte d'une page recette (ingrédients, étapes, etc.) — Claude va l'analyser et créer la recette automatiquement.</p>
      <div class="st-form-row">
        <label style="flex:1">URL source (optionnel) <input id="pSourceUrl" placeholder="https://..." /></label>
      </div>
      <div class="st-form-row">
        <label style="flex:1">Contenu <textarea id="pContent" rows="14"></textarea></label>
      </div>
      <button class="primary-btn" id="pExtractBtn">Analyser et enregistrer</button>
      <span id="pStatus" style="margin-left:10px;color:var(--muted);font-size:0.85rem;"></span>
    `;
    rRoot.querySelector("#rBackBtn").addEventListener("click", () => goTo("list"));
    rRoot.querySelector("#pExtractBtn").addEventListener("click", async () => {
      const content = rRoot.querySelector("#pContent").value.trim();
      if (!content) return;
      const statusEl = rRoot.querySelector("#pStatus");
      const btn = rRoot.querySelector("#pExtractBtn");
      btn.disabled = true;
      statusEl.textContent = "Analyse en cours…";
      try {
        const created = await api("/api/recipes/extract", {
          method: "POST",
          body: JSON.stringify({
            content,
            source_url: rRoot.querySelector("#pSourceUrl").value.trim() || null,
          }),
        });
        goTo("detail", created.id);
      } catch (e) {
        statusEl.textContent = `Erreur : ${e.message}`;
        btn.disabled = false;
      }
    });
  }

  function escapeAttr(str) {
    return escapeHtml(str).replace(/"/g, "&quot;");
  }

  return { mount };
})();
