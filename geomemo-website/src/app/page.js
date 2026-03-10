import Link from 'next/link';
import { fetchWebsiteFeed, fetchSponsors, fetchPodcasts, fetchNewestUpdates, fetchEvents } from '@/lib/api';
import ArticleCluster from '@/components/ArticleCluster';
import SubscribeForm from '@/components/SubscribeForm';

export const dynamic = 'force-dynamic';

function getTimeAgo(dateStr) {
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHrs = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHrs < 24) return `${diffHrs} hour${diffHrs === 1 ? '' : 's'} ago`;
    if (diffDays === 1) return 'yesterday';
    return `${diffDays} days ago`;
  } catch {
    return '';
  }
}

function stripHtml(str) {
  if (!str) return '';
  return str.replace(/<[^>]*>/g, '').trim();
}

function extractYouTubeId(url) {
  if (!url) return '';
  const match = url.match(/(?:v=|\/embed\/|youtu\.be\/)([\w-]{11})/);
  return match ? match[1] : '';
}

export default async function Home() {
  const [feed, sponsors, podcasts, latestNews, events] = await Promise.all([
    fetchWebsiteFeed(),
    fetchSponsors(),
    fetchPodcasts(),
    fetchNewestUpdates(),
    fetchEvents(),
  ]);

  const { top_stories = [], main_stories: rawMainStories = [], more_news: rawMoreNews = [] } = feed;

  // Cap total articles in the main column; excess flows to "More News"
  const MAIN_COLUMN_MAX = 20;
  const mainBudget = Math.max(0, MAIN_COLUMN_MAX - top_stories.length);
  const main_stories = rawMainStories.slice(0, mainBudget);
  const overflowStories = rawMainStories.slice(mainBudget);
  const more_news = [...overflowStories, ...rawMoreNews];

  const hasContent = top_stories.length > 0 || main_stories.length > 0;

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
      {/* Hero — ultra-slim banner, no Subscribe button */}
      <section style={{
        background: 'var(--color-primary)',
        color: 'var(--color-text-inverse)',
        padding: '12px 0',
      }}>
        <div className="container" style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '8px',
        }}>
          <div>
            <p style={{
              fontSize: '0.65rem',
              fontWeight: 600,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              color: 'var(--color-accent)',
              marginBottom: '2px',
            }}>
              {today}
            </p>
            <h1 style={{
              fontSize: 'clamp(1rem, 2.5vw, 1.3rem)',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              margin: 0,
            }}>
              Geopolitical Intelligence for{' '}
              <span style={{ color: 'var(--color-accent)' }}>Global Decision Makers</span>
            </h1>
          </div>
          {/* Newsletter callout — inside hero, below Subscribe button */}
          <Link href="/newsletter" className="newsletter-callout">
            Get our Daily Newsletter and never miss a story!
          </Link>
        </div>
      </section>

      {!hasContent ? (
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
        <section style={{ padding: 'var(--space-4) 0 var(--space-12)' }}>
          <div className="container">

            <div className="homepage-grid">

              {/* LEFT COLUMN — Main News (flat: Top News → Main Stories, no categories) */}
              <div className="main-column">

                {/* Top News */}
                {top_stories.length > 0 && (
                  <div style={{ marginBottom: 'var(--space-8)' }}>
                    <h2 className="section-title" style={{ marginBottom: 'var(--space-4)' }}>Top News</h2>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
                      {top_stories.map((article) => (
                        <ArticleCluster
                          key={article.id}
                          parent={article}
                          relatedArticles={[]}
                          relatedSources={[]}
                          matchedTweets={[]}
                          isTopStory={true}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Main Stories — flat list, no category headers */}
                {main_stories.length > 0 && (
                  <div style={{ marginBottom: 'var(--space-8)' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
                      {main_stories.map((article) => (
                        <ArticleCluster
                          key={article.id}
                          parent={article}
                          relatedArticles={[]}
                          relatedSources={article.related_sources || []}
                          matchedTweets={article.matched_tweets || []}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* RIGHT SIDE WRAPPER — stacks WorldMonitor → sidebars → calendar */}
              <div className="right-side-wrapper">

              {/* WORLDMONITOR — live map embed */}
              <div className="worldmonitor-section">
                <h3 className="sidebar-title" style={{ marginBottom: 'var(--space-3)' }}>
                  Monitor the World Live —{' '}
                  <a href="https://monitor.geomemo.news" target="_blank" rel="noopener noreferrer"
                     style={{ color: 'var(--color-accent)', textDecoration: 'none', fontWeight: 600 }}>
                    powered by WorldMonitor
                  </a>
                </h3>
                <a href="https://monitor.geomemo.news" target="_blank" rel="noopener noreferrer"
                   style={{
                     display: 'block',
                     position: 'relative',
                     width: '100%',
                     height: '480px',
                     overflow: 'hidden',
                     borderRadius: 'var(--radius-sm)',
                   }}>
                  <iframe
                    src="https://monitor.geomemo.news"
                    title="WorldMonitor Live Map"
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '300%',
                      height: '300%',
                      transform: 'scale(0.333)',
                      transformOrigin: 'top left',
                      border: 'none',
                      pointerEvents: 'none',
                    }}
                    loading="lazy"
                  />
                </a>
              </div>

              {/* MIDDLE + RIGHT ROW — sidebars side-by-side */}
              <div className="middle-right-row">

              {/* MIDDLE COLUMN — Sponsors + Podcasts (with background) */}
              <div className="middle-column middle-column-bg">

                {/* Sponsor Posts — charcoal fonts, no gold */}
                {sponsors.length > 0 && (
                  <div>
                    <h3 className="sidebar-title">Featured Think Tanks</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                      {sponsors.slice(0, 5).map((sponsor) => (
                        <a
                          key={sponsor.id}
                          href={sponsor.link_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="sponsor-item"
                        >
                          <div style={{
                            fontSize: '0.65rem',
                            fontWeight: 700,
                            letterSpacing: '0.06em',
                            textTransform: 'uppercase',
                            color: 'var(--color-text-muted)',
                            marginBottom: '3px',
                          }}>
                            {sponsor.company_name}
                          </div>
                          <div style={{
                            fontSize: '0.88rem',
                            fontWeight: 700,
                            lineHeight: 1.35,
                            color: 'var(--color-text)',
                            marginBottom: '4px',
                          }}>
                            {sponsor.headline}
                          </div>
                          <div style={{
                            fontSize: '0.75rem',
                            color: 'var(--color-text-secondary)',
                            lineHeight: 1.55,
                          }}>
                            {sponsor.summary.length > 150
                              ? sponsor.summary.substring(0, 150) + '...'
                              : sponsor.summary}
                          </div>
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Featured Podcasts — charcoal fonts */}
                {podcasts.length > 0 && (
                  <div>
                    <h3 className="sidebar-title">Featured Podcasts</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {podcasts.slice(0, 5).map((podcast) => {
                        const youtubeId = podcast.video_url ? extractYouTubeId(podcast.video_url) : '';
                        return (
                          <div key={podcast.id} className="podcast-card">
                            {/* YouTube embed if video_url present */}
                            {youtubeId ? (
                              <div style={{ marginBottom: '8px' }}>
                                <iframe
                                  width="100%"
                                  height="160"
                                  src={`https://www.youtube.com/embed/${youtubeId}`}
                                  frameBorder="0"
                                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                  allowFullScreen
                                  style={{ borderRadius: 'var(--radius-sm)' }}
                                  loading="lazy"
                                />
                              </div>
                            ) : null}
                            <a
                              href={podcast.link_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ textDecoration: 'none', color: 'inherit' }}
                            >
                              <div style={{ overflow: 'hidden' }}>
                                {!youtubeId && podcast.image_url && (
                                  // eslint-disable-next-line @next/next/no-img-element
                                  <img
                                    src={podcast.image_url.startsWith('/') ? `${process.env.NEXT_PUBLIC_API_URL || ''}${podcast.image_url}` : podcast.image_url}
                                    alt=""
                                    style={{
                                      float: 'right',
                                      width: '88px',
                                      height: '88px',
                                      objectFit: 'cover',
                                      borderRadius: 'var(--radius-sm)',
                                      marginLeft: '10px',
                                      marginBottom: '4px',
                                    }}
                                    loading="lazy"
                                  />
                                )}
                                <div style={{
                                  fontSize: '0.72rem',
                                  color: 'var(--color-text-secondary)',
                                  marginBottom: '3px',
                                }}>
                                  {podcast.show_name}:
                                </div>
                                <div style={{
                                  fontSize: '0.88rem',
                                  fontWeight: 700,
                                  lineHeight: 1.35,
                                  color: 'var(--color-text)',
                                  marginBottom: '6px',
                                }}>
                                  {podcast.episode_title}
                                </div>
                                <div style={{
                                  fontSize: '0.72rem',
                                  color: 'var(--color-text-secondary)',
                                  lineHeight: 1.5,
                                }}>
                                  {podcast.description
                                    ? (podcast.description.length > 120
                                        ? podcast.description.substring(0, 120) + '...'
                                        : podcast.description)
                                    : `Listen to ${podcast.show_name} for insightful analysis and discussion.`}
                                </div>
                              </div>
                              <div style={{
                                clear: 'both',
                                fontSize: '0.7rem',
                                color: 'var(--color-text-secondary)',
                                fontWeight: 600,
                                marginTop: '8px',
                                paddingTop: '6px',
                                borderTop: '1px solid var(--color-border)',
                              }}>
                                Subscribe to {podcast.show_name}.
                              </div>
                            </a>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* RIGHT COLUMN — Latest News (charcoal fonts) */}
              <div className="right-column">
                {latestNews.length > 0 && (
                  <div>
                    <h3 className="sidebar-title">Latest News</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                      {latestNews.slice(0, 15).map((article) => (
                        <div
                          key={article.id}
                          style={{
                            padding: '8px 0',
                            borderBottom: '1px solid var(--color-border)',
                          }}
                        >
                          <div style={{
                            fontSize: '0.72rem',
                            fontWeight: 600,
                            color: 'var(--color-text)',
                            marginBottom: '2px',
                          }}>
                            {article.author ? (
                              <>{article.author} / {article.publication_name}:</>
                            ) : (
                              <>{article.publication_name}:</>
                            )}
                          </div>
                          <a
                            href={article.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="latest-news-link"
                          >
                            {article.summary
                              ? (() => { const s = stripHtml(article.summary); return s.length > 180 ? s.substring(0, 180) + '...' : s; })()
                              : (article.headline_en || article.headline || '')}
                          </a>
                          {article.scraped_at && (
                            <div style={{
                              fontSize: '0.62rem',
                              color: 'var(--color-text-muted)',
                              marginTop: '3px',
                            }}>
                              {getTimeAgo(article.scraped_at)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              </div>{/* end middle-right-row */}

              {/* EVENTS CALENDAR */}
              <div className="events-calendar-section">
                <h2 className="section-title" style={{ marginBottom: 'var(--space-3)', fontSize: '0.95rem' }}>
                  Upcoming Geopolitical Events
                </h2>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    fontSize: '0.78rem',
                  }}>
                    <thead>
                      <tr style={{
                        borderBottom: '2px solid var(--color-border)',
                      }}>
                        <th style={{ textAlign: 'left', padding: '6px 8px 6px 0', fontWeight: 700, color: 'var(--color-text-secondary)', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>Date</th>
                        <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 700, color: 'var(--color-text-secondary)', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Event</th>
                        <th style={{ textAlign: 'left', padding: '6px 0 6px 8px', fontWeight: 700, color: 'var(--color-text-secondary)', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Location</th>
                      </tr>
                    </thead>
                    <tbody>
                      {/* Real event rows */}
                      {events.slice(0, 20).map((event) => {
                        const startDate = new Date(event.start_date);
                        const dateStr = startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                        return (
                          <tr key={event.id} style={{
                            borderBottom: '1px solid var(--color-border)',
                          }}>
                            <td style={{
                              padding: '6px 8px 6px 0',
                              fontWeight: 600,
                              color: 'var(--color-accent)',
                              whiteSpace: 'nowrap',
                              fontSize: '0.75rem',
                            }}>
                              {dateStr}
                            </td>
                            <td style={{ padding: '6px 8px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                                {event.url ? (
                                  <a href={event.url} target="_blank" rel="noopener noreferrer" className="hover-link" style={{ fontWeight: 600, fontSize: '0.78rem' }}>
                                    {event.title}
                                  </a>
                                ) : (
                                  <span style={{ fontWeight: 600, color: 'var(--color-text)', fontSize: '0.78rem' }}>{event.title}</span>
                                )}
                                {event.is_featured && event.register_url && (
                                  <a
                                    href={event.register_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                      fontSize: '0.55rem',
                                      fontWeight: 700,
                                      padding: '1px 6px',
                                      borderRadius: '999px',
                                      background: 'var(--color-accent)',
                                      color: 'var(--color-primary)',
                                      textDecoration: 'none',
                                      letterSpacing: '0.04em',
                                      textTransform: 'uppercase',
                                      whiteSpace: 'nowrap',
                                    }}
                                  >
                                    Register Now
                                  </a>
                                )}
                              </div>
                            </td>
                            <td style={{
                              padding: '6px 0 6px 8px',
                              color: 'var(--color-text-secondary)',
                              fontSize: '0.72rem',
                            }}>
                              {event.location || ''}
                            </td>
                          </tr>
                        );
                      })}
                      {/* Pad remaining rows to always total 20 */}
                      {Array.from({ length: Math.max(0, 20 - events.length) }, (_, i) => (
                        <tr key={`empty-${i}`} style={{
                          borderBottom: '1px solid var(--color-border)',
                          opacity: events.length === 0 && i === 0 ? 1 : Math.max(0.15, 1 - i * 0.045),
                        }}>
                          <td style={{
                            padding: '6px 8px 6px 0',
                            fontWeight: 600,
                            color: 'var(--color-text-muted)',
                            whiteSpace: 'nowrap',
                            fontSize: '0.75rem',
                          }}>
                            {events.length === 0 && i === 0 ? '—' : ''}
                          </td>
                          <td style={{ padding: '6px 8px' }}>
                            {events.length === 0 && i === 0 ? (
                              <span style={{
                                fontSize: '0.78rem',
                                color: 'var(--color-text-muted)',
                                fontStyle: 'italic',
                              }}>
                                Events will appear here as they are added.
                              </span>
                            ) : (
                              <div style={{
                                height: '6px',
                                background: 'var(--color-border)',
                                borderRadius: '3px',
                                width: `${35 + ((i * 37) % 45)}%`,
                                opacity: 0.3,
                              }} />
                            )}
                          </td>
                          <td style={{ padding: '6px 0 6px 8px' }}>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {/* Footer links */}
                <div style={{
                  display: 'flex',
                  gap: 'var(--space-3)',
                  marginTop: 'var(--space-3)',
                  fontSize: '0.72rem',
                  flexWrap: 'wrap',
                }}>
                  <Link href="/events" className="hover-link" style={{ fontWeight: 600, color: 'var(--color-accent)' }}>
                    View all events
                  </Link>
                  <Link href="/calendar" className="hover-link" style={{ fontWeight: 600, color: 'var(--color-accent)' }}>
                    Add to your calendar
                  </Link>
                  <Link href="/advertise" className="hover-link" style={{ fontWeight: 600, color: 'var(--color-accent)' }}>
                    Add your event here
                  </Link>
                </div>
              </div>

              </div>{/* end right-side-wrapper */}

            </div>
          </div>
        </section>
      )}

      {/* More News — two-column section below calendar */}
      {more_news.length > 0 && (
        <section style={{
          padding: '0 0 var(--space-12)',
        }}>
          <div className="container">
            <div style={{
              borderTop: '2px solid var(--color-border)',
              paddingTop: 'var(--space-6)',
            }}>
              <h2 className="section-title" style={{ marginBottom: 'var(--space-4)' }}>More News</h2>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                gap: 'var(--space-6)',
              }}>
                {/* Left column */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                  {more_news.slice(0, Math.ceil(more_news.length / 2)).map((article) => (
                    <ArticleCluster
                      key={article.id}
                      parent={article}
                      relatedArticles={[]}
                      relatedSources={[]}
                      matchedTweets={[]}
                    />
                  ))}
                </div>
                {/* Right column */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                  {more_news.slice(Math.ceil(more_news.length / 2)).map((article) => (
                    <ArticleCluster
                      key={article.id}
                      parent={article}
                      relatedArticles={[]}
                      relatedSources={[]}
                      matchedTweets={[]}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Newsletter CTA — inline subscribe form */}
      <section style={{
        background: 'var(--color-primary)',
        color: 'var(--color-text-inverse)',
        padding: '32px 0',
        textAlign: 'center',
      }}>
        <div className="container" style={{ maxWidth: '640px' }}>
          <p style={{
            fontSize: '0.95rem',
            fontWeight: 600,
            margin: 0,
            marginBottom: 'var(--space-4)',
          }}>
            Never miss a geopolitical shift —{' '}
            <span style={{ color: 'var(--color-accent)' }}>join professionals who start their day with GeoMemo</span>
          </p>
          <div style={{ maxWidth: '440px', margin: '0 auto' }}>
            <SubscribeForm variant="compact" darkBackground={true} />
          </div>
        </div>
      </section>
    </>
  );
}
