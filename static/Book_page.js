const state = {
  books: [],
  auth: null,
  selectedBook: null,
  category: 'All',
  search: ''
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

function showToast(message) {
  const toast = el('toast');
  if (!toast) {
    return;
  }
  toast.textContent = message;
  toast.classList.remove('hidden');
  setTimeout(() => {
    toast.classList.add('hidden');
  }, 2200);
}

function restoreCachedAuth() {
  const raw = localStorage.getItem('bookPageAuth');
  if (!raw) {
    return;
  }
  try {
    const parsed = JSON.parse(raw);
    if (parsed && parsed.token && parsed.profile) {
      state.auth = parsed;
    }
  } catch (error) {
    localStorage.removeItem('bookPageAuth');
  }
}

async function hydrateFromLBASSession() {
  if (state.auth) {
    return;
  }
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
  localStorage.setItem('bookPageAuth', JSON.stringify(state.auth));
}

function syncSessionUI() {
  const menu = el('accountMenuToggle');
  const logoutBtn = el('logoutSessionBtn');
  const reserveSchoolId = el('reserveSchoolId');
  const fab = el('idLoginFab');
  if (!menu || !logoutBtn || !reserveSchoolId || !fab) {
    return;
  }
  if (state.auth && state.auth.profile) {
    const sid = state.auth.profile.school_id || 'Account';
    menu.textContent = sid;
    logoutBtn.classList.remove('hidden');
    reserveSchoolId.value = sid;
    fab.classList.add('hidden');
  } else {
    menu.textContent = 'Account';
    logoutBtn.classList.add('hidden');
    reserveSchoolId.value = '';
    fab.classList.remove('hidden');
  }
}

async function verifyIdOnly() {
  const sid = (el('userSchoolId')?.value || '').trim().toLowerCase();
  if (!sid) {
    showToast('School ID is required');
    return;
  }
  const res = await fetch('/api/verify_id', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ school_id: sid })
  });
  const data = await res.json();
  if (!res.ok || !data.success) {
    showToast(data.message || 'Verification failed');
    return;
  }
  state.auth = {
    token: data.token,
    profile: data.profile
  };
  localStorage.setItem('bookPageAuth', JSON.stringify(state.auth));
  localStorage.setItem('lbas_id', data.profile.school_id || sid);
  localStorage.setItem('lbas_token', data.token);
  toggleModal('idLoginModal', false);
  syncSessionUI();
  showToast('ID verified. You can now reserve books.');
}

function openReserveModal(book) {
  state.selectedBook = book;
  el('modalBookTitle').textContent = book.title || '';
  el('modalBookAuthor').textContent = book.author || 'Unknown';
  el('modalBookNo').textContent = book.book_no || '';
  el('modalBookCategory').textContent = book.category || '';
  el('modalBookStatus').textContent = book.status || '';
  if (!state.auth) {
    showToast('Please verify your ID first.');
    toggleModal('idLoginModal', true);
    return;
  }
  el('reserveSchoolId').value = state.auth.profile.school_id || '';
  toggleModal('bookReserveModal', true);
}

async function reserveSelectedBook() {
  if (!state.selectedBook) {
    showToast('No selected book');
    return;
  }
  const date = (el('reservePickupDate').value || '').trim();
  const time = (el('reservePickupTime').value || '').trim();
  const contactType = (el('reserveContactType').value || '').trim();
  const contactValue = (el('reserveContactValue').value || '').trim();
  if (!date || !time || !contactType || !contactValue) {
    showToast('Please complete all fields.');
    return;
  }
  const requestId = `REQ-${Date.now()}`;
  const res = await fetch('/api/reserve', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: state.auth?.token || ''
    },
    body: JSON.stringify({
      book_no: state.selectedBook.book_no,
      school_id: state.auth.profile.school_id,
      borrower_name: state.auth.profile.name || state.auth.profile.school_id,
      pickup_schedule: `${date} ${time}`,
      phone_number: contactValue,
      contact_type: contactType,
      request_id: requestId,
      pickup_location: 'Main Library'
    })
  });
  const data = await res.json();
  if (!res.ok || !data.success) {
    showToast(data.message || 'Reservation failed');
    return;
  }
  toggleModal('bookReserveModal', false);
  await loadBooks();
  showToast('Book reserved successfully.');
}

async function loadBooks() {
  const res = await fetch('/api/books', {
    headers: {
      Authorization: state.auth?.token || ''
    }
  });
  const data = await res.json();
  state.books = Array.isArray(data) ? data : [];
  renderCatalog();
}

function getBookCategories(rows) {
  const set = new Set(['All']);
  rows.forEach((row) => {
    const category = (row.category || '').trim();
    if (category) {
      set.add(category);
    }
  });
  return Array.from(set);
}

function renderCategoryPills(rows) {
  const wrap = el('catalogCategoryPills');
  if (!wrap) {
    return;
  }
  const categories = getBookCategories(rows);
  wrap.innerHTML = '';
  categories.forEach((category) => {
    const btn = document.createElement('button');
    btn.className = 'catalog-pill';
    if (category === state.category) {
      btn.classList.add('active');
    }
    btn.textContent = category;
    btn.addEventListener('click', () => {
      state.category = category;
      renderCatalog();
    });
    wrap.appendChild(btn);
  });
}

function statusClass(status) {
  const s = (status || '').toLowerCase();
  if (s === 'available') {
    return 'status-available';
  }
  if (s === 'reserved') {
    return 'status-reserved';
  }
  return 'status-borrowed';
}

function renderCatalog() {
  const grid = el('catalogBookGrid');
  const count = el('catalogResultCount');
  if (!grid || !count) {
    return;
  }
  renderCategoryPills(state.books);
  const filtered = state.books.filter((book) => {
    const passCategory = state.category === 'All' || (book.category || '') === state.category;
    const q = state.search.toLowerCase();
    const passSearch = !q
      || `${book.title || ''} ${book.author || ''} ${book.book_no || ''}`.toLowerCase().includes(q);
    return passCategory && passSearch;
  });
  count.textContent = `${filtered.length} books`;
  grid.innerHTML = '';
  filtered.forEach((book) => {
    const card = document.createElement('article');
    card.className = 'catalog-card';
    const title = document.createElement('h3');
    title.className = 'catalog-card-title';
    title.textContent = book.title || 'Untitled';
    const author = document.createElement('div');
    author.className = 'catalog-card-author';
    author.textContent = book.author || 'Unknown Author';
    const badge = document.createElement('span');
    badge.className = `catalog-status-badge ${statusClass(book.status)}`;
    badge.textContent = book.status || 'unknown';
    const reserveBtn = document.createElement('button');
    reserveBtn.textContent = 'Reserve';
    reserveBtn.disabled = (book.status || '').toLowerCase() === 'borrowed';
    reserveBtn.addEventListener('click', () => openReserveModal(book));
    card.appendChild(title);
    card.appendChild(author);
    card.appendChild(badge);
    card.appendChild(reserveBtn);
    grid.appendChild(card);
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
    error.textContent = 'Passwords do not match.';
    error.classList.remove('hidden');
    return;
  }
  error.classList.add('hidden');
  const fd = new FormData();
  fd.append('name', name);
  fd.append('school_id', schoolId);
  fd.append('email', email);
  fd.append('password', password);
  const photo = el('signUpPhotoFile').files?.[0];
  if (photo) {
    fd.append('photo', photo);
  }
  const res = await fetch('/api/register_request', {
    method: 'POST',
    body: fd
  });
  const data = await res.json();
  if (!res.ok || !data.success) {
    error.textContent = data.message || 'Could not submit sign up';
    error.classList.remove('hidden');
    return;
  }
  el('signUpSuccessEmail').textContent = email;
  el('signUpSuccess').classList.remove('hidden');
}

function logout() {
  state.auth = null;
  localStorage.removeItem('bookPageAuth');
  localStorage.removeItem('lbas_id');
  localStorage.removeItem('lbas_token');
  syncSessionUI();
  showToast('Logged out.');
}

function wireEvents() {
  document.querySelectorAll('[data-close]').forEach((btn) => {
    btn.addEventListener('click', () => {
      toggleModal(btn.getAttribute('data-close'), false);
    });
  });
  el('verifyIdBtn').addEventListener('click', verifyIdOnly);
  el('reserveSubmitBtn').addEventListener('click', reserveSelectedBook);
  el('catalogSearchInput').addEventListener('input', (event) => {
    state.search = event.target.value || '';
    renderCatalog();
  });
  el('idLoginFab').addEventListener('click', () => toggleModal('idLoginModal', true));
  el('accountMenuToggle').addEventListener('click', () => toggleModal('idLoginModal', true));
  el('logoutSessionBtn').addEventListener('click', logout);
  el('openSignUpFromLoginBtn').addEventListener('click', () => {
    toggleModal('idLoginModal', false);
    toggleModal('signUpModal', true);
  });
  el('signUpSubmitBtn').addEventListener('click', submitSignUp);
  el('signUpCancelBtn').addEventListener('click', () => toggleModal('signUpModal', false));
  el('signUpCloseBtn').addEventListener('click', () => toggleModal('signUpModal', false));
  el('signUpLoginLink').addEventListener('click', () => {
    toggleModal('signUpModal', false);
    toggleModal('idLoginModal', true);
  });
  el('signUpCameraIcon').addEventListener('click', () => el('signUpPhotoFile').click());
  el('signUpPhotoCircle').addEventListener('click', () => el('signUpPhotoFile').click());
  el('signUpPhotoFile').addEventListener('change', () => {
    const file = el('signUpPhotoFile').files?.[0];
    if (!file) {
      return;
    }
    const url = URL.createObjectURL(file);
    el('signUpPhotoPreview').src = url;
  });
}

(async function init() {
  wireEvents();
  restoreCachedAuth();
  await hydrateFromLBASSession();
  syncSessionUI();
  await loadBooks();
})();
