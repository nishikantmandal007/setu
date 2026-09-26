// the meshing algorithm (the same rules as setu/builder/mesh.py)
(() => {
  const { svg, html, lerp, clamp, ease, SAFFRON, GREEN, STEEL, label, player, register } = window.SetuAnim;

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

  register("mesh", meshAnim, "Animation of Setu's meshing: strip edges, girder lines and brace lines are kept, the gaps are filled to the target size, and a deck node and shell element are created at every crossing and cell.");
})();
