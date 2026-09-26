// MathJax settings for the arithmatex output; the library itself is bundled in vendor/ so formulas render offline and behind blockers
window.MathJax = {
  tex: { inlineMath: [["\\(", "\\)"]], displayMath: [["\\[", "\\]"]], processEscapes: true, processEnvironments: true },
  svg: { fontCache: "global" },
  options: { ignoreHtmlClass: ".*|", processHtmlClass: "arithmatex" },
};
// Material swaps pages without reloading; typeset each new page
if (window.document$) window.document$.subscribe(() => { if (window.MathJax.typesetPromise) { window.MathJax.typesetClear?.(); window.MathJax.typesetPromise(); } });
