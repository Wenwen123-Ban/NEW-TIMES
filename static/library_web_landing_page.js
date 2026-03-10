const state = {
  cards: [],
  news: [],
  auth: null,
  selectedBook: null,
  pendingReserveBook: null,
  books: []
};

function el(id) {
  return document.getElementById(id);
}

function toggleModal(id, show) {
  const node = el(id);
  if (!node) {
    return;
  }
  if (show) {
    node.classList.remove('hidden');
  } else {
    node.classList.add('hidden');
  }
}

function toast(message) {
  const box = el('constructionToast');
  if (!box) {
    return;
  }
  box.textContent = message;
  box.classList.remove('hidden');
  setTimeout(() => {
    box.classList.add('hidden');
  }, 2300);
}

async function hydrateSession() {
  const sid = localStorage.getItem('lbas_id');
  const token = localStorage.getItem('lbas_token');
  if (!sid || !token) {
    return;
  }
  const res = await fetch(`/api/user/${encodeURIComponent(sid)}`, {
    headers: {
      Authorization: token
    }
  });
  if (!res.ok) {
    return;
  }
  const profile = await res.json();
  if (!profile || profile.is_staff) {
    return;
  }
  state.auth = {
    token,
    profile
  };
}

function syncSessionUI() {
  const menu = el('landingAccountMenuToggle');
  const logoutBtn = el('landingLogoutBtn');
  const reserveSchoolId = el('reserveSchoolId');
  if (!menu || !logoutBtn || !reserveSchoolId) {
    return;
  }
  if (state.auth?.profile) {
    menu.textContent = state.auth.profile.school_id || 'Account';
    logoutBtn.classList.remove('hidden');
    reserveSchoolId.value = state.auth.profile.school_id || '';
  } else {
    menu.textContent = 'Account';
    logoutBtn.classList.add('hidden');
    reserveSchoolId.value = '';
  }
}

async function submitLandingLogin(isAdmin) {
  if (isAdmin) {
    const school_id = (el('adminSchoolId').value || '').trim().toLowerCase();
    const password = (el('adminPassword').value || '').trim();
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ school_id, password })
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      toast(data.message || 'Admin login failed');
      return;
    }
    if (!data.profile?.is_staff) {
      toast('Not an admin account');
      return;
    }
    window.location.href = '/admin';
    return;
  }

  const school_id = (el('userSchoolId').value || '').trim().toLowerCase();
  const res = await fetch('/api/verify_id', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ school_id })
  });
  const data = await res.json();
  if (!res.ok || !data.success) {
    toast(data.message || 'Verification failed');
    return;
  }
  state.auth = {
    token: data.token,
    profile: data.profile
  };
  localStorage.setItem('lbas_id', data.profile.school_id || school_id);
  localStorage.setItem('lbas_token', data.token);
  toggleModal('userLoginModal', false);
  syncSessionUI();
  toast('ID verified. Welcome!');
  if (state.pendingReserveBook) {
    const pending = state.pendingReserveBook;
    state.pendingReserveBook = null;
    openReserveModal(pending);
  }
}

function openReserveModal(book) {
  state.selectedBook = book;
  el('modalBookTitle').textContent = book.title || '';
  el('modalBookAuthor').textContent = book.author || '';
  el('modalBookNo').textContent = book.book_no || '';
  el('modalBookCategory').textContent = book.category || '';
  el('modalBookStatus').textContent = book.status || '';
  if (!state.auth) {
    state.pendingReserveBook = book;
    toast('Please verify ID first');
    toggleModal('userLoginModal', true);
    return;
  }
  el('reserveSchoolId').value = state.auth.profile.school_id || '';
  toggleModal('bookReserveModal', true);
}

async function submitLandingReserve() {
  if (!state.auth || !state.selectedBook) {
    toast('No active session or selected book');
    return;
  }
  const date = (el('reservePickupDate').value || '').trim();
  const time = (el('reservePickupTime').value || '').trim();
  const contactType = (el('reserveContactType').value || '').trim();
  const contactValue = (el('reserveContactValue').value || '').trim();
  if (!date || !time || !contactType || !contactValue) {
    toast('Complete all reservation fields');
    return;
  }
  const reqId = `REQ-${Date.now()}`;
  const res = await fetch('/api/reserve', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: state.auth.token
    },
    body: JSON.stringify({
      book_no: state.selectedBook.book_no,
      school_id: state.auth.profile.school_id,
      borrower_name: state.auth.profile.name || state.auth.profile.school_id,
      pickup_schedule: `${date} ${time}`,
      phone_number: contactValue,
      contact_type: contactType,
      request_id: reqId,
      pickup_location: 'Main Library'
    })
  });
  const data = await res.json();
  if (!res.ok || !data.success) {
    toast(data.message || 'Reservation failed');
    return;
  }
  toggleModal('bookReserveModal', false);
  toast('Reservation submitted successfully');
  await loadBooksPreview();
}

function renderHomeCards() {
  const wrap = el('homeCardsGrid');
  if (!wrap) {
    return;
  }
  wrap.innerHTML = '';
  const rows = Array.isArray(state.cards) ? state.cards : [];
  rows.forEach((card) => {
    const item = document.createElement('article');
    item.className = 'home-info-card';
    const h3 = document.createElement('h3');
    h3.textContent = card.title || 'Library Update';
    const body = document.createElement('p');
    body.textContent = card.body || 'Content will be posted by library staff.';
    item.appendChild(h3);
    item.appendChild(body);
    wrap.appendChild(item);
  });
}

function openNews(post) {
  el('newsModalTitle').textContent = post.title || '';
  el('newsModalMeta').textContent = `${post.date || post.date_created || ''} • ${post.author || 'Admin'}`;
  el('newsModalBody').textContent = post.body || post.summary || '';
  const img = el('newsModalImage');
  if (post.image_filename) {
    img.src = `/LandingUploads/${post.image_filename}`;
    img.classList.remove('hidden');
  } else {
    img.classList.add('hidden');
  }
  toggleModal('newsReadModal', true);
}

function renderNewsDesktop() {
  const wrap = el('newsDesktopList');
  if (!wrap) {
    return;
  }
  wrap.innerHTML = '';
  state.news.forEach((post) => {
    const row = document.createElement('div');
    row.className = 'news-post-row';
    const left = document.createElement('div');
    left.innerHTML = `<h4>${post.title || 'Untitled'}</h4><p>${post.summary || ''}</p>`;
    const right = document.createElement('button');
    right.textContent = 'Read More';
    right.addEventListener('click', () => openNews(post));
    row.appendChild(left);
    row.appendChild(right);
    wrap.appendChild(row);
  });
}

function renderNewsMobile() {
  const wrap = el('newsMobileStrip');
  if (!wrap) {
    return;
  }
  wrap.innerHTML = '';
  state.news.forEach((post) => {
    const card = document.createElement('div');
    card.className = 'mobile-news-card';
    card.innerHTML = `<strong>${post.title || 'Untitled'}</strong><p>${post.summary || ''}</p>`;
    const btn = document.createElement('button');
    btn.textContent = 'Read More';
    btn.addEventListener('click', () => openNews(post));
    card.appendChild(btn);
    wrap.appendChild(card);
  });
}

function renderLeaderRows(list, node, key) {
  node.innerHTML = '';
  list.forEach((row) => {
    const div = document.createElement('div');
    div.className = 'leader-row';
    div.textContent = `${row.rank || '-'} • ${row.name || row.title || row.school_id || row.book_no} • ${row[key] || 0}`;
    node.appendChild(div);
  });
}

function loadLeaderboard(payload) {
  const borrowers = payload.top_borrowers || [];
  const books = payload.top_books || [];
  const borWrap = el('landingTopBorrowers');
  const bookWrap = el('landingTopBooks');
  if (!borWrap || !bookWrap) {
    return;
  }
  renderLeaderRows(borrowers, borWrap, 'total_borrowed');
  renderLeaderRows(books, bookWrap, 'total_borrowed');
}

async function loadLandingContent() {
  const [cardsRes, newsRes, leaderRes] = await Promise.all([
    fetch('/api/home_cards'),
    fetch('/api/news_posts'),
    fetch('/api/monthly_leaderboard')
  ]);
  state.cards = await cardsRes.json();
  state.news = await newsRes.json();
  const leaderboard = await leaderRes.json();
  renderHomeCards();
  renderNewsDesktop();
  renderNewsMobile();
  loadLeaderboard(leaderboard || {});
}

async function loadBooksPreview() {
  const res = await fetch('/api/books', {
    headers: {
      Authorization: state.auth?.token || ''
    }
  });
  const data = await res.json();
  state.books = Array.isArray(data) ? data.slice(0, 6) : [];
  const wrap = el('landingCatalogPreview');
  if (!wrap) {
    return;
  }
  wrap.innerHTML = '';
  state.books.forEach((book) => {
    const card = document.createElement('article');
    card.className = 'catalog-preview-card';
    card.innerHTML = `
      <h4>${book.title || 'Untitled'}</h4>
      <p>${book.author || ''}</p>
      <span class="catalog-status-badge ${(book.status || '').toLowerCase() === 'available' ? 'status-available' : (book.status || '').toLowerCase() === 'reserved' ? 'status-reserved' : 'status-borrowed'}">${book.status || ''}</span>
    `;
    const btn = document.createElement('button');
    btn.textContent = 'Reserve';
    btn.addEventListener('click', () => openReserveModal(book));
    card.appendChild(btn);
    wrap.appendChild(card);
  });
}

async function submitSignUp() {
  const name = (el('signUpName').value || '').trim();
  const schoolId = (el('signUpId').value || '').trim().toLowerCase();
  const email = (el('signUpEmail').value || '').trim().toLowerCase();
  const password = (el('signUpPassword').value || '').trim();
  const confirm = (el('signUpConfirm').value || '').trim();
  const error = el('signUpError');
  if (!name || !schoolId || !email || !password || !confirm) {
    error.textContent = 'All fields are required.';
    error.classList.remove('hidden');
    return;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    error.textContent = 'Invalid email address.';
    error.classList.remove('hidden');
    return;
  }
  if (password !== confirm) {
    error.textContent = 'Password mismatch.';
    error.classList.remove('hidden');
    return;
  }
  error.classList.add('hidden');
  const body = new FormData();
  body.append('name', name);
  body.append('school_id', schoolId);
  body.append('email', email);
  body.append('password', password);
  const file = el('signUpPhotoFile').files?.[0];
  if (file) {
    body.append('photo', file);
  }
  const res = await fetch('/api/register_request', {
    method: 'POST',
    body
  });
  const data = await res.json();
  if (!res.ok || !data.success) {
    error.textContent = data.message || 'Request failed';
    error.classList.remove('hidden');
    return;
  }
  el('signUpSuccessEmail').textContent = email;
  el('signUpSuccess').classList.remove('hidden');
}

function logoutSession() {
  state.auth = null;
  localStorage.removeItem('lbas_id');
  localStorage.removeItem('lbas_token');
  syncSessionUI();
  toast('Signed out');
}

function wireEvents() {
  document.querySelectorAll('[data-close]').forEach((btn) => {
    btn.addEventListener('click', () => toggleModal(btn.dataset.close, false));
  });

  el('verifyIdBtn').addEventListener('click', () => submitLandingLogin(false));
  el('reserveSubmitBtn').addEventListener('click', submitLandingReserve);
  el('landingAccountMenuToggle').addEventListener('click', () => {
    if (state.auth) {
      toast('Session active');
    } else {
      toggleModal('userLoginModal', true);
    }
  });
  el('landingLogoutBtn').addEventListener('click', logoutSession);
  el('openSignUpFromLoginBtn').addEventListener('click', () => {
    toggleModal('userLoginModal', false);
    toggleModal('signUpModal', true);
  });
  el('signUpSubmitBtn').addEventListener('click', submitSignUp);
  el('signUpCancelBtn').addEventListener('click', () => toggleModal('signUpModal', false));
  el('signUpCloseBtn').addEventListener('click', () => toggleModal('signUpModal', false));
  el('signUpLoginLink').addEventListener('click', () => {
    toggleModal('signUpModal', false);
    toggleModal('userLoginModal', true);
  });
  el('signUpPhotoCircle').addEventListener('click', () => el('signUpPhotoFile').click());
  el('signUpCameraIcon').addEventListener('click', () => el('signUpPhotoFile').click());
  el('signUpPhotoFile').addEventListener('change', () => {
    const file = el('signUpPhotoFile').files?.[0];
    if (!file) {
      return;
    }
    el('signUpPhotoPreview').src = URL.createObjectURL(file);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      toggleModal('userLoginModal', false);
      toggleModal('adminLoginModal', false);
      toggleModal('signUpModal', false);
      toggleModal('bookReserveModal', false);
      toggleModal('newsReadModal', false);
    }
  });
}

(async function init() {
  wireEvents();
  await hydrateSession();
  syncSessionUI();
  await loadLandingContent();
  await loadBooksPreview();
})();
