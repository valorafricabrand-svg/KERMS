document.addEventListener("DOMContentLoaded", () => {
  const carousel = document.querySelector(".site-workflow-carousel");
  if (!carousel) return;

  const viewport = carousel.querySelector(".site-workflow-viewport");
  const cards = Array.from(carousel.querySelectorAll(".site-workflow-card"));
  const previous = carousel.querySelector("[data-workflow-prev]");
  const next = carousel.querySelector("[data-workflow-next]");
  const currentLabel = carousel.querySelector("[data-workflow-current]");
  const progress = carousel.querySelector("[data-workflow-progress]");
  let resizeFrame = null;
  let scrollTimer = null;

  function visibleCount() {
    const styles = getComputedStyle(carousel);
    return Number(styles.getPropertyValue("--workflow-visible").trim()) || 1;
  }

  function maxIndex() {
    return Math.max(0, cards.length - visibleCount());
  }

  function stepSize() {
    const gap = Number.parseFloat(getComputedStyle(cards[0].parentElement).columnGap) || 0;
    return cards[0].getBoundingClientRect().width + gap;
  }

  function updateControls() {
    const cardStep = stepSize();
    const index = Math.min(maxIndex(), Math.max(0, Math.round(viewport.scrollLeft / cardStep)));
    const visible = visibleCount();
    const end = Math.min(cards.length, index + visible);

    currentLabel.textContent = `${String(index + 1).padStart(2, "0")}–${String(end).padStart(2, "0")}`;
    progress.style.width = `${(end / cards.length) * 100}%`;
    previous.disabled = index === 0;
    next.disabled = index >= maxIndex();
  }

  function move(direction) {
    const cardStep = stepSize();
    const index = Math.min(maxIndex(), Math.max(0, Math.round(viewport.scrollLeft / cardStep)));
    const target = Math.min(maxIndex(), Math.max(0, index + direction));
    viewport.scrollTo({
      left: target * cardStep,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  }

  previous.addEventListener("click", () => move(-1));
  next.addEventListener("click", () => move(1));
  viewport.addEventListener("scroll", () => {
    window.clearTimeout(scrollTimer);
    scrollTimer = window.setTimeout(updateControls, 80);
  }, { passive: true });

  carousel.addEventListener("keydown", event => {
    if (event.target.closest("button, a")) return;
    if (event.key === "ArrowRight") {
      event.preventDefault();
      move(1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      move(-1);
    }
  });

  window.addEventListener("resize", () => {
    window.cancelAnimationFrame(resizeFrame);
    resizeFrame = window.requestAnimationFrame(() => {
      const cardStep = stepSize();
      const index = Math.min(maxIndex(), Math.max(0, Math.round(viewport.scrollLeft / cardStep)));
      viewport.scrollLeft = index * cardStep;
      updateControls();
    });
  });

  updateControls();
});
