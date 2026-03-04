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

    // Newsletter Elements
    const generateNewsletterBtn = document.getElementById('generate-newsletter-btn');
    const newsletterModal = document.getElementById('newsletter-modal');
    const newsletterOutput = document.getElementById('newsletter-output');
    const newsletterSubject = document.getElementById('newsletter-subject');
    const copyHtmlBtn = document.getElementById('copy-html-btn');
    const closeNewsletterBtn = document.getElementById('close-newsletter-btn');

    // Other Managers
    const tweetForm = document.getElementById('tweet-entry-form');
    const sponsorForm = document.getElementById('sponsor-form');
    const podcastForm = document.getElementById('podcast-form');
    const fetchMetaBtn = document.getElementById('fetch-podcast-meta-btn');

    // --- STYLE CONSTANTS (MODERN PREMIUM) ---
    // Using System Fonts for a clean, app-like feel
    const FONT_STACK = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

    // --- STATE ---
    let allArticlesCache = [];
    let currentEnhanceId = null;
    let currentSortBy = 'scraped_at';
    let currentSortOrder = 'desc';
    
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
    if (categoryFilter) categoryFilter.addEventListener('change', () => renderArticles());
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

    // Newsletter Listeners
    if (generateNewsletterBtn) generateNewsletterBtn.addEventListener('click', generateNewsletter);
    if (closeNewsletterBtn) closeNewsletterBtn.addEventListener('click', () => newsletterModal.classList.add('hidden'));
    if (copyHtmlBtn) copyHtmlBtn.addEventListener('click', () => {
        newsletterOutput.select();
        document.execCommand('copy');
        alert('HTML Copied!');
    });

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
        try { 
            await fetch(`${API_BASE_URL}/articles/${id}/status`, { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({ status: status }) 
            }); 
            fetchArticles(true); 
        } catch (e) { alert("Failed to update status"); } 
    };

    window.handleFindSimilarClick = (id, headline) => {
        handleFindSimilarLogic(id, headline);
    };

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

    async function fetchArticles(preserveScroll = false) {
        const currentScrollY = window.scrollY;
        if (articlesTbody && articlesTbody.children.length === 0) showLoading(true);
        try {
            const params = new URLSearchParams();
            if (currentSortBy !== 'scraped_at') params.set('sort_by', currentSortBy);
            if (currentSortOrder !== 'desc') params.set('order', currentSortOrder);
            const qs = params.toString();
            const response = await fetch(`${API_BASE_URL}/articles${qs ? '?' + qs : ''}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            allArticlesCache = await response.json();
            renderArticles(); 
            if (preserveScroll) window.scrollTo(0, currentScrollY);
        } catch (error) { 
            console.error('Error fetching articles:', error); 
        } finally { 
            if (articlesTbody) showLoading(false); 
        }
    }

    function renderArticles() {
        if(!articlesTbody) return;
        const selectedCategory = categoryFilter ? categoryFilter.value : 'All';
        
        // Filter
        const filtered = (selectedCategory === 'All') 
            ? allArticlesCache 
            : allArticlesCache.filter(a => a.category === selectedCategory);

        // Group by Date
        const grouped = filtered.reduce((groups, article) => {
            let date = (article.scraped_at && typeof article.scraped_at === 'string') 
                ? article.scraped_at.split('T')[0] 
                : 'Unsorted';
            if (!groups[date]) groups[date] = [];
            groups[date].push(article);
            return groups;
        }, {});

        renderGroupedArticles(grouped);
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
                    prettyDate = new Date(date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }); 
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

    function createArticleRow(article, isChild = false) {
        const tr = document.createElement('tr');
        tr.className = `article-row ${article.status}`;
        
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
            <td class="p-3 align-top w-1/12">
                <select class="category-dropdown w-full p-1 border rounded border-gray-300 text-xs bg-white" data-id="${article.id}">
                    ${categoryOptions}
                </select>
            </td>
            <td class="p-3 align-top w-3/12 text-sm text-gray-600">
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
                try { await fetch(`${API_BASE_URL}/articles/${article.id}/toggle-top`, { method: 'POST' }); fetchArticles(true); } catch(err) {} 
            });
        }
        
        return tr;
    }

    // =========================================
    // ENHANCE / EDIT MODAL & SIMILARITY LOGIC
    // =========================================
    
    async function handleEnhanceSubmit() {
        if (!currentEnhanceId) return;
        
        // ** FIX: Update SUMMARY, not Headline **
        const payload = { 
            summary: enhanceInput.value, 
            publication_name: enhancePubInput.value, 
            author: enhanceAuthorInput.value 
        };
        
        const btn = document.getElementById('confirm-enhance-btn');
        const originalText = btn.textContent;
        btn.textContent = "Saving..."; 
        btn.disabled = true;
        
        try {
            const response = await fetch(`${API_BASE_URL}/articles/${currentEnhanceId}/enhance`, { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(payload) 
            });
            if (!response.ok) throw new Error("Failed to update article");
            closeEnhanceModal(); 
            fetchArticles(true);
        } catch (error) { 
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
                fetchArticles(true); 
            }, 2000); 
            
        } catch (error) { 
            resText.textContent = 'Error: ' + error.message; 
            resContainer.classList.add('bg-red-50', 'text-red-700');
            btn.disabled = false;
            btn.textContent = "Try Again";
        }
    }

    // =========================================
    // NEWSLETTER GENERATOR (FIXED TECHMEME FORMATTING + COLORS)
    // =========================================
    function generateNewsletter() {
        const articles = allArticlesCache.filter(a => a.status === 'approved' && isToday(a.scraped_at)); 
        
        if (articles.length === 0) { 
            alert("No approved articles found for TODAY."); 
            return; 
        }

        // Separate Parents and Children
        const parents = articles.filter(a => !a.parent_id);
        const children = articles.filter(a => a.parent_id);
        
        const childMap = {};
        children.forEach(c => {
            if(!childMap[c.parent_id]) childMap[c.parent_id] = [];
            childMap[c.parent_id].push(c);
        });

        // Top News Logic
        const topStories = parents.filter(a => a.is_top_story);
        const otherParents = parents.filter(a => !a.is_top_story);
        
        let subject = topStories.length ? "GeoMemo: " + (topStories[0].summary || topStories[0].headline || "Daily Update") : "GeoMemo Daily Update";
        subject = subject.replace(/<[^>]*>?/gm, '');
        newsletterSubject.value = subject;
        
        // --- 1. Top Header (NO BOOKMARKS) ---
        let html = `<div style="font-family:${FONT_STACK};color:#111;max-width:600px;margin:0 auto;">
            <div style="border-bottom:2px solid #eee;padding-bottom:15px;margin-bottom:20px;">
                <span style="font-size:24px;font-weight:800;color:#430297;letter-spacing:-0.5px;text-transform:uppercase;">GeoMemo</span><br>
                <span style="color:#666;font-size:13px;font-weight:400;">Daily Intelligence • ${new Date().toLocaleDateString('en-US', {month:'long', day:'numeric', year:'numeric'})}</span>
            </div>`;
        
        // --- 2. Top News Section ---
        if (topStories.length) { 
            html += `<h3 style="color:#b00;font-size:14px;border-bottom:2px solid #b00;margin-bottom:15px;text-transform:uppercase;margin-top:0;">Top News</h3>`; 
            topStories.forEach(p => html += renderNewsletterCluster(p, childMap[p.id] || [])); 
        }
        
        // --- 3. Category Sections ---
        VALID_CATEGORIES.forEach(cat => {
            const group = otherParents.filter(p => (VALID_CATEGORIES.includes(p.category) ? p.category : 'Other') === cat);
            
            if (group.length) { 
                const anchorId = cat.replace(/\s+/g, '-').toLowerCase();
                html += `<h3 id="${anchorId}" style="color:#b00;font-size:14px;border-bottom:1px solid #ddd;margin-top:25px;margin-bottom:15px;text-transform:uppercase;">${cat}</h3>`; 
                group.forEach(p => html += renderNewsletterCluster(p, childMap[p.id] || [])); 
            }
        });
        
        html += `<div style="margin-top:40px;border-top:1px solid #eee;padding-top:20px;text-align:center;color:#888;font-size:12px;">&copy; 2025 GeoMemo.</div></div>`;
        
        html = html.replace(/\s+/g, ' ').trim();
        
        newsletterOutput.value = html; 
        newsletterModal.classList.remove('hidden');
    }

    // Helper to render one Parent + its Children (PREMIUM COLORS)
    function renderNewsletterCluster(parent, children) {
        // COLOR PALETTE UPDATE
        const C_HEAD_LINK = "#111827"; // Dark Blue-Black (Tailwind Gray-900)
        const C_META = "#888"; 
        const C_CHILD_PUB = "#008000"; // Techmeme Green
        const C_CHILD_TEXT = "#666666"; // Light Grey
        
        let parentText = parent.summary || parent.headline || "No Content";
        parentText = parentText.replace(/<[^>]*>?/gm, '');

        // Parent Row: Dark Blue-Black
        let html = `
            <div style="margin-bottom:15px; padding-bottom:15px; border-bottom:1px solid #eee;">
                <div style="line-height:1.4; font-size:16px;">
                    <a href="${parent.url}" style="color:${C_HEAD_LINK}; text-decoration:none; font-weight:700;">${parentText}</a>
                    <span style="color:${C_META}; font-size:12px; margin-left:6px;">(${parent.publication_name || ''} ${parent.author ? '- ' + parent.author : ''})</span>
                </div>
        `;

        // Children Rows: Light Grey & Normal Weight
        if (children && children.length > 0) {
            children.forEach(child => {
                const childPub = child.publication_name || 'Source';
                let childSum = child.summary || child.headline;
                childSum = childSum.replace(/<[^>]*>?/gm, '');
                
                html += `
                    <div style="margin-top:8px; font-size:13px; color:${C_CHILD_TEXT}; line-height:1.4; margin-left:0px;">
                        <a href="${child.url}" style="color:${C_CHILD_PUB}; font-weight:bold; text-decoration:none;">${childPub}</a>: ${childSum}
                    </div>
                `;
            });
        }

        html += `</div>`;
        return html;
    }

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
        tb.innerHTML=items.map(s=>`<tr><td>${s.company_name}</td><td><button onclick="deleteItem('sponsors', ${s.id})">🗑️</button></td></tr>`).join(''); 
    }

    async function handlePodcastSubmit(e) { 
        e.preventDefault(); 
        const fd=new FormData(e.target); 
        await fetch(`${API_BASE_URL}/podcasts`,{method:'POST', body:fd}); 
        e.target.reset(); 
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
        const threshold = prompt("Auto-approve all pending articles with score >= ?", "80");
        if (threshold === null) return;
        const val = parseFloat(threshold);
        if (isNaN(val)) return alert("Invalid number");
        if (!confirm(`Approve ALL pending articles with auto_approval_score >= ${val}?`)) return;

        try {
            const res = await fetch(`${API_BASE_URL}/articles/auto-approve`, {
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

    async function handleAutoReject() {
        const threshold = prompt("Auto-reject all pending articles with score <= ?", "30");
        if (threshold === null) return;
        const val = parseFloat(threshold);
        if (isNaN(val)) return alert("Invalid number");
        if (!confirm(`Reject ALL pending articles with auto_approval_score <= ${val}?`)) return;

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
            tb.innerHTML = sources.map(s => `
                <tr>
                    <td class="font-medium text-gray-800">${s.name}</td>
                    <td class="text-gray-500">${s.domain || '—'}</td>
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
            `).join('');
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

    async function handleSourceSubmit(e) {
        e.preventDefault();
        const data = {
            name: document.getElementById('source-name').value,
            domain: document.getElementById('source-domain').value || null,
            credibility_score: parseInt(document.getElementById('source-credibility').value) || 50,
            tier: parseInt(document.getElementById('source-tier').value) || 3,
            country: document.getElementById('source-country').value || null,
            language: 'en'
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

});
