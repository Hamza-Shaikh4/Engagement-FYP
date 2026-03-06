let readingStartTime = Date.now();
let latestTrackerResult = {
  disengagedWindows: 0,
  latestFocusLoss: 0,
  latestIdleRatio: 0
};

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

  if (data.needs_quiz) {
    window.location.href = data.quiz_url;
    return;
  }

  alert("Nice work! ✅\n\n+40 XP\nHealth reset ❤️\n\nNext content may be unlocked in the library!");
  window.location.href = "/books";
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
});