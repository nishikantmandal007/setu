// one solve instead of thousands
(() => {
  const { svg, html, clamp, ease, NAVY, heat, label, player, SPAN, WIDTH, GIRDERS, TARGET, influence, PEAK, register } = window.SetuAnim;

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

  register("adjoint", adjointAnim, "Animation comparing two ways of getting an influence surface: the slow way solves the model once per deck point and fills the map square by square; Setu applies one virtual action and fills the whole map in one solve.");
})();
