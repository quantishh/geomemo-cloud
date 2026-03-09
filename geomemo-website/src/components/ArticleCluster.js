/* eslint-disable @next/next/no-img-element */

function stripHtml(str) {
  if (!str) return '';
  return str.replace(/<[^>]*>/g, '').trim();
}

export default function ArticleCluster({ parent, relatedArticles, isTopStory }) {
  const hasChildren = relatedArticles && relatedArticles.length > 0;
  const ogImage = parent.og_image;
  const tweets = parent.embedded_tweets;
  const hasTweets = tweets && tweets.length > 0;

  // Separator: "A and B" for 2, "A, B, and C" for 3+
  const listSep = (idx, total) => {
    if (idx >= total - 1) return '';
    if (total === 2) return ' and ';
    if (idx === total - 2) return ', and ';
    return ', ';
  };

  return (
    <article style={{
      paddingBottom: 'var(--space-5)',
      borderBottom: '1px solid var(--color-border)',
      ...(isTopStory ? { borderLeft: '3px solid var(--color-accent)', paddingLeft: 'var(--space-4)' } : {}),
    }}>
      {/* Source / Author — Techmeme style: "Author / Publication:" */}
      <div style={{ fontSize: '0.82rem', marginBottom: '2px' }}>
        {parent.author ? (
          <>
            <span>{parent.author}</span>
            {' / '}
            <span style={{ fontStyle: 'italic' }}>{parent.publication_name}</span>:
          </>
        ) : (
          <span style={{ fontWeight: 500 }}>{parent.publication_name}:</span>
        )}
      </div>

      {/* Summary displayed as headline + optional floating image */}
      <div style={{ overflow: 'hidden' }}>
        {ogImage && (
          <img
            src={ogImage}
            alt=""
            style={{
              float: 'right',
              width: '100px',
              height: '70px',
              objectFit: 'cover',
              marginLeft: '12px',
              marginBottom: '6px',
              borderRadius: '2px',
            }}
            loading="lazy"
          />
        )}
        <h3 style={{
          fontSize: isTopStory ? '1.15rem' : '1rem',
          fontWeight: 700,
          lineHeight: 1.35,
          margin: 0,
        }}>
          <a
            href={parent.url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover-link"
          >
            {stripHtml(parent.summary) || parent.headline_en || parent.headline}
          </a>
        </h3>
      </div>

      {/* Related: "More:" with publication name links */}
      {hasChildren && (
        <div style={{ marginTop: '6px', fontSize: '0.78rem', lineHeight: 1.6 }}>
          <span style={{ fontWeight: 700, color: 'var(--color-accent)' }}>More:</span>{' '}
          {relatedArticles.map((child, idx) => (
            <span key={child.id}>
              <a href={child.url} target="_blank" rel="noopener noreferrer" className="hover-link">
                {child.publication_name}
              </a>
              {listSep(idx, relatedArticles.length)}
            </span>
          ))}
        </div>
      )}

      {/* X discussions — logo inline with usernames, popup on hover */}
      {hasTweets && (
        <div style={{ marginTop: '2px', fontSize: '0.78rem', lineHeight: 1.8 }}>
          <span style={{ fontWeight: 700, color: 'var(--color-accent)', whiteSpace: 'nowrap' }}>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" style={{ display: 'inline', verticalAlign: '-1px', marginRight: '1px' }}>
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
            </svg>:</span>{' '}
          {tweets.map((tweet, idx) => (
            <span key={idx} className="tweet-hover-wrapper">
              <a href={tweet.url || '#'} target="_blank" rel="noopener noreferrer" className="hover-link">
                @{tweet.username}
              </a>
              {tweet.text && (
                <span className="tweet-popup">
                  <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--color-text)' }}>@{tweet.username}</strong>
                  {tweet.text.length > 280 ? tweet.text.substring(0, 280) + '...' : tweet.text}
                </span>
              )}
              {listSep(idx, tweets.length)}
              {idx === tweets.length - 1 && '.'}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}
