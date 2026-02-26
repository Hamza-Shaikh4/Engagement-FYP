// =======================================
// tracker.js (with scroll depth + focus loss)
// =======================================

// -------- SETTINGS ----------
const WINDOW_SECONDS = 10;
const IDLE_THRESHOLD_MS = 12000; // reading pauses are normal

// -------- STORY DETECTION ----------
const storyId = String(window.STORY_ID || "").trim();
const isCalibrationBook = (storyId === "1");

// -------- READER ELEMENT (your app scrolls inside this) ----------
const reader = document.getElementById("reader");
const hasReader = Boolean(reader);

// -------- WINDOW VARIABLES ----------
let windowStartMs = Date.now();

let totalScrollPx = 0;
let interactionCount = 0;
let navigationCount = 0;

let lastActivityMs = Date.now();
let idleSamples = 0;
let totalSamples = 0;

// Track scroll position on the correct element
let lastScrollPos = hasReader ? reader.scrollTop : window.scrollY;

// NEW: track max scroll position reached in this window (for depth)
let maxScrollPosThisWindow = hasReader ? reader.scrollTop : window.scrollY;

// NEW: track how long tab was hidden during this window
let hiddenStartMs = null;
let hiddenMsThisWindow = 0;

// -------- CALIBRATION STORAGE ----------
let calibrationWindows = [];
let calibrationFinished = false;

// -------- DEBUG PANEL ----------
function createPanel() {
  let panel = document.getElementById("trackerPanel");
  if (panel) return panel;

  panel = document.createElement("div");
  panel.id = "trackerPanel";
  panel.style.position = "fixed";
  panel.style.top = "12px";
  panel.style.right = "12px";
  panel.style.background = "#111";
  panel.style.color = "#fff";
  panel.style.padding = "12px";
  panel.style.borderRadius = "12px";
  panel.style.fontFamily = "system-ui, Arial";
  panel.style.fontSize = "13px";
  panel.style.whiteSpace = "pre-line";
  panel.style.zIndex = "9999";
  panel.style.width = "380px";
  document.body.appendChild(panel);

  return panel;
}

function updatePanel(text) {
  createPanel().textContent = text;
}

// -------- ACTIVITY ----------
function markActivity() {
  lastActivityMs = Date.now();
}

// -------- FOCUS LOSS (TAB SWITCH) ----------
// This is the best signal for "user left the page".
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    // tab became hidden
    hiddenStartMs = Date.now();
  } else {
    // tab became visible again
    if (hiddenStartMs !== null) {
      hiddenMsThisWindow += (Date.now() - hiddenStartMs);
      hiddenStartMs = null;
    }
  }
});

// -------- SCROLL TRACKING (INSIDE #reader) ----------
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

// -------- INTERACTION ----------
window.addEventListener("click", (e) => {
  interactionCount++;
  markActivity();
  if (e.target.closest("a")) navigationCount++;
});

window.addEventListener("keydown", () => {
  interactionCount++;
  markActivity();
});

window.addEventListener("mousemove", markActivity);

// -------- IDLE SAMPLER ----------
setInterval(() => {
  totalSamples++;
  if ((Date.now() - lastActivityMs) >= IDLE_THRESHOLD_MS) {
    idleSamples++;
  }
}, 250);

// -------- RESET WINDOW ----------
function resetWindow() {
  windowStartMs = Date.now();

  totalScrollPx = 0;
  interactionCount = 0;
  navigationCount = 0;

  idleSamples = 0;
  totalSamples = 0;

  maxScrollPosThisWindow = hasReader ? reader.scrollTop : window.scrollY;

  // If tab is currently hidden, carry start time forward (don’t lose it)
  hiddenMsThisWindow = 0;
}

// -------- CALCULATE FEATURES ----------
function calculateFeatures() {
  const now = Date.now();
  const elapsedSeconds = (now - windowStartMs) / 1000;
  const safeSeconds = Math.max(1, elapsedSeconds);

  // If the tab is hidden right now, include "hidden so far" in this window’s total
  let hiddenMsTotal = hiddenMsThisWindow;
  if (document.hidden && hiddenStartMs !== null) {
    hiddenMsTotal += (now - hiddenStartMs);
  }

  const idle_ratio = totalSamples === 0 ? 0 : idleSamples / totalSamples;
  const scroll_speed_px_s = totalScrollPx / safeSeconds;
  const nav_rate_per_min = (navigationCount / safeSeconds) * 60;
  const interaction_rate_per_min = (interactionCount / safeSeconds) * 60;

  // Scroll depth ratio:
  // how far through the scrollable content we got (0..1)
  let scroll_depth_ratio = 0;
  if (hasReader) {
    const maxScrollPossible = Math.max(1, reader.scrollHeight - reader.clientHeight);
    scroll_depth_ratio = Math.min(1, maxScrollPosThisWindow / maxScrollPossible);
  } else {
    const maxScrollPossible = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    scroll_depth_ratio = Math.min(1, maxScrollPosThisWindow / maxScrollPossible);
  }

  // Focus loss ratio:
  // fraction of this window spent hidden (0..1)
  const focus_loss_ratio = Math.min(1, hiddenMsTotal / (safeSeconds * 1000));

  return {
    idle_ratio,
    scroll_speed_px_s,
    scroll_depth_ratio,
    focus_loss_ratio,
    nav_rate_per_min,
    interaction_rate_per_min
  };
}

// -------- MAIN LOOP ----------
setInterval(async () => {
  const features = calculateFeatures();

  console.table({
    storyId,
    mode: isCalibrationBook ? "CALIBRATION" : "NORMAL",
    ...Object.fromEntries(Object.entries(features).map(([k,v]) => [k, Number(v).toFixed(3)]))
  });

  // ==========================
  // CALIBRATION MODE (BOOK 1)
  // ==========================
  if (isCalibrationBook && !calibrationFinished) {
    calibrationWindows.push({ ...features, ts_ms: Date.now() });

    updatePanel(
      `MODE: CALIBRATION (Book 1)\n\n` +
      `windows collected: ${calibrationWindows.length}\n\n` +
      `idle_ratio: ${features.idle_ratio.toFixed(2)}\n` +
      `scroll_speed_px_s: ${features.scroll_speed_px_s.toFixed(2)}\n` +
      `scroll_depth_ratio: ${features.scroll_depth_ratio.toFixed(2)}\n` +
      `focus_loss_ratio: ${features.focus_loss_ratio.toFixed(2)}\n` +
      `nav_rate_per_min: ${features.nav_rate_per_min.toFixed(2)}\n` +
      `interaction_rate_per_min: ${features.interaction_rate_per_min.toFixed(2)}\n\n` +
      `Tip: switch tabs to test focus_loss_ratio.\n` +
      `Click Continue when finished.`
    );

    resetWindow();
    return;
  }

  // ==========================
  // NORMAL MODE (OTHER BOOKS)
  // ==========================
  if (!isCalibrationBook) {
    try {
      // Only send the 4 features your current Python fuzzy uses
      // (we keep the extra ones visible for now)
      const payloadForFuzzy = {
        idle_ratio: features.idle_ratio,
        scroll_speed_px_s: features.scroll_speed_px_s,
        nav_rate_per_min: features.nav_rate_per_min,
        interaction_rate_per_min: features.interaction_rate_per_min
      };

      const res = await fetch("/api/engagement", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payloadForFuzzy)
      });

      const result = await res.json();

      updatePanel(
        `MODE: NORMAL\n\n` +
        `Engagement: ${result.label}\n` +
        `Score: ${Number(result.score).toFixed(2)}\n\n` +
        `idle_ratio: ${features.idle_ratio.toFixed(2)}\n` +
        `scroll_speed_px_s: ${features.scroll_speed_px_s.toFixed(2)}\n` +
        `scroll_depth_ratio: ${features.scroll_depth_ratio.toFixed(2)}\n` +
        `focus_loss_ratio: ${features.focus_loss_ratio.toFixed(2)}\n` +
        `nav_rate_per_min: ${features.nav_rate_per_min.toFixed(2)}\n` +
        `interaction_rate_per_min: ${features.interaction_rate_per_min.toFixed(2)}`
      );
    } catch (err) {
      updatePanel("ERROR calling /api/engagement\n\n" + String(err));
      console.error(err);
    }
  }

  resetWindow();
}, WINDOW_SECONDS * 1000);

// -------- CONTINUE BUTTON (END CALIBRATION) ----------
const finishBtn = document.getElementById("finishReadingBtn");

if (finishBtn) {
  finishBtn.addEventListener("click", () => {
    if (!isCalibrationBook) return;
    if (calibrationFinished) return;

    const selfReport = confirm(
      "Calibration question:\n\nDid you feel engaged while reading?\n\nOK = Yes\nCancel = No"
    );

    calibrationFinished = true;

    const calibrationData = {
      story_id: storyId,
      self_report_engaged: selfReport,
      windows: calibrationWindows,
      created_at: Date.now()
    };

    localStorage.setItem("calibration_data", JSON.stringify(calibrationData));

    updatePanel(
      `CALIBRATION SAVED ✅\n\n` +
      `self_report_engaged: ${selfReport}\n` +
      `windows saved: ${calibrationWindows.length}\n\n` +
      `Saved to localStorage: calibration_data\n` +
      `Now open Book 2 to test normal mode.`
    );

    console.log("Calibration saved:", calibrationData);
  });
}

// -------- INITIAL MESSAGE ----------
updatePanel(
  `Tracker Loaded ✅\n\n` +
  `storyId: ${storyId}\n` +
  `mode: ${isCalibrationBook ? "CALIBRATION" : "NORMAL"}\n` +
  `scroll source: ${hasReader ? "#reader.scrollTop" : "window.scrollY"}\n\n` +
  `Wait ${WINDOW_SECONDS}s for first window...\n` +
  `Tip: switch tabs to test focus_loss_ratio.`
);
