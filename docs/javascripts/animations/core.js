// Shared pieces for the docs animations: SVG helpers, colours, the play/pause player and a small illustrative deck.
// Each animation lives in its own file in this folder and registers itself; start.js draws them on the page.
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

  // the animations, by the name used in <div class="anim" data-anim="name">, with the text a screen reader reads instead
  const registry = {};
  const register = (name, draw, description) => { registry[name] = { draw, description }; };

  window.SetuAnim = { svg, html, lerp, clamp, ease, fmt, NAVY, SAFFRON, RED, GREEN, STEEL, GREY, V, heat, polyline, label, player, SPAN, WIDTH, GIRDERS, TARGET, influence, PEAK, deckPlan, register, registry };
})();
