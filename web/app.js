/* ============================================================
   VILLAVO · RUTAS — frontend
   Mapa Leaflet + renderer de canvas propio para animar la
   exploración (miles de segmentos) y la ruta final.
   ============================================================ */
"use strict";

const COLORS = {
  expFrom: [138, 61, 0],    // #8a3d00  exploración temprana
  expTo:   [255, 200, 87],  // #ffc857  exploración reciente
  path:    "#2ee6d6",
  pathGlow:"rgba(46,230,214,0.9)",
};

const state = {
  origin: null,      // {lat, lon}
  dest: null,
  algo: "dijkstra",
  speed: 5,
  running: false,
  nextClick: "origin",
};

/* ---------- Mapa ------------------------------------------- */
const map = L.map("map", { zoomControl: false, attributionControl: true })
  .setView([4.1334, -73.6267], 13);

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; OpenStreetMap · &copy; CARTO',
  subdomains: "abcd",
  maxZoom: 19,
}).addTo(map);

/* ---------- Renderer de canvas ----------------------------- */
class RouteRenderer {
  constructor(map) {
    this.map = map;
    this.main = document.getElementById("route-canvas");
    this.main.classList.add("leaflet-zoom-hide");      // Leaflet lo oculta al hacer zoom
    map.getPanes().overlayPane.appendChild(this.main); // bajo los marcadores
    this.mctx = this.main.getContext("2d");
    this.off = document.createElement("canvas");        // explorado cacheado
    this.octx = this.off.getContext("2d");
    this.explored = [];
    this.path = [];
    this.revealed = 0;
    this.pathK = 0;
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    this._scheduled = false;

    this.resize();
    window.addEventListener("resize", () => this.resize());
    map.on("moveend zoomend viewreset", () => { this.reset(); this._schedule(); });
  }

  resize() {
    const s = this.map.getSize();
    this.W = s.x; this.H = s.y;
    for (const cv of [this.main, this.off]) {
      cv.width = this.W * this.dpr; cv.height = this.H * this.dpr;
      cv.style.width = this.W + "px"; cv.style.height = this.H + "px";
    }
    this.octx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this.mctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this.reset();
    this.rebuild();
  }

  // alinea el origen del canvas con la esquina del contenedor del mapa
  reset() {
    L.DomUtil.setPosition(this.main, this.map.containerPointToLayerPoint([0, 0]));
  }

  _schedule() {
    if (this._scheduled) return;
    this._scheduled = true;
    requestAnimationFrame(() => { this._scheduled = false; this.rebuild(); });
  }

  _project(pt) { return this.map.latLngToContainerPoint([pt[0], pt[1]]); }

  _stroke(ctx, poly) {
    if (poly.length < 2) return;
    const p = this._project(poly[0]);
    ctx.moveTo(p.x, p.y);
    for (let i = 1; i < poly.length; i++) {
      const q = this._project(poly[i]);
      ctx.lineTo(q.x, q.y);
    }
  }

  _expColor(i) {
    const t = this.explored.length > 1 ? i / (this.explored.length - 1) : 1;
    const e = (a, b) => Math.round(a + (b - a) * t);
    const [r, g, b] = [0, 1, 2].map(k => e(COLORS.expFrom[k], COLORS.expTo[k]));
    return `rgba(${r},${g},${b},0.55)`;
  }

  setData(explored, path) {
    this.explored = explored; this.path = path;
    this.revealed = 0; this.pathK = 0;
    this.octx.clearRect(0, 0, this.W, this.H);
    this._blit();
  }

  // dibuja explorados [this.revealed, n) sobre el canvas offscreen (incremental)
  revealExplored(n) {
    const ctx = this.octx;
    ctx.lineWidth = 1.15; ctx.lineCap = "round";
    for (let i = this.revealed; i < n; i++) {
      ctx.beginPath();
      ctx.strokeStyle = this._expColor(i);
      this._stroke(ctx, this.explored[i]);
      ctx.stroke();
    }
    this.revealed = n;
    this._blit();
  }

  _blit() {
    const c = this.mctx;
    c.save();
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.clearRect(0, 0, this.main.width, this.main.height);
    c.drawImage(this.off, 0, 0);
    c.restore();
  }

  drawPath(k) {
    this.pathK = k;
    this._blit();
    const ctx = this.mctx;
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    // halo
    ctx.shadowColor = COLORS.pathGlow; ctx.shadowBlur = 14;
    ctx.strokeStyle = COLORS.path; ctx.lineWidth = 4.5;
    ctx.beginPath();
    for (let i = 0; i < k; i++) this._stroke(ctx, this.path[i]);
    ctx.stroke();
    // núcleo nítido
    ctx.shadowBlur = 0; ctx.strokeStyle = "rgba(230,255,252,0.9)"; ctx.lineWidth = 1.4;
    ctx.beginPath();
    for (let i = 0; i < k; i++) this._stroke(ctx, this.path[i]);
    ctx.stroke();
  }

  rebuild() {
    // reproyecta todo lo revelado (tras pan/zoom)
    this.octx.clearRect(0, 0, this.W, this.H);
    const n = this.revealed; this.revealed = 0;
    this.revealExplored(n);
    if (this.pathK > 0) this.drawPath(this.pathK);
  }

  clear() {
    this.explored = []; this.path = []; this.revealed = 0; this.pathK = 0;
    this.octx.clearRect(0, 0, this.W, this.H);
    this._blit();
  }
}

const renderer = new RouteRenderer(map);

/* ---------- Marcadores ------------------------------------- */
function pinIcon(role) {
  return L.divIcon({
    className: "",
    html: `<div class="pin pin--${role}"><span class="pin__ring"></span><span class="pin__core"></span></div>`,
    iconSize: [14, 14], iconAnchor: [7, 7],
  });
}
const markers = { origin: null, dest: null };

function setMarker(role, lat, lon) {
  const r = role === "origin" ? "o" : "d";
  if (markers[role]) markers[role].setLatLng([lat, lon]);
  else markers[role] = L.marker([lat, lon], { icon: pinIcon(r), interactive: false }).addTo(map);
}

/* ---------- Estado / UI ------------------------------------ */
const $ = (s) => document.querySelector(s);
const traceBtn = $("#trace-btn");
const statusText = $("#status-text");
const fields = { origin: $('.field[data-role="origin"]'), dest: $('.field[data-role="dest"]') };

function status(msg) { statusText.textContent = msg; }

function highlightNext() {
  fields.origin.classList.toggle("is-active", state.nextClick === "origin");
  fields.dest.classList.toggle("is-active", state.nextClick === "dest");
}

function setPoint(role, lat, lon, label) {
  state[role] = { lat, lon };
  setMarker(role, lat, lon);
  $(`#${role}-input`).value = label || `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  state.nextClick = role === "origin" ? "dest" : "origin";
  highlightNext();
  traceBtn.disabled = !(state.origin && state.dest) || state.running;
}

/* ---------- Eventos de mapa -------------------------------- */
map.on("click", (e) => {
  if (state.running) return;
  const role = state.nextClick;
  setPoint(role, e.latlng.lat, e.latlng.lng);
  status(role === "origin"
    ? "Origen fijado · ahora marca el destino"
    : "Destino fijado · listo para trazar");
});

/* ---------- Geocodificación -------------------------------- */
async function geocode(role) {
  const q = $(`#${role}-input`).value.trim();
  if (!q) return;
  status(`Buscando «${q}»…`);
  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
    if (!res.ok) { status("Dirección no encontrada"); return; }
    const d = await res.json();
    const short = d.display_name.split(",").slice(0, 2).join(",");
    setPoint(role, d.lat, d.lon, short);
    map.panTo([d.lat, d.lon]);
    status(`${role === "origin" ? "Origen" : "Destino"}: ${short}`);
  } catch { status("Error de red al geocodificar"); }
}

document.querySelectorAll("[data-geocode]").forEach((b) =>
  b.addEventListener("click", () => geocode(b.dataset.geocode)));
["origin", "dest"].forEach((role) => {
  const inp = $(`#${role}-input`);
  inp.addEventListener("keydown", (e) => { if (e.key === "Enter") geocode(role); });
  inp.addEventListener("focus", () => { state.nextClick = role; highlightNext(); });
});

$("#swap-btn").addEventListener("click", () => {
  if (!state.origin && !state.dest) return;
  const o = state.origin, d = state.dest;
  const oi = $("#origin-input").value, di = $("#dest-input").value;
  state.origin = state.dest = null;
  if (d) setPoint("origin", d.lat, d.lon, di);
  if (o) setPoint("dest", o.lat, o.lon, oi);
  status("Origen y destino intercambiados");
});

/* ---------- Selector de algoritmo + velocidad -------------- */
const seg = $("#algo-seg");
seg.querySelectorAll(".seg").forEach((btn, i) => {
  btn.addEventListener("click", () => {
    seg.querySelectorAll(".seg").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    seg.dataset.pos = i;
    state.algo = btn.dataset.algo;
  });
});
$("#speed").addEventListener("input", (e) => { state.speed = +e.target.value; });

/* ---------- Trazado de ruta -------------------------------- */
async function fetchRoute(algorithm) {
  const res = await fetch("/api/route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origin: { lat: state.origin.lat, lon: state.origin.lon },
      dest: { lat: state.dest.lat, lon: state.dest.lon },
      algorithm,
    }),
  });
  return res.json();
}

function showReadout(sel, results) {
  $("#readout").hidden = false;
  $("#r-dist").textContent = sel.stats.distance_km.toFixed(2);
  $("#r-time").textContent = sel.stats.time_min.toFixed(1);
  const dij = results.dijkstra.stats.iterations;
  const ast = results.a_star.stats.iterations;
  $("#r-dij").textContent = dij.toLocaleString("es");
  $("#r-astar").textContent = ast.toLocaleString("es");
  const ratio = dij ? Math.round((1 - ast / dij) * 100) : 0;
  $("#r-bar").style.width = (dij ? (ast / dij) * 100 : 0) + "%";
  $("#r-note").textContent = ratio > 0
    ? `A* exploró ${ratio}% menos nodos que Dijkstra para la misma ruta óptima.`
    : "Ambos exploraron un frente similar en este caso.";
}

function frameTarget() { return Math.max(16, 150 - state.speed * 11); }

function animateExploration(explored) {
  return new Promise((resolve) => {
    const perFrame = Math.max(4, Math.ceil(explored.length / frameTarget()));
    let i = 0;
    const step = () => {
      i = Math.min(explored.length, i + perFrame);
      renderer.revealExplored(i);
      if (i < explored.length) requestAnimationFrame(step);
      else resolve();
    };
    requestAnimationFrame(step);
  });
}

function animatePath(path) {
  return new Promise((resolve) => {
    const frames = Math.max(18, Math.min(55, path.length));
    let f = 0;
    const step = () => {
      f++;
      renderer.drawPath(Math.ceil((path.length * f) / frames));
      if (f < frames) requestAnimationFrame(step);
      else resolve();
    };
    requestAnimationFrame(step);
  });
}

async function trace() {
  if (!state.origin || !state.dest || state.running) return;
  state.running = true;
  traceBtn.disabled = true;
  traceBtn.classList.add("is-running");
  renderer.clear();
  status("Calculando ruta…");

  let results;
  try {
    const [a, b] = await Promise.all([fetchRoute("dijkstra"), fetchRoute("a_star")]);
    results = { dijkstra: a, a_star: b };
  } catch {
    status("Error de red al calcular la ruta");
    state.running = false; traceBtn.classList.remove("is-running");
    traceBtn.disabled = false; return;
  }

  const sel = results[state.algo];
  if (!sel.found) {
    status("No hay ruta posible entre esos dos puntos");
    state.running = false; traceBtn.classList.remove("is-running");
    traceBtn.disabled = false; return;
  }

  // reubicar marcadores al nodo real de la malla
  setMarker("origin", sel.origin.snapped[0], sel.origin.snapped[1]);
  setMarker("dest", sel.dest.snapped[0], sel.dest.snapped[1]);

  showReadout(sel, results);
  renderer.setData(sel.explored, sel.path);

  status(`Explorando con ${state.algo === "a_star" ? "A*" : "Dijkstra"}…`);
  await animateExploration(sel.explored);
  status("Reconstruyendo ruta óptima…");
  await animatePath(sel.path);

  const b = L.latLngBounds(sel.path.flat().map((p) => [p[0], p[1]]));
  map.fitBounds(b, { paddingTopLeft: [380, 60], paddingBottomRight: [60, 80] });

  status(`Ruta encontrada · ${sel.stats.distance_km.toFixed(2)} km · ${sel.stats.time_min.toFixed(0)} min`);
  state.running = false;
  traceBtn.classList.remove("is-running");
  traceBtn.disabled = false;
}

traceBtn.addEventListener("click", trace);

/* ---------- Metadatos / arranque --------------------------- */
(async function init() {
  try {
    const m = await (await fetch("/api/meta")).json();
    map.fitBounds([m.bounds[0], m.bounds[1]]);
    $("#status-meta").textContent =
      `${m.place} · ${m.nodes.toLocaleString("es")} nodos · ${m.edges.toLocaleString("es")} aristas`;
    status("Marca un origen y un destino (clic en el mapa)");
    highlightNext();
  } catch {
    status("No se pudo cargar la malla vial");
  }
})();
