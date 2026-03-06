const WINDOW_SECONDS = 10;
const IDLE_THRESHOLD_MS = 12000;

const storyId = String(window.STORY_ID || "").trim() || "unknown";

const reader = document.getElementById("reader");
const hasReader = Boolean(reader);

let windowStartMs = Date.now();

let totalScrollPx = 0;
let interactionCount = 0;
let navigationCount = 0;

let lastActivityMs = Date.now();
let idleSamples = 0;
let totalSamples = 0;

let lastScrollPos = hasReader ? reader.scrollTop : window.scrollY;
let maxScrollPosThisWindow = hasReader ? reader.scrollTop : window.scrollY;

let hiddenStartMs = null;
let hiddenMsThisWindow = 0;

let disengagedWindowsCount = 0;
let latestFocusLossRatio = 0;
let latestIdleRatio = 0;

function createPanel() {
  let panel = document.getElementById("trackerPanel");
  if (panel) return panel;

  panel = document.createElement("div");
  panel.id = "trackerPanel";
  panel.style.position = "fixed";
  panel.style.top = "12px";
  panel.style.right = "12px";
  panel.style.bottom = "auto";
  panel.style.width = "260px";
  panel.style.maxWidth = "40vw";
  panel.style.background = "rgba(17,17,17,0.92)";
  panel.style.color = "#fff";
  panel.style.padding = "12px";
  panel.style.borderRadius = "12px";
  panel.style.fontFamily = "system-ui, Arial";
  panel.style.fontSize = "13px";
  panel.style.whiteSpace = "pre-line";
  panel.style.zIndex = "9999";
  panel.style.pointerEvents = "none";
  document.body.appendChild(panel);

  return panel;
}

function updatePanel(text) {
  createPanel().textContent = text;
}

function markActivity() {
  lastActivityMs = Date.now();
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    hiddenStartMs = Date.now();
  } else {
    if (hiddenStartMs !== null) {
      hiddenMsThisWindow += (Date.now() - hiddenStartMs);
      hiddenStartMs = null;
    }
  }
});

if (hasReader) {
  reader.addEventListener("scroll", () => {
    const current = reader.scrollTop;
    totalScrollPx += Math.abs(current - lastScrollPos);
    lastScrollPos = current;
    if (current > maxScrollPosThisWindow) maxScrollPosThisWindow = current;
    markActivity();
  }, { passive: true });
} else {
  window.addEventListener("scroll", () => {
    const current = window.scrollY;
    totalScrollPx += Math.abs(current - lastScrollPos);
    lastScrollPos = current;
    if (current > maxScrollPosThisWindow) maxScrollPosThisWindow = current;
    markActivity();
  }, { passive: true });
}

window.addEventListener("click", (e) => {
  if (e.target.closest("[data-no-track='true']")) return;
  interactionCount++;
  markActivity();
  if (e.target.closest("a")) navigationCount++;
});

window.addEventListener("keydown", () => {
  interactionCount++;
  markActivity();
});

window.addEventListener("mousemove", markActivity);

setInterval(() => {
  totalSamples++;
  if ((Date.now() - lastActivityMs) >= IDLE_THRESHOLD_MS) idleSamples++;
}, 250);

function resetWindow() {
  windowStartMs = Date.now();
  totalScrollPx = 0;
  interactionCount = 0;
  navigationCount = 0;
  idleSamples = 0;
  totalSamples = 0;
  maxScrollPosThisWindow = hasReader ? reader.scrollTop : window.scrollY;
  hiddenMsThisWindow = 0;
}

function calculateFeatures() {
  const now = Date.now();
  const elapsedSeconds = (now - windowStartMs) / 1000;
  const safeSeconds = Math.max(1, elapsedSeconds);

  let hiddenMsTotal = hiddenMsThisWindow;
  if (document.hidden && hiddenStartMs !== null) hiddenMsTotal += (now - hiddenStartMs);

  const idle_ratio = totalSamples === 0 ? 0 : idleSamples / totalSamples;
  const scroll_speed_px_s = totalScrollPx / safeSeconds;
  const nav_rate_per_min = (navigationCount / safeSeconds) * 60;
  const interaction_rate_per_min = (interactionCount / safeSeconds) * 60;

  let scroll_depth_ratio = 0;
  if (hasReader) {
    const maxScrollPossible = Math.max(1, reader.scrollHeight - reader.clientHeight);
    scroll_depth_ratio = Math.min(1, maxScrollPosThisWindow / maxScrollPossible);
  } else {
    const maxScrollPossible = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    scroll_depth_ratio = Math.min(1, maxScrollPosThisWindow / maxScrollPossible);
  }

  const focus_loss_ratio = Math.min(1, hiddenMsTotal / (safeSeconds * 1000));

  return {
    story_id: storyId,
    idle_ratio,
    scroll_speed_px_s,
    scroll_depth_ratio,
    focus_loss_ratio,
    nav_rate_per_min,
    interaction_rate_per_min
  };
}

setInterval(async () => {
  if (window.__TRACKING_PAUSED__) return;

  const features = calculateFeatures();

  try {
    const res = await fetch("/api/engagement", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(features)
    });
    const result = await res.json();

    latestFocusLossRatio = features.focus_loss_ratio;
    latestIdleRatio = features.idle_ratio;

    if (result.label === "disengaged") {
      disengagedWindowsCount += 1;
    }

    if (typeof window.setLatestTrackerResult === "function") {
      window.setLatestTrackerResult({
        disengagedWindows: disengagedWindowsCount,
        latestFocusLoss: latestFocusLossRatio,
        latestIdleRatio: latestIdleRatio
      });
    }

    updatePanel(
      `Engagement: ${result.label}\n` +
      `Score: ${Number(result.score).toFixed(2)}\n\n` +
      `Support: ${result.support_message}\n\n` +
      `idle: ${features.idle_ratio.toFixed(2)}\n` +
      `speed: ${features.scroll_speed_px_s.toFixed(1)} px/s\n` +
      `depth: ${features.scroll_depth_ratio.toFixed(2)}\n` +
      `focusLoss: ${features.focus_loss_ratio.toFixed(2)}\n`
    );
  } catch (err) {
    updatePanel("ERROR calling /api/engagement\n\n" + String(err));
    console.error(err);
  }

  resetWindow();
}, WINDOW_SECONDS * 1000);

updatePanel(
  `Tracker Loaded ✅\n\n` +
  `storyId: ${storyId}\n` +
  `Wait ${WINDOW_SECONDS}s...\n`
);