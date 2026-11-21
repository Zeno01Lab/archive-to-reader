"use strict";

const SESSION_SECONDS = 30 * 60;
const PAGE_SIZE = 45;
const TIMER_KEY = "archive-to-reader-timer-v1";
const PICKS_PREFIX = "archive-to-reader-picks-v1-";
const READING_SCOPE_KEY = "archive-to-reader-scope-v1";
const LANGUAGE_KEY = "archive-to-reader-language-v1";
const UNCLASSIFIED = "待分类";
const MAX_TAGS = 12;
const MAX_TAG_LENGTH = 40;
const MAX_BATCH_SIZE = 1000;
const USE_LABELS = {
  daily: ["Daily reading", "日常阅读"],
  roadmap: ["Learning roadmaps", "学习路线"],
  resources: ["Resource lists", "资源清单"],
  materials: ["Learning and reference", "学习与参考资料"],
};
const TOPIC_NAMES_EN = {
  "科技与开发": "Technology and Development",
  "工程与硬件": "Engineering and Hardware",
  "研究与写作": "Research and Writing",
  "课程与学习": "Courses and Learning",
  "工作与职业": "Work and Careers",
  "知识管理": "Knowledge Management",
  "文化与生活": "Culture and Life",
  "商业与产品": "Business and Product",
  [UNCLASSIFIED]: "Uncategorized",
};
const SAVE_STATUS_LABELS = {
  opening: ["Opening…", "正在打开…"],
  saving: ["Saving…", "保存中…"],
  saved: ["Saved", "已保存"],
  unsaved: ["Unsaved", "未保存"],
  reloaded: ["Reloaded", "已重新载入"],
};
const $ = (id) => document.getElementById(id);

let uiLanguage = "en";
const translatedNodes = new Map();
let catalogLoaded = false;
let catalogError = null;
let saveError = null;
let saveStatusKey = "";
let catalog = [];
let byId = new Map();
let topics = [];
let topicFilter = "";
let tagFilter = "";
let libraryMode = "daily";
let referenceKind = "";
const libraryFilters = {
  daily: { topic: "", tag: "", query: "", status: "queue", sort: "newest" },
  reference: { topic: "", tag: "", query: "", status: "all", sort: "newest" },
};
let readingState = { schemaVersion: 1, items: {} };
let confirmedState = { schemaVersion: 1, items: {} };
let revision = "";
let selectedId = null;
let selectedPayload = null;
let openRequest = 0;
let currentTab = "source";
let visibleCount = PAGE_SIZE;
let batchSelecting = false;
let batchReview = false;
let batchSaving = false;
let batchVisibleIds = new Set();
const batchIds = new Set();
let todayIds = [];
let pendingSaves = [];
let saveBusy = false;
let saveBlocked = false;
let progressTimer = null;
let toastTimer = null;
let noteTimer = null;
let timer = { day: "", remaining: SESSION_SECONDS, runningSince: null, started: false };

function tr(en, zh) {
  return uiLanguage === "zh-CN" ? zh : en;
}

function useLabel(use) {
  return tr(...(USE_LABELS[use] || USE_LABELS.daily));
}

function topicLabel(topic) {
  return tr(TOPIC_NAMES_EN[topic] || topic, topic);
}

function readingTime(item) {
  return tr(`About ${minutesOf(item)} min`, `约 ${minutesOf(item)} 分钟`);
}

function loadLanguage() {
  try { return localStorage.getItem(LANGUAGE_KEY) || "en"; }
  catch (_) { return "en"; }
}

function setLanguage(language) {
  uiLanguage = language === "zh-CN" ? "zh-CN" : "en";
  document.documentElement.lang = uiLanguage;
  $("uiLanguage").value = uiLanguage;
  const attributes = ["aria-label", "title", "placeholder"];
  const selector = ["[data-zh]", ...attributes.map((name) => `[data-${name}-zh]`)].join(",");
  for (const node of document.querySelectorAll(selector)) {
    if (!translatedNodes.has(node)) {
      const originalAttributes = attributes.filter((name) => node.hasAttribute(`data-${name}-zh`));
      translatedNodes.set(node, {
        text: node.textContent,
        attributes: originalAttributes.map((name) => [name, node.getAttribute(name)]),
      });
    }
    const original = translatedNodes.get(node);
    if (node.hasAttribute("data-zh")) node.textContent = tr(original.text, node.dataset.zh);
    for (const [name, value] of original.attributes) {
      node.setAttribute(name, tr(value, node.getAttribute(`data-${name}-zh`)));
    }
  }
  updateLibraryLabels();
  updateSaveStatus(saveStatusKey);
  if (saveError) $("saveErrorText").textContent = saveErrorMessage(saveError);
  $("toast").hidden = true;
  updateClock();
  renderTimer();
  if (catalogLoaded) {
    refreshReadingScope();
    renderAll();
  }
  renderCatalogStatus();
  if (selectedPayload) {
    renderReaderMeta(selectedPayload.item || byId.get(selectedId));
    const body = currentTab === "summary" ? selectedPayload.summaryBody : selectedPayload.body;
    if (!body?.trim()) renderArticle();
    if ($("classificationEditor").open) {
      const fields = [$("editTopic"), $("editTags"), $("editUse")];
      const values = fields.map((field) => field.value);
      fillClassificationEditor();
      fields.forEach((field, index) => { field.value = values[index]; });
    }
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function localDateParts(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-US", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23"
  }).formatToParts(date);
  return Object.fromEntries(parts.map((part) => [part.type, part.value]));
}

function localDay(date = new Date()) {
  const p = localDateParts(date);
  return `${p.year}-${p.month}-${p.day}`;
}

function displayDate(date = new Date()) {
  return new Intl.DateTimeFormat(uiLanguage, {
    month: "long", day: "numeric", weekday: "long"
  }).format(date);
}

function shortDate(raw) {
  if (!raw) return tr("Undated", "日期未记载");
  const match = String(raw).match(/\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : String(raw).slice(0, 16);
}

function statusOf(id) {
  return readingState.items?.[id]?.status || "unread";
}

function statusLabel(status) {
  return ({ unread: tr("To read", "待读"), reading: tr("Reading", "阅读中"), done: tr("Completed", "已完成"), later: tr("Read later", "稍后") })[status] || tr("To read", "待读");
}

function recordOf(id) {
  return readingState.items?.[id] || {};
}

function topicOf(item) {
  return recordOf(item.id).topicOverride ?? item.topic ?? UNCLASSIFIED;
}

function tagsOf(item) {
  return recordOf(item.id).tagsOverride ?? item.tags ?? [];
}

function useOf(item) {
  return recordOf(item.id).useOverride ?? item.use ?? "daily";
}

function inLibrary(item) {
  const use = useOf(item);
  return libraryMode === "daily" ? use === "daily" :
    use !== "daily" && (!referenceKind || use === referenceKind);
}

function tagKey(tag) {
  return tag.trim().toLocaleLowerCase();
}

function inReadingScope(item) {
  return (!topicFilter || topicOf(item) === topicFilter) &&
    (!tagFilter || tagsOf(item).some((tag) => tagKey(tag) === tagFilter));
}

function setReadingScope(topic, tag) {
  topicFilter = topic;
  tagFilter = tag;
  if (libraryMode === "daily") {
    try {
      localStorage.setItem(READING_SCOPE_KEY, JSON.stringify({ topic, tag }));
    } catch (_) { /* The selection still works in this tab. */ }
  }
  refreshReadingScope();
  visibleCount = PAGE_SIZE;
  batchReview = false;
  renderAll();
}

function switchLibrary(mode) {
  if (mode !== libraryMode) {
    clearBatchSelection();
    batchSelecting = false;
    libraryFilters[libraryMode] = {
      topic: topicFilter, tag: tagFilter, query: $("searchInput").value,
      status: $("statusFilter").value, sort: $("sortSelect").value,
    };
    libraryMode = mode;
    const page = window.location.pathname + window.location.search;
    window.history.replaceState(null, "", mode === "reference" ? `${page}#references` : page);
    const next = libraryFilters[mode];
    topicFilter = next.topic;
    tagFilter = next.tag;
    $("searchInput").value = next.query;
    $("statusFilter").value = next.status;
    $("sortSelect").value = next.sort;
    visibleCount = PAGE_SIZE;
  }
  showHome();
  refreshReadingScope();
  renderAll();
}

function loadReadingScope() {
  try {
    const scope = JSON.parse(localStorage.getItem(READING_SCOPE_KEY) || "null");
    const topic = topics.includes(scope?.topic) ? scope.topic : "";
    const tag = typeof scope?.tag === "string" ? scope.tag : "";
    if (libraryMode === "daily") {
      topicFilter = topic;
      tagFilter = tag;
    } else {
      Object.assign(libraryFilters.daily, { topic, tag });
    }
  } catch (_) { /* Use the default scope. */ }
}

function selectOption(value, label) {
  return `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`;
}

function refreshReadingScope() {
  const topicCounts = new Map();
  const tagCounts = new Map();
  for (const item of catalog) {
    if (!inLibrary(item)) continue;
    const topic = topicOf(item);
    const tags = tagsOf(item);
    if (!tagFilter || tags.some((tag) => tagKey(tag) === tagFilter)) {
      topicCounts.set(topic, (topicCounts.get(topic) || 0) + 1);
    }
    if (topicFilter && topic !== topicFilter) continue;
    for (const tag of tags) {
      const key = tagKey(tag);
      const entry = tagCounts.get(key) || { label: tag, count: 0 };
      entry.count += 1;
      tagCounts.set(key, entry);
    }
  }
  if (tagFilter && !tagCounts.has(tagFilter)) tagCounts.set(tagFilter, { label: tagFilter, count: 0 });
  const tagOptions = [...tagCounts].sort((a, b) =>
    b[1].count - a[1].count || a[1].label.localeCompare(b[1].label, uiLanguage));
  $("topicFilter").innerHTML = selectOption("", tr("All topics", "全部主题")) +
    topics.map((topic) => selectOption(topic, `${topicLabel(topic)} (${topicCounts.get(topic) || 0})`)).join("");
  $("topicFilter").value = topicFilter;
  $("tagFilter").innerHTML = selectOption("", tr("All tags", "全部标签")) +
    tagOptions.map(([key, { label, count }]) => selectOption(key, `${label} (${count})`)).join("");
  $("tagFilter").value = tagFilter;
  $("activeReadingScope").hidden = !topicFilter && !tagFilter;
  const tagLabel = tagCounts.get(tagFilter)?.label;
  $("readingScopeLabel").textContent = [topicLabel(topicFilter), tagLabel && `#${tagLabel}`].filter(Boolean).join(" · ");
  if (libraryMode === "daily") todayIds = chooseToday(false);
}

function cloneState(state) {
  return JSON.parse(JSON.stringify(state));
}

function minutesOf(item) {
  const n = Number(item?.minutes);
  return Number.isFinite(n) && n > 0 ? Math.max(1, Math.round(n)) : 5;
}

function itemMeta(item) {
  const segments = [shortDate(item.date), readingTime(item)];
  if (item.summaryPath) segments.push(tr("Includes a companion summary", "含配套笔记"));
  if (item.coverage === "url-only") segments.push(tr("Link only", "仅保存链接"));
  if (item.coverage === "excerpt") segments.push(tr("Excerpt or archive notes only", "仅有节选或归档笔记"));
  return segments;
}

function renderReaderMeta(item) {
  $("readerMeta").innerHTML = itemMeta(item).map((part) => `<span>${escapeHtml(part)}</span>`).join("");
}

function announce(message, ms = 3500) {
  const node = $("toast");
  node.textContent = message;
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, ms);
}

async function readJson(url, options) {
  const response = await fetch(url, { cache: "no-store", ...options });
  let data = null;
  try { data = await response.json(); } catch (_) { /* handled below */ }
  if (!response.ok) {
    const error = new Error(data?.error || data?.message || "");
    error.status = response.status;
    throw error;
  }
  return data;
}

function apiErrorMessage(error) {
  if (uiLanguage === "zh-CN" && error.message) return error.message;
  const byStatus = {
    400: "The reader rejected this request.",
    403: "Open the reader on the same computer as the server.",
    404: "The requested item could not be found.",
    409: "Reading progress changed in another window.",
    413: "The request was too large or empty.",
    415: "The reader received an unsupported format.",
  };
  if (!error.status) return tr("Check the connection to the local reader.", "请检查与本地阅读服务的连接。");
  return tr(byStatus[error.status] || `Request failed (${error.status}).`, `请求失败（${error.status}）。`);
}

function updateSaveStatus(key) {
  saveStatusKey = key;
  $("saveStatus").textContent = key ? tr(...SAVE_STATUS_LABELS[key]) : "";
}

function saveErrorMessage(error) {
  if (error.status === 409) {
    return tr("Reading progress changed in another window. Reload to retry your changes.",
      "阅读记录已在另一窗口更新。本次更改未保存。请重新载入后重试。");
  }
  const detail = apiErrorMessage(error);
  return tr(`Changes were not saved. ${detail} Reload to try again.`, `更改未保存：${detail} 请重新载入后重试。`);
}

async function loadEverything() {
  const [catalogData, stateData] = await Promise.all([
    readJson("/api/catalog"), readJson("/api/state")
  ]);
  readingState = stateData.state || { schemaVersion: 1, items: {} };
  readingState.items ||= {};
  confirmedState = cloneState(readingState);
  revision = stateData.revision || "";
  setCatalog(catalogData, true);
}

function setCatalog(data, initial = false) {
  catalogLoaded = true;
  catalogError = null;
  catalog = Array.isArray(data.items) ? data.items : [];
  byId = new Map(catalog.map((item) => [item.id, item]));
  topics = Array.isArray(data.topics) ? data.topics : [UNCLASSIFIED];
  if (initial) loadReadingScope();
  if (topicFilter && !topics.includes(topicFilter)) topicFilter = "";
  renderCatalogStatus();
  refreshReadingScope();
  renderAll();
}

function renderCatalogStatus() {
  if (catalogError) {
    $("archiveCount").textContent = tr("Couldn’t load the archive", "无法读取归档");
    $("todayList").innerHTML = `<p class="today-empty">${tr("The local reader couldn’t load the archive. Start the reader again and refresh this page.", "本地阅读服务未能读取知识库。请重新运行“打开阅读台”，然后刷新页面。")}</p>`;
    $("allList").innerHTML = `<p class="empty-list">${escapeHtml(apiErrorMessage(catalogError))}</p>`;
    $("referenceSummary").textContent = tr("The local reader couldn’t load your references.", "本地阅读服务未能读取资料。");
    return;
  }
  $("archiveCount").textContent = catalogLoaded
    ? tr(`${catalog.length} archived`, `归档 ${catalog.length} 篇`)
    : tr("Loading archive…", "正在读取归档…");
}

async function refreshCatalogQuietly() {
  if (saveBusy || saveBlocked) return;
  try {
    const data = await readJson("/api/catalog");
    const items = Array.isArray(data.items) ? data.items : [];
    if (items.length === catalog.length &&
        items.every((item, index) => JSON.stringify(item) === JSON.stringify(catalog[index]))) return;
    setCatalog(data);
    announce(tr("Reading shelf updated.", "归档书架已更新。"), 3000);
  } catch (_) { /* Manual refresh offers an explicit error. */ }
}

function updateClock() {
  const p = localDateParts();
  $("nowClock").textContent = `${p.hour}:${p.minute}`;
  const display = displayDate();
  $("sessionDate").textContent = display;
  $("homeDate").textContent = tr(`${display} · Daily Reading`, `${display} · 今日阅读`);
  if (timer.day && timer.day !== localDay()) {
    timer = freshTimer();
    saveTimer();
    if (libraryMode === "daily") {
      todayIds = chooseToday(false);
      renderToday();
    }
  }
}

function freshTimer() {
  return { day: localDay(), remaining: SESSION_SECONDS, runningSince: null, started: false };
}

function loadTimer() {
  try {
    const saved = JSON.parse(localStorage.getItem(TIMER_KEY) || "null");
    if (saved && saved.day === localDay() && Number.isFinite(saved.remaining)) {
      timer = {
        day: saved.day,
        remaining: Math.max(0, Math.min(SESSION_SECONDS, Math.floor(saved.remaining))),
        runningSince: Number.isFinite(saved.runningSince) ? saved.runningSince : null,
        started: !!saved.started
      };
      return;
    }
  } catch (_) { /* Reset damaged local timer data. */ }
  timer = freshTimer();
  saveTimer();
}

function saveTimer() {
  try { localStorage.setItem(TIMER_KEY, JSON.stringify(timer)); } catch (_) { /* Timer still works in this tab. */ }
}

function remainingSeconds() {
  if (!timer.runningSince) return timer.remaining;
  return Math.max(0, timer.remaining - Math.floor((Date.now() - timer.runningSince) / 1000));
}

function renderTimer() {
  const remaining = remainingSeconds();
  if (remaining === 0 && timer.runningSince) {
    timer.remaining = 0;
    timer.runningSince = null;
    saveTimer();
    announce(tr("Your 30-minute session is complete. Keep reading or come back tomorrow.", "本次 30 分钟阅读结束。你可以继续读，也可以明天再来。"), 6000);
  }
  const mins = String(Math.floor(remaining / 60)).padStart(2, "0");
  const secs = String(remaining % 60).padStart(2, "0");
  $("timerDisplay").textContent = `${mins}:${secs}`;
  $("timerFill").style.width = `${((SESSION_SECONDS - remaining) / SESSION_SECONDS) * 100}%`;
  const running = !!timer.runningSince;
  $("timerStatus").textContent = remaining === 0 ? tr("Finished", "本次结束") : running ? tr("Reading", "正在阅读") : timer.started ? tr("Paused", "已暂停") : tr("Ready", "准备开始");
  $("timerToggle").textContent = remaining === 0 ? tr("Read another 30 minutes", "再读 30 分钟") : running ? tr("Pause", "暂停") : timer.started ? tr("Resume", "继续阅读") : tr("Start reading", "开始阅读");
}

function toggleTimer() {
  const left = remainingSeconds();
  if (timer.runningSince) {
    timer.remaining = left;
    timer.runningSince = null;
  } else {
    if (left === 0) timer.remaining = SESSION_SECONDS;
    timer.runningSince = Date.now();
    timer.started = true;
  }
  saveTimer();
  renderTimer();
}

function resetTimer() {
  timer = freshTimer();
  saveTimer();
  renderTimer();
}

function sortItems(items) {
  const mode = $("sortSelect").value;
  const sorted = [...items];
  sorted.sort((a, b) => {
    if (mode === "shortest") return minutesOf(a) - minutesOf(b) || String(b.date).localeCompare(String(a.date));
    const compared = String(a.date || "").localeCompare(String(b.date || ""));
    return mode === "oldest" ? compared || String(a.title).localeCompare(String(b.title)) : -compared || String(a.title).localeCompare(String(b.title));
  });
  return sorted;
}

function queueCandidates(exclude = new Set()) {
  const eligible = catalog.filter((item) => !exclude.has(item.id) &&
    useOf(item) === "daily" && inReadingScope(item) && ["unread", "reading"].includes(statusOf(item.id)));
  return sortItems(eligible).sort((a, b) => (statusOf(a.id) === "reading" ? -1 : 0) - (statusOf(b.id) === "reading" ? -1 : 0));
}

function chooseToday(forceNew) {
  const scope = topicFilter || tagFilter ? JSON.stringify([topicFilter, tagFilter]) : "";
  const key = PICKS_PREFIX + localDay() + scope;
  let stored = [];
  try { stored = JSON.parse(localStorage.getItem(key) || "[]"); } catch (_) { /* ignore */ }
  if (!Array.isArray(stored)) stored = [];
  const storedCount = stored.length;
  stored = stored.filter((id) => {
    const item = byId.get(id);
    return item && useOf(item) === "daily" && inReadingScope(item);
  });
  if (!forceNew && stored.length && stored.length === storedCount) return stored;
  const previous = new Set(forceNew ? stored : []);
  let candidates = queueCandidates(previous);
  if (!candidates.length) candidates = queueCandidates();
  let budget = SESSION_SECONDS / 60;
  const picks = [];
  for (const item of candidates) {
    if (picks.length >= 5) break;
    const minutes = minutesOf(item);
    if (picks.length > 0 && minutes > budget) continue;
    picks.push(item.id);
    budget -= minutes;
    if (budget <= 0) break;
  }
  try { localStorage.setItem(key, JSON.stringify(picks)); } catch (_) { /* this tab still uses the picks */ }
  return picks;
}

function renderAllList() {
  const query = $("searchInput").value.trim().toLocaleLowerCase();
  const filter = $("statusFilter").value;
  const isReference = libraryMode === "reference";
  const matches = sortItems(catalog.filter((item) => {
    if (!inLibrary(item)) return false;
    if (batchReview && !isReference) return batchIds.has(item.id);
    if (!inReadingScope(item)) return false;
    const status = statusOf(item.id);
    if (filter === "queue" && !["unread", "reading"].includes(status)) return false;
    if (filter !== "queue" && filter !== "all" && status !== filter) return false;
    if (!query) return true;
    const topic = topicOf(item);
    const fields = [item.title, item.path, item.type, item.source, item.summaryTitle, topic, TOPIC_NAMES_EN[topic], ...tagsOf(item)];
    if (isReference) {
      fields.push(...(USE_LABELS[useOf(item)] || []), item.referenceSearch);
      const text = fields.filter(Boolean).join(" ").toLocaleLowerCase();
      return query.split(/\s+/u).every((term) => text.includes(term));
    }
    return fields.some((part) => String(part || "").toLocaleLowerCase().includes(query));
  }));
  const shown = matches.slice(0, visibleCount);
  const count = matches.length;
  const noun = count === 1 ? "item" : "items";
  const summary = batchReview ? tr(`${count} selected`, `${count} 篇已选`)
    : tr(`${count} ${noun}${query ? " found" : ""}`, `${count} 篇${query ? "匹配" : ""}`);
  $("listSummary").hidden = isReference;
  $("allList").hidden = isReference;
  $("loadMoreButton").hidden = isReference || shown.length >= matches.length;
  batchVisibleIds = new Set(isReference ? [] : shown.map((item) => item.id));
  if (!batchSaving) {
    for (const id of batchIds) {
      const item = byId.get(id);
      if (!item || useOf(item) !== "daily") batchIds.delete(id);
    }
  }
  renderBatchControls();
  if (isReference) {
    renderReferences(shown, summary, matches.length);
    return;
  }
  $("listSummary").textContent = summary;
  $("allList").innerHTML = shown.length ? shown.map((item) => `
    <div class="shelf-item ${selectedId === item.id ? "is-selected" : ""}${batchSelecting ? " batch-selectable" : ""}">
      ${batchSelecting ? batchCheckbox(item) : ""}
      <button class="shelf-open" type="button" data-open="${escapeHtml(item.id)}">
        <span class="shelf-item-title">${escapeHtml(item.title || item.path)}</span>
        <span class="shelf-item-meta">
          <span>${escapeHtml(shortDate(item.date))}</span>
          <span>${readingTime(item)}</span>
          <span class="shelf-item-status">${escapeHtml(statusLabel(statusOf(item.id)))}</span>
        </span>
        ${cardClassification(item)}
      </button>
      ${batchSelecting ? "" : completionButton(item)}
    </div>`).join("") : `<p class="empty-list">${tr("No matches. Try changing the topic, tag, search, or status.", "没有匹配的归档。可调整主题、标签、关键词或状态。")}</p>`;
}

function batchCheckbox(item) {
  const label = tr(`Select ${item.title || item.path}`, `选择《${item.title || item.path}》`);
  return `<label class="batch-check-target"><input class="batch-checkbox" type="checkbox"
    data-batch-id="${escapeHtml(item.id)}" aria-label="${escapeHtml(label)}"
    ${batchIds.has(item.id) ? "checked" : ""}${batchSaving ? " disabled" : ""}></label>`;
}

function clearBatchSelection() {
  batchIds.clear();
  batchReview = false;
  $("batchUse").value = "";
}

function renderBatchControls() {
  const isDaily = libraryMode === "daily";
  const button = $("batchSelectionButton");
  button.hidden = !isDaily;
  button.disabled = batchSaving;
  button.textContent = batchSelecting ? tr("Exit selection", "退出多选") : tr("Select multiple", "多选");
  button.setAttribute("aria-pressed", String(batchSelecting));
  $("batchMoveForm").hidden = !isDaily || !batchSelecting;
  if (!isDaily || !batchSelecting) return;
  const hiddenCount = [...batchIds].filter((id) => !batchVisibleIds.has(id)).length;
  const hidden = hiddenCount ? tr(` (${hiddenCount} hidden)`, `，其中 ${hiddenCount} 篇未显示`) : "";
  $("batchSelectionCount").textContent = tr(`${batchIds.size} selected`, `已选 ${batchIds.size} 篇`) + hidden;
  const review = $("batchReviewButton");
  review.disabled = batchSaving || !batchIds.size;
  review.textContent = batchReview ? tr("Back to results", "回到结果") : tr("Show selected only", "只看已选");
  review.setAttribute("aria-pressed", String(batchReview));
  $("batchClearButton").disabled = batchSaving || !batchIds.size;
  $("batchUse").disabled = batchSaving;
  $("batchMoveButton").disabled = batchSaving || saveBlocked || !batchIds.size || !$("batchUse").value;
  $("batchMoveButton").textContent = batchSaving ? tr("Moving…", "正在移动…") : tr("Move to reference library", "移到按需查阅");
}

function onBatchSelectionChange(event) {
  const checkbox = event.target.closest("input[data-batch-id]");
  if (!checkbox || !batchSelecting || batchSaving) return;
  const id = checkbox.dataset.batchId;
  if (checkbox.checked && !batchIds.has(id) && batchIds.size >= MAX_BATCH_SIZE) {
    checkbox.checked = false;
    announce(tr(`Move up to ${MAX_BATCH_SIZE} items at a time.`, `一次最多移动 ${MAX_BATCH_SIZE} 篇。`));
    return;
  }
  if (checkbox.checked) batchIds.add(id);
  else batchIds.delete(id);
  if (!batchReview) {
    renderBatchControls();
    return;
  }
  if (!batchIds.size) batchReview = false;
  renderAllList();
  (batchIds.size ? $("batchReviewButton") : $("searchInput")).focus();
}

function moveSelectedToReferences(event) {
  event.preventDefault();
  const use = $("batchUse").value;
  if (!batchSelecting || batchSaving || !batchIds.size || !Object.hasOwn(USE_LABELS, use) || use === "daily") return;
  const changes = Object.fromEntries([...batchIds].map((id) => [id, { useOverride: use }]));
  const count = batchIds.size;
  batchSaving = true;
  const queued = enqueueChanges(changes, {
    optimistic: false,
    onSaved() {
      batchSaving = false;
      clearBatchSelection();
      const category = useLabel(use);
      announce(tr(`Moved ${count} to Reference Library · ${category}.`, `已将 ${count} 篇移到「按需查阅 · ${category}」。`), 5000);
    },
    onFailed() {
      batchSaving = false;
    },
  });
  if (!queued) {
    batchSaving = false;
    renderBatchControls();
  }
}

function renderReferences(items, summary, total) {
  $("referenceSummary").textContent = summary;
  for (const button of $("referenceKinds").querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(button.dataset.use === referenceKind));
  }
  $("referenceList").innerHTML = items.length ? items.map((item) => `
    <button class="reference-card" type="button" data-open="${escapeHtml(item.id)}">
      <span class="reference-card-kind">${escapeHtml(useLabel(useOf(item)))}</span>
      <span class="shelf-item-title">${escapeHtml(item.title || item.path)}</span>
      ${cardClassification(item)}
    </button>`).join("") : `<p class="empty-list">${tr("No references matched. Try a different search, category, or tag.", "没有匹配的资料。可试试其他关键词、类别或标签。")}</p>`;
  $("referenceMoreButton").hidden = items.length >= total;
}

function renderToday() {
  const items = todayIds.map((id) => byId.get(id)).filter((item) => item && useOf(item) === "daily");
  $("todayList").innerHTML = items.length ? items.map((item, index) => `
    <div class="today-item">
      <button class="today-open" type="button" data-open="${escapeHtml(item.id)}">
        <span class="today-index">${String(index + 1).padStart(2, "0")}</span>
        <span>
          <span class="today-title">${escapeHtml(item.title || item.path)}</span>
          <span class="today-sub">${escapeHtml(shortDate(item.date))} · ${escapeHtml(statusLabel(statusOf(item.id)))}${item.summaryPath ? tr(" · Includes a companion summary", " · 含配套笔记") : ""}</span>
          ${cardClassification(item)}
        </span>
        <span class="today-time">${readingTime(item)}</span>
      </button>
      ${completionButton(item)}
    </div>`).join("") : `<p class="today-empty">${topicFilter || tagFilter
      ? tr("Nothing to read with these filters. Adjust the filters or find completed items on the shelf.", "当前主题和标签下没有待读材料。可以调整筛选，或在书架查看已完成的文章。")
      : tr("Your queue is empty. Find completed items on the shelf.", "队列里没有待读材料了。可以在书架查看已完成的文章。")}</p>`;
}

function cardClassification(item) {
  const tags = tagsOf(item).slice(0, 2).map((tag) => `#${tag}`);
  return `<span class="card-classification">${escapeHtml([topicLabel(topicOf(item)), ...tags].join(" · "))}</span>`;
}

function renderReaderClassification() {
  const item = byId.get(selectedId) || selectedPayload?.item;
  if (!item) return;
  const topic = topicOf(item);
  const tags = tagsOf(item);
  const use = useOf(item);
  const record = recordOf(item.id);
  const isManual = record.topicOverride != null || record.tagsOverride != null || record.useOverride != null;
  const chips = $("readerClassification");
  const classification = JSON.stringify([uiLanguage, topic, tags, use, isManual]);
  if (chips.dataset.classification === classification) return;
  chips.dataset.classification = classification;
  const useName = useLabel(use);
  const editUseLabel = tr(`Edit reading use (${useName})`, `编辑阅读用途，当前为${useName}`);
  chips.innerHTML =
    `<button class="use-chip" type="button" data-edit-use aria-label="${escapeHtml(editUseLabel)}">${escapeHtml(useName)}</button>` +
    `<button class="topic-chip" type="button" data-topic="${escapeHtml(topic)}">${escapeHtml(topicLabel(topic))}</button>` +
    tags.map((tag) => `<button class="tag-chip" type="button" data-tag="${escapeHtml(tagKey(tag))}">#${escapeHtml(tag)}</button>`).join("") +
    `<span class="classification-origin">${isManual ? tr("Edited manually", "已手动调整") : tr("Categorized automatically", "自动分类")}</span>`;
  $("resetClassification").disabled = !isManual;
}

function fillClassificationEditor() {
  const item = byId.get(selectedId);
  if (!item) return;
  $("editTopic").innerHTML = topics.map((topic) => selectOption(topic, topicLabel(topic))).join("");
  $("editTopic").value = topicOf(item);
  $("editTags").value = tagsOf(item).join(", ");
  const automatic = tr("Automatic", "自动");
  $("editUse").innerHTML = selectOption("", `${automatic} · ${useLabel(item.use ?? "daily")}`) +
    Object.keys(USE_LABELS).map((value) => selectOption(value, useLabel(value))).join("");
  $("editUse").value = recordOf(item.id).useOverride ?? "";
  $("classificationEvidence").textContent = item.topicEvidence ? tr(
    item.topic === UNCLASSIFIED ? "The title and existing tags gave no clear clue to the topic."
      : "Automatic topic based on the title and existing tags.",
    `主题依据 · ${item.topicEvidence}`) : "";
  $("useEvidence").textContent = item.useEvidence ? tr(
    item.useEvidence === "归档标注的阅读用途" ? "Reading use specified in archive metadata."
      : "Automatic reading use based on the archive type, title, or main heading.",
    `用途依据 · ${item.useEvidence}`) : "";
}

function saveClassification(event) {
  event.preventDefault();
  const item = byId.get(selectedId);
  if (!item) return;
  const topic = $("editTopic").value;
  const tags = [];
  const seen = new Set();
  for (const value of $("editTags").value.split(/[,，、]/u)) {
    const tag = value.trim().replace(/^#+\s*/u, "");
    const key = tagKey(tag);
    if (!tag || seen.has(key)) continue;
    tags.push(tag);
    seen.add(key);
  }
  if (tags.length > MAX_TAGS || tags.some((tag) => [...tag].length > MAX_TAG_LENGTH)) {
    announce(tr(`Use up to ${MAX_TAGS} tags and ${MAX_TAG_LENGTH} characters per tag.`, `请保留最多 ${MAX_TAGS} 个标签，每个不超过 ${MAX_TAG_LENGTH} 个字。`), 5000);
    return;
  }
  const change = {};
  const useOverride = $("editUse").value || null;
  if (useOverride !== (recordOf(item.id).useOverride ?? null)) change.useOverride = useOverride;
  if (topic !== topicOf(item)) change.topicOverride = topic;
  if (JSON.stringify(tags) !== JSON.stringify(tagsOf(item))) change.tagsOverride = tags;
  if (!Object.keys(change).length || enqueueSave(item.id, change)) closeClassificationEditor();
}

function closeClassificationEditor() {
  $("classificationEditor").open = false;
  $("classificationEditor").querySelector("summary").focus();
}

function completionButton(item) {
  const done = statusOf(item.id) === "done";
  const title = item.title || item.path;
  const label = done ? tr(`Undo completion for ${title}`, `撤销《${title}》的完成状态`) : tr(`Mark ${title} as complete`, `将《${title}》标记完成`);
  return `<button class="quick-complete ${done ? "is-done" : ""}" type="button" data-complete="${escapeHtml(item.id)}" aria-label="${escapeHtml(label)}">${done ? tr("Undo completion", "撤销完成") : tr("Mark as complete", "标记完成")}</button>`;
}

function renderAll() {
  renderAllList();
  renderToday();
  if (selectedId) {
    renderReaderStatus();
    renderReaderClassification();
  }
}

function renderReaderStatus() {
  const status = statusOf(selectedId);
  $("readerKicker").textContent = tr(`${statusLabel(status)} · Saved material`, `${statusLabel(status)} · 来源归档`);
  const done = status === "done";
  const title = (selectedPayload?.item || byId.get(selectedId))?.title || tr("current item", "当前材料");
  for (const button of [$("readerDoneButton"), $("readerBottomDoneButton")]) {
    button.textContent = done ? tr("Undo completion", "撤销完成") : tr("Mark as complete", "标记完成");
    button.setAttribute("aria-label", done ? tr(`Undo completion for ${title}`, `撤销《${title}》的完成状态`) : tr(`Mark ${title} as complete`, `将《${title}》标记完成`));
    button.classList.toggle("button-primary", !done);
    button.classList.toggle("button-outline", done);
  }
  const item = byId.get(selectedId) || selectedPayload?.item;
  const isDailyItem = item && useOf(item) === "daily";
  $("readerLaterButton").hidden = !isDailyItem;
  $("readerNextButton").hidden = libraryMode === "reference";
  $("readerLaterButton").textContent = status === "later" ? tr("Return to queue", "放回队列") : tr("Read later", "稍后读");
  const progress = Math.round(Number(recordOf(selectedId).progress) || 0);
  $("progressText").textContent = progress > 0 ? tr(`Last read to about ${progress}%`, `上次读到约 ${progress}%`) : tr("Your place is saved as you scroll.", "滚动阅读时会记录当前位置。");
}

function updateLibraryLabels() {
  const isReference = libraryMode === "reference";
  $("shelfHeading").textContent = isReference ? tr("Reference Filters", "资料筛选") : tr("Reading Shelf", "归档书架");
  $("searchInput").placeholder = isReference ? tr("Search by book, course, or keyword", "搜索书名、课程或资料关键词") : tr("Search title, source, or tag", "搜索标题、来源或标签");
  $("backLabel").textContent = isReference ? tr("Back to references", "返回资料库") : tr("Back to queue", "返回队列");
}

function showHome() {
  openRequest += 1;
  saveNoteDraft();
  $("classificationEditor").open = false;
  $("readerPanel").hidden = true;
  const isReference = libraryMode === "reference";
  $("homePanel").hidden = isReference;
  $("referencePanel").hidden = !isReference;
  $("sessionPanel").hidden = isReference;
  updateLibraryLabels();
  $("dailyModeButton").setAttribute("aria-pressed", String(!isReference));
  $("referenceModeButton").setAttribute("aria-pressed", String(isReference));
  document.body.classList.remove("reading-open");
  selectedId = null;
  selectedPayload = null;
  renderAllList();
  window.scrollTo({ top: 0, behavior: "auto" });
}

async function openItem(id, preferredTab = "source") {
  if (!byId.has(id)) return;
  clearTimeout(progressTimer);
  if (selectedId && selectedId !== id) saveNoteDraft();
  const request = ++openRequest;
  updateSaveStatus("opening");
  try {
    const payload = await readJson(`/api/item?id=${encodeURIComponent(id)}`);
    if (request !== openRequest) return;
    $("classificationEditor").open = false;
    selectedId = id;
    selectedPayload = payload;
    const item = payload.item || byId.get(id);
    $("readerTitle").textContent = item.title || item.path;
    renderReaderMeta(item);
    const url = typeof item.source === "string" && /^https?:\/\//i.test(item.source.trim()) ? item.source.trim() : "";
    $("sourceLink").hidden = !url;
    if (url) $("sourceLink").href = url;
    $("summaryTab").hidden = !payload.summaryBody;
    $("noteInput").value = recordOf(id).note || "";
    currentTab = payload.summaryBody && preferredTab === "summary" ? "summary" : "source";
    $("homePanel").hidden = true;
    $("referencePanel").hidden = true;
    $("readerPanel").hidden = false;
    document.body.classList.add("reading-open");
    renderArticle();
    renderReaderStatus();
    renderReaderClassification();
    renderAllList();
    updateSaveStatus("");
    if (useOf(item) === "daily" && ["unread", "later"].includes(statusOf(id))) enqueueSave(id, { status: "reading" });
    requestAnimationFrame(() => {
      if (currentTab === "source") resumePosition();
      else window.scrollTo({ top: 0, behavior: "auto" });
    });
  } catch (error) {
    if (request !== openRequest) return;
    updateSaveStatus("");
    const detail = apiErrorMessage(error);
    announce(tr(`Couldn’t open this item. ${detail}`, `打开失败：${detail}`), 6000);
  }
}

function setTab(tab) {
  if (tab === "summary" && !selectedPayload?.summaryBody) return;
  currentTab = tab;
  renderArticle();
  window.scrollTo({ top: 0, behavior: "auto" });
}

function renderArticle() {
  $("sourceTab").setAttribute("aria-selected", String(currentTab === "source"));
  $("summaryTab").setAttribute("aria-selected", String(currentTab === "summary"));
  const item = selectedPayload?.item || byId.get(selectedId);
  const base = currentTab === "summary" ? item?.summaryPath || item?.path : item?.path;
  const body = currentTab === "summary" ? selectedPayload?.summaryBody : selectedPayload?.body;
  $("articleBody").innerHTML = markdownToHtml(body || "", base || "");
}

function resumePosition() {
  const progress = Number(recordOf(selectedId).progress || 0);
  if (progress < 5 || progress >= 100) {
    window.scrollTo({ top: 0, behavior: "auto" });
    return;
  }
  const article = $("articleBody");
  const top = article.getBoundingClientRect().top + window.scrollY;
  const travel = Math.max(0, article.offsetHeight - window.innerHeight * .75);
  window.scrollTo({ top: Math.max(0, top + travel * progress / 100), behavior: "auto" });
}

function saveNoteDraft() {
  clearTimeout(noteTimer);
  if (!selectedId) return;
  const value = $("noteInput").value;
  if (value !== (recordOf(selectedId).note || "")) enqueueSave(selectedId, { note: value });
}

function onScroll() {
  if (!selectedId || currentTab !== "source" || $("readerPanel").hidden || saveBlocked || statusOf(selectedId) === "done") return;
  const article = $("articleBody");
  const top = article.getBoundingClientRect().top + window.scrollY;
  const travel = Math.max(1, article.offsetHeight - window.innerHeight * .75);
  const progress = Math.max(0, Math.min(100, Math.round(((window.scrollY - top) / travel) * 100)));
  const saved = Number(recordOf(selectedId).progress || 0);
  if (progress <= saved + 3 || progress >= 100) return;
  clearTimeout(progressTimer);
  const id = selectedId;
  progressTimer = setTimeout(() => enqueueSave(id, { progress }), 700);
}

function nextItem() {
  const i = todayIds.indexOf(selectedId);
  const next = todayIds.slice(i + 1).find((id) => {
    const item = byId.get(id);
    return item && useOf(item) === "daily" && ["unread", "reading"].includes(statusOf(id));
  }) ||
    queueCandidates(new Set([selectedId]))[0]?.id;
  if (next) openItem(next);
  else announce(tr("There’s nothing else in this queue.", "队列里暂时没有下一篇。"), 4000);
}

function enqueueSave(id, delta) {
  return enqueueChanges({ [id]: delta });
}

function applyOptimisticChanges(changes) {
  for (const [id, delta] of Object.entries(changes)) {
    readingState.items[id] = { ...recordOf(id), ...delta };
  }
}

function enqueueChanges(changes, { optimistic = true, onSaved, onFailed } = {}) {
  if (saveBlocked) {
    announce(tr("Reload your reading progress first.", "请先重新载入阅读记录。"), 4500);
    return false;
  }
  readingState.items ||= {};
  const changesClassification = Object.values(changes).some((delta) =>
    "topicOverride" in delta || "tagsOverride" in delta || "useOverride" in delta);
  pendingSaves.push({ changes, optimistic, changesClassification, onSaved, onFailed });
  if (optimistic) {
    applyOptimisticChanges(changes);
    if (changesClassification) refreshReadingScope();
  }
  renderAll();
  updateSaveStatus("saving");
  void flushSaves();
  return true;
}

async function flushSaves() {
  if (saveBusy || saveBlocked) return;
  saveBusy = true;
  while (pendingSaves.length && !saveBlocked) {
    const change = pendingSaves.shift();
    try {
      const data = await readJson("/api/state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ revision, changes: change.changes })
      });
      revision = data.revision;
      readingState = data.state;
      readingState.items ||= {};
      confirmedState = cloneState(readingState);
      for (const pending of pendingSaves) {
        if (pending.optimistic) applyOptimisticChanges(pending.changes);
      }
      updateSaveStatus(pendingSaves.length ? "saving" : "saved");
      change.onSaved?.();
      if (change.changesClassification) refreshReadingScope();
      renderAll();
    } catch (error) {
      readingState = cloneState(confirmedState);
      for (const failed of [change, ...pendingSaves]) failed.onFailed?.();
      pendingSaves = [];
      saveBlocked = true;
      saveError = error;
      $("saveErrorText").textContent = saveErrorMessage(error);
      $("conflictBanner").hidden = false;
      updateSaveStatus("unsaved");
      refreshReadingScope();
      renderAll();
      announce($("saveErrorText").textContent, 5500);
      break;
    }
  }
  saveBusy = false;
}

async function reloadState() {
  const draft = $("noteInput").value;
  try {
    const data = await readJson("/api/state");
    readingState = data.state;
    readingState.items ||= {};
    confirmedState = cloneState(readingState);
    revision = data.revision;
    pendingSaves = [];
    saveBlocked = false;
    saveError = null;
    $("conflictBanner").hidden = true;
    if (selectedId) $("noteInput").value = draft;
    updateSaveStatus("reloaded");
    refreshReadingScope();
    renderAll();
    announce(tr("Reading progress reloaded. Retry unsaved changes. Your note draft is still in the text box.", "已重新载入进度。未保存的状态操作请重做；笔记草稿仍在输入框。"), 6000);
  } catch (error) {
    const detail = apiErrorMessage(error);
    announce(tr(`Couldn’t reload progress. ${detail}`, `重新载入失败：${detail}`), 5000);
  }
}

function onDelegatedOpen(event) {
  const target = event.target.closest("[data-open]");
  if (!target) return;
  openItem(target.dataset.open);
}

function toggleCompletion(id) {
  if (!byId.has(id)) return;
  const undo = statusOf(id) === "done";
  if (selectedId === id) {
    clearTimeout(progressTimer);
    saveNoteDraft();
  }
  if (enqueueSave(id, undo ? { status: "unread", progress: 0 } : { status: "done", progress: 100 })) {
    if (undo && selectedId === id) window.scrollTo({ top: 0, behavior: "auto" });
    announce(undo ? tr("Undoing completion…", "正在撤销完成状态…") : tr("Saving completion…", "正在保存完成状态…"), 2500);
  }
}

function onDelegatedComplete(event) {
  const target = event.target.closest("[data-complete]");
  if (!target) return;
  event.stopPropagation();
  toggleCompletion(target.dataset.complete);
}

function normalizeVaultPath(raw, basePath) {
  let value = String(raw || "").trim();
  if (!value || value.startsWith("#")) return null;
  if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(value)) return null;
  value = value.replace(/\\/g, "/").split(/[?#]/, 1)[0];
  try { value = decodeURIComponent(value); } catch (_) { /* keep the literal path */ }
  const parts = value.startsWith("/") ? [] : String(basePath || "").split("/").slice(0, -1).filter(Boolean);
  for (const part of value.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") {
      if (!parts.length) return null;
      parts.pop();
    } else if (part.includes(":")) {
      return null;
    } else {
      parts.push(part);
    }
  }
  return parts.join("/");
}

function linkData(raw, basePath) {
  const value = String(raw || "").trim().replace(/^<([^>]+)>$/, "$1");
  if (/^https?:\/\//i.test(value)) {
    return { href: value, attrs: ' target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer"' };
  }
  if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(value)) return null;
  const target = normalizeVaultPath(value, basePath);
  if (!target) return null;
  const matching = catalog.find((item) => item.path === target || item.summaryPath === target);
  if (matching) {
    const tab = matching.summaryPath === target ? "summary" : "source";
    return {
      href: "#阅读归档",
      attrs: ` data-entry-id="${escapeHtml(matching.id)}" data-entry-tab="${tab}"`
    };
  }
  const encoded = target.split("/").map(encodeURIComponent).join("/");
  return { href: `/asset/${encoded}`, attrs: ' target="_blank" rel="noopener noreferrer"' };
}

function inlineMarkdown(raw, basePath) {
  const replacements = [];
  const token = (html) => {
    const index = replacements.push(html) - 1;
    return `\uE000${index}\uE001`;
  };
  let text = String(raw || "");
  text = text.replace(/!\[\[([^\]]+)\]\]/g, (_, inside) => {
    const [path, alt = ""] = inside.split("|");
    const link = linkData(path, basePath);
    if (!link) return token(escapeHtml(inside));
    return token(`<img src="${escapeHtml(link.href)}" alt="${escapeHtml(alt)}" loading="lazy" referrerpolicy="no-referrer">`);
  });
  text = text.replace(/(!?)\[([^\]]*)\]\(((?:[^()]|\([^()]*\))+)\)/g, (_, bang, label, href) => {
    const link = linkData(href, basePath);
    if (!link) return token(escapeHtml(label || href));
    if (bang) {
      return token(`<img src="${escapeHtml(link.href)}" alt="${escapeHtml(label)}" loading="lazy" referrerpolicy="no-referrer">`);
    }
    return token(`<a href="${escapeHtml(link.href)}"${link.attrs}>${escapeHtml(label || href)}</a>`);
  });
  text = text.replace(/(?<!!)\[\[([^\]]+)\]\]/g, (_, inside) => {
    const [path, label = path] = inside.split("|");
    const link = linkData(path, basePath);
    if (!link) return token(escapeHtml(label));
    return token(`<a href="${escapeHtml(link.href)}"${link.attrs}>${escapeHtml(label)}</a>`);
  });
  text = text.replace(/`([^`]+)`/g, (_, code) => token(`<code>${escapeHtml(code)}</code>`));
  let rendered = escapeHtml(text);
  rendered = rendered.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/~~([^~]+)~~/g, "<del>$1</del>")
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  return rendered.replace(/\uE000(\d+)\uE001/g, (_, index) => replacements[Number(index)] || "");
}

function stripFrontmatter(raw) {
  const text = String(raw || "").replace(/\r\n?/g, "\n");
  if (!text.startsWith("---\n")) return text;
  const end = text.indexOf("\n---\n", 4);
  return end >= 0 && end < 4000 ? text.slice(end + 5) : text;
}

function splitTableCells(line) {
  return String(line).trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map((cell) => cell.trim());
}

function isTableRule(line) {
  return /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function markdownToHtml(raw, basePath) {
  const lines = stripFrontmatter(raw).split("\n");
  const blocks = [];
  let paragraph = [];
  let listType = "";
  let listItems = [];
  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push(`<p>${inlineMarkdown(paragraph.join(" "), basePath)}</p>`);
      paragraph = [];
    }
  };
  const flushList = () => {
    if (listItems.length) {
      blocks.push(`<${listType}>${listItems.map((item) => `<li>${inlineMarkdown(item, basePath)}</li>`).join("")}</${listType}>`);
      listItems = [];
      listType = "";
    }
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*```/.test(line)) {
      flushParagraph(); flushList();
      const code = [];
      while (++i < lines.length && !/^\s*```/.test(lines[i])) code.push(lines[i]);
      blocks.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
      continue;
    }
    if (!line.trim()) { flushParagraph(); flushList(); continue; }
    if (line.includes("|") && i + 1 < lines.length && isTableRule(lines[i + 1])) {
      flushParagraph(); flushList();
      const headers = splitTableCells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim() && lines[i].includes("|")) {
        rows.push(splitTableCells(lines[i]));
        i++;
      }
      i--;
      blocks.push(`<div class="table-wrap"><table><thead><tr>${headers.map((cell) => `<th>${inlineMarkdown(cell, basePath)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${inlineMarkdown(cell, basePath)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph(); flushList();
      const level = heading[1].length;
      blocks.push(`<h${level}>${inlineMarkdown(heading[2], basePath)}</h${level}>`);
      continue;
    }
    if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      flushParagraph(); flushList(); blocks.push("<hr>"); continue;
    }
    if (/^\s*>/.test(line)) {
      flushParagraph(); flushList();
      const quote = [line.replace(/^\s*>\s?/, "")];
      while (i + 1 < lines.length && /^\s*>/.test(lines[i + 1])) quote.push(lines[++i].replace(/^\s*>\s?/, ""));
      blocks.push(`<blockquote><p>${inlineMarkdown(quote.join(" "), basePath)}</p></blockquote>`);
      continue;
    }
    const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      flushParagraph();
      const type = unordered ? "ul" : "ol";
      if (listType && listType !== type) flushList();
      listType = type;
      listItems.push((unordered || ordered)[1]);
      continue;
    }
    if (listItems.length) flushList();
    paragraph.push(line.trim());
  }
  flushParagraph(); flushList();
  return blocks.join("\n") || `<p>${tr("This item has no text to display. Open the original source or view the attachments in Obsidian.", "这份归档没有可显示的文字。请打开原始来源或在 Obsidian 中查看附件。")}</p>`;
}

function bindEvents() {
  $("uiLanguage").addEventListener("change", (event) => {
    setLanguage(event.target.value);
    try { localStorage.setItem(LANGUAGE_KEY, uiLanguage); }
    catch (_) { /* The selection still works in this tab. */ }
  });
  $("dailyModeButton").addEventListener("click", () => switchLibrary("daily"));
  $("referenceModeButton").addEventListener("click", () => switchLibrary("reference"));
  $("batchSelectionButton").addEventListener("click", () => {
    batchSelecting = !batchSelecting;
    if (!batchSelecting) clearBatchSelection();
    renderAllList();
  });
  $("batchReviewButton").addEventListener("click", () => {
    batchReview = !batchReview;
    visibleCount = PAGE_SIZE;
    renderAllList();
  });
  $("batchClearButton").addEventListener("click", () => {
    clearBatchSelection();
    renderAllList();
    $("batchSelectionButton").focus();
  });
  $("batchUse").addEventListener("change", renderBatchControls);
  $("batchMoveForm").addEventListener("submit", moveSelectedToReferences);
  $("allList").addEventListener("change", onBatchSelectionChange);
  $("referenceKinds").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-use]");
    if (!button) return;
    referenceKind = button.dataset.use;
    visibleCount = PAGE_SIZE;
    refreshReadingScope();
    renderAllList();
  });
  $("referenceList").addEventListener("click", onDelegatedOpen);
  $("referenceMoreButton").addEventListener("click", () => { visibleCount += PAGE_SIZE; renderAllList(); });
  $("timerToggle").addEventListener("click", toggleTimer);
  $("timerReset").addEventListener("click", resetTimer);
  $("searchInput").addEventListener("input", () => { batchReview = false; visibleCount = PAGE_SIZE; renderAllList(); });
  $("statusFilter").addEventListener("change", () => { batchReview = false; visibleCount = PAGE_SIZE; renderAllList(); });
  $("sortSelect").addEventListener("change", () => { visibleCount = PAGE_SIZE; renderAllList(); });
  $("topicFilter").addEventListener("change", () => setReadingScope($("topicFilter").value, tagFilter));
  $("tagFilter").addEventListener("change", () => setReadingScope(topicFilter, $("tagFilter").value));
  $("clearReadingScope").addEventListener("click", () => setReadingScope("", ""));
  $("readerClassification").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.hasAttribute("data-edit-use")) {
      $("classificationEditor").open = true;
      fillClassificationEditor();
      $("editUse").focus();
      return;
    }
    const item = byId.get(selectedId);
    if (!item) return;
    const use = useOf(item);
    if (use !== "daily") referenceKind = "";
    switchLibrary(use === "daily" ? "daily" : "reference");
    setReadingScope(button.dataset.topic || "", button.dataset.tag || "");
  });
  $("classificationEditor").addEventListener("toggle", () => {
    if ($("classificationEditor").open) fillClassificationEditor();
  });
  $("classificationForm").addEventListener("submit", saveClassification);
  $("resetClassification").addEventListener("click", () => {
    if (selectedId && enqueueSave(selectedId, { topicOverride: null, tagsOverride: null, useOverride: null })) {
      closeClassificationEditor();
    }
  });
  $("loadMoreButton").addEventListener("click", () => { visibleCount += PAGE_SIZE; renderAllList(); });
  $("allList").addEventListener("click", onDelegatedOpen);
  $("allList").addEventListener("click", onDelegatedComplete);
  $("todayList").addEventListener("click", onDelegatedOpen);
  $("todayList").addEventListener("click", onDelegatedComplete);
  $("backButton").addEventListener("click", showHome);
  $("sourceTab").addEventListener("click", () => setTab("source"));
  $("summaryTab").addEventListener("click", () => setTab("summary"));
  $("readerDoneButton").addEventListener("click", () => { if (selectedId) toggleCompletion(selectedId); });
  $("readerBottomDoneButton").addEventListener("click", () => { if (selectedId) toggleCompletion(selectedId); });
  $("readerLaterButton").addEventListener("click", () => {
    if (!selectedId) return;
    const status = statusOf(selectedId) === "later" ? "unread" : "later";
    enqueueSave(selectedId, { status });
    announce(status === "later" ? tr("Moved to Read Later.", "已放到稍后。") : tr("Returned to the reading queue.", "已放回待阅读队列。"), 2500);
  });
  $("saveNoteButton").addEventListener("click", () => {
    if (!selectedId) return;
    saveNoteDraft();
    announce(tr("Saving notes…", "正在保存笔记…"), 2500);
  });
  $("noteInput").addEventListener("input", () => {
    clearTimeout(noteTimer);
    noteTimer = setTimeout(saveNoteDraft, 1200);
  });
  $("readerNextButton").addEventListener("click", nextItem);
  $("reloadStateButton").addEventListener("click", reloadState);
  $("newSelectionButton").addEventListener("click", () => { todayIds = chooseToday(true); renderToday(); });
  $("refreshButton").addEventListener("click", async () => {
    $("refreshButton").disabled = true;
    try {
      setCatalog(await readJson("/api/catalog?refresh=1"));
      announce(tr("Reading shelf refreshed.", "归档书架已刷新。"), 2500);
    }
    catch (error) {
      const detail = apiErrorMessage(error);
      announce(tr(`Couldn’t refresh the archive. ${detail}`, `刷新失败：${detail}`), 5000);
    }
    finally { $("refreshButton").disabled = false; }
  });
  $("articleBody").addEventListener("click", (event) => {
    const link = event.target.closest("a[data-entry-id]");
    if (!link) return;
    event.preventDefault();
    openItem(link.dataset.entryId, link.dataset.entryTab || "source");
  });
  window.addEventListener("scroll", onScroll, { passive: true });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || $("readerPanel").hidden) return;
    if ($("classificationEditor").open) {
      closeClassificationEditor();
    } else {
      showHome();
    }
  });
}

async function main() {
  bindEvents();
  loadTimer();
  setLanguage(loadLanguage());
  if (window.location.hash === "#references") switchLibrary("reference");
  setInterval(() => { updateClock(); renderTimer(); }, 1000);
  setInterval(refreshCatalogQuietly, 5 * 60 * 1000);
  try { await loadEverything(); }
  catch (error) {
    catalogError = error;
    renderCatalogStatus();
  }
}

document.addEventListener("DOMContentLoaded", main);
