(function () {
  const state = { cards: [], news: [], auth: null };
  const homeCardsGrid = document.getElementById('homeCardsGrid');
  const newsDesktopList = document.getElementById('newsDesktopList');
  const newsMobileStrip = document.getElementById('newsMobileStrip');

  const safe = (v) => String(v || '').replace(/[&<>\"]/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
  function toggleModal(id, show) { const node = document.getElementById(id); if (!node) return; node.classList.toggle('show', !!show); node.setAttribute('aria-hidden', show ? 'false' : 'true'); }
  window.toggleModal = toggleModal;


  function showSignUpError(message) {
    const error = document.getElementById('signUpError');
    if (!error) return;
    error.textContent = message || 'Unable to submit request.';
    error.hidden = false;
  }

  function previewSignUpPhoto(input) {
    if (input.files && input.files[0]) {
      const reader = new FileReader();
      reader.onload = function (e) {
        const preview = document.getElementById('signUpPhotoPreview');
        const icon = document.getElementById('signUpCameraIcon');
        if (!preview || !icon) return;
        preview.src = e.target.result;
        preview.hidden = false;
        icon.style.display = 'none';
      };
      reader.readAsDataURL(input.files[0]);
    }
  }

  function openSignUpModal() {
    document.getElementById('navDropdownMenu')?.classList.remove('open');
    ['signUpName', 'signUpId', 'signUpEmail', 'signUpPassword', 'signUpConfirm'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });

    const preview = document.getElementById('signUpPhotoPreview');
    const icon = document.getElementById('signUpCameraIcon');
    const file = document.getElementById('signUpPhotoFile');
    const circle = document.getElementById('signUpPhotoCircle');
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
      const el = document.getElementById(id);
      if (el) el.style.display = 'block';
    });

    const error = document.getElementById('signUpError');
    const success = document.getElementById('signUpSuccess');
    const submit = document.getElementById('signUpSubmitBtn');
    const cancel = document.getElementById('signUpCancelBtn');
    if (error) error.hidden = true;
    if (success) success.hidden = true;
    if (submit) {
      submit.style.display = 'block';
      submit.disabled = false;
      submit.innerHTML = '<i class="fas fa-paper-plane"></i> Submit Request';
    }
    if (cancel) cancel.textContent = 'Cancel';
    const footerLink = document.getElementById('signUpFooterLink');
    if (footerLink) footerLink.style.display = 'block';

    toggleModal('userLoginModal', false);
    document.getElementById('signUpModal')?.classList.add('active');
    document.getElementById('signUpModal')?.setAttribute('aria-hidden', 'false');
  }

  function closeSignUpModal() {
    const modal = document.getElementById('signUpModal');
    if (!modal) return;
    modal.classList.remove('active');
    modal.setAttribute('aria-hidden', 'true');
  }

  async function submitSignUp() {
    const name = document.getElementById('signUpName')?.value.trim() || '';
    const schoolId = (document.getElementById('signUpId')?.value || '').trim().toLowerCase();
    const email = (document.getElementById('signUpEmail')?.value || '').trim().toLowerCase();
    const password = document.getElementById('signUpPassword')?.value.trim() || '';
    const confirm = document.getElementById('signUpConfirm')?.value.trim() || '';
    const photoFile = document.getElementById('signUpPhotoFile')?.files?.[0];

    if (!name) return showSignUpError('Please enter your full name.');
    if (!schoolId) return showSignUpError('Please enter your School ID.');
    if (!email) return showSignUpError('Please enter your email address.');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return showSignUpError('Please enter a valid email address.');
    if (!password) return showSignUpError('Please create a password.');
    if (password.length < 6) return showSignUpError('Password must be at least 6 characters.');
    if (password !== confirm) return showSignUpError('Passwords do not match.');

    const btn = document.getElementById('signUpSubmitBtn');
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
          document.getElementById(id).style.display = 'none';
        });
        document.getElementById('signUpPhotoCircle').style.display = 'none';
        document.querySelector('.signup-photo-hint').style.display = 'none';
        btn.style.display = 'none';
        document.getElementById('signUpCancelBtn').textContent = 'Close';
        const footerLink = document.getElementById('signUpFooterLink');
        if (footerLink) footerLink.style.display = 'none';
        document.getElementById('signUpSuccessEmail').textContent = email;
        document.getElementById('signUpSuccess').hidden = false;
        document.getElementById('signUpError').hidden = true;
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

  window.openSignUpModal = openSignUpModal;
  window.closeSignUpModal = closeSignUpModal;

  function showToast(message) {
    const toast = document.getElementById('constructionToast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 1700);
  }

  function syncSessionUI() {
    const toggle = document.getElementById('landingAccountMenuToggle');
    const logoutBtn = document.getElementById('landingLogoutBtn');
    if (toggle) toggle.textContent = state.auth?.profile?.school_id ? `Account (${state.auth.profile.school_id})` : 'Account';
    if (logoutBtn) logoutBtn.classList.toggle('d-none', !state.auth?.token);
  }

  async function hydrateSession() {
    const id = localStorage.getItem('lbas_id');
    const token = localStorage.getItem('lbas_token');
    if (!id || !token) return;
    try {
      const res = await fetch(`/api/user/${encodeURIComponent(id)}`);
      const data = await res.json();
      if (data?.profile?.school_id) {
        state.auth = {
          token,
          profile: {
            school_id: String(data.profile.school_id || id).trim().toLowerCase(),
            name: data.profile.name || id,
          },
        };
      }
    } catch (_) {}
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
    state.auth = { token: data.token, profile: data.profile };
    localStorage.setItem('bookPageAuth', JSON.stringify(state.auth));
    localStorage.setItem('lbas_id', state.auth.profile.school_id);
    localStorage.setItem('lbas_token', state.auth.token);
    toggleModal('userLoginModal', false);
    syncSessionUI();
    showToast('Login successful. You can reserve books now.');
  }
  window.submitLandingLogin = submitLandingLogin;

  function logoutSession() {
    state.auth = null;
    localStorage.removeItem('bookPageAuth');
    localStorage.removeItem('lbas_id');
    localStorage.removeItem('lbas_token');
    syncSessionUI();
    showToast('Logged out.');
  }

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
  document.getElementById('landingLogoutBtn')?.addEventListener('click', logoutSession);

  document.getElementById('openSignUpFromLoginBtn')?.addEventListener('click', openSignUpModal);
  document.getElementById('signUpSubmitBtn')?.addEventListener('click', submitSignUp);
  document.getElementById('signUpCancelBtn')?.addEventListener('click', closeSignUpModal);
  document.getElementById('signUpCloseBtn')?.addEventListener('click', closeSignUpModal);
  document.getElementById('signUpLoginLink')?.addEventListener('click', () => {
    closeSignUpModal();
    toggleModal('userLoginModal', true);
  });
  document.getElementById('signUpPhotoCircle')?.addEventListener('click', () => document.getElementById('signUpPhotoFile')?.click());
  document.getElementById('signUpPhotoFile')?.addEventListener('change', (e) => previewSignUpPhoto(e.target));

  (async function init() {
    await hydrateSession();
    syncSessionUI();
    loadLandingContent();
  })();
})();
