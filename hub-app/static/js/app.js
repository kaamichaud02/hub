const hubView = document.getElementById("hubView");
const boardView = document.getElementById("boardView");
const pageTitle = document.getElementById("pageTitle");
const backBtn = document.getElementById("backBtn");
const newBoardBtn = document.getElementById("newBoardBtn");
const modalRoot = document.getElementById("modalRoot");

let currentBoardId = null;

// ---------- API helpers ----------

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  if (res.status === 204) return null;
  return res.json();
}

// ---------- Navigation ----------

function showHub() {
  currentBoardId = null;
  boardView.hidden = true;
  hubView.hidden = false;
  backBtn.hidden = true;
  newBoardBtn.hidden = false;
  pageTitle.textContent = "Hub";
  loadHub();
}

function showBoard(boardId) {
  currentBoardId = boardId;
  hubView.hidden = true;
  boardView.hidden = false;
  backBtn.hidden = false;
  newBoardBtn.hidden = true;
  loadBoard(boardId);
}

backBtn.addEventListener("click", showHub);

// ---------- Hub (tuiles) ----------

async function loadHub() {
  const boards = await api("/api/boards");
  hubView.innerHTML = "";

  if (boards.length === 0) {
    hubView.innerHTML = `<div class="empty-hint">Aucun projet pour l'instant. Clique sur "+ Projet" pour en créer un.</div>`;
    return;
  }

  for (const board of boards) {
    const tile = document.createElement("div");
    tile.className = "board-tile";
    tile.dataset.id = board.id;
    tile.style.setProperty("--tile-color", board.color || "#00d4a0");
    tile.innerHTML = `
      <div class="tile-icon">${board.icon || "📋"}</div>
      <div class="tile-name">${escapeHtml(board.name)}</div>
      <div class="tile-desc">${escapeHtml(board.description || "")}</div>
      <div class="tile-meta"><span>#${board.id}</span></div>
    `;
    tile.addEventListener("click", (e) => {
      if (tile.classList.contains("dragging-just-ended")) return;
      showBoard(board.id);
    });
    hubView.appendChild(tile);
  }

  new Sortable(hubView, {
    animation: 150,
    onEnd: async (evt) => {
      const tiles = [...hubView.querySelectorAll(".board-tile")];
      await Promise.all(
        tiles.map((t, i) => api(`/api/boards/${t.dataset.id}/reorder`, {
          method: "PATCH",
          body: JSON.stringify({ position: i }),
        }))
      );
    },
  });
}

newBoardBtn.addEventListener("click", () => openBoardModal());

function openBoardModal() {
  const icons = ["📋", "🕒", "🛠️", "🌐", "🔥", "📦", "🧩", "⚙️"];
  modalRoot.innerHTML = `
    <div class="modal-overlay">
      <div class="modal">
        <h2>Nouveau projet</h2>
        <input id="mName" placeholder="Nom du projet" />
        <textarea id="mDesc" placeholder="Description" rows="2"></textarea>
        <input id="mColor" type="color" value="#00d4a0" />
        <select id="mIcon">${icons.map((i) => `<option value="${i}">${i}</option>`).join("")}</select>
        <div class="modal-actions">
          <button class="cancel-btn" id="mCancel">Annuler</button>
          <button class="primary-btn" id="mSave">Créer</button>
        </div>
      </div>
    </div>
  `;
  document.getElementById("mCancel").onclick = closeModal;
  document.getElementById("mSave").onclick = async () => {
    const name = document.getElementById("mName").value.trim();
    if (!name) return;
    await api("/api/boards", {
      method: "POST",
      body: JSON.stringify({
        name,
        description: document.getElementById("mDesc").value.trim(),
        color: document.getElementById("mColor").value,
        icon: document.getElementById("mIcon").value,
      }),
    });
    closeModal();
    loadHub();
  };
}

function closeModal() {
  modalRoot.innerHTML = "";
}

// ---------- Board (kanban) ----------

async function loadBoard(boardId) {
  const data = await api(`/api/boards/${boardId}`);
  pageTitle.textContent = `${data.board.icon || ""} ${data.board.name}`;
  boardView.innerHTML = "";

  for (const col of data.columns) {
    boardView.appendChild(renderColumn(col));
  }

  const addColBtn = document.createElement("button");
  addColBtn.className = "add-column-btn";
  addColBtn.textContent = "+ Colonne";
  addColBtn.onclick = async () => {
    const name = prompt("Nom de la colonne :");
    if (!name) return;
    await api("/api/columns", {
      method: "POST",
      body: JSON.stringify({ board_id: boardId, name }),
    });
    loadBoard(boardId);
  };
  boardView.appendChild(addColBtn);
}

function renderColumn(col) {
  const wrap = document.createElement("div");
  wrap.className = "kanban-col";
  wrap.dataset.id = col.id;

  wrap.innerHTML = `
    <div class="kanban-col-header">
      <span>${escapeHtml(col.name)}</span>
      <span class="count">${col.tasks.length}</span>
    </div>
    <div class="kanban-col-body" data-col-id="${col.id}"></div>
    <button class="add-task-btn">+ Tâche</button>
  `;

  const body = wrap.querySelector(".kanban-col-body");
  for (const task of col.tasks) {
    body.appendChild(renderTaskCard(task));
  }

  wrap.querySelector(".add-task-btn").addEventListener("click", () => openTaskModal(col.id));

  new Sortable(body, {
    group: "kanban",
    animation: 150,
    onEnd: async (evt) => {
      const taskId = evt.item.dataset.id;
      const newColId = evt.to.dataset.colId;
      const newIndex = evt.newIndex;
      await api(`/api/tasks/${taskId}/move`, {
        method: "PATCH",
        body: JSON.stringify({ column_id: Number(newColId), position: newIndex }),
      });
      // Rafraîchit les compteurs de colonnes sans perdre le scroll global
      loadBoard(currentBoardId);
    },
  });

  return wrap;
}

function renderTaskCard(task) {
  const card = document.createElement("div");
  card.className = "task-card";
  card.dataset.id = task.id;
  const tags = (task.tags || "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);

  card.innerHTML = `
    <div class="task-title">${escapeHtml(task.title)}</div>
    ${task.description ? `<div class="task-desc">${escapeHtml(task.description)}</div>` : ""}
    ${tags.length ? `<div class="task-tags">${tags.map((t) => `<span class="tag-chip">${escapeHtml(t)}</span>`).join("")}</div>` : ""}
  `;

  card.addEventListener("dblclick", () => {
    if (confirm(`Supprimer la tâche "${task.title}" ?`)) {
      api(`/api/tasks/${task.id}`, { method: "DELETE" }).then(() => loadBoard(currentBoardId));
    }
  });

  return card;
}

function openTaskModal(columnId) {
  modalRoot.innerHTML = `
    <div class="modal-overlay">
      <div class="modal">
        <h2>Nouvelle tâche</h2>
        <input id="tTitle" placeholder="Titre" />
        <textarea id="tDesc" placeholder="Description" rows="3"></textarea>
        <input id="tTags" placeholder="Tags (séparés par des virgules)" />
        <div class="modal-actions">
          <button class="cancel-btn" id="tCancel">Annuler</button>
          <button class="primary-btn" id="tSave">Ajouter</button>
        </div>
      </div>
    </div>
  `;
  document.getElementById("tCancel").onclick = closeModal;
  document.getElementById("tSave").onclick = async () => {
    const title = document.getElementById("tTitle").value.trim();
    if (!title) return;
    await api("/api/tasks", {
      method: "POST",
      body: JSON.stringify({
        column_id: columnId,
        title,
        description: document.getElementById("tDesc").value.trim(),
        tags: document.getElementById("tTags").value.trim(),
      }),
    });
    closeModal();
    loadBoard(currentBoardId);
  };
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------- Init ----------

showHub();
