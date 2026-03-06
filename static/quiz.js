let quizData = [];

async function loadQuiz() {
  const container = document.getElementById("quizContainer");
  const storyId = window.STORY_ID;

  const res = await fetch(`/api/quiz/${storyId}`);
  const data = await res.json();

  if (!data.ok) {
    container.textContent = data.error || "Could not load quiz.";
    return;
  }

  quizData = data.quiz || [];

  if (quizData.length === 0) {
    container.innerHTML = "<p>No quiz set for this story yet.</p>";
    return;
  }

  container.innerHTML = "";

  quizData.forEach((q, index) => {
    const block = document.createElement("div");
    block.style.marginBottom = "18px";

    const title = document.createElement("div");
    title.style.fontWeight = "800";
    title.style.marginBottom = "8px";
    title.textContent = `${index + 1}. ${q.question}`;
    block.appendChild(title);

    q.options.forEach((opt, optIndex) => {
      const label = document.createElement("label");
      label.style.display = "block";
      label.style.marginBottom = "6px";

      const input = document.createElement("input");
      input.type = "radio";
      input.name = `q${index}`;
      input.value = String(optIndex);

      label.appendChild(input);
      label.appendChild(document.createTextNode(" " + opt));
      block.appendChild(label);
    });

    container.appendChild(block);
  });
}

async function submitQuiz() {
  const storyId = window.STORY_ID;

  const answers = quizData.map((_, index) => {
    const checked = document.querySelector(`input[name="q${index}"]:checked`);
    return checked ? Number(checked.value) : -1;
  });

  const res = await fetch(`/api/quiz/${storyId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers })
  });

  const data = await res.json();

  if (!data.ok) {
    alert(data.error || "Could not submit quiz.");
    return;
  }

  if (data.passed) {
    alert(`Nice work! You scored ${data.score}/${data.total}. Book completed ✅`);
    window.location.href = "/books";
  } else {
    alert(`You scored ${data.score}/${data.total}. Try rereading the story and then come back.`);
    window.location.href = `/reading/${storyId}`;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await loadQuiz();

  const btn = document.getElementById("submitQuizBtn");
  if (btn) {
    btn.addEventListener("click", submitQuiz);
  }
});