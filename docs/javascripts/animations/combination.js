// load combinations
(() => {
  const { svg, html, lerp, clamp, ease, SAFFRON, GREEN, STEEL, label, player, register } = window.SetuAnim;

  function combinationAnim(root) {
    const s = svg("svg", { viewBox: "0 0 620 280", class: "anim-svg" });
    // temperature is combined too, but on a simply supported span with a free bearing it gives the girders no force, so it has no bar here
    const effects = [["dead", 45, STEEL], ["surfacing", 8, "#3b3f45"], ["traffic", 32, SAFFRON], ["wind", 9, "#00a6a6"]];
    const combos = [["Traffic leads", [1.35, 1.75, 1.5, 0.9]], ["Wind leads", [1.35, 1.75, 1.15, 1.5]]];
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
        : `${combos[k][0]}: it takes its full factor (1.5); the others take their smaller 'accompanying' factor. Dead load × 1.35, surfacing × 1.75 always (IRC:6 Table B.2). Temperature adds no girder force on a simply supported span with a free bearing, so it is not drawn.`;
    });
  }

  register("combination", combinationAnim, "Animation of IRC:6 Annex B load combinations: traffic and wind each lead in turn with factor 1.5 while the other takes its accompanying factor; the largest total is the design value. Temperature adds no girder force on a simply supported span with a free bearing.");
})();
