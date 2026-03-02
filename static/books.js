(function () {
  const lockedCards = document.querySelectorAll(".card.locked[data-locked='true']");
  const toast = document.getElementById("lockedToast");

  lockedCards.forEach(card => {
    card.addEventListener("click", () => {
      if (!toast) return;
      toast.style.display = "block";
      clearTimeout(window.__toastTimer);
      window.__toastTimer = setTimeout(() => {
        toast.style.display = "none";
      }, 1800);
    });
  });
})();