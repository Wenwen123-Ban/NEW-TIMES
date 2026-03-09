(function () {
  const state = { books: [], auth: null, selectedBook: null, category: 'All', search: '' };
  const byId = (id) => document.getElementById(id);

  function safe(v) { return String(v || '').replace(/[&<>\"]/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m])); }
  function toast(msg) { const t = byId('toast'); t.textContent = msg; t.classList.add('show'); setTimeout(() => t.classList.remove('show'), 1800); }
  function modal(id, show) { const n = byId(id); n.classList.toggle('show', !!show); n.setAttribute('aria-hidden', show ? 'false' : 'true'); }
  function openLoginModal() { modal('idLoginModal', true); }
  window.openLoginModal = openLoginModal;


  function showSignUpError(message) {
    const error = byId('signUpError');
    if (!error) return;
    error.textContent = message || 'Unable to submit request.';
    error.hidden = false;
  }

  function previewSignUpPhoto(input) {
    if (input.files && input.files[0]) {
      const reader = new FileReader();
      reader.onload = function (e) {
        const preview = byId('signUpPhotoPreview');
        const icon = byId('signUpCameraIcon');
        if (!preview || !icon) return;
        preview.src = e.target.result;
        preview.hidden = false;
        icon.style.display = 'none';
      };
      reader.readAsDataURL(input.files[0]);
    }
  }

  function openSignUpModal() {
    ['signUpName', 'signUpId', 'signUpEmail', 'signUpPassword', 'signUpConfirm'].forEach((id) => {
      const el = byId(id);
      if (el) el.value = '';
    });

    const preview = byId('signUpPhotoPreview');
    const icon = byId('signUpCameraIcon');
    const file = byId('signUpPhotoFile');
    const circle = byId('signUpPhotoCircle');
    const hint = document.querySelector('.signup-photo-hint');
    if (preview) {
      preview.src = '';
      preview.hidden = true;
    }
    if (icon) icon.style.display = 'block';
    if (file) file.value = '';
    if (circle) circle.style.display = 'flex';
    if (hint) hint.style.display = 'block';

    ['fgSignUpName', 'fgSignUpId', 'fgSignUpEmail', 'fgSignUpPassword', 'fgSignUpConfirm'].forEach((id) => {
      const el = byId(id);
      if (el) el.style.display = 'block';
    });

    if (byId('signUpError')) byId('signUpError').hidden = true;
    if (byId('signUpSuccess')) byId('signUpSuccess').hidden = true;
    const submit = byId('signUpSubmitBtn');
    if (submit) {
      submit.style.display = 'block';
      submit.disabled = false;
      submit.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Request';
    }
    if (byId('signUpCancelBtn')) byId('signUpCancelBtn').textContent = 'Cancel';
    if (byId('signUpFooterLink')) byId('signUpFooterLink').style.display = 'block';

    modal('idLoginModal', false);
    byId('signUpModal')?.classList.add('active');
    byId('signUpModal')?.setAttribute('aria-hidden', 'false');
  }
  window.openSignUpModal = openSignUpModal;

  function closeSignUpModal() {
    byId('signUpModal')?.classList.remove('active');
    byId('signUpModal')?.setAttribute('aria-hidden', 'true');
  }

  async function submitSignUp() {
    const name = byId('signUpName')?.value.trim() || '';
    const schoolId = (byId('signUpId')?.value || '').trim().toLowerCase();
    const email = (byId('signUpEmail')?.value || '').trim().toLowerCase();
    const password = byId('signUpPassword')?.value.trim() || '';
    const confirm = byId('signUpConfirm')?.value.trim() || '';
    const photoFile = byId('signUpPhotoFile')?.files?.[0];

    if (!name) return showSignUpError('Please enter your full name.');
    if (!schoolId) return showSignUpError('Please enter your School ID.');
    if (!email) return showSignUpError('Please enter your email address.');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return showSignUpError('Please enter a valid email address.');
    if (!password) return showSignUpError('Please create a password.');
    if (password.length < 6) return showSignUpError('Password must be at least 6 characters.');
    if (password !== confirm) return showSignUpError('Passwords do not match.');

    const btn = byId('signUpSubmitBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting...';

    const fd = new FormData();
    fd.append('name', name);
    fd.append('school_id', schoolId);
    fd.append('email', email);
    fd.append('password', password);
    if (photoFile) fd.append('photo', photoFile);

    try {
      const res = await fetch('/api/register_request', { method: 'POST', body: fd });
      const data = await res.json();
      if (data.success) {
        ['fgSignUpName', 'fgSignUpId', 'fgSignUpEmail', 'fgSignUpPassword', 'fgSignUpConfirm'].forEach((id) => {
          byId(id).style.display = 'none';
        });
        byId('signUpPhotoCircle').style.display = 'none';
        document.querySelector('.signup-photo-hint').style.display = 'none';
        btn.style.display = 'none';
        byId('signUpCancelBtn').textContent = 'Close';
        if (byId('signUpFooterLink')) byId('signUpFooterLink').style.display = 'none';
        byId('signUpSuccessEmail').textContent = email;
        byId('signUpSuccess').hidden = false;
        byId('signUpError').hidden = true;
      } else {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Request';
        showSignUpError(data.message || 'Submission failed. Try again.');
      }
    } catch (_) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Request';
      showSignUpError('Connection error. Please try again.');
    }
  }

  function statusClass(status) {
    const s = String(status || '').toLowerCase();
    if (s === 'borrowed') return 'status-borrowed';
    if (s === 'reserved') return 'status-reserved';
    return 'status-available';
  }

  function syncSessionUI() {
    const logoutBtn = byId('logoutSessionBtn');
    const menuToggle = byId('accountMenuToggle');
    if (logoutBtn) logoutBtn.classList.toggle('d-none', !state.auth?.token);
    if (menuToggle) {
      menuToggle.textContent = state.auth?.profile?.school_id ? `Account (${state.auth.profile.school_id})` : 'Account';
    }
    const sid = state.auth?.profile?.school_id || '';
    if (byId('reserveSchoolId')) byId('reserveSchoolId').value = sid;
  }

  function normalizeProfile(profile, fallbackId) {
    return {
      school_id: String(profile?.school_id || fallbackId || '').trim().toLowerCase(),
      name: profile?.name || profile?.school_id || fallbackId || '',
      is_staff: !!profile?.is_staff,
      phone_number: profile?.phone_number || '',
      photo: profile?.photo || 'default.png',
      source: profile?.source || 'users',
    };
  }

  async function hydrateFromLBASSession() {
    if (state.auth?.token) return;
    const savedID = localStorage.getItem('lbas_id');
    const savedToken = localStorage.getItem('lbas_token');
    if (!savedID || !savedToken) return;

    try {
      const res = await fetch(`/api/user/${encodeURIComponent(savedID)}`);
      const data = await res.json();
      if (data?.profile?.school_id && String(data.profile.status || '').toLowerCase() !== 'pending') {
        state.auth = { token: savedToken, profile: normalizeProfile(data.profile, savedID) };
        localStorage.setItem('bookPageAuth', JSON.stringify(state.auth));
      }
    } catch (_) {
      // keep book page accessible even without active account session
    }
  }

  function restoreCachedAuth() {
    try {
      state.auth = JSON.parse(localStorage.getItem('bookPageAuth') || 'null');
    } catch (_) {
      state.auth = null;
    }
  }

  function renderCatalog() {
    const q = state.search.toLowerCase().trim();
    const filtered = state.books.filter((b) => {
      const catOk = state.category === 'All' || String(b.category || 'General') === state.category;
      const hay = `${b.book_no || ''} ${b.title || ''} ${b.author || ''}`.toLowerCase();
      return catOk && (!q || hay.includes(q));
    });

    byId('catalogResultCount').textContent = `${filtered.length} results`;
    byId('catalogBookGrid').innerHTML = filtered.map((book) => `
      <article class="catalog-card">
        <div class="small text-info">${safe(book.book_no || '-')}</div>
        <h5 class="catalog-card-title">${safe(book.title || 'Untitled')}</h5>
        <p class="catalog-card-author">${safe(book.author || 'Unknown')}</p>
        <span class="catalog-status-badge ${statusClass(book.status)}">${safe(book.status || 'Available')}</span>
        <button class="btn btn-sm btn-light w-100 reserve-btn" data-book-no="${safe(book.book_no)}">Reserve</button>
      </article>
    `).join('');

    document.querySelectorAll('.reserve-btn').forEach((btn) => btn.addEventListener('click', () => {
      const book = state.books.find((b) => String(b.book_no) === String(btn.dataset.bookNo));
      if (book) openReserveModal(book);
    }));

    const categories = ['All', ...new Set(state.books.map((b) => b.category || 'General'))];
    byId('catalogCategoryPills').innerHTML = categories.map((cat) => `<button class="catalog-pill ${cat === state.category ? 'active' : ''}" data-cat="${safe(cat)}">${safe(cat)}</button>`).join('');
    byId('catalogCategoryPills').querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { state.category = b.dataset.cat; renderCatalog(); }));
  }

  async function verifyIdOnly() {
    const school_id = byId('userSchoolId').value.trim();
    if (!school_id) return toast('Enter school ID.');
    const res = await fetch('/api/verify_id', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ school_id }) });
    const data = await res.json();
    if (!data.success) return toast(data.message || 'Login failed.');
    state.auth = { token: data.token, profile: normalizeProfile(data.profile, school_id) };
    localStorage.setItem('bookPageAuth', JSON.stringify(state.auth));
    localStorage.setItem('lbas_id', state.auth.profile.school_id);
    localStorage.setItem('lbas_token', data.token);
    byId('userSchoolId').value = '';
    modal('idLoginModal', false);
    syncSessionUI();
    toast(`Logged in as ${state.auth.profile.school_id}`);
  }

  function openReserveModal(book) {
    state.selectedBook = book;
    byId('modalBookTitle').textContent = book.title || '-';
    byId('modalBookAuthor').textContent = `by ${book.author || 'Unknown'}`;
    byId('modalBookNo').textContent = book.book_no || '-';
    byId('modalBookCategory').textContent = book.category || 'General';

    if (!state.auth?.token || !state.auth?.profile?.school_id) {
      toast('Please log in first before continuing.');
      openLoginModal();
      return;
    }

    byId('reserveSchoolId').value = state.auth.profile.school_id;
    modal('bookReserveModal', true);
  }

  async function reserveSelectedBook() {
    if (!state.selectedBook?.book_no) return;
    if (!state.auth?.token || !state.auth?.profile?.school_id) {
      toast('Please log in first before continuing.');
      openLoginModal();
      return;
    }

    const pickupDate = byId('reservePickupDate').value.trim();
    const pickupTime = byId('reservePickupTime').value.trim();
    const contactType = byId('reserveContactType').value;
    const contactValue = byId('reserveContactValue').value.trim();
    if (!pickupDate || !pickupTime || !contactValue) return toast('Please complete reservation fields.');

    const body = {
      book_no: state.selectedBook.book_no,
      school_id: state.auth.profile.school_id,
      borrower_name: state.auth.profile.name,
      pickup_schedule: `${pickupDate} ${pickupTime}`,
      phone_number: contactValue,
      contact_type: contactType,
      request_id: `REQ-${Date.now().toString(36).toUpperCase()}`,
      pickup_location: 'Main Library',
    };

    const res = await fetch('/api/reserve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: state.auth.token },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    toast(data.message || (data.success ? 'Reserved.' : 'Reservation failed.'));
    if (data.success) {
      modal('bookReserveModal', false);
      loadBooks();
    }
  }

  async function loadBooks() {
    const res = await fetch('/api/books');
    const payload = await res.json();
    state.books = Array.isArray(payload) ? payload : [];
    renderCatalog();
  }

  function logout() {
    state.auth = null;
    localStorage.removeItem('bookPageAuth');
    localStorage.removeItem('lbas_id');
    localStorage.removeItem('lbas_token');
    syncSessionUI();
    toast('Logged out.');
  }

  byId('catalogSearchInput').addEventListener('input', (e) => { state.search = e.target.value || ''; renderCatalog(); });
  byId('idLoginFab').addEventListener('click', openLoginModal);
  byId('verifyIdBtn').addEventListener('click', verifyIdOnly);
  byId('reserveSubmitBtn').addEventListener('click', reserveSelectedBook);
  byId('logoutSessionBtn')?.addEventListener('click', logout);
  document.querySelectorAll('[data-close]').forEach((btn) => btn.addEventListener('click', () => modal(btn.dataset.close, false)));

  byId('openSignUpFromBookLoginBtn')?.addEventListener('click', openSignUpModal);
  byId('signUpSubmitBtn')?.addEventListener('click', submitSignUp);
  byId('signUpCancelBtn')?.addEventListener('click', closeSignUpModal);
  byId('signUpCloseBtn')?.addEventListener('click', closeSignUpModal);
  byId('signUpLoginLink')?.addEventListener('click', () => { closeSignUpModal(); openLoginModal(); });
  byId('signUpPhotoCircle')?.addEventListener('click', () => byId('signUpPhotoFile')?.click());
  byId('signUpPhotoFile')?.addEventListener('change', (e) => previewSignUpPhoto(e.target));

  (async function init() {
    restoreCachedAuth();
    await hydrateFromLBASSession();
    syncSessionUI();
    loadBooks();
  })();
})();
