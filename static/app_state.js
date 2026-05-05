// This file updates shared page parts like the avatar, health bar, and main read button.

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
    // default theme
  }
})();

function updateAvatarUI(state) {
  const avatarBox = document.getElementById("hudAvatar");
  if (!avatarBox) return;

  const avatarName = state.selected_avatar || "defaultAvatar";
  const mood = state.last_engagement_label || "engaged";

  const avatarSprites = {
    defaultAvatar: {
      engaged: "/static/avatars/default.png",
      neutral: "/static/avatars/default.png",
      disengaged: "/static/avatars/default.png"
    },
    blueTrainer: {
      engaged: "/static/avatars/steven-gen6.png",
      neutral: "/static/avatars/steven-gen6.png",
      disengaged: "/static/avatars/steven.png"
    },
    blondeTrainer: {
      engaged: "/static/avatars/cynthia-gen4.png",
      neutral: "/static/avatars/cynthia-gen4.png",
      disengaged: "/static/avatars/cynthia.png"
    }
  };

  const avatar = avatarSprites[avatarName] || avatarSprites.defaultAvatar;
  const imagePath = avatar[mood] || avatar.engaged;

  avatarBox.innerHTML = `
    <img
      src="${imagePath}"
      alt="${avatarName}"
      class="hud-avatar-img"
    >
  `;
}



// ---------------------------------------
// UI HELPERS
// ---------------------------------------
function updateHealthUI(state) {
  const healthBar = document.getElementById("hudHealthBar");
  const healthText = document.getElementById("hudHealthText");

  if (healthBar && typeof state.health === "number") {
    healthBar.style.width = `${state.health}%`;
  }

  if (healthText && typeof state.health === "number") {
    healthText.textContent = `${state.health}%`;
  }
}

function updateReadButton(state, stories) {
  const readBtn = document.getElementById("readBtn");
  const readBtnTitle = document.getElementById("readBtnTitle");
  const readBtnSub = document.getElementById("readBtnSub");

  if (!readBtn || !readBtnTitle || !readBtnSub) return;

  const completed = state.completed_books || [];

  // No books completed yet
  if (completed.length === 0) {
    readBtn.href = "/reading/book1";
    readBtnTitle.textContent = "Start Reading";
    readBtnSub.textContent = "Begin your first story";
    return;
  }

  // Find next unread story
  const nextStory = stories.find(story => !completed.includes(story.id));

  if (nextStory) {
    readBtn.href = `/reading/${nextStory.id}`;
    readBtnTitle.textContent = "Continue Reading";
    readBtnSub.textContent = nextStory.title;
    return;
  }

  // All books completed
  readBtn.href = "/books";
  readBtnTitle.textContent = "Read Again";
  readBtnSub.textContent = "Replay your unlocked stories";
}


// ---------------------------------------
// LOAD STATE
// ---------------------------------------
async function loadAppState() {
  try {
    const res = await fetch("/api/state");
    const data = await res.json();

    // /api/state returns an object like:
    // { state: {...}, unlocks: {...}, stories: [...] }
    const state = data.state || {};
    const stories = data.stories || [];

    window.APP_STATE = data;

    updateAvatarUI(state);
    updateHealthUI(state);
    updateReadButton(state, stories);

  } catch (err) {
    console.error("Failed to load app state:", err);
  }
}


// ---------------------------------------
// INIT
// ---------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  loadAppState();
});
