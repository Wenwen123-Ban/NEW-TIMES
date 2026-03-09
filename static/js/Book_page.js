(function () {
  const state = { books: [], auth: null, selectedBook: null, category: 'All', search: '' };
  const byId = (id) => document.getElementById(id);

  function safe(v) { return String(v || '').replace(/[&<>\"]/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m])); }
  function toast(msg) { const t = byId('toast'); t.textContent = msg; t.classList.add('show'); setTimeout(() => t.classList.remove('show'), 1800); }
  function modal(id, show) { const n = byId(id); n.classList.toggle('show', !!show); n.setAttribute('aria-hidden', show ? 'false' : 'true'); }

  function statusClass(status) { const s = String(status || '').toLowerCase(); return s === 'borrowed' ? 'danger' : s === 'reserved' ? 'warning' : 'success'; }

  function renderCatalog() {
    const q = state.search.toLowerCase().trim();
    const filtered = state.books.filter((b) => {
      const catOk = state.category === 'All' || String(b.category || 'General') === state.category;
      const hay = `${b.book_no || ''} ${b.title || ''} ${b.author || ''}`.toLowerCase();
      return catOk && (!q || hay.includes(q));
    });

    byId('catalogResultCount').textContent = `${filtered.length} results`;
    byId('catalogBookGrid').innerHTML = filtered.map((book) => `
      <article class="book-card">
        <div class="small text-info">${safe(book.book_no || '-')}</div>
        <h5>${safe(book.title || 'Untitled')}</h5>
        <p class="small mb-1">${safe(book.author || 'Unknown')}</p>
        <span class="badge text-bg-${statusClass(book.status)}">${safe(book.status || 'Available')}</span>
        <button class="btn btn-sm btn-light w-100 mt-2 reserve-btn" data-book-no="${safe(book.book_no)}">Reserve</button>
      </article>
    `).join('');

    document.querySelectorAll('.reserve-btn').forEach((btn) => btn.addEventListener('click', () => {
      const book = state.books.find((b) => String(b.book_no) === String(btn.dataset.bookNo));
      if (book) openReserveModal(book);
    }));

    const categories = ['All', ...new Set(state.books.map((b) => b.category || 'General'))];
    byId('catalogCategoryPills').innerHTML = categories.map((cat) => `<button class="${cat === state.category ? 'active' : ''}" data-cat="${safe(cat)}">${safe(cat)}</button>`).join('');
    byId('catalogCategoryPills').querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { state.category = b.dataset.cat; renderCatalog(); }));
  }

  async function verifyIdOnly() {
    const school_id = byId('userSchoolId').value.trim();
    if (!school_id) return toast('Enter school ID.');
    const res = await fetch('/api/verify_id', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ school_id }) });
    const data = await res.json();
    if (!data.success) return toast(data.message || 'Verification failed.');
    state.auth = { token: data.token, profile: data.profile };
    localStorage.setItem('bookPageAuth', JSON.stringify(state.auth));
    modal('idLoginModal', false);
    toast(`Verified: ${data.profile?.name || data.profile?.school_id}`);
  }

  function openReserveModal(book) {
    state.selectedBook = book;
    byId('modalBookTitle').textContent = book.title || '-';
    byId('modalBookAuthor').textContent = `by ${book.author || 'Unknown'}`;
    byId('modalBookNo').textContent = book.book_no || '-';
    byId('modalBookCategory').textContent = book.category || 'General';
    const sid = state.auth?.profile?.school_id || '';
    byId('reserveSchoolId').value = sid;
    byId('reserveSchoolId').readOnly = true;
    modal('bookReserveModal', true);
  }

  async function reserveSelectedBook() {
    if (!state.selectedBook?.book_no) return;
    if (!state.auth?.token || !state.auth?.profile?.school_id) {
      toast('ID verification required before reserving.');
      modal('idLoginModal', true);
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
      body: JSON.stringify(body)
    });
    const data = await res.json();
    toast(data.message || (data.success ? 'Reserved.' : 'Reservation failed.'));
    if (data.success) { modal('bookReserveModal', false); loadBooks(); }
  }

  async function loadBooks() {
    const res = await fetch('/api/books');
    state.books = await res.json();
    renderCatalog();
  }

  byId('catalogSearchInput').addEventListener('input', (e) => { state.search = e.target.value || ''; renderCatalog(); });
  byId('idLoginFab').addEventListener('click', () => modal('idLoginModal', true));
  byId('verifyIdBtn').addEventListener('click', verifyIdOnly);
  byId('reserveSubmitBtn').addEventListener('click', reserveSelectedBook);
  document.querySelectorAll('[data-close]').forEach((btn) => btn.addEventListener('click', () => modal(btn.dataset.close, false)));

  try { state.auth = JSON.parse(localStorage.getItem('bookPageAuth') || 'null'); } catch (_) {}
  loadBooks();
})();
