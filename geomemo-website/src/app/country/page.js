import Link from 'next/link';
import { fetchCountryList } from '@/lib/api';

export const metadata = {
  title: 'Countries — GeoMemo',
  description: 'Browse geopolitical news by country. Coverage across 100+ nations tracked by GeoMemo.',
};

export const dynamic = 'force-dynamic';

// ISO country code to name + flag emoji
const COUNTRY_INFO = {
  US: { name: 'United States', flag: '🇺🇸' }, CN: { name: 'China', flag: '🇨🇳' },
  RU: { name: 'Russia', flag: '🇷🇺' }, IR: { name: 'Iran', flag: '🇮🇷' },
  IL: { name: 'Israel', flag: '🇮🇱' }, UA: { name: 'Ukraine', flag: '🇺🇦' },
  GB: { name: 'United Kingdom', flag: '🇬🇧' }, FR: { name: 'France', flag: '🇫🇷' },
  DE: { name: 'Germany', flag: '🇩🇪' }, JP: { name: 'Japan', flag: '🇯🇵' },
  KR: { name: 'South Korea', flag: '🇰🇷' }, KP: { name: 'North Korea', flag: '🇰🇵' },
  IN: { name: 'India', flag: '🇮🇳' }, PK: { name: 'Pakistan', flag: '🇵🇰' },
  SA: { name: 'Saudi Arabia', flag: '🇸🇦' }, AE: { name: 'UAE', flag: '🇦🇪' },
  TR: { name: 'Turkey', flag: '🇹🇷' }, EG: { name: 'Egypt', flag: '🇪🇬' },
  NG: { name: 'Nigeria', flag: '🇳🇬' }, ZA: { name: 'South Africa', flag: '🇿🇦' },
  BR: { name: 'Brazil', flag: '🇧🇷' }, MX: { name: 'Mexico', flag: '🇲🇽' },
  AU: { name: 'Australia', flag: '🇦🇺' }, CA: { name: 'Canada', flag: '🇨🇦' },
  TW: { name: 'Taiwan', flag: '🇹🇼' }, SY: { name: 'Syria', flag: '🇸🇾' },
  IQ: { name: 'Iraq', flag: '🇮🇶' }, AF: { name: 'Afghanistan', flag: '🇦🇫' },
  YE: { name: 'Yemen', flag: '🇾🇪' }, LB: { name: 'Lebanon', flag: '🇱🇧' },
  PS: { name: 'Palestine', flag: '🇵🇸' }, QA: { name: 'Qatar', flag: '🇶🇦' },
  JO: { name: 'Jordan', flag: '🇯🇴' }, LY: { name: 'Libya', flag: '🇱🇾' },
  SD: { name: 'Sudan', flag: '🇸🇩' }, ET: { name: 'Ethiopia', flag: '🇪🇹' },
  PL: { name: 'Poland', flag: '🇵🇱' }, GR: { name: 'Greece', flag: '🇬🇷' },
  IT: { name: 'Italy', flag: '🇮🇹' }, ES: { name: 'Spain', flag: '🇪🇸' },
  NL: { name: 'Netherlands', flag: '🇳🇱' }, SE: { name: 'Sweden', flag: '🇸🇪' },
  NO: { name: 'Norway', flag: '🇳🇴' }, FI: { name: 'Finland', flag: '🇫🇮' },
  CH: { name: 'Switzerland', flag: '🇨🇭' }, AT: { name: 'Austria', flag: '🇦🇹' },
  TH: { name: 'Thailand', flag: '🇹🇭' }, VN: { name: 'Vietnam', flag: '🇻🇳' },
  PH: { name: 'Philippines', flag: '🇵🇭' }, MY: { name: 'Malaysia', flag: '🇲🇾' },
  SG: { name: 'Singapore', flag: '🇸🇬' }, ID: { name: 'Indonesia', flag: '🇮🇩' },
  BD: { name: 'Bangladesh', flag: '🇧🇩' }, MM: { name: 'Myanmar', flag: '🇲🇲' },
  CO: { name: 'Colombia', flag: '🇨🇴' }, AR: { name: 'Argentina', flag: '🇦🇷' },
  VE: { name: 'Venezuela', flag: '🇻🇪' }, CL: { name: 'Chile', flag: '🇨🇱' },
  PE: { name: 'Peru', flag: '🇵🇪' }, CU: { name: 'Cuba', flag: '🇨🇺' },
  NZ: { name: 'New Zealand', flag: '🇳🇿' },
};

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
          const info = COUNTRY_INFO[country.code] || { name: country.code, flag: '🌐' };
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
              <span style={{ fontSize: '1.5rem' }}>{info.flag}</span>
              <div>
                <div style={{
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  color: 'var(--color-text-primary)',
                }}>
                  {info.name}
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
