document.addEventListener("DOMContentLoaded", () => {
  const toast = document.getElementById("lockedToast");
  const lockedCards = document.querySelectorAll("[data-locked='true'], .locked-btn");

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.style.display = "block";

    clearTimeout(window.__booksToastTimer);
    window.__booksToastTimer = setTimeout(() => {
      toast.style.display = "none";
    }, 2200);
  }

  lockedCards.forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      showToast("This stage is locked — finish the previous book first ✨");
    });
  });

  const currentNode = document.querySelector("[data-status='current'] .stage-node");
  if (currentNode) {
    currentNode.animate(
      [
        { transform: "translateY(0px)" },
        { transform: "translateY(-4px)" },
        { transform: "translateY(0px)" }
      ],
      {
        duration: 1600,
        iterations: Infinity
      }
    );
  }
});