(function () {
  const toast = document.getElementById('constructionToast');
  const constructionLinks = document.querySelectorAll('.construction-link');
  let toastTimer = null;

  function showConstructionToast() {
    if (!toast) return;
    toast.classList.add('show');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove('show');
    }, 1900);
  }

  constructionLinks.forEach((link) => {
    link.addEventListener('click', (event) => {
      showConstructionToast();
      const targetId = link.getAttribute('href');
      if (targetId && targetId.startsWith('#')) {
        const target = document.querySelector(targetId);
        if (target) {
          event.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  });
})();
