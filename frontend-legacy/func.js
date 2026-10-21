document.addEventListener('DOMContentLoaded', () => {
  const numbers = document.querySelectorAll('.number');
  const container = document.querySelector('.container-statics');

  function countUp(el, target) {
    let current = 0;
    const duration = 1800; // ms
    const increment = target / (duration / 16);
    const interval = setInterval(() => {
      current += increment;
      if (current >= target) {
        current = target;
        clearInterval(interval);
      }
      el.textContent = '+' + Math.floor(current).toLocaleString();
    }, 16);
  }

  function resetNumbers() {
    numbers.forEach(el => { el.textContent = '+0'; });
  }

  if (!container || !numbers.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        numbers.forEach(el => {
          const target = parseInt(el.getAttribute('data-target'), 10);
          countUp(el, target);
        });
      } else {
        resetNumbers();
      }
    });
  }, { threshold: 0.4 });

  observer.observe(container);
});
