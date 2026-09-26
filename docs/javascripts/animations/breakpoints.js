// why checking only the kinks is exact
(() => {
  const { svg, html, lerp, clamp, SAFFRON, RED, GREEN, STEEL, polyline, label, player, register } = window.SetuAnim;

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

  register("breakpoints", breakpointsAnim, "Animation: a three-axle vehicle rolls over a girder whose influence line is straight between mesh stations; the moment against vehicle position is made of straight pieces that bend only where a wheel crosses a station, so the largest value always sits on one of those kinks.");
})();
