// Idaho Eats web app: the iPhone app's guides, search, filters, map and place details, in the browser. Keep its guide rules in
// step with IdahoEats/Models/Guide.swift and its search with IdahoEats/Models/Search.swift.
// Same data file as the app (split into core + detail by scripts/make-site.py). No cookies, no trackers; saved places and the last
// guide live in this browser's localStorage only, under "ideats-" keys, because other sites share the nickstrom5.github.io origin.
// There are no inspection results: Idaho's health districts publish none in bulk, so a place links to its district's own lookup.
// The page runs under a strict Content-Security-Policy (hash-pinned inline script and style): never add inline event
// handlers or inline style attributes to the HTML built here; set properties from code instead.
(() => {
  "use strict";
  const BASE = document.documentElement.dataset.base || "";
  const $ = (s) => document.querySelector(s);
  const APP = $("#ex-app");
  // every value that goes into innerHTML passes through esc(), numbers included (the data file is trusted, but not that much)
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const own = (o, k) => typeof k === "string" && Object.prototype.hasOwnProperty.call(o, k);   // "constructor" in a URL is not a guide
  const PREFIX = "ideats-";
  const store = {
    get(k, d) { try { const v = localStorage.getItem(PREFIX + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem(PREFIX + k, JSON.stringify(v)); } catch { /* private mode */ } },
  };
  // only http(s) links leave the page; bare hosts ("example.com/menu") get https://
  const safeUrl = (u) => {
    u = String(u ?? "").trim();
    if (/^https?:\/\/[^\s"'<>\\]+$/i.test(u)) return u;
    if (/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}(?:[/?#][^\s"'<>\\]*)?$/i.test(u)) return "https://" + u;
    return null;
  };
  const telHref = (ph) => { const t = String(ph ?? "").replace(/[^\d+]/g, ""); return t.replace(/\D/g, "").length >= 10 ? "tel:" + t : null; };
  const num = (x) => (x == null || x === "" || !Number.isFinite(Number(x)) ? null : Number(x));
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const fmtDate = (s) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s ?? "")); return m ? `${MONTHS[+m[2] - 1]} ${+m[3]}, ${m[1]}` : String(s ?? ""); };

  // ---------------------------------------------------------------- search (a port of IdahoEats/Models/Search.swift)
  const typeSyn = { avenue: "ave", av: "ave", street: "st", boulevard: "blvd", road: "rd", drive: "dr", place: "pl", court: "ct",
    parkway: "pkwy", highway: "hwy", lane: "ln", trail: "trl", circle: "cir", terrace: "ter" };
  const syn = { ...typeSyn, north: "n", south: "s", east: "e", west: "w", saint: "st", mount: "mt", fort: "ft" };
  const abbrs = new Set(Object.values(syn)), typeAbbrs = new Set(Object.values(typeSyn));
  // the tag bits, in pipeline/idaho.py's TAGS order (scripts/make-site.py asserts the data file's order matches)
  const BASQUE = 1, FINGER = 2, DRIVEIN = 4, SPUD = 8, HUCK = 16, TROUT = 32, TAQ = 64, HISTORIC = 128, OLDEST = 256, RESORT = 512;
  const GUIDE_TAGS = BASQUE | FINGER | DRIVEIN | SPUD | HUCK | TROUT | TAQ | HISTORIC | OLDEST;
  // a dish ("fry sauce", "trout") is not a tag: it's in each place's search text (its dishes), so it finds the places that serve it
  const tagPhrases = [["finger steaks", FINGER], ["finger steak", FINGER], ["fingersteaks", FINGER], ["drive ins", DRIVEIN], ["drive in", DRIVEIN],
    ["drivein", DRIVEIN], ["basque", BASQUE], ["spud plates", SPUD], ["spuds", SPUD], ["huckleberries", HUCK], ["huckleberry", HUCK],
    ["taquerias", TAQ], ["taqueria", TAQ], ["historic saloons", HISTORIC], ["resort towns", RESORT], ["resort town", RESORT]];
  function normalize(s) {
    let t = String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    t = t.replace(/\b([a-z0-9])\s*&\s*([a-z0-9])\b/g, "$1$2").replace(/&/g, " and ").replace(/['’`]/g, "");
    return t.replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  }
  const normAddr = (s) => normalize(s).split(" ").map((w) => (own(syn, w) ? syn[w] : w)).join(" ");
  // "huckleberries" -> "huckleberry", "taquerias" -> "taqueria", "spuds" -> "spud" (no lookbehind: older Safari can't parse one)
  const stemOf = (s) => (/ies$/.test(s) ? s.replace(/ies$/, "y") : s.replace(/(^|[^y])s$/, "$1"));

  function parse(text) {
    const q = { tokens: [], town: null, townNeedle: null, tag: 0, tagStem: null };
    let raw = normalize(text).split(" ").filter(Boolean);
    if (!raw.length) return q;
    let mapped = raw.map((w) => (own(syn, w) ? syn[w] : w));
    const find = (phrase) => {
      const p = phrase.split(" ");
      for (let i = 0; i + p.length <= mapped.length; i++) if (p.every((w, k) => mapped[i + k] === w)) return [i, i + p.length];
      return null;
    };
    const cut = ([a, b]) => { const words = raw.slice(a, b).join(" "); raw.splice(a, b - a); mapped.splice(a, b - a); return words; };
    for (const [phrase, tag] of tagPhrases) {
      const r = find(normalize(phrase));
      if (r) { q.tag = tag; const stem = stemOf(normalize(cut(r))); q.tagStem = stem ? " " + stem : null; break; }
    }
    // the longest town named in the query wins, unless a street type follows it ("meridian rd" is a street)
    for (const key of TOWN_KEYS_BY_LENGTH) {
      const r = find(key);
      if (r && !(r[1] < mapped.length && typeAbbrs.has(mapped[r[1]]))) { q.town = TOWN_KEYS.get(key); q.townNeedle = " " + normalize(cut(r)); break; }
    }
    const stop = new Set(["the", "and", "of", "a", "in", "near", "me"]);   // "basque near me" isn't Mexican places
    let idx = raw.map((_, i) => i);
    // stop words stay only when they're all there is ("the"); next to a guide or a town ("basque near me") they go
    if (q.tag || q.town || idx.some((i) => !stop.has(mapped[i]))) idx = idx.filter((i) => !stop.has(mapped[i]));
    idx.forEach((i, n) => {
      const token = raw[i], isLast = n === idx.length - 1;
      if (own(syn, token)) { q.tokens.push([` ${syn[token]} `, ` ${token}`]); return; }
      const whole = (abbrs.has(token) && (!isLast || token.length > 1)) || (token.length <= 2 && !isLast);
      const needles = [" " + token + (whole ? " " : "")];
      if (isLast && token.length >= 3) for (const [word, abbr] of Object.entries(typeSyn)) if (word !== token && word.startsWith(token)) needles.push(` ${abbr} `);
      q.tokens.push(needles);
    });
    // "vista ave": a finished street type sticks to the word before it
    if (q.tokens.length >= 2 && idx.length && typeAbbrs.has(mapped[idx[idx.length - 1]])) {
      const last = idx[idx.length - 1], prev = idx[idx.length - 2];
      q.tokens.splice(-2, 2, [` ${mapped[prev]} ${mapped[last]} `, ` ${raw[prev]} ${raw[last]}`]);
    }
    return q;
  }
  const qEmpty = (q) => !q.tokens.length && !q.town && !q.tag;
  function matches(p, q) {
    if (q.tag && (p.g & q.tag) !== q.tag && !(q.tagStem && p.nameText.includes(q.tagStem))) return false;
    if (q.town && p.c !== q.town && !(q.townNeedle && p.nameText.includes(q.townNeedle))) return false;
    return q.tokens.every((needles) => needles.some((n) => p.search.includes(n)));
  }
  const nameMatches = (p, q) => q.tokens.length && q.tokens.every((needles) => needles.some((n) => p.nameText.includes(n)));

  // ---------------------------------------------------------------- guides (IdahoEats/Models/Guide.swift)
  // the guides that promise "hand-checked" list only places checked with a 2025-26 source (hc)
  const GUIDES = {
    basque: { title: "Basque", sub: "Boise's Basque Block and Basque kitchens around the state, hand-checked", inc: (p) => p.hc && p.g & BASQUE, sorts: ["featured", "nearest", "name"], idaho: true },
    fingersteaks: { title: "Finger Steaks & Drive-Ins", sub: "Finger steaks, fry sauce and drive-in burgers, hand-checked", inc: (p) => p.hc && p.g & (FINGER | DRIVEIN), sorts: ["featured", "nearest", "name"], idaho: true },
    spuds: { title: "Spud Plates", sub: "Potato plates named on the menu, hand-checked", inc: (p) => p.hc && p.g & SPUD, sorts: ["featured", "nearest", "name"], idaho: true },
    huckleberry: { title: "Huckleberry", sub: "Huckleberry shakes, pies and pancakes, hand-checked", inc: (p) => p.hc && p.g & HUCK, sorts: ["featured", "nearest", "name"], idaho: true },
    trout: { title: "Idaho Trout", sub: "Idaho rainbow trout on the menu, hand-checked", inc: (p) => p.hc && p.g & TROUT, sorts: ["featured", "nearest", "name"], idaho: true },
    taquerias: { title: "Taquerías", sub: "Taquerías with a fixed address, hand-checked", inc: (p) => p.hc && p.g & TAQ, sorts: ["featured", "nearest", "name"], idaho: true },
    historic: { title: "Historic Saloons", sub: "Old saloons and supper clubs, hand-checked", inc: (p) => p.hc && p.g & HISTORIC, sorts: ["featured", "nearest", "name"], idaho: true },
    honors: { title: "James Beard Honors", sub: "James Beard winners, nominees, semifinalists and America's Classics", inc: (p) => p.jb, sorts: ["iconic", "nearest"] },
    oldest: { title: "Oldest Places", sub: "Founding years checked at the same address, oldest first", inc: (p) => p.f != null, sorts: ["oldest"], ranked: true },
    all: { title: "All Restaurants", sub: "Restaurants, cafés, bars and bakeries statewide", inc: () => true, sorts: ["name", "nearest"] },
    saved: { title: "Saved", sub: "Places you saved in this browser", inc: (p) => saved.has(p.id), sorts: ["name", "nearest"] },
  };
  const DEFAULT_GUIDE = own(GUIDES, APP.dataset.default) ? APP.dataset.default : "all";
  const SORT_LABEL = { featured: "Featured first", nearest: "Nearest", oldest: "Oldest first", name: "A to Z", iconic: "By James Beard honor" };
  const GUIDE_LABELS = [[BASQUE, "Basque"], [FINGER, "Finger steaks"], [DRIVEIN, "Drive-in"], [SPUD, "Spud plate"], [HUCK, "Huckleberry"],
    [TROUT, "Trout"], [TAQ, "Taquería"], [HISTORIC, "Historic saloon"]];

  // ---------------------------------------------------------------- state
  let P = [], D = null, CAL = {}, TOWN_KEYS = new Map(), TOWN_KEYS_BY_LENGTH = [], GENERATED = "", CHECKED = "", ABC = 0, LIQ_DATE = "";
  let DISTRICT_OF = new Map(), INS_PAGE = "";
  let here = null, shown = 100, current = [], view = "list", wired = false;
  const savedRaw = store.get("saved", []);
  const saved = new Set(Array.isArray(savedRaw) ? savedRaw.filter((x) => typeof x === "string" && x.length < 64) : []);
  const st = { g: DEFAULT_GUIDE, q: "", sort: "", town: "", cuisine: "", chains: false, p: "" };

  const miles = (a, b) => {
    const r = Math.PI / 180, dLa = (b.la - a.la) * r, dLo = (b.lo - a.lo) * r;
    const h = Math.sin(dLa / 2) ** 2 + Math.cos(a.la * r) * Math.cos(b.la * r) * Math.sin(dLo / 2) ** 2;
    return 3958.8 * 2 * Math.asin(Math.sqrt(h));
  };
  const milesText = (m) => (m < 10 ? m.toFixed(1) : Math.round(m)) + " mi";
  // Idaho's outline, simplified and padded 3 km, (lat, lon) pairs: the same one the app uses (LocationService.swift), because a box
  // would take in Pullman and Jackson. Every place is in Idaho, so a visitor elsewhere is told why the distances are long.
  const OUTLINE = [[44.426, -117.25], [44.746, -117.085], [44.901, -116.88], [45.036, -116.875], [45.61, -116.501], [45.726, -116.567],
    [45.798, -116.795], [45.888, -116.883], [46.077, -117.011], [46.232, -116.987], [46.346, -117.092], [49.008, -117.061],
    [49.03, -116.041], [48.0, -116.019], [47.713, -115.698], [47.558, -115.684], [47.486, -115.6], [47.427, -115.643],
    [47.32, -115.495], [47.281, -115.302], [46.744, -114.735], [46.759, -114.635], [46.668, -114.588], [46.66, -114.294],
    [46.137, -114.456], [45.877, -114.359], [45.783, -114.515], [45.704, -114.465], [45.597, -114.509], [45.495, -114.33],
    [45.736, -113.991], [45.63, -113.794], [45.342, -113.702], [45.072, -113.425], [44.889, -113.43], [44.795, -113.111],
    [44.471, -112.976], [44.434, -112.901], [44.534, -112.721], [44.485, -112.394], [44.598, -112.29], [44.557, -112.107],
    [44.596, -111.866], [44.549, -111.82], [44.586, -111.555], [44.725, -111.512], [44.785, -111.386], [44.493, -111.028],
    [41.99, -111.019], [41.972, -117.036], [43.831, -117.063], [44.017, -116.971], [44.095, -117.006], [44.158, -116.934],
    [44.266, -117.237]];
  function inIdaho(pt) {
    let inside = false;
    for (let i = 0, j = OUTLINE.length - 1; i < OUTLINE.length; j = i++) {
      const [yi, xi] = OUTLINE[i], [yj, xj] = OUTLINE[j];
      if ((yi > pt.la) !== (yj > pt.la) && pt.lo < (xj - xi) * (pt.la - yi) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }

  function order() {
    const g = GUIDES[st.g];
    let o = st.sort && g.sorts.includes(st.sort) ? st.sort : g.idaho && here ? "nearest" : g.sorts[0];
    if (o === "nearest" && !here) o = g.sorts.find((s) => s !== "nearest") || o;   // no location yet: say what the list is really sorted by
    return o;
  }

  function allows(p) {
    if (p.v && st.g !== "saved") return false;            // gas-station counters, stadium stands and the like
    if (st.town && p.c !== st.town) return false;
    if (st.cuisine && p.cu !== st.cuisine) return false;
    if (st.chains && p.ch >= 5) return false;
    return true;
  }

  function list() {
    const g = GUIDES[st.g], q = parse(st.q), o = order();
    if (qEmpty(q) && st.q.trim()) return [];   // typed something, but nothing searchable ("🍕", "!!!")
    let out = P.filter((p) => g.inc(p) && allows(p) && (qEmpty(q) || matches(p, q)));
    const byName = (a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
    const dist = (p) => (here && p.la != null ? miles(here, p) : Infinity);
    if (o === "nearest" && here) out.sort((a, b) => dist(a) - dist(b) || byName(a, b));
    else if (o === "featured") out.sort((a, b) => (b.ip ?? -1) - (a.ip ?? -1) || (a.f ?? 9999) - (b.f ?? 9999) || byName(a, b));
    else if (o === "oldest") out.sort((a, b) => (a.f ?? 9999) - (b.f ?? 9999) || byName(a, b));
    else if (o === "iconic") {   // the James Beard honor (America's Classic, winner, nominee, semifinalist), then name: the app's order
      const jb = (p) => (p.h & 1 ? 4 : p.h & 2 ? 3 : p.h & 4 ? 2 : p.h & 8 ? 1 : 0);
      out.sort((a, b) => jb(b) - jb(a) || byName(a, b));
    }
    else out.sort(byName);
    if (q.tokens.length && !g.ranked) {       // name matches first when searching ("eagle" puts Eagle Rock ahead of the town)
      const named = out.filter((p) => nameMatches(p, q));
      if (named.length && named.length < out.length) { const ids = new Set(named); out = named.concat(out.filter((p) => !ids.has(p))); }
    }
    return out;
  }

  // ---------------------------------------------------------------- rendering
  const jbLabel = (p) => (p.h & 1 ? "America's Classic" : p.h & 2 ? "James Beard winner" : p.h & 4 ? "James Beard nominee"
    : p.h & 8 ? "James Beard semifinalist" : p.jb ? "James Beard (restaurateur)" : null);
  function chips(p, max) {
    const c = [];
    const jb = jbLabel(p);
    if (jb) c.push(`<span class="tag tag-jb">${esc(jb)}</span>`);
    if (p.hc) for (const [bit, label] of GUIDE_LABELS) if (p.g & bit) c.push(`<span class="tag">${esc(label)}</span>`);
    if (p.g & OLDEST && p.f) c.push(`<span class="tag tag-plain">Since ${esc(p.f)}</span>`);
    if (p.ch >= 5) c.push(`<span class="tag tag-plain">Chain · ${esc(p.ch)}</span>`);
    if (p.t === 0 && !p.h && !p.hc) c.push('<span class="tag tag-dash">Listing only</span>');
    return (max ? c.slice(0, max) : c).join("");
  }

  function metric(p, o) {
    if (o === "nearest" && here && p.la != null) return [milesText(miles(here, p)), "away"];
    if (p.f && st.g !== "all") return [String(p.f), "since"];
    return null;
  }

  // before the data arrives: the guide from the URL or the last visit, so nothing moves when the list fills in
  function preRender() {
    document.querySelectorAll(".ex-guides button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.g === st.g)));
    $("#ex-sub").textContent = GUIDES[st.g].sub;
  }

  function render() {
    const g = GUIDES[st.g], o = order();
    current = list();
    preRender();
    const sortSel = $("#ex-sort");
    sortSel.innerHTML = g.sorts.map((s) => `<option value="${esc(s)}"${s === o ? " selected" : ""}>${esc(SORT_LABEL[s])}</option>`).join("");
    sortSel.disabled = g.sorts.length < 2;
    const filters = [st.town && `in ${st.town}`, st.cuisine && st.cuisine, st.chains && "no chains"].filter(Boolean);
    $("#ex-count").textContent = `${current.length.toLocaleString()} ${current.length === 1 ? "place" : "places"} · ${SORT_LABEL[o]}` + (filters.length ? ` · ${filters.join(", ")}` : "");
    const clear = $("#ex-clear");
    clear.classList.toggle("ex-off", !filters.length);   // kept in the layout, so the row doesn't reflow
    clear.disabled = !filters.length;
    if (view === "list") renderList(o); else drawMap();
    saveHash();
  }

  // A search inside a guide looks only in that guide, and the app opens on one: a first visit that types a well-known place from
  // elsewhere would find nothing. When a guide search lists none or only a few, offer the same search and filters in All restaurants,
  // with its count. (Worded by the list's name, so the button makes no claim about how complete the list is.)
  const FEW = 5;
  function elsewhere() {
    const q = parse(st.q);
    if (st.g === "all" || qEmpty(q) || current.length >= FEW) return 0;
    const n = P.filter((p) => !p.v && allows(p) && matches(p, q)).length;   // what All restaurants will list (list() with g = "all")
    return n > current.length ? n : 0;
  }
  function widen() {
    st.g = "all"; st.sort = ""; shown = 100; render();
    showChip();
    $(".ex-row")?.focus();
  }
  const widenButton = (n) => `<button type="button" class="ex-small ex-widen" id="ex-widen">See ${esc(n.toLocaleString())} ${n === 1 ? "match" : "matches"} in All restaurants</button>`;

  function renderList(o) {
    const ol = $("#ex-list");
    const g = GUIDES[st.g];
    const more = elsewhere();
    const scope = st.g === "saved" ? "your saved places" : `the ${g.title} guide`;
    if (!current.length) {
      ol.innerHTML = `<li class="ex-empty">${more ? `No place in ${esc(scope)} matches that. ${widenButton(more)}`
        : st.g === "saved" && !saved.size ? "Nothing saved yet. Open a place and tap Save to keep it here, in this browser."
        : st.g === "all" || st.g === "saved" || st.q.trim() ? "No places match. Try fewer words or clear the filters."
        : "No places in this guide match. Try All restaurants or clear the filters."}</li>`;
      if (more) $("#ex-widen").onclick = widen;
      $("#ex-more").hidden = true;
      return;
    }
    ol.innerHTML = current.slice(0, shown).map((p, i) => {
      const m = metric(p, o);
      const rank = g.ranked ? `<span class="ex-rank${i < 3 ? " top" : ""}"><span class="vh">Rank </span>${i + 1}</span>` : "";
      const where = [p.c, p.cu].filter(Boolean).join(" · ");
      return `<li><button type="button" class="ex-row" data-i="${esc(p.i)}">${rank}<span class="ex-main"><b>${esc(p.n)}</b><span class="ex-town">${esc(where)}</span><span class="ex-chips">${chips(p, 4)}</span></span>${m ? `<span class="ex-metric"><b>${esc(m[0])}</b><small>${esc(m[1])}</small></span>` : ""}</button></li>`;
    }).join("") + (more ? `<li class="ex-empty ex-few">Only ${current.length === 1 ? "one" : esc(current.length)} in ${esc(scope)}. ${widenButton(more)}</li>` : "");
    if (more) $("#ex-widen").onclick = widen;
    const left = current.length - shown;
    $("#ex-more").hidden = left <= 0;
    $("#ex-more").textContent = `Show more (${left.toLocaleString()} left)`;
  }

  // ---------------------------------------------------------------- place panel
  const JUR = { 1: "Idaho State Police alcohol licenses (Alcohol Beverage Control)" };
  const TIER = { 2: "On an official record", 1: "Confirmed listing", 0: "Listing only" };

  // the share of listings like this one that matched a licensed business in a test against Denver's full food-license list
  // (same Overture release): Idaho has no public food-license list to test against
  function rate(p) {
    if (p.t === 2) return null;   // an official record confirms it; no listing rate needed
    const src = SOURCES[p.s] || "meta";
    const group = src === "meta" ? (p.t === 1 ? "meta_high" : "meta_mid") : (src === "AllThePlaces" || src === "DAC") ? "brand_feed" : null;
    const v = group && CAL?.reference_colorado_denver?.groups?.[group]?.official;
    return typeof v === "number" ? `${Math.round(v * 100)}%` : null;
  }

  function howWeKnow(p) {
    const src = SOURCES[p.s] || "meta";
    if (src === "research") return `On our hand-checked list (checked in ${CHECKED} against a 2025 or 2026 source). The open map data didn't list it as a place to eat, so it's placed from its own map listing or street address.`;
    if (p.t === 2) return src === "official"
      ? `From the ${JUR[p.j] || "official records"}. The open map data didn't have it, so its location comes from the record's street address.`
      : `Matched to the ${JUR[p.j] || "official records"}.`;
    const r = rate(p);
    return (p.t === 1 ? "A high-confidence listing in Overture's open map data." : "A single listing in Overture's open map data, so it may be closed or misfiled.")
      + (r ? ` In a test against Denver's full list of food licenses (Colorado, same map data), listings like this matched a licensed business ${r} of the time.` : "")
      + (p.hc ? ` It's also on our hand-checked list, checked in ${CHECKED} against a 2025 or 2026 source.` : "");
  }

  function servesAlcohol(d, lics) {
    if (d.liq) return `Yes · ${d.liq}`;
    if (lics.length) return "Beer or wine to go only (store license)";
    return "Unknown (no on-premises alcohol license matched)";
  }

  const kv = (k, v) => (v == null || v === "" ? "" : `<div class="ex-kv"><span>${esc(k)}</span><b>${esc(v)}</b></div>`);
  const section = (t, body) => `<section class="ex-sec"><h3>${esc(t)}</h3>${body}</section>`;
  const phone = matchMedia("(max-width: 600px)");
  let listAtPush = null;   // the list's URL state when a place was opened with pushState (Back then closes the panel)

  // the panel is a modal dialog at every width (a bottom sheet on phones; on wider screens a side panel over the List, Map and
  // Near me controls), so everything behind it is inert while it's open; Close, Escape and Back close it
  function panelMode() {
    const panel = $("#ex-panel"), modal = !panel.hidden;
    if (modal) { panel.setAttribute("role", "dialog"); panel.setAttribute("aria-modal", "true"); }
    else { panel.removeAttribute("role"); panel.removeAttribute("aria-modal"); }
    const scrim = $("#ex-scrim");
    if (scrim) scrim.hidden = !modal;   // dims the page behind; a click on it closes the panel
    const behind = [...document.querySelectorAll("body > .skip, .wrap > header, .wrap > .ridge, .wrap > nav, .wrap > footer, #main > *")].filter((el) => el !== panel && el !== scrim);
    behind.forEach((el) => { el.inert = modal; });
  }

  function openPlace(p, push = true) {
    const panel = $("#ex-panel");
    const wasOpen = !panel.hidden;
    st.p = p.id;
    const d = (D && D[p.i]) || {};
    const la = num(p.la), lo = num(p.lo);
    const addr = [p.a, [p.c, p.z].filter(Boolean).join(" ")].filter(Boolean).join(", ");
    const apple = la != null && lo != null
      ? `https://maps.apple.com/?q=${encodeURIComponent(p.n)}&ll=${la},${lo}`
      : `https://maps.apple.com/?q=${encodeURIComponent(p.n + ", " + addr + ", Idaho")}`;
    const dirs = la != null && lo != null ? `https://maps.apple.com/?daddr=${la},${lo}&dirflg=d` : apple;
    const site = safeUrl(d.w), tel = telHref(d.ph);
    const county = p.co && p.co !== p.c ? p.co : "";
    let html = `<button type="button" class="ex-close" id="ex-close" aria-label="Close">×</button>
      <p class="ex-kicker">${esc([(p.c || "Idaho").toUpperCase(), county.toUpperCase()].filter(Boolean).join(" · "))}</p>
      <h2 id="ex-pname">${esc(p.n)}</h2>
      <p class="ex-addr">${esc([addr, p.cu].filter(Boolean).join(" · "))}</p>
      ${here && la != null ? `<p class="ex-dist">${esc(milesText(miles(here, p)))} away</p>` : ""}
      <p class="ex-chips">${chips(p)}</p>
      <div class="ex-actions">
        <a class="btn ex-apple" href="${esc(apple)}" rel="noopener" target="_blank">Ratings, hours &amp; photos · Apple Maps</a>
        <div class="ex-act-row">
          <a href="${esc(dirs)}" rel="noopener" target="_blank">Directions</a>
          ${tel ? `<a href="${esc(tel)}">Call</a>` : ""}
          ${site ? `<a href="${esc(site)}" rel="noopener nofollow" target="_blank">Website</a>` : ""}
          <button type="button" id="ex-save" aria-pressed="${saved.has(p.id)}">${saved.has(p.id) ? "Saved" : "Save"}</button>
        </div>
      </div>`;
    if (!D) html += `<p class="ex-fine" id="ex-more-loading">Loading details…</p>`;
    if (p.hc && (d.note || d.dish || p.f || d.seas)) {
      html += section("Hand-checked", (d.note ? `<p>${esc(d.note)}</p>` : "") + kv("On the menu", d.dish ? String(d.dish).split("; ").join(", ") : "")
        + kv("Open here since", p.f) + (p.f && d.fn ? `<p class="ex-fine">${esc(d.fn)}</p>` : "") + kv("Season", d.seas)
        + `<p class="ex-fine">Checked by hand in ${esc(CHECKED)} against a 2025 or 2026 source: the place's own site or menu, or local news. Menus and seasons change, and resort-town places close between seasons, so check before you go.</p>`);
    }
    if (d.jbf) {
      const lines = String(d.jbf).split("; ").filter(Boolean).map((x) => "James Beard: " + x);
      html += section("Honors", `<ul>${lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul><p class="ex-fine">Honors are facts, not ratings. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation.</p>`);
    }
    // Idaho publishes no inspection results in bulk: say so, and point to the district that inspects this place
    const dist = DISTRICT_OF.get(p.co || "");
    html += section("Health inspections", `<p>Idaho's public health districts inspect restaurants about once a year, but none publishes results in bulk or issues a grade, so there are no inspection results here.</p>`
      + (dist ? (safeUrl(dist.url) ? `<p><a href="${esc(safeUrl(dist.url))}" rel="noopener" target="_blank">${esc(dist.name)}: food inspections</a></p>` : `<p>${esc(dist.name)} has no online inspection lookup.</p>`) : "")
      + `<p><a href="${esc(INS_PAGE)}">How to look up an Idaho restaurant inspection</a></p>`);
    const lics = Array.isArray(d.lic) ? d.lic : [];
    if (ABC > 0) {
      // a past expiry date reads like a lapsed license, so only a date on or after the list's own date is shown
      const lic = lics.map((l) => kv(l.src, [l.type, l.id, l.exp && LIQ_DATE && String(l.exp) >= String(LIQ_DATE) && "expires " + fmtDate(l.exp)].filter(Boolean).join(" · "))).join("");
      html += section("Official records", lic + kv("Serves alcohol", servesAlcohol(d, lics))
        + `<p class="ex-fine">${lics.length ? `From Idaho State Police's alcohol license list${LIQ_DATE ? " (as of " + esc(fmtDate(LIQ_DATE)) + ")" : ""}.` : "No Idaho State Police alcohol license matched this place. Idaho has no public list of food licenses, so a missing record means unknown, not unlicensed."}</p>`);
    }
    html += section("How we know it's here", kv("Listed as", TIER[p.t]) + (p.t === 2 ? kv("Official record", JUR[p.j]) : "")
      + (p.ch >= 2 ? kv("Locations in Idaho", p.ch.toLocaleString()) : "") + `<p class="ex-fine">${esc(howWeKnow(p))}</p>`);
    const storeUrl = safeUrl(APP.dataset.store);   // set by scripts/make-site.py once the App Store listing exists
    html += storeUrl
      ? `<p class="ex-app">Save it on your phone: <a href="${esc(storeUrl)}" rel="noopener">get the free iPhone app</a></p>`
      : `<p class="ex-app">The iPhone app is coming soon. <a href="${BASE}/#download">Get early access</a></p>`;
    panel.innerHTML = html;
    panel.dataset.id = p.id;
    panel.hidden = false;
    document.body.classList.add("ex-open");
    panelMode();
    $("#ex-close").onclick = () => closePlace();
    $("#ex-save").onclick = (e) => {
      if (saved.has(p.id)) saved.delete(p.id); else saved.add(p.id);
      store.set("saved", [...saved]);
      e.target.textContent = saved.has(p.id) ? "Saved" : "Save";
      e.target.setAttribute("aria-pressed", String(saved.has(p.id)));
      if (st.g === "saved") render();
    };
    panel.scrollTop = 0;
    $("#ex-close").focus();
    if (push) {
      if (wasOpen) saveHash();            // one Back step per panel, not per place looked at
      else { listAtPush = listHash(); saveHash(true); }
    }
    if (!D) loadDetail().then(() => { if (st.p === p.id && !panel.hidden) openPlace(p, false); });   // details load on the first open only
  }

  // fromHistory: the Back button (or a hash link) already moved the URL, so don't touch history again
  function closePlace(fromHistory = false) {
    const was = st.p;
    st.p = "";
    const panel = $("#ex-panel");
    panel.hidden = true;
    delete panel.dataset.id;
    document.body.classList.remove("ex-open");
    panelMode();
    if (!fromHistory) {
      // the list hasn't changed since the panel opened: step back over the entry openPlace pushed, so Back isn't a dead click
      if (history.state && history.state.ideats === "place" && listHash() === listAtPush) history.back();
      else saveHash();
    }
    listAtPush = null;
    const row = was && document.querySelector(`.ex-row[data-i="${P.findIndex((p) => p.id === was)}"]`);
    if (row) row.focus();
  }

  // ---------------------------------------------------------------- map (canvas: county outlines + a dot per place)
  // Idaho is tall and narrow (about 0.62 wide for its height): lon -117.25..-111.04, lat 41.99..49.0
  let SHAPES = null, cam = null;
  const LAT0 = 45.5, KX = Math.cos(LAT0 * Math.PI / 180);
  const proj = (lo, la) => [(lo + 114.15) * KX, -(la - LAT0)];

  function fitCam(w, h) {
    const [x0, y0] = proj(-117.25, 49.0), [x1, y1] = proj(-111.04, 41.99);
    const k = Math.min(w / (x1 - x0), h / (y1 - y0)) * 0.95;
    return { k, x: (w - (x1 - x0) * k) / 2 - x0 * k, y: (h - (y1 - y0) * k) / 2 - y0 * k };
  }

  // calls f on every ring, however deeply it's nested (the state is [polygon[ring[point]]], each county [ring[point]])
  const eachRing = (g, f) => {
    if (!Array.isArray(g) || !g.length) return;
    if (Array.isArray(g[0]) && typeof g[0][0] === "number") f(g); else g.forEach((x) => eachRing(x, f));
  };

  async function drawMap() {
    const cv = $("#ex-map"), wrap = $("#ex-mapwrap");
    const w = wrap.clientWidth, h = wrap.clientHeight, dpr = window.devicePixelRatio || 1;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    if (!cam) cam = fitCam(w, h);
    if (!SHAPES) SHAPES = await fetchJSON(`${BASE}/data/id_shapes.json`).catch(() => ({ state: [], counties: [] }));
    const css = getComputedStyle(document.documentElement), tok = (n, d) => css.getPropertyValue(n).trim() || d;   // light or dark
    const c = cv.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const X = (lo, la) => { const [x, y] = proj(lo, la); return [x * cam.k + cam.x, y * cam.k + cam.y]; };
    const ring = (r) => { r.forEach(([lo, la], i) => { const [x, y] = X(lo, la); i ? c.lineTo(x, y) : c.moveTo(x, y); }); c.closePath(); };
    c.fillStyle = tok("--land", "#fff");
    c.beginPath(); eachRing(SHAPES.state, ring); c.fill("evenodd");
    c.strokeStyle = tok("--county", "rgba(94,86,104,.35)"); c.lineWidth = 0.8;
    for (const co of SHAPES.counties || []) { c.beginPath(); eachRing(co.c, ring); c.stroke(); }
    const pts = current.filter((p) => p.la != null);
    const r = Math.max(2.2, Math.min(5, 1.6 + cam.k / 120));
    // drawn in three passes so the hand-checked picks (russet) and James Beard honorees (pine) sit on top of the plain dots
    const kind = (p) => (p.h & 15 || p.jb ? 2 : p.hc && p.g & GUIDE_TAGS ? 1 : 0);
    for (const pass of [0, 1, 2]) {
      c.fillStyle = pass === 2 ? tok("--pin-honor", "#2e5a4c") : pass === 1 ? tok("--pin-pick", "#c9a06b") : tok("--dot", "#4b2a5c");
      c.strokeStyle = tok("--pin-edge", "#1f1a24"); c.lineWidth = 1;
      for (const p of pts) {
        if (kind(p) !== pass) continue;
        const [x, y] = X(p.lo, p.la);
        if (x < -5 || y < -5 || x > w + 5 || y > h + 5) continue;
        c.beginPath(); c.arc(x, y, pass ? r + 1 : r, 0, 6.2832); c.fill(); if (pass) c.stroke();
      }
    }
    $("#ex-maphint").textContent = pts.length ? `${pts.length.toLocaleString()} ${pts.length === 1 ? "place" : "places"} · tap a dot` : "No places to show";
  }

  function nearestDot(px, py) {
    let best = null, bd = 14 * 14;
    for (const p of current) {
      if (p.la == null) continue;
      const [x0, y0] = proj(p.lo, p.la), x = x0 * cam.k + cam.x, y = y0 * cam.k + cam.y;
      const d = (x - px) ** 2 + (y - py) ** 2;
      if (d < bd) { bd = d; best = p; }
    }
    return best;
  }

  function zoomAt(f, px, py) {
    const k = Math.min(Math.max(cam.k * f, 30), 60000);
    const s = k / cam.k;
    cam = { k, x: px - (px - cam.x) * s, y: py - (py - cam.y) * s };
    drawMap();
  }

  function mapEvents() {
    const cv = $("#ex-map");
    const ptrs = new Map();
    let moved = false, pinch0 = null;
    cv.addEventListener("wheel", (e) => { e.preventDefault(); const b = cv.getBoundingClientRect(); zoomAt(e.deltaY < 0 ? 1.25 : 0.8, e.clientX - b.left, e.clientY - b.top); }, { passive: false });
    cv.addEventListener("pointerdown", (e) => { loadDetail(); cv.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, [e.clientX, e.clientY]); moved = false; pinch0 = null; });
    cv.addEventListener("pointermove", (e) => {
      if (!ptrs.has(e.pointerId)) return;
      const prev = ptrs.get(e.pointerId);
      ptrs.set(e.pointerId, [e.clientX, e.clientY]);
      if (ptrs.size === 2) {
        const [a, b] = [...ptrs.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        const r = cv.getBoundingClientRect();
        if (pinch0) zoomAt(d / pinch0, (a[0] + b[0]) / 2 - r.left, (a[1] + b[1]) / 2 - r.top);
        pinch0 = d; moved = true; return;
      }
      const dx = e.clientX - prev[0], dy = e.clientY - prev[1];
      if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
      cam.x += dx; cam.y += dy; drawMap();
    });
    const up = (e) => {
      ptrs.delete(e.pointerId);
      if (!moved && ptrs.size === 0) {
        const b = cv.getBoundingClientRect(), p = nearestDot(e.clientX - b.left, e.clientY - b.top);
        if (p) openPlace(p);
      }
      if (ptrs.size < 2) pinch0 = null;
    };
    cv.addEventListener("pointerup", up);
    cv.addEventListener("pointercancel", (e) => ptrs.delete(e.pointerId));
    $("#ex-zin").onclick = () => zoomAt(1.6, cv.clientWidth / 2, cv.clientHeight / 2);
    $("#ex-zout").onclick = () => zoomAt(0.625, cv.clientWidth / 2, cv.clientHeight / 2);
    window.addEventListener("resize", () => { if (view === "map") drawMap(); });
    matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => { if (view === "map") drawMap(); });
  }

  function centerOn(pt) {
    const cv = $("#ex-map"), w = cv.clientWidth, h = cv.clientHeight;
    const k = 4000, [x, y] = proj(pt.lo, pt.la);
    cam = { k, x: w / 2 - x * k, y: h / 2 - y * k };
  }

  // ---------------------------------------------------------------- data, URL state, controls
  let SOURCES = [];
  async function fetchJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(r.status + " " + url); return r.json(); }
  let detailPromise = null;
  // detail.json (phones, sites, notes, honors, licenses) is fetched only once someone reaches for a place
  function loadDetail() {
    detailPromise ||= fetchJSON(`${BASE}/data/detail.json`).then((d) => { D = Array.isArray(d) ? d : []; }).catch(() => { D = []; });
    return detailPromise;
  }

  async function load() {
    const d = await fetchJSON(`${BASE}/data/core.json`);
    GENERATED = d.generated || ""; CAL = d.calibration || {}; SOURCES = d.srcs || []; CHECKED = d.checked || "2026";
    ABC = num(d.abc_licenses) || 0; LIQ_DATE = d.liquor_updated || "";
    INS_PAGE = BASE + "/" + String(d.inspections_page || "");
    DISTRICT_OF = new Map();
    for (const x of Array.isArray(d.districts) ? d.districts : []) for (const co of x.counties || []) DISTRICT_OF.set(co, x);
    const C = d.cols, n = C.id.length, towns = new Map();
    P = new Array(n);
    TOWN_KEYS = new Map();
    for (let i = 0; i < n; i++) {
      const city = C.c[i] == null ? null : d.cities[C.c[i]], cu = d.cuisines[C.cu[i]], brand = C.b[i] == null ? null : d.brands[C.b[i]];
      const county = C.co[i] == null ? null : d.counties[C.co[i]];
      const p = { i, id: String(C.id[i]), n: String(C.n[i] ?? ""), c: city, co: county, cu, t: C.t[i], s: C.s[i], a: C.a[i], z: C.z[i], la: C.la[i], lo: C.lo[i],
        ch: num(C.ch[i]) || 1, v: C.v[i] === 1, g: C.g[i] || 0, hc: C.hc[i] === 1, ip: num(C.ip[i]), f: num(C.f[i]), h: C.h[i] || 0, j: C.j[i],
        jb: C.jb[i] === 1, dish: C.dish[i] };
      p.search = " " + normalize([p.n, city, county, p.z, cu, brand, p.dish].filter(Boolean).join(" ")) + " " + normAddr(p.a || "") + " ";
      p.nameText = " " + normalize([p.n, brand].filter(Boolean).join(" ")) + " ";
      p.key = normalize(p.n);   // the app's A-to-Z key: case, accents and leading punctuation don't change the order
      P[i] = p;
      if (city && !p.v) towns.set(city, (towns.get(city) || 0) + 1);
    }
    const byCount = [...towns.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    for (const [name] of byCount) { const k = normAddr(name); if (!TOWN_KEYS.has(k)) TOWN_KEYS.set(k, name); }   // biggest town wins a shared spelling
    TOWN_KEYS_BY_LENGTH = [...TOWN_KEYS.keys()].sort((a, b) => b.length - a.length);
    $("#ex-town").innerHTML = '<option value="">All towns</option>' + [...towns.keys()].sort((a, b) => a.localeCompare(b)).map((t) => `<option>${esc(t)}</option>`).join("");
    const cuis = new Map();
    for (const p of P) if (!p.v) cuis.set(p.cu, (cuis.get(p.cu) || 0) + 1);
    $("#ex-cuisine").innerHTML = '<option value="">All kinds</option>' + [...cuis.entries()].sort((a, b) => b[1] - a[1]).map(([c, k]) => `<option value="${esc(c)}">${esc(c)} (${esc(k.toLocaleString())})</option>`).join("");
  }

  // a guide button exists only for a guide with places (scripts/make-site.py leaves out an empty one, as the app's Home does)
  const guideOk = (g) => own(GUIDES, g) && (g === "saved" || g === "all" || Boolean(document.querySelector(`.ex-guides button[data-g="${g}"]`)));
  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    const last = store.get("guide", DEFAULT_GUIDE);
    // a returning visitor gets the guide they used last, unless it's an empty Saved list
    st.g = guideOk(h.get("g")) ? h.get("g") : guideOk(last) && !(last === "saved" && !saved.size) ? last : DEFAULT_GUIDE;
    st.q = h.get("q") || ""; st.town = h.get("town") || ""; st.cuisine = h.get("kind") || ""; st.chains = h.get("chains") === "1";
    st.sort = h.get("sort") || ""; st.p = h.get("p") || "";
  }
  function hashOf(withPlace) {
    const h = new URLSearchParams();
    h.set("g", st.g);
    if (st.q) h.set("q", st.q); if (st.town) h.set("town", st.town); if (st.cuisine) h.set("kind", st.cuisine);
    if (st.chains) h.set("chains", "1"); if (st.sort) h.set("sort", st.sort); if (withPlace && st.p) h.set("p", st.p);
    return "#" + h.toString();
  }
  const listHash = () => hashOf(false);
  // filter changes replace the current history entry; opening a place pushes one, so Back closes the panel
  function saveHash(push = false) {
    const url = hashOf(true);
    if (push) history.pushState({ ideats: "place" }, "", url);
    else history.replaceState(st.p ? { ideats: "place" } : null, "", url);
    store.set("guide", st.g);
  }

  function locate() {
    if (!navigator.geolocation) { $("#ex-locmsg").textContent = "This browser can't share its location."; return; }
    $("#ex-locmsg").textContent = "Finding you…";
    navigator.geolocation.getCurrentPosition((pos) => {
      here = { la: pos.coords.latitude, lo: pos.coords.longitude };
      const away = !inIdaho(here);   // the app's wording (GuideListView.swift); the map stays on Idaho rather than an empty spot
      $("#ex-locmsg").textContent = away
        ? "You're outside Idaho. Every place here is in Idaho, so distances are from where you are now. Your location stays in this browser."
        : "Sorted by distance from you. Your location stays in this browser.";
      $("#ex-locmsg").classList.toggle("ex-away", away);
      st.sort = GUIDES[st.g].sorts.includes("nearest") ? "nearest" : st.sort;
      if (view === "map" && !away) centerOn(here);
      shown = 100; render();
    }, () => { $("#ex-locmsg").textContent = "Location is off for this site. Allow it in your browser settings to sort by distance."; },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 0 });   // a fresh fix on every tap: an earlier one can be miles off
  }

  function setView(v) {
    view = v;
    document.querySelectorAll(".ex-view button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
    $("#ex-listwrap").hidden = v !== "list";
    $("#ex-mapwrap").hidden = v !== "map";
    render();
    if (v === "map" && phone.matches) $("#ex-mapwrap").scrollIntoView({ block: "nearest" });   // on phones the map starts below the fold
  }

  // the URL moved under us: Back/Forward (popstate) or a link to another #hash (hashchange). Both can fire for one step.
  function fromURL() {
    const before = listHash();
    readHash();
    if (listHash() !== before) { syncInputs(); shown = 100; render(); }
    const p = st.p && P.find((x) => x.id === st.p);
    const panel = $("#ex-panel");
    if (p) {
      if (panel.hidden || panel.dataset.id !== p.id) openPlace(p, false);
      // Forward onto an entry openPlace pushed: closing steps back over it again, so the next Back isn't a dead click
      if (history.state && history.state.ideats === "place" && listAtPush == null) listAtPush = listHash();
    }
    else if (!panel.hidden) closePlace(true);
  }

  function controls() {
    document.querySelectorAll(".ex-guides button").forEach((b) => b.onclick = () => { if (guideOk(b.dataset.g)) st.g = b.dataset.g; st.sort = ""; shown = 100; render(); });
    let t = null;
    $("#ex-q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { st.q = e.target.value; shown = 100; render(); }, 120); });
    $("#ex-sort").onchange = (e) => { st.sort = e.target.value; if (st.sort === "nearest" && !here) locate(); shown = 100; render(); };
    $("#ex-town").onchange = (e) => { st.town = e.target.value; shown = 100; render(); };
    $("#ex-cuisine").onchange = (e) => { st.cuisine = e.target.value; shown = 100; render(); };
    $("#ex-chains").onchange = (e) => { st.chains = e.target.checked; shown = 100; render(); };
    $("#ex-clear").onclick = () => { st.town = st.cuisine = ""; st.chains = false; syncInputs(); shown = 100; render(); };
    $("#ex-locate").onclick = locate;
    if ($("#ex-scrim")) $("#ex-scrim").onclick = () => closePlace();
    $("#ex-more").onclick = () => { shown += 200; renderList(order()); };
    document.querySelectorAll(".ex-view button").forEach((b) => b.onclick = () => setView(b.dataset.v));
    $("#ex-list").addEventListener("click", (e) => { const b = e.target.closest(".ex-row"); if (b && P[+b.dataset.i]) openPlace(P[+b.dataset.i]); });
    for (const ev of ["pointerover", "focusin"]) $("#ex-list").addEventListener(ev, () => loadDetail(), { once: true });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && st.p) closePlace(); });
    window.addEventListener("popstate", fromURL);
    window.addEventListener("hashchange", fromURL);
    phone.addEventListener?.("change", panelMode);
    mapEvents();
  }
  function syncInputs() {
    $("#ex-q").value = st.q; $("#ex-town").value = st.town; $("#ex-cuisine").value = st.cuisine; $("#ex-chains").checked = st.chains;
  }

  async function start() {
    const box = $("#ex-loading");
    box.hidden = false;
    box.textContent = "Loading the restaurant list…";
    try { await load(); } catch {
      box.innerHTML = 'The restaurant list couldn’t load. Check your connection, then <button type="button" class="ex-linkbtn" id="ex-retry">try again</button>';
      $("#ex-retry").onclick = start;
      return;
    }
    document.querySelectorAll("#ex-app [disabled]").forEach((el) => { el.disabled = false; });
    syncInputs();
    if (!wired) { controls(); wired = true; }
    box.hidden = true;
    render();
    const open = st.p && P.find((p) => p.id === st.p);
    if (open) { await loadDetail(); openPlace(open, false); }
  }

  // on a phone the guide chips scroll sideways (their right edge fades out over 32px): bring the current guide's chip into view
  function showChip() {
    const chip = document.querySelector(`.ex-guides button[data-g="${st.g}"]`), row = $(".ex-guides");
    if (!chip || !row) return;
    const c = chip.getBoundingClientRect(), r = row.getBoundingClientRect();
    if (c.right > r.right - 32 || c.left < r.left) row.scrollLeft += c.left - r.left - 16;
  }

  readHash();
  preRender();
  showChip();
  start();
})();
