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
  function draw(v, { title = null, label = true } = {}) {
    const look = LOOK[v.name] || LOOK["Class A"], [b0, b1] = v.body_m, w = look.width, y0 = -w / 2;
    const nose = v.heading < 0 ? b0 : b1, back = v.heading < 0 ? 1 : -1;
    const g = el("g", { class: "vehicle" });
    if (title) g.append(el("title", {}, title));
    g.append(el("rect", { x: b0 + 0.25, y: y0 + 0.3, width: b1 - b0, height: w, rx: 0.4, fill: "#000", opacity: 0.35, filter: "url(#setu-soft)" }));
    if (v.tracked) {
      const [tl, tw] = v.track_m;
      [-1, 1].forEach(side => {
        const y = side * v.gauge_m / 2 - tw / 2;
        g.append(el("rect", { x: 0, y, width: tl, height: tw, rx: 0.2, fill: "#222" }));
        for (let x = 0.15; x < tl; x += 0.3) g.append(el("line", { x1: x, y1: y + 0.05, x2: x, y2: y + tw - 0.05, stroke: "#555", "stroke-width": 0.06 }));
      });
      const inner = v.gauge_m / 2 - tw / 2 + 0.1;
      g.append(el("rect", { x: 0.25, y: -inner, width: tl - 0.5, height: 2 * inner, rx: 0.3, fill: look.body, stroke: look.edge, "stroke-width": 0.05 }));
      const cx = tl * 0.55;
      g.append(el("line", { x1: cx, y1: 0, x2: nose - back * 1.6, y2: 0, stroke: look.edge, "stroke-width": 0.22, "stroke-linecap": "round" }));
      g.append(el("circle", { cx, cy: 0, r: 0.95, fill: look.cab, stroke: look.edge, "stroke-width": 0.06 }), el("circle", { cx: cx + 0.3, cy: -0.3, r: 0.22, fill: look.edge }));
      return g;
    }
    v.axles_m.forEach((x, k) => [-1, 1].forEach(side => {
      const tw = v.axle_loads_t[k] >= 10 ? look.tyre[1] : look.tyre[0];
      g.append(el("rect", { x: x - 0.45, y: side * v.gauge_m / 2 - tw / 2, width: 0.9, height: tw, rx: 0.14, fill: "#1b1b1d" }));
      if (tw > 0.4) g.append(el("line", { x1: x - 0.45, y1: side * v.gauge_m / 2, x2: x + 0.45, y2: side * v.gauge_m / 2, stroke: "#4a4a4d", "stroke-width": 0.05 }));
    }));
    const cabLength = v.name === "Class A" ? 2.1 : 2.6, cabEnd = nose + back * cabLength, bedStart = cabEnd + back * 0.18, tail = v.heading < 0 ? b1 : b0;
    g.append(el("rect", { ...across(bedStart, tail), y: y0, height: w, rx: 0.2, fill: look.body, stroke: look.edge, "stroke-width": 0.05, opacity: 0.94 }));
    const [lo, hi] = [Math.min(bedStart, tail), Math.max(bedStart, tail)];
    for (let x = lo + 0.7; x < hi - 0.3; x += 0.7) g.append(el("line", { x1: x, y1: y0 + 0.08, x2: x, y2: -y0 - 0.08, stroke: look.edge, "stroke-width": 0.03, opacity: 0.35 }));
    if (v.name !== "Class A") g.append(el("line", { x1: lo + 0.3, y1: 0, x2: hi - 0.3, y2: 0, stroke: look.edge, "stroke-width": 0.05, opacity: 0.4 }));
    g.append(el("rect", { ...across(nose, cabEnd), y: y0 + 0.05, height: w - 0.1, rx: 0.45, fill: look.cab, stroke: look.edge, "stroke-width": 0.05 }));
    g.append(el("rect", { ...across(nose + back * 0.25, nose + back * 0.8), y: y0 + 0.22, height: w - 0.44, rx: 0.15, fill: "url(#setu-glass)", opacity: 0.9 }));
    g.append(el("rect", { ...across(nose + back * 1.0, cabEnd - back * 0.2), y: y0 + 0.35, height: w - 0.7, rx: 0.2, fill: "#fff", opacity: 0.14 }));
    [-1, 1].forEach(side => g.append(el("rect", { ...across(nose + back * 0.45, nose + back * 0.7), y: side * (w / 2 + 0.05) - 0.08, height: 0.16, rx: 0.05, fill: look.edge })));
    if (label) g.append(el("text", { x: (lo + hi) / 2, y: 0.2, "font-size": 0.55, "text-anchor": "middle", fill: "#2b1d00", "font-weight": 650, opacity: 0.8 }, v.name.replace("Class ", "")));
    return g;
  }

  window.SetuVehicles = { CATALOGUE, LOOK, vehicle, wheels, defs, draw };
})();
