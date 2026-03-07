const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchApprovedArticles() {
  try {
    // Try today's approved articles first
    const res = await fetch(`${API_URL}/articles/approved`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    const articles = await res.json();

    // If today has articles, use them
    if (articles.length > 0) return articles;

    // Fallback: fetch recent approved articles (for testing when today is empty)
    const fallback = await fetch(
      `${API_URL}/articles?status=approved&days=2&sort_by=scraped_at&order=desc`,
      { cache: 'no-store' }
    );
    if (!fallback.ok) return [];
    return fallback.json();
  } catch (error) {
    console.error('Failed to fetch approved articles:', error);
    return [];
  }
}

export async function fetchNewestUpdates() {
  try {
    // Use the general /articles endpoint with score filter (works on production)
    const res = await fetch(
      `${API_URL}/articles?status=approved&min_score=75&days=2&sort_by=auto_approval_score&order=desc&limit=20`,
      { cache: 'no-store' }
    );
    if (!res.ok) return [];
    const data = await res.json();
    // The endpoint returns {articles, total, ...} when limit is set
    return data.articles || data;
  } catch (error) {
    console.error('Failed to fetch newest updates:', error);
    return [];
  }
}

export async function fetchEvents() {
  try {
    const res = await fetch(`${API_URL}/events`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return res.json();
  } catch (error) {
    console.error('Failed to fetch events:', error);
    return [];
  }
}

export async function fetchSponsors() {
  try {
    const res = await fetch(`${API_URL}/sponsors`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return res.json();
  } catch (error) {
    console.error('Failed to fetch sponsors:', error);
    return [];
  }
}

export async function fetchPodcasts() {
  try {
    const res = await fetch(`${API_URL}/podcasts`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return res.json();
  } catch (error) {
    console.error('Failed to fetch podcasts:', error);
    return [];
  }
}

export async function fetchNewsletterArchive() {
  try {
    const res = await fetch(`${API_URL}/newsletter/archive`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return res.json();
  } catch (error) {
    console.error('Failed to fetch newsletter archive:', error);
    return [];
  }
}
