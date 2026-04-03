/* eslint-disable @next/next/no-img-element */
import Link from 'next/link';
import { fetchCountryArticles } from '@/lib/api';
import { getCountryName } from '@/lib/countries';

export const dynamic = 'force-dynamic';

const CATEGORY_COLORS = {
  'Geopolitical Conflict': '#DC2626',
  'Geopolitical Economics': '#C9A84C',
  'Global Markets': '#3B82F6',
  'International Relations': '#0EA5E9',
  'Geopolitical Politics': '#8B5CF6',
  'GeoNatDisaster': '#EF4444',
  'GeoLocal': '#6B7280',
  'Other': '#9CA3AF',
};

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const date = new Date(dateStr);
  const diff = Math.floor((now - date) / 1000);
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export async function generateMetadata({ params }) {
  const { code } = await params;
  const name = getCountryName(code);
  return {
    title: `${name} — GeoMemo`,
    description: `Latest geopolitical news and intelligence about ${name} from GeoMemo.`,
  };
}

export default async function CountryPage({ params }) {
  const { code } = await params;
  const upperCode = code.toUpperCase();
  const countryName = getCountryName(upperCode);
  const data = await fetchCountryArticles(upperCode, 14, 15);
  const categories = data.categories || {};
  const totalArticles = data.total || 0;

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 var(--space-6)' }}>
      {/* Breadcrumb */}
      <div style={{ padding: 'var(--space-4) 0', fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
        <Link href="/" style={{ color: 'var(--color-accent)', textDecoration: 'none' }}>Home</Link>
        {' › '}
        <Link href="/country" style={{ color: 'var(--color-accent)', textDecoration: 'none' }}>Countries</Link>
        {' › '}
        <span style={{ color: 'var(--color-text-primary)' }}>{countryName}</span>
      </div>

      {/* Header */}
      <div style={{
        borderBottom: '3px solid var(--color-accent)',
        paddingBottom: 'var(--space-4)',
        marginBottom: 'var(--space-8)',
      }}>
        <h1 style={{
          fontSize: 'clamp(1.8rem, 4vw, 2.5rem)',
          fontWeight: 800,
          color: 'var(--color-text-primary)',
          letterSpacing: '-0.02em',
          margin: 0,
        }}>
          {countryName}
        </h1>
        <p style={{
          fontSize: '0.95rem',
          color: 'var(--color-text-secondary)',
          marginTop: 'var(--space-2)',
        }}>
          {totalArticles} articles in the last 14 days
        </p>
      </div>

      {/* No articles */}
      {totalArticles === 0 && (
        <div style={{ textAlign: 'center', padding: 'var(--space-16) 0', color: 'var(--color-text-muted)' }}>
          <p style={{ fontSize: '1.1rem' }}>No recent articles found for {countryName}.</p>
          <Link href="/country" style={{ color: 'var(--color-accent)', textDecoration: 'underline', marginTop: 'var(--space-4)', display: 'inline-block' }}>
            Browse all countries
          </Link>
        </div>
      )}

      {/* Category sections */}
      {Object.entries(categories).map(([category, articles]) => (
        <div key={category} style={{ marginBottom: 'var(--space-10)' }}>
          {/* Category header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-3)',
            borderBottom: `2px solid ${CATEGORY_COLORS[category] || '#E5E7EB'}`,
            paddingBottom: 'var(--space-2)',
            marginBottom: 'var(--space-5)',
          }}>
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '1.5px',
              color: CATEGORY_COLORS[category] || 'var(--color-text-secondary)',
            }}>
              {category}
            </span>
            <span style={{
              fontSize: '0.75rem',
              color: 'var(--color-text-muted)',
            }}>
              {articles.length} {articles.length === 1 ? 'article' : 'articles'}
            </span>
          </div>

          {/* Articles grid — 2 columns on desktop */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 400px), 1fr))',
            gap: 'var(--space-5)',
          }}>
            {articles.map((article) => (
              <article key={article.id} style={{
                borderBottom: '1px solid var(--color-border)',
                paddingBottom: 'var(--space-4)',
              }}>
                <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
                  {/* Text content */}
                  <div style={{ flex: 1 }}>
                    {/* Headline */}
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: '0.95rem',
                        fontWeight: 700,
                        color: 'var(--color-text-primary)',
                        textDecoration: 'none',
                        lineHeight: 1.35,
                        display: 'block',
                      }}
                    >
                      {article.headline || article.headline_original}
                    </a>

                    {/* Summary + inline attribution + timestamp */}
                    <div style={{
                      fontSize: '0.85rem',
                      color: 'var(--color-text-secondary)',
                      lineHeight: 1.5,
                      marginTop: 'var(--space-1)',
                    }}>
                      {article.summary && article.summary !== 'Pending review.' && (
                        <span>{article.summary} </span>
                      )}
                      <span style={{
                        fontSize: '0.78rem',
                        color: 'var(--color-text-muted)',
                      }}>
                        {article.author
                          ? `(${article.author} / ${article.publication_name})`
                          : `(${article.publication_name})`
                        }
                        {' · '}
                        {timeAgo(article.scraped_at)}
                      </span>
                    </div>
                  </div>

                  {/* OG Image */}
                  {article.og_image && (
                    <div style={{ flexShrink: 0 }}>
                      <img
                        src={article.og_image}
                        alt=""
                        loading="lazy"
                        style={{
                          width: 120,
                          height: 80,
                          objectFit: 'cover',
                          borderRadius: 'var(--radius)',
                        }}
                      />
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
