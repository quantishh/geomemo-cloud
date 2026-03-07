import Link from 'next/link';
import { fetchEvents } from '@/lib/api';

export const metadata = {
  title: 'Events — GeoMemo',
  description: 'Upcoming geopolitical events, summits, conferences, and elections tracked by GeoMemo.',
};

export const dynamic = 'force-dynamic';

const categoryColors = {
  Summit: '#C9A84C',
  Conference: '#3B82F6',
  Election: '#DC2626',
  'UN Session': '#16A34A',
  'Trade Summit': '#8B5CF6',
  Military: '#EF4444',
  Diplomatic: '#0EA5E9',
  Other: '#6B7280',
};

function formatDateRange(start, end) {
  const startDate = new Date(start);
  const opts = { month: 'short', day: 'numeric' };
  const yearOpts = { month: 'short', day: 'numeric', year: 'numeric' };

  if (!end || start === end) {
    return startDate.toLocaleDateString('en-US', yearOpts);
  }

  const endDate = new Date(end);
  if (startDate.getMonth() === endDate.getMonth() && startDate.getFullYear() === endDate.getFullYear()) {
    return `${startDate.toLocaleDateString('en-US', opts)}–${endDate.getDate()}, ${endDate.getFullYear()}`;
  }

  return `${startDate.toLocaleDateString('en-US', opts)} – ${endDate.toLocaleDateString('en-US', yearOpts)}`;
}

export default async function EventsPage() {
  const events = await fetchEvents();

  // Group events by month/year
  const grouped = {};
  events.forEach((event) => {
    const date = new Date(event.start_date);
    const key = date.toLocaleDateString('en-US', { year: 'numeric', month: 'long' });
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(event);
  });

  return (
    <>
      {/* Hero */}
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
            Events
          </p>
          <h1 style={{
            fontSize: 'clamp(1.5rem, 3vw, 2rem)',
            fontWeight: 800,
            letterSpacing: '-0.02em',
            marginBottom: 'var(--space-3)',
          }}>
            Geopolitical Calendar
          </h1>
          <p style={{
            fontSize: '0.95rem',
            color: 'rgba(255,255,255,0.6)',
            maxWidth: '500px',
            margin: '0 auto',
          }}>
            Summits, elections, conferences, and diplomatic milestones that shape global affairs.
          </p>
        </div>
      </section>

      {/* Events list */}
      <section className="section">
        <div className="container" style={{ maxWidth: '860px' }}>
          {events.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: 'var(--space-16) 0',
            }}>
              <p style={{
                fontSize: '1rem',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-6)',
              }}>
                No upcoming events listed yet. Events will be added as they are identified.
              </p>
              <Link href="/" className="btn-outline">
                Back to Briefings
              </Link>
            </div>
          ) : (
            Object.entries(grouped).map(([monthYear, items]) => (
              <div key={monthYear} style={{ marginBottom: 'var(--space-10)' }}>
                {/* Month header */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-3)',
                  marginBottom: 'var(--space-5)',
                  paddingBottom: 'var(--space-2)',
                  borderBottom: '2px solid var(--color-border)',
                }}>
                  <h2 style={{
                    fontSize: '1.15rem',
                    fontWeight: 700,
                    color: 'var(--color-accent)',
                  }}>
                    {monthYear}
                  </h2>
                  <span style={{
                    fontSize: '0.75rem',
                    color: 'var(--color-text-muted)',
                  }}>
                    {items.length} {items.length === 1 ? 'event' : 'events'}
                  </span>
                </div>

                {/* Event items */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {items.map((event) => (
                    <div
                      key={event.id}
                      style={{
                        display: 'flex',
                        gap: 'var(--space-4)',
                        padding: 'var(--space-4) 0',
                        borderBottom: '1px solid var(--color-border)',
                        alignItems: 'flex-start',
                      }}
                    >
                      {/* Date column */}
                      <div style={{
                        flexShrink: 0,
                        width: '130px',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        color: 'var(--color-accent)',
                        paddingTop: '2px',
                      }}>
                        {formatDateRange(event.start_date, event.end_date)}
                      </div>

                      {/* Event details */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 'var(--space-2)',
                          marginBottom: '4px',
                          flexWrap: 'wrap',
                        }}>
                          {/* Event title */}
                          {event.url ? (
                            <a
                              href={event.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                fontSize: '0.95rem',
                                fontWeight: 700,
                                color: 'var(--color-text)',
                                textDecoration: 'none',
                                transition: 'color 0.15s',
                              }}
                            >
                              {event.title}
                            </a>
                          ) : (
                            <span style={{
                              fontSize: '0.95rem',
                              fontWeight: 700,
                              color: 'var(--color-text)',
                            }}>
                              {event.title}
                            </span>
                          )}

                          {/* Category badge */}
                          {event.category && (
                            <span style={{
                              fontSize: '0.6rem',
                              fontWeight: 600,
                              padding: '1px 8px',
                              borderRadius: '999px',
                              border: `1px solid ${categoryColors[event.category] || categoryColors.Other}`,
                              color: categoryColors[event.category] || categoryColors.Other,
                              letterSpacing: '0.04em',
                              textTransform: 'uppercase',
                              whiteSpace: 'nowrap',
                            }}>
                              {event.category}
                            </span>
                          )}
                        </div>

                        {/* Location */}
                        {event.location && (
                          <p style={{
                            fontSize: '0.8rem',
                            color: 'var(--color-text-secondary)',
                            margin: '0 0 4px',
                          }}>
                            {event.location}
                          </p>
                        )}

                        {/* Description */}
                        {event.description && (
                          <p style={{
                            fontSize: '0.8rem',
                            color: 'var(--color-text-muted)',
                            lineHeight: 1.5,
                            margin: 0,
                          }}>
                            {event.description}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      {/* CTA */}
      <section style={{
        background: 'var(--color-surface)',
        padding: 'var(--space-12) 0',
        textAlign: 'center',
      }}>
        <div className="container">
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: 'var(--space-3)' }}>
            Get event coverage in your inbox
          </h2>
          <p style={{
            fontSize: '0.9rem',
            color: 'var(--color-text-secondary)',
            marginBottom: 'var(--space-6)',
          }}>
            Our daily briefing covers key developments from these events as they unfold.
          </p>
          <Link href="/newsletter" className="btn-primary" style={{ padding: '14px 32px' }}>
            Subscribe to Daily Briefing
          </Link>
        </div>
      </section>
    </>
  );
}
