(async function () {
  const avatarGrid = document.getElementById("avatarGrid");
  const bgGrid = document.getElementById("bgGrid");
  const selectedAvatar = document.getElementById("selectedAvatar");
  const toast = document.getElementById("avatarToast");

  // Sprite paths for each avatar and mood
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

  // Small message at bottom of page
  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
  }

  // Get correct image for avatar + mood
  function getAvatarImage(avatarName, mood = "engaged") {
    const avatar = avatarSprites[avatarName];

    // Default fallback image if avatar does not exist
    if (!avatar) {
      return "/static/avatars/default.png";
    }

    return avatar[mood] || avatar.engaged;
  }

  // Update preview image on the avatar page
  function updateSelectedAvatarPreview(avatarName, mood = "engaged") {
    if (!selectedAvatar) return;

    // If using an <img>
    if (selectedAvatar.tagName === "IMG") {
      selectedAvatar.src = getAvatarImage(avatarName, mood);
      selectedAvatar.alt = avatarName;
    }

    // Fallback if still using a div/text
    else {
      selectedAvatar.textContent = avatarName;
    }
  }

  // Avatar button click
  if (avatarGrid) {
    avatarGrid.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-avatar]");
      if (!btn) return;

      const avatar = btn.getAttribute("data-avatar");

      try {
        const res = await fetch("/api/select_avatar", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ avatar })
        });

        const data = await res.json();

        if (!data.ok) {
          showToast(data.error || "Avatar locked");
          return;
        }

        updateSelectedAvatarPreview(avatar);
        showToast("Avatar selected ✅");
      } catch (err) {
        console.error(err);
        showToast("Could not save avatar");
      }
    });
  }

  // Background button click
  if (bgGrid) {
    bgGrid.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-bg]");
      if (!btn) return;

      const bg = btn.getAttribute("data-bg");

      try {
        const res = await fetch("/api/select_bg", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ bg })
        });

        const data = await res.json();

        if (!data.ok) {
          showToast(data.error || "Background locked");
          return;
        }

        showToast("Background selected ✅ (go Home to see it)");
      } catch (err) {
        console.error(err);
        showToast("Could not save background");
      }
    });
  }

  // Load initial preview if page already knows selected avatar
  const currentAvatar = selectedAvatar?.getAttribute("data-current-avatar");

  if (currentAvatar) {
    updateSelectedAvatarPreview(currentAvatar);
  }
})();