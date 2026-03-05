(function () {
  const state = {
    home: [],
    news: [],
    homeIndex: 0,
    newsIndex: 0,
  };

  const homeCard = document.getElementById('homePostCard');
  const newsCard = document.getElementById('newsPostCard');

  function safe(v) {
    return String(v || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderPost(section) {
    const posts = state[section];
    const indexKey = section === 'home' ? 'homeIndex' : 'newsIndex';
    const card = section === 'home' ? homeCard : newsCard;
    if (!card) return;

    if (!posts.length) {
      card.innerHTML = '<p class="placeholder-text mb-0">No post yet.</p>';
      return;
    }

    const post = posts[state[indexKey]];
    const media = post.image
      ? `<img src="/LandingUploads/${encodeURIComponent(post.image)}" class="landing-post-image" alt="${safe(post.post_id)}">`
      : '';
    const documentLink = post.document
      ? `<a class="btn btn-sm btn-outline-light mt-2" href="/LandingUploads/${encodeURIComponent(post.document)}" target="_blank" rel="noopener">Open document</a>`
      : '';

    card.innerHTML = `
      <span class="post-id-chip">${safe(post.post_id)}</span>
      ${media}
      <p class="mb-2 mt-2">${safe(post.text || '(no text)')}</p>
      ${documentLink}
    `;
  }

  function rotate(section, step) {
    const posts = state[section];
    const indexKey = section === 'home' ? 'homeIndex' : 'newsIndex';
    if (!posts.length) return;
    const len = posts.length;
    state[indexKey] = (state[indexKey] + step + len) % len;
    renderPost(section);
  }

  function renderLeaderboard(rows) {
    const tbody = document.querySelector('#catalogLeaderboardTable tbody');
    if (!tbody) return;
    tbody.innerHTML = rows.map((row, idx) => `
      <tr>
        <td>${idx + 1}</td>
        <td>${safe(row.name)}</td>
        <td>${safe(row.school_id)}</td>
        <td>${safe(row.total_borrowed)}</td>
      </tr>
    `).join('') || '<tr><td colspan="4" class="text-center">No data yet.</td></tr>';
  }

  async function loadLandingContent() {
    try {
      const [postRes, lbRes] = await Promise.all([
        fetch('/api/landing/posts'),
        fetch('/api/monthly_leaderboard')
      ]);
      const postData = await postRes.json();
      const lbData = await lbRes.json();

      state.home = Array.isArray(postData.home) ? postData.home : [];
      state.news = Array.isArray(postData.news) ? postData.news : [];
      state.homeIndex = 0;
      state.newsIndex = 0;

      renderPost('home');
      renderPost('news');
      renderLeaderboard(Array.isArray(lbData.top_borrowers) ? lbData.top_borrowers : []);
    } catch (error) {
      console.error(error);
    }
  }

  document.getElementById('homePrevBtn')?.addEventListener('click', () => rotate('home', -1));
  document.getElementById('homeNextBtn')?.addEventListener('click', () => rotate('home', 1));
  document.getElementById('newsPrevBtn')?.addEventListener('click', () => rotate('news', -1));
  document.getElementById('newsNextBtn')?.addEventListener('click', () => rotate('news', 1));

  loadLandingContent();
})();
