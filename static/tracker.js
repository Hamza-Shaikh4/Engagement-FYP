// static/tracker.js

const WINDOW_SECONDS = 10;
const IDLE_THRESHOLD_MS = 3000;

let windowStartMs = Date.now();

let totalScrollPx = 0;
let interactionCount = 0;
let navigationCount = 0;

let lastActivityMs = Date.now();
let idleSamples = 0;
let totalSamples = 0;

let lastScrollY = window.scrollY;

function markActivity() {
  lastActivityMs = Date.now();
}

// ---- events ----
window.addEventListener("scroll", () => {
  const y = window.scrollY;
  totalScrollPx += Math.abs(y - lastScrollY);
  lastScrollY = y;
  markActivity();
}, { passive: true });

window.addEventListener("click", (e) => {
  interactionCount++;
  markActivity();

  // Count link clicks as "navigation"
  if (e.target.closest("a")) {
    navigationCount++;
  }
});

window.addEventListener("keydown", () => {
  interactionCount++;
  markActivity();
});

window.addEventListener("mousemove", () => {
  markActivity();
});

// ---- idle sampler (4x per second) ----
setInterval(() => {
  totalSamples++;
  const idleNow = (Date.now() - lastActivityMs) >= IDLE_THRESHOLD_MS;
  if (idleNow) idleSamples++;
}, 250);

// ---- simple UI badge ----
function getBadge() {
  let badge = document.getElementById("engagementBadge");
  if (!badge) {
    badge = document.createElement("div");
    badge.id = "engagementBadge";
    badge.style.position = "fixed";
    badge.style.bottom = "12px";
    badge.style.right = "12px";
    badge.style.padding = "10px 12px";
    badge.style.borderRadius = "10px";
    badge.style.background = "#111";
    badge.style.color = "#fff";
    badge.style.fontFamily = "system-ui, Arial";
    badge.style.fontSize = "14px";
    badge.style.zIndex = "9999";
    document.body.appendChild(badge);
  }
  return badge;
}

function resetWindow() {
  windowStartMs = Date.now();
  totalScrollPx = 0;
  interactionCount = 0;
  navigationCount = 0;
  idleSamples = 0;
  totalSamples = 0;
}

// ---- every 10 seconds: compute features and call backend ----
setInterval(async () => {
  const now = Date.now();
  const elapsedSeconds = (now - windowStartMs) / 1000;
  const safeSeconds = Math.max(1, elapsedSeconds);

  const idle_ratio = totalSamples === 0 ? 0 : idleSamples / totalSamples;
  const scroll_speed_px_s = totalScrollPx / safeSeconds;
  const nav_rate_per_min = (navigationCount / safeSeconds) * 60;
  const interaction_rate_per_min = (interactionCount / safeSeconds) * 60;

  const payload = {
    idle_ratio,
    scroll_speed_px_s,
    nav_rate_per_min,
    interaction_rate_per_min
  };

  try {
    const res = await fetch("/api/engagement", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const result = await res.json();

    const badge = getBadge();
    badge.textContent =
      `Engagement: ${result.label} (${Number(result.score).toFixed(2)})`;

    console.log("Features sent:", payload, "Result:", result);
  } catch (err) {
    console.error("Engagement API error:", err);
  }

  resetWindow();
}, WINDOW_SECONDS * 1000);
