// Animations for the Setu docs. Each <div class="anim" data-anim="name"> becomes one.
// The bridges here are small illustrations of each idea; the vehicles are the real IRC ones (vehicles.js).
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const svg = (tag, attrs = {}, ...kids) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    n.append(...kids);
    return n;
  };
  const html = (tag, attrs = {}, ...kids) => { const n = Object.assign(document.createElement(tag), attrs); n.append(...kids); return n; };
  const lerp = (a, b, t) => a + (b - a) * t;
  const clamp = (v, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
  const ease = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
  const fmt = (v, d = 0) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
  const NAVY = "#1b3160", SAFFRON = "#f28c28", RED = "#c2352b", GREEN = "#1f8a4c", STEEL = "#4a67a3", GREY = "#8a94a3";
  const V = () => window.SetuVehicles;

  // pale → saffron → deep red, for influence values 0..1
  function heat(v) {
    v = clamp(v);
    const stops = [[255, 247, 236], [248, 190, 120], [242, 140, 40], [194, 53, 43]];
    const x = v * (stops.length - 1), i = Math.min(stops.length - 2, Math.floor(x)), f = x - i;
    return `rgb(${stops[i].map((a, k) => Math.round(lerp(a, stops[i + 1][k], f))).join(",")})`;
  }
  const polyline = (pts, fx, fy) => pts.length ? "M" + pts.map(([x, y]) => `${fx(x).toFixed(1)},${fy(y).toFixed(1)}`).join(" L") : "";
  const label = (x, y, text, attrs = {}) => svg("text", { x, y, "font-size": 12, fill: "currentColor", ...attrs }, text);

  // a player: timeline t in seconds with play/pause, a scrubber, and a pause while off screen
  function player(root, length, draw, { loop = true, hold = 2.5 } = {}) {
    const bar = html("div", { className: "anim-bar" });
    const button = html("button", { className: "anim-button", type: "button", textContent: "❚❚ Pause" });
    button.setAttribute("aria-label", "play or pause the animation");
    const scrub = html("input", { type: "range", min: 0, max: 1000, value: 0, className: "anim-scrub" });
    scrub.setAttribute("aria-label", "animation position");
    bar.append(button, scrub);
    root.append(bar);
    // readers who ask their system for less motion get the finished picture, paused, and can still play it
    const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    let t = calm ? length : 0, playing = !calm, last = null, visible = true;
    const total = length + hold;
    if (calm) button.textContent = "▶ Play";
    new IntersectionObserver(entries => { visible = entries[0].isIntersecting; }).observe(root);
    button.onclick = () => {
      if (!playing && t >= total && !loop) t = 0;
      playing = !playing;
      button.textContent = playing ? "❚❚ Pause" : "▶ Play";
    };
    scrub.oninput = () => { t = (scrub.value / 1000) * length; draw(Math.min(t, length)); };
    const frame = now => {
      if (!root.isConnected) return;
      if (last !== null && playing && visible) {
        t += (now - last) / 1000;
        if (t >= total) {
          if (loop) t = 0;
          else { t = total; playing = false; button.textContent = "↺ Replay"; }
        }
        draw(Math.min(t, length));
        scrub.value = Math.round((Math.min(t, length) / length) * 1000);
      }
      last = now;
      requestAnimationFrame(frame);
    };
    draw(t);
    scrub.value = Math.round((t / length) * 1000);
    requestAnimationFrame(frame);
    return { restart() { t = calm ? length : 0; playing = !calm; button.textContent = calm ? "▶ Play" : "❚❚ Pause"; scrub.value = Math.round((t / length) * 1000); draw(t); } };
  }

  // ── a small illustrative deck for the plan views ─────────────────────────────
  const SPAN = 24, WIDTH = 8, GIRDERS = [1, 3, 5, 7], TARGET = 1;
  function influence(x, z) {
    if (x < 0 || x > SPAN || z < 0 || z > WIDTH) return 0;
    const along = x <= SPAN / 2 ? x / 2 : (SPAN - x) / 2;
    return along * (0.12 + 0.88 * Math.exp(-Math.pow((z - GIRDERS[TARGET]) / 2.1, 2)));
  }
  const PEAK = influence(SPAN / 2, GIRDERS[TARGET]);

  function deckPlan(group, x0, y0, cellW, cellH, nx, nz) {
    const cells = [];
    group.append(svg("rect", { x: x0 - 2, y: y0 - 2, width: nx * cellW + 4, height: nz * cellH + 4, rx: 4, fill: "none", stroke: "currentColor", "stroke-opacity": 0.35 }));
    for (let j = 0; j < nz; j++) for (let i = 0; i < nx; i++) {
      const r = svg("rect", { x: x0 + i * cellW, y: y0 + j * cellH, width: cellW - 1, height: cellH - 1, fill: "currentColor", "fill-opacity": 0.06 });
      group.append(r);
      cells.push(r);
    }
    GIRDERS.forEach((z, k) => {
      const y = y0 + (z / WIDTH) * nz * cellH;
      group.append(svg("line", { x1: x0, y1: y, x2: x0 + nx * cellW, y2: y, stroke: "currentColor", "stroke-opacity": k === TARGET ? 0.95 : 0.3, "stroke-width": k === TARGET ? 2.5 : 1, "stroke-dasharray": "6 4" }));
      group.append(label(x0 - 8, y + 4, `G${k + 1}`, { "text-anchor": "end", "font-size": 11, "fill-opacity": k === TARGET ? 1 : 0.55, "font-weight": k === TARGET ? 700 : 400 }));
    });
    [x0, x0 + nx * cellW].forEach(x => group.append(svg("path", { d: `M${x - 7},${y0 + nz * cellH + 14} l7,-10 l7,10 z`, fill: "currentColor", "fill-opacity": 0.6 })));
    return cells;
  }

  // ── 1. what an influence surface is ────────────────────────────────────────
  function influenceAnim(root) {
    const NX = 24, NZ = 8, CW = 22, CH = 20, X0 = 44, Y0 = 34;
    const s = svg("svg", { viewBox: "0 0 660 340", class: "anim-svg" });
    s.append(label(X0, 20, "Deck from above — a 1 kN load visits every point", { "font-size": 13, "font-weight": 600 }));
    const cells = deckPlan(s, X0, Y0, CW, CH, NX, NZ);
    const load = svg("g", {}, svg("circle", { r: 8, fill: NAVY, stroke: "#fff", "stroke-width": 2 }), label(0, -12, "1 kN", { "text-anchor": "middle", "font-size": 11, "font-weight": 700 }));
    s.append(load);
    const BX0 = X0, BX1 = X0 + NX * CW, BY = 262;
    s.append(label(BX0, 232, "Girder G2 from the side — its bending moment for this load position", { "font-size": 13, "font-weight": 600 }));
    s.append(svg("line", { x1: BX0, y1: BY, x2: BX1, y2: BY, stroke: "currentColor", "stroke-width": 4 }));
    [BX0, BX1].forEach(x => s.append(svg("path", { d: `M${x - 7},${BY + 12} l7,-10 l7,10 z`, fill: "currentColor", "fill-opacity": 0.6 })));
    const bmd = svg("path", { fill: SAFFRON, "fill-opacity": 0.35, stroke: SAFFRON, "stroke-width": 2 });
    const mid = svg("line", { x1: (BX0 + BX1) / 2, y1: BY - 4, x2: (BX0 + BX1) / 2, y2: BY + 70, stroke: RED, "stroke-width": 1.5, "stroke-dasharray": "3 3" });
    const readout = label((BX0 + BX1) / 2 + 8, BY + 66, "", { fill: RED, "font-weight": 700 });
    s.append(bmd, mid, readout);
    const legend = svg("g", { transform: `translate(${X0 + NX * CW + 20}, ${Y0})` });
    for (let k = 0; k <= 10; k++) legend.append(svg("rect", { x: 0, y: (10 - k) * 14, width: 14, height: 14, fill: heat(k / 10) }));
    legend.append(label(20, 10, "big", { "font-size": 11 }), label(20, 150, "small", { "font-size": 11 }));
    s.append(legend);
    const caption = html("p", { className: "anim-caption" });
    root.append(s, caption);
    const PER = 0.035, n = NX * NZ;
    player(root, n * PER + 0.5, t => {
      const k = Math.min(n - 1, Math.floor(t / PER));
      cells.forEach((c, m) => {
        const i = m % NX, j = Math.floor(m / NX), v = influence((i + 0.5) * SPAN / NX, (j + 0.5) * WIDTH / NZ) / PEAK;
        if (m <= k) { c.setAttribute("fill", heat(v)); c.setAttribute("fill-opacity", 1); } else { c.setAttribute("fill", "currentColor"); c.setAttribute("fill-opacity", 0.06); }
      });
      const i = k % NX, j = Math.floor(k / NX), x = (i + 0.5) * SPAN / NX, z = (j + 0.5) * WIDTH / NZ;
      load.setAttribute("transform", `translate(${X0 + (i + 0.5) * CW},${Y0 + (j + 0.5) * CH})`);
      const share = influence(x, z) / influence(x, GIRDERS[TARGET]) || 0, a = x / SPAN, peakM = share * a * (1 - a) * SPAN;
      bmd.setAttribute("d", `M${BX0},${BY} L${BX0 + a * (BX1 - BX0)},${BY + 60 * peakM / (SPAN / 4)} L${BX1},${BY} Z`);
      readout.textContent = `moment at midspan = ${influence(x, z).toFixed(2)} kN·m per kN`;
      caption.textContent = t >= n * PER
        ? "Done. Each square is coloured by the moment at G2's midspan when the load stands there: this map is its influence surface. Setu builds seven such maps for every girder (moment at four sections near midspan, shear, reaction, deflection)."
        : `Load at x = ${x.toFixed(1)} m, z = ${z.toFixed(1)} m. The square it stands on is coloured by the moment it causes at the red line.`;
    });
  }

  // ── 2. one solve instead of thousands ──────────────────────────────────────
  function adjointAnim(root) {
    const NX = 14, NZ = 6, CW = 18, CH = 18;
    const s = svg("svg", { viewBox: "0 0 620 210", class: "anim-svg" });
    const grids = [["The slow way: one solve per point", 24], ["Setu: one solve for every point", 330]].map(([title, x0]) => {
      s.append(label(x0, 20, title, { "font-size": 12.5, "font-weight": 600 }));
      const g = svg("g", { transform: `translate(${x0 + 12}, 40)` });
      s.append(g);
      const cells = [];
      for (let j = 0; j < NZ; j++) for (let i = 0; i < NX; i++) {
        const r = svg("rect", { x: i * CW, y: j * CH, width: CW - 1, height: CH - 1, fill: "currentColor", "fill-opacity": 0.06 });
        g.append(r); cells.push(r);
      }
      const counter = label(x0 + 12, 40 + NZ * CH + 30, "", { "font-size": 20, "font-weight": 800 });
      s.append(counter);
      return { cells, counter, x0 };
    });
    const value = m => influence(((m % NX) + 0.5) * SPAN / NX, (Math.floor(m / NX) + 0.5) * WIDTH / NZ) / PEAK;
    const kick = svg("g", { transform: `translate(${grids[1].x0 + 12 + NX * CW / 2}, ${40 + (GIRDERS[TARGET] / WIDTH) * NZ * CH})`, opacity: 0 },
      svg("path", { d: "M-16,0 a16,16 0 0,1 16,-16", fill: "none", stroke: NAVY, "stroke-width": 3, "marker-end": "url(#setu-arrow)" }),
      svg("path", { d: "M16,0 a16,16 0 0,1 -16,16", fill: "none", stroke: NAVY, "stroke-width": 3, "marker-end": "url(#setu-arrow)" }),
      svg("circle", { r: 4, fill: NAVY }));
    s.append(svg("defs", {}, svg("marker", { id: "setu-arrow", viewBox: "0 0 10 10", refX: 5, refY: 5, markerWidth: 5, markerHeight: 5, orient: "auto-start-reverse" }, svg("path", { d: "M0,0 L10,5 L0,10 z", fill: NAVY }))), kick);
    const caption = html("p", { className: "anim-caption" });
    root.append(s, caption);
    const n = NX * NZ, PER = 0.07;
    player(root, n * PER + 0.4, t => {
      const k = Math.min(n, Math.floor(t / PER));
      grids[0].cells.forEach((c, m) => { c.setAttribute("fill", m < k ? heat(value(m)) : "currentColor"); c.setAttribute("fill-opacity", m < k ? 1 : 0.06); });
      grids[0].counter.textContent = `${k} solves`;
      const f = ease(clamp((t - 0.8) / 0.9));
      kick.setAttribute("opacity", clamp((t - 0.3) / 0.3) * (1 - clamp((t - 1.9) / 0.5)));
      grids[1].cells.forEach((c, m) => { c.setAttribute("fill", f > 0 ? heat(value(m) * f) : "currentColor"); c.setAttribute("fill-opacity", f > 0 ? 1 : 0.06); });
      grids[1].counter.textContent = t > 0.8 ? "1 solve" : "0 solves";
      caption.textContent = t < 0.8
        ? "Instead of a real load, Setu applies a 'virtual' action at the one place it wants to know about (here, a unit kink in G2 at midspan)…"
        : t < n * PER ? "…and the deck's movement under that single action is the whole influence surface at once (Maxwell–Betti reciprocity). The slow way needs one full solve for every point of the deck."
          : `Same map. The slow way took ${n} solves for this small grid; a real deck mesh has thousands of points. Setu always needs one.`;
    });
  }

  // ── 3. the search replayed with real IRC vehicles on a 35 m deck, for any girder and any design place ──
  const RSPAN = 35, RWIDTH = 11, KERB = 0.5, RGIRDERS = [1.4, 4.1, 6.9, 9.6];
  // the design places Setu checks on every girder; the moment is read at midspan and at 0.02L, 0.04L and 0.06L towards the bearing
  const PLACES = {
    moment: { label: "Moment near midspan", unit: "kN·m", spread: 2.6, sections: [0.5, 0.48, 0.46, 0.44] },
    shear: { label: "Shear at the support", unit: "kN", spread: 2.0, sections: [0] },
    reaction: { label: "Reaction at the bearing", unit: "kN", spread: 1.7, sections: [0] },
  };
  function influence35(x, z, girder, kind, section) {
    if (x < 0 || x > RSPAN || z < 0 || z > RWIDTH) return 0;
    const place = PLACES[kind], a = section * RSPAN;
    const along = kind === "moment" ? (x <= a ? x * (RSPAN - a) / RSPAN : a * (RSPAN - x) / RSPAN) : (RSPAN - x) / RSPAN * (kind === "reaction" ? 1 : 0.92);
    return along * (0.1 + 0.9 * Math.exp(-Math.pow((z - RGIRDERS[girder]) / place.spread, 2)));
  }

  function replayAnim(root) {
    const PX = 17.5, X0 = 60 + 12 * PX, Y0 = 44, DECK_W = RSPAN * PX, DECK_H = RWIDTH * PX;
    const state = { girder: 1, kind: "moment" };
    const controls = html("div", { className: "anim-controls" });
    const girderButtons = RGIRDERS.map((_, k) => html("button", { type: "button", textContent: `G${k + 1}${k === 0 || k === RGIRDERS.length - 1 ? " (edge)" : ""}` }));
    const placeButtons = Object.entries(PLACES).map(([key, p]) => { const b = html("button", { type: "button", textContent: p.label }); b.dataset.kind = key; return b; });
    controls.append(html("span", { textContent: "Girder" }), ...girderButtons, html("span", { className: "gap", textContent: "Result" }), ...placeButtons);
    root.append(controls);
    const s = svg("svg", { viewBox: "0 0 1100 580", class: "anim-svg anim-wide" });
    V().defs(s);
    const title = label(60, 24, "", { "font-size": 14, "font-weight": 600 });
    s.append(title);
    s.append(svg("defs", {}, svg("clipPath", { id: "replay-clip" }, svg("rect", { x: 60, y: Y0 - 6, width: 980, height: DECK_H + 12 }))));
    s.append(svg("rect", { x: 60, y: Y0, width: 980, height: DECK_H, fill: "#3b3f45", opacity: 0.35 }));
    const CELL = 0.5, cells = [];
    for (let x = 0; x < RSPAN; x += CELL) for (let z = 0; z < RWIDTH; z += CELL) {
      const r = svg("rect", { x: X0 + x * PX, y: Y0 + z * PX, width: CELL * PX + 0.5, height: CELL * PX + 0.5 });
      r.dataset.x = x + CELL / 2; r.dataset.z = z + CELL / 2;
      s.append(r); cells.push(r);
    }
    [KERB, RWIDTH - KERB].forEach(z => s.append(svg("line", { x1: X0, y1: Y0 + z * PX, x2: X0 + DECK_W, y2: Y0 + z * PX, stroke: "#fff", "stroke-width": 1.5, opacity: 0.8 })));
    const girderLines = RGIRDERS.map((z, k) => {
      const line = svg("line", { x1: X0, y1: Y0 + z * PX, x2: X0 + DECK_W, y2: Y0 + z * PX, "stroke-dasharray": "7 5" });
      const tag = label(X0 - 8, Y0 + z * PX + 4, `G${k + 1}`, { "text-anchor": "end", "font-size": 11 });
      s.append(line, tag);
      return { line, tag };
    });
    [X0, X0 + DECK_W].forEach(x => s.append(svg("line", { x1: x, y1: Y0 - 6, x2: x, y2: Y0 + DECK_H + 6, stroke: "currentColor", "stroke-width": 2.5 })));
    const sectionTicks = svg("g"), sectionMark = svg("line", { stroke: RED, "stroke-width": 3 });
    s.append(sectionTicks, sectionMark);
    const world = svg("g", { transform: `translate(${X0},${Y0}) scale(${PX})` });
    s.append(svg("g", { "clip-path": "url(#replay-clip)" }, world));

    // each vehicle alone in a few places, then lane arrangements rolled together (impact factors illustrative)
    const IMPACT = { "Class A": 1.186, "Class 70R Wheeled": 1.186, "Class 70R Tracked": 1.10 };
    const STEPS = 120;
    const layouts = () => {
      const zg = Math.min(Math.max(RGIRDERS[state.girder], 1.8), RWIDTH - 1.8), zOther = zg > RWIDTH / 2 ? zg - 3.5 : zg + 3.5;
      const single = (name, heading, z) => ({ label: `${name.replace("Class ", "")}${heading > 0 ? " ↺" : ""} alone · z ${z.toFixed(2)} m`, kind: "single", vehicles: [{ name, heading, z }] });
      return [
        single("Class A", -1, 9.35), single("Class A", -1, 6.85), single("Class A", -1, zg), single("Class A", 1, zg),
        single("Class 70R Wheeled", -1, Math.min(Math.max(zg, 2.95), RWIDTH - 2.95)), single("Class 70R Wheeled", 1, Math.min(Math.max(zg, 2.95), RWIDTH - 2.95)),
        single("Class 70R Tracked", -1, Math.min(Math.max(zg, 2.95), RWIDTH - 2.95)),
        { label: "Class A + Class A", kind: "arrangement", vehicles: [{ name: "Class A", heading: -1, z: zg }, { name: "Class A", heading: 1, z: zOther }] },
        { label: "Class A × 3 (× 0.9)", kind: "arrangement", vehicles: [{ name: "Class A", heading: -1, z: 2.3 }, { name: "Class A", heading: -1, z: 5.8 }, { name: "Class A", heading: 1, z: 9.3 }], reduction: 0.9 },
      ];
    };
    // roll every layout over one section's surface; each vehicle drives the way it faces
    const rollAll = section => layouts().map(tr => {
      tr.parts = tr.vehicles.map(v => { const drawn = V().vehicle(v.name, { heading: v.heading, z_m: v.z, impact_factor: IMPACT[v.name] }); return { drawn, wheels: V().wheels(drawn) }; });
      tr.pos = tr.parts.map(p => {
        const enter = p.drawn.heading < 0 ? RSPAN + 4 : -p.drawn.body_m[1] - 4, leave = p.drawn.heading < 0 ? -p.drawn.body_m[1] - 4 : RSPAN + 4;
        return Array.from({ length: STEPS + 1 }, (_, i) => lerp(enter, leave, i / STEPS));
      });
      tr.xs = tr.pos[0];
      tr.moments = tr.xs.map((_, i) => (tr.reduction || 1) * tr.parts.reduce((sum, p, n) => sum + p.drawn.impact_factor * p.wheels.reduce((a, [dx, dy, kn]) => a + kn * influence35(tr.pos[n][i] + dx, p.drawn.z_m + dy, state.girder, state.kind, section), 0), 0));
      tr.peakAt = tr.moments.indexOf(Math.max(...tr.moments));
      tr.total = tr.peak = tr.moments[tr.peakAt];
      return tr;
    });
    let trials = [], winner = 0, top = 1, section = 0.5;

    const GX0 = 80, GX1 = 560, GY0 = 300, GY1 = 530, BX = 860, BY = 296;
    const graphTitle = label(GX0, GY0 - 16, "", { "font-size": 13, "font-weight": 600 });
    s.append(graphTitle);
    s.append(svg("line", { x1: GX0, y1: GY1, x2: GX1, y2: GY1, stroke: "currentColor", "stroke-opacity": 0.4 }), svg("line", { x1: GX0, y1: GY0, x2: GX0, y2: GY1, stroke: "currentColor", "stroke-opacity": 0.4 }));
    const gx = x => lerp(GX0, GX1, (x + 24) / (RSPAN + 28)), gy = v => lerp(GY1, GY0, v / top);
    [0, RSPAN / 2, RSPAN].forEach(x => s.append(label(gx(x), GY1 + 16, `${x} m`, { "text-anchor": "middle", "font-size": 10.5, "fill-opacity": 0.7 })));
    s.append(label((GX0 + GX1) / 2, GY1 + 34, "front axle position x", { "text-anchor": "middle", "font-size": 11, "fill-opacity": 0.7 }));
    const faint = svg("g"), curve = svg("path", { fill: "none", "stroke-width": 3 }), dot = svg("circle", { r: 6, stroke: "#fff", "stroke-width": 2 }), peakText = label(0, 0, "", { "text-anchor": "middle", "font-weight": 700 });
    s.append(faint, curve, dot, peakText);
    s.append(label(620, BY - 12, "What was tried — largest effect of each", { "font-size": 13, "font-weight": 600 }));
    const bars = Array.from({ length: 9 }, (_, k) => {
      const y = BY + k * 25;
      const name = label(BX - 8, y + 13, "", { "text-anchor": "end", "font-size": 11 }), rect = svg("rect", { x: BX, y, height: 17, rx: 3, width: 0 }), value = label(BX, y + 13, "", { "font-size": 11, "font-weight": 600 });
      s.append(name, rect, value);
      return { name, rect, value };
    });
    const caption = html("p", { className: "anim-caption" });
    root.append(s, caption);

    // recompute everything for the chosen girder and place, and redraw the static parts
    function rebuild() {
      const place = PLACES[state.kind];
      const bySection = place.sections.map(sec => ({ sec, trials: rollAll(sec) }));
      const governing = bySection.reduce((a, b) => Math.max(...b.trials.map(t => t.total)) > Math.max(...a.trials.map(t => t.total)) ? b : a);
      section = governing.sec; trials = governing.trials;
      winner = trials.reduce((a, t, k) => t.total > trials[a].total ? k : a, 0);
      top = Math.max(...trials.map(t => t.total)) * 1.1;
      const peakValue = Math.max(...cells.map(c => influence35(+c.dataset.x, +c.dataset.z, state.girder, state.kind, section)));
      cells.forEach(c => c.setAttribute("fill", heat(influence35(+c.dataset.x, +c.dataset.z, state.girder, state.kind, section) / peakValue)));
      girderLines.forEach(({ line, tag }, k) => {
        const on = k === state.girder;
        line.setAttribute("stroke", on ? NAVY : "#fff"); line.setAttribute("stroke-width", on ? 2.5 : 1); line.setAttribute("opacity", on ? 1 : 0.6);
        tag.setAttribute("font-weight", on ? 700 : 400);
      });
      const zg = RGIRDERS[state.girder];
      sectionTicks.replaceChildren(...place.sections.map(sec => svg("line", { x1: X0 + sec * DECK_W, y1: Y0 + (zg - 0.8) * PX, x2: X0 + sec * DECK_W, y2: Y0 + (zg + 0.8) * PX, stroke: RED, "stroke-width": 1.5, opacity: 0.55 })));
      sectionMark.setAttribute("x1", X0 + section * DECK_W); sectionMark.setAttribute("x2", X0 + section * DECK_W);
      sectionMark.setAttribute("y1", Y0 + (zg - 1.3) * PX); sectionMark.setAttribute("y2", Y0 + (zg + 1.3) * PX);
      title.textContent = `Top view — G${state.girder + 1}'s influence surface for the ${place.label.toLowerCase()}, and the vehicles Setu tries on it`;
      graphTitle.textContent = `${place.label} in G${state.girder + 1} as the vehicles roll (${place.unit})`;
      bars.forEach((b, k) => { b.name.textContent = trials[k].label; });
      girderButtons.forEach((b, k) => { b.classList.toggle("on", k === state.girder); b.setAttribute("aria-pressed", k === state.girder); });
      placeButtons.forEach(b => { b.classList.toggle("on", b.dataset.kind === state.kind); b.setAttribute("aria-pressed", b.dataset.kind === state.kind); });
      shown = -1;
    }

    const ROLL = 2.2, HOLDT = 0.5, EACH = ROLL + HOLDT, FINAL = 1.5;
    let shown = -1;
    rebuild();
    const playback = player(root, 9 * EACH + FINAL, t => {
      const place = PLACES[state.kind];
      const done = t >= trials.length * EACH;
      const k = done ? winner : Math.min(trials.length - 1, Math.floor(t / EACH));
      const tr = trials[k], f = done ? 1 : clamp((t - k * EACH) / ROLL), rolling = !done && f < 1;
      const i = rolling ? Math.round(f * STEPS) : tr.peakAt;
      if (shown !== k) { world.replaceChildren(...tr.parts.map(p => V().draw(p.drawn))); shown = k; }
      [...world.children].forEach((g, n) => g.setAttribute("transform", `translate(${tr.pos[n][i]},${tr.parts[n].drawn.z_m})`));
      const finished = done ? trials.length : rolling ? k : k + 1;
      faint.replaceChildren(...trials.slice(0, done ? trials.length : k).filter((_, m) => !(done && m === winner)).map(p => svg("path", {
        d: polyline(p.xs.map((x, m) => [x, p.moments[m]]), gx, gy), fill: "none", "stroke-width": 1.3, stroke: p.kind === "arrangement" ? STEEL : GREY, opacity: 0.45 })));
      const colour = done ? GREEN : tr.kind === "arrangement" ? STEEL : SAFFRON;
      const upto = rolling ? i + 1 : tr.xs.length;
      curve.setAttribute("d", polyline(tr.xs.slice(0, upto).map((x, m) => [x, tr.moments[m]]), gx, gy));
      curve.setAttribute("stroke", colour);
      const seen = tr.moments.slice(0, upto), best = seen.indexOf(Math.max(...seen));
      dot.setAttribute("cx", gx(tr.xs[best])); dot.setAttribute("cy", gy(seen[best])); dot.setAttribute("fill", colour);
      peakText.setAttribute("x", gx(tr.xs[best])); peakText.setAttribute("y", gy(seen[best]) - 12); peakText.setAttribute("fill", colour);
      peakText.textContent = `peak ${fmt(seen[best])}`;
      const scale = 170 / top;
      bars.forEach((b, m) => {
        const on = m < finished, w = on ? trials[m].total * scale : 0;
        b.rect.setAttribute("width", w);
        b.rect.setAttribute("fill", done && m === winner ? GREEN : trials[m].kind === "arrangement" ? STEEL : "#b9b4ab");
        b.value.setAttribute("x", BX + w + 5); b.value.textContent = on ? fmt(trials[m].total) : "";
        b.name.setAttribute("font-weight", m === k && !done ? 700 : 400);
      });
      const where = state.kind === "moment" ? ` at x = ${fmt(section * RSPAN, 1)} m (the worst of midspan, 0.02L, 0.04L and 0.06L off it)` : "";
      caption.textContent = done
        ? `Critical position for the ${place.label.toLowerCase()} of G${state.girder + 1}${where}: ${trials[winner].label}. Setu repeats this search for every girder and every design place — pick another above.`
        : `${k + 1} / ${trials.length} · ${tr.label} — ${rolling ? `now ${fmt(tr.moments[i])} ${place.unit}` : `peak ${fmt(tr.peak)} ${place.unit}`}`;
    }, { hold: 3.5 });
    girderButtons.forEach((b, k) => b.onclick = () => { state.girder = k; rebuild(); playback.restart(); });
    placeButtons.forEach(b => b.onclick = () => { state.kind = b.dataset.kind; rebuild(); playback.restart(); });
  }

  // ── 4. dead load in construction stages ─────────────────────────────────────
  function stagesAnim(root) {
    const s = svg("svg", { viewBox: "0 0 620 300", class: "anim-svg" });
    const CX = 170, TOP = 90;
    const slab = svg("rect", { x: CX - 120, y: TOP, width: 240, height: 34, rx: 3 });
    const studs = svg("g", {}, ...[-30, -10, 10, 30].map(dx => svg("rect", { x: CX + dx - 2, y: TOP + 30, width: 4, height: 12, fill: "#666" })));
    const girder = svg("g", { fill: STEEL }, svg("rect", { x: CX - 40, y: TOP + 40, width: 80, height: 10 }), svg("rect", { x: CX - 5, y: TOP + 50, width: 10, height: 120 }),
      svg("rect", { x: CX - 50, y: TOP + 170, width: 100, height: 12 }));
    const kerbs = svg("g", {}, svg("rect", { x: CX - 118, y: TOP - 22, width: 26, height: 22, fill: "#9a948a" }), svg("rect", { x: CX + 92, y: TOP - 22, width: 26, height: 22, fill: "#9a948a" }),
      svg("rect", { x: CX - 92, y: TOP - 7, width: 184, height: 7, fill: "#3b3f45" }));
    // a Class A lorry seen from behind: box body, cab roof, dual tyres
    const lorry = svg("g", {},
      svg("rect", { x: CX - 26, y: TOP - 70, width: 52, height: 10, rx: 3, fill: "#d9480f" }),
      svg("rect", { x: CX - 36, y: TOP - 62, width: 72, height: 42, rx: 4, fill: "#f6c453", stroke: "#8a5a00", "stroke-width": 1.5 }),
      svg("rect", { x: CX - 30, y: TOP - 22, width: 60, height: 5, fill: "#39414a" }),
      ...[-1, 1].flatMap(side => [svg("rect", { x: CX + side * 30 - 9, y: TOP - 20, width: 8, height: 13, rx: 2, fill: "#1b1b1d" }), svg("rect", { x: CX + side * 30 + 1, y: TOP - 20, width: 8, height: 13, rx: 2, fill: "#1b1b1d" })]));
    const na = svg("g", {}, svg("line", { x1: CX - 140, x2: CX + 140, stroke: RED, "stroke-width": 1.5, "stroke-dasharray": "5 4" }), label(CX + 144, 4, "neutral axis", { "font-size": 11, fill: RED }));
    s.append(slab, studs, girder, kerbs, lorry, na);
    const bars = svg("g", { transform: "translate(380, 40)" });
    s.append(bars);
    const parts = [["steel self weight", 0.11, STEEL], ["wet slab", 0.34, "#8d99ae"], ["kerbs, barriers, footpath", 0.1, "#9a948a"], ["surfacing", 0.07, "#3b3f45"], ["traffic", 0.38, SAFFRON]];
    bars.append(label(0, -14, "Moment at midspan, stage by stage", { "font-size": 12.5, "font-weight": 600 }));
    const rects = parts.map(([name, , colour]) => { const r = svg("rect", { x: 0, width: 50, fill: colour }), l = label(60, 0, name, { "font-size": 11.5 }); bars.append(r, l); return [r, l]; });
    const caption = html("p", { className: "anim-caption" });
    root.append(s, caption);
    const steps = [
      ["1 · The steel girders go up. They carry their own weight alone.", "steel"],
      ["2 · Wet concrete is poured. It cannot help yet, so the steel alone carries it (the 'un-propped' method).", "wet"],
      ["3 · The concrete hardens and the shear studs lock it to the steel: now they bend together as one composite section.", "composite"],
      ["4 · Kerbs, barriers, footpath and surfacing go on. They stay for decades, so concrete creep is allowed for (modular ratio 15).", "sidl"],
      ["5 · Traffic comes and goes, so the concrete is taken at full stiffness (modular ratio 7.5). All stages add up.", "live"],
    ];
    const STEP = 2.6, H = 200;
    player(root, steps.length * STEP, t => {
      const k = Math.min(steps.length - 1, Math.floor(t / STEP)), f = ease(clamp((t - k * STEP) / 0.8)), stage = steps[k][1];
      const wet = stage === "wet", composite = k >= 2;
      slab.setAttribute("fill", wet ? "#b8c0cc" : "#c8ccd2"); slab.setAttribute("opacity", k === 0 ? 0 : wet ? 0.35 + 0.4 * f : 1);
      slab.setAttribute("stroke", wet ? "#8d99ae" : "none"); slab.setAttribute("stroke-dasharray", wet ? "4 3" : "");
      studs.setAttribute("opacity", composite ? (k === 2 ? f : 1) : 0);
      kerbs.setAttribute("opacity", k >= 3 ? (k === 3 ? f : 1) : 0);
      lorry.setAttribute("opacity", k >= 4 ? f : 0);
      lorry.setAttribute("transform", `translate(0,${k >= 4 ? lerp(-60, 0, f) : -60})`);
      na.setAttribute("transform", `translate(0,${composite ? lerp(TOP + 111, stage === "live" ? TOP + 58 : TOP + 72, k === 2 ? f : 1) : TOP + 111})`);
      let y = H;
      rects.forEach(([r, l], m) => {
        const grow = m < k ? 1 : m === k ? f : 0, h = parts[m][1] * H * grow;
        y -= h;
        r.setAttribute("y", y); r.setAttribute("height", h);
        l.setAttribute("y", y + h / 2 + 4); l.setAttribute("opacity", grow > 0.05 ? 1 : 0);
      });
      caption.textContent = steps[k][0];
    }, { hold: 3 });
  }

  // ── 5. load combinations ───────────────────────────────────────────────────
  function combinationAnim(root) {
    const s = svg("svg", { viewBox: "0 0 620 280", class: "anim-svg" });
    const effects = [["dead", 45, STEEL], ["surfacing", 8, "#3b3f45"], ["traffic", 32, SAFFRON], ["wind", 9, "#00a6a6"], ["temperature", 6, "#9b5de5"]];
    const combos = [["Traffic leads", [1.35, 1.75, 1.5, 0.9, 0.9]], ["Wind leads", [1.35, 1.75, 1.15, 1.5, 0.9]], ["Temperature leads", [1.35, 1.75, 1.15, 0.9, 1.5]]];
    const totals = combos.map(([, f]) => f.reduce((sum, v, i) => sum + v * effects[i][1], 0));
    const worst = totals.indexOf(Math.max(...totals));
    const X0 = 130, SCALE = 2.4;
    const rows = effects.map(([name, v, colour], i) => {
      const y = 30 + i * 34;
      s.append(label(X0 - 10, y + 16, name, { "text-anchor": "end" }), svg("rect", { x: X0, y, height: 22, width: v * SCALE, fill: colour, "fill-opacity": 0.25 }));
      const bar = svg("rect", { x: X0, y, height: 22, rx: 3, fill: colour }), l = label(0, y + 16, "", { "font-weight": 600 });
      s.append(bar, l);
      return { bar, l, v };
    });
    const totalBars = combos.map(([name], k) => {
      const y = 214 + k * 20;
      s.append(label(X0 - 10, y + 12, name, { "text-anchor": "end", "font-size": 11.5 }));
      const r = svg("rect", { x: X0, y, height: 14, rx: 3, fill: "currentColor", "fill-opacity": 0.35 }), tl = label(0, y + 12, "", { "font-size": 11.5 });
      s.append(r, tl);
      return { r, tl };
    });
    const caption = html("p", { className: "anim-caption" });
    root.append(s, caption);
    const STEP = 2.8;
    player(root, combos.length * STEP + 1, t => {
      const k = Math.min(combos.length - 1, Math.floor(t / STEP)), f = ease(clamp((t - k * STEP) / 1)), done = t >= combos.length * STEP;
      rows.forEach((row, i) => { const w = row.v * SCALE * lerp(1, combos[k][1][i], f); row.bar.setAttribute("width", w); row.l.setAttribute("x", X0 + w + 6); row.l.textContent = `× ${combos[k][1][i]}`; });
      totalBars.forEach((b, m) => {
        const on = m < k || (m === k && f > 0.95) || done, w = on ? totals[m] * 0.95 : 0, win = done && m === worst;
        b.r.setAttribute("width", w); b.tl.setAttribute("x", X0 + w + 6); b.tl.textContent = on ? totals[m].toFixed(0) : "";
        b.r.setAttribute("fill", win ? GREEN : "currentColor"); b.r.setAttribute("fill-opacity", win ? 1 : 0.35);
      });
      caption.textContent = done
        ? `Setu tries every combination and keeps the largest ("${combos[worst][0]}" here). That is the design value, with the combination and each load's share recorded.`
        : `${combos[k][0]}: it takes its full factor (1.5); the others take their smaller 'accompanying' factor. Dead load × 1.35, surfacing × 1.75 always (IRC:6 Table B.2).`;
    });
  }

  // ── 6. the meshing algorithm (the same rules as setu/builder/mesh.py) ───────
  function meshAnim(root) {
    const strips = [["footpath", 1.2], ["kerb", 0.3], ["carriageway", 6.0], ["kerb", 0.3], ["footpath", 1.2]];
    const L = 20, W = strips.reduce((a, [, w]) => a + w, 0), OVERHANG = 1.0, GCOUNT = 3, BRACES = 4, PANELS = 3, TARGET_SIZE = 0.9;
    const edges = strips.reduce((acc, [, w]) => [...acc, acc[acc.length - 1] + w], [0]);
    const girders = Array.from({ length: GCOUNT }, (_, k) => lerp(OVERHANG, W - OVERHANG, k / (GCOUNT - 1)));
    const braces = Array.from({ length: BRACES }, (_, k) => L * k / (BRACES - 1));
    const keep = [...new Set([...edges, ...girders].map(v => +v.toFixed(5)))].sort((a, b) => a - b);
    const across = [];
    keep.slice(0, -1).forEach((a, k) => { const b = keep[k + 1], n = Math.max(1, Math.ceil((b - a) / TARGET_SIZE - 1e-9)); for (let m = 0; m < n; m++) across.push(a + (b - a) * m / n); });
    across.push(W);
    const along = [];
    braces.slice(0, -1).forEach((a, k) => { for (let m = 0; m < PANELS; m++) along.push(a + (braces[k + 1] - a) * m / PANELS); });
    along.push(L);
    const PX = 26, X0 = 70, Y0 = 44, X = x => X0 + x * PX, Z = z => Y0 + z * PX;
    const s = svg("svg", { viewBox: "0 0 760 380", class: "anim-svg" });
    s.append(label(X0, 22, "Deck from above: the lines the mesh must keep, then the fill", { "font-size": 13, "font-weight": 600 }));
    s.append(svg("rect", { x: X(0), y: Z(0), width: L * PX, height: W * PX, fill: "currentColor", "fill-opacity": 0.04, stroke: "currentColor", "stroke-opacity": 0.4 }));
    const layer = () => { const g = svg("g", { opacity: 0 }); s.append(g); return g; };
    const shells = layer(), fillAcross = layer(), fillAlong = layer(), stripLines = layer(), girderLines = layer(), braceLines = layer(), nodes = layer();
    for (let i = 0; i < along.length - 1; i++) for (let j = 0; j < across.length - 1; j++)
      shells.append(svg("rect", { x: X(along[i]) + 0.8, y: Z(across[j]) + 0.8, width: (along[i + 1] - along[i]) * PX - 1.6, height: (across[j + 1] - across[j]) * PX - 1.6, fill: SAFFRON, "fill-opacity": 0.14 + 0.1 * ((i + j) % 2) }));
    across.forEach(z => fillAcross.append(svg("line", { x1: X(0), y1: Z(z), x2: X(L), y2: Z(z), stroke: "currentColor", "stroke-opacity": 0.35, "stroke-width": 0.8 })));
    along.forEach(x => fillAlong.append(svg("line", { x1: X(x), y1: Z(0), x2: X(x), y2: Z(W), stroke: "currentColor", "stroke-opacity": 0.35, "stroke-width": 0.8 })));
    edges.forEach((z, k) => {
      stripLines.append(svg("line", { x1: X(0), y1: Z(z), x2: X(L), y2: Z(z), stroke: SAFFRON, "stroke-width": 2 }));
      if (k < strips.length) stripLines.append(label(X(L) + 8, Z(z + strips[k][1] / 2) + 4, strips[k][0], { "font-size": 11, fill: SAFFRON }));
    });
    girders.forEach((z, k) => { girderLines.append(svg("line", { x1: X(0), y1: Z(z), x2: X(L), y2: Z(z), stroke: STEEL, "stroke-width": 3 }), label(X(0) - 8, Z(z) + 4, `G${k + 1}`, { "text-anchor": "end", "font-size": 11, "font-weight": 700 })); });
    braces.forEach(x => braceLines.append(svg("line", { x1: X(x), y1: Z(0) - 8, x2: X(x), y2: Z(W) + 8, stroke: GREEN, "stroke-width": 2.5 })));
    along.forEach(x => across.forEach(z => nodes.append(svg("circle", { cx: X(x), cy: Z(z), r: 1.8, fill: "currentColor", "fill-opacity": 0.7 }))));
    const caption = html("p", { className: "anim-caption" });
    root.append(s, caption);
    const steps = [
      [[stripLines], "1 · Strip edges: every footpath, kerb, carriageway and median edge becomes a mesh line, so each strip's load lands exactly on it."],
      [[stripLines, girderLines], "2 · Girder lines: girders are spaced evenly between the two overhangs. Each must sit on a mesh line so the slab can be tied to it."],
      [[stripLines, girderLines, braceLines], "3 · Brace lines: cross bracing at evenly spaced stations along the span, both ends included."],
      [[stripLines, girderLines, braceLines, fillAcross], `4 · Fill across: each gap between kept lines is split into equal pieces no wider than the target size (${TARGET_SIZE} m here).`],
      [[stripLines, girderLines, braceLines, fillAcross, fillAlong], `5 · Fill along: each brace panel is split into the chosen number of equal panels (${PANELS} here).`],
      [[stripLines, girderLines, braceLines, fillAcross, fillAlong, shells, nodes], `6 · A deck node at every crossing and a shell in every cell: ${along.length} × ${across.length} = ${along.length * across.length} nodes, ${(along.length - 1) * (across.length - 1)} shells.`],
    ];
    const STEP = 2.4;
    player(root, steps.length * STEP, t => {
      const k = Math.min(steps.length - 1, Math.floor(t / STEP)), f = ease(clamp((t - k * STEP) / 0.7));
      const visible = new Set(steps[k][0]), before = new Set(k > 0 ? steps[k - 1][0] : []);
      [shells, fillAcross, fillAlong, stripLines, girderLines, braceLines, nodes].forEach(g => g.setAttribute("opacity", visible.has(g) ? (before.has(g) ? 1 : f) : 0));
      caption.textContent = steps[k][1];
    }, { hold: 3 });
  }

  // ── 7. why checking only the kinks is exact ────────────────────────────────
  function breakpointsAnim(root) {
    const L = 20, stations = Array.from({ length: 9 }, (_, i) => i * 2.5), section = 8;
    const eta = x => (x <= section ? x * (L - section) / L : section * (L - x) / L);
    const ordinates = stations.map(x => eta(x) * (1 + 0.08 * Math.sin(x * 1.7)));
    const lineAt = x => {
      if (x < 0 || x > L) return 0;
      const i = Math.min(stations.length - 2, Math.floor(x / 2.5));
      return lerp(ordinates[i], ordinates[i + 1], (x - stations[i]) / 2.5);
    };
    const AXLES = [[0, 60], [3.2, 110], [4.4, 110]];
    const response = front => AXLES.reduce((sum, [dx, kn]) => sum + kn * lineAt(front + dx), 0);
    const kinks = [...new Set(stations.flatMap(xs => AXLES.map(([dx]) => +(xs - dx).toFixed(4))))].filter(f => f >= -4.4 && f <= L).sort((a, b) => a - b);
    const fronts = Array.from({ length: 241 }, (_, i) => lerp(L, -5, i / 240));
    const PX = 28, X0 = 190, BY = 74, X = x => X0 + x * PX;
    const s = svg("svg", { viewBox: "0 0 760 400", class: "anim-svg" });
    s.append(label(40, 24, "Girder from the side: between mesh stations the influence line is straight", { "font-size": 13, "font-weight": 600 }));
    s.append(svg("line", { x1: X(0), y1: BY, x2: X(L), y2: BY, stroke: "currentColor", "stroke-width": 3 }));
    stations.forEach(x => s.append(svg("circle", { cx: X(x), cy: BY, r: 3.5, fill: "currentColor" })));
    const IY = BY + 12, iy = v => IY + v * 12;
    s.append(svg("path", { d: `M${X(0)},${IY} ` + stations.map((x, i) => `L${X(x)},${iy(ordinates[i])}`).join(" ") + ` L${X(L)},${IY} Z`, fill: SAFFRON, "fill-opacity": 0.2, stroke: SAFFRON, "stroke-width": 2 }));
    s.append(label(X(0) - 10, IY + 26, "influence line", { "font-size": 11, fill: SAFFRON, "text-anchor": "end" }));
    const wheels = svg("g");
    AXLES.forEach(([dx, kn]) => { const g = svg("g", {}, svg("line", { x1: 0, y1: -34, x2: 0, y2: -6, stroke: STEEL, "stroke-width": 2.5 }), svg("path", { d: "M-5,-10 L0,-2 L5,-10 z", fill: STEEL }), label(0, -38, `${kn} kN`, { "text-anchor": "middle", "font-size": 10, fill: STEEL })); g.dataset.dx = dx; wheels.append(g); });
    s.append(wheels);
    const GY0 = 200, GY1 = 360, top = Math.max(...fronts.map(response)) * 1.15, gx = f => X(f), gy = v => lerp(GY1, GY0, v / top);
    s.append(label(40, GY0 - 14, "Moment against where the vehicle's front axle stands", { "font-size": 13, "font-weight": 600 }));
    s.append(svg("line", { x1: X(-5), y1: GY1, x2: X(L), y2: GY1, stroke: "currentColor", "stroke-opacity": 0.4 }));
    const kinkTicks = svg("g", { opacity: 0 });
    kinks.forEach(f => kinkTicks.append(svg("line", { x1: gx(f), y1: GY1, x2: gx(f), y2: gy(response(f)), stroke: RED, "stroke-width": 1, "stroke-dasharray": "2 3", opacity: 0.6 }), svg("circle", { cx: gx(f), cy: gy(response(f)), r: 3.2, fill: RED })));
    const curve = svg("path", { fill: "none", stroke: STEEL, "stroke-width": 2.5 });
    const bestKink = kinks.reduce((a, f) => response(f) > response(a) ? f : a, kinks[0]);
    const best = svg("g", { opacity: 0 }, svg("circle", { cx: gx(bestKink), cy: gy(response(bestKink)), r: 8, fill: "none", stroke: GREEN, "stroke-width": 3 }),
      label(gx(bestKink), gy(response(bestKink)) - 14, "largest value: on a kink", { "text-anchor": "middle", fill: GREEN, "font-weight": 700 }));
    s.append(kinkTicks, curve, best);
    const caption = html("p", { className: "anim-caption" });
    root.append(s, caption);
    const ROLL = 6;
    player(root, ROLL + 3, t => {
      const i = Math.round(clamp(t / ROLL) * (fronts.length - 1)), front = fronts[i];
      [...wheels.children].forEach(g => g.setAttribute("transform", `translate(${X(front + Number(g.dataset.dx))},${BY})`));
      curve.setAttribute("d", polyline(fronts.slice(0, i + 1).map(fr => [fr, response(fr)]), gx, gy));
      kinkTicks.setAttribute("opacity", clamp((t - ROLL) / 0.8));
      best.setAttribute("opacity", clamp((t - ROLL - 1) / 0.6));
      caption.textContent = t < ROLL
        ? "Setu reads the surface linearly between mesh stations, so as the vehicle rolls the moment changes along straight pieces, bending only when a wheel crosses a station."
        : "The red dots are those kinks: positions where some wheel sits exactly on a station. A straight piece peaks at one of its ends, so the largest value is always at a kink. Setu evaluates exactly these positions: no step size, nothing missed between steps.";
    }, { hold: 3 });
  }

  // ── 8. placing a train by dynamic programming (along_span.place_train) ──────
  function trainsAnim(root) {
    const L = 110, PITCH = 38.8, N = 3;
    const xs = Array.from({ length: 441 }, (_, i) => -8 + i * (L + 8) / 440);
    const r = x => x < 0 || x > L ? 0 : 100 * Math.sin(Math.PI * x / L) * (1 - 0.35 * Math.cos(2 * Math.PI * x / L));
    const one = xs.map(r), layers = [one], came = [null];
    for (let n = 1; n < N; n++) {
      const prev = layers[n - 1], runMax = [], runArg = [];
      prev.forEach((v, i) => { if (i === 0 || v > runMax[i - 1]) { runMax.push(v); runArg.push(i); } else { runMax.push(runMax[i - 1]); runArg.push(runArg[i - 1]); } });
      const next = [], from = [];
      xs.forEach((x, i) => {
        let j = -1;
        for (let m = i; m >= 0; m--) if (xs[m] <= x - PITCH + 1e-9) { j = m; break; }
        next.push(j < 0 ? -Infinity : one[i] + runMax[j]); from.push(j < 0 ? -1 : runArg[j]);
      });
      layers.push(next); came.push(from);
    }
    const finite = layers[N - 1].map(v => Number.isFinite(v) ? v : -Infinity);
    let at = finite.indexOf(Math.max(...finite));
    const chosen = [at];
    for (let n = N - 1; n > 0; n--) { at = came[n][at]; chosen.unshift(at); }
    const PX = 5.1, X0 = 90, GY0 = 70, GY1 = 290, top = Math.max(...finite) * 1.1;
    const X = x => X0 + (x + 8) * PX, Y = v => lerp(GY1, GY0, Math.max(0, v) / top);
    const s = svg("svg", { viewBox: "0 0 760 400", class: "anim-svg" });
    V().defs(s);
    s.append(label(40, 24, "Best total for a train of 1, 2 and 3 vehicles, with the last vehicle's front axle at x", { "font-size": 13, "font-weight": 600 }));
    s.append(svg("line", { x1: X(-8), y1: GY1, x2: X(L), y2: GY1, stroke: "currentColor", "stroke-opacity": 0.4 }));
    const colours = [GREY, STEEL, SAFFRON];
    const paths = layers.map((_, n) => { const p = svg("path", { fill: "none", stroke: colours[n], "stroke-width": n === 0 ? 2 : 2.6 }); s.append(p); return p; });
    const tags = layers.map((_, n) => { const tg = label(0, 0, `${n + 1} vehicle${n ? "s" : ""}`, { "font-size": 11.5, fill: colours[n], "font-weight": 700, "text-anchor": "end" }); s.append(tg); return tg; });
    const RY = GY1 + 30;
    s.append(svg("rect", { x: X(-8), y: RY, width: (L + 8) * PX, height: 34, fill: "#3b3f45", opacity: 0.3 }));
    [0, L].forEach(x => s.append(svg("path", { d: `M${X(x) - 7},${RY + 46} l7,-10 l7,10 z`, fill: "currentColor", "fill-opacity": 0.6 })));
    const road = svg("g", { transform: `translate(${X(0)},${RY + 17}) scale(${PX})`, opacity: 0 });
    chosen.forEach(i => { const g = V().draw(V().vehicle("Class A"), { label: false }); g.setAttribute("transform", `translate(${xs[i]},0)`); road.append(g); });
    s.append(road);
    const arrows = svg("g", { opacity: 0 });
    chosen.forEach((i, n) => arrows.append(svg("line", { x1: X(xs[i]), y1: Y(layers[n][i]), x2: X(xs[i]), y2: RY, stroke: GREEN, "stroke-width": 1.5, "stroke-dasharray": "3 3" }), svg("circle", { cx: X(xs[i]), cy: Y(layers[n][i]), r: 5, fill: GREEN })));
    s.append(arrows);
    const caption = html("p", { className: "anim-caption" });
    root.append(s, caption);
    const DRAW = 2.4;
    player(root, N * DRAW + 3, t => {
      layers.forEach((layer, n) => {
        const f = clamp((t - n * DRAW) / DRAW), upto = Math.round(f * (xs.length - 1));
        const pts = xs.slice(0, upto + 1).map((x, i) => [x, layer[i]]).filter(([, v]) => Number.isFinite(v));
        paths[n].setAttribute("d", polyline(pts, X, Y));
        const last = pts[pts.length - 1];
        tags[n].setAttribute("opacity", f > 0 && last ? 1 : 0);
        if (last) { tags[n].setAttribute("x", X(last[0]) - 4); tags[n].setAttribute("y", Y(last[1]) - 10); }
      });
      const reveal = clamp((t - N * DRAW) / 0.8);
      road.setAttribute("opacity", reveal); arrows.setAttribute("opacity", reveal);
      const n = Math.min(N - 1, Math.floor(t / DRAW));
      caption.textContent = t >= N * DRAW
        ? `Walking back from the best end point gives each vehicle's place, one Class A pitch (20.3 m lorry + 18.5 m gap = ${PITCH} m, IRC:6 Fig. 3) or more apart. Setu does this for trains of 1, 2, 3… vehicles and keeps the worst.`
        : n === 0 ? "Grey: the effect of one vehicle with its front axle at x, read off the influence surface."
          : `Best total for ${n + 1} vehicles ending at x = this vehicle's effect + the best total for ${n} ending at least one pitch behind. That best-behind is a running maximum, so each curve costs a single pass.`;
    }, { hold: 3 });
  }

  // ── 9. lanes across the carriageway (across_carriageway.cases_for_one_carriageway) ──
  function lanesAnim(root) {
    const CW = 7.5, GZ = 2.4;
    const envelope = { A: z => 1000 * (0.25 + 0.75 * Math.exp(-Math.pow((z - GZ) / 2.2, 2))), R: z => 1650 * (0.25 + 0.75 * Math.exp(-Math.pow((z - GZ) / 2.4, 2))) };
    // Table 3 blocks: a Class A lane is 2.3 m with 0.15 m to the kerb and 1.2 m between lanes; a lone 70R zone is 5.3 m with its vehicle in the middle
    const patterns = [
      { name: "one Class A lane", blocks: [["A", 2.3]], clearance: 0.15, gap: 0 },
      { name: "two Class A lanes", blocks: [["A", 2.3], ["A", 2.3]], clearance: 0.15, gap: 1.2 },
      { name: "one 70R zone", blocks: [["R", 5.3]], clearance: 0, gap: 0 },
    ];
    const STEPS = 24;
    patterns.forEach(p => {
      const used = 2 * p.clearance + p.blocks.reduce((a, [, w]) => a + w, 0) + p.gap * (p.blocks.length - 1);
      p.room = CW - used;
      const centres = offsets => { let edge = p.clearance; return p.blocks.map(([, w], k) => { const c = edge + offsets[k] + w / 2; edge += w + p.gap; return c; }); };
      const offsets = p.blocks.length === 1 ? Array.from({ length: STEPS + 1 }, (_, i) => [p.room * i / STEPS])
        : [...Array.from({ length: STEPS + 1 }, (_, i) => [0, p.room * i / STEPS]), ...Array.from({ length: STEPS + 1 }, (_, i) => [p.room * i / STEPS, p.room])];
      p.tries = offsets.map(o => { const c = centres(o); return { centres: c, value: c.reduce((a, z, k) => a + envelope[p.blocks[k][0]](z), 0) }; });
      p.best = p.tries.reduce((a, tr) => tr.value > a.value ? tr : a, p.tries[0]);
    });
    const winner = patterns.reduce((a, p, k) => p.best.value > patterns[a].best.value ? k : a, 0);
    const PX = 70, X0 = 90, EY0 = 50, EY1 = 190, RY = 224, Zx = z => X0 + z * PX, ey = v => lerp(EY1, EY0, v / 1800);
    const s = svg("svg", { viewBox: "0 0 760 420", class: "anim-svg" });
    s.append(label(40, 24, "Across the carriageway: the worst vehicle's effect at each lateral position (its envelope)", { "font-size": 13, "font-weight": 600 }));
    ["A", "R"].forEach(kind => {
      const pts = Array.from({ length: 76 }, (_, i) => [i * CW / 75, envelope[kind](i * CW / 75)]);
      s.append(svg("path", { d: polyline(pts, Zx, ey), fill: "none", stroke: kind === "A" ? SAFFRON : STEEL, "stroke-width": 2 }));
      s.append(label(Zx(CW) + 8, ey(envelope[kind](CW)) + 4, kind === "A" ? "Class A" : "70R", { "font-size": 11, fill: kind === "A" ? SAFFRON : STEEL, "font-weight": 700 }));
    });
    s.append(svg("line", { x1: Zx(GZ), y1: EY0 - 6, x2: Zx(GZ), y2: RY + 56, stroke: STEEL, "stroke-width": 1.5, "stroke-dasharray": "5 4" }), label(Zx(GZ) + 5, EY0 + 4, "girder below", { "font-size": 10.5, fill: STEEL }));
    s.append(svg("rect", { x: Zx(0), y: RY, width: CW * PX, height: 50, fill: "#3b3f45", opacity: 0.85 }));
    [[Zx(0) - 12, "kerb"], [Zx(CW), "kerb"]].forEach(([x]) => s.append(svg("rect", { x, y: RY - 6, width: 12, height: 62, fill: "#9a948a" })));
    const blocks = svg("g"), marks = svg("g");
    s.append(blocks, marks);
    const readout = label(40, RY + 86, "", { "font-size": 13, "font-weight": 600 });
    s.append(readout);
    const results = patterns.map((_, k) => { const tl = label(40, RY + 114 + k * 22, "", { "font-size": 12 }); s.append(tl); return tl; });
    const caption = html("p", { className: "anim-caption" });
    root.append(s, caption);
    const EACH = 3.4;
    player(root, patterns.length * EACH + 1.2, t => {
      const done = t >= patterns.length * EACH;
      const k = done ? winner : Math.min(patterns.length - 1, Math.floor(t / EACH)), p = patterns[k];
      const f = done ? 1 : clamp((t - k * EACH) / (EACH - 0.7));
      const tr = f >= 1 ? p.best : p.tries[Math.min(p.tries.length - 1, Math.round(f * (p.tries.length - 1)))];
      blocks.replaceChildren(...tr.centres.map((c, m) => {
        const kind = p.blocks[m][0], w = kind === "A" ? 2.3 : 2.9;
        return svg("g", {}, svg("rect", { x: Zx(c - w / 2), y: RY + 6, width: w * PX, height: 38, rx: 6, fill: kind === "A" ? "#f6c453" : "#a7b1bc", stroke: kind === "A" ? "#8a5a00" : "#39414a", "stroke-width": 1.5 }),
          label(Zx(c), RY + 30, kind === "A" ? "Class A" : "70R", { "text-anchor": "middle", "font-size": 11, fill: "#2b1d00", "font-weight": 700 }));
      }));
      marks.replaceChildren(...tr.centres.map((c, m) => svg("circle", { cx: Zx(c), cy: ey(envelope[p.blocks[m][0]](c)), r: 6, fill: RED, stroke: "#fff", "stroke-width": 2 })));
      readout.textContent = `${p.name}: ${tr.centres.map((c, m) => fmt(envelope[p.blocks[m][0]](c))).join(" + ")} = ${fmt(tr.value)} kN·m`;
      results.forEach((tl, m) => {
        const q = patterns[m], seen = m < k || (m === k && f >= 1) || done;
        tl.textContent = seen ? `${q.name}: best ${fmt(q.best.value)} kN·m${done && m === winner ? "   ← worst: the critical arrangement" : ""}` : "";
        tl.setAttribute("fill", done && m === winner ? GREEN : "currentColor"); tl.setAttribute("font-weight", done && m === winner ? 700 : 400);
      });
      caption.textContent = done
        ? "Every lane pattern the code allows is packed against the left kerb, then slid through every offset that could matter. The worst total after lane reduction (1.0 for two lanes here) is the critical arrangement."
        : `${p.name}: the blocks keep their IRC:6 widths, gaps and kerb clearances as they slide. Each reads its vehicle's effect off the envelope at its centre; neighbouring blocks may also spread apart.`;
    }, { hold: 3 });
  }

  const DESCRIPTIONS = {
    influence: "Animation: a 1 kN load visits every point of a deck; each point is coloured by the bending moment it causes at midspan of girder G2, building up the influence surface. A side view shows the girder's bending moment for the current load position.",
    adjoint: "Animation comparing two ways of getting an influence surface: the slow way solves the model once per deck point and fills the map square by square; Setu applies one virtual action and fills the whole map in one solve.",
    replay: "Interactive animation: IRC vehicles roll across a deck coloured by the chosen girder's influence surface for the chosen result (moment near midspan, shear at the support or reaction at the bearing). A graph traces the effect against vehicle position and a bar chart ranks every layout tried; the worst one is the critical position.",
    stages: "Animation of un-propped construction: the steel girder carries its own weight, then the wet slab; the slab hardens and becomes composite; kerbs and surfacing go on; then traffic. A bar grows with each stage's share of the midspan moment and the neutral axis rises when the section becomes composite.",
    combination: "Animation of IRC:6 Annex B load combinations: traffic, wind and temperature each lead in turn with factor 1.5 while the others take accompanying factors; the largest total is the design value.",
    mesh: "Animation of Setu's meshing: strip edges, girder lines and brace lines are kept, the gaps are filled to the target size, and a deck node and shell element are created at every crossing and cell.",
    breakpoints: "Animation: a three-axle vehicle rolls over a girder whose influence line is straight between mesh stations; the moment against vehicle position is made of straight pieces that bend only where a wheel crosses a station, so the largest value always sits on one of those kinks.",
    trains: "Animation of train placement by dynamic programming: the best total for one, two and three vehicles is built up along the span, then walking back from the best end point gives each vehicle's position, one Class A pitch or more apart.",
    lanes: "Animation of the search across the carriageway: each lane pattern the code allows is packed against the kerb and slid across; each vehicle reads its effect off the envelope at its centre, and the worst total is the critical arrangement.",
  };

  const ANIMATIONS = { influence: influenceAnim, adjoint: adjointAnim, replay: replayAnim, stages: stagesAnim, combination: combinationAnim,
    mesh: meshAnim, breakpoints: breakpointsAnim, trains: trainsAnim, lanes: lanesAnim };

  function start() {
    document.querySelectorAll(".anim[data-anim]:not([data-ready])").forEach(root => {
      root.dataset.ready = "1";
      root.setAttribute("role", "figure");
      root.setAttribute("aria-label", DESCRIPTIONS[root.dataset.anim] || "Animation");
      ANIMATIONS[root.dataset.anim]?.(root);
      root.querySelectorAll("svg").forEach(s => s.setAttribute("aria-hidden", "true"));
    });
  }
  if (window.document$) window.document$.subscribe(start); else document.addEventListener("DOMContentLoaded", start);
})();
