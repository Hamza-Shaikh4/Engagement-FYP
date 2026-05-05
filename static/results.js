// This file fills the xp bar on the quests page.

(async function () {
  async function loadState() {
    const res = await fetch("/api/state");
    if (!res.ok) throw new Error("Failed to load /api/state");
    return await res.json();
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function renderAchievements(list) {
    const container = document.getElementById("achievementsList");
    if (!container) return;

    container.innerHTML = "";

    if (!list || list.length === 0) {
      const div = document.createElement("div");
      div.className = "muted";
      div.style.fontWeight = "900";
      div.textContent = "No achievements yet — finish a book to earn your first ⭐";
      container.appendChild(div);
      return;
    }

    list.forEach(a => {
      const chip = document.createElement("div");
      chip.className = "chip";
      chip.style.display = "inline-flex";
      chip.style.alignItems = "center";
      chip.style.gap = "8px";
      chip.textContent = `🏅 ${a}`;
      container.appendChild(chip);
    });
  }

  function renderXP(xp) {
    setText("xpText", String(xp));

    const xpBar = document.getElementById("xpBar");
    if (xpBar) {
      const pct = Math.max(0, Math.min(100, xp % 100));
      xpBar.style.width = pct + "%";
    }
  }

  try {
    const data = await loadState();
    const st = data.state;

    setText("booksCompleted", String((st.completed_books || []).length));
    setText("streak", `${st.streak} 🔥`);
    setText("level", String(st.level));
    setText("activeAvatar", st.selected_avatar);

    renderXP(st.xp);
    renderAchievements(st.achievements);

    const label = st.last_engagement_label || "neutral";
    const score = typeof st.last_engagement_score === "number" ? st.last_engagement_score : 0.5;
    setText("engagementLine", `${label} (${score.toFixed(2)})`);
    setText("supportLine", st.last_support_message || "Ready to read?");

  } catch (err) {
    console.error(err);
    alert("Results page failed to load state. Check Console (F12).");
  }
})();