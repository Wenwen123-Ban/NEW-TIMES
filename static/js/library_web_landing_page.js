(function () {
  const state = { cards: [], news: [], books: [], auth: null, selectedBook: null, category: 'All', search: '' };

  const homeCardsGrid = document.getElementById('homeCardsGrid');
  const newsDesktopList = document.getElementById('newsDesktopList');
  const newsMobileStrip = document.getElementById('newsMobileStrip');
  const newsReadModal = document.getElementById('newsReadModal');
  const imageLightboxModal = document.getElementById('imageLightboxModal');
  const catalogSearchInput = document.getElementById('catalogSearchInput');
  const catalogCategoryPills = document.getElementById('catalogCategoryPills');
  const catalogResultCount = document.getElementById('catalogResultCount');
  const catalogBookGrid = document.getElementById('catalogBookGrid');

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

  function statusClass(status) {
    const key = String(status || 'Available').toLowerCase();
    if (key === 'borrowed') return 'status-borrowed';
    if (key === 'reserved') return 'status-reserved';
    return 'status-available';
  }

  function shuffle(list) {
    const cloned = [...list];
    for (let i = cloned.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [cloned[i], cloned[j]] = [cloned[j], cloned[i]];
    }
    return cloned;
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
    if (!catalogBookGrid) return;

    const categories = ['All', ...new Set(state.books.map((b) => String(b.category || 'General').trim()).filter(Boolean))];
    if (catalogCategoryPills) {
      catalogCategoryPills.innerHTML = categories.map((cat) => `<button class="catalog-pill ${state.category === cat ? 'active' : ''}" data-cat="${safe(cat)}">${safe(cat)}</button>`).join('');
      catalogCategoryPills.querySelectorAll('.catalog-pill').forEach((pill) => {
        pill.addEventListener('click', () => {
          state.category = pill.dataset.cat;
          renderCatalog();
        });
      });
    }

    const q = state.search.trim().toLowerCase();
    let filtered = state.books.filter((book) => {
      const passCategory = state.category === 'All' || String(book.category || 'General').trim() === state.category;
      const haystack = `${book.book_no || ''} ${book.title || ''} ${book.author || ''}`.toLowerCase();
      return passCategory && (!q || haystack.includes(q));
    });

    if (state.category === 'All') filtered = shuffle(filtered);

    if (catalogResultCount) catalogResultCount.textContent = `${filtered.length} result${filtered.length === 1 ? '' : 's'}`;

    catalogBookGrid.innerHTML = filtered.map((book) => `
      <article class="catalog-card" data-book-no="${safe(book.book_no)}">
        <span class="catalog-mini-pill">${safe(book.category || 'General')}</span>
        <h5 class="catalog-card-title">${safe(book.title || 'Untitled')}</h5>
        <p class="catalog-card-author">${safe(book.author || 'Unknown')}</p>
        <div><code>${safe(book.book_no)}</code></div>
        <span class="catalog-status-badge ${statusClass(book.status)}">${safe(book.status || 'Available')}</span>
      </article>
    `).join('') || '<p class="placeholder-text">No books found.</p>';

    catalogBookGrid.querySelectorAll('.catalog-card').forEach((card) => {
      card.addEventListener('click', () => {
        const book = state.books.find((row) => String(row.book_no) === String(card.dataset.bookNo));
        if (book) openReserveModal(book);
      });
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

    const pickupDate = document.getElementById('reservePickupDate')?.value?.trim();
    const pickupTime = document.getElementById('reservePickupTime')?.value?.trim();
    const contactType = document.getElementById('reserveContactType')?.value?.trim() || 'phone';
    const contactValue = document.getElementById('reserveContactValue')?.value?.trim() || '';

    if (!pickupDate || !pickupTime) return showToast('Please provide pickup date and time.');
    const [hours] = pickupTime.split(':').map(Number);
    if (hours < 7 || hours >= 17) return showToast('Pickup time must be within library hours: 7:00 AM – 5:00 PM');
    if (!contactValue) return showToast('Must fill the credentials!');
    if (contactType === 'phone' && !/^\d{11}$/.test(contactValue)) return showToast('Phone number must be exactly 11 numbers.');
    if (contactType === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contactValue)) return showToast('Please provide a valid email address.');

    const restrictionRes = await fetch(`/api/date_restrictions/check?date=${encodeURIComponent(pickupDate)}`);
    const restriction = await restrictionRes.json();
    if (restriction?.restricted) return showToast(restriction.reason || 'Selected pickup date is restricted.');

    const body = {
      book_no: bookNo,
      school_id: state.auth.profile.school_id,
      borrower_name: state.auth.profile.name,
      pickup_schedule: `${pickupDate} ${pickupTime}`,
      phone_number: contactValue,
      contact_type: contactType,
      request_id: `REQ-${Date.now().toString(36).toUpperCase()}`,
      pickup_location: 'Main Library',
      reservation_note: `${state.selectedBook?.book_no || ''} - ${state.selectedBook?.title || ''}`
    };

    const res = await fetch('/api/reserve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: state.auth.token },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    showToast(data.message || (data.success ? 'Reserved.' : 'Reservation failed.'));
    if (data.success) {
      toggleModal('bookReserveModal', false);
      loadLandingContent();
    }
  }

  function openReserveModal(book) {
    state.selectedBook = book;
    document.getElementById('modalBookTitle').textContent = book.title || 'Untitled';
    document.getElementById('modalBookAuthor').textContent = `by ${book.author || 'Unknown'}`;
    document.getElementById('modalBookNo').textContent = book.book_no || '-';
    document.getElementById('modalBookCategory').textContent = book.category || 'General';
    const status = document.getElementById('modalBookStatus');
    status.textContent = book.status || 'Available';
    status.className = `catalog-status-badge ${statusClass(book.status)}`;
    document.getElementById('reservePickupDate').value = '';
    document.getElementById('reservePickupTime').value = '';
    document.getElementById('reserveContactType').value = 'phone';
    document.getElementById('reserveContactValue').value = state.auth?.profile?.phone_number || '';
    document.getElementById('reserveContactValue').placeholder = '09XXXXXXXXX';
    toggleModal('bookReserveModal', true);
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
  document.getElementById('reserveContactType')?.addEventListener('change', (e) => {
    const input = document.getElementById('reserveContactValue');
    input.placeholder = e.target.value === 'email' ? 'name@example.com' : '09XXXXXXXXX';
    input.value = '';
  });
  document.getElementById('reserveSubmitBtn')?.addEventListener('click', () => {
    if (state.selectedBook?.book_no) handleReserve(state.selectedBook.book_no);
  });
  catalogSearchInput?.addEventListener('input', (e) => {
    state.search = e.target.value || '';
    renderCatalog();
  });
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
