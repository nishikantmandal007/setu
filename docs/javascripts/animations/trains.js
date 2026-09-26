// placing a train by dynamic programming (along_span.place_train)
(() => {
  const { svg, html, lerp, clamp, SAFFRON, GREEN, STEEL, GREY, V, polyline, label, player, register } = window.SetuAnim;

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

  register("trains", trainsAnim, "Animation of train placement by dynamic programming: the best total for one, two and three vehicles is built up along the span, then walking back from the best end point gives each vehicle's position, one Class A pitch or more apart.");
})();
