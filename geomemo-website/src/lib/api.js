const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchApprovedArticles() {
  try {
    const res = await fetch(`${API_URL}/articles/approved`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return res.json();
  } catch (error) {
    console.error('Failed to fetch approved articles:', error);
    return [];
  }
}

export async function fetchNewestUpdates() {
  try {
    const res = await fetch(`${API_URL}/articles/newest-updates`, {
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return res.json();
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
