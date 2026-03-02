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
  const storyId = window.STORY_ID || "book1";

  const res = await fetch("/api/complete_book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ story_id: storyId })
  });

  const data = await res.json();
  if (!data.ok) {
    alert(data.error || "Could not finish book");
    return;
  }

  // Friendly reward popup
  const gained = 40;
  alert(`Nice work! ✅\n\n+${gained} XP\nHealth boosted ❤️\n\nNext content may be unlocked in the library!`);

  window.location.href = "/books";
}

loadStory();

const finishBtn = document.getElementById("finishReadingBtn");
if (finishBtn) {
  finishBtn.addEventListener("click", finishBook);
}