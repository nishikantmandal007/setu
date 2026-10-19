const $ = s => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => { const n = Object.assign(document.createElement(tag), attrs); n.append(...kids); return n; };
const svgNS = "http://www.w3.org/2000/svg";
const sv = (tag, attrs = {}, ...kids) => { const n = document.createElementNS(svgNS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); n.append(...kids); return n; };
const fmt = (v, d = 0) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
const M = "maximum composite moment", V = "support shear", R = "bearing reaction";
const ULS = "ultimate, basic", RARE = "serviceability, rare";
const state = { tables: {}, on: {}, strips: [] };
let schema, result, job, girder = 0;
const PROGRESS_PROTOCOL = 10;
let redrawSections = () => {};

// ── inputs, from the same schema as examples/form.html ──────────────────────
function field(f, value, onChange) {
  let input;
  if (f.choices) {
    input = el("select");
    f.choices.forEach(c => input.append(el("option", { value: String(c), textContent: c === null ? "Automatic" : String(c), selected: String(c) === String(value) })));
    input.onchange = () => onChange(input.value === "null" ? null : input.value === "true" ? true : input.value === "false" ? false : isNaN(input.value) ? input.value : Number(input.value));
  } else if (f.type === "text") {
    input = el("input", { type: "text", value, maxLength: 80, placeholder: "Not specified" });
    input.oninput = () => onChange(input.value);
  } else {
    input = el("input", { type: "number", step: f.integer ? 1 : "any", value: value ?? "", required: !f.nullable, placeholder: f.nullable ? "Automatic" : "" });
    if (f.min !== undefined) input.min = f.min;
    if (f.max !== undefined) input.max = f.max;
    input.oninput = () => onChange(input.value === "" ? (f.nullable ? null : "") : Number(input.value));
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
    on.onchange = () => {
      state.on[t.table] = on.checked;
      box.classList.toggle("off", !on.checked);
      grid.querySelectorAll("input,select").forEach(input => input.disabled = !on.checked);
    };
    box.append(el("label", { className: "toggle" }, on, "include this load"));
  }
  t.fields.forEach(f => { state.tables[t.table][f.key] = f.value; grid.append(field(f, f.value, v => {
    state.tables[t.table][f.key] = v;
    if (t.table === "girders" && f.key === "count") redrawSections();
  })); });
  box.append(grid);
  if (t.table === "analysis") {
    const mode = el("select", { "ariaLabel": "Braking force height" },
      el("option", { value: "standard", textContent: "Standard IRC:6 — 1.2 m above road surface" }),
      el("option", { value: "custom", textContent: "Custom height above deck top" }));
    const selectMode = () => {
      const custom = mode.value === "custom";
      grid.hidden = !custom;
      const height = custom ? 1.2 + state.tables.deck.wearing_course_thickness_m : null;
      state.tables.analysis.braking_height_above_deck_m = height;
      grid.querySelector("input").value = height ?? "";
      grid.querySelector("input").disabled = !custom;
      grid.querySelector("input").required = custom;
    };
    mode.onchange = selectMode;
    box.insertBefore(el("label", {}, "Braking force height", mode), grid);
    selectMode();
  }
  if (t.table === "girders.section") {
    const individual = el("input", { type: "checkbox" }), rows = el("div");
    redrawSections = () => {
      const g = state.tables.girders;
      grid.querySelectorAll("input").forEach(input => input.disabled = individual.checked);
      if (!individual.checked) { delete g.sections; rows.replaceChildren(); return; }
      if (!Number.isInteger(g.count) || g.count < 2 || g.count > 12) { rows.textContent = "Choose 2–12 girders first."; return; }
      g.sections = Array.from({ length: g.count }, (_, k) => g.sections?.[k] ?? { ...state.tables[t.table] });
      rows.replaceChildren(...g.sections.map((section, k) => el("div", {}, el("h3", {}, `Girder ${k} (left to right)`),
        el("div", { className: "grid" }, ...t.fields.map(f => field(f, section[f.key], v => section[f.key] = v))))));
    };
    individual.onchange = redrawSections;
    box.append(el("label", { className: "toggle" }, individual, "Use individual sections"), rows);
  }
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
  box.append(rows, add, el("p", { className: "sub", textContent: "Names: footpath, kerb, carriageway, median, crash_barrier, railing" }));
  return box;
}

// what the page sends: every table's values, the strips left to right, and which site loads are ticked
function formData() {
  return { tables: state.tables, strips: state.strips, include: state.on };
}

// ── running ─────────────────────────────────────────────────────────────────
async function analyse() {
  $("#input-error").textContent = "";
  if(schema.progress_protocol!==PROGRESS_PROTOCOL){
    $("#input-error").textContent="The Python server is still running the older visualization backend. Restart your existing web/main.py process, refresh this page, then analyse again.";
    return;
  }
  const invalid = $("#fields").querySelector("input:invalid");
  if (invalid) {
    for (let parent = invalid.parentElement; parent; parent = parent.parentElement) if (parent.tagName === "DETAILS") parent.open = true;
    invalid.reportValidity();
    return;
  }
  const response = await fetch("/analyse", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(formData()) });
  const reply = await response.json();
  if (!response.ok) { $("#input-error").textContent = reply.error; return; }
  job = reply.id;
  $("#analyse").disabled = true;
  showProgress();
  const events = new EventSource(`/progress/${job}`);
  events.onmessage = async e => {
    try {
      const s = JSON.parse(e.data);
      updateProgress(s);
      if (s.error) { events.close(); $("#analyse").disabled = false; }
      if (s.finished) {
        events.close();
        const response=await fetch(`/result/${job}`);
        if(!response.ok)throw Error(`Result download failed (${response.status})`);
        result=await response.json();$("#analyse").disabled=false;showResults();
      }
    } catch(problem) {
      $("#progress-error").textContent=`Progress display error: ${problem.message}`;
      console.error(problem);
      if(events.readyState===EventSource.CLOSED)$("#analyse").disabled=false;
    }
  };
  // the browser retries a dropped stream by itself; a closed one means the server no longer has this analysis
  events.onerror=()=>{
    const lost=events.readyState===EventSource.CLOSED;
    if($("#progress-error"))$("#progress-error").textContent=lost?"The server no longer has this analysis (it was probably restarted). Press Analyse to run it again.":"Connection to the server dropped; reconnecting…";
    if(lost)$("#analyse").disabled=false;
  };
}

const ANALYSIS_STAGES = [
  { step: "Dead load stages", title: "Solve construction dead loads" },
  { step: "Influence surfaces", title: "Map the deck’s response" },
  { step: "Searching traffic", title: "Search traffic & combine actions" },
  { step: "Fatigue truck", title: "Calculate fatigue ranges" },
  { step: "Checking in OpenSees", title: "Re-solve the critical positions" },
  { step: "Preparing the plots", title: "Bring the results together" },
];
let progressStage = null;
let progressPreviewId = null;
let progressGeometry = null;

// Show each completed preview once.
function showProgressPreview(geometry, preview, key) {
  if (key === progressPreviewId) return;
  progressPreviewId = key;
  progressPlot(geometry, preview);
}

const sig = (v, n = 4) => Number(v).toLocaleString("en-IN", { maximumSignificantDigits: n });
// ordinate values span 1e-9 to 1e6; keep labels short in every range
const num = v => { const a = Math.abs(Number(v)); return a && (a < 1e-3 || a >= 1e5) ? Number(v).toExponential(2) : sig(v); };

let planSceneId = 0;
// One fixed frame for every stage, with vehicles clipped to it.
function planScene(b) {
  const W = b.width_m, L = b.span_m, s = b.skew, margin = 0.12 * L + 1.6;
  const x0 = Math.min(0, s * W) - margin, x1 = Math.max(L, L + s * W) + margin;
  const zTop = -3.4, zBot = W + 4.2, h = zBot - zTop;
  const svg = sv("svg", { viewBox: `${x0} ${zTop} ${x1 - x0} ${h}`, role: "img", "aria-label": "Top view of the deck with the vehicles placed by the calculation" });
  SetuVehicles.defs(svg);
  const clip = `plan-clip-${++planSceneId}`;
  svg.append(sv("defs", {}, sv("clipPath", { id: clip }, sv("rect", { x: x0, y: zTop + .5, width: x1 - x0, height: h - 1 }))));
  const at = (x, z) => `${x + s * z},${z}`;
  const band = (xa, xc, za, zc, fill, extra = {}) => sv("polygon", { points: [at(xa, za), at(xc, za), at(xc, zc), at(xa, zc)].join(" "), fill, ...extra });
  const deck = sv("g", { class: "plan-deck" });
  b.strips.forEach(strip => {
    deck.append(band(0, L, strip.from_m, strip.to_m, stripColour(strip.name), {}, sv("title", {}, `${strip.name.replaceAll("_", " ")} · ${fmt(strip.to_m - strip.from_m, 2)} m`)));
    if (strip.name.startsWith("carriageway")) [strip.from_m + .12, strip.to_m - .12].forEach(z => deck.append(sv("line", { x1: s * z, y1: z, x2: L + s * z, y2: z, stroke: "#f4f1ea", "stroke-width": .075, opacity: .8 })));
  });
  [0, L].forEach(x => deck.append(sv("line", { x1: x, y1: -.7, x2: x + s * W, y2: W + .7, stroke: "var(--ink)", "stroke-width": .13, opacity: .9 }, sv("title", {}, `bearing line at x ${fmt(x, 2)} m`))));
  b.girder_lines_m.forEach((z, k) => {
    deck.append(sv("line", { x1: s * z, y1: z, x2: L + s * z, y2: z, stroke: "rgba(255,255,255,.4)","stroke-width": .055, "stroke-dasharray": "0.55 0.35" }, sv("title", {}, `G${k} girder line at z ${fmt(z, 2)} m`)),
      sv("text", { x: s * z - .4, y: z + .22, "font-size": .55, fill: "var(--muted)", "text-anchor": "end" }, `G${k}`));
  });
  const vehicles = sv("g", { "clip-path": `url(#${clip})` });
  svg.append(deck, vehicles);
  return { svg, deck, vehicles, x0, x1, zTop, zBot };
}

// one stat block: the number is the headline, everything else stays quiet
function stageReadout(unit) {
  const value = el("strong", { className: "stage-value" }, "–");
  const label = el("span", { className: "stage-label" });
  const meta = el("span", { className: "stage-meta" });
  return { root: el("div", { className: "stage-readout" }, el("div", { className: "stage-metric" }, label, el("span", { className: "stage-number" }, value, el("span", { className: "stage-unit" }, unit)), meta)), value, label, meta };
}

function spriteFor(v, parent) {
  const g = vehicleSvg(v);
  g.setAttribute("transform", `translate(${v.x_m},${v.z_m})`);
  parent.append(g);
  return g;
}

// transpose a [rows=x][cols=z] matrix so Plotly heatmaps draw x horizontally and z vertically
const transpose = m => (m && m.length ? m[0].map((_, j) => m.map(row => row[j])) : []);

// lane pattern in words: "class_a + class_a | zone_70r" -> "Class A + Class A | 70R"
const lanePatternText = p => String(p).replaceAll("class_a", "Class A").replaceAll("zone_70r", "70R");

// Live traffic search: the worst layout found for this girder and section, drawn on the deck.
function progressSearch(b, preview) {
  const best = preview.ranking[0], scene = planScene(b);
  best.vehicles.forEach(v => spriteFor(v, scene.vehicles));
  return el("div", { className: "stage-plan" },
    scene.svg,
    el("p", { className: "stage-meta" }, `Worst layout: ${lanePatternText(best.lane_pattern)} → ${num(best.response)} ${preview.unit}`),
    ...(b.carriageways.some(c => c.design_lanes === 1) ? [el("p", { className: "stage-caption" },
      "No 70R: carriageway narrower than 5.3 m (IRC:6 Table 6).")] : []));
}

// Static braking forces at the solved vehicle positions.
function brakingScene(b, data) {
  const scene = planScene(b);
  const forces = sv("g", { class: "braking-forces" });
  data.vehicles.forEach(v => spriteFor(v, scene.vehicles));
  scene.vehicles.append(forces);
  const read = stageReadout(data.unit);
  const stage = el("div", { className: "stage-plan" }, scene.svg, read.root);
  const buttons = el("div", { className: "progress-frame-controls" });
  const labels = { forwards: "+x braking", backwards: "−x braking" };
  const draw = name => {
    const d = data.directions[name];
    const total = d.nodes.reduce((sum, nd) => sum + nd.fx_kn, 0);
    const direction = total < 0 ? -1 : 1;
    forces.replaceChildren();
    const axles = data.vehicles.flatMap(v => v.tracked ? [{ v, x: (v.body_m[0] + v.body_m[1]) / 2, share: 1 }]
      : v.axles_m.map((x, k) => ({ v, x, share: v.axle_loads_t[k] })));
    const reach = Math.min(b.span_m * .13, 3.4);
    axles.forEach(({ v, x, share }) => {
      const length = reach * share / Math.max(...axles.map(a => a.share));
      const z = v.z_m, tip = v.x_m + x + direction * length;
      // arrows along the braking force the tyres drag into the deck (the direction of travel)
      forces.append(sv("line", { x1: v.x_m + x, y1: z, x2: tip, y2: z, stroke: "#c8402a", "stroke-width": .16, "stroke-linecap": "round" }),
        sv("polygon", { points: `${tip},${z - .34} ${tip + direction * .3},${z} ${tip},${z + .34}`, fill: "#c8402a" }));
    });
    const fitted = Number.isFinite(d.response) ? d.response : Math.abs(total);
    read.value.textContent = fmt(fitted, 2);
    read.meta.textContent = `${labels[name]}${name === data.selected ? " governs" : ""} · braking force ${fmt(Math.abs(total), 1)} kN${Number.isFinite(data.live) ? ` · traffic alone ${fmt(data.live, 2)} ${data.unit}` : ""}`;
    read.label.textContent = `Girder ${data.girder} with braking`;
    [...buttons.children].forEach(x => x.classList.toggle("on", x.dataset.direction === name));
  };
  Object.keys(data.directions).forEach(name => {
    const button = el("button", { textContent: labels[name], onclick: () => draw(name) });
    button.dataset.direction = name; buttons.append(button);
  });
  draw(data.selected);
  stage.append(buttons);
  return stage;
}

// Truck positions at the two solved fatigue extrema.
// Fatigue: the one 40 t truck at the two positions that give the largest and smallest stress; range = their difference.
function progressFatigue(b, preview) {
  const v = preview.vehicles[0], scene = planScene(b), u = preview.unit;
  [["A", preview.maximum_front_m], ["B", preview.minimum_front_m]].forEach(([tag, x]) => {
    spriteFor({ ...v, x_m: x }, scene.vehicles);
    const mid = Math.min(Math.max(x + (v.body_m[0] + v.body_m[1]) / 2, 0), b.span_m);
    scene.svg.append(sv("text", { x: mid, y: v.z_m - 1.9, "font-size": .85, "font-weight": 700, "text-anchor": "middle", fill: "var(--ink)", "paint-order": "stroke", stroke: "var(--panel)", "stroke-width": .25 }, tag));
  });
  return el("div", { className: "stage-plan" },
    scene.svg,
    el("p", { className: "stage-meta" }, `Stress range = A − B = ${num(preview.largest)} − (${num(preview.smallest)}) = ${num(preview.range)} ${u}`));
}

const DIVERGING_SCALE = [[0, "#2b66b7"], [0.5, "#f4f3ef"], [1, "#c8402a"]];

// Static summaries of completed operations.
function progressPlot(geometry, preview, host = $("#progress-plot")) {
  if (!preview) {
    host.textContent = "Waiting for the first result…";
    return;
  }
  let visual, columns, rows;
  if (preview.kind === "loading" || preview.kind === "dead") {
    columns = ["Stage", "Total applied downward load (kN)", "Status"];
    rows = preview.stages.map(s => [s.name, num(s.total_downward_kn), s.solved ? "solved" : "applied"]);
  } else if (preview.kind === "surface") {
    const s = preview.surface, span = Math.max(Math.abs(s.minimum), Math.abs(s.maximum)) || 1;
    const zg = geometry.girder_lines_m[preview.girder], plot = el("div", { className: "plot" });
    host.replaceChildren(plot, el("p", { className: "stage-caption" }, `min ${num(s.minimum)} · max ${num(s.maximum)} ${s.unit}`));
    Plotly.react(plot, [
      { type: "heatmap", x: s.x_m, y: s.z_m, z: transpose(s.values),
        zmid: 0, zmin: -span, zmax: span, colorscale: DIVERGING_SCALE,
        colorbar: { title: { text: s.unit }, thickness: 12 } },
      { type: "scatter", mode: "lines", x: [s.x_m[0], s.x_m.at(-1)], y: [zg, zg],
        line: { color: css("--accent"), width: 2, dash: "dash" }, name: `G${preview.girder}` },
      { type: "scatter", mode: "markers", x: [preview.station_m], y: [zg],
        marker: { symbol: "x", size: 11, color: css("--bad") }, name: "Checked station" }
    ], plotLayout({ height: 340, margin: { l: 58, r: 20, t: 24, b: 48 },
      legend: { orientation: "h", y: 1.1 },
      xaxis: axis({ title: "Along span, x (m)" }),
      yaxis: axis({ title: "Across deck, z (m)", autorange: "reversed" })
    }), { staticPlot: true, displayModeBar: false, responsive: true });
    return;
  } else if (preview.kind === "braking") {
    visual = brakingScene(geometry, preview);
  } else if (preview.kind === "search") {
    visual = progressSearch(geometry, preview);
  } else if (preview.kind === "fatigue") {
    visual = progressFatigue(geometry, preview);
  } else if (preview.kind === "check") {
    columns = ["Girder", "Response", "Adverse", "Influence-surface prediction", "Direct OpenSees solve", "Difference (%)"];
    rows = preview.rows.map(r => [`G${r.girder}`, r.response, r.adverse, `${num(r.searched)} ${r.unit}`, `${num(r.solved)} ${r.unit}`, r.difference_pct === null ? "—" : num(r.difference_pct)]);
  } else if (preview.kind === "results") {
    visual = el("p", {}, `Assembling results: ${preview.combinations} load combinations`);
  }
  if (columns) visual = el("div", { className: "scroll" }, el("table", {},
    el("thead", {}, el("tr", {}, ...columns.map(c => el("th", {}, c)))),
    el("tbody", {}, ...rows.map(r => el("tr", {}, ...r.map(v => el("td", {}, v)))))));
  host.replaceChildren(visual);
}

function showProgress() {
  progressStage = null;
  progressPreviewId = null;
  progressGeometry = null;
  const R = 32, C = 2 * Math.PI * R;
  const ring = sv("svg", { class: "progress-ring", id: "analysis-meter", viewBox: "0 0 76 76", role: "progressbar",
    "aria-label": "Overall analysis progress", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": "0" },
    sv("circle", { class: "progress-ring-track", cx: 38, cy: 38, r: R }),
    sv("circle", { class: "progress-ring-arc", id: "progress-bar", cx: 38, cy: 38, r: R, "stroke-dasharray": C.toFixed(2), "stroke-dashoffset": C.toFixed(2) }),
    sv("text", { class: "progress-ring-value", id: "progress-percent", x: 38, y: 38, "text-anchor": "middle", "dominant-baseline": "middle" }, "0%"));
  $("#out").replaceChildren(el("section", { className: "card analysis-progress" },
    el("header", { className: "progress-topbar" }, ring,
      el("div", { className: "progress-topblock" },
        el("h2", { id: "progress-title", "aria-live": "polite" }, "Waiting for the solver"),
        el("p", { className: "progress-field-caption", id: "progress-task" }, ""))),
    el("div", { className: "progress-stage" }, el("div", { id: "progress-plot", className: "progress-plot" })),
    el("div", { className: "progress-operation", id: "progress-operation" }),
    el("div", { className: "error", id: "progress-error", role: "alert" })));
  progressPlot(null, null);
}

function updateProgress(s) {
  if(s.progress_protocol!==PROGRESS_PROTOCOL){
    $("#progress-error").textContent="Visualization/backend version mismatch. Restart web/main.py and refresh before starting a new analysis.";
    return;
  }
  if (s.geometry) progressGeometry = s.geometry;
  const now = ANALYSIS_STAGES.findIndex(stage => stage.step === s.step), percent = Math.max(0, Math.min(100, s.percent));
  const arc = $("#progress-bar"), ring = $("#analysis-meter");
  const C = Number(arc.getAttribute("stroke-dasharray")) || 2 * Math.PI * 32;
  arc.style.strokeDashoffset = String(C * (1 - percent / 100));
  ring.setAttribute("aria-valuenow", String(percent));
  $("#progress-percent").textContent = `${percent}%`;
  $(".analysis-progress").classList.toggle("has-error", Boolean(s.error));
  $(".analysis-progress").dataset.finished = String(Boolean(s.finished));
  const stageChanged = progressStage !== now;
  if (stageChanged) {
    progressStage = now;
    $("#progress-title").textContent = now < 0 ? "Waiting for the solver" : `Stage ${now + 1} of ${ANALYSIS_STAGES.length} · ${ANALYSIS_STAGES[now].title}`;
  }
  const preview = s.preview?.stage === s.step ? s.preview : null;
  const layoutKey=preview?.id;
  const previewId = `${now}:${layoutKey ?? 'pending'}:${Boolean(progressGeometry)}`;
  if (progressGeometry) {
    if (preview || stageChanged) showProgressPreview(progressGeometry, preview, previewId);
  } else {
    $("#progress-plot").textContent = "Waiting for the first result…";
  }
  const task=s.activity||{};
  const target = task.target?.replace(", ", " · ");
  const details = [task.girder !== undefined ? `girder ${task.girder}` : null,
    task.response && `${task.response}${task.station_m !== undefined ? ` at ${num(task.station_m)} m` : ""}`].filter(Boolean).join(" · ");
  const subjects = [preview?.stages?.at(-1)?.name || "construction dead loads", "influence surfaces", "traffic layouts", "fatigue stress ranges", "critical positions", "results"];
  $("#progress-task").textContent = target || details || subjects[now] || "";
  $("#progress-error").textContent = s.error || "";
  const countUnit=["load cases","fields","searches","ranges","load cases","report tasks"][now]||"operations";
  if(now===2 && s.traffic_work){
    $("#progress-operation").textContent=Object.entries(s.traffic_work).map(([name,v])=>`${v.count} of ${v.of} ${name}`).join(" · ");
  } else $("#progress-operation").textContent = s.of ? `${s.count} of ${s.of} ${countUnit}` : "";
}

// ── results ─────────────────────────────────────────────────────────────────
const girderName = g => `Girder ${g}${g === 0 || g === result.bridge.girders - 1 ? " (edge)" : ""}`;
const girders = () => [...Array(result.bridge.girders).keys()];
const deadDeflection = g => Object.values(result.deflections_m[`girder ${g}`].dead_m).reduce((a, b) => a + b, 0);
const fatigueStress = g => Object.entries(result.fatigue_stresses_mpa[`girder ${g}`]).reduce((a, b) => b[1].range > a[1].range ? b : a);
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const PALETTE = ["#2458d3", "#e4572e", "#1f8a4c", "#9b5de5", "#f2a007", "#00a6a6", "#c2185b", "#6d4c41", "#546e7a", "#7cb342", "#3949ab", "#d81b60"];
let tab = "positions", plotCase = null, plotGirder = "all", plotQty = "m", addDead = false;

// Design-value explanations are available on the label tooltip.
function row(label, value, unit, chip, explain) {
  return el("div", { className: "row-kv" },
    el("span", { className: "k", textContent: label, title: explain }),
    el("span", { className: "v" }, value, el("small", { textContent: ` ${unit}` })),
    el("span", { className: "chip", textContent: chip }));
}

function movementCheck(label, valueMm, limitMm, g, rule) {
  const within = valueMm <= limitMm;
  return el("div", { className: "movement-check" },
    el("div", { className: "check-heading" }, el("h3", {}, label), el("span", { className: `chip ${within ? "ok" : "bad"}`, textContent: within ? "Within limit" : "Above limit" })),
    el("div", { className: "movement-value" }, fmt(valueMm, 1), el("small", {}, " mm")),
    el("p", { className: "check-limit" }, `Allowed: ${fmt(limitMm, 1)} mm · ${girderName(g)}`),
    el("small", { className: "check-rule", textContent: rule }));
}

function showResults() {
  const g = result.governing, L = result.bridge.span_m;
  const worst = key => girders().reduce((a, b) => (result.deflections_m[`girder ${b}`][key] > result.deflections_m[`girder ${a}`][key] ? b : a), 0);
  const live = worst("live_m"), total = worst("total_m");
  const liveMm = 1000 * result.deflections_m[`girder ${live}`].live_m, totalMm = 1000 * result.deflections_m[`girder ${total}`].total_m;
  const liveLimit = 1000 * L / 800, totalLimit = 1000 * L / 600;
  const fatigue = girders().reduce((a, b) => fatigueStress(b)[1].range > fatigueStress(a)[1].range ? b : a, 0);
  const forces = el("details", { className: "design-summary" }, el("summary", {}, "See design forces & fatigue stress"),
    row("Bending moment", fmt(g["ULS sagging"].value), "kN·m", `Girder ${g["ULS sagging"].girder}`,
      `The turning effect that bends the girder. Largest factored demand, ${fmt(g["ULS sagging"].at_m, 1)} m from the first bearing.`),
    row("Shear at the support", fmt(Math.abs(g["ULS shear"].value)), "kN", `Girder ${g["ULS shear"].girder}`, "The force that tends to shear the girder near its support. Includes design load factors."),
    row("Load on the bearing", fmt(g["ULS reaction"].value), "kN", `Girder ${g["ULS reaction"].girder}`, "The upward force carried by a bearing. Use this factored demand to size the bearing."),
    ...(result.site.seismic ? [row("Earthquake bending moment", fmt(g["ULS seismic"].value), "kN·m", `Girder ${g["ULS seismic"].girder}`, "The bending demand under the earthquake design combination.")] : []),
    row("Fatigue stress range", fmt(fatigueStress(fatigue)[1].range, 2), "MPa", `Girder ${fatigue}`, "The change in steel stress during one 40 t truck passage. Compare it with the resistance of the fatigue detail."));
  const summary = el("div", { className: "card pad result-overview" },
    el("h2", {}, "Deflection"),
    el("div", { className: "movement-checks" },
      movementCheck("From traffic", liveMm, liveLimit, live, "limit L/800"),
      movementCheck("From all loads", totalMm, totalLimit, total, "limit L/600")),
    forces);
  girder = g["ULS sagging"].girder;
  plotCase = `Live · largest moment in G${girder}`;
  const tabs = el("div", { className: "big-tabs", id: "big-tabs" }, ...[["positions", "Traffic positions"], ["replay", "Search replay"], ["diagrams", "Girder diagrams"], ["model", "3D model"], ["site", "Wind, earthquake & temperature"]]
    .map(([key, label]) => { const b = el("button", { textContent: label }); b.dataset.tab = key; b.onclick = () => { tab = key; showTab(); }; return b; }));
  $("#out").replaceChildren(summary, verificationCard(), tabs, el("div", { id: "panel" }), tableCard());
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
function deckSvg() {
  const d = result.drawing, W = d.width_m, L = d.span_m, s = d.skew, margin = 0.12 * L + 1.6;
  const x0 = Math.min(0, s * W) - margin, x1 = Math.max(L, L + s * W) + margin;
  const viewBox = `${x0} -2.2 ${x1 - x0} ${W + 4.2}`, svg = sv("svg", { viewBox, role: "img", "aria-label": "top view of the deck" });
  svg.append(sv("defs", {},
    sv("clipPath", { id: "view" }, sv("rect", { x: x0, y: -0.5, width: x1 - x0, height: W + 1 })),
));
  SetuVehicles.defs(svg);
  const at = (x, z) => `${x + s * z},${z}`;
  const band = (z0, z1, fill, extra = {}) => sv("polygon", { points: [at(0, z0), at(L, z0), at(L, z1), at(0, z1)].join(" "), fill, ...extra });
  d.strips.forEach(strip => {
    svg.append(band(strip.from_m, strip.to_m, stripColour(strip.name), {}, sv("title", {}, `${strip.name.replaceAll("_", " ")}: ${fmt(strip.to_m - strip.from_m, 2)} m`)));
    if (strip.name.startsWith("carriageway"))
      [strip.from_m + 0.12, strip.to_m - 0.12].forEach(z => svg.append(sv("line", { x1: s * z, y1: z, x2: L + s * z, y2: z, stroke: "#f4f1ea", "stroke-width": 0.08, opacity: 0.8 })));
  });
  [0, L].forEach(x => svg.append(sv("line", { x1: x, y1: -0.3, x2: x + s * W, y2: W + 0.3, stroke: "var(--ink)", "stroke-width": 0.1 })));
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
    el("div", { className: "card-head" },
      el("div", { style: "min-width:0" }, el("h2", { id: "deck-title" }), el("p", { className: "sub", id: "deck-caption", style: "margin-top:3px" })),
      el("div", { className: "card-head-tabs" }, el("div", { id: "place-tabs" }), el("div", { id: "girder-tabs" }))),
    el("div", { id: "deck" }),
    el("details", {}, el("summary", {}, "See vehicle positions & impact factors"), el("div", { id: "vehicle-positions", className: "scroll" })),
    el("div", { className: "legend" },
      el("span", {}, el("i", { style: "background:var(--asphalt)" }), "carriageway"), el("span", {}, el("i", { style: "background:var(--footpath)" }), "footpath"),
      el("span", {}, el("i", { style: "background:var(--kerb)" }), "kerb / median"),
      el("span", {}, el("i", { style: "background:var(--udl);outline:1px solid var(--accent)" }), "lane load"), el("span", {}, el("i", { style: "background:var(--foot);outline:1px solid var(--ok)" }), "footpath load"),
      el("span", {}, el("i", { style: "background:var(--bad)" }), "section checked")),
    el("div", { className: "row" },
      el("button", { className: "primary", textContent: "Export critical loads CSV (this girder, maximum moment)", onclick: () => location.href = `/critical-loads/${job}.csv?girder=${girder}` }),
      el("button", { textContent: "Export critical loads CSV (all girders, maximum moment)", onclick: () => location.href = `/critical-loads/${job}.csv?girder=all` })));
}

function sectionMarker(svg, at_m) {
  const d = result.drawing, zg = d.girder_lines_m[girder], x = at_m + d.skew * zg;
  const atBearing = at_m < 0.5;
  svg.append(sv("line", { x1: x, y1: zg - 1.1, x2: x, y2: zg + 1.1, stroke: "var(--bad)", "stroke-width": 0.14 }),
    sv("text", { x: atBearing ? x + 0.4 : x, y: atBearing ? d.width_m + 1.1 : -1.2, "font-size": 0.6, fill: "var(--bad)", "text-anchor": atBearing ? "start" : "middle", "font-weight": 700 },
      `x = ${fmt(at_m, 2)} m`));
}

function drawDeck() {
  $("#girder-tabs").replaceChildren(girderTabs(drawDeck));
  $("#place-tabs").replaceChildren(placeTabs(drawDeck));
  const c = result.drawing.places[place][girder], p = placeInfo();
  $("#deck-title").textContent = "Traffic positions";
  const { svg, layer, loads } = deckSvg();
  c.patches.forEach(p => loads.append(sv("polygon", { points: p.corners.map(([x, z]) => `${x},${z}`).join(" "),
    fill: p.kind === "footway" ? "var(--foot)" : "var(--udl)" }, sv("title", {}, `${p.kind}: ${fmt(p.kpa, 2)} kN/m²`))));
  c.vehicles.forEach(v => layer.append(placeVehicle(v)));
  sectionMarker(svg, c.at_m);
  $("#deck").replaceChildren(svg);
  $("#deck-caption").textContent = `G${girder} · ${fmt(c.value, place === "deflection" ? 2 : 0)} ${p.unit} · lane reduction ${fmt(c.lane_reduction, 2)}${place === "deflection" ? " · footway excluded (IRC:22)" : ""}`;
  $("#vehicle-positions").replaceChildren(el("table", {},
    el("tr", {}, ...["Vehicle", "Carriageway", "Centre z (m)", "From left kerb (m)", "Front x (m)", "Impact multiplier"].map(t => el("th", { textContent: t }))),
    ...c.vehicles.map(v => {
      const strip = result.drawing.strips.find(s => s.name.startsWith("carriageway") && v.z_m >= s.from_m && v.z_m <= s.to_m);
      return el("tr", {}, ...[`${v.name} ${v.heading > 0 ? "→" : "←"}`, strip?.name || "—", fmt(v.z_m, 3), strip ? fmt(v.z_m - strip.from_m, 3) : "—",
        fmt(v.x_m, 3), `${fmt(v.impact_factor, 4)} (i = ${fmt(v.impact_factor - 1, 4)})`].map(t => el("td", { textContent: t })));
    })));
}

// ── search replay: every vehicle rolled along every lane, then Setu's best arrangements ──
const HOLD = 18;
let replay = null;

function replayCard() {
  return el("div", { className: "card pad" },
    el("div", { className: "card-head" },
      el("div", { style: "min-width:0" },
        el("h2", {}, "Traffic rolled across the span"),
        el("p", { className: "sub", style: "margin-top:3px" }, "Vehicles alone, then setu's best lane arrangements, rolled along the span.")),
      el("div", { className: "card-head-tabs" }, el("div", { id: "place-tabs" }), el("div", { id: "girder-tabs" }))),
    el("div",{className:"progress-frame-controls"},el("button",{id:"replay-traffic-choice",textContent:"Traffic passes",onclick:()=>showReplayBraking(false)}),el("button",{id:"replay-braking-choice",textContent:"Braking checks",onclick:()=>showReplayBraking(true)})),
    el("div", { id: "replay-deck", className: "deck" }),el("section",{id:"replay-braking",hidden:true}),
    el("div", { className: "player" },
      el("button", { id: "play", className: "primary", textContent: "❚❚ Pause" }),
      el("input", { id: "scrub", type: "range", min: 0, value: 0 }),
      el("select", { id: "speed" }, ...[["0.5", "0.5×"], ["1", "1×"], ["2", "2×"], ["4", "4×"]].map(([v, t]) => el("option", { value: v, textContent: t, selected: v === "1" })))),
    el("div", { className: "now-trying", id: "trying" }),
    el("div", { className: "charts2",id:"replay-charts" }, el("div", { id: "trace", className: "plot" }), el("div", { id: "race", className: "plot" })));
}

function startReplay() {
  $("#girder-tabs").replaceChildren(girderTabs(() => { stopReplay(); showTab(); }));
  $("#place-tabs").replaceChildren(placeTabs(() => { stopReplay(); showTab(); }));
  const r = result.replay[place][girder], trials = r.trials;
  const brakingHost=$("#replay-braking");
  $("#replay-braking-choice").disabled=!r.braking;
  if(r.braking){
    brakingHost.replaceChildren(el("h3",{},"Braking at this critical traffic layout"),
      brakingScene(result.geometry,r.braking));
  } else brakingHost.replaceChildren();
  const starts = [];
  let total = 0;
  trials.forEach(t => { starts.push(total); total += t.shifts.length + HOLD; });
  const { svg, layer } = deckSvg();
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
  $("#replay-traffic-choice").classList.add("on");
}

function showReplayBraking(enabled) {
  if(!replay)return;
  replay.playing=false;$("#play").textContent="▶ Play";
  $("#replay-deck").hidden=enabled;$("#replay-braking").hidden=!enabled;
  $("#replay-charts").hidden=enabled;$("#trying").hidden=enabled;$("#scrub").closest(".player").hidden=enabled;
  $("#replay-traffic-choice").classList.toggle("on",!enabled);$("#replay-braking-choice").classList.toggle("on",enabled);
}

function stopReplay() { if (replay) { cancelAnimationFrame(replay.timer); replay = null; } }

function tickReplay(now) {
  if (!replay) return;
  const speed = Number($("#speed")?.value || 1);
  if (replay.playing) {
    replay.frame = Math.min(replay.total - 1, replay.frame + (now - replay.last) * 0.045 * speed);
    if (replay.frame >= replay.total - 1) { replay.playing = false; $("#play").textContent = "↺ Replay"; if(replay.r.braking)showReplayBraking(true); }
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
  const blend=rolling ? replay.frame-f : 0,shift=t.shifts[idx]+blend*((t.shifts[Math.min(idx+1,t.shifts.length-1)]??t.shifts[idx])-t.shifts[idx]);
  [...replay.layer.children].forEach((g, n) => g.setAttribute("transform", `translate(${t.vehicles[n].x_m + t.vehicles[n].heading * shift},${t.vehicles[n].z_m})`));
  if(replay.lastPlotFrame===f)return;
  replay.lastPlotFrame=f;
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
    ? el("span", {}, el("b", { className: "pass", textContent: "Critical position found: " }), `${t.label.replace("Critical: ", "")} — ${fmt(t.total, place === "deflection" ? 2 : 0)} ${placeInfo().unit} (${placeInfo().label.toLowerCase()}) in G${girder}.`)
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
    $("#readout").textContent = show.map(k => `${girderName(Number(k))} at x = ${fmt(x[i], 2)} m · M = ${fmt(forces[k].m[i])} kN·m · V = ${fmt(forces[k].v[i])} kN · δ = ${fmt(forces[k].d[i], 2)} mm · bearing reactions: first ${fmt(forces[k].r)} kN, far ${fmt(forces[k].r_end)} kN`).join("  ");
  });
}

// ── 3D model: deck mesh, girders, braces and force ribbons (like OsdagBridge's 3D view) ──
function modelCard() {
  return el("div", { className: "card pad" }, el("h2", {}, "3D model with force diagrams"),
    plotControls(drawModel, true), el("div", { id: "model", className: "plot tall" }));
}

function drawModel() {
  const m = result.mesh, s = m.skew, x = result.diagrams.x_m, forces = caseForces(plotCase), L = result.bridge.span_m, W = result.drawing.width_m;
  const depth = m.depth_m, depths = m.girder_depths_m, top = -m.slab_m / 2, line = css("--line"), muted = css("--muted");
  const seg = (pts, arr) => { pts.forEach(p => arr.push(p)); arr.push([null, null, null]); };
  const deck = [], steel = [], braces = [];
  m.x_m.forEach(xi => seg([[xi + s * m.z_m[0], m.z_m[0], 0], [xi + s * m.z_m.at(-1), m.z_m.at(-1), 0]], deck));
  m.z_m.forEach(zi => seg([[s * zi, zi, 0], [L + s * zi, zi, 0]], deck));
  m.girder_lines_m.forEach((z, k) => { seg([[s * z, z, top - depths[k]], [L + s * z, z, top - depths[k]]], steel); m.brace_lines_m.forEach(xi => seg([[xi + s * z, z, top], [xi + s * z, z, top - depths[k]]], steel)); });
  m.brace_lines_m.forEach(xb => m.girder_lines_m.slice(1).forEach((z, k) => {
    const za = m.girder_lines_m[k];
    const a = [xb + s * za, za, top], b = [xb + s * z, z, top];
    const ab = [a[0], za, top - depths[k]], bb = [b[0], z, top - depths[k + 1]];
    if (m.bracing.startsWith("K")) {
      const mid = ab.map((v, i) => (v + bb[i]) / 2);
      [a, b, ab, bb].forEach(p => seg([p, mid], braces));
    } else { seg([a, bb], braces); seg([ab, b], braces); }
    if (m.bracing.includes("T")) seg([a, b], braces);
    if (m.bracing.includes("B")) seg([ab, bb], braces);
  }));
  const lines = (pts, colour, width, name) => ({ type: "scatter3d", mode: "lines", name, x: pts.map(p => p[0]), y: pts.map(p => p[1]), z: pts.map(p => p[2]),
    line: { color: colour, width }, hoverinfo: "skip", showlegend: true });
  const traces = [lines(deck, line, 2, "deck mesh"), lines(steel, css("--accent"), 5, "girders"), lines(braces, muted, 2, "braces")];
  const bearings = m.girder_lines_m.flatMap((z, k) => [[s * z, z, top - depths[k] - 0.15], [L + s * z, z, top - depths[k] - 0.15]]);
  traces.push({ type: "scatter3d", mode: "markers", x: bearings.map(b => b[0]), y: bearings.map(b => b[1]), z: bearings.map(b => b[2]),
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
  const kv = rows => el("table", { className: "kv" }, ...rows.map(([k, v]) => el("tr", {}, el("td", { textContent: k }), el("td", { textContent: v }))));
  const wind = site.wind ? [kv([["Basic wind speed", `${fmt(site.wind.basic_speed_mps, 1)} m/s`], ["Hourly mean speed at deck level", `${fmt(site.wind.speed_at_deck_mps, 1)} m/s`],
    ...Object.entries(site.wind.forces_kn).map(([k, v]) => [`Force, ${k}`, `${fmt(v, 1)} kN`])])] : [];
  const s = site.seismic;
  const seismic = s ? [kv([["Zone / soil", `${s.zone} / ${s.soil}`], ["Importance factor I", fmt(s.importance_factor, 2)], ["Response reduction R", fmt(s.response_reduction, 1)],
    ["Period T", `${fmt(s.period_s, 2)} s`], ["Horizontal coefficient Ah", fmt(s.horizontal_coefficient, 3)], ["Vertical coefficient Av", fmt(s.vertical_coefficient, 3)],
    ["Vertical motion included", s.vertical_included ? "yes" : "no"]])] : [];
  const t = site.temperature;
  const temperature = t ? [kv([["Shade air temperature", `${fmt(t.shade_min_c)} to ${fmt(t.shade_max_c)} °C`], ["Effective bridge temperature", `${fmt(t.effective_range_c[0])} to ${fmt(t.effective_range_c[1])} °C`],
    ["Free bearing movement", `${fmt(1000 * t.free_bearing_movement_m, 1)} mm`], ["Girder force", "none: simply supported with a free bearing"]]),
    el("div", { id: "profile", className: "plot" }), el("div", { className: "scroll" }, stressTable(t))] : [];
  return el("div", { className: "card pad" },
    el("h2", {}, "What makes up each design value"),
    el("div", { id: "shares", className: "plot" }),
    el("div", { className: "site-grid" },
      el("div", {}, el("h2", {}, "Wind (IRC:6 209)"), ...wind),
      el("div", {}, el("h2", {}, "Seismic (IRC:SP:114)"), ...seismic)),
    el("h2", { style: "margin-top:18px" }, "Temperature (IRC:6 215)"), ...temperature);
}

function stressTable(t) {
  const levels = [["slab_top", "slab top"], ["slab_bottom", "slab bottom"], ["steel_top", "steel top"], ["steel_bottom", "steel bottom"]];
  const kinds = Object.keys(Object.values(t.stresses_kpa)[0]);
  const head = el("tr", {}, el("th", { textContent: "Girder" }), ...kinds.flatMap(k => levels.map(([, name]) => el("th", { textContent: `${k === "positive difference" ? "Heating" : "Cooling"}, ${name} (MPa, +tension)` }))));
  const rows = Object.entries(t.stresses_kpa).map(([g, byKind]) => el("tr", {}, el("td", { textContent: g.replace("girder", "Girder") }),
    ...kinds.flatMap(k => levels.map(([key]) => el("td", { textContent: fmt(byKind[k][key] / 1000, 2) })))));
  return el("table", {}, head, ...rows);
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

function verificationCard() {
  const b = result.bridge;
  const table = rows => el("table", { className: "kv" }, ...rows.map(([label, value]) => el("tr", {}, el("td", { textContent: label }), el("td", { textContent: value }))));
  const materials = [["Girder steel", b.grades.girder], ["Cross bracing steel", b.grades["cross bracing"]], ["End diaphragm steel", b.grades["end diaphragm"]], ["Deck concrete", b.grades.concrete]];
  const stageNames = { "steel self weight": "Steel girders & bracing", "wet slab": "Wet concrete slab", "superimposed": "Footpaths, kerbs & other fixed loads", "surfacing": "Road surfacing" };
  const selected = el("select", {}, ...girders().map(g => el("option", { value: g, textContent: girderName(g), selected: g === girder })));
  const stages = el("div");
  const drawStages = () => {
    const g = Number(selected.value), dead = result.deflections_m[`girder ${g}`].dead_m;
    stages.replaceChildren(table([...Object.entries(dead).map(([stage, value]) => [stageNames[stage] || stage, `${fmt(1000 * value, 2)} mm`]), ["Total from bridge weight", `${fmt(1000 * deadDeflection(g), 2)} mm`]]));
  };
  selected.onchange = drawStages;
  drawStages();
  return el("details", { className: "card pad verification" },
    el("summary", {}, "Check bridge inputs"),
    el("div", { className: "verification-section" }, el("h3", {}, "Bridge geometry"),
      table([["Total width, edge to edge", `${fmt(b.deck_width_m, 3)} m`], ["Gap between girder centres", `${fmt(b.girder_spacing_m, 3)} m`]])),
    el("details", {}, el("summary", {}, "Material grades & stiffness"),
      table(materials.map(([label, grade]) => [label, grade || "Grade not entered"])),
      table([["Steel stiffness (E), all members", `${fmt(b.steel_modulus_mpa)} MPa`], ["Concrete stiffness (Ecm)", `${fmt(b.concrete_modulus_mpa)} MPa`]])),
    el("details", {}, el("summary", {}, "Slab width acting with each girder"),
      table(girders().map(g => [girderName(g), `${fmt(b.effective_slab_widths_m[`girder ${g}`], 3)} m`]))),
    el("details", {}, el("summary", {}, "Movement from bridge weight, stage by stage"),
      el("div", { className: "controls" }, el("label", {}, "Choose a girder", selected)), stages));
}

function tableCard() {
  const choice = el("select", {}, el("option", { value: "", textContent: "Worst combination for each check" }),
    ...Object.keys(result.combinations["girder 0"][M]).map(name => el("option", { value: name, textContent: name })));
  const body = el("div"), trace = el("details", {}, el("summary", {}, "Combination and load shares"));
  const draw = () => {
    const combo = choice.value;
    const columns = combo ? [["Moment kN·m", M, ULS, "maximum"], ["Shear kN (− = Setu sign)", V, ULS, "minimum"], ["Reaction kN", R, ULS, "maximum"]]
      : [["ULS moment kN·m", M, ULS, "maximum"], ["SLS rare moment kN·m", M, RARE, "maximum"], ["ULS shear kN (− = Setu sign)", V, ULS, "minimum"], ["ULS reaction kN", R, ULS, "maximum"]];
    const valueAt = (g, [, response, limit, adverse]) => combo ? result.combinations[`girder ${g}`][response][combo][adverse] : result.design_values[`girder ${g}`][response][limit][adverse];
    const head = ["Girder", ...columns.map(c => c[0]), "Dead deflection mm", "Traffic deflection mm", "Total deflection mm", "Fatigue stress range MPa"];
    body.replaceChildren(el("div", { className: "scroll" }, el("table", {}, el("tr", {}, ...head.map(t => el("th", { textContent: t }))),
      ...girders().map(g => {
        const df = result.deflections_m[`girder ${g}`];
        return el("tr", {}, el("td", { textContent: girderName(g) }), ...columns.map(c => el("td", { textContent: fmt(valueAt(g, c).value) })),
          ...[1000 * deadDeflection(g), 1000 * df.live_m, 1000 * df.total_m, fatigueStress(g)[1].range].map(v => el("td", { textContent: fmt(v, 2) })));
      }))));
    trace.replaceChildren(el("summary", {}, "Combination and load shares"), el("div", { className: "scroll" }, el("table", {},
      el("tr", {}, ...["Girder", "Response", "Combination", "Station x (m)", "Factored load shares (kN·m or kN)"].map(t => el("th", { textContent: t }))),
      ...girders().flatMap(g => columns.map(c => {
        const v = valueAt(g, c);
        return el("tr", {}, ...[girderName(g), c[0], v.combination, fmt(v.at_m, 3), Object.entries(v.shares).map(([group, share]) => `${group}: ${fmt(share, 2)}`).join("; ")].map(t => el("td", { textContent: t })));
      })))));
  };
  choice.onchange = draw;
  draw();
  const fatigue = el("details", {}, el("summary", {}, "Fatigue stresses and truck positions"), el("div", { className: "scroll" }, el("table", {},
    el("tr", {}, ...["Girder", "Steel face", "Range MPa", "Max (MPa, +tension)", "Min (MPa, +tension)", "Station (m)", "Truck z (m)", "Front x at max (m)", "Front x at min (m)", "Impact multiplier"].map(t => el("th", { textContent: t }))),
    ...girders().flatMap(g => Object.entries(result.fatigue_stresses_mpa[`girder ${g}`]).map(([face, f]) => el("tr", {},
      ...[girderName(g), face, fmt(f.range, 2), fmt(f.largest, 2), fmt(f.smallest, 2), fmt(f.at_m, 3), fmt(f.z_centre_m, 3), fmt(f.x_front_at_largest_m, 3), fmt(f.x_front_at_smallest_m, 3), fmt(f.impact_factor, 4)].map(t => el("td", { textContent: t }))))))));
  return el("details", { className: "card pad detailed-results" }, el("summary", {}, "Detailed results by girder"),
    el("div", { className: "controls" }, el("label", {}, "Load combination", choice)), body, trace, fatigue);
}

// ── start ───────────────────────────────────────────────────────────────────
(async () => {
  schema = await (await fetch("/schema")).json();
  schema.tables.forEach((t, k) => $("#fields").append(tableGroup(t, k < 3)));
  $("#analyse").onclick = analyse;
})();
