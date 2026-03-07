import Link from 'next/link';
import { fetchApprovedArticles, fetchSponsors, fetchPodcasts, fetchNewestUpdates } from '@/lib/api';
import ArticleCluster from '@/components/ArticleCluster';

export const dynamic = 'force-dynamic';

export default async function Home() {
  const [articles, sponsors, podcasts, latestNews] = await Promise.all([
    fetchApprovedArticles(),
    fetchSponsors(),
    fetchPodcasts(),
    fetchNewestUpdates(),
  ]);

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
    if (article.parent_id) return;

    const children = childMap[article.id] || [];
    children.forEach((c) => processedIds.add(c.id));
    processedIds.add(article.id);

    clusters.push({
      parent: article,
      children,
    });
  });

  // Separate top stories from regular stories
  const topStoryClusters = clusters.filter((c) => c.parent.is_top_story);
  const regularClusters = clusters.filter((c) => !c.parent.is_top_story);

  // Group regular clusters by category
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
  regularClusters.forEach((cluster) => {
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
      {/* Hero — slim banner */}
      <section style={{
        background: 'var(--color-primary)',
        color: 'var(--color-text-inverse)',
        padding: '20px 0',
      }}>
        <div className="container" style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}>
          <div>
            <p style={{
              fontSize: '0.7rem',
              fontWeight: 600,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              color: 'var(--color-accent)',
              marginBottom: '4px',
            }}>
              {today}
            </p>
            <h1 style={{
              fontSize: 'clamp(1.1rem, 2.5vw, 1.4rem)',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              margin: 0,
            }}>
              Geopolitical Intelligence for{' '}
              <span style={{ color: 'var(--color-accent)' }}>Global Decision Makers</span>
            </h1>
          </div>
          <Link href="/newsletter" className="btn-primary" style={{
            fontSize: '0.8rem',
            padding: '10px 24px',
          }}>
            Subscribe Free
          </Link>
        </div>
      </section>

      {articles.length === 0 ? (
        <section className="section">
          <div className="container">
            <p style={{
              textAlign: 'center',
              color: 'var(--color-text-secondary)',
              padding: 'var(--space-16) 0',
            }}>
              No articles published yet today. Check back soon.
            </p>
          </div>
        </section>
      ) : (
        /* Main Content — 3-column Techmeme-style layout */
        <section style={{ padding: 'var(--space-6) 0 var(--space-12)' }}>
          <div className="container">
            <div className="homepage-grid">

              {/* LEFT COLUMN — Main News */}
              <div className="main-column">

                {/* Top News */}
                {topStoryClusters.length > 0 && (
                  <div style={{ marginBottom: 'var(--space-8)' }}>
                    <div className="section-header">
                      <h2 className="section-title">Top News</h2>
                      <div className="accent-bar" />
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
                      {topStoryClusters.map((cluster) => (
                        <ArticleCluster
                          key={cluster.parent.id}
                          parent={cluster.parent}
                          relatedArticles={cluster.children}
                          isTopStory={true}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Category sections */}
                {orderedCategories.map((category) => (
                  <div key={category} style={{ marginBottom: 'var(--space-8)' }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--space-3)',
                      marginBottom: 'var(--space-4)',
                      paddingBottom: 'var(--space-2)',
                      borderBottom: '2px solid var(--color-border)',
                    }}>
                      <span className="badge">{category}</span>
                      <span style={{
                        fontSize: '0.7rem',
                        color: 'var(--color-text-muted)',
                      }}>
                        {byCategory[category].length} {byCategory[category].length === 1 ? 'story' : 'stories'}
                      </span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
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

              {/* MIDDLE COLUMN — Sponsors + Podcasts */}
              <div className="middle-column">

                {/* Sponsor Posts */}
                {sponsors.length > 0 && (
                  <div className="sidebar-section">
                    <h3 className="sidebar-title">Sponsor Posts</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {sponsors.map((sponsor) => (
                        <a
                          key={sponsor.id}
                          href={sponsor.link_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="sponsor-sidebar-card"
                        >
                          <div style={{
                            fontSize: '0.6rem',
                            fontWeight: 700,
                            letterSpacing: '0.08em',
                            textTransform: 'uppercase',
                            color: 'var(--color-text-muted)',
                            marginBottom: '4px',
                          }}>
                            {sponsor.company_name}
                          </div>
                          <div style={{
                            fontSize: '0.82rem',
                            fontWeight: 600,
                            lineHeight: 1.4,
                            color: 'var(--color-text)',
                          }}>
                            {sponsor.headline}
                          </div>
                          <div style={{
                            fontSize: '0.72rem',
                            color: 'var(--color-text-secondary)',
                            lineHeight: 1.5,
                            marginTop: '4px',
                          }}>
                            {sponsor.summary.length > 120
                              ? sponsor.summary.substring(0, 120) + '...'
                              : sponsor.summary}
                          </div>
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Featured Podcasts */}
                {podcasts.length > 0 && (
                  <div className="sidebar-section">
                    <h3 className="sidebar-title">Featured Podcasts</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {podcasts.map((podcast) => (
                        <a
                          key={podcast.id}
                          href={podcast.link_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="podcast-sidebar-card"
                        >
                          <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                            {podcast.image_url && (
                              <div style={{
                                flexShrink: 0,
                                width: '56px',
                                height: '56px',
                                borderRadius: 'var(--radius-sm)',
                                overflow: 'hidden',
                                background: 'var(--color-border)',
                              }}>
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img
                                  src={podcast.image_url.startsWith('/') ? `${process.env.NEXT_PUBLIC_API_URL || ''}${podcast.image_url}` : podcast.image_url}
                                  alt=""
                                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                  loading="lazy"
                                />
                              </div>
                            )}
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{
                                fontSize: '0.6rem',
                                fontWeight: 700,
                                letterSpacing: '0.08em',
                                textTransform: 'uppercase',
                                color: 'var(--color-text-muted)',
                                marginBottom: '2px',
                              }}>
                                {podcast.show_name}
                              </div>
                              <div style={{
                                fontSize: '0.8rem',
                                fontWeight: 600,
                                lineHeight: 1.35,
                                color: 'var(--color-text)',
                              }}>
                                {podcast.episode_title.length > 80
                                  ? podcast.episode_title.substring(0, 80) + '...'
                                  : podcast.episode_title}
                              </div>
                            </div>
                          </div>
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* RIGHT COLUMN — Latest News */}
              <div className="right-column">
                {latestNews.length > 0 && (
                  <div className="sidebar-section">
                    <h3 className="sidebar-title">Latest News</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                      {latestNews.slice(0, 20).map((article) => (
                        <div
                          key={article.id}
                          style={{
                            padding: '8px 0',
                            borderBottom: '1px solid var(--color-border)',
                          }}
                        >
                          <div style={{
                            fontSize: '0.65rem',
                            color: 'var(--color-text-muted)',
                            marginBottom: '2px',
                          }}>
                            {article.publication_name}
                            {article.category && (
                              <span style={{
                                marginLeft: '6px',
                                padding: '0 4px',
                                fontSize: '0.58rem',
                                border: '1px solid var(--color-accent)',
                                borderRadius: '3px',
                                color: 'var(--color-accent)',
                              }}>
                                {article.category}
                              </span>
                            )}
                          </div>
                          <a
                            href={article.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover-link"
                            style={{
                              fontSize: '0.78rem',
                              fontWeight: 600,
                              lineHeight: 1.35,
                            }}
                          >
                            {article.headline || article.headline_en}
                          </a>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

            </div>
          </div>
        </section>
      )}

      {/* Newsletter CTA — slim */}
      <section style={{
        background: 'var(--color-primary)',
        color: 'var(--color-text-inverse)',
        padding: '28px 0',
        textAlign: 'center',
      }}>
        <div className="container" style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-4)',
        }}>
          <p style={{
            fontSize: '0.95rem',
            fontWeight: 600,
            margin: 0,
          }}>
            Never miss a geopolitical shift —{' '}
            <span style={{ color: 'var(--color-accent)' }}>join professionals who start their day with GeoMemo</span>
          </p>
          <Link href="/newsletter" className="btn-primary" style={{
            fontSize: '0.8rem',
            padding: '10px 24px',
          }}>
            Subscribe Free
          </Link>
        </div>
      </section>
    </>
  );
}
