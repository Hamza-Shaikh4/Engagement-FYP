async function loadStory() {
  const reader = document.getElementById("reader");
  reader.textContent = "Loading story...";

  try {
    const res = await fetch("/static/stories.json");
    const stories = await res.json();

    const storyId = window.STORY_ID || "book1";
    const story = stories.find(s => s.id === storyId);

    if (!story) {
      reader.textContent = `Story not found: ${storyId}`;
      return;
    }

    // Render title + paragraphs
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

loadStory();
