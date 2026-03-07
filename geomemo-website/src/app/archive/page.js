'use client';

import { useState, useEffect } from 'react';

export default function ArchivePage() {
  const [archives, setArchives] = useState([]);
  const [expandedDate, setExpandedDate] = useState(null);
  const [loading, setLoading] = useState(true);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_URL}/newsletter/archive`);
        if (res.ok) {
          const data = await res.json();
          setArchives(data);
        }
      } catch (err) {
        console.error('Failed to load archives:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [API_URL]);

  // Group by month/year
  const grouped = {};
  archives.forEach((item) => {
    const date = new Date(item.date);
    const key = date.toLocaleDateString('en-US', { year: 'numeric', month: 'long' });
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(item);
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
            Archive
          </p>
          <h1 style={{
            fontSize: 'clamp(1.5rem, 3vw, 2rem)',
            fontWeight: 800,
            letterSpacing: '-0.02em',
          }}>
            Past Briefings
          </h1>
        </div>
      </section>

      {/* Archive list */}
      <section className="section">
        <div className="container" style={{ maxWidth: '800px' }}>
          {loading ? (
            <p style={{ textAlign: 'center', color: 'var(--color-text-secondary)' }}>Loading archives...</p>
          ) : archives.length === 0 ? (
            <p style={{ textAlign: 'center', color: 'var(--color-text-secondary)' }}>
              No archived briefings yet. Archives will appear here as newsletters are published.
            </p>
          ) : (
            Object.entries(grouped).map(([monthYear, items]) => (
              <div key={monthYear} style={{ marginBottom: 'var(--space-8)' }}>
                <h2 style={{
                  fontSize: '1.1rem',
                  fontWeight: 700,
                  color: 'var(--color-accent)',
                  marginBottom: 'var(--space-4)',
                  paddingBottom: 'var(--space-2)',
                  borderBottom: '2px solid var(--color-border)',
                }}>
                  {monthYear}
                </h2>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {items.map((item) => {
                    const isExpanded = expandedDate === item.date;
                    const dateStr = new Date(item.date).toLocaleDateString('en-US', {
                      weekday: 'long',
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    });

                    return (
                      <div key={item.date} style={{
                        borderBottom: '1px solid var(--color-border)',
                      }}>
                        <button
                          onClick={() => setExpandedDate(isExpanded ? null : item.date)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            width: '100%',
                            padding: 'var(--space-4) 0',
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            fontSize: '0.95rem',
                            fontWeight: 600,
                            color: 'var(--color-text)',
                            textAlign: 'left',
                          }}
                        >
                          <span>{dateStr}</span>
                          <span style={{
                            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                            transition: 'transform 0.2s',
                            fontSize: '0.8rem',
                          }}>
                            ▼
                          </span>
                        </button>

                        {isExpanded && item.html && (
                          <div
                            style={{
                              padding: 'var(--space-4) var(--space-4) var(--space-6)',
                              fontSize: '0.875rem',
                              lineHeight: 1.7,
                            }}
                            dangerouslySetInnerHTML={{ __html: item.html }}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </>
  );
}
