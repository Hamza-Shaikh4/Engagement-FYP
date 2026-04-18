let readingStartTime = Date.now();
let latestTrackerResult = {
  disengagedWindows: 0,
  latestFocusLoss: 0,
  latestIdleRatio: 0
};

let lastBuddyMessageAt = 0;
const BUDDY_SUPPORT_COOLDOWN_MS = 6000;

const LOW_ENGAGEMENT_LINES = [
  "Try one more paragraph.",
  "Take it slowly.",
  "Focus on this page.",
  "Keep going — read carefully.",
  "You’re doing fine. Keep reading."
];

function showCalibrationModal() {
  const modal = document.getElementById("calibrationModal");
  if (modal) {
    modal.classList.remove("hidden");
    modal.classList.add("show");
  }
}

function hideCalibrationModal() {
  const modal = document.getElementById("calibrationModal");
  if (modal) {
    modal.classList.remove("show");
    modal.classList.add("hidden");
  }
}

async function submitCalibrationResponse(selfReport) {
  const storyId = window.STORY_ID || "book1";

  const res = await fetch("/api/calibration_response", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      story_id: storyId,
      self_report: selfReport
    })
  });

  const data = await res.json();

  if (!data.ok) {
    alert(data.error || "Could not save calibration response.");
    return;
  }

  hideCalibrationModal();

  if (data.needs_quiz) {
    window.location.href = data.quiz_url;
    return;
  }

  window.location.href = "/books?celebrate=1";
}

async function startReadingSession() {
  await fetch("/api/start_reading", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ story_id: window.STORY_ID })
  });
}

async function loadStory() {
  const reader = document.getElementById("reader");
  reader.textContent = "Loading story...";

  try {
    const res = await fetch("/api/stories");
    const stories = await res.json();

    const storyId = window.STORY_ID || "book1";
    const story = stories.find(s => s.id === storyId);

    if (!story) {
      reader.textContent = `Story not found: ${storyId}`;
      return;
    }

    reader.innerHTML = "";

    const title = document.createElement("h2");
    title.textContent = story.title;
    reader.appendChild(title);

    const paragraphs = story.text.split("\n\n");
    paragraphs.forEach(p => {
      const para = document.createElement("p");
      para.textContent = p;
      reader.appendChild(para);
    });

  } catch (err) {
    console.error(err);
    reader.textContent = "Failed to load story. Open Console (F12) for details.";
  }
}

function showBuddySupport(message) {
  const box = document.getElementById("buddySupport");
  const text = document.getElementById("buddySupportText");

  if (!box || !text) return;

  text.textContent = message;
  box.classList.remove("hidden");
  box.classList.add("show");
}

function hideBuddySupport() {
  const box = document.getElementById("buddySupport");
  if (!box) return;

  box.classList.remove("show");
  box.classList.add("hidden");
}

function pickLowEngagementLine() {
  const index = Math.floor(Math.random() * LOW_ENGAGEMENT_LINES.length);
  return LOW_ENGAGEMENT_LINES[index];
}

window.onEngagementFeedback = function (result) {
  const now = Date.now();
  const score = Number(result.score || 0);

  if (score <= 0.30 || result.label === "disengaged") {
    if ((now - lastBuddyMessageAt) >= BUDDY_SUPPORT_COOLDOWN_MS) {
      showBuddySupport(pickLowEngagementLine());
      lastBuddyMessageAt = now;
    }
  } else {
    hideBuddySupport();
  }
};

async function finishBook() {
  window.__TRACKING_PAUSED__ = true;

  const storyId = window.STORY_ID || "book1";
  const readingTime = (Date.now() - readingStartTime) / 1000;

  const reader = document.getElementById("reader");
  let scrollDepth = 0;

  if (reader) {
    const maxScroll = Math.max(1, reader.scrollHeight - reader.clientHeight);
    scrollDepth = Math.min(1, reader.scrollTop / maxScroll);
  }

  const res = await fetch("/api/complete_book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      story_id: storyId,
      reading_time: readingTime,
      scroll_depth: scrollDepth,
      disengaged_windows: latestTrackerResult.disengagedWindows,
      focus_loss_ratio: latestTrackerResult.latestFocusLoss,
      idle_ratio: latestTrackerResult.latestIdleRatio
    })
  });

  const data = await res.json();

  if (!data.ok) {
    alert(data.error || "Could not finish book");
    window.__TRACKING_PAUSED__ = false;
    return;
  }

  if (data.calibration_required) {
    showCalibrationModal();
    return;
  }

  if (data.needs_quiz) {
    window.location.href = data.quiz_url;
    return;
  }

  window.location.href = "/books?celebrate=1";
}

window.setLatestTrackerResult = function (result) {
  latestTrackerResult = result;
};

document.addEventListener("DOMContentLoaded", async () => {
  await startReadingSession();
  await loadStory();

  const finishBtn = document.getElementById("finishReadingBtn");
  if (finishBtn) {
    finishBtn.addEventListener("click", finishBook);
  }

  const calibrationButtons = document.querySelectorAll("[data-calibration-response]");
  calibrationButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const response = button.getAttribute("data-calibration-response");
      await submitCalibrationResponse(response);
    });
  });
});