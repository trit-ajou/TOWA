(function () {
  const slideWidth = 1920;
  const slideHeight = 1080;
  const root = document.documentElement;
  const slides = Array.from(document.querySelectorAll(".slide"));
  const prevButton = document.getElementById("prevSlide");
  const nextButton = document.getElementById("nextSlide");
  const slideNumber = document.getElementById("slideNumber");
  const slideTotal = document.getElementById("slideTotal");
  let currentIndex = 0;

  function fitDeck() {
    const scale = Math.min(window.innerWidth / slideWidth, window.innerHeight / slideHeight);
    root.style.setProperty("--deck-scale", String(scale));
  }

  function indexFromHash() {
    const match = window.location.hash.match(/^#slide-(\d+)$/);
    if (!match) {
      return 0;
    }

    const index = Number(match[1]) - 1;
    if (!Number.isInteger(index) || index < 0 || index >= slides.length) {
      return 0;
    }

    return index;
  }

  function render(index, options = {}) {
    currentIndex = Math.max(0, Math.min(index, slides.length - 1));

    slides.forEach((slide, slideIndex) => {
      slide.classList.toggle("is-active", slideIndex === currentIndex);
      slide.setAttribute("aria-hidden", slideIndex === currentIndex ? "false" : "true");
    });

    slideNumber.textContent = String(currentIndex + 1);
    slideTotal.textContent = String(slides.length);
    document.title = `TOWA 발표자료 · ${currentIndex + 1}/${slides.length}`;

    if (!options.skipHash) {
      history.replaceState(null, "", `#slide-${currentIndex + 1}`);
    }
  }

  function move(delta) {
    render(currentIndex + delta);
  }

  function handleKeydown(event) {
    const key = event.key;

    if (key === "ArrowRight" || key === "PageDown" || key === " " || key === "Enter") {
      event.preventDefault();
      move(1);
      return;
    }

    if (key === "ArrowLeft" || key === "PageUp" || key === "Backspace") {
      event.preventDefault();
      move(-1);
      return;
    }

    if (key === "Home") {
      event.preventDefault();
      render(0);
      return;
    }

    if (key === "End") {
      event.preventDefault();
      render(slides.length - 1);
      return;
    }

    if (key.toLowerCase() === "f") {
      event.preventDefault();
      document.documentElement.requestFullscreen();
    }
  }

  prevButton.addEventListener("click", () => move(-1));
  nextButton.addEventListener("click", () => move(1));
  window.addEventListener("keydown", handleKeydown);
  window.addEventListener("resize", fitDeck);
  window.addEventListener("hashchange", () => render(indexFromHash(), { skipHash: true }));

  fitDeck();
  render(indexFromHash(), { skipHash: true });
})();
