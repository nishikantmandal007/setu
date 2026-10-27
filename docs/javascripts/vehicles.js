// IRC vehicles drawn from above, to scale, in metres. One file for the docs and the web app (web/main.py serves it).
// A vehicle's own frame: x from its front axle (the other axles lie behind it in +x), y across from its centre line.
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    n.append(...kids);
    return n;
  };
  const across = (a, b) => ({ x: Math.min(a, b), width: Math.abs(b - a) });
  const positions = spacings => spacings.reduce((at, s) => [...at, at[at.length - 1] + s], [0]);

  const LOOK = {
    "Class A": { cab: "#d9480f", body: "#f6c453", edge: "#8a5a00", width: 2.0, tyre: [0.25, 0.5] },
    "Class 70R Wheeled": { cab: "#1f4fa3", body: "#a7b1bc", edge: "#39414a", width: 2.5, tyre: [0.86, 0.86] },
    "Class 70R Tracked": { cab: "#55652a", body: "#71833a", edge: "#2d3516", width: 2.9, tyre: [0.84, 0.84] },
    // the fatigue-load lorry of IRC:6 clause 204.6: 12/14/14 t axles 4.5 m + 1.4 m apart, dual tyres
    "Fatigue truck": { cab: "#6d5aa8", body: "#c9bfd8", edge: "#4b3d78", width: 2.39, tyre: [0.31, 0.71] },
  };

  // IRC:6-2017 Figs. 1 and 3, the same numbers as setu/irc6/vehicles.py
  const CATALOGUE = {
    "Class A": { axle_loads_t: [2.7, 2.7, 11.4, 11.4, 6.8, 6.8, 6.8, 6.8], axles_m: positions([1.1, 3.2, 1.2, 4.3, 3.0, 3.0, 3.0]), gauge_m: 1.8, lead_m: 0.6, trail_m: 0.9 },
    "Class 70R Wheeled": { axle_loads_t: [8, 12, 12, 17, 17, 17, 17], axles_m: positions([3.96, 1.52, 2.13, 1.37, 3.05, 1.37]), gauge_m: 1.93, lead_m: 0.81, trail_m: 0.91 },
    "Class 70R Tracked": { axle_loads_t: [70], tracked: true, track_m: [4.57, 0.84], gauge_m: 2.06 },
  };

  // a vehicle ready to draw: name from the catalogue, facing forwards (heading -1, driving towards -x) or turned round (+1)
  function vehicle(name, { heading = -1, x_m = 0, z_m = 0, impact_factor = 1 } = {}) {
    const c = CATALOGUE[name];
    if (c.tracked) return { name, tracked: true, track_m: c.track_m, gauge_m: c.gauge_m, axle_loads_t: c.axle_loads_t, body_m: [0, c.track_m[0]], heading: -1, axles_m: [], x_m, z_m, impact_factor };
    const length = c.axles_m[c.axles_m.length - 1];
    const turned = heading > 0;
    return {
      name, tracked: false, gauge_m: c.gauge_m, heading, x_m, z_m, impact_factor,
      axle_loads_t: turned ? [...c.axle_loads_t].reverse() : c.axle_loads_t,
      axles_m: turned ? [...c.axles_m].reverse().map(p => length - p) : c.axles_m,
      body_m: turned ? [-c.trail_m, length + c.lead_m] : [-c.lead_m, length + c.trail_m],
    };
  }

  // the wheels of a vehicle in its own frame: [dx, dy, kN], two per axle (a track as its two lines of load)
  function wheels(v) {
    if (v.tracked) return [-1, 1].map(side => [v.track_m[0] / 2, side * v.gauge_m / 2, v.axle_loads_t[0] * 9.81 / 2]);
    return v.axles_m.flatMap((x, k) => [-1, 1].map(side => [x, side * v.gauge_m / 2, v.axle_loads_t[k] * 9.81 / 2]));
  }

  // the shadow blur and windscreen gradient every drawing uses; add once per <svg>
  function defs(svg) {
    if (svg.querySelector("#setu-soft")) return;
    svg.append(el("defs", {},
      el("filter", { id: "setu-soft", x: "-20%", y: "-20%", width: "140%", height: "140%" }, el("feGaussianBlur", { stdDeviation: 0.18 })),
      el("linearGradient", { id: "setu-glass", x1: 0, x2: 1 }, el("stop", { offset: 0, "stop-color": "#cfe8ff" }), el("stop", { offset: 1, "stop-color": "#6fa8dc" }))));
  }

  // one vehicle as an SVG group in its own frame; place it with a transform
  function draw(v, { title = null, label = true, width_m = null } = {}) {
    const look = LOOK[v.name] || LOOK["Class A"], [b0, b1] = v.body_m, w = width_m ?? v.width_m ?? look.width, y0 = -w / 2;
    const nose = v.heading < 0 ? b0 : b1, back = v.heading < 0 ? 1 : -1;
    const g = el("g", { class: "vehicle" });
    if (title) g.append(el("title", {}, title));
    g.append(el("rect", { x: b0 + 0.22, y: y0 + 0.25, width: b1 - b0, height: w, rx: 0.38, fill: "#000", opacity: 0.28, filter: "url(#setu-soft)" }));
    if (v.tracked) {
      const [tl, tw] = v.track_m;
      [-1, 1].forEach(side => {
        const y = side * v.gauge_m / 2 - tw / 2;
        g.append(el("rect", { x: 0, y, width: tl, height: tw, rx: 0.18, fill: "#23272b", stroke: "#111", "stroke-width": 0.04 }));
        for (let x = 0.18; x < tl - 0.1; x += 0.28) g.append(el("line", { x1: x, y1: y + 0.05, x2: x, y2: y + tw - 0.05, stroke: "#5c6460", "stroke-width": 0.055 }));
      });
      const inner = v.gauge_m / 2 - tw / 2 + 0.12;
      g.append(el("rect", { x: 0.22, y: -inner, width: tl - 0.44, height: 2 * inner, rx: 0.28, fill: look.body, stroke: look.edge, "stroke-width": 0.055 }));
      const cx = tl * 0.52;
      g.append(el("line", { x1: cx, y1: 0, x2: nose - back * 1.45, y2: 0, stroke: look.edge, "stroke-width": 0.2, "stroke-linecap": "round" }));
      g.append(el("circle", { cx, cy: 0, r: 0.88, fill: look.cab, stroke: look.edge, "stroke-width": 0.06 }), el("circle", { cx: cx + 0.26, cy: -0.26, r: 0.2, fill: look.edge }));
      if (label) g.append(el("text", { x: cx, y: 0.18, "font-size": 0.46, "text-anchor": "middle", fill: "#f4f6f0", "font-weight": 700 }, "70R T"));
      return g;
    }
    v.axles_m.forEach((x, k) => {
      g.append(el("line", { x1: x, y1: -v.gauge_m / 2, x2: x, y2: v.gauge_m / 2, stroke: "#2b3036", "stroke-width": 0.07 }));
      [-1, 1].forEach(side => {
        const tw = v.axle_loads_t[k] >= 10 ? look.tyre[1] : look.tyre[0];
        g.append(el("rect", { x: x - 0.44, y: side * v.gauge_m / 2 - tw / 2, width: 0.88, height: tw, rx: 0.13, fill: "#1b1d21", stroke: "#0e1012", "stroke-width": 0.03 }));
        if (tw > 0.4) g.append(el("line", { x1: x - 0.42, y1: side * v.gauge_m / 2, x2: x + 0.42, y2: side * v.gauge_m / 2, stroke: "#4f545c", "stroke-width": 0.045 }));
      });
    });
    const cabLength = v.name === "Fatigue truck" ? 1.85 : v.name === "Class A" ? 2.05 : 2.45;
    const cabEnd = nose + back * cabLength, bedStart = cabEnd + back * 0.16, tail = v.heading < 0 ? b1 : b0;
    const drawBed = (xStart, xEnd, tagText = null) => {
      const [lo, hi] = [Math.min(xStart, xEnd), Math.max(xStart, xEnd)];
      g.append(el("rect", { x: lo, y: y0, width: hi - lo, height: w, rx: 0.18, fill: look.body, stroke: look.edge, "stroke-width": 0.055, opacity: 0.95 }));
      for (let x = lo + 0.65; x < hi - 0.25; x += 0.65) g.append(el("line", { x1: x, y1: y0 + 0.08, x2: x, y2: -y0 - 0.08, stroke: look.edge, "stroke-width": 0.028, opacity: 0.32 }));
      if (tagText) {
        const cx = (lo + hi) / 2, pillW = Math.min(hi - lo - 0.3, tagText.length * 0.31 + 0.45);
        g.append(el("rect", { x: cx - pillW / 2, y: -0.36, width: pillW, height: 0.72, rx: 0.18, fill: "rgba(255,255,255,.72)", stroke: look.edge, "stroke-width": 0.03 }),
          el("text", { x: cx, y: 0.17, "font-size": 0.48, "text-anchor": "middle", fill: "#1f242b", "font-weight": 700 }, tagText));
      }
    };
    if (v.name === "Class A" && v.axles_m.length === 8) {
      // IRC:6-2017 Fig. 2: driving vehicle 8.3 m, then two 4.8 m trailers 1.2 m apart (cl. 204.1.1: not detachable)
      const at = d => nose + back * d;
      for (const [ca, cb] of [[8.3, 9.5], [14.3, 15.5]]) g.append(el("line", { x1: at(ca), y1: 0, x2: at(cb), y2: 0, stroke: "#3a4149", "stroke-width": 0.14, "stroke-linecap": "round" }));
      drawBed(bedStart, at(8.3), label ? "Class A" : null);
      drawBed(at(9.5), at(14.3));
      drawBed(at(15.5), tail);
    } else {
      const shortName = v.name === "Fatigue truck" ? "40t Fatigue" : v.name.replace("Class ", "");
      drawBed(bedStart, tail, label ? shortName : null);
    }
    g.append(el("rect", { ...across(nose, cabEnd), y: y0 + 0.05, height: w - 0.1, rx: 0.42, fill: look.cab, stroke: look.edge, "stroke-width": 0.055 }));
    g.append(el("rect", { ...across(nose + back * 0.24, nose + back * 0.78), y: y0 + 0.22, height: w - 0.44, rx: 0.14, fill: "url(#setu-glass)", opacity: 0.92 }));
    g.append(el("rect", { ...across(nose + back * 0.95, cabEnd - back * 0.18), y: y0 + 0.34, height: w - 0.68, rx: 0.18, fill: "#fff", opacity: 0.16 }));
    [-1, 1].forEach(side => g.append(el("rect", { ...across(nose + back * 0.42, nose + back * 0.68), y: side * (w / 2 + 0.05) - 0.08, height: 0.16, rx: 0.05, fill: look.edge })));
    return g;
  }

  window.SetuVehicles = { CATALOGUE, LOOK, vehicle, wheels, defs, draw };
})();
