// temperature difference through the depth (IRC:6 cl. 215, Fig. 17b / Table 15B)
(() => {
  const { svg, html, lerp, clamp, ease, STEEL, label, player, register } = window.SetuAnim;

  function temperatureAnim(root) {
    // a 0.23 m slab with 75 mm surfacing on a 2.2 m girder: h1 = 0.6 h, h2 = 0.4 m below it
    const SLAB = 0.23, DEPTH = 2.4, H1 = 0.6 * SLAB, H2 = 0.4;
    const PROFILES = [
      { name: "Heating: the sun warms the slab", colour: "#e8792b", pts: [[0, 16.3], [H1, 4], [H1 + H2, 0], [DEPTH, 0]] },
      { name: "Cooling: the slab loses heat faster", colour: "#2b8ad6", pts: [[0, -4.5], [H1, 0], [H1 + H2, -8], [DEPTH, -8]] },
    ];
    const s = svg("svg", { viewBox: "0 0 700 372", class: "anim-svg" });
    const Y0 = 40, PXY = 120, Y = d => Y0 + d * PXY, CX = 150;
    // the composite section: slab, steel girder
    s.append(svg("rect", { x: CX - 120, y: Y(0), width: 240, height: SLAB * PXY, fill: "#c8ccd2" }));
    s.append(svg("rect", { x: CX - 45, y: Y(SLAB), width: 90, height: 6, fill: STEEL }), svg("rect", { x: CX - 4, y: Y(SLAB) + 6, width: 8, height: (DEPTH - SLAB) * PXY - 14, fill: STEEL }),
      svg("rect", { x: CX - 55, y: Y(DEPTH) - 8, width: 110, height: 8, fill: STEEL }));
    const glow = svg("rect", { x: CX - 120, y: Y(0), width: 240, height: (H1 + H2) * PXY, opacity: 0 });
    s.append(glow);
    s.append(label(CX, Y(DEPTH) + 22, "slab on a steel girder", { "text-anchor": "middle", "font-size": 12, "fill-opacity": 0.7 }));
    // the profile plot
    const PX0 = 380, PX1 = 670, T = t => lerp(PX0, PX1, (t + 10) / 30);
    s.append(svg("line", { x1: T(0), y1: Y(0) - 10, x2: T(0), y2: Y(DEPTH), stroke: "currentColor", "stroke-opacity": 0.5 }));
    [-10, 0, 10, 20].forEach(t => s.append(label(T(t), Y(DEPTH) + 18, `${t} °C`, { "text-anchor": "middle", "font-size": 10.5, "fill-opacity": 0.7 })));
    s.append(label(PX0, 22, "Temperature difference through the depth", { "font-size": 13, "font-weight": 600 }));
    [[H1, "h1 = 0.6 × slab"], [H1 + H2, "h1 + 0.4 m"]].forEach(([d, text]) => s.append(svg("line", { x1: PX0, y1: Y(d), x2: PX1, y2: Y(d), stroke: "currentColor", "stroke-opacity": 0.15, "stroke-dasharray": "3 3" }),
      label(PX1, Y(d) - 3, text, { "text-anchor": "end", "font-size": 10, "fill-opacity": 0.6 })));
    const curve = svg("path", { fill: "none", "stroke-width": 3 });
    const area = svg("path", { opacity: 0.18 });
    s.append(area, curve);
    const caption = html("p", { className: "anim-caption" });
    root.append(s, caption);
    const EACH = 3.4;
    player(root, 2 * EACH, t => {
      const k = Math.min(1, Math.floor(t / EACH)), f = ease(clamp((t - k * EACH) / 1.6)), p = PROFILES[k];
      const pts = p.pts.map(([d, v]) => [d, v * f]);
      curve.setAttribute("d", "M" + pts.map(([d, v]) => `${T(v)},${Y(d)}`).join(" L")); curve.setAttribute("stroke", p.colour);
      area.setAttribute("d", `M${T(0)},${Y(0)} ` + pts.map(([d, v]) => `L${T(v)},${Y(d)}`).join(" ") + ` L${T(0)},${Y(DEPTH)} Z`); area.setAttribute("fill", p.colour);
      glow.setAttribute("fill", p.colour); glow.setAttribute("opacity", 0.35 * f);
      caption.textContent = `${p.name}. The deck cannot bend freely to follow this uneven temperature, so it locks in stresses through the depth (Fig. 17b / Table 15B). `
        + "On a simply supported span with a free bearing these stresses balance inside each section: no girder force, only the stresses Setu reports and the bearing movement.";
    }, { hold: 2 });
  }

  register("temperature", temperatureAnim, "Animation of the IRC:6 temperature difference through the depth of a composite deck: the heating profile (slab hotter, 16.3 °C at the top falling to 4 °C at h1 and zero 0.4 m lower) and the cooling profile (slab colder, reversing to minus 8 °C). The locked-in stresses balance within each section, so a simply supported girder with a free bearing gets no force.");
})();
