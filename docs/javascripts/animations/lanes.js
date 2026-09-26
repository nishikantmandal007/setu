// lanes across the carriageway (across_carriageway.cases_for_one_carriageway)
(() => {
  const { svg, html, lerp, clamp, fmt, SAFFRON, RED, GREEN, STEEL, polyline, label, player, register } = window.SetuAnim;

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

  register("lanes", lanesAnim, "Animation of the search across the carriageway: each lane pattern the code allows is packed against the kerb and slid across; each vehicle reads its effect off the envelope at its centre, and the worst total is the critical arrangement.");
})();
