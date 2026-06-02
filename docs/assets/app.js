const DATA_URL = "data/papers.json";
const FAVORITES_KEY = "dac2026.favoritePaperIds";

const state = {
  papers: [],
  favorites: new Set(),
  page: document.body.dataset.page || "papers",
  query: "",
  track: "",
  sort: "id",
};

const els = {
  list: document.querySelector("#paperList"),
  summary: document.querySelector("#resultSummary"),
  search: document.querySelector("#searchInput"),
  track: document.querySelector("#trackFilter"),
  sort: document.querySelector("#sortSelect"),
  favoriteCounts: document.querySelectorAll("[data-favorite-count]"),
};

function loadFavorites() {
  try {
    const ids = JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]");
    return new Set(Array.isArray(ids) ? ids : []);
  } catch {
    return new Set();
  }
}

function saveFavorites() {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify([...state.favorites].sort()));
  updateFavoriteCounts();
}

function updateFavoriteCounts() {
  els.favoriteCounts.forEach((node) => {
    node.textContent = String(state.favorites.size);
  });
}

function normalize(value) {
  return String(value || "").toLowerCase();
}

function paperText(paper) {
  return [
    paper.id,
    paper.title,
    paper.abstract,
    paper.eventType,
    paper.authorInstitutions,
    ...(paper.authors || []),
    ...(paper.tracks || []),
    ...(paper.sessionTitles || []),
    ...(paper.locations || []),
  ].join(" ");
}

function matchesFilters(paper) {
  if (state.page === "favorites" && !state.favorites.has(paper.id)) {
    return false;
  }

  if (state.track && !(paper.tracks || []).includes(state.track)) {
    return false;
  }

  if (!state.query) {
    return true;
  }

  return normalize(paperText(paper)).includes(state.query);
}

function sortPapers(papers) {
  const key = state.sort;
  return [...papers].sort((a, b) => {
    if (key === "title") {
      return a.title.localeCompare(b.title);
    }
    if (key === "authors") {
      return (a.authors?.[0] || "").localeCompare(b.authors?.[0] || "");
    }
    return a.id.localeCompare(b.id, undefined, { numeric: true });
  });
}

function joinList(values, fallback = "Not listed") {
  if (!values || values.length === 0) {
    return fallback;
  }
  return values.join("; ");
}

function shortList(values, maxItems = 1, fallback = "Not listed") {
  if (!values || values.length === 0) {
    return fallback;
  }

  const visible = values.slice(0, maxItems).join("; ");
  const hiddenCount = values.length - maxItems;
  return hiddenCount > 0 ? `${visible} +${hiddenCount}` : visible;
}

function createTextElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  node.textContent = text;
  return node;
}

function createMetaItem(label, value, title = value) {
  const item = document.createElement("span");
  item.className = "meta-item";
  item.title = title;
  item.append(createTextElement("strong", "", `${label}:`));
  item.append(document.createTextNode(value));
  return item;
}

function toggleFavorite(paperId) {
  if (state.favorites.has(paperId)) {
    state.favorites.delete(paperId);
  } else {
    state.favorites.add(paperId);
  }
  saveFavorites();
  render();
}

function createPaperCard(paper) {
  const card = document.createElement("article");
  card.className = "paper-card";

  const top = document.createElement("div");
  top.className = "card-top";
  const titleBlock = document.createElement("div");
  titleBlock.className = "title-block";
  titleBlock.append(createTextElement("div", "paper-id", paper.id));
  titleBlock.append(createTextElement("h2", "paper-title", paper.title));
  titleBlock.append(createTextElement("p", "paper-authors", joinList(paper.authors)));
  top.append(titleBlock);

  const favoriteButton = document.createElement("button");
  const isFavorite = state.favorites.has(paper.id);
  favoriteButton.className = "icon-button favorite-button";
  favoriteButton.type = "button";
  favoriteButton.title = isFavorite ? "Remove from favorites" : "Save to favorites";
  favoriteButton.setAttribute("aria-label", favoriteButton.title);
  favoriteButton.setAttribute("aria-pressed", String(isFavorite));
  favoriteButton.textContent = isFavorite ? "★" : "☆";
  favoriteButton.addEventListener("click", () => toggleFavorite(paper.id));
  top.append(favoriteButton);
  card.append(top);

  const meta = document.createElement("div");
  meta.className = "compact-meta";
  meta.append(createMetaItem("Date", shortList(paper.dates), joinList(paper.dates)));
  meta.append(createMetaItem("Location", shortList(paper.locations), joinList(paper.locations)));
  meta.append(createMetaItem("Session", shortList(paper.sessionTitles), joinList(paper.sessionTitles)));
  card.append(meta);

  const abstract = document.createElement("details");
  abstract.className = "paper-abstract";
  const summary = document.createElement("summary");
  summary.textContent = "Abstract";
  abstract.append(summary);
  abstract.append(createTextElement("p", "", paper.abstract));
  card.append(abstract);

  const chips = document.createElement("div");
  chips.className = "chips";
  const tracks = (paper.tracks || []).slice(0, 4);
  tracks.forEach((track) => chips.append(createTextElement("span", "chip", track)));
  if ((paper.tracks || []).length > tracks.length) {
    chips.append(createTextElement("span", "chip", `+${paper.tracks.length - tracks.length} more`));
  }
  card.append(chips);

  if (paper.urls?.[0]) {
    const link = document.createElement("a");
    link.className = "icon-button program-link";
    link.href = paper.urls[0];
    link.target = "_blank";
    link.rel = "noreferrer";
    link.title = "Open program page";
    link.setAttribute("aria-label", "Open program page");
    link.textContent = "↗";
    card.append(link);
  }

  return card;
}

function renderEmpty(message, linkText) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.append(createTextElement("h2", "", message));

  if (state.page === "favorites") {
    empty.append(createTextElement("p", "", "Mark papers from the main list to keep them here."));
    const link = document.createElement("a");
    link.className = "details-link";
    link.href = "index.html";
    link.textContent = linkText || "Browse papers";
    empty.append(link);
  }

  els.list.append(empty);
}

function render() {
  const filtered = sortPapers(state.papers.filter(matchesFilters));
  els.list.innerHTML = "";

  const noun = filtered.length === 1 ? "paper" : "papers";
  if (state.page === "favorites") {
    els.summary.textContent = `${filtered.length} favorite ${noun}`;
  } else {
    els.summary.textContent = `${filtered.length} of ${state.papers.length} papers`;
  }

  if (filtered.length === 0) {
    renderEmpty(state.page === "favorites" ? "No favorite papers yet" : "No matching papers");
    return;
  }

  filtered.forEach((paper) => {
    els.list.append(createPaperCard(paper));
  });
}

function populateTrackFilter() {
  if (!els.track) {
    return;
  }

  const tracks = [...new Set(state.papers.flatMap((paper) => paper.tracks || []))]
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b));

  tracks.forEach((track) => {
    const option = document.createElement("option");
    option.value = track;
    option.textContent = track;
    els.track.append(option);
  });
}

function bindEvents() {
  els.search?.addEventListener("input", (event) => {
    state.query = normalize(event.target.value.trim());
    render();
  });

  els.track?.addEventListener("change", (event) => {
    state.track = event.target.value;
    render();
  });

  els.sort?.addEventListener("change", (event) => {
    state.sort = event.target.value;
    render();
  });
}

async function init() {
  state.favorites = loadFavorites();
  updateFavoriteCounts();
  bindEvents();

  try {
    const response = await fetch(DATA_URL);
    if (!response.ok) {
      throw new Error(`Failed to load ${DATA_URL}: ${response.status}`);
    }
    state.papers = await response.json();
    populateTrackFilter();
    render();
  } catch (error) {
    els.summary.textContent = error.message;
  }
}

init();
