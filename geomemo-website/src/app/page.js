import Link from 'next/link';
import { fetchApprovedArticles } from '@/lib/api';
import ArticleCluster from '@/components/ArticleCluster';
import NewestUpdates from '@/components/NewestUpdates';

export const dynamic = 'force-dynamic';

export default async function Home() {
  const articles = await fetchApprovedArticles();

  // Group articles into clusters (parent + children) and standalone
  const clusters = [];
  const childMap = {};

  // First pass: identify children
  articles.forEach((article) => {
    if (article.parent_id) {
      if (!childMap[article.parent_id]) childMap[article.parent_id] = [];
      childMap[article.parent_id].push(article);
    }
  });

  // Second pass: build clusters
  const processedIds = new Set();
  articles.forEach((article) => {
    if (processedIds.has(article.id)) return;
    if (article.parent_id) return; // skip children, handled via parent

    const children = childMap[article.id] || [];
    children.forEach((c) => processedIds.add(c.id));
    processedIds.add(article.id);

    clusters.push({
      parent: article,
      children,
    });
  });

  // Group clusters by category
  const categoryOrder = [
    'Geopolitical Conflict',
    'Geopolitical Politics',
    'Geopolitical Economics',
    'Global Markets',
    'GeoNatDisaster',
    'GeoLocal',
    'Other',
  ];

  const byCategory = {};
  clusters.forEach((cluster) => {
    const cat = cluster.parent.category || 'Other';
    if (!byCategory[cat]) byCategory[cat] = [];
    byCategory[cat].push(cluster);
  });

  const orderedCategories = categoryOrder.filter((c) => byCategory[c]?.length > 0);

  // Today's date
  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'America/New_York',
  });

  return (
    <>
      {/* Section 1: Hero */}
      <section style={{
        background: 'var(--color-primary)',
        color: 'var(--color-text-inverse)',
        padding: 'var(--space-12) 0',
        textAlign: 'center',
      }}>
        <div className="container">
          <p style={{
            fontSize: '0.8rem',
            fontWeight: 600,
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            color: 'var(--color-accent)',
            marginBottom: 'var(--space-3)',
          }}>
            {today}
          </p>
          <h1 style={{
            fontSize: 'clamp(1.75rem, 4vw, 2.5rem)',
            fontWeight: 800,
            letterSpacing: '-0.03em',
            marginBottom: 'var(--space-3)',
          }}>
            Geopolitical Intelligence for<br />
            <span style={{ color: 'var(--color-accent)' }}>Global Decision Makers</span>
          </h1>
          <p style={{
            fontSize: '1rem',
            color: 'rgba(255,255,255,0.65)',
            maxWidth: '540px',
            margin: '0 auto var(--space-6)',
            lineHeight: 1.6,
          }}>
            Daily briefings on conflicts, trade, markets, and policy — curated for investment professionals and policymakers.
          </p>
          <Link href="/newsletter" className="btn-primary" style={{
            fontSize: '0.9rem',
            padding: '14px 32px',
          }}>
            Subscribe to Daily Briefing
          </Link>
        </div>
      </section>

      {/* Section 2: Main News Feed */}
      <section className="section">
        <div className="container">
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-3)',
            marginBottom: 'var(--space-8)',
          }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Latest Intelligence</h2>
            <div className="accent-bar" />
          </div>

          {articles.length === 0 ? (
            <p style={{
              textAlign: 'center',
              color: 'var(--color-text-secondary)',
              padding: 'var(--space-16) 0',
            }}>
              No articles published yet today. Check back soon.
            </p>
          ) : (
            <div>
              {orderedCategories.map((category) => (
                <div key={category} style={{ marginBottom: 'var(--space-10)' }}>
                  {/* Category header */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-3)',
                    marginBottom: 'var(--space-5)',
                    paddingBottom: 'var(--space-3)',
                    borderBottom: '2px solid var(--color-border)',
                  }}>
                    <span className="badge">{category}</span>
                    <span style={{
                      fontSize: '0.75rem',
                      color: 'var(--color-text-muted)',
                    }}>
                      {byCategory[category].length} {byCategory[category].length === 1 ? 'story' : 'stories'}
                    </span>
                  </div>

                  {/* Articles in this category */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
                    {byCategory[category].map((cluster) => (
                      <ArticleCluster
                        key={cluster.parent.id}
                        parent={cluster.parent}
                        relatedArticles={cluster.children}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Section 3: Newest Updates */}
      <section style={{ background: 'var(--color-surface)' }} className="section">
        <div className="container">
          <NewestUpdates />
        </div>
      </section>

      {/* Section 4: Newsletter CTA */}
      <section style={{
        background: 'var(--color-primary)',
        color: 'var(--color-text-inverse)',
        padding: 'var(--space-12) 0',
        textAlign: 'center',
      }}>
        <div className="container">
          <h2 style={{
            fontSize: 'clamp(1.25rem, 3vw, 1.75rem)',
            fontWeight: 700,
            marginBottom: 'var(--space-3)',
          }}>
            Never miss a geopolitical shift
          </h2>
          <p style={{
            fontSize: '0.95rem',
            color: 'rgba(255,255,255,0.6)',
            marginBottom: 'var(--space-6)',
          }}>
            Join professionals who start their day with GeoMemo.
          </p>
          <Link href="/newsletter" className="btn-primary" style={{
            fontSize: '0.9rem',
            padding: '14px 32px',
          }}>
            Subscribe Free
          </Link>
        </div>
      </section>
    </>
  );
}
