(function () {
  const state = { cards: [], news: [] };
  const homeCardsGrid = document.getElementById('homeCardsGrid');
  const newsDesktopList = document.getElementById('newsDesktopList');
  const newsMobileStrip = document.getElementById('newsMobileStrip');

  const safe = (v) => String(v || '').replace(/[&<>\"]/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
  function toggleModal(id, show) { const node = document.getElementById(id); if (!node) return; node.classList.toggle('show', !!show); node.setAttribute('aria-hidden', show ? 'false' : 'true'); }
  window.toggleModal = toggleModal;

  function showToast(message) {
    const toast = document.getElementById('constructionToast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 1700);
  }

  function renderHomeCards() {
    if (!state.cards.length) return homeCardsGrid.innerHTML = '<p class="placeholder-text">No cards yet.</p>';
    homeCardsGrid.innerHTML = state.cards.map((card) => `<article class="home-info-card"><h4>${safe(card.title || `Card ${card.id}`)}</h4><p>${safe(card.body || 'No content yet.')}</p></article>`).join('');
  }

  function openNewsModal(post) {
    document.getElementById('newsModalTitle').textContent = post.title || 'Untitled';
    document.getElementById('newsModalMeta').textContent = `${post.date || ''} • ${post.author || 'Admin'}`;
    document.getElementById('newsModalBody').textContent = post.body || '';
    const img = document.getElementById('newsModalImage');
    if (post.image_filename) { img.src = `/Profile/${encodeURIComponent(post.image_filename)}`; img.style.display = 'block'; } else { img.style.display = 'none'; }
    toggleModal('newsReadModal', true);
  }

  function renderNewsDesktop() {
    if (!state.news.length) return newsDesktopList.innerHTML = '<p class="placeholder-text">No news posts yet.</p>';
    newsDesktopList.innerHTML = state.news.map((post) => `<article class="news-post-row"><div class="news-post-text-wrap"><h4 class="news-post-title">${safe(post.title || 'Untitled')}</h4><div class="news-post-date">${safe(post.date || '')}</div><p class="news-post-summary">${safe(post.summary || '')}</p><button type="button" class="read-more-btn" data-post-id="${safe(post.id)}">Read More</button></div></article>`).join('');
    newsDesktopList.querySelectorAll('.read-more-btn').forEach((btn) => btn.addEventListener('click', () => { const post = state.news.find((row) => String(row.id) === String(btn.dataset.postId)); if (post) openNewsModal(post); }));
  }

  function renderNewsMobile() {
    if (!state.news.length) return newsMobileStrip.innerHTML = '<p class="placeholder-text">No news posts yet.</p>';
    newsMobileStrip.innerHTML = state.news.map((post) => `<article class="mobile-news-card"><h4>${safe(post.title || 'Untitled')}</h4><p>${safe(post.summary || '')}</p><button class="btn btn-sm btn-light read-more-btn" data-post-id="${safe(post.id)}">Read More</button></article>`).join('');
    newsMobileStrip.querySelectorAll('.read-more-btn').forEach((btn) => btn.addEventListener('click', () => { const post = state.news.find((row) => String(row.id) === String(btn.dataset.postId)); if (post) openNewsModal(post); }));
  }

  async function loadLeaderboard() {
    const res = await fetch('/api/monthly_leaderboard');
    const data = await res.json();
    const borrowers = data.top_borrowers || [];
    const books = data.top_books || [];
    document.getElementById('landingTopBorrowers').innerHTML = borrowers.length ? borrowers.map((r, i) => `<div class="leader-row"><span>#${r.rank || i + 1} ${safe(r.name || r.school_id)}</span><strong>${r.total_borrowed}</strong></div>`).join('') : '<p class="placeholder-text">No borrower data.</p>';
    document.getElementById('landingTopBooks').innerHTML = books.length ? books.map((r, i) => `<div class="leader-row"><span>#${r.rank || i + 1} ${safe(r.title || r.book_no)}</span><strong>${r.total_borrowed}</strong></div>`).join('') : '<p class="placeholder-text">No book data.</p>';
  }

  async function submitLandingLogin(isAdmin) {
    const sId = document.getElementById(isAdmin ? 'adminSchoolId' : 'userSchoolId')?.value?.trim();
    if (!sId) return showToast('Enter school ID.');

    if (isAdmin) {
      const pwd = document.getElementById('adminPassword')?.value || '';
      if (!pwd) return showToast('Enter password.');
      const res = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ school_id: sId, password: pwd }) });
      const data = await res.json();
      if (!data.success) return showToast(data.message || 'Login failed.');
      if (!data.profile?.is_staff) return showToast('This account is not an admin account.');
      window.location.href = '/admin';
      return;
    }

    const res = await fetch('/api/verify_id', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ school_id: sId }) });
    const data = await res.json();
    if (!data.success) return showToast(data.message || 'Verification failed.');
    localStorage.setItem('bookPageAuth', JSON.stringify({ token: data.token, profile: data.profile }));
    toggleModal('userLoginModal', false);
    showToast('ID verified. You can now reserve from Books page.');
    window.location.href = '/books';
  }
  window.submitLandingLogin = submitLandingLogin;

  async function loadLandingContent() {
    const [cardRes, newsRes] = await Promise.all([fetch('/api/home_cards'), fetch('/api/news_posts')]);
    state.cards = await cardRes.json();
    state.news = await newsRes.json();
    renderHomeCards(); renderNewsDesktop(); renderNewsMobile(); loadLeaderboard();
  }

  window.openAboutModal = () => document.getElementById('aboutModalBackdrop')?.classList.add('active');
  window.closeAboutModal = () => document.getElementById('aboutModalBackdrop')?.classList.remove('active');

  document.querySelectorAll('[data-close]').forEach((btn) => btn.addEventListener('click', () => toggleModal(btn.dataset.close, false)));
  document.getElementById('newsReadModal')?.addEventListener('click', (e) => { if (e.target.id === 'newsReadModal') toggleModal('newsReadModal', false); });
  loadLandingContent();
})();
