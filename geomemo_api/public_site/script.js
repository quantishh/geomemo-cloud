document.addEventListener('DOMContentLoaded', () => {
    // --- CHANGE: Point explicitly to your Cloud API Port ---
    const API_BASE_URL = "https://www.geomemo.news";
    
    // Containers
    const jumpBar = document.getElementById('category-jump-bar');
    const topNewsContainer = document.getElementById('top-news-container');
    const topNewsHeader = document.getElementById('top-news-header');
    const categoryNewsContainer = document.getElementById('category-news-container');
    const sponsorsContainer = document.getElementById('sponsors-container');
    const podcastsContainer = document.getElementById('podcasts-container');
    const tweetsContainer = document.getElementById('tweets-container');
    const loadingEl = document.getElementById('loading');

    // CORRECT ORDER
    const VALID_CATEGORIES = [
        'Geopolitical Conflict', 
        'Geopolitical Economics', 
        'Global Markets', 
        'Geopolitical Politics', 
        'GeoNatDisaster', 
        'GeoLocal', 
        'Other'
    ];

    // --- INITIALIZATION ---
    loadAllContent();

    async function loadAllContent() {
        if(loadingEl) loadingEl.style.display = 'block';
        
        // 1. Fetch Articles First (to determine active categories for Jump Bar)
        await fetchArticles();
        
        // 2. Fetch Sidebar Items in parallel
        await Promise.all([
            fetchSponsors(),
            fetchPodcasts(),
            fetchTweets()
        ]);
        
        if(loadingEl) loadingEl.style.display = 'none';
    }

    // --- 1. FETCH & RENDER ARTICLES ---
    async function fetchArticles() {
        try {
            const response = await fetch(`${API_BASE_URL}/articles/approved`);
            if (!response.ok) throw new Error("Failed");
            const articles = await response.json();
            processAndRenderArticles(articles);
        } catch (error) {
            console.error("News Error:", error);
            if(categoryNewsContainer) categoryNewsContainer.innerHTML = '<p style="padding:20px;">Unable to load news.</p>';
        }
    }

    function processAndRenderArticles(articles) {
        // 1. Filter for TODAY (Local Time)
        // Note: You might want to adjust this logic if server/client timezones differ significantly
        const todayString = new Date().toLocaleDateString();
        const todaysArticles = articles.filter(a => {
            if (!a.scraped_at) return false;
            return new Date(a.scraped_at).toLocaleDateString() === todayString;
        });

        if (todaysArticles.length === 0) {
            if(topNewsContainer) topNewsContainer.innerHTML = `<div style="padding:20px; color:#666;">No news published for ${todayString}.</div>`;
            return;
        }

        // 2. Cluster Logic (Map Children to Parents)
        const parents = todaysArticles.filter(a => !a.parent_id);
        const children = todaysArticles.filter(a => a.parent_id);
        const childMap = {};
        children.forEach(c => {
            if(!childMap[c.parent_id]) childMap[c.parent_id] = [];
            childMap[c.parent_id].push(c);
        });

        // 3. Split: Top Stories vs Categories
        const topStories = parents.filter(a => a.is_top_story);
        const otherStories = parents.filter(a => !a.is_top_story);

        // 4. Render TOP NEWS
        if(topStories.length > 0 && topNewsContainer) {
            topNewsHeader.style.display = 'block'; // Show the Red "TOP NEWS" Header
            topNewsContainer.innerHTML = topStories.map(p => renderTechmemeItem(p, childMap)).join('');
        }

        // 5. Render CATEGORIES & SMART JUMP BAR
        if(categoryNewsContainer) {
            categoryNewsContainer.innerHTML = ''; // Clear previous
            const activeCategories = [];

            VALID_CATEGORIES.concat(['Other']).forEach(cat => {
                const catGroup = otherStories.filter(a => (VALID_CATEGORIES.includes(a.category) ? a.category : 'Other') === cat);
                
                if(catGroup.length > 0) {
                    activeCategories.push(cat); // Mark as active for Jump Bar

                    // Create Category Wrapper
                    const sectionId = cat.toLowerCase().replace(/ /g, '-');
                    const sectionDiv = document.createElement('div');
                    sectionDiv.id = sectionId;
                    sectionDiv.style.marginTop = "30px";
                    
                    // Category Header
                    sectionDiv.innerHTML = `<div class="section-header">${cat}</div>`;
                    
                    // Render Articles
                    sectionDiv.innerHTML += catGroup.map(p => renderTechmemeItem(p, childMap)).join('');
                    categoryNewsContainer.appendChild(sectionDiv);
                }
            });

            // NOW Render Jump Bar (Only Active Categories)
            renderJumpBar(activeCategories);
        }
    }

    // --- SMART JUMP BAR ---
    function renderJumpBar(activeCats) {
        if(!jumpBar) return;
        if(activeCats.length === 0) { jumpBar.innerHTML = ''; return; }

        jumpBar.innerHTML = activeCats.map(cat => {
            const id = cat.toLowerCase().replace(/ /g, '-');
            return `<a href="#${id}" class="jump-link" style="margin-right:15px; font-weight:700; font-size:12px; color:#105cb6; text-decoration:none; text-transform:uppercase;">${cat}</a>`;
        }).join(' ');
    }

    // --- HTML GENERATOR (TECHMEME STYLE - WEBSITE) ---
    function renderTechmemeItem(parent, childMap) {
        // COLOR PALETTE UPDATE (Requested: Dark Blue-Black + Light Grey)
        const C_HEAD_LINK = "#111827"; // Dark Blue-Black
        const C_META = "#888"; 
        const C_CHILD_PUB = "#008000"; // Green
        const C_CHILD_TEXT = "#666666"; // Light Grey

        // FIX: Clean Summary text
        let parentText = parent.summary || parent.headline || "No Content";
        parentText = parentText.replace(/<[^>]*>?/gm, ''); 

        const pubName = parent.publication_name || "Source";
        const authorTxt = parent.author ? ` - ${parent.author}` : '';
        
        let html = `
            <div class="news-item" style="margin-bottom:15px; padding-bottom:15px; border-bottom:1px solid #eee;">
                <div style="line-height:1.4; font-size:16px;">
                    <a href="${parent.url}" target="_blank" style="color:${C_HEAD_LINK}; font-weight:700; text-decoration:none;">
                        ${parentText}
                    </a>
                    <span style="color:${C_META}; font-size:12px; margin-left:6px;">
                        (${pubName}${authorTxt})
                    </span>
                </div>
        `;

        if (childMap[parent.id]) {
            childMap[parent.id].forEach(c => {
                const childPub = c.publication_name || "Source";
                let childSum = c.summary || c.headline;
                childSum = childSum.replace(/<[^>]*>?/gm, ''); // Clean child summary too

                html += `
                    <div style="margin-top:8px; font-size:13px; margin-left:0px; line-height:1.4; color:${C_CHILD_TEXT};">
                        <a href="${c.url}" target="_blank" style="color:${C_CHILD_PUB}; font-weight:bold; text-decoration:none;">
                            ${childPub}
                        </a>: ${childSum}
                    </div>`;
            });
        }

        html += `</div>`;
        return html;
    }

    // =========================================
    // SIDEBAR FETCHERS
    // =========================================
    async function fetchSponsors() {
        if(!sponsorsContainer) return;
        try {
            const res = await fetch(`${API_BASE_URL}/sponsors`);
            const sponsors = await res.json();
            if(sponsors.length === 0) { sponsorsContainer.innerHTML = ''; return; }
            
            sponsorsContainer.innerHTML = sponsors.map(s => `
                <div class="sponsor-item" style="padding:10px 0; border-bottom:1px solid #eee;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:5px;">
                        <div style="font-size:11px; font-weight:700; text-transform:uppercase; color:#666; margin-top:4px;">
                            ${s.company_name}
                        </div>
                        ${s.logo_url ? `<img src="${s.logo_url}" style="max-height:30px; max-width:80px; object-fit:contain;">` : ''}
                    </div>
                    
                    <a href="${s.link_url}" target="_blank" style="display:block; font-weight:700; color:#105cb6; font-size:14px; margin-bottom:4px; line-height:1.3;">
                        ${s.headline}
                    </a>
                    <div style="font-size:13px; line-height:1.4;">${s.summary}</div>
                </div>`).join('');
        } catch(e){}
    }

    async function fetchPodcasts() {
        if(!podcastsContainer) return;
        try {
            const res = await fetch(`${API_BASE_URL}/podcasts`);
            const items = await res.json();
            if(items.length === 0) { podcastsContainer.innerHTML = ''; return; }

            podcastsContainer.innerHTML = items.map(p => `
                <div class="podcast-item" style="margin-bottom:15px; border:1px solid #eee; padding:12px; background:#fff; border-radius:4px;">
                    <div style="font-size:11px; font-weight:700; color:#666; text-transform:uppercase; margin-bottom:4px;">
                        ${p.show_name}
                    </div>
                    <a href="${p.link_url}" target="_blank" style="font-weight:700; color:#b00; font-size:15px; display:block; margin-bottom:8px; line-height:1.3;">
                        ${p.episode_title}
                    </a>
                    ${p.image_url ? `<img src="${p.image_url}" style="width:100%; height:auto; border:1px solid #eee; display:block;">` : ''}
                    
                    <a href="${p.link_url}" target="_blank" style="display:block; margin-top:8px; font-size:11px; font-weight:700; color:#105cb6; text-decoration:none;">
                        SUBSCRIBE / LISTEN
                    </a>
                </div>`).join('');
        } catch(e){}
    }

    async function fetchTweets() {
        if(!tweetsContainer) return;
        try {
            const res = await fetch(`${API_BASE_URL}/tweets`);
            const tweets = await res.json();
            if(tweets.length === 0) { tweetsContainer.innerHTML = ''; return; }

            tweetsContainer.innerHTML = tweets.map(t => `
                <div class="tweet-item" style="border-bottom:1px solid #eee; padding-bottom:10px; margin-bottom:10px;">
                    <a href="${t.url}" target="_blank" style="font-size:13px; color:#333; text-decoration:none;">${t.content}</a>
                    <div style="font-size:10px; color:#999; margin-top:4px;">Posted by ${t.author || 'X User'}</div>
                </div>`).join('');
        } catch(e){}
    }
});
