(function () {
  const state = { cards: [], news: [], books: [], auth: null };

  const homeCardsGrid = document.getElementById('homeCardsGrid');
  const newsDesktopList = document.getElementById('newsDesktopList');
  const newsMobileStrip = document.getElementById('newsMobileStrip');
  const newsReadModal = document.getElementById('newsReadModal');
  const imageLightboxModal = document.getElementById('imageLightboxModal');

  let aboutModalEscHandler = null;

  function openAboutModal() {
    const backdrop = document.getElementById('aboutModalBackdrop');
    if (!backdrop) return;
    backdrop.classList.add('active');
    backdrop.setAttribute('aria-hidden', 'false');
    if (!aboutModalEscHandler) {
      aboutModalEscHandler = function (event) {
        if (event.key === 'Escape') closeAboutModal();
      };
    }
    document.addEventListener('keydown', aboutModalEscHandler);
  }

  function closeAboutModal() {
    const backdrop = document.getElementById('aboutModalBackdrop');
    if (!backdrop) return;
    backdrop.classList.remove('active');
    backdrop.setAttribute('aria-hidden', 'true');
    if (aboutModalEscHandler) document.removeEventListener('keydown', aboutModalEscHandler);
  }

  window.openAboutModal = openAboutModal;
  window.closeAboutModal = closeAboutModal;

  function safe(v) {
    return String(v || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function toggleModal(id, show) {
    const node = document.getElementById(id);
    if (!node) return;
    node.classList.toggle('show', !!show);
    node.setAttribute('aria-hidden', show ? 'false' : 'true');
    document.body.style.overflow = show ? 'hidden' : '';
  }
  window.toggleModal = toggleModal;

  function showToast(message) {
    const toast = document.getElementById('constructionToast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 1700);
  }

  function truncate(text, max = 110) {
    const raw = String(text || '').trim();
    return raw.length > max ? `${raw.slice(0, max - 1)}…` : raw;
  }

  function renderHomeCards() {
    if (!homeCardsGrid) return;
    if (!state.cards.length) {
      homeCardsGrid.innerHTML = '<p class="placeholder-text">No cards yet.</p>';
      return;
    }

    homeCardsGrid.innerHTML = state.cards.map((card) => {
      const title = String(card.title || '').trim();
      const body = String(card.body || '').trim();
      const empty = !title && !body;
      return `<article class="home-info-card ${empty ? 'placeholder' : ''}"><h4>${safe(title || `Card ${card.id}`)}</h4><p>${safe(body || 'No content yet. Admin can update this card from dashboard.')}</p></article>`;
    }).join('');
  }

  function openNewsModal(post) {
    document.getElementById('newsModalTitle').textContent = post.title || 'Untitled';
    document.getElementById('newsModalMeta').textContent = `${post.date || ''} • ${post.author || 'Admin'}`;
    document.getElementById('newsModalBody').textContent = post.body || '';

    const img = document.getElementById('newsModalImage');
    if (post.image_filename) {
      img.src = `/Profile/${encodeURIComponent(post.image_filename)}`;
      img.style.display = 'block';
      img.onclick = () => {
        const lightbox = document.getElementById('lightboxImage');
        lightbox.src = img.src;
        toggleModal('imageLightboxModal', true);
      };
    } else {
      img.removeAttribute('src');
      img.style.display = 'none';
      img.onclick = null;
    }

    toggleModal('newsReadModal', true);
  }

  function renderNewsDesktop() { /* unchanged behavior */
    if (!newsDesktopList) return;
    if (!state.news.length) {
      newsDesktopList.innerHTML = '<p class="placeholder-text">No news posts yet.</p>';
      return;
    }
    newsDesktopList.innerHTML = state.news.map((post, idx) => {
      const hasImage = !!post.image_filename;
      const imageMarkup = hasImage ? `<div class="news-post-image-wrap"><img class="news-post-image" src="/Profile/${encodeURIComponent(post.image_filename)}" alt="${safe(post.title)}"></div>` : '';
      const textMarkup = `<div class="news-post-text-wrap"><h4 class="news-post-title">${safe(post.title || 'Untitled')}</h4><div class="news-post-date">${safe(post.date || '')}</div><p class="news-post-summary">${safe(post.summary || '')}</p><button type="button" class="read-more-btn" data-post-id="${safe(post.id)}">Read More</button></div>`;
      if (!hasImage) return `<article class="news-post-row no-image">${textMarkup}</article>`;
      return idx % 2 === 0 ? `<article class="news-post-row">${imageMarkup}${textMarkup}</article>` : `<article class="news-post-row">${textMarkup}${imageMarkup}</article>`;
    }).join('');
    newsDesktopList.querySelectorAll('.read-more-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const post = state.news.find((row) => String(row.id) === String(btn.dataset.postId));
        if (post) openNewsModal(post);
      });
    });
  }

  function renderNewsMobile() {
    if (!newsMobileStrip) return;
    if (!state.news.length) {
      newsMobileStrip.innerHTML = '<p class="placeholder-text">No news posts yet.</p>';
      return;
    }
    newsMobileStrip.innerHTML = state.news.map((post) => `<article class="news-mobile-card" data-post-id="${safe(post.id)}">${post.image_filename ? `<img class="news-mobile-thumb" src="/Profile/${encodeURIComponent(post.image_filename)}" alt="${safe(post.title)}">` : ''}<div class="news-mobile-title">${safe(post.title || 'Untitled')}</div><div class="news-mobile-date">${safe(post.date || '')}</div><p class="news-mobile-summary">${safe(truncate(post.summary || ''))}</p></article>`).join('');
    newsMobileStrip.querySelectorAll('.news-mobile-card').forEach((card) => {
      card.addEventListener('click', () => {
        const post = state.news.find((row) => String(row.id) === String(card.dataset.postId));
        if (post) openNewsModal(post);
      });
    });
  }

  function renderCatalog() {
    const tbody = document.querySelector('#catalogBooksTable tbody');
    if (!tbody) return;
    tbody.innerHTML = state.books.map((book) => {
      const canReserve = String(book.status || '').toLowerCase() === 'available';
      return `<tr><td>${safe(book.book_no)}</td><td>${safe(book.title)}</td><td>${safe(book.author)}</td><td>${safe(book.category)}</td><td>${safe(book.status || 'Available')}</td><td><button class="btn btn-sm btn-outline-light reserve-btn" data-book="${safe(book.book_no)}" ${canReserve ? '' : 'disabled'}>Reserve</button></td></tr>`;
    }).join('') || '<tr><td colspan="6" class="text-center">No books yet.</td></tr>';

    tbody.querySelectorAll('.reserve-btn').forEach((btn) => {
      btn.addEventListener('click', () => handleReserve(btn.dataset.book));
    });
  }

  function getStoredAuth() {
    try { return JSON.parse(localStorage.getItem('landingAuth') || 'null'); } catch { return null; }
  }

  async function submitLandingLogin(isAdmin) {
    const sId = document.getElementById(isAdmin ? 'adminSchoolId' : 'userSchoolId')?.value?.trim();
    const pwd = document.getElementById(isAdmin ? 'adminPassword' : 'userPassword')?.value || '';
    if (!sId || !pwd) return showToast('Enter ID and password.');
    const res = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ school_id: sId, password: pwd }) });
    const data = await res.json();
    if (!data.success) return showToast(data.message || 'Login failed.');
    if (isAdmin && !data.profile?.is_staff) return showToast('This account is not an admin account.');

    state.auth = { token: data.token, profile: data.profile };
    localStorage.setItem('landingAuth', JSON.stringify(state.auth));
    toggleModal(isAdmin ? 'adminLoginModal' : 'userLoginModal', false);
    showToast(`Welcome, ${data.profile?.name || 'User'}!`);
    if (isAdmin) window.location.href = '/admin';
  }
  window.submitLandingLogin = submitLandingLogin;

  async function handleReserve(bookNo) {
    state.auth = state.auth || getStoredAuth();
    if (!state.auth?.token || !state.auth?.profile?.school_id) {
      showToast('To reserve a book, please log in first.');
      toggleModal('userLoginModal', true);
      return;
    }

    const body = {
      book_no: bookNo,
      school_id: state.auth.profile.school_id,
      borrower_name: state.auth.profile.name,
      pickup_schedule: new Date(Date.now() + 86400000).toISOString().slice(0, 10),
      phone_number: state.auth.profile.phone_number || ''
    };

    const res = await fetch('/api/reserve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: state.auth.token },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    showToast(data.message || (data.success ? 'Reserved.' : 'Reservation failed.'));
    if (data.success) loadLandingContent();
  }

  async function loadLandingContent() {
    try {
      const [cardRes, newsRes, booksRes] = await Promise.all([fetch('/api/home_cards'), fetch('/api/news_posts'), fetch('/api/books')]);
      state.cards = await cardRes.json();
      state.news = await newsRes.json();
      state.books = await booksRes.json();
      renderHomeCards();
      renderNewsDesktop();
      renderNewsMobile();
      renderCatalog();
    } catch (error) {
      console.error(error);
    }
  }

  document.querySelectorAll('[data-close]').forEach((btn) => btn.addEventListener('click', () => toggleModal(btn.dataset.close, false)));
  newsReadModal?.addEventListener('click', (e) => { if (e.target === newsReadModal) toggleModal('newsReadModal', false); });
  imageLightboxModal?.addEventListener('click', (e) => { if (e.target === imageLightboxModal) toggleModal('imageLightboxModal', false); });

  state.auth = getStoredAuth();
  loadLandingContent();

  document.addEventListener('DOMContentLoaded', function () {
    const footer = document.querySelector('footer');
    const trigger = document.getElementById('aboutTriggerBtn');
    if (!footer || !trigger || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => trigger.classList.toggle('footer-overlap', entry.isIntersecting)), { threshold: 0.1 });
    observer.observe(footer);
  });
})();
