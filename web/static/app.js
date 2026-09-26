const $ = s => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => { const n = Object.assign(document.createElement(tag), attrs); n.append(...kids); return n; };
const svgNS = "http://www.w3.org/2000/svg";
const sv = (tag, attrs = {}, ...kids) => { const n = document.createElementNS(svgNS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); n.append(...kids); return n; };
const fmt = (v, d = 0) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
const STEPS = ["Dead load stages", "Influence surfaces", "Searching traffic", "Fatigue truck", "Checking in OpenSees", "Preparing the plots"];
const M = "maximum composite moment", V = "support shear", R = "bearing reaction";
const ULS = "ultimate, basic", RARE = "serviceability, rare";
const state = { tables: {}, on: {}, strips: [] };
let schema, result, job, girder = 0;

// ── inputs, from the same schema as examples/form.html ──────────────────────
function field(f, value, onChange) {
  let input;
  if (f.choices) {
    input = el("select");
    f.choices.forEach(c => input.append(el("option", { value: String(c), textContent: String(c), selected: String(c) === String(value) })));
    input.onchange = () => onChange(input.value === "true" ? true : input.value === "false" ? false : isNaN(input.value) ? input.value : Number(input.value));
  } else {
    input = el("input", { type: "number", step: f.integer ? 1 : "any", value, required: true });
    if (f.min !== undefined) input.min = f.min;
    if (f.max !== undefined) input.max = f.max;
    input.oninput = () => onChange(input.value === "" ? "" : Number(input.value));
  }
  return el("label", {}, f.label, input);
}

function tableGroup(t, open) {
  const box = el("details", { open });
  const title = el("summary", {}, t.title);
  box.append(title);
  if (t.strips) return stripsGroup(box, t);
  state.tables[t.table] = {};
  const grid = el("div", { className: "grid" });
  if (t.optional) {
    state.on[t.table] = true;
    const on = el("input", { type: "checkbox", checked: true });
    on.onchange = () => { state.on[t.table] = on.checked; box.classList.toggle("off", !on.checked); };
    box.append(el("label", { className: "toggle" }, on, "include this load"));
  }
  t.fields.forEach(f => { state.tables[t.table][f.key] = f.value; grid.append(field(f, f.value, v => state.tables[t.table][f.key] = v)); });
  box.append(grid);
  return box;
}

function stripsGroup(box, t) {
  state.strips = t.strips.map(s => [...s]);
  const rows = el("div");
  const draw = () => rows.replaceChildren(...state.strips.map((strip, k) => {
    const name = el("input", { value: strip[0] }); name.oninput = () => strip[0] = name.value;
    const width = el("input", { type: "number", step: "any", min: 0, value: strip[1] }); width.oninput = () => strip[1] = Number(width.value);
    const remove = el("button", { textContent: "×", title: "remove" }); remove.onclick = () => { state.strips.splice(k, 1); draw(); };
    return el("div", { className: "strip" }, name, width, remove);
  }));
  const add = el("button", { textContent: "+ strip" }); add.style.marginTop = "6px";
  add.onclick = () => { state.strips.push(["carriageway", 3.5]); draw(); };
  draw();
  box.append(rows, add, el("p", { className: "sub", textContent: "Names start with footpath, kerb, carriageway, median, crash_barrier or railing." }));
  return box;
}

// what the page sends: every table's values, the strips left to right, and which site loads are ticked
function formData() {
  return { tables: state.tables, strips: state.strips, include: state.on };
}

// ── running ─────────────────────────────────────────────────────────────────
async function analyse() {
  $("#input-error").textContent = "";
  const response = await fetch("/analyse", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(formData()) });
  const reply = await response.json();
  if (!response.ok) { $("#input-error").textContent = reply.error; return; }
  job = reply.id;
  $("#analyse").disabled = true;
  showProgress();
  const events = new EventSource(`/progress/${job}`);
  events.onmessage = async e => {
    const s = JSON.parse(e.data);
    updateProgress(s);
    if (s.error) { events.close(); $("#analyse").disabled = false; $("#progress-error").textContent = s.error; }
    if (s.finished) { events.close(); result = await (await fetch(`/result/${job}`)).json(); $("#analyse").disabled = false; showResults(); }
  };
}

function showProgress() {
  $("#out").replaceChildren(el("div", { className: "card pad" },
    el("h2", {}, "Analysing the bridge"), el("p", { className: "sub", id: "progress-text", textContent: "Starting…" }),
    el("div", { className: "bar" }, el("div", { id: "progress-bar" })),
    el("ul", { className: "steps", id: "steps" }, ...STEPS.map(s => el("li", { textContent: s }))),
    el("div", { className: "error", id: "progress-error" })));
}

function updateProgress(s) {
  $("#progress-bar").style.width = `${s.percent}%`;
  $("#progress-text").textContent = `${s.step}${s.of > 1 ? ` · ${s.count} of ${s.of}` : ""} · ${s.percent}% · ${s.seconds} s`;
  const now = STEPS.indexOf(s.step);
  [...$("#steps").children].forEach((li, k) => { li.className = s.finished || k < now ? "done" : k === now ? "now" : ""; li.textContent = (li.className === "done" ? "✓ " : "") + STEPS[k]; });
}

// ── results ─────────────────────────────────────────────────────────────────
const girderName = g => `Girder ${g}${g === 0 || g === result.bridge.girders - 1 ? " (edge)" : ""}`;
const design = (g, response, limit, adverse) => result.design_values[`girder ${g}`]?.[response]?.[limit]?.[adverse]?.value;
const girders = () => [...Array(result.bridge.girders).keys()];
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const PALETTE = ["#2458d3", "#e4572e", "#1f8a4c", "#9b5de5", "#f2a007", "#00a6a6", "#c2185b", "#6d4c41", "#546e7a", "#7cb342", "#3949ab", "#d81b60"];
let tab = "positions", plotCase = null, plotGirder = "all", plotQty = "m", addDead = false;

function stat(k, value, unit, text) {
  return el("div", { className: "card stat" }, el("div", { className: "k", textContent: k }),
    el("div", { className: "v" }, value, el("small", { textContent: ` ${unit}` })), el("p", {}, ...[text].flat()));
}

function check(value, limit) {
  const ok = value <= limit;
  return el("span", { className: ok ? "pass" : "fail", textContent: ok ? "✓ within the limit" : "✗ over the limit" });
}

function showResults() {
  const g = result.governing, L = result.bridge.span_m;
  const worst = key => girders().reduce((a, b) => (result.deflections_m[`girder ${b}`][key] > result.deflections_m[`girder ${a}`][key] ? b : a), 0);
  const live = worst("live_m"), total = worst("total_m");
  const liveMm = 1000 * result.deflections_m[`girder ${live}`].live_m, totalMm = 1000 * result.deflections_m[`girder ${total}`].total_m;
  const fatigue = girders().reduce((a, b) => (result.fatigue_ranges[`girder ${b}`][M].range > result.fatigue_ranges[`girder ${a}`][M].range ? b : a), 0);
  const trucks = result.drawing.max_moment[g["ULS sagging"].girder];
  const cards = el("div", { className: "cards" },
    stat("Largest bending moment", fmt(g["ULS sagging"].value), "kN·m",
      `Design (ULS) value in ${girderName(g["ULS sagging"].girder)}, ${fmt(g["ULS sagging"].at_m, 1)} m from the bearing. The traffic is ${describeTraffic(trucks)}.`),
    stat("Largest shear at the support", fmt(Math.abs(g["ULS shear"].value)), "kN", `Design (ULS) value in ${girderName(g["ULS shear"].girder)}, at the bearing.`),
    stat("Largest bearing reaction", fmt(g["ULS reaction"].value), "kN", `Design (ULS) value, ${girderName(g["ULS reaction"].girder)}. Use it to size the bearing.`),
    stat("Traffic deflection", fmt(liveMm, 1), "mm",
      [`Live load with impact, no footway, ${girderName(live)}. Limit span/800 = ${fmt(1000 * L / 800, 1)} mm. `, check(liveMm, 1000 * L / 800)]),
    stat("Total deflection", fmt(totalMm, 1), "mm",
      [`Dead load, surfacing and traffic, ${girderName(total)}. Limit span/600 = ${fmt(1000 * L / 600, 1)} mm before camber. `, check(totalMm, 1000 * L / 600)]),
    stat("Fatigue moment range", fmt(result.fatigue_ranges[`girder ${fatigue}`][M].range), "kN·m", `One 40 t fatigue truck passing over, ${girderName(fatigue)} (IRC:6 204.6).`));
  const site = result.site;
  if (site.seismic)
    cards.append(stat("Seismic case moment", fmt(g["ULS seismic"].value), "kN·m", `Ah = ${fmt(site.seismic.horizontal_coefficient, 3)}, ${girderName(g["ULS seismic"].girder)}.`));
  if (site.temperature)
    cards.append(stat("Bearing movement", fmt(1000 * site.temperature.free_bearing_movement_m, 1), "mm",
      `Free bearing, effective temperature ${fmt(site.temperature.effective_range_c[0])} to ${fmt(site.temperature.effective_range_c[1])} °C (IRC:6 215). No girder force.`));
  if (site.wind)
    cards.append(stat("Wind at deck level", fmt(site.wind.speed_at_deck_mps, 1), "m/s", `Transverse force ${fmt(site.wind.forces_kn.transverse)} kN on the deck (IRC:6 209).`));
  girder = g["ULS sagging"].girder;
  plotCase = `Live · largest moment in G${girder}`;
  const tabs = el("div", { className: "big-tabs", id: "big-tabs" }, ...[["positions", "Critical positions"], ["replay", "Search replay"], ["diagrams", "Girder diagrams"], ["model", "3D model"], ["site", "Site loads"]]
    .map(([key, label]) => { const b = el("button", { textContent: label }); b.dataset.tab = key; b.onclick = () => { tab = key; showTab(); }; return b; }));
  $("#out").replaceChildren(cards, tabs, el("div", { id: "panel" }), tableCard());
  showTab();
}

function showTab() {
  stopReplay();
  [...$("#big-tabs").children].forEach(b => b.classList.toggle("on", b.dataset.tab === tab));
  const panel = $("#panel");
  if (tab === "positions") { panel.replaceChildren(deckCard()); drawDeck(); }
  if (tab === "replay") { panel.replaceChildren(replayCard()); startReplay(); }
  if (tab === "diagrams") { panel.replaceChildren(diagramCard()); drawDiagrams(); }
  if (tab === "model") { panel.replaceChildren(modelCard()); drawModel(); }
  if (tab === "site") { panel.replaceChildren(siteCard()); drawSite(); }
}

function describeTraffic(d) {
  const counts = {};
  d.vehicles.forEach(v => counts[v.name] = (counts[v.name] || 0) + 1);
  const list = Object.entries(counts).map(([name, n]) => `${n} × ${name}`).join(" and ");
  return `${list}${d.patches.some(p => p.kind === "residual UDL") ? " plus the residual lane load" : ""}${d.patches.some(p => p.kind === "footway") ? " plus people on the footpath" : ""}`;
}

// the design places Setu checks on every girder; the page shows one at a time
let place = "moment";
function placeTabs(onPick) {
  return el("div", { className: "tabs" }, ...Object.entries(result.places).map(([key, p]) => {
    const b = el("button", { textContent: p.label, className: key === place ? "on" : "" });
    b.onclick = () => { place = key; onPick(); }; return b;
  }));
}
const placeInfo = () => result.places[place];

function girderTabs(onPick) {
  return el("div", { className: "tabs" }, ...girders().map(k => {
    const b = el("button", { textContent: girderName(k), className: k === girder ? "on" : "" });
    b.onclick = () => { girder = k; onPick(); }; return b;
  }));
}

// ── the deck, drawn to scale from above ─────────────────────────────────────
function stripColour(name) {
  if (name.startsWith("carriageway")) return "var(--asphalt)";
  if (name.startsWith("footpath")) return "var(--footpath)";
  return "var(--kerb)";
}

// the deck, bearings and girder lines; returns the svg and a layer to put vehicles in
function deckSvg(extraXs = []) {
  const d = result.drawing, W = d.width_m, L = d.span_m, s = d.skew;
  const xs = [0, L, s * W, L + s * W, ...extraXs];
  const x0 = Math.max(Math.min(...xs), -0.3 * L) - 1, x1 = Math.min(Math.max(...xs), 1.3 * L + s * W) + 1;
  const svg = sv("svg", { viewBox: `${x0} -2.2 ${x1 - x0} ${W + 3.6}`, role: "img", "aria-label": "top view of the deck" });
  svg.append(sv("defs", {},
    sv("clipPath", { id: "view" }, sv("rect", { x: x0, y: -0.5, width: x1 - x0, height: W + 1 })),
));
  SetuVehicles.defs(svg);
  const at = (x, z) => `${x + s * z},${z}`;
  const band = (z0, z1, fill, extra = {}) => sv("polygon", { points: [at(0, z0), at(L, z0), at(L, z1), at(0, z1)].join(" "), fill, ...extra });
  d.strips.forEach(strip => [[x0, s * strip.from_m, s * strip.to_m, x0], [L + s * strip.from_m, x1, x1, L + s * strip.to_m]].forEach(([a, b, c, e]) =>
    svg.append(sv("polygon", { points: `${a},${strip.from_m} ${b},${strip.from_m} ${c},${strip.to_m} ${e},${strip.to_m}`, fill: stripColour(strip.name), opacity: 0.4 }))));
  d.strips.forEach(strip => {
    svg.append(band(strip.from_m, strip.to_m, stripColour(strip.name), {}, sv("title", {}, `${strip.name.replaceAll("_", " ")}: ${fmt(strip.to_m - strip.from_m, 2)} m`)));
    if (strip.name.startsWith("carriageway"))
      [strip.from_m + 0.12, strip.to_m - 0.12].forEach(z => svg.append(sv("line", { x1: s * z, y1: z, x2: L + s * z, y2: z, stroke: "#f4f1ea", "stroke-width": 0.08, opacity: 0.8 })));
    if (strip.name.startsWith("footpath"))
      for (let x = 0.6; x < L; x += 0.6) svg.append(sv("line", { x1: x + s * strip.from_m, y1: strip.from_m, x2: x + s * strip.to_m, y2: strip.to_m, stroke: "rgba(0,0,0,.07)", "stroke-width": 0.03 }));
  });
  [0, L].forEach(x => svg.append(sv("line", { x1: x, y1: -0.3, x2: x + s * W, y2: W + 0.3, stroke: "var(--ink)", "stroke-width": 0.1 })));
  svg.append(sv("text", { x: 0, y: -1.2, "font-size": 0.6, fill: "var(--muted)" }, "bearing"), sv("text", { x: L, y: -1.2, "font-size": 0.6, fill: "var(--muted)", "text-anchor": "end" }, "bearing"));
  svg.append(sv("text", { x: L / 2, y: W + 1.1, "font-size": 0.6, fill: "var(--muted)", "text-anchor": "middle" }, `span ${fmt(L, 1)} m · deck ${fmt(W, 2)} m wide`));
  const loads = sv("g");
  svg.append(loads);
  d.girder_lines_m.forEach((z, k) => {
    svg.append(sv("line", { x1: s * z, y1: z, x2: L + s * z, y2: z, stroke: k === girder ? "var(--accent)" : "rgba(255,255,255,.35)", "stroke-width": k === girder ? 0.12 : 0.05, "stroke-dasharray": "0.5 0.3" }));
    svg.append(sv("text", { x: s * z - 0.3, y: z + 0.2, "font-size": 0.5, fill: k === girder ? "var(--accent)" : "var(--muted)", "text-anchor": "end", "font-weight": k === girder ? 700 : 400 }, `G${k}`));
  });
  const layer = sv("g", { "clip-path": "url(#view)" });
  svg.append(layer);
  return { svg, layer, loads };
}

// one vehicle seen from above, drawn by the shared docs/javascripts/vehicles.js
function vehicleSvg(v) {
  return SetuVehicles.draw(v, { title: `${v.name}${v.heading > 0 ? " (turned round)" : ""}\n${v.tracked ? "tracked, " : ""}`
    + `${v.tracked ? "total" : "axle loads"} ${v.axle_loads_t.join(", ")} t\nfront axle at x = ${fmt(v.x_m, 2)} m, centre z = ${fmt(v.z_m, 2)} m\nimpact factor ${fmt(v.impact_factor, 3)}` });
}

function placeVehicle(v, shift = 0) {
  const g = vehicleSvg(v);
  g.setAttribute("transform", `translate(${v.x_m + shift},${v.z_m})`);
  return g;
}

function deckCard() {
  return el("div", { className: "card pad deck" },
    el("h2", { id: "deck-title" }),
    el("p", { className: "sub", id: "deck-caption" }), el("div", { id: "place-tabs" }), el("div", { id: "girder-tabs" }), el("div", { id: "deck" }),
    el("div", { className: "legend" },
      el("span", {}, el("i", { style: "background:var(--asphalt)" }), "carriageway"), el("span", {}, el("i", { style: "background:var(--footpath)" }), "footpath"),
      el("span", {}, el("i", { style: "background:var(--kerb)" }), "kerb / median"),
      el("span", {}, el("i", { style: "background:var(--udl);outline:1px solid var(--accent)" }), "lane load"), el("span", {}, el("i", { style: "background:var(--foot);outline:1px solid var(--ok)" }), "footpath load"),
      el("span", {}, el("i", { style: "background:var(--bad)" }), "section checked")),
    el("div", { className: "row" },
      el("button", { className: "primary", textContent: "Export critical loads CSV (this girder, maximum moment)", onclick: () => location.href = `/critical-loads/${job}.csv?girder=${girder}` }),
      el("button", { textContent: "Export critical loads CSV (all girders, maximum moment)", onclick: () => location.href = `/critical-loads/${job}.csv?girder=all` }),
      el("span", { className: "sub", style: "margin:0", textContent: "Wheels as point loads (impact and lane reduction included), lane and footpath loads as area loads." })));
}

function sectionMarker(svg, at_m) {
  const d = result.drawing, zg = d.girder_lines_m[girder], x = at_m + d.skew * zg;
  const atBearing = at_m < 0.5;
  svg.append(sv("line", { x1: x, y1: zg - 1.1, x2: x, y2: zg + 1.1, stroke: "var(--bad)", "stroke-width": 0.14 }),
    sv("text", { x: atBearing ? x + 0.4 : x, y: atBearing ? d.width_m + 1.1 : -1.2, "font-size": 0.6, fill: "var(--bad)", "text-anchor": atBearing ? "start" : "middle", "font-weight": 700 },
      atBearing ? "checked at the bearing" : `x = ${fmt(at_m, 2)} m`));
}

function drawDeck() {
  $("#girder-tabs").replaceChildren(girderTabs(drawDeck));
  $("#place-tabs").replaceChildren(placeTabs(drawDeck));
  const c = result.drawing.places[place][girder], p = placeInfo();
  $("#deck-title").textContent = `Where the traffic stands for the worst ${p.label.toLowerCase()}`;
  const { svg, layer, loads } = deckSvg(c.vehicles.flatMap(v => [v.from_m, v.to_m]));
  c.patches.forEach(p => loads.append(sv("polygon", { points: p.corners.map(([x, z]) => `${x},${z}`).join(" "),
    fill: p.kind === "footway" ? "var(--foot)" : "var(--udl)" }, sv("title", {}, `${p.kind}: ${fmt(p.kpa, 2)} kN/m²`))));
  c.vehicles.forEach(v => layer.append(placeVehicle(v)));
  sectionMarker(svg, c.at_m);
  $("#deck").replaceChildren(svg);
  $("#deck-caption").textContent = `${girderName(girder)}: ${describeTraffic(c)}. Live load ${p.label.toLowerCase()} ${fmt(c.value, place === "deflection" ? 2 : 0)} ${p.unit}`
    + ` (impact included, lane reduction ${fmt(c.lane_reduction, 2)}${place === "deflection" ? ", footway left out as IRC:22 allows" : ""}). Hover a vehicle for its details.`;
}

// ── search replay: every vehicle rolled along every lane, then Setu's best arrangements ──
const HOLD = 18;
let replay = null;

function replayCard() {
  return el("div", { className: "card pad" },
    el("h2", {}, "How Setu finds the worst place for the traffic"),
    el("p", { className: "sub" }, "↺ = vehicle turned round, c/w = carriageway. Pick a result and a girder: Setu searches every one. Each vehicle is rolled along each lane; the line shows the effect it makes at that place at every position (read off the girder's influence surface). "
      + "Then Setu's best lane arrangements are rolled together, and the worst one wins. Arrangement bars include the lane reduction and the lane and footpath loads."),
    el("div", { id: "place-tabs" }), el("div", { id: "girder-tabs" }),
    el("div", { id: "replay-deck", className: "deck" }),
    el("div", { className: "player" },
      el("button", { id: "play", className: "primary", textContent: "❚❚ Pause" }),
      el("input", { id: "scrub", type: "range", min: 0, value: 0 }),
      el("select", { id: "speed" }, ...[["0.5", "0.5×"], ["1", "1×"], ["2", "2×"], ["4", "4×"]].map(([v, t]) => el("option", { value: v, textContent: t, selected: v === "1" })))),
    el("div", { className: "now-trying", id: "trying" }),
    el("div", { className: "charts2" }, el("div", { id: "trace", className: "plot" }), el("div", { id: "race", className: "plot" })));
}

function startReplay() {
  $("#girder-tabs").replaceChildren(girderTabs(() => { stopReplay(); showTab(); }));
  $("#place-tabs").replaceChildren(placeTabs(() => { stopReplay(); showTab(); }));
  const r = result.replay[place][girder], trials = r.trials;
  const starts = [];
  let total = 0;
  trials.forEach(t => { starts.push(total); total += t.shifts.length + HOLD; });
  const all = trials.flatMap(t => t.vehicles.flatMap(v => [v.from_m - Math.max(...t.shifts), v.to_m + Math.max(...t.shifts)]));
  const { svg, layer } = deckSvg([Math.max(-8, Math.min(...all)), Math.min(result.bridge.span_m + 8, Math.max(...all))]);
  sectionMarker(svg, r.at_m);
  $("#replay-deck").replaceChildren(svg);
  replay = { r, trials, starts, total, frame: 0, playing: true, layer, shown: -1, groups: [], last: performance.now(), raceShown: -1 };
  $("#scrub").max = total - 1;
  $("#scrub").oninput = e => { replay.frame = Number(e.target.value); renderReplay(); };
  $("#play").onclick = () => {
    if (replay.frame >= replay.total - 1) replay.frame = 0;
    replay.playing = !replay.playing; $("#play").textContent = replay.playing ? "❚❚ Pause" : "▶ Play";
  };
  Plotly.newPlot("trace", [], traceLayout(), { displayModeBar: false, responsive: true });
  Plotly.newPlot("race", [], raceLayout(), { displayModeBar: false, responsive: true });
  renderReplay();
  replay.timer = requestAnimationFrame(tickReplay);
}

function stopReplay() { if (replay) { cancelAnimationFrame(replay.timer); replay = null; } }

function tickReplay(now) {
  if (!replay) return;
  const speed = Number($("#speed")?.value || 1);
  if (replay.playing) {
    replay.frame = Math.min(replay.total - 1, replay.frame + (now - replay.last) * 0.045 * speed);
    if (replay.frame >= replay.total - 1) { replay.playing = false; $("#play").textContent = "↺ Replay"; }
    renderReplay();
  }
  replay.last = now;
  replay.timer = requestAnimationFrame(tickReplay);
}

function traceLayout() {
  const p = placeInfo();
  return plotLayout({ title: { text: `${p.label} in G${girder} as the vehicles roll${place === "shear" ? " (magnitude)" : ""}`, font: { size: 13 } }, showlegend: false, margin: { l: 60, r: 16, t: 36, b: 44 },
    xaxis: axis({ title: "front axle of the first vehicle, x (m)", range: [-10, result.bridge.span_m + 10] }), yaxis: axis({ title: p.unit, rangemode: "tozero" }) });
}

function raceLayout() {
  return plotLayout({ title: { text: "What was tried (largest effect of each)", font: { size: 13 } }, showlegend: false, margin: { l: 200, r: 60, t: 36, b: 40 },
    xaxis: axis({ title: placeInfo().unit, rangemode: "tozero" }), yaxis: axis({ autorange: "reversed", automargin: true, tickfont: { size: 11 } }), bargap: 0.25 });
}

function renderReplay() {
  const { trials, starts, total } = replay;
  const f = Math.floor(replay.frame);
  $("#scrub").value = f;
  let k = starts.length - 1;
  while (starts[k] > f) k--;
  const t = trials[k], i = f - starts[k], rolling = i < t.shifts.length, idx = rolling ? i : (t.kind === "arrangement" && t.winner ? t.shifts.indexOf(0) : t.peak_at);
  const finished = f >= total - 1;
  if (replay.shown !== k) {
    replay.layer.replaceChildren(...t.vehicles.map(v => vehicleSvg(v)));
    replay.shown = k;
  }
  [...replay.layer.children].forEach((g, n) => g.setAttribute("transform", `translate(${t.vehicles[n].x_m + t.vehicles[n].heading * t.shifts[idx]},${t.vehicles[n].z_m})`));
  const x0 = t.vehicles[0].x_m, h0 = t.vehicles[0].heading;
  const done = trials.slice(0, k).map((p, n) => ({ x: p.shifts.map(s => p.vehicles[0].x_m + p.vehicles[0].heading * s), y: p.moments, mode: "lines", hoverinfo: "skip",
    line: { width: 1.2, color: p.kind === "arrangement" ? "rgba(36,88,211,.35)" : "rgba(128,128,128,.35)" } }));
  const upto = Math.min(idx + 1, t.shifts.length);
  const running = t.moments.slice(0, rolling ? upto : t.moments.length);
  const best = running.indexOf(Math.max(...running));
  const colour = t.winner ? css("--ok") : t.kind === "arrangement" ? css("--accent") : css("--truck-edge");
  Plotly.react("trace", [...done,
    { x: t.shifts.slice(0, running.length).map(s => x0 + h0 * s), y: running, mode: "lines", line: { width: 3, color: colour }, hovertemplate: `x %{x:.1f} m<br>%{y:,.2f} ${placeInfo().unit}<extra></extra>` },
    { x: [x0 + h0 * t.shifts[best]], y: [running[best]], mode: "markers+text", marker: { size: 11, color: colour, line: { width: 2, color: "#fff" } },
      text: [`peak ${fmt(running[best])}`], textposition: "top center", textfont: { color: colour, size: 12 }, hoverinfo: "skip" },
    { x: [x0 + h0 * t.shifts[idx]], y: [t.moments[idx]], mode: "markers", marker: { size: 8, color: css("--ink") }, hoverinfo: "skip" }], traceLayout());
  const raced = finished ? k + 1 : rolling ? k : k + 1;
  if (replay.raceShown !== raced) {
    replay.raceShown = raced;
    const bars = trials.slice(0, raced);
    Plotly.react("race", [{ type: "bar", orientation: "h", y: bars.map(b => b.label), x: bars.map(b => b.total),
      marker: { color: bars.map(b => b.winner ? css("--ok") : b.kind === "arrangement" ? css("--accent") : css("--kerb")) },
      text: bars.map(b => fmt(b.total, place === "deflection" ? 1 : 0)), textposition: "outside", cliponaxis: false,
      hovertext: bars.map(b => b.kind === "arrangement" ? `vehicles ${fmt(b.peak, 2)} ${placeInfo().unit} (lane reduction ${fmt(b.lane_reduction, 2)}) + lane and footpath load = ${fmt(b.total, 2)} ${placeInfo().unit}` : `${fmt(b.total, 2)} ${placeInfo().unit}`),
      hoverinfo: "text" }], { ...raceLayout(), height: Math.max(260, 60 + 26 * trials.length) });
  }
  $("#trying").replaceChildren(finished
    ? el("span", {}, el("b", { className: "pass", textContent: "Critical position found: " }), `${t.label.replace("Critical: ", "")} — ${fmt(t.total, place === "deflection" ? 2 : 0)} ${placeInfo().unit} (${placeInfo().label.toLowerCase()}) in G${girder}. This is the layout shown under Critical positions.`)
    : el("span", {}, el("b", { textContent: `${k + 1} / ${trials.length} · ` }), `${t.label} — now ${fmt(t.moments[idx], place === "deflection" ? 2 : 0)} ${placeInfo().unit}, best so far ${fmt(Math.max(...running), place === "deflection" ? 2 : 0)} ${placeInfo().unit}`));
}

// ── girder diagrams (like OsdagBridge: one girder stacked, or every girder overlaid) ──
function caseForces(name) {
  const c = result.diagrams.cases[name];
  if (!addDead || name.startsWith("Dead")) return c;
  const d = result.diagrams.cases["Dead · all stages"], out = {};
  for (const g of Object.keys(c)) out[g] = { m: c[g].m.map((v, i) => v + d[g].m[i]), v: c[g].v.map((v, i) => v + d[g].v[i]), d: c[g].d.map((v, i) => v + d[g].d[i]), r: c[g].r + d[g].r };
  return out;
}

function plotControls(redraw, withQty) {
  const cases = el("select", {}, ...Object.keys(result.diagrams.cases).map(n => el("option", { value: n, textContent: n, selected: n === plotCase })));
  cases.onchange = () => { plotCase = cases.value; redraw(); };
  const which = el("select", {}, el("option", { value: "all", textContent: "All girders", selected: plotGirder === "all" }),
    ...girders().map(k => el("option", { value: k, textContent: girderName(k), selected: String(plotGirder) === String(k) })));
  which.onchange = () => { plotGirder = which.value; redraw(); };
  const dead = el("input", { type: "checkbox", checked: addDead }); dead.onchange = () => { addDead = dead.checked; redraw(); };
  const bits = [el("label", {}, "Load case", cases), el("label", {}, "Girder", which)];
  if (withQty) {
    const qty = el("select", {}, ...[["m", "Bending moment"], ["v", "Shear force"], ["d", "Deflection"]].map(([v, t]) => el("option", { value: v, textContent: t, selected: v === plotQty })));
    qty.onchange = () => { plotQty = qty.value; redraw(); };
    bits.push(el("label", {}, "Show", qty));
  }
  bits.push(el("label", { className: "toggle" }, dead, "add the dead load to live cases (unfactored)"));
  return el("div", { className: "controls" }, ...bits);
}

function diagramCard() {
  return el("div", { className: "card pad" }, el("h2", {}, "Bending moment, shear and deflection along the girders"),
    el("p", { className: "sub" }, "Unfactored forces from Setu's model. Live cases are each girder's critical traffic, solved in OpenSees. Sagging moment is drawn below the axis, as on paper. Hover to read values at any point."),
    plotControls(drawDiagrams, false), el("div", { id: "readout", className: "readout" }), el("div", { id: "diagram", className: "plot tall" }));
}

function extremes(xs, ys, yaxis, unit, digits = 0) {
  const hi = ys.indexOf(Math.max(...ys)), lo = ys.indexOf(Math.min(...ys)), big = Math.max(...ys.map(Math.abs));
  return [...new Set([hi, lo])].filter(i => Math.abs(ys[i]) > 0.05 * big).map(i => ({ x: xs[i], y: ys[i], xref: "x", yref: yaxis, text: `${fmt(ys[i], digits)} ${unit}`,
    showarrow: true, arrowhead: 0, ax: 0, ay: i === hi ? 22 : -22, font: { size: 11, color: css("--ink") }, bgcolor: css("--panel"), bordercolor: css("--line") }));
}

function drawDiagrams() {
  const x = result.diagrams.x_m, forces = caseForces(plotCase), L = result.bridge.span_m;
  const rows = { m: ["y", "Bending moment (kN·m)"], v: ["y2", "Shear force (kN)"], d: ["y3", "Deflection (mm)"] };
  const layout = plotLayout({ height: 720, hovermode: "x unified", margin: { l: 70, r: 20, t: 36, b: 44 }, legend: { orientation: "h", y: 1.06, x: 1, xanchor: "right" },
    xaxis: axis({ title: "along the girder from the first bearing, x (m)", anchor: "y3", showspikes: true, spikemode: "across", spikethickness: 1, spikedash: "dot", spikecolor: css("--muted"), range: [0, L] }),
    yaxis: axis({ title: rows.m[1], domain: [0.68, 1], autorange: "reversed" }), yaxis2: axis({ title: rows.v[1], domain: [0.35, 0.63] }),
    yaxis3: axis({ title: rows.d[1], domain: [0, 0.3], autorange: "reversed" }), annotations: [] });
  let traces = [];
  if (plotGirder === "all") {
    girders().forEach(k => Object.entries(rows).forEach(([q, [ya]]) => traces.push({ x, y: forces[k][q], yaxis: ya, name: `G${k}`, legendgroup: `G${k}`, showlegend: q === "m",
      mode: "lines", line: { width: 2, color: PALETTE[k % PALETTE.length] }, hovertemplate: `G${k} %{y:,.1f}<extra></extra>` })));
  } else {
    const f = forces[plotGirder];
    const colours = { m: css("--accent"), v: "#e4572e", d: "#1f8a4c" };
    Object.entries(rows).forEach(([q, [ya, title]]) => {
      traces.push({ x, y: f[q], yaxis: ya, name: title, mode: "lines", fill: "tozeroy", line: { width: 2.2, color: colours[q], shape: q === "v" ? "hv" : "linear" },
        fillcolor: colours[q] + "22", hovertemplate: `%{y:,.${q === "d" ? 2 : 1}f}<extra>${title}</extra>` });
      layout.annotations.push(...extremes(x, f[q], ya, q === "m" ? "kN·m" : q === "v" ? "kN" : "mm", q === "d" ? 1 : 0));
    });
  }
  Plotly.react("diagram", traces, layout, { displaylogo: false, responsive: true });
  const box = $("#diagram");
  box.removeAllListeners?.("plotly_hover");
  box.on("plotly_hover", e => {
    const i = x.indexOf(e.points[0].x);
    if (i < 0) return;
    const show = plotGirder === "all" ? [girder] : [plotGirder];
    $("#readout").textContent = show.map(k => `${girderName(Number(k))} at x = ${fmt(x[i], 2)} m · M = ${fmt(forces[k].m[i])} kN·m · V = ${fmt(forces[k].v[i])} kN · δ = ${fmt(forces[k].d[i], 2)} mm · reaction at the first bearing ${fmt(forces[k].r)} kN`).join("  ");
  });
}

// ── 3D model: deck mesh, girders, braces and force ribbons (like OsdagBridge's 3D view) ──
function modelCard() {
  return el("div", { className: "card pad" }, el("h2", {}, "3D model with force diagrams"),
    el("p", { className: "sub" }, "The deck mesh Setu analyses, the girders and braces under it, and the chosen force drawn as a ribbon on each girder. Drag to turn, scroll to zoom. Cones are the wheel loads of a live case."),
    plotControls(drawModel, true), el("div", { id: "model", className: "plot tall" }));
}

function drawModel() {
  const m = result.mesh, s = m.skew, x = result.diagrams.x_m, forces = caseForces(plotCase), L = result.bridge.span_m, W = result.drawing.width_m;
  const depth = m.depth_m, line = css("--line"), muted = css("--muted");
  const seg = (pts, arr) => { pts.forEach(p => arr.push(p)); arr.push([null, null, null]); };
  const deck = [], steel = [], braces = [];
  m.x_m.forEach(xi => seg([[xi + s * m.z_m[0], m.z_m[0], 0], [xi + s * m.z_m.at(-1), m.z_m.at(-1), 0]], deck));
  m.z_m.forEach(zi => seg([[s * zi, zi, 0], [L + s * zi, zi, 0]], deck));
  m.girder_lines_m.forEach(z => { seg([[s * z, z, -depth], [L + s * z, z, -depth]], steel); m.brace_lines_m.forEach(xi => seg([[xi + s * z, z, 0], [xi + s * z, z, -depth]], steel)); });
  m.brace_lines_m.forEach(xb => m.girder_lines_m.slice(1).forEach((z, k) => {
    const za = m.girder_lines_m[k];
    seg([[xb + s * za, za, -0.15], [xb + s * z, z, -depth]], braces); seg([[xb + s * za, za, -depth], [xb + s * z, z, -0.15]], braces);
  }));
  const lines = (pts, colour, width, name) => ({ type: "scatter3d", mode: "lines", name, x: pts.map(p => p[0]), y: pts.map(p => p[1]), z: pts.map(p => p[2]),
    line: { color: colour, width }, hoverinfo: "skip", showlegend: true });
  const traces = [lines(deck, line, 2, "deck mesh"), lines(steel, css("--accent"), 5, "girders"), lines(braces, muted, 2, "braces")];
  const bearings = m.girder_lines_m.flatMap(z => [[s * z, z], [L + s * z, z]]);
  traces.push({ type: "scatter3d", mode: "markers", x: bearings.map(b => b[0]), y: bearings.map(b => b[1]), z: bearings.map(() => -depth - 0.15),
    marker: { symbol: "diamond", size: 5, color: css("--ink") }, name: "bearings", hoverinfo: "skip" });
  const shown = plotGirder === "all" ? girders() : [Number(plotGirder)];
  const all = shown.flatMap(k => forces[k][plotQty]), big = Math.max(...all.map(Math.abs)) || 1, scale = 0.2 * W / big;
  const unit = { m: "kN·m", v: "kN", d: "mm" }[plotQty], sign = plotQty === "v" ? 1 : 1;
  shown.forEach(k => {
    const z = m.girder_lines_m[k], vals = forces[k][plotQty];
    traces.push({ type: "surface", x: [x.map(xi => xi + s * z), x.map(xi => xi + s * z)], y: [x.map(() => z), x.map(() => z)], z: [x.map(() => 0.02), vals.map(v => 0.02 + sign * v * scale)],
      surfacecolor: [vals, vals], cmin: -big, cmax: big, colorscale: "RdBu", reversescale: true, showscale: k === shown[0], opacity: 0.85,
      colorbar: { title: { text: unit }, thickness: 12, len: 0.6 }, name: `G${k}`, hovertemplate: `G${k}<br>x %{x:.2f} m<br>%{surfacecolor:,.1f} ${unit}<extra></extra>` });
    const hi = vals.reduce((a, v, i) => Math.abs(v) > Math.abs(vals[a]) ? i : a, 0);
    traces.push({ type: "scatter3d", mode: "text", x: [x[hi] + s * z], y: [z], z: [0.02 + vals[hi] * scale + 0.4], text: [`G${k} ${fmt(vals[hi], plotQty === "d" ? 1 : 0)}`],
      textfont: { size: 11, color: css("--ink") }, showlegend: false, hoverinfo: "skip" });
  });
  const live = plotCase.match(/Live · largest moment in G(\d+)/);
  if (live) {
    const w = result.drawing.max_moment[live[1]].wheels, top = Math.max(...w.map(p => p[2]));
    traces.push({ type: "cone", x: w.map(p => p[0]), y: w.map(p => p[1]), z: w.map(() => 0.05), u: w.map(() => 0), v: w.map(() => 0), w: w.map(p => -p[2] / top),
      sizemode: "scaled", sizeref: 2.2, anchor: "tip", colorscale: [[0, "#f2a007"], [1, "#d9480f"]], showscale: false, name: "wheel loads",
      text: w.map(p => `${fmt(p[2], 1)} kN`), hovertemplate: "wheel %{text}<extra></extra>" });
  }
  const ax = t => ({ title: t, backgroundcolor: "rgba(0,0,0,0)", gridcolor: line, zerolinecolor: line, showspikes: false, color: muted });
  Plotly.react("model", traces, plotLayout({ height: 640, margin: { l: 0, r: 0, t: 10, b: 0 }, legend: { orientation: "h", y: 0.02 },
    scene: { xaxis: ax("x along span (m)"), yaxis: ax("z across from the left edge (m)"), zaxis: { ...ax(""), range: [-depth - 0.6, 0.3 * W + 1], showticklabels: false }, aspectmode: "manual", aspectratio: { x: 2.4, y: 1.1, z: 0.55 },
      camera: { eye: { x: -0.7, y: -2.0, z: 1.1 } } } }), { displaylogo: false, responsive: true });
}

// ── plot styling and the table ──────────────────────────────────────────────
function axis(extra = {}) {
  return { gridcolor: css("--line"), zerolinecolor: css("--muted"), linecolor: css("--line"), color: css("--muted"), ...extra, title: extra.title ? { text: extra.title, font: { size: 12 } } : undefined };
}

function plotLayout(extra) {
  return { paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { family: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", size: 12, color: css("--ink") },
    hoverlabel: { bgcolor: css("--panel"), bordercolor: css("--line"), font: { color: css("--ink") } }, ...extra };
}

// ── site loads: what each load group adds, wind, seismic and temperature ─────
const GROUP_COLOURS = { dead: "#4a6d91", surfacing: "#3b3f45", live: "#e8792b", wind: "#00a6a6", seismic: "#c2352b", thermal: "#9b5de5" };

function siteCard() {
  const site = result.site;
  const off = name => el("p", { className: "sub", textContent: `${name} was not included. Tick "include this load" in its section of the form to add it.` });
  const kv = rows => el("table", { className: "kv" }, ...rows.map(([k, v]) => el("tr", {}, el("td", { textContent: k }), el("td", { textContent: v }))));
  const wind = site.wind ? [kv([["Basic wind speed", `${fmt(site.wind.basic_speed_mps, 1)} m/s`], ["Hourly mean speed at deck level", `${fmt(site.wind.speed_at_deck_mps, 1)} m/s`],
    ...Object.entries(site.wind.forces_kn).map(([k, v]) => [`Force, ${k}`, `${fmt(v, 1)} kN`])])] : [off("Wind")];
  const s = site.seismic;
  const seismic = s ? [kv([["Zone / soil", `${s.zone} / ${s.soil}`], ["Importance factor I", fmt(s.importance_factor, 2)], ["Response reduction R", fmt(s.response_reduction, 1)],
    ["Period T", `${fmt(s.period_s, 2)} s`], ["Horizontal coefficient Ah", fmt(s.horizontal_coefficient, 3)], ["Vertical coefficient Av", fmt(s.vertical_coefficient, 3)],
    ["Vertical motion included", s.vertical_included ? "yes (zones IV and V)" : "no"]])] : [off("Seismic")];
  const t = site.temperature;
  const temperature = t ? [kv([["Shade air temperature", `${fmt(t.shade_min_c)} to ${fmt(t.shade_max_c)} °C`], ["Effective bridge temperature", `${fmt(t.effective_range_c[0])} to ${fmt(t.effective_range_c[1])} °C`],
    ["Free bearing movement", `${fmt(1000 * t.free_bearing_movement_m, 1)} mm`], ["Girder force", "none: simply supported with a free bearing"]]),
    el("div", { id: "profile", className: "plot" }), el("div", { className: "scroll" }, stressTable(t))] : [off("Temperature")];
  return el("div", { className: "card pad" },
    el("h2", {}, "What makes up each design value"),
    el("p", { className: "sub" }, "Each load group's factored share of the governing design values, from the IRC:6 Annex B combination that governs. Temperature adds nothing to the girder forces here; its effect is the stress through the depth below."),
    el("div", { id: "shares", className: "plot" }),
    el("div", { className: "site-grid" },
      el("div", {}, el("h2", {}, "Wind (IRC:6 209)"), ...wind),
      el("div", {}, el("h2", {}, "Seismic (IRC:SP:114)"), ...seismic)),
    el("h2", { style: "margin-top:18px" }, "Temperature (IRC:6 215)"), ...temperature);
}

function stressTable(t) {
  const levels = [["slab_top", "slab top"], ["slab_bottom", "slab bottom"], ["steel_top", "steel top"], ["steel_bottom", "steel bottom"]];
  const kinds = Object.keys(Object.values(t.stresses_kpa)[0]);
  const head = el("tr", {}, el("th", { textContent: "Girder" }), ...kinds.flatMap(k => levels.map(([, name]) => el("th", { textContent: `${k === "positive difference" ? "Heating" : "Cooling"}, ${name}` }))));
  const rows = Object.entries(t.stresses_kpa).map(([g, byKind]) => el("tr", {}, el("td", { textContent: g.replace("girder", "Girder") }),
    ...kinds.flatMap(k => levels.map(([key]) => el("td", { textContent: fmt(byKind[k][key] / 1000, 2) })))));
  return el("table", {}, head, ...rows, el("caption", { textContent: "Primary stresses in MPa (tension positive), Fig. 17b / Table 15B profiles on each girder's IRC:22 effective slab width." }));
}

function drawSite() {
  const titles = Object.keys(result.governing), groups = [...new Set(titles.flatMap(k => Object.keys(result.governing[k].shares)))];
  Plotly.react("shares", groups.map(gr => ({ type: "bar", orientation: "h", name: gr, y: titles.map(k => `${k} (${girderName(result.governing[k].girder)})`),
    x: titles.map(k => result.governing[k].shares[gr] || 0), marker: { color: GROUP_COLOURS[gr] || "#8a94a3" },
    hovertemplate: `${gr}: %{x:,.0f}<extra></extra>` })), plotLayout({ barmode: "relative", height: 300, margin: { l: 230, r: 20, t: 10, b: 40 }, legend: { orientation: "h", y: -0.2 },
      xaxis: axis({ title: "kN·m or kN" }), yaxis: axis({ autorange: "reversed" }) }), { displaylogo: false, responsive: true });
  const t = result.site.temperature;
  if (!t) return;
  Plotly.react("profile", Object.entries(t.profiles).map(([kind, pts]) => ({ x: pts.map(p => p[1]), y: pts.map(p => 1000 * p[0]), mode: "lines+markers",
    name: kind === "positive difference" ? "Heating (slab hotter)" : "Cooling (slab colder)", line: { width: 3, color: kind === "positive difference" ? "#e8792b" : "#2b8ad6" } })),
    plotLayout({ height: 320, margin: { l: 70, r: 20, t: 30, b: 45 }, title: { text: "Temperature difference through the depth", font: { size: 13 } },
      xaxis: axis({ title: "temperature difference (°C)", zeroline: true }), yaxis: axis({ title: "depth below the deck top (mm)", autorange: "reversed" }) }),
    { displaylogo: false, responsive: true });
}

function tableCard() {
  const head = ["Girder", "ULS moment kN·m", "SLS rare moment kN·m", "ULS shear kN", "ULS reaction kN", "Traffic deflection mm", "Total deflection mm", "Fatigue range kN·m"];
  const rows = girders().map(k => {
    const df = result.deflections_m[`girder ${k}`];
    return el("tr", {}, el("td", { textContent: girderName(k) }), ...[design(k, M, ULS, "maximum"), design(k, M, RARE, "maximum"), design(k, V, ULS, "minimum"),
      design(k, R, ULS, "maximum")].map(v => el("td", { textContent: v === undefined ? "—" : fmt(v) })),
      el("td", { textContent: fmt(1000 * df.live_m, 1) }), el("td", { textContent: fmt(1000 * df.total_m, 1) }), el("td", { textContent: fmt(result.fatigue_ranges[`girder ${k}`][M].range) }));
  });
  return el("div", { className: "card pad" }, el("h2", {}, "Design values, all girders"),
    el("p", { className: "sub" }, "ULS = strength check with load factors; SLS rare = working loads. Shear is negative by Setu's sign convention."),
    el("div", { className: "scroll" }, el("table", {}, el("tr", {}, ...head.map(t => el("th", { textContent: t }))), ...rows)));
}

// ── start ───────────────────────────────────────────────────────────────────
(async () => {
  schema = await (await fetch("/schema")).json();
  schema.tables.forEach((t, k) => $("#fields").append(tableGroup(t, k < 3)));
  $("#analyse").onclick = analyse;
})();
