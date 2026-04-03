import Link from 'next/link';
import { fetchCountryList } from '@/lib/api';
import { getCountryName, getFlag } from '@/lib/countries';

export const metadata = {
  title: 'Countries — GeoMemo',
  description: 'Browse geopolitical news by country. Coverage across 100+ nations tracked by GeoMemo.',
};

export const dynamic = 'force-dynamic';

export default async function CountryIndexPage() {
  const countries = await fetchCountryList();

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 var(--space-6)' }}>
      {/* Header */}
      <div style={{
        borderBottom: '3px solid var(--color-accent)',
        paddingBottom: 'var(--space-4)',
        marginBottom: 'var(--space-8)',
        marginTop: 'var(--space-6)',
      }}>
        <h1 style={{
          fontSize: 'clamp(1.8rem, 4vw, 2.5rem)',
          fontWeight: 800,
          color: 'var(--color-text-primary)',
          letterSpacing: '-0.02em',
          margin: 0,
        }}>
          Countries
        </h1>
        <p style={{
          fontSize: '0.95rem',
          color: 'var(--color-text-secondary)',
          marginTop: 'var(--space-2)',
        }}>
          Browse geopolitical intelligence by country
        </p>
      </div>

      {/* Country grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
        gap: 'var(--space-4)',
        marginBottom: 'var(--space-16)',
      }}>
        {countries.map((country) => {
          const name = getCountryName(country.code);
          const flag = getFlag(country.code);
          return (
            <Link
              key={country.code}
              href={`/country/${country.code}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-3)',
                padding: 'var(--space-4) var(--space-5)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius)',
                textDecoration: 'none',
                transition: 'border-color 0.15s, box-shadow 0.15s',
              }}
            >
              <span style={{ fontSize: '1.5rem' }}>{flag}</span>
              <div>
                <div style={{
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  color: 'var(--color-text-primary)',
                }}>
                  {name}
                </div>
                <div style={{
                  fontSize: '0.78rem',
                  color: 'var(--color-text-muted)',
                }}>
                  {country.count} {country.count === 1 ? 'article' : 'articles'}
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      {countries.length === 0 && (
        <div style={{ textAlign: 'center', padding: 'var(--space-16) 0', color: 'var(--color-text-muted)' }}>
          <p>No country data available yet. Articles will appear once the scraper runs.</p>
        </div>
      )}
    </div>
  );
}
