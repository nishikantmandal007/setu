// Draws every <div class="anim" data-anim="name"> on the page with the animation registered under that name.
(() => {
  const { registry } = window.SetuAnim;

  // each animation once, with its description for screen readers in place of the moving picture
  function start() {
    document.querySelectorAll(".anim[data-anim]:not([data-ready])").forEach(root => {
      const animation = registry[root.dataset.anim];
      if (!animation) return;
      root.dataset.ready = "1";
      root.setAttribute("role", "figure");
      root.setAttribute("aria-label", animation.description);
      animation.draw(root);
      root.querySelectorAll("svg").forEach(s => s.setAttribute("aria-hidden", "true"));
    });
  }
  // Material swaps pages without reloading; document$ fires on each
  if (window.document$) window.document$.subscribe(start); else document.addEventListener("DOMContentLoaded", start);
})();
