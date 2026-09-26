// what an influence surface is
(() => {
  const { svg, html, NAVY, SAFFRON, RED, heat, label, player, SPAN, WIDTH, GIRDERS, TARGET, influence, PEAK, deckPlan, register } = window.SetuAnim;

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

  register("influence", influenceAnim, "Animation: a 1 kN load visits every point of a deck; each point is coloured by the bending moment it causes at midspan of girder G2, building up the influence surface. A side view shows the girder's bending moment for the current load position.");
})();
