(async function () {
  const avatarGrid = document.getElementById("avatarGrid");
  const bgGrid = document.getElementById("bgGrid");
  const selectedAvatar = document.getElementById("selectedAvatar");
  const toast = document.getElementById("avatarToast");

  function showToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
  }

  if (avatarGrid) {
    avatarGrid.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-avatar]");
      if (!btn) return;

      const avatar = btn.getAttribute("data-avatar");
      const res = await fetch("/api/select_avatar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ avatar })
      });
      const data = await res.json();

      if (!data.ok) {
        showToast(data.error || "Avatar locked");
        return;
      }

      selectedAvatar.textContent = avatar;
      showToast("Avatar selected ✅");
    });
  }

  if (bgGrid) {
    bgGrid.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-bg]");
      if (!btn) return;

      const bg = btn.getAttribute("data-bg");
      const res = await fetch("/api/select_bg", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bg })
      });
      const data = await res.json();

      if (!data.ok) {
        showToast(data.error || "Background locked");
        return;
      }

      showToast("Background selected ✅ (go Home to see it)");
    });
  }
})();