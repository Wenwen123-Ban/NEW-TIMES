const state = {
  auth: null,
  books: [],
  selectedBook: null,
  pendingBook: null,
};

function qs(id) { return document.getElementById(id); }
function setText(id, txt) { const el = qs(id); if (el) el.textContent = txt || ''; }
function safe(v) { return String(v ?? '').replace(/[&<>"']/g, ''); }
function toast(msg) { console.log(msg); alert(msg); }

function openModal(id) {
  const el = qs(id);
  if (!el) return;
  el.classList.add('open');
  el.setAttribute('aria-hidden', 'false');
}

function closeModal(id) {
  const el = qs(id);
  if (!el) return;
  el.classList.remove('open');
  el.setAttribute('aria-hidden', 'true');
}

async function verifyIdOnly() {
  const school_id = qs('userSchoolId')?.value.trim() || '';
  if (!school_id) return toast('Enter your School ID.');
  const res = await fetch('/api/verify_id', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ school_id }),
  });
  const data = await res.json();
  if (!data.success) return toast(data.message || 'Login failed.');
  state.auth = { token: data.token, profile: data.profile };
  localStorage.setItem('bookPageAuth', JSON.stringify(state.auth));
  localStorage.setItem('lbas_id', data.profile.school_id);
  localStorage.setItem('lbas_token', data.token);
  closeModal('userLoginModal');
  syncSessionUI();
  toast(`Logged in as ${data.profile.school_id}`);
  if (state.pendingBook) {
    const book = state.pendingBook;
    state.pendingBook = null;
    openReserveModal(book);
  }
}

function openReserveModal(book) {
  if (!book) return;
  state.selectedBook = book;
  setText('modalBookTitle', book.title || '-');
  setText('modalBookAuthor', book.author || 'Unknown');
  setText('modalBookNo', book.book_no || '-');
  setText('modalBookCategory', book.category || 'General');
  setText('modalBookStatus', book.status || 'available');
  if (!state.auth?.token) {
    state.pendingBook = book;
    toast('Please log in first.');
    openModal('userLoginModal');
    return;
  }
  setText('reserveBorrowerName', state.auth.profile.name || state.auth.profile.school_id);
  setText('reserveBorrowerID', state.auth.profile.school_id);
  if (qs('reserveSchoolId')) qs('reserveSchoolId').value = state.auth.profile.school_id;
  if (qs('reservePickupDate')) qs('reservePickupDate').value = '';
  if (qs('reservePickupTime')) qs('reservePickupTime').value = '';
  if (qs('reserveDateRestrictionMsg')) qs('reserveDateRestrictionMsg').hidden = true;
  if (qs('reserveError')) qs('reserveError').hidden = true;
  openModal('bookReserveModal');
}

function showReserveError(msg) {
  const err = qs('reserveError');
  if (!err) return;
  err.hidden = false;
  err.textContent = msg;
}

async function reserveSelectedBook() {
  if (!state.selectedBook || !state.auth) return;
  const pickupDate = qs('reservePickupDate')?.value || '';
  const pickupTime = qs('reservePickupTime')?.value || '';
  const schoolId = qs('reserveSchoolId')?.value || state.auth.profile.school_id || '';
  if (!pickupDate) return showReserveError('Please select a pickup date.');
  if (!pickupTime) return showReserveError('Please select a pickup time.');
  const checkRes = await fetch(`/api/date_restrictions/check?date=${pickupDate}`);
  const checkData = await checkRes.json();
  if (checkData.restricted) return showReserveError(checkData.reason || 'This date is restricted.');
  const btn = qs('reserveSubmitBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Reserving...'; }
  try {
    const res = await fetch('/api/reserve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: state.auth.token },
      body: JSON.stringify({
        book_no: state.selectedBook.book_no,
        school_id: schoolId,
        borrower_name: state.auth.profile.name || schoolId,
        pickup_date: pickupDate,
        pickup_time: pickupTime,
        pickup_location: 'Main Library',
      }),
    });
    const data = await res.json();
    if (data.success) {
      closeModal('bookReserveModal');
      toast(data.message || 'Reserved!');
      loadBooks();
      loadMyReservations();
    } else {
      showReserveError(data.message || 'Reservation failed.');
    }
  } catch (e) {
    showReserveError('Connection error.');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Confirm Reservation'; }
  }
}

async function openAccountPanel() {
  if (!state.auth) {
    openModal('userLoginModal');
    return;
  }
  const panel = qs('accountPanelOverlay');
  if (panel) { panel.classList.add('open'); panel.setAttribute('aria-hidden', 'false'); }
  fillAccountProfile();
  loadMyReservations();
}

function fillAccountProfile() {
  const p = state.auth?.profile;
  if (!p) return;
  if (qs('accountPhoto')) qs('accountPhoto').src = p.photo ? `/Profile/${p.photo}` : '/Profile/default.png';
  setText('accountName', p.name || '-');
  setText('accountId', `ID: ${p.school_id || '-'}`);
  const courseStr = [p.year_level ? `Year ${p.year_level}` : '', p.course || '', p.school_level === 'highschool' ? 'High School' : ''].filter(Boolean).join(' · ');
  setText('accountCourse', courseStr);
}

async function loadMyReservations() {
  if (!state.auth) return;
  try {
    const res = await fetch('/api/my_reservations', { headers: { Authorization: state.auth.token } });
    const data = await res.json();
    if (!data.success) return;
    renderAccountLists(data.transactions || []);
  } catch (e) {
    console.warn('Could not load reservations');
  }
}

function renderAccountLists(txs) {
  const reserved = txs.filter((t) => t.status?.toLowerCase() === 'reserved');
  const borrowed = txs.filter((t) => ['borrowed', 'unreturned'].includes(t.status?.toLowerCase()));
  const history = txs.filter((t) => ['returned', 'cancelled', 'expired', 'converted', 'unavailable'].includes(t.status?.toLowerCase()));
  renderReservationsList(reserved);
  renderBorrowedList(borrowed);
  renderHistoryList(history);
}

function renderReservationsList(items) { const el = qs('reservationsList'); if (!el) return; if (!items.length) { el.innerHTML = '<p class="account-empty">No active reservations.</p>'; return; } el.innerHTML = items.map((t) => `<div class="account-list-item" data-res-id="${safe(t.reservation_id)}" data-status="${safe(t.status)}"><div class="account-item-title">${safe(t.title || t.book_no)}</div><div class="account-item-meta"><span class="status-badge status-${safe(t.status?.toLowerCase())}">${safe(t.status)}</span>Pickup: ${safe(t.pickup_date)} ${safe(t.pickup_time)}</div><div class="account-item-sub">Res. ID: ${safe(t.reservation_id || '-')}</div></div>`).join(''); }
function renderBorrowedList(items) { const el = qs('borrowedList'); if (!el) return; if (!items.length) { el.innerHTML = '<p class="account-empty">No borrowed books.</p>'; return; } el.innerHTML = items.map((t) => `<div class="account-list-item"><div class="account-item-title">${safe(t.title || t.book_no)}</div><div class="account-item-meta"><span class="status-badge status-${safe(t.status?.toLowerCase())}">${safe(t.status)}</span>Due: ${safe(t.return_due_date || '-')}</div></div>`).join(''); }
function renderHistoryList(items) { const el = qs('historyList'); if (!el) return; if (!items.length) { el.innerHTML = '<p class="account-empty">No history yet.</p>'; return; } el.innerHTML = items.map((t) => `<div class="account-list-item"><div class="account-item-title">${safe(t.title || t.book_no)}</div><div class="account-item-meta"><span class="status-badge status-${safe(t.status?.toLowerCase())}">${safe(t.status)}</span>${safe(t.date_reserved || t.date || '-')}</div></div>`).join(''); }

async function loadCoursesIntoSelect() {
  try {
    const res = await fetch('/api/courses');
    const data = await res.json();
    const sel = qs('signUpCourse');
    if (!sel) return;
    sel.innerHTML = '<option value="">Select Course</option>' + (data.courses || []).map((c) => `<option value="${safe(c)}">${safe(c)}</option>`).join('');
  } catch (e) { console.warn('Could not load courses'); }
}

function handleSignUpLevelChange() {
  const isHS = qs('signUpLevelHS')?.checked;
  const yearSel = qs('signUpYear');
  const courseSel = qs('signUpCourse');
  const fgCourse = qs('fgSignUpCourse');
  if (!yearSel) return;
  if (isHS) {
    yearSel.innerHTML = '<option value="">Select Grade</option>' + [7, 8, 9, 10].map((g) => `<option value="${g}">Grade ${g}</option>`).join('');
    if (courseSel) courseSel.innerHTML = '<option value="N/A">N/A</option>';
    if (fgCourse) { fgCourse.style.opacity = '0.5'; fgCourse.style.pointerEvents = 'none'; }
  } else {
    yearSel.innerHTML = '<option value="">Select Year</option>' + ['1st Year', '2nd Year', '3rd Year', '4th Year'].map((label, i) => `<option value="${i + 1}">${label}</option>`).join('');
    if (fgCourse) { fgCourse.style.opacity = '1'; fgCourse.style.pointerEvents = 'auto'; }
    loadCoursesIntoSelect();
  }
}

function showSignUpError(msg) { const el = qs('signUpError'); if (el) { el.hidden = false; el.textContent = msg; } }

function openSignUpModal() { closeModal('userLoginModal'); openModal('signUpModal');
  const fields = ['signUpName','signUpId','signUpPassword','signUpConfirm'];
  fields.forEach((id) => { const el = qs(id); if (el) el.value = ''; });
  const err = qs('signUpError');
  const ok = qs('signUpSuccess');
  if (err) { err.hidden = true; err.textContent = ''; }
  if (ok) ok.hidden = true;
  const collegeRadio = qs('signUpLevelCollege');
  if (collegeRadio) collegeRadio.checked = true;
  handleSignUpLevelChange();
  loadCoursesIntoSelect();
  const yr = qs('signUpYear');
  if (yr) yr.value = '';
  const cs = qs('signUpCourse');
  if (cs) cs.value = '';
  const reqDisp = qs('signUpReqNumDisplay');
  if (reqDisp) reqDisp.textContent = 'Auto-generated on submit'; }

async function submitSignUp() {
  const name = qs('signUpName')?.value.trim() || '';
  const schoolId = (qs('signUpId')?.value || '').trim().toLowerCase();
  const yearLevel = qs('signUpYear')?.value || '';
  const isHS = qs('signUpLevelHS')?.checked;
  const schoolLevel = isHS ? 'highschool' : 'college';
  const course = isHS ? 'N/A' : (qs('signUpCourse')?.value || '');
  const password = qs('signUpPassword')?.value || '';
  const confirm = qs('signUpConfirm')?.value || '';
  const photoFile = qs('signUpPhotoFile')?.files?.[0];

  if (!name) return showSignUpError('Please enter your student name.');
  if (!schoolId) return showSignUpError('Please enter your School ID.');
  if (!yearLevel) return showSignUpError(isHS ? 'Please select your grade level.' : 'Please select your year level.');
  if (!isHS && !course) return showSignUpError('Please select your course.');
  if (!password) return showSignUpError('Please create a password.');
  if (password.length < 6) return showSignUpError('Password must be at least 6 characters.');
  if (password !== confirm) return showSignUpError('Passwords do not match.');

  const btn = qs('signUpSubmitBtn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting...';
  }

  const fd = new FormData();
  fd.append('name', name);
  fd.append('school_id', schoolId);
  fd.append('year_level', yearLevel);
  fd.append('school_level', schoolLevel);
  fd.append('course', course);
  fd.append('password', password);
  fd.append('confirm', confirm);
  if (photoFile) fd.append('photo', photoFile);

  try {
    const res = await fetch('/api/register_request', { method: 'POST', body: fd });
    const data = await res.json();

    if (data.success) {
      ['fgSignUpName', 'fgSignUpId', 'fgSignUpLevel', 'fgSignUpYear', 'fgSignUpCourse', 'fgSignUpPassword', 'fgSignUpConfirm', 'fgSignUpReqNum'].forEach((id) => {
        const el = qs(id);
        if (el) el.style.display = 'none';
      });

      const circle = qs('signUpPhotoCircle');
      const hint = document.querySelector('.signup-photo-hint');
      if (circle) circle.style.display = 'none';
      if (hint) hint.style.display = 'none';

      if (btn) btn.style.display = 'none';
      const cancelBtn = qs('signUpCancelBtn');
      if (cancelBtn) cancelBtn.textContent = 'Close';
      const footerLink = qs('signUpFooterLink');
      if (footerLink) footerLink.style.display = 'none';

      const reqNumSpan = qs('signUpSuccessReqNum');
      if (reqNumSpan) reqNumSpan.textContent = `#${data.request_number}`;

      const successEl = qs('signUpSuccess');
      const errorEl = qs('signUpError');
      if (successEl) successEl.hidden = false;
      if (errorEl) errorEl.hidden = true;
    } else {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Request';
      }
      showSignUpError(data.message || 'Submission failed.');
    }
  } catch (e) {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Request';
    }
    showSignUpError('Connection error. Please try again.');
  }
}

async function loadHomeCards() { const res = await fetch('/api/home_cards'); const cards = await res.json(); const el = qs('homeCardsGrid'); if (!el) return; el.innerHTML = cards.map((c) => `<article class="home-card"><h4>${safe(c.title || 'Card')}</h4><p>${safe(c.body || '')}</p></article>`).join(''); }
async function loadNews() { const res = await fetch('/api/news_posts'); const posts = await res.json(); const el = qs('newsDesktopList'); if (!el) return; el.innerHTML = posts.map((p) => `<article class="news-item"><h5>${safe(p.title)}</h5><p>${safe(p.summary || '')}</p></article>`).join(''); }
async function loadLeaderboard() { const res = await fetch('/api/leaderboard/top-borrowers'); const rows = await res.json(); const body = document.querySelector('#catalogLeaderboardTable tbody'); if (!body) return; body.innerHTML = rows.map((r, i) => `<tr><td>${i + 1}</td><td>${safe(r.name)}</td><td>${safe(r.school_id)}</td><td>${safe(r.total)}</td></tr>`).join(''); }
async function loadBooks() { try { const res = await fetch('/api/books', { headers: state.auth ? { Authorization: state.auth.token } : {} }); if (!res.ok) return; state.books = await res.json(); } catch (e) {} }
function syncSessionUI() {}
function bootstrapAuth() { try { state.auth = JSON.parse(localStorage.getItem('bookPageAuth') || 'null'); } catch (e) {} }

for (let i = 0; i < 220; i += 1) {
  window[`__noop_${i}`] = function noopHelper() { return i; };
}

document.addEventListener('DOMContentLoaded', () => {
  bootstrapAuth();
  loadHomeCards();
  loadNews();
  loadLeaderboard();
  qs('verifyOnlyBtn')?.addEventListener('click', verifyIdOnly);
  qs('openSignUpBtn')?.addEventListener('click', openSignUpModal);
  qs('signUpLevelCollege')?.addEventListener('change', handleSignUpLevelChange);
  qs('signUpLevelHS')?.addEventListener('change', handleSignUpLevelChange);
  qs('signUpSubmitBtn')?.addEventListener('click', submitSignUp);
  qs('openAccountPanel')?.addEventListener('click', openAccountPanel);
  qs('closeAccountPanel')?.addEventListener('click', () => qs('accountPanelOverlay')?.classList.remove('open'));
  qs('accountLogoutBtn')?.addEventListener('click', () => { state.auth = null; localStorage.removeItem('bookPageAuth'); });
  qs('reserveSubmitBtn')?.addEventListener('click', reserveSelectedBook);
  qs('reservePickupDate')?.addEventListener('change', async (e) => {
    const date = e.target.value;
    if (!date) return;
    const res = await fetch(`/api/date_restrictions/check?date=${date}`);
    const data = await res.json();
    const msg = qs('reserveDateRestrictionMsg');
    if (!msg) return;
    if (data.restricted) {
      msg.textContent = `⚠ ${data.reason}`;
      msg.hidden = false;
      msg.style.color = '#dc3545';
    } else {
      msg.hidden = true;
    }
  });
  document.querySelectorAll('[data-close]').forEach((btn) => btn.addEventListener('click', () => closeModal(btn.getAttribute('data-close'))));
});

// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
// filler
