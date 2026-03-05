let currentRole = 'student', 
        masterBooks = [], 
        masterUsers = [],
        masterAdmins = [],
        masterTransactions = [],
        masterCategories = [],
        masterApprovalRecords = [],
        masterRegistrationRequests = [],
        masterHomePosts = [],
        masterNewsPosts = [],
        adminHistory = JSON.parse(localStorage.getItem('adminHistory') || '[]'), 
        isStaff = false, 
        activeFilterCat = 'All',
        categoryToDelete = null,
        staffSessionID = localStorage.getItem('adminSchoolId') || '',
        staffSessionToken = localStorage.getItem('adminToken') || '';

    function getAuthToken() {
        const adminToken = localStorage.getItem('adminToken') || '';
        if (adminToken) return adminToken;
        if (staffSessionToken) return staffSessionToken;
        return localStorage.getItem('token') || '';
    }

    function getFallbackAuthToken() {
        const adminToken = localStorage.getItem('adminToken') || '';
        const legacyToken = localStorage.getItem('token') || '';
        const primary = getAuthToken();
        const candidates = [adminToken, staffSessionToken, legacyToken].filter(Boolean);
        return candidates.find((token) => token !== primary) || '';
    }

    function getAuthHeaders() {
        return {
            'Content-Type': 'application/json',
            'Authorization': getAuthToken()
        };
    }

    function setConnectionStatus(isOnline, message) {
        const syncDot = document.getElementById('syncDot');
        const statusText = document.getElementById('systemStateText');
        if (!syncDot || !statusText) return;
        syncDot.classList.toggle('sync-online', isOnline);
        statusText.innerText = message;
    }

    async function apiFetch(url, options = {}, requiresAuth = true) {
        const requestWithToken = async (authToken = '') => {
            const authHeaders = requiresAuth
                ? {
                    'Content-Type': 'application/json',
                    ...(authToken ? { 'Authorization': authToken } : {})
                }
                : { 'Content-Type': 'application/json' };

            const config = {
                ...options,
                headers: {
                    ...authHeaders,
                    ...(options.headers || {})
                }
            };

            return fetch(url, config);
        };

        const primaryToken = requiresAuth ? getAuthToken() : '';

        try {
            let response = await requestWithToken(primaryToken);
            if (response.status === 401 && requiresAuth) {
                const fallbackToken = getFallbackAuthToken();
                if (fallbackToken) {
                    response = await requestWithToken(fallbackToken);
                }
            }
            if (response.status === 401) {
                const unauthorizedError = new Error(`Unauthorized: ${url}`);
                unauthorizedError.code = 'UNAUTHORIZED';
                throw unauthorizedError;
            }
            if (!response.ok) {
                const apiError = new Error(`Request failed (${response.status}): ${url}`);
                apiError.code = 'API_ERROR';
                apiError.status = response.status;
                throw apiError;
            }
            return response;
        } catch (error) {
            console.error(error);
            if (!error.code) {
                error.code = 'NETWORK_ERROR';
            }
            throw error;
        }
    }

let editModal;
    let leaderboardProfileModal;
    let transactionDetailModal;
    let borrowModal;
    let registrationRequestModal;
    let dashboardInitialized = false;

    function initializeDashboard() {
        if (dashboardInitialized) return;
        dashboardInitialized = true;

        editModal = new bootstrap.Modal(document.getElementById('editModal'));
        leaderboardProfileModal = new bootstrap.Modal(document.getElementById('leaderboardProfileModal'));
        transactionDetailModal = new bootstrap.Modal(document.getElementById('transactionDetailModal'));
        borrowModal = new bootstrap.Modal(document.getElementById('borrowModal'));
        registrationRequestModal = new bootstrap.Modal(document.getElementById('registrationRequestModal'));

        mountAdminDropdown();
        bindDashboardDelegatedEvents();
        showAdminIntroStep('welcome');
        if(localStorage.getItem('isStaffAuth') === 'true') {
            executeUnlock(localStorage.getItem('adminName'), localStorage.getItem('adminPhoto'), localStorage.getItem('adminSchoolId'), localStorage.getItem('adminToken'));
        }
        loadData(true);
        heartbeatCheck();
        setInterval(updateLiveClock, 1000);
        setInterval(() => loadData(false), 10000);
        setInterval(heartbeatCheck, 5000);
        updateLiveClock();
    }

    function updateLiveClock() {
        const liveClock = document.getElementById('liveClock');
        if (!liveClock) return;
        liveClock.innerText = new Date().toLocaleTimeString();
    }

    function bindDashboardDelegatedEvents() {
        document.addEventListener('click', (e) => {
            const categoryButton = e.target.closest('.category-btn');
            if (!categoryButton) return;
            const { category } = categoryButton.dataset;
            if (!category) return;
            setCategoryFilter(category, categoryButton);
        });
    }

    document.addEventListener("DOMContentLoaded", function() {
        initializeDashboard();
    });

    async function loadData(resetFilter = false) {
        try {
            const preservedFilterCat = activeFilterCat;
            console.log('[ADMIN] fetch -> /api/admin/books /api/admin/users /api/admin/admins /api/admin/transactions /api/categories /api/admin/approval-records /api/admin/registration-requests');
            const [bRes, uRes, aRes, tRes, cRes, approvalRes, registrationRes] = await Promise.all([
                apiFetch('/api/admin/books', { method: 'GET' }, false),
                apiFetch('/api/admin/users', { method: 'GET' }, false), 
                apiFetch('/api/admin/admins', { method: 'GET' }, false),
                apiFetch('/api/admin/transactions', { method: 'GET' }, false),
                apiFetch('/api/categories', { method: 'GET' }, false),
                apiFetch('/api/admin/approval-records', { method: 'GET' }, false),
                apiFetch('/api/admin/registration-requests', { method: 'GET' }, false)
            ]);
            console.log('[ADMIN] fetch <- statuses', { books: bRes.status, users: uRes.status, admins: aRes.status, transactions: tRes.status, categories: cRes.status, approvals: approvalRes.status, registrations: registrationRes.status });

            masterBooks = await bRes.json();
            const allUsers = await uRes.json();
            masterAdmins = await aRes.json();
            masterTransactions = await tRes.json();
            masterCategories = await cRes.json();
            masterApprovalRecords = await approvalRes.json();
            masterRegistrationRequests = await registrationRes.json();

            if (!Array.isArray(masterBooks)) masterBooks = [];
            if (!Array.isArray(masterAdmins)) masterAdmins = [];
            if (!Array.isArray(masterTransactions)) masterTransactions = [];
            if (!Array.isArray(masterCategories)) masterCategories = [];
            if (!Array.isArray(masterApprovalRecords)) masterApprovalRecords = [];
            if (!Array.isArray(masterRegistrationRequests)) masterRegistrationRequests = [];
            const normalizedUsers = Array.isArray(allUsers) ? allUsers : [];
            
            masterUsers = normalizedUsers;

            setConnectionStatus(true, 'Live & Synced');
            activeFilterCat = resetFilter ? 'All' : preservedFilterCat;
            renderCategoryPills();
            filterInventory(); // Re-apply active category/search filters to fresh data
            syncMonitor();
            renderUsersList();
            renderRegistrationRequestBadge();
            renderRegistrationRequests();
            await loadLandingPostsForAdmin();
            renderBorrowedBooksList();
            renderBookRegistrationStats();
            await renderAdminHistory();
            
        } catch(e) { 
            console.error("Data Sync Failed", e); 
            if (e.code === 'UNAUTHORIZED') {
                setConnectionStatus(true, 'Unauthorized');
                return;
            }
            setConnectionStatus(false, 'Connection Lost');
        }
    }

    async function heartbeatCheck() {
        try {
            await apiFetch('/api/categories', { method: 'GET' }, false);
            setConnectionStatus(true, 'Live & Synced');
        } catch (error) {
            if (error.code === 'UNAUTHORIZED') {
                setConnectionStatus(true, 'Unauthorized');
                return;
            }
            setConnectionStatus(false, 'Connection Lost');
        }
    }

    // --- DYNAMIC CATEGORIES (NEW FEATURE) ---
    function renderCategoryPills() {
        const uniqueCats = [...new Set(masterCategories.map(c => String(c).trim()).filter(Boolean))].sort();
        const defaults = ['General', 'Mathematics', 'Science', 'Literature'];
        defaults.forEach(d => { if(!uniqueCats.includes(d)) uniqueCats.push(d); });

        const container = document.getElementById('categoryPillContainer');
        let html = `<button type="button" class="cat-pill category-btn ${activeFilterCat==='All'?'active':''}" data-category="All">All Collections</button>`;

        uniqueCats.forEach(cat => {
            const escapedCat = String(cat)
                .replace(/&/g, '&amp;')
                .replace(/"/g, '&quot;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            html += `<button type="button" class="cat-pill category-btn ${activeFilterCat===cat?'active':''}" data-category="${escapedCat}">${escapedCat}</button>`;
        });
        container.innerHTML = html;

        updateDropdowns(uniqueCats);
    }

    function setCategoryFilter(category, element) {
        activeFilterCat = category || 'All';
        const root = document.getElementById('categoryPillContainer');
        if (root) {
            root.querySelectorAll('.category-btn').forEach((pill) => {
                pill.classList.toggle('active', pill.dataset.category === activeFilterCat);
            });
        }
        if (element && element.classList.contains('category-btn')) {
            element.classList.add('active');
        }
        filterInventory();
    }

    function updateDropdowns(categories) {
        const bulkSel = document.getElementById('batchCategorySelect');
        const editSel = document.getElementById('editCategory');
        if (!bulkSel || !editSel) return;

        const escapeOption = (value) => String(value)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        const currentBulk = bulkSel.value;
        bulkSel.innerHTML = categories.map(c => `<option value="${escapeOption(c)}">Target: ${escapeOption(c)}</option>`).join('');
        bulkSel.value = categories.includes(currentBulk) ? currentBulk : (categories[0] || 'General');

        const currentEdit = editSel.value;
        editSel.innerHTML = categories.map(c => `<option value="${escapeOption(c)}">${escapeOption(c)}</option>`).join('');
        editSel.value = categories.includes(currentEdit) ? currentEdit : (categories[0] || 'General');
    }

    async function addCustomCategory() {
        const newCat = prompt("Enter Name for New Category:");
        if(!newCat || newCat.trim() === "") return;

        try {
            const res = await apiFetch('/api/categories', {
                method: 'POST',
                body: JSON.stringify({ category: newCat.trim() })
            }, false);
            const data = await res.json();
            if (!data.success) {
                alert(data.message || 'Unable to add category.');
                return;
            }
            await loadData();
            const savedCategory = (Array.isArray(data.categories)
                ? data.categories.find((cat) => String(cat).trim().toLowerCase() === newCat.trim().toLowerCase())
                : null) || newCat.trim();
            document.getElementById('batchCategorySelect').value = savedCategory;
        } catch (error) {
            console.error(error);
            alert('Unable to add category.');
        }
    }

    function confirmDeleteCategoryFromDropdown(){
        const select = document.getElementById('batchCategorySelect');
        const selectedCategory = select.value;

        if(!selectedCategory || selectedCategory === 'All'){
            alert('This category cannot be deleted.');
            return;
        }

        categoryToDelete = selectedCategory;
        const modal = new bootstrap.Modal(
            document.getElementById('deleteCategoryModal')
        );
        modal.show();
    }

    async function executeCategoryDelete(){
        if(!categoryToDelete) return;
        try {
            const res = await apiFetch('/api/delete_category',{
                method:'POST',
                body:JSON.stringify({category:categoryToDelete})
            });

            const data = await res.json();

            if(data.success){
                activeFilterCat = 'All';
                loadData(true);
            } else {
                alert('Delete failed.');
            }
        } catch (error) {
            console.error(error);
            alert('Delete failed.');
        }

        const modal = bootstrap.Modal.getInstance(document.getElementById('deleteCategoryModal'));
        if (modal) modal.hide();
        categoryToDelete = null;
    }

    // --- BULK REGISTER (FIXED) ---
    async function submitBulk() {
        const text = document.getElementById('bulkArea').value;
        if(!text.trim()) return alert("Please enter book data.");

        try {
            const res = await apiFetch('/api/bulk_register', {
                method: 'POST',
                body: JSON.stringify({
                    text: text,
                    category: document.getElementById('batchCategorySelect').value,
                    clear_first: document.getElementById('wipeCheck').checked
                })
            });
            const data = await res.json();
            
            if(data.success) {
                // Handle both legacy and new backend keys
                const count = data.items_added || data.added || 0;
                addHistory(`Bulk Import: ${count} books added`);
                alert(`Success! ${count} books registered.`);
                loadData(); // Force refresh
                document.getElementById('bulkArea').value = ''; // Clear input
            } else {
                alert("Error: " + (data.message || "Import failed. Check console."));
            }
        } catch (error) {
            console.error(error);
            alert('Import failed. Check console.');
        }
    }

    // --- STANDARD UI LOGIC (RETAINED) ---

    function switchView(view) {
        document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active', 'text-white'));
        document.querySelectorAll('.nav-link').forEach(l => l.classList.add('text-white-50'));

        const linkMap = {
            'console': { id: 'linkConsole', title: 'Command Dashboard' },
            'users': { id: 'linkUsers', title: 'User Directory' },
            'registrationRequests': { id: 'linkRegistrationRequests', title: 'Registration Request List' },
            'inventory': { id: 'linkInventory', title: 'Inventory Manager' },
            'postHome': { id: 'linkPostHome', title: 'Post for Home' },
            'postNews': { id: 'linkPostNews', title: 'Post News' },
            'leaderboard': { id: 'linkLeaderboard', title: 'Monthly Leaderboards' },
            'dateRestrictions': { id: 'linkDateRestrictions', title: 'Date Restriction Calendar' }
        };

        const target = linkMap[view];
        if(view === 'leaderboard' && !isStaff) {
            alert('Security Lock Active');
            return;
        }
        if(target) {
            document.getElementById(view + 'View').classList.add('active');
            const link = document.getElementById(target.id);
            link.classList.add('active', 'text-white');
            link.classList.remove('text-white-50');
            document.getElementById('viewTitle').innerText = target.title;
        }
        if(view === 'leaderboard') loadAdminLeaderboards();
        if(view === 'dateRestrictions') loadDateRestrictions();
        if(view === 'postHome') renderAdminLandingPosts('home');
        if(view === 'postNews') renderAdminLandingPosts('news');
    }


    async function loadLandingPostsForAdmin() {
        try {
            const [homeRes, newsRes] = await Promise.all([
                apiFetch('/api/admin/landing/home'),
                apiFetch('/api/admin/landing/news')
            ]);
            const homeData = await homeRes.json();
            const newsData = await newsRes.json();
            masterHomePosts = Array.isArray(homeData.posts) ? homeData.posts : [];
            masterNewsPosts = Array.isArray(newsData.posts) ? newsData.posts : [];
            renderAdminLandingPosts('home');
            renderAdminLandingPosts('news');
        } catch (error) {
            console.error(error);
        }
    }

    function renderAdminLandingPosts(section) {
        const isHome = section === 'home';
        const posts = isHome ? masterHomePosts : masterNewsPosts;
        const root = document.getElementById(isHome ? 'homeAdminPostGrid' : 'newsAdminPostGrid');
        if (!root) return;
        root.innerHTML = posts.map((post) => `
            <article class="admin-post-card-item">
                <span class="post-id-chip">${post.post_id || ''}</span>
                <div class="post-actions-top-right">
                    <button class="btn btn-sm btn-outline-warning" onclick="editLandingPost('${section}', '${String(post.post_id).replace(/'/g, "\'")}')">edit</button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteLandingPost('${section}', '${String(post.post_id).replace(/'/g, "\'")}')">x</button>
                </div>
                ${post.image ? `<img src="/LandingUploads/${encodeURIComponent(post.image)}" class="admin-post-thumb">` : ''}
                ${post.document ? `<a class="btn btn-sm btn-outline-primary mt-2" href="/LandingUploads/${encodeURIComponent(post.document)}" target="_blank">Document</a>` : ''}
                <p class="small mb-0 mt-2">${post.text || ''}</p>
            </article>
        `).join('') || '<p class="text-muted">No posts yet.</p>';
    }

    async function submitLandingPost(section) {
        const isHome = section === 'home';
        const idInput = document.getElementById(isHome ? 'homePostId' : 'newsPostId');
        const textInput = document.getElementById(isHome ? 'homePostText' : 'newsPostText');
        const imageInput = document.getElementById('homePostImage');
        const documentInput = document.getElementById('newsPostDocument');

        const form = new FormData();
        form.append('post_id', idInput.value.trim());
        form.append('text', textInput.value.trim());
        if (isHome && imageInput?.files?.[0]) form.append('image', imageInput.files[0]);
        if (!isHome && documentInput?.files?.[0]) {
            const file = documentInput.files[0];
            if ((file.type || '').startsWith('image/')) form.append('image', file);
            else form.append('document', file);
        }

        try {
            const res = await fetch(`/api/admin/landing/${section}`, {
                method: 'POST',
                headers: { 'Authorization': getAuthToken() },
                body: form
            });
            const data = await res.json();
            if (!res.ok || !data.success) return alert(data.message || 'Unable to post.');
            if (isHome) { masterHomePosts = data.posts || []; imageInput.value=''; }
            else { masterNewsPosts = data.posts || []; documentInput.value=''; }
            idInput.value = '';
            textInput.value = '';
            renderAdminLandingPosts(section);
        } catch (error) {
            console.error(error);
            alert('Unable to post.');
        }
    }

    async function deleteLandingPost(section, postId) {
        if (!confirm(`Delete post ${postId}?`)) return;
        try {
            const res = await apiFetch(`/api/admin/landing/${section}/${encodeURIComponent(postId)}`, { method: 'DELETE' });
            const data = await res.json();
            if (section === 'home') masterHomePosts = data.posts || [];
            else masterNewsPosts = data.posts || [];
            renderAdminLandingPosts(section);
        } catch (error) {
            console.error(error);
            alert('Delete failed.');
        }
    }

    async function editLandingPost(section, postId) {
        const existing = (section === 'home' ? masterHomePosts : masterNewsPosts).find((item) => String(item.post_id) === String(postId));
        const updated = prompt('Edit post text:', existing?.text || '');
        if (updated === null) return;
        try {
            const res = await apiFetch(`/api/admin/landing/${section}/${encodeURIComponent(postId)}`, {
                method: 'PUT',
                body: JSON.stringify({ text: updated })
            });
            const data = await res.json();
            if (section === 'home') masterHomePosts = data.posts || [];
            else masterNewsPosts = data.posts || [];
            renderAdminLandingPosts(section);
        } catch (error) {
            console.error(error);
            alert('Update failed.');
        }
    }

    function renderUsersList() {
        const query = document.getElementById('userSearch').value.toLowerCase();
        const typeFilter = document.getElementById('userTypeFilter').value;
        const tbody = document.getElementById('usersListBody');
        let combined = [...masterUsers.map(u => ({...u, type: 'student'})), ...masterAdmins.map(a => ({...a, type: 'admin'}))];
        const filtered = combined.filter(u => (u.name.toLowerCase().includes(query) || u.school_id.includes(query)) && (typeFilter === 'all' || u.type === typeFilter));

        tbody.innerHTML = filtered.map(u => `
            <tr>
                <td class="ps-4"><img src="/Profile/${u.photo || 'default.png'}" class="user-row-img shadow-sm"></td>
                <td><code class="fw-bold text-dark">${u.school_id}</code></td>
                <td class="fw-bold">${u.name}</td>
                <td><span class="badge ${u.type === 'admin' ? 'bg-danger' : 'bg-primary'}">${u.type.toUpperCase()}</span></td>
                <td><span class="status-pill badge-available">Active</span></td>
                <td class="text-end pe-4"><i class='fas fa-eye text-muted'></i></td>
            </tr>`).join('') || '<tr><td colspan="6" class="text-center py-5 text-muted">No records found.</td></tr>';
    }

    function setQuickRegisterRole(role) {
        currentRole = role === 'admin' ? 'admin' : 'student';
        document.getElementById('btnStudent')?.classList.toggle('active', currentRole === 'student');
        document.getElementById('btnAdmin')?.classList.toggle('active', currentRole === 'admin');
    }

    async function submitQuickRegister() {
        if (!isStaff) return alert('System Locked');

        const name = document.getElementById('quickRegName')?.value.trim();
        const school_id = document.getElementById('quickRegID')?.value.trim();
        const password = document.getElementById('quickRegPass')?.value;
        const photo = document.getElementById('quickRegPhoto')?.files?.[0];

        if (!name || !school_id || !password) {
            alert('Please complete name, ID, and password.');
            return;
        }

        const form = new FormData();
        form.append('name', name);
        form.append('school_id', school_id);
        form.append('password', password);
        if (photo) form.append('photo', photo);

        const endpoint = currentRole === 'admin' ? '/api/register_librarian' : '/api/register_student';
        try {
            const res = await fetch(endpoint, { method: 'POST', body: form });
            const data = await res.json();
            if (!res.ok || !data.success) {
                alert(data.message || 'Registration failed.');
                return;
            }
            alert(`Successfully created ${currentRole} account.`);
            ['quickRegName', 'quickRegID', 'quickRegPass', 'quickRegPhoto'].forEach((id) => {
                const input = document.getElementById(id);
                if (input) input.value = '';
            });
            loadData();
        } catch (error) {
            console.error(error);
            alert('Unable to submit quick registration right now.');
        }
    }


    function getRegistrationRequestCounts() {
        const rows = Array.isArray(masterRegistrationRequests) ? masterRegistrationRequests : [];
        const pending = rows.filter((row) => String(row.status || 'pending').toLowerCase() === 'pending').length;
        const nonRejected = rows.filter((row) => String(row.status || 'pending').toLowerCase() !== 'rejected').length;
        return { pending, nonRejected };
    }

    function renderRegistrationRequestBadge() {
        const badge = document.getElementById('registrationRequestBadge');
        if (!badge) return;
        const { pending } = getRegistrationRequestCounts();
        if (pending > 0) {
            badge.style.display = 'inline-flex';
            badge.innerText = String(pending);
        } else {
            badge.style.display = 'none';
            badge.innerText = '0';
        }
    }

    function renderRegistrationRequests() {
        const body = document.getElementById('registrationRequestsBody');
        if (!body) return;

        const requests = (masterRegistrationRequests || [])
            .filter((row) => String(row.status || 'pending').toLowerCase() === 'pending')
            .reverse();

        body.innerHTML = requests.map((row) => `
            <tr>
                <td class="ps-4"><code class="fw-bold text-dark">${row.request_id || '-'}</code></td>
                <td><img src="/Profile/${row.photo || 'default.png'}" class="user-row-img shadow-sm"></td>
                <td class="fw-bold">${row.name || '-'}</td>
                <td><code class="fw-bold text-dark">${row.school_id || '-'}</code></td>
                <td>
                    <button class="btn btn-sm btn-outline-primary rounded-pill px-3" onclick="openRegistrationRequest('${row.request_id}')">Open</button>
                </td>
            </tr>
        `).join('') || '<tr><td colspan="5" class="text-center py-4 text-muted">No pending registration requests.</td></tr>';
    }

    function openRegistrationRequest(requestID) {
        const row = (masterRegistrationRequests || []).find((req) => req.request_id === requestID);
        if (!row) return alert('Request not found.');

        document.getElementById('registrationRequestModalBody').innerHTML = `
            <div class="small">
                <div class="text-center mb-3">
                    <img src="/Profile/${row.photo || 'default.png'}" class="rounded-circle shadow-sm" style="width:90px;height:90px;object-fit:cover;" alt="profile">
                </div>
                <div><span class="fw-bold text-dark">Request ID:</span> ${row.request_id || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Profile Name:</span> ${row.name || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">ID:</span> ${row.school_id || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Requested Role:</span> ${(row.role || 'student').toUpperCase()}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Created:</span> ${row.created_at || '-'}</div>
            </div>
            <div class="d-flex gap-2 mt-4">
                <button class="btn btn-success w-100" onclick="reviewRegistrationRequest('${row.request_id}', 'approve')">Approve</button>
                <button class="btn btn-danger w-100" onclick="reviewRegistrationRequest('${row.request_id}', 'reject')">Reject</button>
            </div>
        `;
        registrationRequestModal.show();
    }

    async function reviewRegistrationRequest(requestID, decision) {
        if (!isStaff) return alert('System Locked');
        try {
            const res = await apiFetch(`/api/admin/registration-requests/${requestID}/decision`, {
                method: 'POST',
                body: JSON.stringify({ decision })
            }, false);
            const data = await res.json();
            if (!data.success) {
                alert(data.message || 'Unable to update request.');
                return;
            }
            registrationRequestModal.hide();
            alert(`Request ${requestID} ${decision}d.`);
            loadData();
        } catch (error) {
            console.error(error);
            alert('Unable to process request right now.');
        }
    }

    function renderInventory(data) {
        const tbody = document.getElementById('inventoryBody');
        tbody.innerHTML = data.map(b => `
            <tr>
                <td width="150" class="ps-4"><code class="inventory-code">${b.book_no}</code></td>
                <td><div class="inventory-title">${b.title}</div><div class="small text-muted text-uppercase fw-bold" style="font-size:0.65rem">${b.category}</div></td>
                <td><span class="status-pill badge-${b.status.toLowerCase()}">${b.status}</span></td>
                <td class="text-end pe-4">${isStaff ? `<button class="btn btn-sm btn-light border me-1 inventory-action" onclick="openEdit('book', '${b.book_no}', '${b.title}', '${b.category}')"><i class="fas fa-pen"></i></button> <button class="btn btn-sm btn-light border inventory-action" onclick="deleteRecord('book', '${b.book_no}')"><i class="fas fa-trash"></i></button>` : ''}</td>
            </tr>`).join('');
    }

    function renderBorrowedBooksList() {
        const body = document.getElementById('borrowedBooksBody');
        if (!body) return;

        const borrowedRows = getSyncedBorrowedApprovalRows();

        body.innerHTML = borrowedRows.map((row, index) => {
            const recordKey = row.request_id || `${row.book_no || 'book'}-${index}`;
            return `<tr>
                <td class="ps-4"><code class="fw-bold text-dark">${row.book_no || '-'}</code></td>
                <td class="small fw-bold">${row.title || '-'}</td>
                <td>${row.borrower_name || row.school_id || '-'}</td>
                <td>${row.date || '-'}</td>
                <td>${row.expiry || '-'}</td>
                <td class="text-end pe-4">${isStaff ? `<button class="btn btn-sm btn-outline-primary rounded-pill px-3" onclick="showApprovalBorrowInfo('${recordKey}')">Info</button>` : `<i class="fas fa-lock text-muted"></i>`}</td>
            </tr>`;
        }).join('') || '<tr><td colspan="6" class="text-center py-4 text-muted">No borrowed approvals found.</td></tr>';
    }

    function getSyncedBorrowedApprovalRows() {
        const borrowedTransactionKeys = new Set(
            (Array.isArray(masterTransactions) ? masterTransactions : [])
                .filter((tx) => normalizeStatus(tx.status) === 'borrowed')
                .map((tx) => [
                    String(tx.request_id || '').trim(),
                    String(tx.book_no || '').trim(),
                    String(tx.school_id || '').trim().toLowerCase()
                ].join('|'))
        );

        return (Array.isArray(masterApprovalRecords) ? masterApprovalRecords : [])
            .filter((row) => {
                if (normalizeStatus(row.status) !== 'borrowed') return false;
                const rowKey = [
                    String(row.request_id || '').trim(),
                    String(row.book_no || '').trim(),
                    String(row.school_id || '').trim().toLowerCase()
                ].join('|');
                return borrowedTransactionKeys.has(rowKey);
            })
            .reverse();
    }

    function showApprovalBorrowInfo(recordKey) {
        const record = getSyncedBorrowedApprovalRows().find((row, index) => {
            const rowKey = row.request_id || `${row.book_no || 'book'}-${index}`;
            return rowKey === recordKey;
        });
        if (!record) return alert('Borrowed approval record not found.');

        document.getElementById('transactionModalTitle').innerText = `Borrowed Approval • ${record.book_no || '-'}`;
        document.getElementById('transactionModalBody').innerHTML = `
            <div class="small">
                <div><span class="fw-bold text-dark">Book:</span> ${record.title || '-'} (${record.book_no || '-'})</div>
                <div class="mt-1"><span class="fw-bold text-dark">Borrower:</span> ${record.borrower_name || '-'} (${record.school_id || '-'})</div>
                <div class="mt-1"><span class="fw-bold text-dark">Phone:</span> ${record.phone_number || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Pickup Date:</span> ${record.pickup_schedule || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Borrowed Date:</span> ${record.date || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Return Due:</span> ${record.expiry || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Request ID:</span> ${record.request_id || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Approved By:</span> ${record.approved_by || '-'}</div>
            </div>`;
        transactionDetailModal.show();
    }

    function renderBookRegistrationStats() {
        const target = document.getElementById('bookRegistrationStats');
        if (!target) return;
        const total = masterBooks.length;
        const borrowedFromBooks = masterBooks.filter((book) => normalizeStatus(book.status) === 'borrowed').length;
        const reservedFromBooks = masterBooks.filter((book) => normalizeStatus(book.status) === 'reserved').length;
        const available = masterBooks.filter((book) => normalizeStatus(book.status) === 'available').length;
        const reservedFromTransactions = new Set(
            masterTransactions
                .filter((tx) => normalizeStatus(tx.status) === 'reserved')
                .map((tx) => String(tx.book_no || '').trim())
                .filter(Boolean)
        ).size;
        const borrowedFromTransactions = new Set(
            masterTransactions
                .filter((tx) => normalizeStatus(tx.status) === 'borrowed')
                .map((tx) => String(tx.book_no || '').trim())
                .filter(Boolean)
        ).size;
        const reserved = Math.max(reservedFromBooks, reservedFromTransactions);
        const borrowed = Math.max(borrowedFromBooks, borrowedFromTransactions);
        const { pending: pendingRegistrationRequests, nonRejected: activeRegistrationRequests } = getRegistrationRequestCounts();
        const categoryCounts = masterBooks.reduce((acc, book) => {
            const category = String(book.category || '').trim() || 'Uncategorized';
            acc[category] = (acc[category] || 0) + 1;
            return acc;
        }, {});
        const categories = Object.keys(categoryCounts).length;
        const categoryCards = Object.entries(categoryCounts)
            .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
            .map(([category, count]) => `
                <div class="col-sm-6 col-lg-4">
                    <div class="registration-stat-card">
                        <div class="registration-stat-label">${category}</div>
                        <div class="registration-stat-value">${count}</div>
                    </div>
                </div>`)
            .join('');

        target.innerHTML = `
            <div class="row g-3">
                <div class="col-md-6 col-lg-3"><div class="registration-stat-card"><div class="registration-stat-label">Overall Books</div><div class="registration-stat-value">${total}</div></div></div>
                <div class="col-md-6 col-lg-3"><div class="registration-stat-card"><div class="registration-stat-label">Total Categories</div><div class="registration-stat-value">${categories}</div></div></div>
                <div class="col-md-6 col-lg-2"><div class="registration-stat-card"><div class="registration-stat-label">Available</div><div class="registration-stat-value">${available}</div></div></div>
                <div class="col-md-6 col-lg-2"><div class="registration-stat-card"><div class="registration-stat-label">Reserved</div><div class="registration-stat-value">${reserved}</div></div></div>
                <div class="col-md-6 col-lg-2"><div class="registration-stat-card"><div class="registration-stat-label">Borrowed</div><div class="registration-stat-value">${borrowed}</div></div></div>
                <div class="col-md-6 col-lg-3"><div class="registration-stat-card"><div class="registration-stat-label">Registration Request (Pending)</div><div class="registration-stat-value">${pendingRegistrationRequests}</div></div></div>
                <div class="col-md-6 col-lg-3"><div class="registration-stat-card"><div class="registration-stat-label">Registration Request (Not Rejected)</div><div class="registration-stat-value">${activeRegistrationRequests}</div></div></div>
            </div>
            <div class="row g-3 mt-1">
                ${categoryCards || '<div class="col-12"><div class="registration-stat-card text-center">No registered categories yet.</div></div>'}
            </div>`;
    }

    function openEdit(type, id, name, extra) {
        document.getElementById('editType').value = type;
        document.getElementById('editID').value = id;
        document.getElementById('editName').value = name;
        const bookFields = document.getElementById('bookOnlyFields');
        if(type === 'book') {
            bookFields.style.display = 'block';
            document.getElementById('editCategory').value = extra;
        } else {
            bookFields.style.display = 'none';
            document.getElementById('editID').dataset.role = extra;
        }
        editModal.show();
    }

    async function saveEdits() {
        const type = document.getElementById('editType').value;
        const id = document.getElementById('editID').value;
        const name = document.getElementById('editName').value;
        let endpoint = type === 'book' ? '/api/update_book' : '/api/update_member';
        let payload = type === 'book' ? { book_no: id, title: name, category: document.getElementById('editCategory').value } : { school_id: id, name: name, type: document.getElementById('editID').dataset.role };
        try {
            const res = await apiFetch(endpoint, { method: 'POST', body: JSON.stringify(payload) });
            if((await res.json()).success) { editModal.hide(); addHistory(`Updated ${type}: ${id}`); loadData(); }
        } catch (error) {
            console.error(error);
        }
    }

    async function deleteRecord(type, id, role = '') {
        if(!confirm(`Delete ${type} ${id}?`)) return;
        let endpoint = type === 'book' ? '/api/delete_book' : '/api/delete_member';
        let payload = type === 'book' ? { book_no: id } : { school_id: id, type: role };
        try {
            const res = await apiFetch(endpoint, { method: 'POST', body: JSON.stringify(payload) });
            if((await res.json()).success) { addHistory(`Deleted ${type}: ${id}`); loadData(); }
        } catch (error) {
            console.error(error);
        }
    }

    async function attemptLogin() {
        const u = document.getElementById('loginUser').value;
        const p = document.getElementById('loginPass').value;
        try {
            const res = await apiFetch('/api/login', { method: 'POST', body: JSON.stringify({ school_id: u, password: p, id_only: false }) }, false);
            const data = await res.json();
            if(data.success && data.profile.is_staff) {
                localStorage.setItem('isStaffAuth', 'true');
                localStorage.setItem('adminName', data.profile.name);
                localStorage.setItem('adminPhoto', data.profile.photo);
                localStorage.setItem('adminSchoolId', data.profile.school_id || u);
                localStorage.setItem('token', data.token || '');
                localStorage.setItem('adminToken', data.token || '');
                executeUnlock(data.profile.name, data.profile.photo, data.profile.school_id || u, data.token || '');
            } else { showLoginError(); }
        } catch (e) { console.error(e); showLoginError(); }
    }

    const adminIntroSteps = ['welcome', 'manual', 'login'];

    function showAdminIntroStep(step) {
        const welcome = document.getElementById('adminWelcomeStep');
        const manual = document.getElementById('adminManualStep');
        const login = document.getElementById('loginForm');
        const prev = document.getElementById('adminPrevBtn');
        const next = document.getElementById('adminNextBtn');
        if (!welcome || !manual || !login) return;

        welcome.classList.remove('active');
        manual.classList.remove('active');
        login.classList.remove('active');

        if (step === 'manual') {
            manual.classList.add('active');
            if (prev) prev.disabled = false;
            if (next) next.disabled = false;
            return;
        }
        if (step === 'login') {
            login.classList.add('active');
            if (prev) prev.disabled = false;
            if (next) next.disabled = true;
            return;
        }

        welcome.classList.add('active');
        if (prev) prev.disabled = true;
        if (next) next.disabled = false;
    }

    function shiftAdminIntroStep(direction) {
        const activeStep = adminIntroSteps.find((stepName) => {
            const map = {
                welcome: 'adminWelcomeStep',
                manual: 'adminManualStep',
                login: 'loginForm'
            };
            const el = document.getElementById(map[stepName]);
            return el && el.classList.contains('active');
        }) || 'welcome';

        const nextIndex = Math.min(Math.max(adminIntroSteps.indexOf(activeStep) + direction, 0), adminIntroSteps.length - 1);
        showAdminIntroStep(adminIntroSteps[nextIndex]);
    }

    function executeUnlock(name, photo, schoolId = '', token = '') {
        isStaff = true;
        staffSessionID = (schoolId || localStorage.getItem('adminSchoolId') || '').toLowerCase();
        staffSessionToken = token || localStorage.getItem('adminToken') || '';
        if (staffSessionToken) {
            localStorage.setItem('adminToken', staffSessionToken);
            localStorage.setItem('token', staffSessionToken);
        }
        document.getElementById('mainBody').classList.add('is-unlocked');
        document.getElementById('adminWelcomeStep')?.classList.remove('active');
        document.getElementById('adminManualStep')?.classList.remove('active');
        document.getElementById('loginForm')?.classList.remove('active');
        document.getElementById('adminProfile').style.display = 'block';
        document.getElementById('activeAdminName').innerText = name;
        document.getElementById('headerAvatar').src = `/Profile/${photo}`;
        document.getElementById('activeAdminPhoto').src = `/Profile/${photo}`;
        document.getElementById('authStatusBadge').className = "alert alert-success py-2 small fw-bold text-center border-0 shadow-sm rounded-4";
        document.getElementById('authStatusBadge').innerHTML = '<i class="fas fa-check-circle me-2"></i>AUTHORIZED';
        const link = document.getElementById('linkLeaderboard');
        if (link) link.style.display = 'block';
        const linkDateRestrictions = document.getElementById('linkDateRestrictions');
        if (linkDateRestrictions) linkDateRestrictions.style.display = 'block';
        addHistory(`System Unlocked by: ${name}`);
        loadData(true);
    }

    function findMemberById(schoolId) {
        const sid = String(schoolId || '').toLowerCase();
        return [...masterUsers, ...masterAdmins].find(u => String(u.school_id || '').toLowerCase() === sid) || null;
    }

    function parseTxDate(tx) {
        const raw = tx?.date || tx?.reserved_at || '';
        if (!raw) return 0;
        const normalized = raw.replace(' ', 'T');
        const value = Date.parse(normalized);
        return Number.isNaN(value) ? 0 : value;
    }

    function normalizeStatus(value) {
        return String(value || '').trim().toLowerCase();
    }

    function getLatestTransactionForBook(bookNo, statuses = ['Reserved', 'Borrowed']) {
        const normalizedStatuses = statuses.map((status) => normalizeStatus(status));
        return masterTransactions
            .filter((t) => t.book_no === bookNo && normalizedStatuses.includes(normalizeStatus(t.status)))
            .sort((a, b) => parseTxDate(b) - parseTxDate(a))[0] || null;
    }

    function showTransactionInfo(bookNo) {
        const transaction = getLatestTransactionForBook(bookNo, ['Reserved', 'Borrowed']);
        if (!transaction) return;
        const member = findMemberById(transaction.school_id) || {};
        document.getElementById('transactionModalTitle').innerText = 'Borrower Profile & Book Details';
        document.getElementById('transactionModalBody').innerHTML = `
            <div class="d-flex align-items-center gap-3 mb-3">
                <img src="/Profile/${member.photo || 'default.png'}" class="rounded-circle" style="width:58px;height:58px;object-fit:cover;" alt="profile">
                <div>
                    <div class="fw-bold text-dark">${member.name || transaction.borrower_name || transaction.school_id}</div>
                    <div class="small text-muted">ID: ${transaction.school_id || '-'}</div>
                </div>
            </div>
            <div class="border rounded-3 p-3 bg-light">
                <div><span class="fw-bold text-dark">Book No:</span> <code>${transaction.book_no || '-'}</code></div>
                <div class="mt-1"><span class="fw-bold text-dark">Title:</span> ${transaction.title || 'Unknown Title'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Reservation Date:</span> ${transaction.date || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Pickup Date:</span> ${transaction.pickup_schedule || 'Not specified'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Return Date:</span> ${transaction.expiry || 'Not set yet'}</div>
            </div>`;
        transactionDetailModal.show();
    }

    function showBorrowedInfo(bookNo) {
        const transaction = getLatestTransactionForBook(bookNo, ['Borrowed']);
        if (!transaction) {
            alert('Borrowed details are available once the reservation is converted to Borrowed.');
            return;
        }
        document.getElementById('transactionModalTitle').innerText = 'Borrowed Schedule';
        document.getElementById('transactionModalBody').innerHTML = `
            <div class="border rounded-3 p-3 bg-light">
                <div><span class="fw-bold text-dark">Book:</span> <code>${transaction.book_no || '-'}</code> - ${transaction.title || 'Unknown Title'}</div>
                <div class="mt-2"><span class="fw-bold text-dark">Borrowed Date:</span> ${transaction.date || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Return Due Date:</span> ${transaction.expiry || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Reserved At:</span> ${transaction.reserved_at || transaction.date || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Pickup Schedule:</span> ${transaction.pickup_schedule || 'Not specified'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Approved By:</span> ${transaction.approved_by || '-'}</div>
                <div class="mt-1"><span class="fw-bold text-dark">Request ID:</span> ${transaction.request_id || '-'}</div>
            </div>`;
        transactionDetailModal.show();
    }

    function openBorrowForm(bookNo) {
        const transaction = getLatestTransactionForBook(bookNo, ['Reserved']);
        if (!transaction) return alert('No active reservation found.');
        const approvedBy = `${localStorage.getItem('adminName') || 'Librarian'} (${localStorage.getItem('adminSchoolId') || '-'})`;
        document.getElementById('borrowBookNo').value = bookNo;
        document.getElementById('borrowerName').value = transaction.borrower_name || '-';
        document.getElementById('borrowerId').value = transaction.school_id || '-';
        document.getElementById('borrowerPhone').value = transaction.phone_number || '-';
        document.getElementById('borrowBookCode').value = transaction.book_no || '-';
        document.getElementById('borrowBookTitle').value = transaction.title || 'Unknown Title';
        document.getElementById('borrowPickupDate').value = transaction.pickup_schedule || transaction.date || '-';
        document.getElementById('borrowApprovedBy').value = approvedBy;
        document.getElementById('borrowRequestId').value = transaction.request_id || `REQ-${Date.now().toString(36).toUpperCase()}`;
        const pickupDate = String(transaction.pickup_schedule || '').trim();
        const returnDateInput = document.getElementById('borrowReturnDate');
        returnDateInput.value = '';
        returnDateInput.dataset.minPickupDate = pickupDate;
        if (pickupDate) {
            returnDateInput.min = pickupDate;
        } else {
            returnDateInput.removeAttribute('min');
        }
        borrowModal.show();
    }

    function validateBorrowReturnDateSelection() {
        const returnDateInput = document.getElementById('borrowReturnDate');
        const minPickupDate = String(returnDateInput.dataset.minPickupDate || '').trim();
        const selectedDate = String(returnDateInput.value || '').trim();
        if (minPickupDate && selectedDate && selectedDate < minPickupDate) {
            alert('You have picked backward! Pick a date forward!');
            returnDateInput.value = '';
            return false;
        }
        return true;
    }

    async function submitBorrowForm() {
        const b_no = document.getElementById('borrowBookNo').value;
        const return_due_date = document.getElementById('borrowReturnDate').value;
        const approved_by = document.getElementById('borrowApprovedBy').value;
        const request_id = document.getElementById('borrowRequestId').value;
        if (!return_due_date) return alert('Please set return date.');
        if (!validateBorrowReturnDateSelection()) return;
        try {
            const res = await apiFetch('/api/process_transaction', { method: 'POST', body: JSON.stringify({ book_no: b_no, action: 'borrow', return_due_date, approved_by, request_id }) });
            const data = await res.json();
            if (!data.success) return alert(data.message || 'Unable to borrow book.');
            borrowModal.hide();
            addHistory(`Borrowed Book: ${b_no}`);
            loadData();
        } catch (error) {
            console.error(error);
            alert('Unable to borrow book.');
        }
    }

    document.getElementById('borrowReturnDate')?.addEventListener('change', validateBorrowReturnDateSelection);

    async function syncMonitor() {
        const active = masterTransactions.filter((t) => {
            const status = normalizeStatus(t.status);
            return status === 'borrowed' || status === 'reserved';
        });
        document.getElementById('monitorBody').innerHTML = active.map((t) => {
            const status = normalizeStatus(t.status);
            const statusLabel = status ? `${status.charAt(0).toUpperCase()}${status.slice(1)}` : 'Unknown';
            const isReserved = status === 'reserved';
            return `<tr><td class="ps-4"><code class="fw-bold text-dark">${t.book_no}</code></td><td class="small fw-bold">${t.title || 'Unknown Title'}</td><td>${t.borrower_name || '-'}</td><td class="small fw-bold">${t.school_id || '-'}</td><td>${isReserved ? (t.pickup_schedule || t.date || '-') : (t.expiry || '-')}</td><td><span class="status-pill badge-${status || 'unknown'}">${statusLabel}</span></td><td class="text-end pe-4">${isStaff ? `<div class="d-flex gap-1 justify-content-end"><button class="btn btn-sm btn-light border rounded-pill px-3" onclick="showTransactionInfo('${t.book_no}')">Info</button><button class="btn btn-sm btn-primary rounded-pill px-3" ${!isReserved ? 'disabled' : ''} onclick="openBorrowForm('${t.book_no}')">Borrowed</button><button class="btn btn-sm btn-danger rounded-pill px-3" onclick="cancelReservation('${t.book_no}', '${t.school_id || ''}', '${t.request_id || ''}', '${status}')">Release</button></div>` : `<i class="fas fa-lock text-muted"></i>`}</td></tr>`;
        }).join('') || '<tr><td colspan="7" class="text-center py-4 text-muted">No active transactions.</td></tr>';
        updateTimers();
    }


    // --- NEW: Leaderboard API rendering (independent from inventory refresh) ---
    async function loadAdminLeaderboards() {
        if (!isStaff) return;
        try {
            const leaderboardRes = await apiFetch('/api/monthly_leaderboard');
            const leaderboard = await leaderboardRes.json();
            const borrowers = leaderboard.top_borrowers || [];
            const books = leaderboard.top_books || [];

            document.getElementById('topBorrowersBody').innerHTML = borrowers.map((r, i) => `
                <tr role="button" onclick="openLeaderboardProfile('${r.school_id}')">
                    <td class="ps-4 fw-bold">#${r.rank || i + 1}</td>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <img src="/Profile/${r.photo || 'default.png'}" class="rounded-circle" style="width:36px;height:36px;object-fit:cover;" alt="${r.name}">
                            <div>
                                <div class="fw-bold">${r.name || r.school_id}</div>
                                <div class="small text-muted">${r.school_id}</div>
                            </div>
                        </div>
                    </td>
                    <td>${r.total_borrowed}</td>
                </tr>
            `).join('') || '<tr><td colspan="3" class="text-center text-muted py-4">No borrower data this month.</td></tr>';

            document.getElementById('topBooksBody').innerHTML = books.length > 0
                ? books.map((r, i) => `<tr><td class="ps-4 fw-bold">#${r.rank || i + 1}</td><td><code>${r.book_no}</code></td><td>${r.total_borrowed}</td></tr>`).join('')
                : '<tr><td colspan="3" class="text-center text-muted py-4">No book data this month.</td></tr>';
        } catch (e) {
            console.error(e);
            document.getElementById('topBorrowersBody').innerHTML = '<tr><td colspan="3" class="text-center text-danger py-4">Failed to load borrowers leaderboard.</td></tr>';
            document.getElementById('topBooksBody').innerHTML = '<tr><td colspan="3" class="text-center text-danger py-4">Failed to load books leaderboard.</td></tr>';
        }
    }

    async function openLeaderboardProfile(id) {
        try {
            const res = await apiFetch('/api/leaderboard_profile/' + encodeURIComponent(id));
            const data = await res.json();
            if (!res.ok || !data.success) throw new Error(data.message || 'Unable to load profile.');

            const p = data.profile;
            document.getElementById('leaderboardProfilePhoto').src = `/Profile/${p.photo || 'default.png'}`;
            document.getElementById('leaderboardProfileName').innerText = p.name || p.school_id;
            document.getElementById('leaderboardProfileId').innerText = `ID: ${p.school_id || '-'}`;
            document.getElementById('leaderboardProfileTotal').innerText = p.total_borrowed ?? 0;
            document.getElementById('leaderboardProfileBook').innerText = p.most_borrowed_book || 'No records';
            leaderboardProfileModal.show();
        } catch (e) {
            console.error(e);
            alert('Failed to load leaderboard profile.');
        }
    }

    async function loadDateRestrictions() {
        if (!isStaff) return;
        const body = document.getElementById('dateRestrictionBody');
        const statusEl = document.getElementById('restrictionStatus');
        const selectedDate = document.getElementById('restrictionDate')?.value;
        try {
            const now = new Date();
            const res = await apiFetch(`/api/date_restrictions?year=${now.getFullYear()}`);
            const data = await res.json();
            const items = Array.isArray(data.items) ? data.items : [];
            body.innerHTML = items
                .filter((item) => item.restricted || item.source !== 'open')
                .map((item) => `<tr><td>${item.date}</td><td><span class="badge ${item.restricted ? 'bg-danger' : 'bg-success'}">${item.restricted ? 'Restricted' : 'Open'}</span></td><td>${item.source}</td><td>${item.reason || '-'}</td></tr>`)
                .join('') || '<tr><td colspan="4" class="text-center text-muted py-3">No restrictions found.</td></tr>';

            if (selectedDate) {
                const checkRes = await apiFetch(`/api/date_restrictions/check?date=${encodeURIComponent(selectedDate)}`);
                const check = await checkRes.json();
                statusEl.innerText = check.restricted
                    ? `Selected date is restricted. ${check.reason || ''}`
                    : 'Selected date is available.';
            } else {
                statusEl.innerText = 'Select a date to inspect status.';
            }
        } catch (error) {
            console.error(error);
            body.innerHTML = '<tr><td colspan="4" class="text-center text-danger py-3">Unable to load date restrictions.</td></tr>';
        }
    }

    async function saveDateRestriction(action) {
        const date = document.getElementById('restrictionDate').value;
        const reason = document.getElementById('restrictionReason').value.trim();
        if (!date) return alert('Please select a date first.');
        try {
            const res = await apiFetch('/api/date_restrictions/set', {
                method: 'POST',
                body: JSON.stringify({ date, action, reason })
            });
            const data = await res.json();
            if (!data.success) return alert(data.message || 'Unable to save date restriction.');
            loadDateRestrictions();
        } catch (error) {
            console.error(error);
            alert('Unable to save date restriction.');
        }
    }

    async function cancelReservation(b_no, school_id = '', request_id = '', status = '') {
        if(!confirm("Release reservation/borrowed record for " + b_no + "?")) return;
        try {
            const normalizedStatus = normalizeStatus(status);
            const tx = masterTransactions.find((t) => t.book_no === b_no && normalizeStatus(t.status) === 'reserved');
            if (normalizedStatus === 'reserved' || (!normalizedStatus && tx)) {
                const reservedOwner = school_id || (tx ? tx.school_id : '');
                const reservedRequestId = request_id || (tx ? (tx.request_id || '') : '');
                const res = await apiFetch('/api/cancel_reservation', { method: 'POST', body: JSON.stringify({ book_no: b_no, school_id: reservedOwner, request_id: reservedRequestId }) });
                const data = await res.json();
                if(data.success) { addHistory(`Released Reservation: ${b_no}`); loadData(); return; }
                alert(data.message || 'Unable to release reservation.');
                return;
            }
            const normalizedSchool = String(school_id || '').trim().toLowerCase();
            const normalizedRequest = String(request_id || '').trim();
            const borrowed = masterTransactions.find((t) => {
                if (t.book_no !== b_no || normalizeStatus(t.status) !== 'borrowed') return false;
                const txSchool = String(t.school_id || '').trim().toLowerCase();
                const txRequest = String(t.request_id || '').trim();
                return (normalizedRequest && txRequest === normalizedRequest)
                    || (!normalizedRequest && normalizedSchool && txSchool === normalizedSchool)
                    || (!normalizedRequest && !normalizedSchool);
            });
            if (!borrowed) return alert('No active reservation/borrowed record found.');
            const res = await apiFetch('/api/process_transaction', { method: 'POST', body: JSON.stringify({ book_no: b_no, action: 'return', school_id: borrowed.school_id, request_id: borrowed.request_id || request_id || '' }) });
            const data = await res.json();
            if(data.success) { addHistory(`Released Borrowed Book: ${b_no}`); loadData(); return; }
            alert(data.message || 'Unable to release borrowed record.');
        } catch (error) {
            console.error(error);
            alert('Unable to release reservation/borrowed record right now.');
        }
    }

    function addHistory(entry) {
        const stamp = new Date().toLocaleString();
        adminHistory.unshift({ entry, stamp });
        adminHistory = adminHistory.slice(0, 40);
        localStorage.setItem('adminHistory', JSON.stringify(adminHistory));
        renderAdminHistory();
    }

    async function renderAdminHistory() {
        const container = document.getElementById('adminActionLog');
        if (!container) return;
        try {
            const res = await apiFetch('/api/admin/transactions', { method: 'GET' }, false);
            const tx = await res.json();
            const recent = (Array.isArray(tx) ? tx : [])
                .slice(-10)
                .reverse()
                .map(t => ({
                    entry: `${t.status || 'Activity'} • ${t.book_no || '-'} • ${t.school_id || '-'}`,
                    stamp: t.date || t.reserved_at || '-'
                }));

            container.innerHTML = recent.map(r => `<div class="history-item"><div class="fw-bold text-dark">${r.entry}</div><div class="small text-muted">${r.stamp}</div></div>`).join('')
                || '<div class="small text-muted">No log entries yet.</div>';
        } catch (error) {
            console.error(error);
            container.innerHTML = adminHistory.map(r => `<div class="history-item"><div class="fw-bold text-dark">${r.entry}</div><div class="small text-muted">${r.stamp}</div></div>`).join('')
                || '<div class="small text-muted">No log entries yet.</div>';
        }
    }

    function clearHistory() {
        adminHistory = [];
        localStorage.setItem('adminHistory', JSON.stringify(adminHistory));
        renderAdminHistory();
    }

    async function logout() {
        try {
            await apiFetch('/api/logout', { method: 'POST' });
        } catch (error) {
            console.error(error);
        }
        localStorage.removeItem('isStaffAuth');
        localStorage.removeItem('adminToken');
        localStorage.removeItem('token');
        window.location.href = "/";
    }

    function updateTimers() {
        document.querySelectorAll('.timer').forEach(el => {
            if(!el.dataset.expiry){ el.innerText = 'Awaiting pickup'; return; }
            const diff = new Date(el.dataset.expiry) - new Date();
            el.innerText = diff <= 0 ? "OVERDUE" : `${Math.floor(diff / 60000)}m ${Math.floor((diff % 60000) / 1000)}s`;
            if(diff <= 0) el.classList.add('text-danger', 'fw-black');
        });
    }

    function showLoginError() { document.getElementById('loginError').style.display = 'block'; setTimeout(() => { document.getElementById('loginError').style.display = 'none'; }, 3000); }

    function mountAdminDropdown() {
        const globalDropdownContainer = document.getElementById('global-dropdown-container');
        const adminFloatCard = document.getElementById('adminFloatCard');
        if (globalDropdownContainer && adminFloatCard && adminFloatCard.parentElement !== globalDropdownContainer) {
            globalDropdownContainer.appendChild(adminFloatCard);
        }

        document.addEventListener('click', (event) => {
            const card = document.getElementById('adminFloatCard');
            const trigger = document.getElementById('adminProfileTrigger');
            if (!card || !trigger || !card.classList.contains('active')) return;
            if (!card.contains(event.target) && !trigger.contains(event.target)) {
                card.classList.remove('active');
            }
        });

        window.addEventListener('resize', updateAdminDropdownPosition);
        window.addEventListener('scroll', updateAdminDropdownPosition, true);
    }

    function updateAdminDropdownPosition() {
        const trigger = document.getElementById('adminProfileTrigger');
        const card = document.getElementById('adminFloatCard');
        if (!trigger || !card) return;

        const triggerRect = trigger.getBoundingClientRect();
        const dropdownWidth = card.offsetWidth || 380;
        const spacing = 12;
        const maxLeft = window.innerWidth - dropdownWidth - 12;
        const left = Math.min(Math.max(12, triggerRect.right - dropdownWidth), maxLeft);

        card.style.top = `${triggerRect.bottom + spacing}px`;
        card.style.left = `${left}px`;
    }

    function toggleAdminCard(event) {
        if (event) event.stopPropagation();
        const card = document.getElementById('adminFloatCard');
        if (!card) return;
        card.classList.toggle('active');
        if (card.classList.contains('active')) updateAdminDropdownPosition();
    }
    function filterInventory() {
        const q = document.getElementById('inventorySearch').value.toLowerCase();
        const filtered = masterBooks.filter(b =>
            (b.title.toLowerCase().includes(q) ||
             b.book_no.toLowerCase().includes(q)) &&
            (activeFilterCat === 'All' || b.category === activeFilterCat)
        );
        renderInventory(filtered);
    }
