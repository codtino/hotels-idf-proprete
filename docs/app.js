(() => {
  const PAGE = 40;
  const REFRESH_MS = 5 * 60 * 1000;
  const SOURCES = { booking: "Booking", tripadvisor: "TripAdvisor" };
  const DEPTS = { "75": "Paris", "77": "Seine-et-Marne", "78": "Yvelines", "91": "Essonne",
    "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis", "94": "Val-de-Marne", "95": "Val-d'Oise" };

  const $ = (id) => document.getElementById(id);
  const state = { reviews: [], hotels: {}, meta: {}, shown: PAGE, cats: new Set(), lastVisit: null, updatedAt: null };

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  };

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fold = (s) => String(s ?? "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const fmtDate = (s, withTime) => {
    if (!s) return "—";
    const d = new Date(s);
    if (isNaN(d)) return s;
    return d.toLocaleDateString("fr-FR", withTime
      ? { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }
      : { day: "numeric", month: "short", year: "numeric" });
  };

  async function getJSON(path) {
    const r = await fetch(`${path}?t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return r.json();
  }

  async function load(initial) {
    const [rev, hot, meta] = await Promise.all([
      getJSON("data/reviews.json"),
      getJSON("data/hotels.json").catch(() => ({ hotels: [] })),
      getJSON("data/state.json").catch(() => ({})),
    ]);
    const before = new Set(state.reviews.map((r) => r.id));
    state.reviews = rev.reviews || [];
    state.hotels = Object.fromEntries((hot.hotels || []).map((h) => [h.key, h]));
    state.meta = meta;
    state.updatedAt = rev.updated_at;

    if (initial) {
      state.lastVisit = store.get("lastVisit");
      store.set("lastVisit", new Date().toISOString());
      fillCats();
    } else {
      const fresh = state.reviews.filter((r) => !before.has(r.id)).length;
      if (fresh) showBanner(`${fresh} nouvel${fresh > 1 ? "s" : ""} avis depuis l'ouverture de la page.`);
    }
    renderStats();
    render();
  }

  function hotelOf(r) { return state.hotels[r.hotelKey] || { name: r.hotelName || "Hôtel inconnu" }; }

  function fillDepts() {
    const sel = $("dept");
    for (const [code, name] of Object.entries(DEPTS)) sel.add(new Option(`${code} · ${name}`, code));
  }

  function fillCats() {
    const counts = {};
    for (const r of state.reviews) for (const c of r.categories || []) counts[c] = (counts[c] || 0) + 1;
    const box = $("cats");
    box.innerHTML = "";
    for (const [c, n] of Object.entries(counts).sort((a, b) => b[1] - a[1])) {
      const b = document.createElement("button");
      b.className = "chip";
      b.type = "button";
      b.textContent = `${c} (${n})`;
      b.setAttribute("aria-pressed", state.cats.has(c));
      b.onclick = () => {
        state.cats.has(c) ? state.cats.delete(c) : state.cats.add(c);
        b.setAttribute("aria-pressed", state.cats.has(c));
        state.shown = PAGE;
        render();
      };
      box.append(b);
    }
  }

  function renderStats() {
    const hotels = new Set(state.reviews.map((r) => r.hotelKey)).size;
    const m = state.meta;
    const items = [
      [state.reviews.length, "avis signalés"],
      [hotels, "hôtels concernés"],
      [m.hotels_tracked ?? "—", "hôtels surveillés"],
      [fmtDate(m.last_run || state.updatedAt, true), "dernière collecte"],
    ];
    $("stats").innerHTML = items.map(([v, l]) => `<span><b>${esc(v)}</b> ${esc(l)}</span>`).join("");
    if (m.errors && m.errors.length) showBanner(`Dernière collecte incomplète : ${m.errors.join(" · ")}`, true);
  }

  function showBanner(text, warn) {
    const el = $("banner");
    el.className = "banner" + (warn ? " warn" : "");
    el.innerHTML = `<span>${esc(text)}</span><button type="button">Fermer</button>`;
    el.querySelector("button").onclick = () => { el.hidden = true; };
    el.hidden = false;
  }

  function filtered() {
    const src = $("source").value;
    const dept = $("dept").value;
    const minRooms = Number($("minRooms").value) || 0;
    const q = fold($("q").value.trim());
    const list = state.reviews.filter((r) => {
      const h = hotelOf(r);
      if (src && r.source !== src) return false;
      if (dept && !(h.postcode || "").startsWith(dept)) return false;
      if (minRooms && (h.rooms || 0) < minRooms) return false;
      if (state.cats.size && !(r.categories || []).some((c) => state.cats.has(c))) return false;
      if (q && !fold([h.name, h.city, h.postcode, r.title, r.text].join(" ")).includes(q)) return false;
      return true;
    });
    const rooms = (r) => hotelOf(r).rooms;
    const byAdded = (a, b) => (b.addedAt || "").localeCompare(a.addedAt || "") || (b.reviewDate || "").localeCompare(a.reviewDate || "");
    const sorters = {
      added: (a, b) => byAdded(a, b) || (rooms(b) || 0) - (rooms(a) || 0),
      "rooms-desc": (a, b) => (rooms(b) ?? -1) - (rooms(a) ?? -1) || byAdded(a, b),
      "rooms-asc": (a, b) => (rooms(a) ?? Infinity) - (rooms(b) ?? Infinity) || byAdded(a, b),
      review: (a, b) => (b.reviewDate || "").localeCompare(a.reviewDate || "") || byAdded(a, b),
    };
    return list.sort(sorters[$("sort").value]);
  }

  function highlight(text, terms) {
    let html = esc(text);
    const words = (terms || []).filter(Boolean).sort((a, b) => b.length - a.length);
    if (!words.length) return html;
    // Les termes sont stockés sans accents : on les recherche dans une version « pliée » du texte.
    const folded = fold(html);
    const marks = [];
    for (const w of words) {
      const rx = new RegExp(`(?<![\\p{L}\\d])${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+")}(?![\\p{L}\\d])`, "giu");
      for (const m of folded.matchAll(rx)) marks.push([m.index, m.index + m[0].length]);
    }
    if (folded.length !== html.length) return html;
    marks.sort((a, b) => a[0] - b[0]);
    let out = "", pos = 0;
    for (const [s, e] of marks) {
      if (s < pos) continue;
      out += html.slice(pos, s) + "<mark>" + html.slice(s, e) + "</mark>";
      pos = e;
    }
    return out + html.slice(pos);
  }

  function card(r) {
    const h = hotelOf(r);
    const isNew = state.lastVisit && r.addedAt > state.lastVisit;
    const place = [h.city || h.postcode, h.stars ? "★".repeat(h.stars) : ""].filter(Boolean).join(" · ");
    const rooms = h.rooms ? `<span class="rooms">${h.rooms} chambres</span>` : "taille inconnue";
    const excerpts = (r.excerpts || []).map((e) => `<blockquote>${highlight(e, r.terms)}</blockquote>`).join("");
    return `
      <article class="card${isNew ? " is-new" : ""}">
        <div class="card-head">
          <div>
            <div class="hotel">${esc(h.name)}</div>
            <div class="meta">${esc(place)}${place ? " · " : ""}${rooms}</div>
          </div>
          <div class="badges">
            ${isNew ? '<span class="badge new">Nouveau</span>' : ""}
            <span class="badge ${r.source}">${SOURCES[r.source] || r.source}</span>
            <span class="badge rating">${esc(r.ratingLabel)}</span>
          </div>
        </div>
        <div class="cats">${(r.categories || []).map((c) => `<span class="cat">${esc(c)}</span>`).join("")}</div>
        ${r.title ? `<div class="title">${esc(r.title)}</div>` : ""}
        ${excerpts}
        <div class="actions">
          ${r.text ? '<button type="button" data-toggle>Avis complet</button>' : ""}
          ${r.url ? `<a href="${esc(r.url)}" target="_blank" rel="noopener">Voir sur ${SOURCES[r.source]}</a>` : ""}
        </div>
        <div class="full" hidden>${highlight(r.text, r.terms)}</div>
        <div class="dates">Avis du ${fmtDate(r.reviewDate)} · ajouté le ${fmtDate(r.addedAt, true)}</div>
      </article>`;
  }

  function render() {
    const list = filtered();
    $("count").textContent = `${list.length} avis${list.length !== state.reviews.length ? ` sur ${state.reviews.length}` : ""}`;
    if (!state.reviews.length) {
      $("list").innerHTML = `<div class="empty">Aucun avis pour l'instant.<br>La collecte tourne automatiquement ; les premiers résultats apparaîtront ici.</div>`;
      $("more").hidden = true;
      return;
    }
    $("list").innerHTML = list.slice(0, state.shown).map(card).join("") || `<div class="empty">Aucun avis ne correspond aux filtres.</div>`;
    $("more").hidden = list.length <= state.shown;
  }

  $("list").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-toggle]");
    if (!btn) return;
    const full = btn.closest(".card").querySelector(".full");
    full.hidden = !full.hidden;
    btn.textContent = full.hidden ? "Avis complet" : "Masquer";
  });
  fillDepts();
  $("more").onclick = () => { state.shown += PAGE; render(); };
  for (const id of ["sort", "source", "dept", "minRooms", "q"]) {
    $(id).addEventListener("input", () => {
      state.shown = PAGE;
      store.set(`f:${id}`, $(id).value);
      render();
    });
    const saved = store.get(`f:${id}`);
    if (saved !== null && id !== "q") $(id).value = saved;
  }

  load(true).catch((e) => {
    $("list").innerHTML = `<div class="empty">Impossible de charger les données (${esc(e.message)}).</div>`;
  });
  setInterval(() => load(false).catch(() => {}), REFRESH_MS);
})();
