import { fetchNewestUpdates } from '@/lib/api';

export default async function NewestUpdates() {
  const updates = await fetchNewestUpdates();

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        marginBottom: 'var(--space-6)',
      }}>
        <h2 style={{ fontSize: '1.35rem', fontWeight: 700 }}>Latest Intelligence</h2>
        <div className="accent-bar" />
      </div>

      {updates.length === 0 ? (
        <p style={{
          fontSize: '0.875rem',
          color: 'var(--color-text-secondary)',
        }}>
          Latest updates will appear here after the next data refresh.
        </p>
      ) : (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 0,
        }}>
          {updates.slice(0, 20).map((article) => (
            <div
              key={article.id}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 'var(--space-3)',
                padding: 'var(--space-3) 0',
                borderBottom: '1px solid var(--color-border)',
              }}
            >
              {/* Score indicator */}
              <div style={{
                flexShrink: 0,
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                background: article.auto_approval_score >= 85
                  ? 'var(--color-accent)'
                  : 'var(--color-border)',
                color: article.auto_approval_score >= 85
                  ? 'var(--color-primary)'
                  : 'var(--color-text-secondary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.7rem',
                fontWeight: 700,
              }}>
                {article.auto_approval_score}
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                {/* Source + Category */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-2)',
                  marginBottom: '2px',
                  flexWrap: 'wrap',
                }}>
                  <span style={{
                    fontSize: '0.7rem',
                    color: 'var(--color-text-secondary)',
                    fontWeight: 500,
                  }}>
                    {article.publication_name}
                  </span>
                  {article.category && (
                    <span className="badge" style={{ fontSize: '0.6rem', padding: '1px 6px' }}>
                      {article.category}
                    </span>
                  )}
                </div>

                {/* Headline */}
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover-link"
                  style={{
                    fontSize: '0.875rem',
                    fontWeight: 600,
                    lineHeight: 1.4,
                  }}
                >
                  {article.headline_en || article.headline}
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
