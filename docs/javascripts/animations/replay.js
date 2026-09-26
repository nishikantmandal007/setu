// the search replayed with real IRC vehicles on a 35 m deck, for any girder and any design place
(() => {
  const { svg, html, lerp, clamp, fmt, NAVY, SAFFRON, RED, GREEN, STEEL, GREY, V, heat, polyline, label, player, register } = window.SetuAnim;

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

  register("replay", replayAnim, "Interactive animation: IRC vehicles roll across a deck coloured by the chosen girder's influence surface for the chosen result (moment near midspan, shear at the support or reaction at the bearing). A graph traces the effect against vehicle position and a bar chart ranks every layout tried; the worst one is the critical position.");
})();
