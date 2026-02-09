const revealTargets = document.querySelectorAll(".section, .hero, .card");

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("show");
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.2 }
);

revealTargets.forEach((el) => {
  el.classList.add("reveal");
  observer.observe(el);
});
