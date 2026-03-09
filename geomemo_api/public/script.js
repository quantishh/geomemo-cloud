document.addEventListener('DOMContentLoaded', () => {
    // --- CHANGE: Point explicitly to your Cloud API Port ---
    const API_BASE_URL = "";

    // --- DOM ELEMENTS ---
    const articlesTbody = document.getElementById('articles-tbody');
    const loadingEl = document.getElementById('loading');
    const selectAllCheckbox = document.getElementById('select-all-checkbox');
    const batchApproveBtn = document.getElementById('batch-approve');
    const batchRejectBtn = document.getElementById('batch-reject');
    const manualForm = document.getElementById('manual-entry-form');
    const categoryFilter = document.getElementById('category-filter');
    
    // Enhance Modal Elements
    const enhanceModal = document.getElementById('enhance-modal');
    const enhanceInput = document.getElementById('enhance-text-input');
    const enhancePubInput = document.getElementById('enhance-publication');
    const enhanceAuthorInput = document.getElementById('enhance-author');
    const confirmEnhanceBtn = document.getElementById('confirm-enhance-btn');

    // ** Button Name: Enhance & Submit **
    if(confirmEnhanceBtn) confirmEnhanceBtn.textContent = "Enhance & Submit";

    // Newsletter Elements (M3 Upgrade)
    const generateNewsletterBtn = document.getElementById('generate-newsletter-btn');
    const newsletterModal = document.getElementById('newsletter-modal');
    const newsletterOutput = document.getElementById('newsletter-output');
    const newsletterSubject = document.getElementById('newsletter-subject');
    const copyHtmlBtn = document.getElementById('copy-html-btn');
    const closeNewsletterBtn = document.getElementById('close-newsletter-btn');
    const newsletterPreview = document.getElementById('newsletter-preview');
    const togglePreviewBtn = document.getElementById('toggle-preview-btn');
    const toggleHtmlBtn = document.getElementById('toggle-html-btn');
    const pushBeehiivBtn = document.getElementById('push-beehiiv-btn');
    const newsletterWordCount = document.getElementById('newsletter-word-count');
    const newsletterStatus = document.getElementById('newsletter-status');
    const newsletterHistoryList = document.getElementById('newsletter-history-list');
    const regenerateBtn = document.getElementById('regenerate-btn');

    // Other Managers
    const tweetForm = document.getElementById('tweet-entry-form');
    const sponsorForm = document.getElementById('sponsor-form');
    const podcastForm = document.getElementById('podcast-form');
    const fetchMetaBtn = document.getElementById('fetch-podcast-meta-btn');

    // --- STATE ---
    let allArticlesCache = [];
    let currentEnhanceId = null;
    let currentBriefId = null;
    let currentSortBy = 'scraped_at';
    let currentSortOrder = 'desc';
    let isTopicGrouped = false;
    let socialHistoryOffset = 0;
    const SOCIAL_PAGE_SIZE = 10;

    // --- FILTER STATE (Phase 3) ---
    let currentStatusFilter = 'All';
    let currentScoreFilter = 'All';
    let currentAutoApproveThreshold = 80;
    let currentAutoRejectThreshold = 30;
    let currentDateFilter = 'All'; // 'All' or 'YYYY-MM-DD'

    // --- VIEW MODE STATE (Phase 4) ---
    let currentViewMode = localStorage.getItem('geomemo-view') || 'web';
    const ARTICLES_PER_PAGE = 50;
    let mobileCurrentPage = 0;
    let mobileTotalArticles = 0;
    let mobileSelectedDate = null;
    
    // ** UPDATED CATEGORY ORDER **
    const VALID_CATEGORIES = [
        'Geopolitical Conflict', 
        'Geopolitical Economics', 
        'Global Markets', 
        'Geopolitical Politics', 
        'GeoNatDisaster', 
        'GeoLocal', 
        'Other'
    ];

    // --- M2: Score + Source DOM ---
    const autoApproveBtn = document.getElementById('auto-approve-btn');
    const autoRejectBtn = document.getElementById('auto-reject-btn');
    const scoreSortHeader = document.getElementById('score-sort-header');
    const sourceForm = document.getElementById('source-form');
    const seedSourcesBtn = document.getElementById('seed-sources-btn');
    const recalcSourcesBtn = document.getElementById('recalc-sources-btn');

    // --- INITIALIZATION ---
    populateCategoryFilter();
    fetchArticles(false);
    fetchTweetManagerList();
    fetchSponsorsList();
    fetchPodcastsList();
    fetchSourcesList();

    // --- EVENT LISTENERS ---
    if (categoryFilter) categoryFilter.addEventListener('change', () => { renderArticles(); updateScoreDistribution(); });
    if (selectAllCheckbox) selectAllCheckbox.addEventListener('change', handleSelectAll);
    if (batchApproveBtn) batchApproveBtn.addEventListener('click', () => handleBatch('approved'));
    if (batchRejectBtn) batchRejectBtn.addEventListener('click', () => handleBatch('rejected'));
    if (manualForm) manualForm.addEventListener('submit', handleManualSubmit);
    
    // Enhance Modal Listeners
    if (enhanceModal) {
        const closeBtn = enhanceModal.querySelector('.modal-close-btn');
        if(closeBtn) closeBtn.addEventListener('click', closeEnhanceModal);
        enhanceModal.addEventListener('click', (e) => { 
            if (e.target === enhanceModal) closeEnhanceModal(); 
        });
    }
    if (confirmEnhanceBtn) confirmEnhanceBtn.addEventListener('click', handleEnhanceSubmit);

    // Manager Listeners
    if (tweetForm) tweetForm.addEventListener('submit', handleTweetSubmit);
    if (sponsorForm) sponsorForm.addEventListener('submit', handleSponsorSubmit);
    if (podcastForm) podcastForm.addEventListener('submit', handlePodcastSubmit);
    if (fetchMetaBtn) fetchMetaBtn.addEventListener('click', handleFetchMeta);

    // M2: Smart Curation Listeners
    if (autoApproveBtn) autoApproveBtn.addEventListener('click', handleAutoApprove);
    if (autoRejectBtn) autoRejectBtn.addEventListener('click', handleAutoReject);
    if (scoreSortHeader) scoreSortHeader.addEventListener('click', toggleScoreSort);
    if (sourceForm) sourceForm.addEventListener('submit', handleSourceSubmit);
    if (seedSourcesBtn) seedSourcesBtn.addEventListener('click', handleSeedSources);
    if (recalcSourcesBtn) recalcSourcesBtn.addEventListener('click', handleRecalcSources);

    // Newsletter Listeners (M3 Upgrade)
    if (generateNewsletterBtn) generateNewsletterBtn.addEventListener('click', () => generateNewsletter(false));
    if (regenerateBtn) regenerateBtn.addEventListener('click', () => generateNewsletter(true));
    if (closeNewsletterBtn) closeNewsletterBtn.addEventListener('click', () => {
        newsletterModal.classList.add('hidden');
        if (newsletterStatus) newsletterStatus.style.display = 'none';
    });
    if (copyHtmlBtn) copyHtmlBtn.addEventListener('click', () => {
        const htmlContent = newsletterOutput && newsletterOutput.value;
        if (!htmlContent) return;
        const onSuccess = () => {
            copyHtmlBtn.textContent = 'Copied!';
            setTimeout(() => { copyHtmlBtn.textContent = 'Copy HTML'; }, 2000);
        };
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(htmlContent).then(onSuccess).catch(onSuccess);
        } else {
            const tmp = document.createElement('textarea');
            tmp.value = htmlContent;
            tmp.style.position = 'fixed';
            tmp.style.opacity = '0';
            document.body.appendChild(tmp);
            tmp.select();
            document.execCommand('copy');
            document.body.removeChild(tmp);
            onSuccess();
        }
    });
    if (togglePreviewBtn) togglePreviewBtn.addEventListener('click', showPreviewMode);
    if (toggleHtmlBtn) toggleHtmlBtn.addEventListener('click', showHtmlMode);
    if (pushBeehiivBtn) pushBeehiivBtn.addEventListener('click', handlePushToBeehiiv);

    // M6: Social media event listeners
    const checkBreakingBtn = document.getElementById('check-breaking-btn');
    const postNewsletterTelegramBtn = document.getElementById('post-newsletter-telegram-btn');
    if (checkBreakingBtn) checkBreakingBtn.addEventListener('click', handleCheckBreakingNews);
    if (postNewsletterTelegramBtn) postNewsletterTelegramBtn.addEventListener('click', handlePostNewsletterTelegram);
    fetchSocialStatus();
    fetchSocialHistory();

    // Social history pagination
    const socialPrevBtn = document.getElementById('social-prev-btn');
    const socialNextBtn = document.getElementById('social-next-btn');
    if (socialPrevBtn) socialPrevBtn.addEventListener('click', () => {
        socialHistoryOffset = Math.max(0, socialHistoryOffset - SOCIAL_PAGE_SIZE);
        fetchSocialHistory();
    });
    if (socialNextBtn) socialNextBtn.addEventListener('click', () => {
        socialHistoryOffset += SOCIAL_PAGE_SIZE;
        fetchSocialHistory();
    });

    // --- THEME TOGGLE (Phase 2) ---
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const themeIcon = document.getElementById('theme-icon');
    const savedTheme = localStorage.getItem('geomemo-theme') || 'light';
    document.body.className = document.body.className.replace(/theme-\w+/, `theme-${savedTheme}`);
    if (themeIcon) themeIcon.textContent = savedTheme === 'dark' ? '☀️' : '🌙';

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const isDark = document.body.classList.contains('theme-dark');
            document.body.classList.remove(isDark ? 'theme-dark' : 'theme-light');
            document.body.classList.add(isDark ? 'theme-light' : 'theme-dark');
            const newTheme = isDark ? 'light' : 'dark';
            localStorage.setItem('geomemo-theme', newTheme);
            if (themeIcon) themeIcon.textContent = newTheme === 'dark' ? '☀️' : '🌙';
        });
    }

    // --- FILTER BAR (Phase 3) ---
    document.querySelectorAll('.filter-pill').forEach(pill => {
        pill.addEventListener('click', (e) => {
            const btn = e.target.closest('.filter-pill');
            if (!btn) return;
            const type = btn.dataset.filterType;
            const value = btn.dataset.value;

            // Deactivate siblings of same type
            document.querySelectorAll(`.filter-pill[data-filter-type="${type}"]`)
                .forEach(p => p.classList.remove('active'));
            btn.classList.add('active');

            if (type === 'status') currentStatusFilter = value;
            if (type === 'score') currentScoreFilter = value;

            renderArticles();
        });
    });

    // --- TOPIC GROUP TOGGLE ---
    const topicGroupBtn = document.getElementById('topic-group-toggle');
    if (topicGroupBtn) {
        topicGroupBtn.addEventListener('click', () => {
            isTopicGrouped = !isTopicGrouped;
            topicGroupBtn.classList.toggle('active', isTopicGrouped);
            topicGroupBtn.textContent = isTopicGrouped ? '🔗 Grouped by Topic' : '🔗 Group by Topic';
            fetchArticles();
        });
    }

    function updateAutoButtonLabels() {
        document.querySelectorAll('.approve-threshold-label')
            .forEach(el => el.textContent = currentAutoApproveThreshold);
        document.querySelectorAll('.reject-threshold-label')
            .forEach(el => el.textContent = currentAutoRejectThreshold);
        if (autoApproveBtn) autoApproveBtn.textContent = `Auto-Approve (${currentAutoApproveThreshold}+)`;
        if (autoRejectBtn) autoRejectBtn.textContent = `Auto-Reject (${currentAutoRejectThreshold}-)`;
        updateScoreDistribution();
    }

    function getArticleLocalDate(article) {
        if (!article.scraped_at) return 'Unsorted';
        const d = new Date(article.scraped_at);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }

    function updateScoreDistribution() {
        const distEl = document.getElementById('score-distribution');
        if (!distEl || !allArticlesCache.length) return;

        // Build the date picker options from available dates
        const dateCounts = {};
        allArticlesCache.forEach(a => {
            const d = getArticleLocalDate(a);
            dateCounts[d] = (dateCounts[d] || 0) + 1;
        });
        const sortedDates = Object.keys(dateCounts).filter(d => d !== 'Unsorted').sort().reverse();

        // Apply date filter to get scoped articles
        let scoped = allArticlesCache;
        if (currentDateFilter !== 'All') {
            scoped = scoped.filter(a => getArticleLocalDate(a) === currentDateFilter);
        }

        // Apply category filter too (so distribution matches what user sees)
        const selectedCategory = categoryFilter ? categoryFilter.value : 'All';
        if (selectedCategory !== 'All') {
            scoped = scoped.filter(a => a.category === selectedCategory);
        }

        const pending = scoped.filter(a => a.status === 'pending');
        const below30 = pending.filter(a => (a.auto_approval_score || 0) < 30).length;
        const range30to50 = pending.filter(a => { const s = a.auto_approval_score || 0; return s >= 30 && s < 50; }).length;
        const range50to70 = pending.filter(a => { const s = a.auto_approval_score || 0; return s >= 50 && s < 70; }).length;
        const above70 = pending.filter(a => (a.auto_approval_score || 0) >= 70).length;

        // Pretty label for the selected date
        let dateLabel = 'All Days';
        if (currentDateFilter !== 'All') {
            try {
                dateLabel = new Date(currentDateFilter + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
            } catch(e) { dateLabel = currentDateFilter; }
        }

        // Date picker options
        const dateOptions = sortedDates.map(d => {
            let label = d;
            try {
                label = new Date(d + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
            } catch(e) {}
            const selected = d === currentDateFilter ? 'selected' : '';
            return `<option value="${d}" ${selected}>${label} (${dateCounts[d]})</option>`;
        }).join('');

        distEl.innerHTML = `
            <select id="dist-date-picker" class="dist-date-picker" title="Scope score counts to a specific day">
                <option value="All" ${currentDateFilter === 'All' ? 'selected' : ''}>All Days</option>
                ${dateOptions}
            </select>
            <span class="dist-chip dist-low" title="Pending with score below 30">🔴 &lt;30: <strong>${below30}</strong></span>
            <span class="dist-chip dist-medium-low" title="Pending with score 30-50">🟠 30–50: <strong>${range30to50}</strong></span>
            <span class="dist-chip dist-medium-high" title="Pending with score 50-70">🟡 50–70: <strong>${range50to70}</strong></span>
            <span class="dist-chip dist-high" title="Pending with score 70-100">🟢 70+: <strong>${above70}</strong></span>
            <span class="dist-chip dist-total" title="Total pending for ${dateLabel}">📊 Pending: <strong>${pending.length}</strong></span>
        `;

        // Date picker change handler — updates BOTH distribution AND article table
        const picker = document.getElementById('dist-date-picker');
        if (picker) {
            picker.addEventListener('change', (e) => {
                currentDateFilter = e.target.value;
                renderArticles();
                updateScoreDistribution();
            });
        }
    }

    // --- VIEW MODE TOGGLE (Phase 4) ---
    const webViewLink = document.getElementById('web-view-link');
    const mobileViewLink = document.getElementById('mobile-view-link');

    function setViewMode(mode) {
        currentViewMode = mode;
        localStorage.setItem('geomemo-view', mode);

        if (mode === 'web') {
            if (webViewLink) webViewLink.classList.add('active');
            if (mobileViewLink) mobileViewLink.classList.remove('active');

            const paginationEl = document.getElementById('articles-pagination');
            const archiveEl = document.getElementById('mobile-archive');
            const filterBarEl = document.getElementById('filter-bar');
            if (paginationEl) paginationEl.classList.add('hidden');
            if (archiveEl) archiveEl.classList.add('hidden');
            if (filterBarEl) filterBarEl.classList.remove('hidden');

            fetchArticles(false);
        } else {
            if (mobileViewLink) mobileViewLink.classList.add('active');
            if (webViewLink) webViewLink.classList.remove('active');

            const paginationEl = document.getElementById('articles-pagination');
            const archiveEl = document.getElementById('mobile-archive');
            const filterBarEl = document.getElementById('filter-bar');
            if (paginationEl) paginationEl.classList.remove('hidden');
            if (archiveEl) archiveEl.classList.remove('hidden');
            if (filterBarEl) filterBarEl.classList.add('hidden');

            mobileCurrentPage = 0;
            mobileSelectedDate = null;
            fetchMobileArticles();
            buildArchiveLinks();
        }
    }

    if (webViewLink) webViewLink.addEventListener('click', (e) => { e.preventDefault(); setViewMode('web'); });
    if (mobileViewLink) mobileViewLink.addEventListener('click', (e) => { e.preventDefault(); setViewMode('mobile'); });

    // Mobile pagination button listeners
    const articlesPrevBtn = document.getElementById('articles-prev-btn');
    const articlesNextBtn = document.getElementById('articles-next-btn');
    if (articlesPrevBtn) articlesPrevBtn.addEventListener('click', () => {
        mobileCurrentPage = Math.max(0, mobileCurrentPage - 1);
        fetchMobileArticles();
    });
    if (articlesNextBtn) articlesNextBtn.addEventListener('click', () => {
        mobileCurrentPage++;
        fetchMobileArticles();
    });

    async function fetchMobileArticles() {
        const offset = mobileCurrentPage * ARTICLES_PER_PAGE;
        let url = `${API_BASE_URL}/articles?days=1&limit=${ARTICLES_PER_PAGE}&offset=${offset}`;
        if (mobileSelectedDate) {
            url = `${API_BASE_URL}/articles?target_date=${mobileSelectedDate}&limit=${ARTICLES_PER_PAGE}&offset=${offset}`;
        }
        try {
            const response = await fetch(url);
            const data = await response.json();
            const articles = data.articles || data;
            mobileTotalArticles = data.total || articles.length;

            if (!articlesTbody) return;
            articlesTbody.innerHTML = '';
            if (articles.length === 0) {
                articlesTbody.innerHTML = `<tr><td colspan="7" style="padding:24px; text-align:center; color:var(--text-muted);">No articles for this date.</td></tr>`;
                return;
            }
            articles.forEach(article => {
                const row = createArticleRow(article, false);
                articlesTbody.appendChild(row);
            });
            updateMobilePagination();
        } catch (e) {
            console.error('Mobile fetch error:', e);
        }
    }

    function updateMobilePagination() {
        const totalPages = Math.max(1, Math.ceil(mobileTotalArticles / ARTICLES_PER_PAGE));
        const prevBtn = document.getElementById('articles-prev-btn');
        const nextBtn = document.getElementById('articles-next-btn');
        const pageInfo = document.getElementById('articles-page-info');

        if (prevBtn) prevBtn.disabled = mobileCurrentPage === 0;
        if (nextBtn) nextBtn.disabled = (mobileCurrentPage + 1) >= totalPages;
        if (pageInfo) pageInfo.textContent = `Page ${mobileCurrentPage + 1} of ${totalPages} (${mobileTotalArticles} articles)`;
    }

    function buildArchiveLinks() {
        const container = document.getElementById('archive-links');
        if (!container) return;

        const links = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date();
            d.setDate(d.getDate() - i);
            const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
            const label = i === 0 ? 'Today' : d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
            const isActive = (mobileSelectedDate === dateStr) || (i === 0 && !mobileSelectedDate);
            links.push(`<a href="#" class="archive-link${isActive ? ' active' : ''}" data-date="${dateStr}">${label}</a>`);
        }
        container.innerHTML = links.join('');

        container.querySelectorAll('.archive-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                mobileSelectedDate = e.target.dataset.date;
                mobileCurrentPage = 0;
                container.querySelectorAll('.archive-link').forEach(l => l.classList.remove('active'));
                e.target.classList.add('active');
                fetchMobileArticles();
            });
        });
    }

    // Initialize view mode on load
    if (currentViewMode === 'mobile') {
        setViewMode('mobile');
    }
    // else: web mode is default, fetchArticles already called above

    // --- GLOBAL HELPERS ---
    window.deleteItem = async (endpoint, id) => {
        if(!confirm("Delete this item?")) return;
        try {
            await fetch(`${API_BASE_URL}/${endpoint}/${id}`, { method: 'DELETE' });
            if(endpoint === 'sponsors') fetchSponsorsList();
            if(endpoint === 'podcasts') fetchPodcastsList();
            if(endpoint === 'tweets') fetchTweetManagerList();
        } catch(e) { alert(e.message); }
    };

    window.updateStatus = async (id, status) => {
        // Optimistic UI: instantly update the row before API responds
        const row = document.querySelector(`tr[data-article-id="${id}"]`);
        let prevBadgeHtml = '';
        let prevRowClass = '';
        if (row) {
            prevRowClass = row.className;
            const badge = row.querySelector('.status-badge');
            if (badge) {
                prevBadgeHtml = badge.outerHTML;
                const icon = status === 'approved' ? '✓' : status === 'rejected' ? '✗' : '?';
                badge.textContent = `${icon} ${status}`;
                badge.className = `status-badge status-${status} text-xs block mb-1`;
            }
            row.className = `article-row ${status}`;
            row.style.opacity = '0.7';
            row.style.transition = 'opacity 0.2s';
            setTimeout(() => { if (row) row.style.opacity = '1'; }, 200);
        }
        try {
            const res = await fetch(`${API_BASE_URL}/articles/${id}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: status })
            });
            if (!res.ok) throw new Error('API error');
            // Update cache in-place
            const cached = allArticlesCache.find(a => a.id === id);
            if (cached) cached.status = status;
        } catch (e) {
            // Revert on failure
            if (row) {
                row.className = prevRowClass;
                const badge = row.querySelector('.status-badge');
                if (badge && prevBadgeHtml) badge.outerHTML = prevBadgeHtml;
            }
            alert("Failed to update status");
        }
    };

    window.handleFindSimilarClick = (id, headline) => {
        handleFindSimilarLogic(id, headline);
    };

    window.postArticleToTelegram = async (articleId) => {
        if (!confirm('Post this article to Telegram?')) return;
        try {
            const res = await fetch(`${API_BASE_URL}/social/post/article`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ article_id: articleId, platforms: ['telegram'] })
            });
            const data = await res.json();
            if (data.posted && data.posted.length > 0) {
                alert('Posted to Telegram!');
                fetchSocialHistory();
            } else if (data.errors && data.errors.length > 0) {
                alert('Error: ' + data.errors.map(e => e.error).join(', '));
            }
        } catch (e) { alert('Failed: ' + e.message); }
    };

    // --- SOCIAL QUEUE ---
    window.addToQueue = async (articleId, platform) => {
        // Optional: prompt for content override
        const doPaste = confirm(`Add to ${platform} queue?\n\nClick OK to add with auto-generated content.\nIf you want to paste article content for a better summary, click Cancel and use the Enhance button first.`);
        if (!doPaste) return;

        try {
            const res = await fetch(`${API_BASE_URL}/social/queue/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ article_id: articleId, platforms: [platform] })
            });
            const data = await res.json();
            if (data.queued && data.queued.length > 0) {
                alert(`Added to ${platform} queue! Will auto-post within 30 minutes.`);
                loadQueueItems();
            } else {
                alert('Failed to add to queue');
            }
        } catch (e) { alert('Queue error: ' + e.message); }
    };

    async function loadQueueItems() {
        const queuePanel = document.getElementById('queue-items-list');
        if (!queuePanel) return;
        try {
            const res = await fetch(`${API_BASE_URL}/social/queue?status=queued&limit=20`);
            const items = await res.json();
            if (items.length === 0) {
                queuePanel.innerHTML = '<p class="text-xs text-gray-400 p-2">No items in queue</p>';
                return;
            }
            queuePanel.innerHTML = items.map(item => `
                <div class="flex items-center justify-between p-2 border-b border-gray-100 text-xs">
                    <div class="flex-1 truncate mr-2">
                        <span class="font-semibold ${item.platform === 'telegram' ? 'text-blue-500' : 'text-gray-800'}">${item.platform === 'telegram' ? '📢' : '𝕏'}</span>
                        ${item.headline || 'Article #' + item.article_id}
                    </div>
                    <div class="flex gap-1">
                        <button class="text-xs px-2 py-1 bg-green-100 text-green-700 rounded" onclick="postQueueNow(${item.id})">Post Now</button>
                        <button class="text-xs px-2 py-1 bg-red-100 text-red-700 rounded" onclick="cancelQueueItem(${item.id})">Cancel</button>
                    </div>
                </div>
            `).join('');
        } catch (e) { console.error('Queue load error:', e); }
    }

    window.postQueueNow = async (queueId) => {
        if (!confirm('Post this item now?')) return;
        try {
            const res = await fetch(`${API_BASE_URL}/social/queue/${queueId}/post-now`, { method: 'POST' });
            const data = await res.json();
            alert(data.message || 'Posted!');
            loadQueueItems();
            fetchSocialHistory();
        } catch (e) { alert('Post failed: ' + e.message); }
    };

    window.cancelQueueItem = async (queueId) => {
        try {
            const res = await fetch(`${API_BASE_URL}/social/queue/${queueId}`, { method: 'DELETE' });
            if (res.ok) loadQueueItems();
        } catch (e) { console.error('Cancel error:', e); }
    };

    // Load queue on page load
    setTimeout(loadQueueItems, 2000);

    function isToday(dateString) {
        if (!dateString) return false;
        const d = new Date(dateString);
        const today = new Date();
        return d.getDate() === today.getDate() &&
               d.getMonth() === today.getMonth() &&
               d.getFullYear() === today.getFullYear();
    }

    // --- HELPER: SCORE CLASS ---
    function getScoreClass(score) {
        if (score == null || score === 0) return '';
        if (score >= 70) return 'score-high';
        if (score >= 40) return 'score-medium';
        return 'score-low';
    }

    // --- HELPER: POPULATE FILTER ---
    function populateCategoryFilter() {
        if (!categoryFilter) return;
        categoryFilter.innerHTML = '<option value="All">CATEGORY (ALL)</option>';
        VALID_CATEGORIES.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat;
            opt.textContent = cat;
            categoryFilter.appendChild(opt);
        });
    }

    // =========================================
    // CORE ARTICLES LOGIC
    // =========================================

    // Track which article to scroll to after re-render
    let _scrollToArticleId = null;

    async function fetchArticles(preserveScroll = false, scrollToId = null) {
        const currentScrollY = window.scrollY;
        if (scrollToId) _scrollToArticleId = scrollToId;
        if (articlesTbody && articlesTbody.children.length === 0) showLoading(true);
        try {
            const params = new URLSearchParams();
            if (isTopicGrouped) {
                params.set('sort_by', 'topic_group');
            } else if (currentSortBy !== 'scraped_at') {
                params.set('sort_by', currentSortBy);
            }
            if (currentSortOrder !== 'desc') params.set('order', currentSortOrder);
            const qs = params.toString();
            const response = await fetch(`${API_BASE_URL}/articles${qs ? '?' + qs : ''}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            allArticlesCache = await response.json();
            renderArticles();
            updateScoreDistribution();

            // Scroll to specific article if requested, otherwise preserve Y offset
            if (_scrollToArticleId) {
                const targetRow = document.querySelector(`tr[data-article-id="${_scrollToArticleId}"]`);
                if (targetRow) {
                    // Ensure parent group is expanded if in topic-grouped mode
                    if (targetRow.classList.contains('hidden')) {
                        targetRow.classList.remove('hidden');
                    }
                    targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    // Brief highlight effect
                    targetRow.style.transition = 'background 0.3s';
                    targetRow.style.background = '#fef9c3';
                    setTimeout(() => { targetRow.style.background = ''; }, 2000);
                }
                _scrollToArticleId = null;
            } else if (preserveScroll) {
                window.scrollTo(0, currentScrollY);
            }
        } catch (error) {
            console.error('Error fetching articles:', error);
        } finally {
            if (articlesTbody) showLoading(false);
        }
    }

    function renderArticles() {
        if(!articlesTbody) return;
        const selectedCategory = categoryFilter ? categoryFilter.value : 'All';

        // Date Filter — must come first so all counts are scoped to selected day
        let filtered = allArticlesCache;
        let baseTotal = allArticlesCache.length;
        if (currentDateFilter !== 'All') {
            filtered = filtered.filter(a => getArticleLocalDate(a) === currentDateFilter);
            baseTotal = filtered.length;
        }

        // Category Filter
        if (selectedCategory !== 'All') {
            filtered = filtered.filter(a => a.category === selectedCategory);
        }

        // Status Filter (Phase 3)
        if (currentStatusFilter !== 'All') {
            filtered = filtered.filter(a => a.status === currentStatusFilter);
        }

        // Score Range Filter (Phase 3)
        if (currentScoreFilter === 'auto-approve') {
            filtered = filtered.filter(a => (a.auto_approval_score || 0) >= currentAutoApproveThreshold);
        } else if (currentScoreFilter === 'auto-reject') {
            filtered = filtered.filter(a => (a.auto_approval_score || 0) <= currentAutoRejectThreshold);
        } else if (currentScoreFilter === 'in-between') {
            filtered = filtered.filter(a => {
                const score = a.auto_approval_score || 0;
                return score > currentAutoRejectThreshold && score < currentAutoApproveThreshold;
            });
        }

        // Update filter count label (relative to date-scoped total)
        const countLabel = document.getElementById('filter-count-label');
        if (countLabel) {
            countLabel.textContent = `${filtered.length} of ${baseTotal} articles`;
        }

        if (isTopicGrouped) {
            // Topic-grouped view: articles come with topic_group field from server
            renderTopicGroupedArticles(filtered);
        } else {
            // Group by Date (default)
            const grouped = filtered.reduce((groups, article) => {
                let date = 'Unsorted';
                if (article.scraped_at) {
                    // Convert UTC timestamp to user's local date (YYYY-MM-DD)
                    const d = new Date(article.scraped_at);
                    date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
                }
                if (!groups[date]) groups[date] = [];
                groups[date].push(article);
                return groups;
            }, {});

            renderGroupedArticles(grouped);
        }
    }

    function renderGroupedArticles(groupedArticles) {
        articlesTbody.innerHTML = ''; 
        const sortedDates = Object.keys(groupedArticles).filter(d => d !== 'Unsorted').sort().reverse();
        if (groupedArticles['Unsorted']) sortedDates.push('Unsorted');

        if (sortedDates.length === 0) {
             articlesTbody.innerHTML = '<tr><td colspan="7" class="p-4 text-center text-gray-500">No articles found.</td></tr>';
             return;
        }

        sortedDates.forEach(date => {
            const articlesInDate = groupedArticles[date];
            
            // Logic to visually group Parent/Child in the Admin Table
            const parents = articlesInDate.filter(a => !a.parent_id);
            const children = articlesInDate.filter(a => a.parent_id);
            
            const childrenMap = {};
            children.forEach(child => {
                if(!childrenMap[child.parent_id]) childrenMap[child.parent_id] = [];
                childrenMap[child.parent_id].push(child);
            });
            
            const parentIds = new Set(parents.map(p => p.id));
            const orphans = children.filter(c => !parentIds.has(c.parent_id));
            const displayList = [...parents, ...orphans];

            // Safe Date Formatting
            let prettyDate = date;
            if (date !== 'Unsorted') {
                try {
                    prettyDate = new Date(date + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
                } catch(e) { console.warn("Date parse error", e); }
            }

            // DATE HEADER ROW
            const headerRow = document.createElement('tr');
            headerRow.className = 'date-header-row';
            headerRow.innerHTML = `
                <td colspan="7" class="date-header bg-gray-100 p-2 border-b border-gray-200">
                    <div class="flex items-center">
                        <input type="checkbox" class="date-batch-checkbox mr-3 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" data-date="${date}">
                        <span class="toggle-icon inline-block w-4 mr-2 cursor-pointer text-gray-500">▼</span>
                        <span class="cursor-pointer font-bold text-gray-700 select-none">${prettyDate}</span>
                        <span class="text-xs font-normal text-gray-500 ml-2">(${articlesInDate.length} articles)</span>
                    </div>
                </td>
            `;
            
            // Toggle Logic
            headerRow.addEventListener('click', (e) => {
                if (e.target.classList.contains('date-batch-checkbox')) return;
                const rows = document.querySelectorAll(`.article-row[data-date="${date}"]`);
                const icon = headerRow.querySelector('.toggle-icon');
                let isHidden = false;
                rows.forEach(row => {
                    row.classList.toggle('hidden');
                    if (row.classList.contains('hidden')) isHidden = true;
                });
                icon.textContent = isHidden ? '▶' : '▼';
            });

            // Batch Select Logic
            const dateCb = headerRow.querySelector('.date-batch-checkbox');
            dateCb.addEventListener('change', (e) => {
                const isChecked = e.target.checked;
                const groupRows = document.querySelectorAll(`.article-row[data-date="${date}"] .article-checkbox`);
                groupRows.forEach(cb => cb.checked = isChecked);
                updateCheckboxStates();
            });

            articlesTbody.appendChild(headerRow);

            // Render Rows
            displayList.forEach(parent => {
                const parentRow = createArticleRow(parent, false);
                parentRow.setAttribute('data-date', date);
                articlesTbody.appendChild(parentRow);

                if(childrenMap[parent.id]) {
                    childrenMap[parent.id].forEach(child => {
                        const childRow = createArticleRow(child, true);
                        childRow.setAttribute('data-date', date);
                        articlesTbody.appendChild(childRow);
                    });
                }
            });
        });
        
        updateCheckboxStates();
    }

    function renderTopicGroupedArticles(articles) {
        articlesTbody.innerHTML = '';

        if (!articles || articles.length === 0) {
            articlesTbody.innerHTML = '<tr><td colspan="7" class="p-4 text-center text-gray-500">No articles found.</td></tr>';
            return;
        }

        // Group articles by topic_group
        const topicGroups = {};
        const ungroupedArticles = [];
        articles.forEach(a => {
            const gid = (a.topic_group != null) ? a.topic_group : 'ungrouped';
            if (gid === 'ungrouped') {
                ungroupedArticles.push(a);
            } else {
                if (!topicGroups[gid]) topicGroups[gid] = [];
                topicGroups[gid].push(a);
            }
        });

        // Separate multi-article groups from singles mixed in topic groups
        const multiGroups = {};
        const singleGroupArticles = [];
        Object.keys(topicGroups).forEach(gid => {
            if (topicGroups[gid].length >= 2) {
                multiGroups[gid] = topicGroups[gid];
            } else {
                singleGroupArticles.push(...topicGroups[gid]);
            }
        });

        // All singles + ungrouped go into "Other News"
        const otherArticles = [...singleGroupArticles, ...ungroupedArticles];

        const groupKeys = Object.keys(multiGroups);

        // Render multi-article topic groups — ALL COLLAPSED by default
        groupKeys.forEach((gid, idx) => {
            const group = multiGroups[gid];
            const groupSize = group.length;
            const leadHeadline = group[0].headline || group[0].headline_original || 'Topic Group';
            const headerText = leadHeadline.length > 80 ? leadHeadline.substring(0, 77) + '...' : leadHeadline;

            const headerRow = document.createElement('tr');
            headerRow.className = 'topic-group-header';
            headerRow.innerHTML = `
                <td colspan="7" class="p-2 border-b-2" style="background:linear-gradient(90deg,#eef2ff,#fff);border-color:#6366f1;">
                    <div class="flex items-center">
                        <span class="inline-block w-4 mr-2 cursor-pointer text-gray-500 toggle-icon">▶</span>
                        <span class="font-semibold text-indigo-700 text-sm">🔗 ${groupSize} similar articles</span>
                        <span class="text-xs text-gray-500 ml-3 truncate">${headerText}</span>
                    </div>
                </td>
            `;
            headerRow.addEventListener('click', () => {
                const rows = document.querySelectorAll(`.article-row[data-topic-group="${gid}"]`);
                const icon = headerRow.querySelector('.toggle-icon');
                const isCurrentlyCollapsed = icon.textContent === '▶';
                rows.forEach(row => {
                    if (isCurrentlyCollapsed) {
                        row.classList.remove('hidden');
                    } else {
                        row.classList.add('hidden');
                    }
                });
                icon.textContent = isCurrentlyCollapsed ? '▼' : '▶';
            });
            articlesTbody.appendChild(headerRow);

            // All rows start hidden (collapsed)
            group.forEach((article, artIdx) => {
                const isSubItem = artIdx > 0;
                const row = createArticleRow(article, isSubItem);
                row.setAttribute('data-topic-group', gid);
                row.setAttribute('data-date', '');
                row.classList.add('hidden');
                articlesTbody.appendChild(row);
            });

            // Spacing between groups
            if (idx < groupKeys.length - 1) {
                const spacer = document.createElement('tr');
                spacer.innerHTML = '<td colspan="7" style="height:8px;background:transparent;border:none;"></td>';
                articlesTbody.appendChild(spacer);
            }
        });

        // Render "Other News" section — all ungrouped/single articles, collapsed
        if (otherArticles.length > 0) {
            // Spacer before Other News
            if (groupKeys.length > 0) {
                const spacer = document.createElement('tr');
                spacer.innerHTML = '<td colspan="7" style="height:8px;background:transparent;border:none;"></td>';
                articlesTbody.appendChild(spacer);
            }

            const otherHeader = document.createElement('tr');
            otherHeader.className = 'topic-group-header';
            otherHeader.innerHTML = `
                <td colspan="7" class="p-2 border-b-2" style="background:linear-gradient(90deg,#fef3c7,#fff);border-color:#f59e0b;">
                    <div class="flex items-center">
                        <span class="inline-block w-4 mr-2 cursor-pointer text-gray-500 toggle-icon">▶</span>
                        <span class="font-semibold text-amber-700 text-sm">📰 Other News</span>
                        <span class="text-xs text-gray-500 ml-3">(${otherArticles.length} unique articles)</span>
                    </div>
                </td>
            `;
            otherHeader.addEventListener('click', () => {
                const rows = document.querySelectorAll('.article-row[data-topic-group="other-news"]');
                const icon = otherHeader.querySelector('.toggle-icon');
                const isCurrentlyCollapsed = icon.textContent === '▶';
                rows.forEach(row => {
                    if (isCurrentlyCollapsed) {
                        row.classList.remove('hidden');
                    } else {
                        row.classList.add('hidden');
                    }
                });
                icon.textContent = isCurrentlyCollapsed ? '▼' : '▶';
            });
            articlesTbody.appendChild(otherHeader);

            otherArticles.forEach(article => {
                const row = createArticleRow(article, false);
                row.setAttribute('data-topic-group', 'other-news');
                row.setAttribute('data-date', '');
                row.classList.add('hidden');
                articlesTbody.appendChild(row);
            });
        }

        updateCheckboxStates();
    }

    function createArticleRow(article, isChild = false) {
        const tr = document.createElement('tr');
        tr.className = `article-row ${article.status}`;
        tr.dataset.articleId = article.id;
        
        const statusClass = (article.status === 'approved') ? 'status-approved' : (article.status === 'rejected' ? 'status-rejected' : 'status-pending');
        const statusIcon = article.status === 'approved' ? '✓' : (article.status === 'rejected' ? '✗' : '?');
        const starClass = article.is_top_story ? 'text-yellow-500' : 'text-gray-300 hover:text-yellow-400';
        
        const titleCellClass = isChild ? 'pl-8 border-l-4 border-gray-200 bg-gray-50' : '';
        const childIcon = isChild ? '<span class="text-gray-400 mr-1">↳</span>' : '';

        let categoryOptions = VALID_CATEGORIES.map(cat => 
            `<option value="${cat}" ${article.category === cat ? 'selected' : ''}>${cat}</option>`
        ).join('');

        // ** DASHBOARD FIX: Prefer English Headline First **
        const dashboardHeadline = article.headline || article.headline_original || "No Headline";
        const displaySummary = article.summary || "";

        // M2: Score display
        const score = article.auto_approval_score;
        const scoreVal = (score != null && score > 0) ? Math.round(score) : null;
        const scoreClass = getScoreClass(scoreVal);
        const scoreHtml = scoreVal != null
            ? `<span class="score-indicator ${scoreClass}">${scoreVal}</span>`
            : '<span class="text-xs text-gray-400">—</span>';
        const repetitionScore = article.repetition_score || 0;
        const repeatFlag = repetitionScore >= 0.85
            ? '<span class="repeat-flag">REPEAT</span>'
            : '';

        // M2: Country codes display
        const countryCodes = article.country_codes || [];
        const countryHtml = countryCodes.length > 0
            ? `<div class="country-tags">${countryCodes.map(c => `<span class="country-tag">${c}</span>`).join('')}</div>`
            : '';

        tr.innerHTML = `
            <td class="p-3 align-top w-10">
                <input type="checkbox" class="article-checkbox rounded h-4 w-4" data-id="${article.id}">
                ${!isChild ? `<button class="star-btn block mt-2 ${starClass} transition-colors text-lg" data-id="${article.id}">★</button>` : ''}
            </td>
            <td class="p-3 align-top w-3/12 break-words ${titleCellClass}">
                ${childIcon}
                <a href="${article.url}" target="_blank" class="font-semibold text-blue-600 hover:underline text-sm">${dashboardHeadline}</a>
                <div class="text-xs text-gray-500 mt-1">${article.publication_name || 'N/A'}</div>
                ${countryHtml}
            </td>
            <td class="p-3 align-top w-2/12">
                <select class="category-dropdown w-full p-1 border rounded border-gray-300 text-xs bg-white" data-id="${article.id}">
                    ${categoryOptions}
                </select>
            </td>
            <td class="p-3 align-top w-2/12 text-sm text-gray-600">
                ${displaySummary}
            </td>
            <td class="p-3 align-top w-1/12 text-center">
                ${scoreHtml}${repeatFlag}
            </td>
            <td class="p-3 align-top w-1/12">
                <span class="status-badge ${statusClass} text-xs block mb-1">${statusIcon} ${article.status}</span>
            </td>
            <td class="p-3 align-top w-2/12 space-y-2">
                <button class="action-btn approve-btn w-full text-xs" onclick="updateStatus(${article.id}, 'approved')">Approve</button>
                <button class="action-btn reject-btn w-full text-xs" onclick="updateStatus(${article.id}, 'rejected')">Reject</button>
                <button class="similar-btn w-full text-xs" onclick="handleFindSimilarClick(${article.id}, '${dashboardHeadline.replace(/'/g, "\\'")}')">Find Similar</button>
                <button class="enhance-btn w-full text-xs"
                    data-id="${article.id}"
                    data-pub="${article.publication_name || ''}"
                    data-auth="${article.author || ''}">✨ Enhance</button>
                <div class="flex gap-1 mt-1">
                    <button class="telegram-btn text-xs flex-1" style="background:#0088cc;color:#fff;padding:4px 4px;border:none;border-radius:4px;cursor:pointer;" onclick="postArticleToTelegram(${article.id})">📢 TG</button>
                    <button class="text-xs flex-1" style="background:#e0f2fe;color:#0088cc;padding:4px 4px;border:1px solid #0088cc;border-radius:4px;cursor:pointer;" onclick="addToQueue(${article.id},'telegram')">+ Queue</button>
                </div>
                <div class="flex gap-1 mt-1">
                    <button class="twitter-btn text-xs flex-1" style="background:#000;color:#fff;padding:4px 4px;border:none;border-radius:4px;cursor:pointer;" onclick="postArticleToTwitter(${article.id})">𝕏 Post</button>
                    <button class="text-xs flex-1" style="background:#f3f4f6;color:#333;padding:4px 4px;border:1px solid #999;border-radius:4px;cursor:pointer;" onclick="addToQueue(${article.id},'twitter')">+ Queue</button>
                </div>
                <button class="xposts-btn w-full text-xs" style="background:#f3f4f6;color:#374151;padding:4px 8px;border:1px solid #d1d5db;border-radius:4px;cursor:pointer;margin-top:2px;" onclick="openFindXPosts(${article.id})">🔍 Find X Posts</button>
            </td>
        `;
        
        tr.querySelector('.category-dropdown').addEventListener('change', async (e) => {
            try { await fetch(`${API_BASE_URL}/articles/${e.target.dataset.id}/category`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ category: e.target.value }) }); } catch(err) { alert("Failed to update category"); }
        });

        // ** FIXED ENHANCE BUTTON LOGIC **
        tr.querySelector('.enhance-btn').addEventListener('click', (e) => {
            currentEnhanceId = article.id;
            const btn = e.currentTarget;
            
            // Pre-fill Logic:
            const textToEdit = article.summary || article.headline || article.headline_original || "";
            
            if (enhanceInput) enhanceInput.value = textToEdit;
            if (enhancePubInput) enhancePubInput.value = btn.dataset.pub || '';
            if (enhanceAuthorInput) enhanceAuthorInput.value = btn.dataset.auth || '';
            
            if(confirmEnhanceBtn) confirmEnhanceBtn.textContent = "Enhance & Submit";
            
            openEnhanceModal();
        });

        const starBtn = tr.querySelector('.star-btn');
        if(starBtn) {
            starBtn.addEventListener('click', async () => {
                try {
                    await fetch(`${API_BASE_URL}/articles/${article.id}/toggle-top`, { method: 'POST' });
                    // Optimistic update: toggle in cache + update star color
                    const cached = allArticlesCache.find(a => a.id === article.id);
                    if (cached) cached.is_top_story = !cached.is_top_story;
                    const isNowTop = cached ? cached.is_top_story : !article.is_top_story;
                    starBtn.className = `star-btn block mt-2 ${isNowTop ? 'text-yellow-500' : 'text-gray-300 hover:text-yellow-400'} transition-colors text-lg`;
                } catch(err) {}
            });
        }
        
        return tr;
    }

    // =========================================
    // ENHANCE / EDIT MODAL & SIMILARITY LOGIC
    // =========================================
    
    async function handleEnhanceSubmit() {
        if (!currentEnhanceId) return;

        const payload = {
            summary: enhanceInput.value,
            publication_name: enhancePubInput.value,
            author: enhanceAuthorInput.value
        };

        const btn = document.getElementById('confirm-enhance-btn');
        const originalText = btn.textContent;
        btn.textContent = "Enhancing...";
        btn.disabled = true;

        // Show a pulse on the row being enhanced
        const targetRow = document.querySelector(`tr[data-article-id="${currentEnhanceId}"]`);
        if (targetRow) {
            targetRow.style.transition = 'opacity 0.3s';
            targetRow.style.opacity = '0.6';
        }

        try {
            const response = await fetch(`${API_BASE_URL}/articles/${currentEnhanceId}/enhance`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response.ok) throw new Error("Failed to update article");
            const data = await response.json();

            // Optimistic cache update — no full re-fetch needed
            const cached = allArticlesCache.find(a => a.id === currentEnhanceId);
            if (cached) {
                cached.summary = data.new_summary;
                cached.status = 'pending';
                if (payload.publication_name && payload.publication_name.trim()) {
                    cached.publication_name = payload.publication_name;
                }
                if (payload.author && payload.author.trim()) {
                    cached.author = payload.author;
                }
            }

            // Swap just the affected row instead of full table re-render
            if (targetRow && cached) {
                const isChild = targetRow.querySelector('.border-l-4') !== null;
                const newRow = createArticleRow(cached, isChild);
                // Preserve data attributes
                for (const attr of targetRow.attributes) {
                    if (attr.name.startsWith('data-')) {
                        newRow.setAttribute(attr.name, attr.value);
                    }
                }
                targetRow.replaceWith(newRow);
                // Highlight the updated row
                newRow.style.transition = 'background 0.3s';
                newRow.style.background = '#ecfdf5';
                setTimeout(() => { newRow.style.background = ''; }, 2000);
            }

            closeEnhanceModal();
        } catch (error) {
            if (targetRow) targetRow.style.opacity = '1';
            alert("Error: " + error.message);
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    }

    function openEnhanceModal() { 
        if(!enhanceModal) return;
        enhanceModal.classList.remove('hidden'); 
        setTimeout(() => enhanceModal.classList.add('visible'), 10); 
    }

    function closeEnhanceModal() { 
        if(!enhanceModal) return;
        enhanceModal.classList.remove('visible'); 
        setTimeout(() => enhanceModal.classList.add('hidden'), 300); 
    }

    // --- FIND SIMILAR & CLUSTERING ---

    async function handleFindSimilarLogic(id, headline) {
        try {
            // Try smart-similar first (AI-classified relationships)
            const res = await fetch(`${API_BASE_URL}/articles/${id}/smart-similar`, { method: 'POST' });
            if (!res.ok) throw new Error("Smart-similar failed");
            const data = await res.json();
            showSimilarArticlesModal(id, headline, data, true);
        } catch(err) {
            // Fallback to basic similar if smart fails
            try {
                const res = await fetch(`${API_BASE_URL}/articles/${id}/similar`);
                if (!res.ok) throw new Error("Failed to fetch similar articles");
                const data = await res.json();
                showSimilarArticlesModal(id, headline, data, false);
            } catch(fallbackErr) {
                alert("Error: " + fallbackErr.message);
            }
        }
    }

    function formatRelationship(rel) {
        const labels = {
            'ADDS_DETAIL': 'Adds Detail',
            'DIFFERENT_ANGLE': 'Different Angle',
            'CONTRARIAN': 'Contrarian',
            'DUPLICATE': 'Duplicate',
            'RELATED': 'Related',
        };
        return labels[rel] || rel;
    }

    function showSimilarArticlesModal(originalArticleId, originalHeadline, similarArticles, isSmartMode) {
        const existingOverlay = document.querySelector('.similar-modal-overlay');
        if(existingOverlay) document.body.removeChild(existingOverlay);

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay similar-modal-overlay';

        const displayArticles = similarArticles.slice(0, 10);
        const VALUABLE_TYPES = ['ADDS_DETAIL', 'DIFFERENT_ANGLE', 'CONTRARIAN'];

        let articlesHtml = '';
        if (displayArticles.length > 0) {
            articlesHtml = displayArticles.map(article => {
                const similarity = article.distance || article.similarity || 0;
                const simPct = Math.round(similarity * 100);

                // In smart mode: pre-check valuable articles, uncheck duplicates
                const isValuable = isSmartMode && VALUABLE_TYPES.includes(article.relationship);
                const isDuplicate = isSmartMode && (article.relationship === 'DUPLICATE' || article.relationship === 'RELATED');
                const isChecked = isSmartMode ? isValuable : true;

                // Relationship labels (only in smart mode)
                let relationshipHtml = '';
                if (isSmartMode && article.relationship) {
                    const relClass = article.relationship.toLowerCase();
                    relationshipHtml = `
                        <div class="flex items-center gap-2 mt-1">
                            <span class="similarity-badge">${simPct}%</span>
                            <span class="relationship-label rel-${relClass}">${formatRelationship(article.relationship)}</span>
                        </div>`;
                    if (article.reason) {
                        relationshipHtml += `<p class="text-xs text-gray-400 italic mt-1">${article.reason}</p>`;
                    }
                } else if (similarity > 0) {
                    relationshipHtml = `<span class="similarity-badge mt-1">${simPct}% match</span>`;
                }

                const rowOpacity = isDuplicate ? 'opacity-60' : '';

                return `
                    <div class="similar-article p-3 border-b border-gray-100 hover:bg-gray-50 flex items-start ${rowOpacity}">
                        <input type="checkbox" class="similar-article-checkbox mt-1 mr-3 h-4 w-4" data-id="${article.id}" ${isChecked ? 'checked' : ''}>
                        <div class="similar-article-details flex-1">
                            <a href="${article.url}" target="_blank" class="similar-article-headline text-blue-600 font-semibold hover:underline block">${article.headline || article.headline_original}</a>
                            <div class="similar-article-meta text-xs text-gray-500 mt-1">
                                <span class="font-bold">${article.publication_name || 'N/A'}</span> | ${article.category || 'N/A'} | Status: ${article.status}
                            </div>
                            ${relationshipHtml}
                        </div>
                    </div>`;
            }).join('');
        } else {
            articlesHtml = '<p class="text-gray-500 p-4 text-center">No similar articles found.</p>';
        }

        // Truncate headline for modal title
        const shortHeadline = originalHeadline.length > 60 ? originalHeadline.substring(0, 60) + '...' : originalHeadline;
        const modeLabel = isSmartMode ? 'AI-labeled — valuable pre-checked, duplicates unchecked' : '';

        overlay.innerHTML = `
            <div class="modal-container bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 overflow-hidden flex flex-col max-h-[90vh]">
                <div class="modal-header bg-gray-100 p-4 border-b flex justify-between items-center gap-3">
                    <div class="min-w-0 flex-1">
                        <h2 class="text-lg font-bold text-gray-800 truncate">Similar to: "${shortHeadline}"</h2>
                        ${modeLabel ? `<p class="text-xs text-green-600 font-semibold mt-1">${modeLabel}</p>` : ''}
                    </div>
                    <button class="modal-close-btn text-gray-500 hover:text-gray-700 text-2xl leading-none flex-shrink-0 px-2">&times;</button>
                </div>

                <div class="modal-body p-0 overflow-y-auto flex-1">
                    ${articlesHtml}
                </div>

                <div class="p-4 border-t bg-gray-50 space-y-2">
                    <div id="analysis-result-container" class="mb-3 hidden bg-blue-50 p-3 rounded text-sm text-gray-700">
                        <strong>AI Analysis:</strong> <span id="analysis-result-text">Initializing...</span>
                    </div>
                    <button id="analyze-cluster-btn" class="w-full bg-purple-600 text-white py-2 px-4 rounded hover:bg-purple-700 transition font-bold disabled:opacity-50" ${displayArticles.length === 0 ? 'disabled' : ''}>
                        Cluster & Submit
                    </button>
                    <button id="close-similar-btn" class="w-full bg-gray-200 text-gray-700 py-2 px-4 rounded hover:bg-gray-300 transition font-semibold">
                        Cancel
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const close = () => {
            overlay.classList.remove('visible');
            setTimeout(() => { if(document.body.contains(overlay)) document.body.removeChild(overlay); }, 200);
        };

        overlay.querySelector('.modal-close-btn').addEventListener('click', close);
        overlay.querySelector('#close-similar-btn').addEventListener('click', close);
        overlay.addEventListener('click', (e) => { if(e.target === overlay) close(); });

        const analyzeBtn = overlay.querySelector('#analyze-cluster-btn');
        if(analyzeBtn) {
            analyzeBtn.addEventListener('click', () => handleAnalyzeCluster(overlay, originalArticleId));
        }

        setTimeout(() => overlay.classList.add('visible'), 10);
    }

    async function handleAnalyzeCluster(overlay, oid) {
        const cids = Array.from(overlay.querySelectorAll('.similar-article-checkbox:checked')).map(cb => parseInt(cb.dataset.id));
        
        if(!cids.length) {
            alert("Please select at least one similar article to cluster.");
            return;
        }

        const resContainer = overlay.querySelector('#analysis-result-container');
        const resText = overlay.querySelector('#analysis-result-text');
        const btn = overlay.querySelector('#analyze-cluster-btn');

        resContainer.classList.remove('hidden');
        resContainer.style.display = 'block';
        resText.textContent = 'Analyzing and clustering...';
        btn.disabled = true;
        btn.textContent = "Processing...";

        try { 
            const res = await fetch(`${API_BASE_URL}/cluster/approve`, { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({ 
                    original_article_id: parseInt(oid), 
                    cluster_ids: cids 
                }), 
            }); 
            
            if (!res.ok) throw new Error('Network error during clustering');
            const result = await res.json(); 
            
            resText.innerHTML = "Success! " + result.new_summary; 
            btn.textContent = "Done";
            
            setTimeout(() => {
                overlay.classList.remove('visible');
                setTimeout(() => document.body.removeChild(overlay), 200);
                fetchArticles(false, parseInt(oid));
            }, 2000);
            
        } catch (error) { 
            resText.textContent = 'Error: ' + error.message; 
            resContainer.classList.add('bg-red-50', 'text-red-700');
            btn.disabled = false;
            btn.textContent = "Try Again";
        }
    }

    // =========================================
    // NEWSLETTER GENERATOR (M3: SERVER-DRIVEN + AI BRIEF)
    // =========================================
    async function generateNewsletter(regenerate = false) {
        // Show modal immediately with loading state
        newsletterModal.classList.remove('hidden');
        showNewsletterLoading(true);

        if (newsletterStatus) {
            newsletterStatus.style.display = 'block';
            newsletterStatus.textContent = 'Generating AI brief and building newsletter...';
            newsletterStatus.style.color = '#2563eb';
        }

        // Reset Beehiiv button
        if (pushBeehiivBtn) {
            pushBeehiivBtn.disabled = false;
            pushBeehiivBtn.textContent = 'Push to Beehiiv (Draft)';
            pushBeehiivBtn.style.background = '#7c3aed';
            pushBeehiivBtn.style.cursor = 'pointer';
        }

        try {
            const res = await fetch(`${API_BASE_URL}/newsletter/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ regenerate: regenerate })
            });
            // Read body ONCE as text, then parse — prevents "Body already consumed" errors
            const rawText = await res.text();
            if (!res.ok) {
                let errMsg = 'Generation failed';
                try {
                    const err = JSON.parse(rawText);
                    errMsg = err.detail || errMsg;
                } catch {
                    if (rawText.includes('<!DOCTYPE') || rawText.includes('<html')) {
                        errMsg = `Server returned HTML instead of JSON (status ${res.status}). The newsletter endpoint may not be loaded — try rebuilding the container.`;
                    } else {
                        errMsg = `Server error (${res.status}): ${rawText.substring(0, 200)}`;
                    }
                }
                throw new Error(errMsg);
            }
            let data;
            try {
                data = JSON.parse(rawText);
            } catch {
                throw new Error(`Invalid response from server. Expected JSON but got: ${rawText.substring(0, 200)}`);
            }
            currentBriefId = data.id;

            // Populate subject
            if (newsletterSubject) newsletterSubject.value = data.subject_line || '';

            // Populate preview iframe + raw HTML
            const fullHtml = data.newsletter_html || data.summary_html || '';
            if (newsletterPreview) newsletterPreview.srcdoc = fullHtml;
            if (newsletterOutput) newsletterOutput.value = fullHtml;

            // Word count
            if (newsletterWordCount && data.word_count) {
                newsletterWordCount.textContent = `AI Brief: ${data.word_count} words`;
            }

            // Update status
            if (newsletterStatus) {
                newsletterStatus.textContent = regenerate ? 'Newsletter regenerated with fresh AI brief.' : 'Newsletter generated successfully.';
                newsletterStatus.style.color = '#16a34a';
            }

            // Show preview mode by default
            showPreviewMode();

            // Update Beehiiv button state
            if (pushBeehiivBtn && data.published) {
                pushBeehiivBtn.disabled = true;
                pushBeehiivBtn.textContent = 'Already Published';
                pushBeehiivBtn.style.background = '#9ca3af';
                pushBeehiivBtn.style.cursor = 'not-allowed';
            }

            // Refresh history sidebar
            fetchNewsletterHistory();

        } catch (e) {
            if (newsletterStatus) {
                newsletterStatus.textContent = 'Error: ' + e.message;
                newsletterStatus.style.color = '#dc2626';
            }
        } finally {
            showNewsletterLoading(false);
        }
    }

    function showNewsletterLoading(show) {
        if (!newsletterPreview) return;
        if (show) {
            newsletterPreview.srcdoc = `<div style="display:flex;align-items:center;justify-content:center;height:100%;font-family:Inter,system-ui,sans-serif;color:#666;">
                <div style="text-align:center;">
                    <div style="width:40px;height:40px;border:4px solid #e5e7eb;border-top-color:#7c3aed;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 12px;"></div>
                    <p style="margin:0 0 4px;">Generating newsletter with AI brief...</p>
                    <p style="font-size:12px;color:#999;margin:0;">This may take 10-15 seconds</p>
                </div>
                <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
            </div>`;
            newsletterPreview.classList.remove('hidden');
            if (newsletterOutput) newsletterOutput.classList.add('hidden');
        }
    }

    function showPreviewMode() {
        if (newsletterPreview) newsletterPreview.style.display = '';
        if (newsletterOutput) newsletterOutput.style.display = 'none';
        if (togglePreviewBtn) { togglePreviewBtn.style.background = '#f3e8ff'; togglePreviewBtn.style.color = '#7c3aed'; }
        if (toggleHtmlBtn) { toggleHtmlBtn.style.background = '#f3f4f6'; toggleHtmlBtn.style.color = '#6b7280'; }
    }

    function showHtmlMode() {
        if (newsletterPreview) newsletterPreview.style.display = 'none';
        if (newsletterOutput) newsletterOutput.style.display = '';
        if (toggleHtmlBtn) { toggleHtmlBtn.style.background = '#f3e8ff'; toggleHtmlBtn.style.color = '#7c3aed'; }
        if (togglePreviewBtn) { togglePreviewBtn.style.background = '#f3f4f6'; togglePreviewBtn.style.color = '#6b7280'; }
    }

    async function handlePushToBeehiiv() {
        if (!currentBriefId) return alert('No newsletter generated yet. Click "Generate Newsletter" first.');
        if (!confirm('Push this newsletter to Beehiiv as a draft?')) return;

        if (pushBeehiivBtn) {
            pushBeehiivBtn.disabled = true;
            pushBeehiivBtn.textContent = 'Publishing...';
        }
        if (newsletterStatus) {
            newsletterStatus.style.display = 'block';
            newsletterStatus.style.color = '#2563eb';
            newsletterStatus.textContent = 'Pushing to Beehiiv...';
        }

        try {
            const res = await fetch(`${API_BASE_URL}/newsletter/${currentBriefId}/publish`, {
                method: 'POST'
            });
            const rawText = await res.text();
            if (!res.ok) {
                let errMsg = 'Publish failed';
                try {
                    const err = JSON.parse(rawText);
                    errMsg = err.detail || errMsg;
                } catch {
                    errMsg = `Server error (${res.status})`;
                }
                throw new Error(errMsg);
            }
            const data = JSON.parse(rawText);

            if (newsletterStatus) {
                newsletterStatus.textContent = `Draft created in Beehiiv! Post ID: ${data.beehiiv_post_id}`;
                newsletterStatus.style.color = '#16a34a';
            }
            if (pushBeehiivBtn) {
                pushBeehiivBtn.textContent = 'Published';
                pushBeehiivBtn.style.background = '#9ca3af';
                pushBeehiivBtn.style.cursor = 'not-allowed';
            }
            fetchNewsletterHistory();
        } catch (e) {
            if (newsletterStatus) {
                newsletterStatus.textContent = 'Error: ' + e.message;
                newsletterStatus.style.color = '#dc2626';
            }
            if (pushBeehiivBtn) {
                pushBeehiivBtn.disabled = false;
                pushBeehiivBtn.textContent = 'Push to Beehiiv (Draft)';
            }
        }
    }

    async function fetchNewsletterHistory() {
        if (!newsletterHistoryList) return;
        try {
            const res = await fetch(`${API_BASE_URL}/newsletter/history?limit=15`);
            if (!res.ok) return;
            const briefs = await res.json();

            if (briefs.length === 0) {
                newsletterHistoryList.innerHTML = '<div style="color:#999; font-size:0.75rem;">No newsletters yet.</div>';
                return;
            }

            newsletterHistoryList.innerHTML = briefs.map(b => {
                const isActive = b.id === currentBriefId;
                const borderColor = isActive ? '#7c3aed' : '#e5e7eb';
                const bgColor = isActive ? '#f3e8ff' : '#fff';
                const pubLabel = b.published
                    ? '<span style="color:#16a34a; font-weight:700; margin-left:4px;">Published</span>'
                    : '<span style="color:#d97706; margin-left:4px;">Draft</span>';
                return `
                    <div onclick="loadHistoryBrief(${b.id})" style="padding:8px; border-radius:4px; border:1px solid ${borderColor}; background:${bgColor}; cursor:pointer; transition:background 0.15s;">
                        <div style="font-weight:600; color:#374151;">${b.date}</div>
                        <div style="font-size:0.7rem; color:#6b7280;">${b.word_count || 0} words ${pubLabel}</div>
                    </div>`;
            }).join('');
        } catch (e) {
            console.error('Error fetching newsletter history:', e);
        }
    }

    window.loadHistoryBrief = async (briefId) => {
        try {
            const res = await fetch(`${API_BASE_URL}/newsletter/${briefId}`);
            if (!res.ok) throw new Error('Failed to load');
            const data = await res.json();
            currentBriefId = data.id;

            if (newsletterSubject) newsletterSubject.value = data.subject_line || '';
            const fullHtml = data.newsletter_html || data.summary_html || '';
            if (newsletterPreview) newsletterPreview.srcdoc = fullHtml;
            if (newsletterOutput) newsletterOutput.value = fullHtml;
            if (newsletterWordCount && data.word_count) newsletterWordCount.textContent = `AI Brief: ${data.word_count} words`;

            showPreviewMode();

            // Update Beehiiv button state
            if (pushBeehiivBtn) {
                if (data.published) {
                    pushBeehiivBtn.disabled = true;
                    pushBeehiivBtn.textContent = 'Already Published';
                    pushBeehiivBtn.style.background = '#9ca3af';
                    pushBeehiivBtn.style.cursor = 'not-allowed';
                } else {
                    pushBeehiivBtn.disabled = false;
                    pushBeehiivBtn.textContent = 'Push to Beehiiv (Draft)';
                    pushBeehiivBtn.style.background = '#7c3aed';
                    pushBeehiivBtn.style.cursor = 'pointer';
                }
            }

            if (newsletterStatus) {
                newsletterStatus.style.display = 'block';
                newsletterStatus.textContent = `Loaded newsletter from ${data.date}`;
                newsletterStatus.style.color = '#2563eb';
            }

            // Re-render history to highlight active
            fetchNewsletterHistory();
        } catch (e) {
            alert('Error loading brief: ' + e.message);
        }
    };

    // ... (Remainder of file: Podcast Metadata, Batch, Managers) ...
    // =========================================
    // PODCAST METADATA
    // =========================================
    async function handleFetchMeta() { 
        const url = document.getElementById('podcast-link').value; 
        if(!url) return alert("Enter URL"); 
        
        const btn = document.getElementById('fetch-podcast-meta-btn'); 
        btn.textContent = "Fetching..."; 
        btn.disabled = true; 
        
        try { 
            const res = await fetch(`${API_BASE_URL}/api/scrape-metadata`, { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({ url: url }) 
            }); 
            
            if(!res.ok) throw new Error("Failed"); 
            const data = await res.json(); 
            
            document.getElementById('podcast-show').value = data.site_name || "Featured";
            document.getElementById('podcast-title').value = data.title || "";
            document.getElementById('podcast-desc').value = data.description || "";
            document.getElementById('podcast-image-url').value = data.image_url || "";

            // Auto-fill video URL for YouTube links
            const videoUrlField = document.getElementById('podcast-video-url');
            const videoPreview = document.getElementById('podcast-video-preview');
            const videoIframe = document.getElementById('podcast-video-iframe');
            if ((url.includes('youtube.com') || url.includes('youtu.be')) && videoUrlField) {
                videoUrlField.value = url;
                const match = url.match(/(?:v=|\/embed\/|youtu\.be\/)([\w-]{11})/);
                if (match && videoPreview && videoIframe) {
                    videoIframe.src = `https://www.youtube.com/embed/${match[1]}`;
                    videoPreview.style.display = 'block';
                }
            }
        } catch(e) {
            alert("Failed: " + e.message);
        } finally {
            btn.textContent = "Fetch";
            btn.disabled = false;
        }
    }

    // =========================================
    // UTILS (Batch, Checkboxes, Manual Submit)
    // =========================================
    async function handleBatch(status) { 
        const ids = Array.from(document.querySelectorAll('.article-checkbox:checked')).map(cb => parseInt(cb.dataset.id)); 
        if(!ids.length) return; 
        await fetch(`${API_BASE_URL}/articles/batch-update`, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({ ids, status }) 
        }); 
        fetchArticles(true); 
    }

    function handleSelectAll(e) { 
        document.querySelectorAll('.article-checkbox').forEach(cb => cb.checked = e.target.checked); 
        updateCheckboxStates(); 
    }

    function updateCheckboxStates() { 
        const all = document.querySelectorAll('.article-checkbox'); 
        if(selectAllCheckbox) selectAllCheckbox.checked = all.length && Array.from(all).every(cb => cb.checked); 
    }

    function showLoading(show) { 
        if(loadingEl) loadingEl.style.display = show ? 'table-row' : 'none'; 
    }

    async function handleManualSubmit(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData.entries());
        data.is_top_story = document.getElementById('manual-is-top').checked;
        try {
            const res = await fetch(`${API_BASE_URL}/articles/manual-submission`, { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(data) 
            });
            if(!res.ok) throw new Error("Failed");
            e.target.reset();
            fetchArticles(true);
            alert("Article Added");
        } catch(err) { alert(err.message); }
    }

    // --- OTHER MANAGERS ---
    async function handleTweetSubmit(e) { 
        e.preventDefault(); 
        const btn=e.target.querySelector('button'); 
        btn.disabled=true; 
        try{ 
            await fetch(`${API_BASE_URL}/tweets`, {
                method:'POST', 
                headers:{'Content-Type':'application/json'}, 
                body:JSON.stringify({url: document.getElementById('tweet-url').value})
            }); 
            e.target.reset(); 
            fetchTweetManagerList(); 
            alert("Posted!"); 
        } catch(err){ alert(err.message); } 
        finally { btn.disabled=false; } 
    }

    async function fetchTweetManagerList() { 
        const tb=document.getElementById('tweets-manager-tbody'); 
        if(!tb)return; 
        const res=await fetch(`${API_BASE_URL}/tweets`); 
        const items=await res.json(); 
        tb.innerHTML=items.map(t=>`<tr><td>${t.content}</td><td><button onclick="deleteItem('tweets', ${t.id})">🗑️</button></td></tr>`).join(''); 
    }

    async function handleSponsorSubmit(e) { 
        e.preventDefault(); 
        const fd=new FormData(e.target); 
        await fetch(`${API_BASE_URL}/sponsors`,{method:'POST', body:fd}); 
        e.target.reset(); 
        fetchSponsorsList(); 
    }

    async function fetchSponsorsList() {
        const tb=document.getElementById('sponsors-tbody');
        if(!tb)return;
        const res=await fetch(`${API_BASE_URL}/sponsors`);
        const items=await res.json();
        tb.innerHTML=items.map(s=>{
            const logoThumb = s.logo_url ? `<img src="${s.logo_url}" alt="${s.company_name}" style="max-height:30px;max-width:50px;vertical-align:middle;border-radius:2px;">` : '<span style="color:#999;font-size:0.75rem;">No logo</span>';
            const headlineText = (s.headline || '').length > 40 ? s.headline.slice(0, 40) + '...' : (s.headline || '');
            const linkShort = s.link_url ? `<a href="${s.link_url}" target="_blank" style="font-size:0.75rem;color:#1d4ed8;">Link</a>` : '';
            return `<tr>
                <td>${logoThumb}</td>
                <td style="font-weight:600;">${s.company_name}</td>
                <td style="font-size:0.85rem;color:#555;">${headlineText}</td>
                <td>${linkShort}</td>
                <td><button onclick="deleteItem('sponsors', ${s.id})">🗑️</button></td>
            </tr>`;
        }).join('');
    }

    async function handlePodcastSubmit(e) {
        e.preventDefault();
        const fd=new FormData(e.target);
        await fetch(`${API_BASE_URL}/podcasts`,{method:'POST', body:fd});
        e.target.reset();
        // Hide video preview after submit
        const vp = document.getElementById('podcast-video-preview');
        if (vp) vp.style.display = 'none';
        fetchPodcastsList();
    }

    async function fetchPodcastsList() {
        const tb=document.getElementById('podcasts-tbody');
        if(!tb)return;
        const res=await fetch(`${API_BASE_URL}/podcasts`);
        const items=await res.json();
        tb.innerHTML=items.map(p=>`<tr><td>${p.show_name}</td><td><button onclick="deleteItem('podcasts', ${p.id})">🗑️</button></td></tr>`).join('');
    }

    // =========================================
    // M2: SMART CURATION — AUTO-APPROVE/REJECT
    // =========================================

    async function handleAutoApprove() {
        const threshold = prompt("Set auto-approve threshold (preview first, then commit):", String(currentAutoApproveThreshold));
        if (threshold === null) return;
        const val = parseFloat(threshold);
        if (isNaN(val)) return alert("Invalid number");

        // Step 1: Update threshold + filters — PREVIEW only, no commit
        currentAutoApproveThreshold = val;
        updateAutoButtonLabels();
        updateScoreDistribution();

        // Activate the auto-approve filter pill so user sees what will be approved
        document.querySelectorAll('.filter-pill[data-filter-type="score"]')
            .forEach(p => p.classList.remove('active'));
        const approvePill = document.querySelector('.filter-pill[data-value="auto-approve"]');
        if (approvePill) approvePill.classList.add('active');
        currentScoreFilter = 'auto-approve';
        renderArticles();

        // Step 2: Show "Commit" button — let the browser paint the preview first
        // (Previously used confirm() which blocked paint and skipped preview)
        const allPendingAbove = allArticlesCache.filter(
            a => a.status === 'pending' && (a.auto_approval_score || 0) >= val
        ).length;

        if (allPendingAbove === 0) {
            alert(`No pending articles with score ≥ ${val}. Adjust threshold or review the filter.`);
            return;
        }

        // Show a commit banner at the top of the articles area
        let commitBanner = document.getElementById('auto-approve-commit-banner');
        if (commitBanner) commitBanner.remove();
        commitBanner = document.createElement('div');
        commitBanner.id = 'auto-approve-commit-banner';
        commitBanner.style.cssText = 'background:#ecfdf5;border:2px solid #10b981;border-radius:8px;padding:12px 20px;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;gap:12px;';

        let countText = `<strong>${allPendingAbove}</strong> pending articles with score ≥ ${val} across ALL dates will be approved.`;
        if (currentDateFilter !== 'All') {
            const scopedAbove = allArticlesCache.filter(
                a => a.status === 'pending' && (a.auto_approval_score || 0) >= val && getArticleLocalDate(a) === currentDateFilter
            ).length;
            countText = `Previewing <strong>${scopedAbove}</strong> for selected date. Total: <strong>${allPendingAbove}</strong> across ALL dates.`;
        }

        commitBanner.innerHTML = `
            <span style="font-size:0.85rem;color:#065f46;">📋 Preview: ${countText}</span>
            <div style="display:flex;gap:8px;flex-shrink:0;">
                <button id="commit-auto-approve-btn" style="background:#10b981;color:#fff;border:none;padding:8px 20px;border-radius:6px;font-weight:600;font-size:0.85rem;cursor:pointer;">✓ Commit Auto-Approve</button>
                <button id="cancel-auto-approve-btn" style="background:#f3f4f6;color:#374151;border:1px solid #d1d5db;padding:8px 16px;border-radius:6px;font-size:0.85rem;cursor:pointer;">Cancel</button>
            </div>
        `;

        const tableContainer = articlesTbody ? articlesTbody.closest('table')?.parentElement : null;
        if (tableContainer) {
            tableContainer.insertBefore(commitBanner, tableContainer.firstChild);
        }

        // Commit button handler
        document.getElementById('commit-auto-approve-btn').addEventListener('click', async () => {
            const commitBtn = document.getElementById('commit-auto-approve-btn');
            commitBtn.textContent = 'Approving...';
            commitBtn.disabled = true;
            try {
                const res = await fetch(`${API_BASE_URL}/articles/auto-approve`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ threshold: val })
                });
                if (!res.ok) throw new Error("Failed");
                const data = await res.json();
                commitBanner.remove();
                alert(data.message);
                fetchArticles(true);
            } catch (e) {
                commitBtn.textContent = '✓ Commit Auto-Approve';
                commitBtn.disabled = false;
                alert("Error: " + e.message);
            }
        });

        // Cancel button handler
        document.getElementById('cancel-auto-approve-btn').addEventListener('click', () => {
            commitBanner.remove();
        });
    }

    async function handleAutoReject() {
        const threshold = prompt("Set auto-reject threshold (preview first, then commit):", String(currentAutoRejectThreshold));
        if (threshold === null) return;
        const val = parseFloat(threshold);
        if (isNaN(val)) return alert("Invalid number");

        // Step 1: Update threshold + filters — PREVIEW only, no commit
        currentAutoRejectThreshold = val;
        updateAutoButtonLabels();
        updateScoreDistribution();

        // Activate the auto-reject filter pill so user sees what will be rejected
        document.querySelectorAll('.filter-pill[data-filter-type="score"]')
            .forEach(p => p.classList.remove('active'));
        const rejectPill = document.querySelector('.filter-pill[data-value="auto-reject"]');
        if (rejectPill) rejectPill.classList.add('active');
        currentScoreFilter = 'auto-reject';
        renderArticles();

        // Step 2: Ask user to commit
        const allPendingBelow = allArticlesCache.filter(
            a => a.status === 'pending' && (a.auto_approval_score || 0) <= val
        ).length;

        if (allPendingBelow === 0) {
            alert(`No pending articles with score ≤ ${val}. Adjust threshold or review the filter.`);
            return;
        }

        let confirmMsg = `This will reject ${allPendingBelow} pending articles with score ≤ ${val} across ALL dates.`;
        if (currentDateFilter !== 'All') {
            const scopedBelow = allArticlesCache.filter(
                a => a.status === 'pending' && (a.auto_approval_score || 0) <= val && getArticleLocalDate(a) === currentDateFilter
            ).length;
            confirmMsg = `Currently viewing ${scopedBelow} for selected date.\nTotal: ${allPendingBelow} pending articles with score ≤ ${val} across ALL dates will be rejected.`;
        }
        confirmMsg += `\n\nCommit auto-reject now? (Click Cancel to just preview)`;
        if (!confirm(confirmMsg)) return;

        try {
            const res = await fetch(`${API_BASE_URL}/articles/auto-reject`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ threshold: val })
            });
            if (!res.ok) throw new Error("Failed");
            const data = await res.json();
            alert(data.message);
            fetchArticles(true);
        } catch (e) {
            alert("Error: " + e.message);
        }
    }

    function toggleScoreSort() {
        if (currentSortBy === 'auto_approval_score') {
            currentSortOrder = currentSortOrder === 'desc' ? 'asc' : 'desc';
        } else {
            currentSortBy = 'auto_approval_score';
            currentSortOrder = 'desc';
        }
        const arrow = document.getElementById('score-sort-arrow');
        if (arrow) arrow.textContent = currentSortOrder === 'desc' ? '▼' : '▲';
        fetchArticles(true);
    }

    // =========================================
    // M2: SOURCE MANAGEMENT
    // =========================================

    async function fetchSourcesList() {
        const tb = document.getElementById('sources-tbody');
        if (!tb) return;
        try {
            const res = await fetch(`${API_BASE_URL}/api/sources`);
            if (!res.ok) return;
            const sources = await res.json();
            tb.innerHTML = sources.map(s => {
                const rssDisplay = s.rss_feed_url
                    ? `<a href="${s.rss_feed_url}" target="_blank" class="text-blue-600 hover:underline" title="${s.rss_feed_url}">${s.rss_feed_url.length > 30 ? s.rss_feed_url.substring(0, 30) + '...' : s.rss_feed_url}</a>`
                    : '';
                const handleDisplay = s.twitter_handle || '';
                return `
                <tr>
                    <td class="font-medium text-gray-800">${s.name}</td>
                    <td class="text-gray-500">${s.domain || '—'}</td>
                    <td class="text-xs">
                        <span class="editable-cell" onclick="editSourceField(${s.id}, 'rss_feed_url', this)" title="Click to edit">${rssDisplay || '<span class=&quot;text-gray-400 cursor-pointer&quot;>+ add feed</span>'}</span>
                    </td>
                    <td>
                        <span class="editable-cell" onclick="editSourceField(${s.id}, 'twitter_handle', this)" title="Click to edit">${handleDisplay ? `<span class="text-blue-700 font-medium">${handleDisplay}</span>` : '<span class=&quot;text-gray-400 cursor-pointer&quot;>+ add handle</span>'}</span>
                    </td>
                    <td>
                        <span class="score-indicator ${getScoreClass(s.credibility_score)}">${s.credibility_score}</span>
                    </td>
                    <td>${s.tier || '—'}</td>
                    <td>${s.total_articles || 0}</td>
                    <td class="text-green-700">${s.approved_count || 0}</td>
                    <td class="text-red-700">${s.rejected_count || 0}</td>
                    <td>
                        <button onclick="deleteSource(${s.id})" class="text-red-500 hover:text-red-700 text-xs font-semibold">Delete</button>
                    </td>
                </tr>
            `}).join('');
        } catch (e) {
            console.error('Error fetching sources:', e);
        }
    }

    window.deleteSource = async (id) => {
        if (!confirm("Delete this source? Articles will be unlinked.")) return;
        try {
            const res = await fetch(`${API_BASE_URL}/api/sources/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error("Failed");
            fetchSourcesList();
        } catch (e) {
            alert("Error: " + e.message);
        }
    };

    window.editSourceField = (sourceId, field, spanEl) => {
        // Prevent double-click creating multiple inputs
        if (spanEl.querySelector('input')) return;

        const currentValue = field === 'twitter_handle'
            ? (spanEl.querySelector('.text-blue-700')?.textContent || '')
            : (spanEl.querySelector('a')?.getAttribute('href') || '');

        const placeholder = field === 'twitter_handle' ? '@handle' : 'https://feed-url...';
        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentValue;
        input.placeholder = placeholder;
        input.className = 'p-1 border rounded text-sm w-full';
        input.style.minWidth = field === 'twitter_handle' ? '100px' : '180px';

        spanEl.innerHTML = '';
        spanEl.appendChild(input);
        input.focus();

        const saveValue = async () => {
            const newValue = input.value.trim();
            if (newValue === currentValue) {
                fetchSourcesList(); // Revert to display mode
                return;
            }
            try {
                const res = await fetch(`${API_BASE_URL}/api/sources/${sourceId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ [field]: newValue || null })
                });
                if (!res.ok) throw new Error("Update failed");
                fetchSourcesList();
            } catch (err) {
                alert("Error: " + err.message);
                fetchSourcesList();
            }
        };

        input.addEventListener('blur', saveValue);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
            if (e.key === 'Escape') { fetchSourcesList(); }
        });
    };

    async function handleSourceSubmit(e) {
        e.preventDefault();
        const data = {
            name: document.getElementById('source-name').value,
            domain: document.getElementById('source-domain').value || null,
            credibility_score: parseInt(document.getElementById('source-credibility').value) || 50,
            tier: parseInt(document.getElementById('source-tier').value) || 3,
            country: document.getElementById('source-country').value || null,
            language: 'en',
            rss_feed_url: document.getElementById('source-rss-url').value || null,
            twitter_handle: document.getElementById('source-twitter-handle').value || null,
        };
        try {
            const res = await fetch(`${API_BASE_URL}/api/sources`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed");
            }
            e.target.reset();
            document.getElementById('source-credibility').value = '50';
            fetchSourcesList();
            alert("Source created!");
        } catch (err) {
            alert("Error: " + err.message);
        }
    }

    async function handleSeedSources() {
        if (!confirm("Seed sources table from existing article publication names?")) return;
        try {
            const res = await fetch(`${API_BASE_URL}/api/sources/seed`, { method: 'POST' });
            if (!res.ok) throw new Error("Failed");
            const data = await res.json();
            alert(data.message);
            fetchSourcesList();
        } catch (e) {
            alert("Error: " + e.message);
        }
    }

    async function handleRecalcSources() {
        if (!confirm("Recalculate credibility scores from approve/reject history?")) return;
        try {
            const res = await fetch(`${API_BASE_URL}/api/sources/recalculate`, { method: 'POST' });
            if (!res.ok) throw new Error("Failed");
            const data = await res.json();
            alert(data.message);
            fetchSourcesList();
        } catch (e) {
            alert("Error: " + e.message);
        }
    }

    // =========================================
    // GOOGLE NEWS INTELLIGENCE BUILDER
    // =========================================

    let currentPreviewFeedData = null;

    // --- Event Listeners ---
    const generateGnewsBtn = document.getElementById('generate-gnews-btn');
    const migrateGnewsBtn = document.getElementById('migrate-gnews-btn');
    const gnewsManualPreviewBtn = document.getElementById('gnews-manual-preview-btn');
    const gnewsManualAddBtn = document.getElementById('gnews-manual-add-btn');
    const closeGnewsPreviewBtn = document.getElementById('close-gnews-preview-btn');
    const gnewsPreviewModal = document.getElementById('gnews-preview-modal');

    if (generateGnewsBtn) generateGnewsBtn.addEventListener('click', handleGenerateGnewsFeeds);
    if (migrateGnewsBtn) migrateGnewsBtn.addEventListener('click', handleMigrateGnewsFeeds);
    if (gnewsManualPreviewBtn) gnewsManualPreviewBtn.addEventListener('click', handleManualGnewsPreview);
    if (gnewsManualAddBtn) gnewsManualAddBtn.addEventListener('click', handleManualGnewsAdd);
    if (closeGnewsPreviewBtn) closeGnewsPreviewBtn.addEventListener('click', () => gnewsPreviewModal?.classList.add('hidden'));
    if (gnewsPreviewModal) gnewsPreviewModal.addEventListener('click', (e) => { if (e.target === gnewsPreviewModal) gnewsPreviewModal.classList.add('hidden'); });

    document.getElementById('gnews-preview-add-btn')?.addEventListener('click', async () => {
        if (!currentPreviewFeedData) return;
        await addFeedAsSource(currentPreviewFeedData.label, currentPreviewFeedData.rss_url);
        gnewsPreviewModal?.classList.add('hidden');
    });

    // Manual builder: live URL preview
    const manualQueryInput = document.getElementById('gnews-manual-query');
    const manualFreshnessSelect = document.getElementById('gnews-manual-freshness');
    if (manualQueryInput) {
        const updateManualUrl = () => {
            const q = manualQueryInput.value.trim();
            const f = manualFreshnessSelect?.value || '1d';
            const preview = document.getElementById('gnews-manual-url-preview');
            if (preview) {
                if (q) {
                    const encoded = encodeURIComponent(`${q} when:${f}`);
                    preview.textContent = `https://news.google.com/rss/search?q=${encoded}&hl=en-US&gl=US&ceid=US:en`;
                } else {
                    preview.textContent = 'URL will appear here...';
                }
            }
        };
        manualQueryInput.addEventListener('input', updateManualUrl);
        manualFreshnessSelect?.addEventListener('change', updateManualUrl);
    }

    // --- Init ---
    fetchActiveGnewsFeeds();
    checkGnewsMigrationNeeded();

    // --- Core Functions ---

    async function handleGenerateGnewsFeeds() {
        const description = document.getElementById('gnews-description')?.value?.trim();
        if (!description) return alert('Please describe the intelligence you want to track.');

        const region = document.getElementById('gnews-region')?.value || null;
        const focus = document.getElementById('gnews-focus')?.value || null;
        const freshness = document.getElementById('gnews-freshness')?.value || '1d';
        const statusEl = document.getElementById('gnews-generate-status');
        const resultsEl = document.getElementById('gnews-results');
        const btn = document.getElementById('generate-gnews-btn');

        btn.disabled = true;
        btn.textContent = '⏳ Generating...';
        if (statusEl) { statusEl.textContent = 'Asking AI to craft optimized search queries...'; statusEl.style.color = ''; }

        try {
            const res = await fetch(`${API_BASE_URL}/api/sources/generate-google-feeds`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ description, region, focus, freshness })
            });
            if (!res.ok) throw new Error((await res.json()).detail || 'Generation failed');
            const data = await res.json();

            if (statusEl) statusEl.textContent = `Generated ${data.feeds.length} feed suggestions`;
            window._gnewsGeneratedFeeds = data.feeds;

            resultsEl.innerHTML = data.feeds.map((feed, i) => `
                <div class="p-4 rounded border" style="background: var(--bg-card, #fff); border-color: var(--border-default);">
                    <div class="flex justify-between items-start mb-2">
                        <div class="flex-1 min-w-0 mr-3">
                            <span class="font-bold text-sm" style="color: var(--text-primary);">${feed.label}</span>
                            <p class="text-xs mt-1" style="color: var(--text-muted);">${feed.rationale}</p>
                        </div>
                        <div class="flex gap-2 flex-shrink-0">
                            <button onclick="previewGnewsFeed(${i})" class="text-xs font-semibold px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200 text-gray-700">Preview</button>
                            <button onclick="addGnewsFeedToSources(${i})" class="text-xs font-semibold px-3 py-1.5 rounded bg-green-600 hover:bg-green-700 text-white">+ Add</button>
                        </div>
                    </div>
                    <div class="text-xs font-mono p-2 rounded mt-2 break-all" style="background: var(--bg-section); color: var(--text-muted);">${feed.rss_url}</div>
                </div>
            `).join('');
        } catch (e) {
            if (statusEl) { statusEl.textContent = `Error: ${e.message}`; statusEl.style.color = '#dc2626'; }
        } finally {
            btn.disabled = false;
            btn.textContent = '✨ Generate Feeds';
        }
    }

    window.previewGnewsFeed = async (index) => {
        const feed = window._gnewsGeneratedFeeds?.[index];
        if (!feed) return;
        currentPreviewFeedData = feed;
        showGnewsPreview(feed.rss_url, feed.label);
    };

    window.addGnewsFeedToSources = async (index) => {
        const feed = window._gnewsGeneratedFeeds?.[index];
        if (!feed) return;
        await addFeedAsSource(feed.label, feed.rss_url);
    };

    async function showGnewsPreview(rssUrl, label) {
        const modal = document.getElementById('gnews-preview-modal');
        const titleEl = document.getElementById('gnews-preview-title');
        const contentEl = document.getElementById('gnews-preview-content');
        const countEl = document.getElementById('gnews-preview-count');

        if (titleEl) titleEl.textContent = `Preview: ${label || 'Feed'}`;
        if (contentEl) contentEl.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem;">⏳ Fetching headlines...</p>';
        if (modal) modal.classList.remove('hidden');

        try {
            const res = await fetch(`${API_BASE_URL}/api/sources/preview-feed`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rss_url: rssUrl })
            });
            if (!res.ok) throw new Error((await res.json()).detail || 'Preview failed');
            const data = await res.json();

            if (countEl) countEl.textContent = `${data.total_items} articles found`;

            if (data.headlines.length === 0) {
                contentEl.innerHTML = '<p style="color: #dc2626; font-size: 0.85rem;">No articles found. Try adjusting the query.</p>';
                return;
            }

            contentEl.innerHTML = data.headlines.map(h => `
                <div class="py-2" style="border-bottom: 1px solid var(--border-light, #eee);">
                    <a href="${h.url}" target="_blank" class="text-sm font-medium hover:underline" style="color: var(--accent-blue, #2563eb);">${h.title}</a>
                    <div class="flex gap-3 text-xs mt-1" style="color: var(--text-muted);">
                        ${h.source ? `<span>${h.source}</span>` : ''}
                        ${h.published ? `<span>${h.published}</span>` : ''}
                    </div>
                </div>
            `).join('');
        } catch (e) {
            contentEl.innerHTML = `<p style="color: #dc2626; font-size: 0.85rem;">Error: ${e.message}</p>`;
        }
    }

    async function addFeedAsSource(name, rssUrl) {
        const sourceName = name.startsWith('GNews:') ? name : `GNews: ${name}`;
        try {
            const res = await fetch(`${API_BASE_URL}/api/sources`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: sourceName,
                    domain: 'news.google.com',
                    credibility_score: 50,
                    tier: 2,
                    country: 'Global',
                    language: 'en',
                    rss_feed_url: rssUrl,
                    twitter_handle: null,
                })
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed');
            }
            alert(`Added "${sourceName}" to sources! It will be active on the next scraper run.`);
            fetchSourcesList();
            fetchActiveGnewsFeeds();
        } catch (e) {
            alert(`Error: ${e.message}`);
        }
    }

    async function fetchActiveGnewsFeeds() {
        const container = document.getElementById('gnews-active-feeds');
        if (!container) return;
        try {
            const res = await fetch(`${API_BASE_URL}/api/sources`);
            if (!res.ok) return;
            const sources = await res.json();
            const gnewsFeeds = sources.filter(s => s.rss_feed_url && s.rss_feed_url.includes('news.google.com/rss/search'));
            if (gnewsFeeds.length === 0) {
                container.innerHTML = '<p style="color: var(--text-muted);">No Google News feeds in database yet. Use the AI Generator or migrate hardcoded feeds above.</p>';
                return;
            }
            container.innerHTML = gnewsFeeds.map(s => {
                const safeName = s.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                const safeUrl = encodeURIComponent(s.rss_feed_url);
                return `
                    <div class="flex justify-between items-center py-1.5 px-2 rounded hover:bg-gray-50" style="border-bottom: 1px solid var(--border-light, #eee);">
                        <div class="flex-1 min-w-0">
                            <span class="text-sm font-medium" style="color: var(--text-primary);">${s.name}</span>
                            <span class="text-xs block truncate" style="color: var(--text-muted);">${s.rss_feed_url.length > 80 ? s.rss_feed_url.substring(0, 80) + '...' : s.rss_feed_url}</span>
                        </div>
                        <div class="flex gap-2 flex-shrink-0 ml-2">
                            <button onclick="previewExistingGnewsFeed('${safeUrl}', '${safeName}')" class="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-700">Preview</button>
                            <button onclick="deleteSource(${s.id})" class="text-xs px-2 py-1 rounded text-red-500 hover:text-red-700 font-semibold">Remove</button>
                        </div>
                    </div>
                `;
            }).join('');
        } catch (e) {
            container.innerHTML = '<p style="color: #dc2626;">Error loading feeds</p>';
        }
    }

    window.previewExistingGnewsFeed = (encodedUrl, label) => {
        const url = decodeURIComponent(encodedUrl);
        currentPreviewFeedData = { label, rss_url: url };
        showGnewsPreview(url, label);
    };

    async function handleMigrateGnewsFeeds() {
        if (!confirm('Migrate 13 hardcoded Google News feeds into the database? This is a one-time operation.')) return;
        const statusEl = document.getElementById('migrate-gnews-status');
        try {
            const res = await fetch(`${API_BASE_URL}/api/sources/migrate-google-feeds`, { method: 'POST' });
            const data = await res.json();
            if (statusEl) statusEl.textContent = data.message;
            fetchSourcesList();
            fetchActiveGnewsFeeds();
            document.getElementById('gnews-migrate-banner')?.classList.add('hidden');
        } catch (e) {
            if (statusEl) statusEl.textContent = `Error: ${e.message}`;
        }
    }

    async function checkGnewsMigrationNeeded() {
        try {
            const res = await fetch(`${API_BASE_URL}/api/sources`);
            if (!res.ok) return;
            const sources = await res.json();
            const gnewsCount = sources.filter(s => s.rss_feed_url && s.rss_feed_url.includes('news.google.com/rss/search')).length;
            const banner = document.getElementById('gnews-migrate-banner');
            if (banner && gnewsCount < 5) banner.classList.remove('hidden');
        } catch (e) { /* silently fail */ }
    }

    async function handleManualGnewsPreview() {
        const query = document.getElementById('gnews-manual-query')?.value?.trim();
        if (!query) return alert('Enter a search query.');
        const freshness = document.getElementById('gnews-manual-freshness')?.value || '1d';
        const encoded = encodeURIComponent(`${query} when:${freshness}`);
        const rssUrl = `https://news.google.com/rss/search?q=${encoded}&hl=en-US&gl=US&ceid=US:en`;
        currentPreviewFeedData = { label: query.substring(0, 40), rss_url: rssUrl };
        showGnewsPreview(rssUrl, 'Manual Query');
    }

    async function handleManualGnewsAdd() {
        const query = document.getElementById('gnews-manual-query')?.value?.trim();
        if (!query) return alert('Enter a search query first.');
        const freshness = document.getElementById('gnews-manual-freshness')?.value || '1d';
        const encoded = encodeURIComponent(`${query} when:${freshness}`);
        const rssUrl = `https://news.google.com/rss/search?q=${encoded}&hl=en-US&gl=US&ceid=US:en`;
        const label = prompt('Name for this feed:', query.substring(0, 50));
        if (!label) return;
        await addFeedAsSource(label, rssUrl);
    }

    // =========================================
    // M6: SOCIAL MEDIA FUNCTIONS
    // =========================================

    async function fetchSocialStatus() {
        const container = document.getElementById('social-status');
        if (!container) return;
        try {
            const res = await fetch(`${API_BASE_URL}/social/status`);
            if (!res.ok) return;
            const data = await res.json();
            container.innerHTML = Object.entries(data).map(([platform, info]) => {
                const dot = info.configured ? '🟢' : '🔴';
                let label = info.configured ? 'Connected' : 'Not configured';
                if (platform === 'twitter' && info.configured && info.monthly_posts !== undefined) {
                    label += ` (${info.monthly_posts}/${info.monthly_limit} posts this month)`;
                }
                return `<span>${dot} <b>${platform}</b>: ${label}</span>`;
            }).join('');
        } catch (e) {
            container.innerHTML = '<span class="text-red-500">Failed to load status</span>';
        }
    }

    async function fetchSocialHistory() {
        const tbody = document.getElementById('social-posts-tbody');
        if (!tbody) return;
        try {
            const res = await fetch(`${API_BASE_URL}/social/history?limit=${SOCIAL_PAGE_SIZE}&offset=${socialHistoryOffset}`);
            if (!res.ok) return;
            const data = await res.json();
            const total = data.total || 0;
            const totalPages = Math.max(1, Math.ceil(total / SOCIAL_PAGE_SIZE));
            const currentPage = Math.floor(socialHistoryOffset / SOCIAL_PAGE_SIZE) + 1;

            // Update pagination controls
            const prevBtn = document.getElementById('social-prev-btn');
            const nextBtn = document.getElementById('social-next-btn');
            const pageInfo = document.getElementById('social-page-info');
            if (prevBtn) prevBtn.disabled = socialHistoryOffset === 0;
            if (nextBtn) nextBtn.disabled = (socialHistoryOffset + SOCIAL_PAGE_SIZE) >= total;
            if (pageInfo) pageInfo.textContent = `Page ${currentPage} of ${totalPages} (${total} posts)`;

            if (!data.posts || data.posts.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-gray-400">No posts yet</td></tr>';
                return;
            }
            tbody.innerHTML = data.posts.map(p => {
                const statusColor = p.status === 'sent' ? 'text-green-600' : 'text-red-600';
                const contentPreview = (p.content_text || '').replace(/<[^>]*>/g, '').slice(0, 80) + '...';
                const headline = p.article_headline || contentPreview;
                const time = p.posted_at ? new Date(p.posted_at).toLocaleString() : '—';
                return `<tr class="border-b">
                    <td class="p-2 font-semibold">${p.platform === 'telegram' ? '📢' : '𝕏'} ${p.platform}</td>
                    <td class="p-2">${p.post_type}</td>
                    <td class="p-2 text-xs">${headline.slice(0, 60)}</td>
                    <td class="p-2 ${statusColor} font-semibold">${p.status}</td>
                    <td class="p-2 text-xs text-gray-500">${time}</td>
                </tr>`;
            }).join('');
        } catch (e) {
            tbody.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-red-500">Failed to load history</td></tr>';
        }
    }

    async function handleCheckBreakingNews() {
        const btn = document.getElementById('check-breaking-btn');
        const result = document.getElementById('breaking-result');
        if (btn) { btn.disabled = true; btn.textContent = 'Checking...'; }
        try {
            const res = await fetch(`${API_BASE_URL}/social/breaking-news/check`, { method: 'POST' });
            const data = await res.json();
            if (result) {
                result.textContent = `Found ${data.articles_found} articles, posted ${data.articles_posted}`;
                result.style.color = data.articles_posted > 0 ? '#16a34a' : '#6b7280';
            }
            fetchSocialHistory();
        } catch (e) {
            if (result) { result.textContent = 'Error: ' + e.message; result.style.color = '#dc2626'; }
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '🔴 Check Breaking News Now'; }
        }
    }

    // M6 Phase 2: X/Twitter posting
    window.postArticleToTwitter = async (articleId) => {
        // First get a preview of the tweet
        try {
            const previewRes = await fetch(`${API_BASE_URL}/social/preview/article/${articleId}?platform=twitter`);
            const previewData = await previewRes.json();
            const tweetText = previewData.content || '';

            // Expand the Social Media <details> section if collapsed
            const socialDetails = document.querySelector('details:has(#tweet-compose-text)');
            if (socialDetails && !socialDetails.open) {
                socialDetails.open = true;
            }

            // Show in composer for editing before posting
            const composer = document.getElementById('tweet-compose-text');
            const charCount = document.getElementById('tweet-char-count');
            if (composer) {
                composer.value = tweetText;
                composer.dataset.articleId = articleId;
                if (charCount) charCount.textContent = `${tweetText.length}/280`;
                // Small delay to let the details section expand before scrolling
                setTimeout(() => {
                    composer.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    composer.focus();
                }, 100);
            }
        } catch (e) {
            alert('Failed to generate tweet preview: ' + e.message);
        }
    };

    // Tweet composer character counter
    const tweetComposeText = document.getElementById('tweet-compose-text');
    const tweetCharCount = document.getElementById('tweet-char-count');
    if (tweetComposeText && tweetCharCount) {
        tweetComposeText.addEventListener('input', () => {
            const len = tweetComposeText.value.length;
            tweetCharCount.textContent = `${len}/280`;
            tweetCharCount.style.color = len > 260 ? (len > 280 ? '#dc2626' : '#f59e0b') : '#9ca3af';
        });
    }

    // Post tweet button
    const postTweetBtn = document.getElementById('post-tweet-btn');
    if (postTweetBtn) {
        postTweetBtn.addEventListener('click', async () => {
            const text = document.getElementById('tweet-compose-text')?.value;
            if (!text) return alert('Write a tweet first.');
            if (text.length > 280) return alert('Tweet exceeds 280 characters.');
            if (!confirm('Post this tweet to X?')) return;

            const composerEl = document.getElementById('tweet-compose-text');
            const articleId = composerEl?.dataset.articleId || null;
            const quoteTweetId = composerEl?.dataset.quoteTweetId || null;
            postTweetBtn.disabled = true;
            postTweetBtn.textContent = quoteTweetId ? 'Quoting...' : 'Posting...';

            try {
                const payload = {
                    text: text,
                    article_id: articleId ? parseInt(articleId) : null,
                };
                if (quoteTweetId) payload.quote_tweet_id = quoteTweetId;

                const res = await fetch(`${API_BASE_URL}/social/post/tweet`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.posted) {
                    const result = document.getElementById('tweet-compose-result');
                    const label = data.is_quote_tweet ? 'Quote tweeted' : 'Posted';
                    if (result) {
                        result.textContent = `✅ ${label}! Tweet ID: ${data.tweet_id} (${data.monthly_count}/100 this month)`;
                        result.style.color = '#16a34a';
                    }
                    document.getElementById('tweet-compose-text').value = '';
                    document.getElementById('tweet-compose-text').dataset.articleId = '';
                    delete document.getElementById('tweet-compose-text').dataset.quoteTweetId;
                    delete document.getElementById('tweet-compose-text').dataset.quoteTweetUrl;
                    const quoteIndicator = document.getElementById('quote-tweet-indicator');
                    if (quoteIndicator) quoteIndicator.innerHTML = '';
                    if (tweetCharCount) tweetCharCount.textContent = '0/280';
                    fetchSocialHistory();
                } else if (data.quote_restricted) {
                    // Author restricts quote tweets via API — fall back to X.com web intent
                    const quoteTweetUrl = composerEl?.dataset.quoteTweetUrl || `https://x.com/i/status/${quoteTweetId}`;
                    const intentUrl = `https://x.com/intent/tweet?text=${encodeURIComponent(text + '\n\n' + quoteTweetUrl)}`;
                    window.open(intentUrl, '_blank');

                    const result = document.getElementById('tweet-compose-result');
                    if (result) {
                        result.textContent = '⚠️ Author restricts API quotes. Opened X.com for manual posting.';
                        result.style.color = '#d97706';
                    }
                    // Clear composer
                    document.getElementById('tweet-compose-text').value = '';
                    document.getElementById('tweet-compose-text').dataset.articleId = '';
                    delete document.getElementById('tweet-compose-text').dataset.quoteTweetId;
                    delete document.getElementById('tweet-compose-text').dataset.quoteTweetUrl;
                    const quoteIndicator = document.getElementById('quote-tweet-indicator');
                    if (quoteIndicator) quoteIndicator.innerHTML = '';
                    if (tweetCharCount) tweetCharCount.textContent = '0/280';
                } else {
                    alert('Error: ' + (data.detail || JSON.stringify(data)));
                }
            } catch (e) {
                alert('Failed: ' + e.message);
            } finally {
                postTweetBtn.disabled = false;
                postTweetBtn.textContent = '𝕏 Post Tweet';
            }
        });
    }

    // Find X Posts modal
    let currentXPostsArticleId = null;
    let currentXPostsArticleSummary = '';
    window.openFindXPosts = (articleId) => {
        currentXPostsArticleId = articleId;
        // Look up article data from cache — avoids inline escaping issues with quotes in summaries
        const article = allArticlesCache.find(a => a.id === articleId) || {};
        const headline = article.headline || article.headline_original || 'No Headline';
        const summary = article.summary || '';
        currentXPostsArticleSummary = summary || headline;
        const modal = document.getElementById('xposts-modal');
        const queryInput = document.getElementById('xposts-search-query');
        const results = document.getElementById('xposts-results');
        if (queryInput) queryInput.value = headline;
        if (results) results.innerHTML = '<p style="color:#9ca3af; font-size:0.85rem;">Click "Search 𝕏" to find related tweets.</p>';
        if (modal) modal.classList.remove('hidden');
    };

    const closeXPostsBtn = document.getElementById('close-xposts-btn');
    if (closeXPostsBtn) closeXPostsBtn.addEventListener('click', () => {
        document.getElementById('xposts-modal')?.classList.add('hidden');
    });
    const xpostsModal = document.getElementById('xposts-modal');
    if (xpostsModal) xpostsModal.addEventListener('click', (e) => {
        if (e.target === xpostsModal) xpostsModal.classList.add('hidden');
    });

    const xpostsSearchBtn = document.getElementById('xposts-search-btn');
    if (xpostsSearchBtn) {
        xpostsSearchBtn.addEventListener('click', async () => {
            const query = document.getElementById('xposts-search-query')?.value;
            if (!query) return alert('Enter a search query.');
            const status = document.getElementById('xposts-search-status');
            const results = document.getElementById('xposts-results');
            if (status) { status.textContent = 'Searching...'; status.style.color = '#6b7280'; }

            try {
                const res = await fetch(`${API_BASE_URL}/social/twitter/search`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query, max_results: 50, exclude_publications: true, boost_experts: true, include_replies: true })
                });
                const data = await res.json();

                if (!res.ok) {
                    if (status) { status.textContent = data.detail || 'Search failed'; status.style.color = '#dc2626'; }
                    return;
                }

                if (status) status.textContent = `Found ${data.count} tweets`;
                if (!results) return;

                if (data.count === 0) {
                    results.innerHTML = '<p style="color:#9ca3af; font-size:0.85rem;">No tweets found for this query.</p>';
                    return;
                }

                // Store full tweet data so includeXPostInNewsletter can access it by index (no truncation)
                window._xpostsTweets = data.tweets;
                results.innerHTML = data.tweets.map((t, idx) => {
                    const followerLabel = t.followers_count >= 1000000 ? (t.followers_count / 1000000).toFixed(1) + 'M'
                        : t.followers_count >= 1000 ? (t.followers_count / 1000).toFixed(1) + 'K'
                        : t.followers_count;
                    const replyTag = t.is_reply
                        ? '<span style="font-size:0.65rem;padding:1px 6px;background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;border-radius:9999px;font-weight:600;">REPLY</span>'
                        : '';
                    const expertTag = t.is_likely_news
                        ? '<span style="font-size:0.65rem;padding:1px 6px;background:#fef2f2;color:#dc2626;border:1px solid #fecaca;border-radius:9999px;font-weight:600;">NEWS</span>'
                        : (t.followers_count < 100000
                            ? '<span style="font-size:0.65rem;padding:1px 6px;background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0;border-radius:9999px;font-weight:600;">EXPERT</span>'
                            : '');
                    const scoreColor = t.relevance_score >= 30 ? '#16a34a' : t.relevance_score >= 15 ? '#ca8a04' : '#6b7280';
                    return `
                    <div style="border:1px solid var(--border-default, #e5e7eb); border-radius:8px; padding:12px; background:var(--bg-card, #fff);">
                        <div style="display:flex; justify-content:space-between; align-items:start;">
                            <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                                <span style="font-weight:600; font-size:0.85rem; color:var(--text-primary);">${t.author_name}</span>
                                <span style="color:var(--text-muted, #6b7280); font-size:0.8rem;">@${t.author_username}</span>
                                <span style="color:var(--text-muted, #6b7280); font-size:0.7rem;">· ${followerLabel} followers</span>
                                ${expertTag}${replyTag}
                            </div>
                            <div style="display:flex; gap:8px; font-size:0.7rem; color:var(--text-muted, #6b7280); white-space:nowrap;">
                                <span title="Relevance Score" style="font-weight:700; color:${scoreColor};">⚡${t.relevance_score}</span>
                                <span>❤️ ${t.like_count}</span>
                                <span>🔁 ${t.retweet_count}</span>
                            </div>
                        </div>
                        <p style="margin:8px 0; font-size:0.85rem; line-height:1.4; color:var(--text-primary);">${t.text}</p>
                        <div style="display:flex; gap:6px; margin-top:6px; flex-wrap:wrap;">
                            <a href="${t.url}" target="_blank" style="font-size:0.75rem; color:#1d4ed8;">View on 𝕏</a>
                            <button onclick="includeXPostInNewsletter(${idx})" style="font-size:0.75rem; padding:2px 8px; background:#f3e8ff; color:#7c3aed; border:1px solid #ddd6fe; border-radius:4px; cursor:pointer;">Include in Newsletter</button>
                            <button onclick="repostOnX('${t.id}', '${t.author_username}', '${t.url}')" style="font-size:0.75rem; padding:2px 8px; background:#000; color:#fff; border:none; border-radius:4px; cursor:pointer;">Quote on 𝕏</button>
                        </div>
                    </div>`;
                }).join('');
            } catch (e) {
                if (status) { status.textContent = 'Error: ' + e.message; status.style.color = '#dc2626'; }
            }
        });
    }

    window.includeXPostInNewsletter = async (tweetIndex) => {
        if (!currentXPostsArticleId) {
            alert('No article selected. Open "Find X Posts" from an article first.');
            return;
        }
        const tweets = window._xpostsTweets || [];
        const t = tweets[tweetIndex];
        if (!t) {
            alert('Tweet data not found. Try searching again.');
            return;
        }
        const { url, author_username: username, text } = t;
        try {
            const res = await fetch(`${API_BASE_URL}/social/twitter/embed/${currentXPostsArticleId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify([{ username, text, url }])
            });
            if (!res.ok) {
                const err = await res.json();
                alert('Failed to save tweet: ' + (err.detail || 'Unknown error'));
                return;
            }
            // Mark the button as added
            const btns = document.querySelectorAll('#xposts-results button');
            btns.forEach(btn => {
                const onclickStr = btn.getAttribute('onclick') || '';
                if (onclickStr === `includeXPostInNewsletter(${tweetIndex})`) {
                    btn.textContent = '✓ Added';
                    btn.style.background = '#dcfce7';
                    btn.style.color = '#16a34a';
                    btn.style.borderColor = '#86efac';
                    btn.disabled = true;
                }
            });
        } catch (e) {
            alert('Error saving tweet: ' + e.message);
        }
    };

    // Quote on X: two options — compose in dashboard OR open X.com directly
    window.repostOnX = (tweetId, authorUsername, tweetUrl) => {
        const summary = currentXPostsArticleSummary || '';
        if (!summary) return alert('No article summary available.');

        // Build quote tweet text: emoji + summary + CTA
        const cta = '\u{1F310} Follow @GeoMemoNews for daily geopolitical intel';
        const fixedParts = `\u{1F4CA} \n\n${cta}`;
        const maxSummary = 280 - fixedParts.length - 2;
        let trimmedSummary = summary;
        if (trimmedSummary.length > maxSummary) {
            trimmedSummary = trimmedSummary.slice(0, maxSummary - 3).replace(/\s+\S*$/, '') + '...';
        }
        const tweetText = `\u{1F4CA} ${trimmedSummary}\n\n${cta}`;

        // Open X.com with quote tweet intent — most reliable method
        const quoteTweetUrl = tweetUrl || `https://x.com/i/status/${tweetId}`;
        const intentUrl = `https://x.com/intent/tweet?text=${encodeURIComponent(tweetText)}&url=${encodeURIComponent(quoteTweetUrl)}`;
        window.open(intentUrl, '_blank');

        // Also load into dashboard composer as backup
        const composer = document.getElementById('tweet-compose-text');
        if (composer) {
            // Find and expand the Social Media details section
            let el = composer;
            while (el && el.tagName !== 'DETAILS') el = el.parentElement;
            if (el && !el.open) el.open = true;

            composer.value = tweetText;
            composer.dataset.articleId = currentXPostsArticleId || '';
            composer.dataset.quoteTweetId = tweetId;
            composer.dataset.quoteTweetUrl = quoteTweetUrl;
            const charCount = document.getElementById('tweet-char-count');
            if (charCount) {
                charCount.textContent = `${tweetText.length}/280`;
                charCount.style.color = tweetText.length > 260 ? (tweetText.length > 280 ? '#dc2626' : '#f59e0b') : '#9ca3af';
            }
            // Show quote tweet indicator above composer
            let quoteIndicator = document.getElementById('quote-tweet-indicator');
            if (!quoteIndicator) {
                quoteIndicator = document.createElement('div');
                quoteIndicator.id = 'quote-tweet-indicator';
                composer.parentElement.insertBefore(quoteIndicator, composer);
            }
            quoteIndicator.innerHTML = `<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;font-size:0.8rem;color:#0369a1;margin-bottom:6px;">
                <span>🔁 Quote tweet of @${authorUsername} (X.com opened in new tab)</span>
                <button onclick="clearQuoteTweet()" style="margin-left:auto;font-size:0.7rem;color:#dc2626;background:none;border:none;cursor:pointer;">✕ Cancel quote</button>
            </div>`;
        }

        // Close the X Posts modal
        document.getElementById('xposts-modal')?.classList.add('hidden');
    };

    // Clear quote tweet mode (switch back to regular tweet)
    window.clearQuoteTweet = () => {
        const composer = document.getElementById('tweet-compose-text');
        if (composer) {
            delete composer.dataset.quoteTweetId;
            delete composer.dataset.quoteTweetUrl;
        }
        const indicator = document.getElementById('quote-tweet-indicator');
        if (indicator) indicator.innerHTML = '';
    };

    async function handlePostNewsletterTelegram() {
        if (!currentBriefId) return alert('No newsletter generated yet. Generate one first.');
        if (!confirm('Post this newsletter digest to Telegram?')) return;

        const btn = document.getElementById('post-newsletter-telegram-btn');
        if (btn) { btn.disabled = true; btn.textContent = 'Posting...'; }

        try {
            const res = await fetch(`${API_BASE_URL}/social/post/newsletter/${currentBriefId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ platforms: ['telegram'] })
            });
            const data = await res.json();
            if (data.posted && data.posted.length > 0) {
                if (btn) { btn.textContent = '✅ Posted!'; btn.style.background = '#16a34a'; }
                fetchSocialHistory();
            } else if (data.errors && data.errors.length > 0) {
                alert('Error: ' + data.errors.map(e => e.error).join(', '));
                if (btn) { btn.disabled = false; btn.textContent = '📢 Post to Telegram'; }
            }
        } catch (e) {
            alert('Failed: ' + e.message);
            if (btn) { btn.disabled = false; btn.textContent = '📢 Post to Telegram'; }
        }
    }

});
