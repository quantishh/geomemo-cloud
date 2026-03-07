export default function ArticleCluster({ parent, relatedArticles, isTopStory }) {
  const hasChildren = relatedArticles && relatedArticles.length > 0;
  const ogImage = parent.og_image;
  const tweets = parent.embedded_tweets;
  const hasTweets = tweets && tweets.length > 0;

  return (
    <article style={{
      paddingBottom: 'var(--space-5)',
      borderBottom: '1px solid var(--color-border)',
      ...(isTopStory ? { borderLeft: '3px solid var(--color-accent)', paddingLeft: 'var(--space-4)' } : {}),
    }}>
      {/* Source */}
      <div style={{
        fontSize: '0.75rem',
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
        fontSize: isTopStory ? '1.25rem' : '1.05rem',
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
        fontSize: isTopStory ? '0.88rem' : '0.84rem',
        color: 'var(--color-text-secondary)',
        lineHeight: 1.6,
        margin: 0,
      }}>
        {parent.summary}
      </p>

      {/* Embedded X Posts */}
      {hasTweets && (
        <div style={{
          marginTop: 'var(--space-3)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}>
          <span style={{
            fontSize: '0.72rem',
            fontWeight: 700,
            color: 'var(--color-text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
            Discussion:
          </span>
          {tweets.map((tweet, idx) => (
            <div key={idx} style={{
              fontSize: '0.78rem',
              lineHeight: 1.5,
              paddingLeft: 'var(--space-3)',
              borderLeft: '2px solid #1DA1F2',
              color: 'var(--color-text-secondary)',
            }}>
              {tweet.username && (
                <a
                  href={tweet.url || '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover-link"
                  style={{ fontWeight: 600, fontSize: '0.76rem' }}
                >
                  @{tweet.username}
                </a>
              )}
              {tweet.text && (
                <span style={{ display: 'block', marginTop: '2px', fontSize: '0.76rem' }}>
                  {tweet.text.length > 200 ? tweet.text.substring(0, 200) + '...' : tweet.text}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Related coverage (children) */}
      {hasChildren && (
        <div style={{ marginTop: 'var(--space-3)' }}>
          <span style={{
            fontSize: '0.72rem',
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
            {relatedArticles.map((child) => (
              <li key={child.id} style={{
                fontSize: '0.78rem',
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
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
