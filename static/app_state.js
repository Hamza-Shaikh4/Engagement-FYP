// Applies background theme (simple, no heavy CSS changes)
(function () {
  const bg = document.body.getAttribute("data-bg") || "bg-default";
  const root = document.documentElement;

  if (bg === "bg-space") {
    root.style.setProperty("--bg-top", "#0b1020");
    root.style.setProperty("--bg-bottom", "#1b2a6b");
    root.style.setProperty("--surface", "rgba(255,255,255,0.10)");
    root.style.setProperty("--text", "#f8fafc");
    root.style.setProperty("--muted", "rgba(248,250,252,0.70)");
  } else if (bg === "bg-forest") {
    root.style.setProperty("--bg-top", "#dcfce7");
    root.style.setProperty("--bg-bottom", "#bbf7d0");
    root.style.setProperty("--surface", "rgba(255,255,255,0.85)");
    root.style.setProperty("--text", "#111827");
    root.style.setProperty("--muted", "rgba(17,24,39,0.65)");
  } else {
    // default (matches your current palette)
  }
})();