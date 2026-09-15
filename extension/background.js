// Extension "Capture de recette" — clic sur l'icône de la barre d'outils :
// capture le contenu de la page active (JSON-LD schema.org/Recipe si trouvé,
// sinon le texte visible de la page), l'envoie au hub qui appelle Claude pour
// en extraire une recette structurée et la sauvegarde directement.
//
// Pas d'aperçu, pas de popup : juste un badge ✓/✗ sur l'icône après l'envoi.
// Pas de clé API Anthropic ici — l'extension ne parle qu'au hub.

// Adapter selon l'environnement testé (hubtest pendant les tests, hub une
// fois la prod en place) — doit correspondre à un des host_permissions du
// manifest.
const HUB_BASE_URL = "https://hubtest.kaa.zone";

// Injectée dans la page active via chrome.scripting.executeScript — doit être
// autonome (sérialisée et exécutée dans le contexte de la page, pas d'accès
// aux variables/fonctions de background.js).
function extractPageContent() {
  // La plupart des sites de recettes intègrent un bloc JSON-LD
  // schema.org/Recipe pour les rich snippets Google — bien plus fiable à
  // analyser que le texte brut de la page (moins de bruit : pubs, commentaires,
  // navigation...).
  const ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const script of ldScripts) {
    try {
      const data = JSON.parse(script.textContent);
      const items = Array.isArray(data) ? data : [data, ...(data["@graph"] || [])];
      const recipe = items.find((item) => {
        const type = item && item["@type"];
        return type === "Recipe" || (Array.isArray(type) && type.includes("Recipe"));
      });
      if (recipe) {
        return { content: JSON.stringify(recipe), title: document.title };
      }
    } catch {
      // bloc JSON-LD invalide/non pertinent, on continue
    }
  }

  // Repli : texte visible de la page, tronqué pour rester raisonnable.
  const text = document.body ? document.body.innerText : "";
  return { content: text.slice(0, 15000), title: document.title };
}

async function captureActiveTab(tab) {
  if (!tab || !tab.id || !tab.url || !tab.url.startsWith("http")) {
    await chrome.action.setBadgeText({ text: "✗" });
    return;
  }

  await chrome.action.setBadgeText({ text: "…" });
  await chrome.action.setBadgeBackgroundColor({ color: "#8b93a1" });

  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageContent,
    });

    const res = await fetch(`${HUB_BASE_URL}/api/recipes/extract`, {
      method: "POST",
      credentials: "include", // envoie le cookie CF_Authorization déjà présent si l'utilisateur est connecté au hub
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: result.content,
        source_url: tab.url,
        title_hint: result.title,
      }),
    });

    if (!res.ok) throw new Error(`Hub -> ${res.status}`);

    await chrome.action.setBadgeText({ text: "✓" });
    await chrome.action.setBadgeBackgroundColor({ color: "#00d4a0" });
  } catch (err) {
    console.error("Capture recette échouée :", err);
    await chrome.action.setBadgeText({ text: "✗" });
    await chrome.action.setBadgeBackgroundColor({ color: "#ff4d6d" });
  }

  setTimeout(() => chrome.action.setBadgeText({ text: "" }), 4000);
}

chrome.action.onClicked.addListener(captureActiveTab);
