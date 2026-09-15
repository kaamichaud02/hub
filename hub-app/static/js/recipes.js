// Section "Recette" du hub — SPA vanilla JS consommant /api/recipes, mêmes
// conventions que app.js/timesheets.js. Monté dans #recipesPlaceholder par
// app.js::setActiveSection.

window.RecipesUI = (() => {
  let rRoot = null;
  let rView = "list"; // "list" | "detail" | "form" | "paste"
  let rCurrentId = null;

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
    } catch (err) {
      showError(err);
      return;
    }
    if (p && typeof p.catch === "function") p.catch(showError);
  }

  function goTo(view, id = null) {
    rView = view;
    rCurrentId = id;
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
      </div>
    `;
  }

  function wireToolbar() {
    rRoot.querySelector("#rNewBtn")?.addEventListener("click", () => goTo("form", null));
    rRoot.querySelector("#rPasteBtn")?.addEventListener("click", () => goTo("paste"));
  }

  // ---------- Vue liste ----------

  async function renderList() {
    rRoot.innerHTML = toolbar() + `<div id="rGrid"></div>`;
    wireToolbar();

    const gridEl = rRoot.querySelector("#rGrid");
    let recipes;
    try {
      recipes = await api("/api/recipes");
    } catch {
      gridEl.innerHTML = `<div class="empty-hint">Impossible de charger les recettes.</div>`;
      return;
    }

    if (!recipes.length) {
      gridEl.innerHTML = `<div class="empty-hint">Aucune recette pour l'instant. Colle une recette depuis un site, ou ajoute-la manuellement.</div>`;
      return;
    }

    gridEl.className = "recipe-grid";
    gridEl.innerHTML = recipes.map((r) => `
      <div class="recipe-card" data-id="${r.id}">
        ${r.image_url ? `<img class="recipe-card-img" src="${escapeAttr(r.image_url)}" alt="" />` : `<div class="recipe-card-img recipe-card-img-empty">🍲</div>`}
        <div class="recipe-card-body">
          <div class="recipe-card-title">${escapeHtml(r.title)}</div>
          <div class="recipe-card-meta">${recipeMeta(r)}</div>
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
      ${r.image_url ? `<img class="recipe-detail-img" src="${escapeAttr(r.image_url)}" alt="" />` : ""}
      ${r.source_url ? `<p><a href="${escapeAttr(r.source_url)}" target="_blank" rel="noopener">Source</a></p>` : ""}
      <h4>Ingrédients</h4>
      <ul>${ingredients.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>
      <h4>Étapes</h4>
      <ol>${steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ol>
      <div class="st-toolbar">
        <button class="ghost-btn" id="rEditBtn">Modifier</button>
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
