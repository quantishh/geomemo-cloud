export default function ArticleCluster({ parent, children }) {
  const hasChildren = children && children.length > 0;
  const ogImage = parent.og_image;

  return (
    <article style={{
      paddingBottom: 'var(--space-5)',
      borderBottom: '1px solid var(--color-border)',
    }}>
      {/* Parent article */}
      <div style={{
        display: 'flex',
        gap: 'var(--space-4)',
        alignItems: 'flex-start',
      }}>
        {/* Featured image (OG image) */}
        {ogImage && (
          <div style={{
            flexShrink: 0,
            width: '120px',
            height: '80px',
            borderRadius: 'var(--radius-sm)',
            overflow: 'hidden',
            background: 'var(--color-surface)',
          }}
            className="article-image"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={ogImage}
              alt=""
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
              }}
              loading="lazy"
            />
          </div>
        )}

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Source */}
          <div style={{
            fontSize: '0.8rem',
            color: 'var(--color-text-secondary)',
            marginBottom: '4px',
          }}>
            {parent.publication_name}
            {parent.author && (
              <span style={{ fontStyle: 'italic' }}> / {parent.author}</span>
            )}
          </div>

          {/* Headline */}
          <h3 style={{
            fontSize: '1.1rem',
            fontWeight: 700,
            lineHeight: 1.3,
            marginBottom: '6px',
          }}>
            <a
              href={parent.url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover-link"
            >
              {parent.headline_en || parent.headline}
            </a>
          </h3>

          {/* Summary */}
          <p style={{
            fontSize: '0.875rem',
            color: 'var(--color-text-secondary)',
            lineHeight: 1.6,
            margin: 0,
          }}>
            {parent.summary}
          </p>
        </div>
      </div>

      {/* Related coverage (children) */}
      {hasChildren && (
        <div style={{
          marginTop: 'var(--space-3)',
          paddingLeft: ogImage ? '136px' : '0',
        }}
          className="related-coverage"
        >
          <span style={{
            fontSize: '0.75rem',
            fontWeight: 700,
            color: 'var(--color-text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}>
            Related:
          </span>
          <ul style={{
            listStyle: 'none',
            padding: 0,
            margin: '6px 0 0 0',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}>
            {children.map((child) => (
              <li key={child.id} style={{
                fontSize: '0.8rem',
                lineHeight: 1.5,
                paddingLeft: 'var(--space-3)',
                borderLeft: '2px solid var(--color-border)',
              }}>
                <span style={{ color: 'var(--color-text-secondary)', fontWeight: 500 }}>
                  {child.publication_name}:
                </span>{' '}
                <a
                  href={child.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover-link"
                >
                  {child.headline_en || child.headline}
                </a>
                {child.summary && (
                  <span style={{
                    display: 'block',
                    fontSize: '0.75rem',
                    color: 'var(--color-text-muted)',
                    marginTop: '2px',
                  }}>
                    {child.summary}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
