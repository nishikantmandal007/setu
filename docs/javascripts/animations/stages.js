// dead load in construction stages
(() => {
  const { svg, html, lerp, clamp, ease, SAFFRON, RED, STEEL, label, player, register } = window.SetuAnim;

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

  register("stages", stagesAnim, "Animation of un-propped construction: the steel girder carries its own weight, then the wet slab; the slab hardens and becomes composite; kerbs and surfacing go on; then traffic. A bar grows with each stage's share of the midspan moment and the neutral axis rises when the section becomes composite.");
})();
