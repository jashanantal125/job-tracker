(() => {
  "use strict";

  const CATEGORIES = [
    "Software Engineering", "Cloud & Infrastructure", "Data & AI", "Cybersecurity",
    "Tech Consulting", "Product Management", "Enterprise Platforms", "IT / Tech (General)",
  ];
  const REVIEW = "Needs Review";
  const POLL_MS = 5 * 60 * 1000;
  const SOURCE_LABELS = { jobstreet: "JobStreet", linkedin: "LinkedIn" };
  const KEYS = { status: "mit.status", lastSeen: "mit.lastSeen", filters: "mit.filters" };

  // ------------------------------------------------------------------ storage (never required)
  const store = {
    get(key, fallback) {
      try { const v = localStorage.getItem(key); return v == null ? fallback : JSON.parse(v); }
      catch { return fallback; }
    },
    set(key, value) {
      try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode etc. */ }
    },
  };

  const state = {
    jobs: [],
    health: null,
    status: store.get(KEYS.status, {}),
    // Jobs found after this moment are "new". First visit: last 24 hours.
    seenBefore: store.get(KEYS.lastSeen, null) || new Date(Date.now() - 864e5).toISOString(),
    arrivedWhileOpen: new Set(),
    selectedCats: new Set(),
  };

  const $ = (id) => document.getElementById(id);
  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") node.className = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children.flat()) if (c != null && c !== false) node.append(c);
    return node;
  };
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);

  // ------------------------------------------------------------------ time
  function ago(iso) {
    if (!iso) return "";
    const t = new Date(iso.length === 10 ? iso + "T00:00:00Z" : iso).getTime();
    const s = Math.max(0, (Date.now() - t) / 1000);
    if (iso.length === 10) {
      const d = Math.floor(s / 86400);
      return d <= 0 ? "today" : d === 1 ? "yesterday" : `${d} days ago`;
    }
    if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min ago`;
    if (s < 86400) return `${Math.round(s / 3600)} h ago`;
    const d = Math.round(s / 86400);
    return d === 1 ? "1 day ago" : `${d} days ago`;
  }
  const isNew = (j) => j.active && (j.first_seen > state.seenBefore || state.arrivedWhileOpen.has(j.id));

  // ------------------------------------------------------------------ data
  async function getJson(path) {
    const res = await fetch(`${path}?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`${path}: ${res.status}`);
    return res.json();
  }

  async function load(initial) {
    let jobs, health;
    try {
      [jobs, health] = await Promise.all([getJson("data/jobs.json"), getJson("data/health.json").catch(() => null)]);
    } catch (e) {
      if (initial) $("updated").textContent = "Couldn't load data — try refreshing.";
      return;
    }
    const incoming = jobs.jobs || [];
    if (!initial) {
      const known = new Set(state.jobs.map((j) => j.id));
      const fresh = incoming.filter((j) => j.active && !known.has(j.id) && j.category !== REVIEW);
      fresh.forEach((j) => state.arrivedWhileOpen.add(j.id));
      if (fresh.length) announce(fresh);
    }
    state.jobs = incoming;
    state.health = health;
    renderHeader();
    renderFilters();
    renderJobs();
    renderSources();
  }

  // ------------------------------------------------------------------ alerts
  function announce(fresh) {
    const msg = fresh.length === 1
      ? `New: ${fresh[0].title} — ${fresh[0].company}`
      : `${fresh.length} new internships just posted`;
    toast(msg);
    try {
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification("MY Tech Internships", { body: msg, tag: "mit-new" });
      }
    } catch { /* some mobile browsers only allow notifications from a service worker */ }
  }

  let toastTimer;
  function toast(text) {
    const t = $("toast");
    t.textContent = text;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 6000);
  }

  function renderHeader() {
    const active = state.jobs.filter((j) => j.active && j.category !== REVIEW);
    const fresh = active.filter(isNew);
    const applied = state.jobs.filter((j) => state.status[j.id] === "applied").length;
    const checked = state.health && state.health.checked_at;
    $("updated").textContent = checked
      ? `MNC internships in Malaysia · last checked ${ago(checked)}`
      : "MNC internships in Malaysia";

    document.title = fresh.length ? `(${fresh.length}) MY Tech Internships` : "MY Tech Internships";
    $("alert").hidden = fresh.length === 0;
    $("alert-text").textContent = `${fresh.length} new internship${fresh.length === 1 ? "" : "s"} since your last visit`;

    const companies = new Set(active.map((j) => j.company)).size;
    const stat = (n, label, hot) => el("div", { class: `stat${hot ? " hot" : ""}` }, el("b", {}, String(n)), el("span", {}, label));
    $("stats").replaceChildren(
      stat(fresh.length, "New", fresh.length > 0),
      stat(active.length, "Open internships"),
      stat(companies, "Companies hiring"),
      stat(applied, "Applied"),
    );
  }

  // ------------------------------------------------------------------ filters
  const saved = store.get(KEYS.filters, {});
  for (const c of saved.cats || []) state.selectedCats.add(c);

  function persistFilters() {
    store.set(KEYS.filters, {
      cats: [...state.selectedCats], type: $("f-type").value, city: $("f-city").value,
      status: $("f-status").value, sort: $("f-sort").value,
    });
  }

  function fillSelect(select, values, keep) {
    const current = select.value || keep || "";
    const first = select.options[0];
    select.replaceChildren(first, ...values.map((v) => el("option", { value: v }, v)));
    select.value = values.includes(current) ? current : "";
  }

  function renderFilters() {
    const active = state.jobs.filter((j) => j.active);
    const counts = {};
    for (const j of active) counts[j.category] = (counts[j.category] || 0) + 1;
    $("categories").replaceChildren(...CATEGORIES.map((c) =>
      el("button", {
        class: "chip", type: "button", "aria-pressed": String(state.selectedCats.has(c)),
        onclick: () => {
          state.selectedCats.has(c) ? state.selectedCats.delete(c) : state.selectedCats.add(c);
          persistFilters(); renderFilters(); renderJobs();
        },
      }, c, el("small", {}, String(counts[c] || 0)))));
    fillSelect($("f-type"), [...new Set(state.jobs.map((j) => j.company_type))].sort(), saved.type);
    fillSelect($("f-city"), ["Klang Valley", "Penang / Kedah", "Johor", "Other Malaysia"], saved.city);
  }

  function visibleJobs() {
    const q = $("q").value.trim().toLowerCase();
    const type = $("f-type").value;
    const city = $("f-city").value;
    const status = $("f-status").value;
    const showReview = $("f-review").checked;
    const showClosed = $("f-closed").checked;

    let list = state.jobs.filter((j) => {
      const mine = state.status[j.id];
      if (!showClosed && !j.active) return false;
      if (j.category === REVIEW ? !showReview : (state.selectedCats.size && !state.selectedCats.has(j.category))) return false;
      if (type && j.company_type !== type) return false;
      if (city && j.city_group !== city) return false;
      if (status === "open" && (mine === "applied" || mine === "hidden")) return false;
      if (status === "new" && (!isNew(j) || mine === "hidden")) return false;
      if (["saved", "applied", "hidden"].includes(status) && mine !== status) return false;
      if (q && !`${j.title} ${j.company} ${j.location} ${j.category}`.toLowerCase().includes(q)) return false;
      return true;
    });

    const sort = $("f-sort").value;
    const by = {
      found: (a, b) => b.first_seen.localeCompare(a.first_seen),
      posted: (a, b) => (b.posted_at || b.first_seen).localeCompare(a.posted_at || a.first_seen),
      company: (a, b) => a.company.localeCompare(b.company) || a.title.localeCompare(b.title),
    }[sort];
    return list.sort(by);
  }

  // ------------------------------------------------------------------ jobs
  function setStatus(id, value) {
    if (state.status[id] === value) delete state.status[id];
    else state.status[id] = value;
    store.set(KEYS.status, state.status);
    renderHeader();
    renderJobs();
  }

  function jobCard(j) {
    const mine = state.status[j.id];
    const fresh = isNew(j);
    const url = safeUrl(j.apply_url);
    const sourceLabel = j.source_kind === "portal" ? `via ${SOURCE_LABELS[j.source] || j.source}` : "company careers site";
    const mark = (value, label) => el("button", {
      class: "mark", type: "button", "aria-pressed": String(mine === value), onclick: () => setStatus(j.id, value),
    }, label);

    const also = (j.also_on || []).map((a) => safeUrl(a.url) && el("a", { href: a.url, target: "_blank", rel: "noopener noreferrer" },
      SOURCE_LABELS[a.source] || a.source));

    return el("li", { class: `job${fresh ? " is-new" : ""}${!j.active ? " is-closed" : ""}${mine === "applied" ? " is-applied" : ""}` },
      el("div", {},
        el("p", { class: "job-title" }, j.title),
        el("p", { class: "job-co" }, el("strong", {}, j.company), ` · ${j.location}`),
        el("div", { class: "tags" },
          fresh && el("span", { class: "tag new" }, "NEW"),
          !j.active && el("span", { class: "tag closed" }, "Closed"),
          el("span", { class: "tag cat" }, j.category),
          j.duration && el("span", { class: "tag" }, j.duration),
          el("span", { class: "tag" }, j.company_type),
          el("span", { class: "tag", title: j.first_seen }, `found ${ago(j.first_seen)}`),
          j.posted_at && el("span", { class: "tag" }, `posted ${ago(j.posted_at)}`),
          el("span", { class: "tag" }, sourceLabel),
        ),
      ),
      el("div", { class: "actions" },
        url ? el("a", { class: "apply", href: url, target: "_blank", rel: "noopener noreferrer" }, "Apply ↗") : null,
        el("div", { class: "marks" }, mark("saved", "★ Save"), mark("applied", "✓ Applied"), mark("hidden", "✕ Hide")),
      ),
      j.snippet && el("p", { class: "snippet" }, j.snippet),
      also.some(Boolean) && el("div", { class: "also" }, "Also listed on: ", ...also.filter(Boolean).flatMap((a, i) => (i ? [", ", a] : [a]))),
    );
  }

  function renderJobs() {
    const list = visibleJobs();
    $("count").textContent = `${list.length} internship${list.length === 1 ? "" : "s"}`;
    if (!list.length) {
      const nothingYet = !state.jobs.length;
      $("jobs").replaceChildren(el("li", { class: "empty" }, nothingYet
        ? "No internships found yet. The tracker checks every 30 minutes — see the Sources tab for status."
        : "Nothing matches these filters."));
      return;
    }
    $("jobs").replaceChildren(...list.map(jobCard));
  }

  // ------------------------------------------------------------------ sources
  function renderSources() {
    const h = state.health;
    if (!h) {
      $("health-summary").textContent = "No run recorded yet.";
      $("sources").replaceChildren();
      $("watchlist").replaceChildren();
      return;
    }
    $("health-summary").textContent =
      `Last checked ${ago(h.checked_at)} · ${h.sources_ok} sources working, ${h.sources_failed} failing.`;
    const rows = (h.sources || []).map((s) => el("tr", {},
      el("td", {}, el("span", { class: `dot ${s.ok ? "ok" : "bad"}` }), s.source),
      el("td", {}, String(s.fetched)),
      el("td", {}, String(s.matched)),
      el("td", { class: s.ok ? "" : "err" }, s.ok ? (s.seconds != null ? `${s.seconds}s` : "") : (s.error || "failed")),
    ));
    $("sources").replaceChildren(
      el("thead", {}, el("tr", {}, el("th", {}, "Source"), el("th", {}, "Fetched"), el("th", {}, "Matched"), el("th", {}, "Status"))),
      el("tbody", {}, rows),
    );

    const manual = (h.companies || []).filter((c) => !c.tracked && safeUrl(c.careers));
    const groups = {};
    for (const c of manual) (groups[c.type] = groups[c.type] || []).push(c);
    $("watchlist").replaceChildren(...Object.keys(groups).sort().map((type) => el("div", {},
      el("h3", {}, type),
      el("ul", {}, groups[type].map((c) => el("li", {},
        el("a", { href: c.careers, target: "_blank", rel: "noopener noreferrer" }, `${c.company} ↗`)))),
    )));
  }

  // ------------------------------------------------------------------ wiring
  function markSeen() {
    state.seenBefore = new Date().toISOString();
    state.arrivedWhileOpen.clear();
    store.set(KEYS.lastSeen, state.seenBefore);
    renderHeader();
    renderJobs();
  }

  function init() {
    for (const [id, key] of [["f-type", "type"], ["f-city", "city"], ["f-status", "status"], ["f-sort", "sort"]]) {
      if (saved[key]) $(id).value = saved[key];
    }
    for (const id of ["f-type", "f-city", "f-status", "f-sort", "f-review", "f-closed"]) {
      $(id).addEventListener("change", () => { persistFilters(); renderJobs(); });
    }
    $("q").addEventListener("input", renderJobs);
    $("mark-seen").addEventListener("click", markSeen);

    document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => {
        const on = t === tab;
        t.classList.toggle("active", on);
        t.setAttribute("aria-selected", String(on));
        $(`tab-${t.dataset.tab}`).hidden = !on;
      });
    }));

    const notifyBtn = $("notify");
    if (!("Notification" in window)) notifyBtn.hidden = true;
    else if (Notification.permission === "granted") notifyBtn.textContent = "Browser alerts on";
    notifyBtn.addEventListener("click", async () => {
      try {
        const p = await Notification.requestPermission();
        notifyBtn.textContent = p === "granted" ? "Browser alerts on" : "Browser alerts blocked";
      } catch { notifyBtn.textContent = "Browser alerts unavailable"; }
    });

    $("export").addEventListener("click", () => {
      const blob = new Blob([JSON.stringify({ status: state.status }, null, 1)], { type: "application/json" });
      const a = el("a", { href: URL.createObjectURL(blob), download: "internship-statuses.json" });
      document.body.append(a); a.click(); a.remove();
    });
    $("import").addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const data = JSON.parse(await file.text());
        Object.assign(state.status, data.status || {});
        store.set(KEYS.status, state.status);
        renderHeader(); renderJobs();
        toast("Statuses imported");
      } catch { toast("That file couldn't be read"); }
      e.target.value = "";
    });

    // Leaving the page counts as having seen everything currently listed.
    const remember = () => store.set(KEYS.lastSeen, new Date().toISOString());
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") remember(); });
    window.addEventListener("pagehide", remember);

    setupLocalRefresh();
    load(true);
    setInterval(() => load(false), POLL_MS);
    setInterval(renderHeader, 60 * 1000); // keep "last checked x min ago" fresh
  }

  // Only when served by local.py: a button that runs the tracker right now.
  async function setupLocalRefresh() {
    const btn = $("refresh");
    let status;
    try {
      const res = await fetch("api/status", { cache: "no-store" });
      if (!res.ok) return;
      status = await res.json();
    } catch { return; }
    btn.hidden = false;

    const waitForRun = async () => {
      btn.disabled = true;
      btn.textContent = "Fetching…";
      for (;;) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          const s = await (await fetch("api/status", { cache: "no-store" })).json();
          if (!s.running) break;
        } catch { break; }
      }
      btn.disabled = false;
      btn.textContent = "Refresh now";
      await load(false);
    };
    btn.addEventListener("click", async () => {
      try { await fetch("api/refresh", { method: "POST" }); } catch { return; }
      waitForRun();
    });
    if (status.running) waitForRun();
  }

  init();
})();
