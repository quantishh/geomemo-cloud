import Link from 'next/link';
import { fetchEvents } from '@/lib/api';

export const metadata = {
  title: 'Calendar — GeoMemo',
  description: 'Add upcoming geopolitical events to your calendar. Google Calendar, Apple Calendar, and Outlook support.',
};

export const dynamic = 'force-dynamic';

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

function toICSDate(dateStr) {
  // Convert YYYY-MM-DD to YYYYMMDD for all-day events
  return dateStr.replace(/-/g, '');
}

function generateGoogleCalendarUrl(event) {
  const start = toICSDate(event.start_date);
  // End date for Google Calendar all-day events needs to be the day AFTER
  const endDate = event.end_date || event.start_date;
  const end = new Date(endDate);
  end.setDate(end.getDate() + 1);
  const endStr = end.toISOString().slice(0, 10).replace(/-/g, '');

  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: event.title,
    dates: `${start}/${endStr}`,
    details: event.description || '',
    location: event.location || '',
  });

  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

function generateICSData(event) {
  const start = toICSDate(event.start_date);
  const endDate = event.end_date || event.start_date;
  const end = new Date(endDate);
  end.setDate(end.getDate() + 1);
  const endStr = end.toISOString().slice(0, 10).replace(/-/g, '');

  const ics = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//GeoMemo//Events//EN',
    'BEGIN:VEVENT',
    `DTSTART;VALUE=DATE:${start}`,
    `DTEND;VALUE=DATE:${endStr}`,
    `SUMMARY:${event.title}`,
    `DESCRIPTION:${(event.description || '').replace(/\n/g, '\\n')}`,
    `LOCATION:${event.location || ''}`,
    `URL:${event.url || ''}`,
    'END:VEVENT',
    'END:VCALENDAR',
  ].join('\r\n');

  return `data:text/calendar;charset=utf-8,${encodeURIComponent(ics)}`;
}

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

export default async function CalendarPage() {
  const events = await fetchEvents();

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
            Calendar
          </p>
          <h1 style={{
            fontSize: 'clamp(1.5rem, 3vw, 2rem)',
            fontWeight: 800,
            letterSpacing: '-0.02em',
            marginBottom: 'var(--space-3)',
          }}>
            Add Events to Your Calendar
          </h1>
          <p style={{
            fontSize: '0.95rem',
            color: 'rgba(255,255,255,0.6)',
            maxWidth: '500px',
            margin: '0 auto',
          }}>
            Add individual geopolitical events to Google Calendar, Apple Calendar, or Outlook.
          </p>
        </div>
      </section>

      {/* Events list with calendar buttons */}
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
                No upcoming events. Check back soon.
              </p>
              <Link href="/" className="btn-outline">
                Back to Home
              </Link>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {events.map((event) => (
                <div
                  key={event.id}
                  style={{
                    display: 'flex',
                    gap: 'var(--space-4)',
                    padding: 'var(--space-4) 0',
                    borderBottom: '1px solid var(--color-border)',
                    alignItems: 'flex-start',
                    flexWrap: 'wrap',
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
                  <div style={{ flex: 1, minWidth: '200px' }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--space-2)',
                      marginBottom: '4px',
                      flexWrap: 'wrap',
                    }}>
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

                    {event.location && (
                      <p style={{
                        fontSize: '0.8rem',
                        color: 'var(--color-text-secondary)',
                        margin: '0 0 4px',
                      }}>
                        {event.location}
                      </p>
                    )}

                    {event.description && (
                      <p style={{
                        fontSize: '0.8rem',
                        color: 'var(--color-text-muted)',
                        lineHeight: 1.5,
                        margin: '0 0 8px',
                      }}>
                        {event.description}
                      </p>
                    )}

                    {/* Calendar buttons */}
                    <div style={{
                      display: 'flex',
                      gap: '8px',
                      flexWrap: 'wrap',
                    }}>
                      <a
                        href={generateGoogleCalendarUrl(event)}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          fontSize: '0.68rem',
                          fontWeight: 600,
                          padding: '4px 10px',
                          borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--color-border)',
                          color: 'var(--color-text-secondary)',
                          textDecoration: 'none',
                          transition: 'border-color 0.15s',
                        }}
                      >
                        + Google Calendar
                      </a>
                      <a
                        href={generateICSData(event)}
                        download={`geomemo-${event.title.toLowerCase().replace(/\s+/g, '-').slice(0, 30)}.ics`}
                        style={{
                          fontSize: '0.68rem',
                          fontWeight: 600,
                          padding: '4px 10px',
                          borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--color-border)',
                          color: 'var(--color-text-secondary)',
                          textDecoration: 'none',
                          transition: 'border-color 0.15s',
                        }}
                      >
                        + Apple / Outlook
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Back link */}
          <div style={{
            textAlign: 'center',
            marginTop: 'var(--space-10)',
          }}>
            <Link href="/events" className="btn-outline" style={{ marginRight: '12px' }}>
              Full Events Page
            </Link>
            <Link href="/" className="btn-outline">
              Back to Home
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
